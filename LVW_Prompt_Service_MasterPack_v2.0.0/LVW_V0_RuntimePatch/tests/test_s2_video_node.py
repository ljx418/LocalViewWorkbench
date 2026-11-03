from pathlib import Path
import json
import unittest

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import NODE_CLASS_MAPPINGS
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_decoder import DecodedVideo
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_node import comfy_frames


class VideoNodeTests(unittest.TestCase):
    def setUp(self):
        self.frames = tuple(b"P6\n2 1\n255\n" + bytes([i]) * 6 for i in range(4))
        self.video = DecodedVideo("a" * 64, 20, 640, 480, 8,
                                  self.frames, tuple({"index":i,"pts":i * 1000} for i in range(4)))

    def test_registered_input_returns_cpu_tensor_and_visible_temporal_metadata(self):
        calls = []
        video = self.video
        class Decoder:
            def decode(self, reference): calls.append(reference); return video
        node = NODE_CLASS_MAPPINGS["LVWControlledVideoInput"](decoder=Decoder())
        result = node.load("authorized.mp4")
        tensor, metadata = result["result"]
        self.assertEqual(["authorized.mp4"], calls)
        self.assertEqual((4, 1, 2, 3), tuple(tensor.shape))
        self.assertEqual("cpu", tensor.device.type)
        self.assertEqual(metadata, result["ui"]["text"][0])
        parsed = json.loads(metadata)
        self.assertEqual(4, len(parsed["frames"]))
        self.assertEqual("a" * 64, parsed["source_sha256"])
        self.assertIn("do not establish", parsed["limitations"])

    def test_file_failure_never_builds_tensor(self):
        class Decoder:
            def decode(self, reference):
                raise BridgeError("PATH_FORBIDDEN", "denied", subcode="TEST_DENIED")
        built = []
        node = NODE_CLASS_MAPPINGS["LVWControlledVideoInput"](decoder=Decoder(), tensor_builder=lambda values: built.append(values))
        with self.assertRaises(BridgeError): node.load("../outside.mp4")
        self.assertEqual([], built)

    def test_public_file_node_to_public_bridge_runs_four_ordered_calls(self):
        video = self.video
        class Decoder:
            def decode(self, reference): return video
        class Transport:
            endpoint = "http://127.0.0.1:11434/api/chat"
            def __init__(self): self.calls = []; self.cleanups = []
            def chat(self, payload, timeout_seconds):
                index = len(self.calls); self.calls.append(payload)
                content = {"observations":[f"a colored subject at position {index}"],
                           "inferences":[],"unknowns":[],"tags":["color"],
                           "prompt":f"colored subject at position {index} on plain background",
                           "change":"baseline" if index == 0 else "subject position differs"}
                return json.dumps({"done":True,"done_reason":"stop",
                                   "message":{"role":"assistant","content":json.dumps(content)}})
            def cleanup(self, model, timeout_seconds): self.cleanups.append(model)
        loaded = NODE_CLASS_MAPPINGS["LVWControlledVideoInput"](decoder=Decoder()).load("authorized.mp4")
        transport = Transport()
        bridge = NODE_CLASS_MAPPINGS["LVWVideoFramesPromptBridge"](transport=transport, encoder=lambda frame: "fixture")
        result = bridge.analyze(loaded["result"][0])
        self.assertEqual(4, len(transport.calls))
        self.assertEqual(4, len(transport.cleanups))
        raw, suggestion = result["result"]
        self.assertEqual(4, len(json.loads(raw)["frame_raw_responses"]))
        self.assertEqual(4, len(json.loads(suggestion)["domains"]["observation"]))

    def test_dimension_change_does_not_silently_resize_or_drop_frame(self):
        with self.assertRaises(BridgeError) as error:
            comfy_frames(self.frames[:3] + (b"P6\n1 1\n255\nxxx",))
        self.assertEqual("VIDEO_FRAME_SHAPE_MISMATCH", error.exception.details["subcode"])

    def test_ui_and_api_graphs_are_wired_to_registered_public_owners(self):
        workflows = Path(__file__).resolve().parents[1] / "workflows"
        api = json.loads((workflows / "video_reverse_prompt_v0.api.json").read_text())
        ui = json.loads((workflows / "video_reverse_prompt_v0.ui.json").read_text())
        self.assertEqual({"1"}, set(api))
        self.assertEqual("LVWVideoPromptOwner", api["1"]["class_type"])
        for entry in api.values():
            cls = NODE_CLASS_MAPPINGS[entry["class_type"]]
            self.assertEqual(set(cls.INPUT_TYPES()["required"]), set(entry["inputs"]))
        self.assertEqual(set(n["type"] for n in ui["nodes"]), {n["class_type"] for n in api.values()})
        self.assertEqual([], ui["links"])


if __name__ == "__main__":
    unittest.main()
