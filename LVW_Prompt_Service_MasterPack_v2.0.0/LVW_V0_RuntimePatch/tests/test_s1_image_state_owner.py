import errno
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from PIL import Image

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import NODE_CLASS_MAPPINGS
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.image_input import (
    ControlledImageOwner, MAX_IMAGE_BYTES, MAX_IMAGE_PIXELS,
    validate_image_byte_count, validate_image_pixel_count,
)
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.nodes import (
    LVWControlledImageInput, LVWDraftStateOwner,
)


def image_bytes(fmt="PNG", *, mode="RGB", size=(8, 4), color=None, exif=None):
    if color is None:
        color = (10, 20, 30, 128) if mode == "RGBA" else (10, 20, 30)
    output = BytesIO()
    options = {"exif": exif} if exif is not None else {}
    Image.new(mode, size, color).save(output, format=fmt, **options)
    return output.getvalue()


class ControlledImageOwnerTests(unittest.TestCase):
    def node(self, root):
        return LVWControlledImageInput(owner=ControlledImageOwner(Path(root)))

    def test_public_owner_is_registered_and_reachable(self):
        self.assertIs(NODE_CLASS_MAPPINGS["LVWControlledImageInput"], LVWControlledImageInput)
        self.assertEqual("load", LVWControlledImageInput.FUNCTION)
        with tempfile.TemporaryDirectory() as temp:
            raw = image_bytes("PNG")
            Path(temp, "sample.jpg").write_bytes(raw)
            image, metadata_json = self.node(temp).load("sample.jpg")
            metadata = json.loads(metadata_json)
            self.assertEqual((1, 4, 8, 3), tuple(image.shape))
            self.assertEqual("PNG", metadata["actual_format"])
            self.assertEqual(hashlib.sha256(raw).hexdigest(), metadata["source_sha256"])
            self.assertRegex(metadata["output_rgb_sha256"], r"^[a-f0-9]{64}$")

    def test_byte_and_pixel_boundaries_without_large_allocations(self):
        validate_image_byte_count(MAX_IMAGE_BYTES)
        with self.assertRaises(BridgeError) as byte_error:
            validate_image_byte_count(MAX_IMAGE_BYTES + 1)
        self.assertEqual("MEDIA_LIMIT_EXCEEDED", byte_error.exception.code)
        validate_image_pixel_count(MAX_IMAGE_PIXELS, 1)
        with self.assertRaises(BridgeError) as pixel_error:
            validate_image_pixel_count(MAX_IMAGE_PIXELS + 1, 1)
        self.assertEqual("MEDIA_LIMIT_EXCEEDED", pixel_error.exception.code)

    def test_one_over_pixel_header_is_rejected_before_full_decode(self):
        source = mock.Mock(format="PNG", size=(MAX_IMAGE_PIXELS + 1, 1))
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "oversized.png").write_bytes(b"small header fixture")
            with mock.patch("PIL.Image.open", return_value=source), self.assertRaises(BridgeError) as raised:
                self.node(temp).load("oversized.png")
        self.assertEqual("MEDIA_LIMIT_EXCEEDED", raised.exception.code)
        self.assertEqual("IMAGE_PIXEL_LIMIT", raised.exception.details["subcode"])
        source.load.assert_not_called()

    def test_exif_transpose_precedes_dimension_recording(self):
        exif = Image.Exif()
        exif[274] = 6
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "oriented.jpg").write_bytes(image_bytes("JPEG", size=(2, 3), exif=exif))
            _, metadata_json = self.node(temp).load("oriented.jpg")
            metadata = json.loads(metadata_json)
            self.assertEqual([2, 3], metadata["original_dimensions"])
            self.assertEqual([3, 2], metadata["oriented_dimensions"])
            self.assertTrue(metadata["exif_transpose"])
            self.assertEqual("applied_before_limits", metadata["exif_strategy"])

    def test_rgba_is_composited_on_white_and_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "alpha.png").write_bytes(image_bytes("PNG", mode="RGBA", size=(1, 1), color=(0, 0, 0, 0)))
            image, metadata_json = self.node(temp).load("alpha.png")
            self.assertEqual("white_background", json.loads(metadata_json)["alpha_strategy"])
            self.assertTrue(all(abs(float(value) - 1.0) < 0.001 for value in image[0, 0, 0]))

    def test_long_edge_is_bounded_and_recorded(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "wide.webp").write_bytes(image_bytes("WEBP", size=(1100, 11)))
            image, metadata_json = self.node(temp).load("wide.webp")
            metadata = json.loads(metadata_json)
            self.assertEqual(1024, max(metadata["output_dimensions"]))
            self.assertEqual("lanczos_long_edge_1024", metadata["resize_strategy"])
            self.assertEqual(1024, max(int(image.shape[1]), int(image.shape[2])))

    def test_corrupt_and_actual_format_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            root.joinpath("broken.png").write_bytes(b"not an image")
            root.joinpath("bitmap.png").write_bytes(image_bytes("BMP"))
            for name in ("broken.png", "bitmap.png"):
                with self.subTest(name=name), self.assertRaises(BridgeError) as raised:
                    self.node(root).load(name)
                self.assertEqual("MEDIA_INVALID", raised.exception.code)
            self.assertEqual({"broken.png", "bitmap.png"}, {path.name for path in root.iterdir()})

    def test_absolute_escape_parent_escape_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp, "input")
            outside = Path(temp, "outside")
            root.mkdir()
            outside.mkdir()
            outside_file = outside / "outside.png"
            outside_file.write_bytes(image_bytes())
            try:
                (root / "link.png").symlink_to(outside_file)
            except OSError as exc:
                if not (isinstance(exc, PermissionError) or getattr(exc, "winerror", None) == 1314
                        or exc.errno in {errno.EPERM, errno.EACCES}):
                    raise
                self.skipTest(f"platform cannot create symlink fixture: {exc.winerror if hasattr(exc, 'winerror') else exc.errno}")
            for reference in (str(outside_file), "../outside/outside.png", "link.png", r"sub\file.png"):
                with self.subTest(reference=reference), self.assertRaises(BridgeError) as raised:
                    self.node(root).load(reference)
                self.assertEqual("PATH_FORBIDDEN", raised.exception.code)


