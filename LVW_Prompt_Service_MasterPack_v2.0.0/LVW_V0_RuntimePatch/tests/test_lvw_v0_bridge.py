from __future__ import annotations

import json
from pathlib import Path
import sys
import unittest

PATCH_ROOT = Path(__file__).resolve().parents[1]
CUSTOM_NODES = PATCH_ROOT / "custom_nodes"
sys.path.insert(0, str(CUSTOM_NODES))

from lvw_v0_bridge import NODE_CLASS_MAPPINGS  # noqa: E402
from lvw_v0_bridge.core import BridgeError, FROZEN_ERROR_CODES, MAX_LONG_EDGE, MAX_NUM_CTX, MAX_NUM_PREDICT  # noqa: E402


class Frame:
    def __init__(self, label: str, height=120, width=160, channels=3):
        self.label = label
        self.shape = (height, width, channels)


def envelope(content, *, done=True, done_reason="stop"):
    return json.dumps({"message": {"role": "assistant", "content": content},
                       "done": done, "done_reason": done_reason})


def image_content(**overrides):
    value = {"observations": ["a red subject on a plain background"], "inferences": [],
             "unknowns": ["location is unknown"], "prompt": "red subject, plain background", "tags": ["red"]}
    value.update(overrides)
    return json.dumps(value)


def video_content(index: int, **overrides):
    value = {"observations": [f"frame {index} contains subject {index}"], "inferences": [],
             "unknowns": [], "prompt": f"ordered scene at frame {index}", "tags": [f"f{index}"],
             "change": "baseline frame" if index == 0 else f"subject changed to position {index}"}
    value.update(overrides)
    return json.dumps(value)


class FakeTransport:
    def __init__(self, responses=None, endpoint="http://127.0.0.1:11434/api/chat", chat_error=None,
                 cleanup_error=None):
        self.endpoint = endpoint
        self.responses = list(responses or [])
        self.chat_error = chat_error
        self.cleanup_error = cleanup_error
        self.chat_calls = []
        self.cleanup_calls = []

    def chat(self, payload, timeout_seconds):
        self.chat_calls.append((payload, timeout_seconds))
        if self.chat_error is not None:
            raise self.chat_error
        if not self.responses:
            raise AssertionError("unexpected model call")
        return self.responses.pop(0)

    def cleanup(self, model, timeout_seconds):
        self.cleanup_calls.append((model, timeout_seconds))
        if self.cleanup_error is not None:
            raise self.cleanup_error


def encoder(frame):
    return f"encoded-{frame.label}"


class PublicNodeOwnerTests(unittest.TestCase):
    image_cls = NODE_CLASS_MAPPINGS["LVWImagePromptBridge"]
    video_cls = NODE_CLASS_MAPPINGS["LVWVideoFramesPromptBridge"]

    @classmethod
    def setUpClass(cls):
        errors_path = PATCH_ROOT.parent / "contracts" / "errors.json"
        cls.frozen_error_codes = set(json.loads(errors_path.read_text(encoding="utf-8"))["codes"])

    def assert_code(self, code, callable_):
        with self.assertRaises(BridgeError) as caught:
            callable_()
        self.assertEqual(code, caught.exception.code)
        self.assertIn(caught.exception.code, self.frozen_error_codes)
        self.assertIsInstance(caught.exception.details.get("subcode"), str)
        return caught.exception

    def unpack(self, output):
        self.assertEqual({"ui", "result"}, set(output))
        self.assertEqual(2, len(output["result"]))
        self.assertEqual(list(output["result"]), output["ui"]["text"])
        return output["result"]

    def assert_prompt_spec_contract(self, value):
        contract_path = PATCH_ROOT.parent / "contracts" / "v0-result.schema.json"
        defs = json.loads(contract_path.read_text(encoding="utf-8"))["$defs"]
        spec = defs["PromptSpec"]
        self.assertEqual(set(spec["required"]), set(value))
        self.assertFalse(spec["additionalProperties"])
        self.assertEqual(set(defs["Domains"]["required"]), set(value["domains"]))
        self.assertEqual(set(defs["Technical"]["required"]), set(value["technical"]))

    def test_registration_exposes_real_public_node_owners(self):
        self.assertEqual({"LVWImagePromptBridge", "LVWVideoFramesPromptBridge", "LVWManualPromptOwner",
                          "LVWControlledImageInput", "LVWDraftStateOwner"},
                         set(NODE_CLASS_MAPPINGS))
        self.assertEqual("analyze", self.image_cls.FUNCTION)
        self.assertIs(self.image_cls.OUTPUT_NODE, True)
        self.assertIs(self.video_cls.OUTPUT_NODE, True)
        self.assertIn("image", self.image_cls.INPUT_TYPES()["required"])
        self.assertIn("frames", self.video_cls.INPUT_TYPES()["required"])

    def test_frozen_error_code_copy_exactly_matches_contract(self):
        self.assertEqual(self.frozen_error_codes, set(FROZEN_ERROR_CODES))

    def test_normal_image_through_public_owner(self):
        transport = FakeTransport([envelope(image_content())])
        node = self.image_cls(transport=transport, encoder=encoder)
        raw, suggestion_raw = self.unpack(node.analyze([Frame("image")], user_instruction="describe visible content"))
        self.assertEqual(envelope(image_content()), raw)
        suggestion = json.loads(suggestion_raw)
        self.assertEqual("lvw.prompt/1", suggestion["schema_version"])
        self.assertTrue(suggestion["domains"]["observation"])
        self.assert_prompt_spec_contract(suggestion)
        self.assertEqual(1, len(transport.chat_calls))
        self.assertEqual([("gemma4:26b", 120)], transport.cleanup_calls)
        payload = transport.chat_calls[0][0]
        self.assertFalse(payload["think"])
        self.assertEqual(0, payload["keep_alive"])
        self.assertEqual(MAX_NUM_CTX, payload["options"]["num_ctx"])
        self.assertEqual(MAX_NUM_PREDICT, payload["options"]["num_predict"])
        self.assertEqual(["encoded-image"], payload["messages"][0]["images"])

    def test_four_video_frames_are_called_in_order_and_cleaned_each_time(self):
        transport = FakeTransport([envelope(video_content(i)) for i in range(4)])
        node = self.video_cls(transport=transport, encoder=encoder)
        raw, suggestion_raw = self.unpack(node.analyze([Frame(str(i)) for i in range(4)]))
        self.assertEqual(4, len(transport.chat_calls))
        self.assertEqual(4, len(transport.cleanup_calls))
        self.assertEqual([[f"encoded-{i}"] for i in range(4)],
                         [call[0]["messages"][0]["images"] for call in transport.chat_calls])
        self.assertTrue(all(len(call[0]["messages"][0]["images"]) == 1 for call in transport.chat_calls))
        self.assertEqual(4, len(json.loads(raw)["frame_raw_responses"]))
        suggestion = json.loads(suggestion_raw)
        self.assertEqual(4, len(suggestion["domains"]["observation"]))
        self.assertIn("subject changed to position 3", suggestion["technical"]["camera_motion"])
        self.assert_prompt_spec_contract(suggestion)

    def test_public_owner_instruction_requires_grounded_non_copy_prompt(self):
        user_instruction = "focus on the subject's visible pose"
        transport = FakeTransport([envelope(video_content(0))])
        node = self.video_cls(transport=transport, encoder=encoder)
        self.unpack(node.analyze([Frame("0")], user_instruction=user_instruction))
        outgoing = transport.chat_calls[0][0]["messages"][0]["content"]
        normalized = outgoing.casefold()
        for required in (
            "prompt field must be a concrete generation prompt",
            "grounded only in visible facts from the current image or frame",
            "do not copy, quote, paraphrase, summarize, translate, or otherwise rewrite",
            "user instruction",
            "additional analysis constraint (not prompt content)",
        ):
            self.assertIn(required, normalized)
        self.assertIn(user_instruction, outgoing)
        self.assertEqual(1, outgoing.count(user_instruction))
        self.assertLess(outgoing.rfind(user_instruction),
                        outgoing.rfind("The prompt field must be a concrete generation prompt"))
        self.assertTrue(outgoing.endswith("instruction into the prompt field."))
        self.assertEqual(1, len(transport.chat_calls))
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_empty_observations_fail_closed_and_cleanup(self):
        transport = FakeTransport([envelope(image_content(observations=[]))])
        node = self.image_cls(transport=transport, encoder=encoder)
        self.assert_code("NO_USABLE_OUTPUT", lambda: node.analyze([Frame("x")]))
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_video_without_change_conclusion_fails_and_cleanup(self):
        transport = FakeTransport([envelope(video_content(0, change=""))])
        node = self.video_cls(transport=transport, encoder=encoder)
        self.assert_code("PARSE_PARTIAL", lambda: node.analyze([Frame("0")]))
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_explicit_no_visible_change_is_a_valid_conclusion(self):
        transport = FakeTransport([envelope(video_content(0, change="baseline frame")),
                                   envelope(video_content(1, change="no visible change can be established"))])
        node = self.video_cls(transport=transport, encoder=encoder)
        _, suggestion_raw = self.unpack(node.analyze([Frame("0"), Frame("1")]))
        self.assertIn("no visible change can be established", json.loads(suggestion_raw)["technical"]["camera_motion"])

    def test_prompt_echo_is_rejected_and_cleaned(self):
        transport = FakeTransport()
        node = self.image_cls(transport=transport, encoder=encoder)
        instruction = "describe visible content"
        # Use a response generated after observing the public owner's exact outgoing instruction.
        transport.responses.append(envelope(image_content(prompt=instruction)))
        self.assert_code("NO_USABLE_OUTPUT", lambda: node.analyze([Frame("x")], user_instruction=instruction))
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_full_request_instruction_echo_is_rejected(self):
        transport = FakeTransport()
        node = self.image_cls(transport=transport, encoder=encoder)
        original_chat = transport.chat

        def echo_chat(payload, timeout):
            transport.chat_calls.append((payload, timeout))
            return envelope(image_content(prompt=payload["messages"][0]["content"]))

        transport.chat = echo_chat
        self.assert_code("NO_USABLE_OUTPUT", lambda: node.analyze([Frame("x")]))
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_invalid_json_is_rejected_and_cleaned(self):
        raw = envelope("not-json")
        transport = FakeTransport([raw])
        node = self.image_cls(transport=transport, encoder=encoder)
        error = self.assert_code("PARSE_PARTIAL", lambda: node.analyze([Frame("x")]))
        self.assertEqual(raw, error.details["raw_response"])
        self.assertEqual(raw, json.loads(str(error))["details"]["raw_response"])
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_schema_extra_field_is_rejected(self):
        transport = FakeTransport([envelope(image_content(extra="not allowed"))])
        node = self.image_cls(transport=transport, encoder=encoder)
        self.assert_code("PARSE_PARTIAL", lambda: node.analyze([Frame("x")]))
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_schema_array_limit_is_rejected(self):
        transport = FakeTransport([envelope(image_content(observations=[f"item {i}" for i in range(7)]))])
        node = self.image_cls(transport=transport, encoder=encoder)
        self.assert_code("PARSE_PARTIAL", lambda: node.analyze([Frame("x")]))
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_done_reason_length_is_rejected(self):
        transport = FakeTransport([envelope(image_content(), done_reason="length")])
        node = self.image_cls(transport=transport, encoder=encoder)
        self.assert_code("PARSE_PARTIAL", lambda: node.analyze([Frame("x")]))
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_more_than_four_frames_rejected_before_transport(self):
        transport = FakeTransport()
        node = self.video_cls(transport=transport, encoder=encoder)
        self.assert_code("MEDIA_LIMIT_EXCEEDED", lambda: node.analyze([Frame(str(i)) for i in range(5)]))
        self.assertEqual([], transport.chat_calls)
        self.assertEqual([], transport.cleanup_calls)

    def test_more_than_one_image_rejected_before_transport(self):
        transport = FakeTransport()
        node = self.image_cls(transport=transport, encoder=encoder)
        self.assert_code("MEDIA_LIMIT_EXCEEDED", lambda: node.analyze([Frame("0"), Frame("1")]))
        self.assertEqual([], transport.chat_calls)

    def test_oversized_frame_rejected_before_transport(self):
        transport = FakeTransport()
        node = self.image_cls(transport=transport, encoder=encoder)
        self.assert_code("MEDIA_LIMIT_EXCEEDED", lambda: node.analyze([Frame("x", width=MAX_LONG_EDGE + 1)]))
        self.assertEqual([], transport.chat_calls)

    def test_non_loopback_endpoint_rejected_before_transport(self):
        transport = FakeTransport(endpoint="https://example.invalid:11434/api/chat")
        node = self.image_cls(transport=transport, encoder=encoder)
        self.assert_code("ORIGIN_FORBIDDEN", lambda: node.analyze([Frame("x")]))
        self.assertEqual([], transport.chat_calls)
        self.assertEqual([], transport.cleanup_calls)

    def test_timeout_failure_still_cleans_up(self):
        transport = FakeTransport(chat_error=BridgeError("MODEL_TIMEOUT", "fake timeout", subcode="FAKE_TIMEOUT"))
        node = self.image_cls(transport=transport, encoder=encoder)
        self.assert_code("MODEL_TIMEOUT", lambda: node.analyze([Frame("x")]))
        self.assertEqual(1, len(transport.chat_calls))
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_video_midstream_failure_stops_and_cleans_each_started_request(self):
        prior_raw = envelope(video_content(0))
        current_raw = envelope("not-json")
        transport = FakeTransport([prior_raw, current_raw, envelope(video_content(2))])
        node = self.video_cls(transport=transport, encoder=encoder)
        error = self.assert_code("PARSE_PARTIAL", lambda: node.analyze([Frame("0"), Frame("1"), Frame("2")]))
        self.assertEqual([prior_raw], error.details["prior_frame_raw_responses"])
        self.assertEqual(current_raw, error.details["raw_response"])
        rendered = json.loads(str(error))["details"]
        self.assertEqual([prior_raw], rendered["prior_frame_raw_responses"])
        self.assertEqual(current_raw, rendered["raw_response"])
        self.assertEqual(2, len(transport.chat_calls))
        self.assertEqual(2, len(transport.cleanup_calls))

    def test_invalid_timeout_rejected_without_starting_request(self):
        transport = FakeTransport()
        node = self.image_cls(transport=transport, encoder=encoder)
        self.assert_code("CONTRACT_UNSUPPORTED", lambda: node.analyze([Frame("x")], timeout_seconds=121))
        self.assertEqual([], transport.chat_calls)
        self.assertEqual([], transport.cleanup_calls)

    def test_cleanup_failure_fails_closed(self):
        raw = envelope(image_content())
        transport = FakeTransport([raw], cleanup_error=RuntimeError("fake cleanup failure"))
        node = self.image_cls(transport=transport, encoder=encoder)
        error = self.assert_code("RESOURCE_RELEASE_PENDING", lambda: node.analyze([Frame("x")]))
        self.assertEqual(raw, error.details["raw_response"])
        self.assertEqual(raw, json.loads(str(error))["details"]["raw_response"])
        self.assertEqual(1, len(transport.cleanup_calls))

    def test_primary_failure_is_preserved_when_cleanup_also_fails(self):
        transport = FakeTransport([envelope("not-json")], cleanup_error=RuntimeError("fake cleanup failure"))
        node = self.image_cls(transport=transport, encoder=encoder)
        error = self.assert_code("PARSE_PARTIAL", lambda: node.analyze([Frame("x")]))
        self.assertIn("cleanup_error", error.details)

    def test_non_frozen_model_tag_is_rejected_by_public_owner(self):
        transport = FakeTransport()
        node = self.image_cls(transport=transport, encoder=encoder)
        error = self.assert_code("CONTRACT_UNSUPPORTED",
                                 lambda: node.analyze([Frame("x")], model="other-model:latest"))
        self.assertEqual("MODEL_TAG_NOT_ALLOWED", error.details["subcode"])
        self.assertEqual([], transport.chat_calls)
        self.assertEqual([], transport.cleanup_calls)


if __name__ == "__main__":
    unittest.main()