class DraftStateOwnerTests(unittest.TestCase):
    def setUp(self):
        self.node = LVWDraftStateOwner()

    def call(self, state="", action="start_run", token="run-1", callback="", draft="", error=""):
        response = self.node.process(state=state, action=action, run_token=token,
                                     callback_payload=callback, draft_payload=draft, error_code=error)
        self.assertEqual({"ui", "result"}, set(response))
        return response["result"][0]

    @staticmethod
    def draft_payload(text="human draft"):
        return json.dumps({"natural_zh": text, "natural_en": "", "image_prompt": "", "video_prompt": "",
                           "tags": [], "negative": "", "edit_instruction": ""})

    def test_public_owner_registered_and_callback_does_not_auto_write_draft(self):
        self.assertIs(NODE_CLASS_MAPPINGS["LVWDraftStateOwner"], LVWDraftStateOwner)
        self.assertTrue(LVWDraftStateOwner.OUTPUT_NODE)
        started = self.call()
        succeeded = self.call(started, action="model_success", callback='{"prompt":"visible subject"}')
        value = json.loads(succeeded)
        self.assertEqual("succeeded", value["analysis_status"])
        self.assertEqual({"prompt": "visible subject"}, value["suggestion"])
        self.assertEqual("", value["draft"]["natural_zh"])
        self.assertEqual(0, value["draft_epoch"])

    def test_explicit_adopt_updates_draft_and_epoch(self):
        state = self.call()
        state = self.call(state, action="model_success", callback='{"prompt":"visible"}')
        state = self.call(state, action="adopt", draft=self.draft_payload())
        value = json.loads(state)
        self.assertEqual("human draft", value["draft"]["natural_zh"])
        self.assertEqual(1, value["draft_epoch"])

    def test_stale_token_and_invalid_json_preserve_prior_state(self):
        state = self.call()
        for token, callback, expected in (("old", "{}", "ATTEMPT_STALE"), ("run-1", "{", "PARSE_PARTIAL")):
            with self.subTest(token=token), self.assertRaises(BridgeError) as raised:
                self.call(state, action="model_success", token=token, callback=callback)
            self.assertEqual(expected, raised.exception.code)
        self.assertEqual("running", json.loads(state)["analysis_status"])
        with self.assertRaises(BridgeError) as raised:
            self.node.process(state=None, action="start_run", run_token="run-2",
                              callback_payload="", draft_payload="", error_code="")
        self.assertEqual("PARSE_PARTIAL", raised.exception.code)

    def test_terminal_run_rejects_late_same_token_callback(self):
        state = self.call()
        succeeded = self.call(state, action="model_success", callback='{"prompt":"visible"}')
        with self.assertRaises(BridgeError) as raised:
            self.call(succeeded, action="model_success", callback='{"prompt":"late"}')
        self.assertEqual("ATTEMPT_STALE", raised.exception.code)
        self.assertEqual({"prompt": "visible"}, json.loads(succeeded)["suggestion"])

    def test_model_failures_partial_and_cancel_never_overwrite_manual_draft(self):
        state = self.call()
        state = self.call(state, action="model_success", callback='{"prompt":"visible"}')
        adopted = self.call(state, action="adopt", draft=self.draft_payload("kept"))
        for action, code, status in (("model_failure", "MODEL_REFUSAL", "failed"),
                                     ("model_failure", "MODEL_TIMEOUT", "failed"),
                                     ("model_failure", "GPU_OOM", "failed"),
                                     ("model_failure", "NO_USABLE_OUTPUT", "failed"),
                                     ("partial", "PARSE_PARTIAL", "partial"),
                                     ("cancel", "", "cancelled")):
            with self.subTest(action=action, code=code):
                running = self.call(adopted, action="start_run", token="next-run")
                failed = self.call(running, action=action, token="next-run", error=code,
                                   callback="safe raw fixture")
                value = json.loads(failed)
                self.assertEqual(status, value["analysis_status"])
                self.assertEqual("kept", value["draft"]["natural_zh"])
                self.assertEqual(1, value["draft_epoch"])
                self.assertEqual(0, value["retry_count"])
                self.assertEqual("safe raw fixture", value["raw_response"])

    def test_failure_cannot_be_adopted(self):
        state = self.call()
        failed = self.call(state, action="model_failure", error="MODEL_TIMEOUT")
        with self.assertRaises(BridgeError) as raised:
            self.call(failed, action="adopt", draft=self.draft_payload("forbidden"))
        self.assertEqual("NO_USABLE_OUTPUT", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
