import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import jsonschema

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import NODE_CLASS_MAPPINGS
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import manual
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraftOwner
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.nodes import LVWManualPromptOwner


PACK_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = PACK_ROOT / "LVW_V0_RuntimePatch" / "workflows" / "manual_prompt_v0.ui.json"


class RecordingClipboard:
    def __init__(self, error=None):
        self.values = []
        self.error = error

    def write(self, payload):
        if self.error:
            raise self.error
        self.values.append(payload)


class ManualPromptOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema = json.loads((PACK_ROOT / "contracts" / "v0-result.schema.json").read_text(encoding="utf-8"))
        cls.validator = jsonschema.Draft202012Validator(schema)

    def node(self, root, clipboard=None):
        owner = ManualDraftOwner(export_root=root, clipboard=clipboard or RecordingClipboard(),
                                 clock=lambda: "2026-10-28T00:00:00Z")
        return LVWManualPromptOwner(owner=owner), owner

    def call(self, node, **overrides):
        values = {
            "natural_zh": "霓虹雨夜中的街道",
            "natural_en": "A neon-lit street in the rain.",
            "image_prompt": "Neon-lit rainy street, cinematic reflections.",
            "video_prompt": "Slow tracking shot through a neon-lit rainy street.",
            "tags": "雨夜, neon\nstreet",
            "negative": "blur",
            "edit_instruction": "Keep the reflections.",
            "action": "preview_json",
            "filename": "人工提示词",
        }
        values.update(overrides)
        return node.process(**values)

    def test_public_comfy_owner_is_registered_output_node(self):
        self.assertIs(NODE_CLASS_MAPPINGS["LVWManualPromptOwner"], LVWManualPromptOwner)
        self.assertTrue(LVWManualPromptOwner.OUTPUT_NODE)
        self.assertEqual("process", LVWManualPromptOwner.FUNCTION)
        self.assertEqual(9, len(LVWManualPromptOwner.RETURN_TYPES))

    def test_public_owner_emits_all_manual_outputs_and_valid_json(self):
        with tempfile.TemporaryDirectory() as temp:
            node, owner = self.node(Path(temp))
            response = self.call(node)
            self.assertEqual({"ui", "result"}, set(response))
            result = response["result"]
            payload = json.loads(result[7])
            self.validator.validate(payload)
            self.assertEqual("manual", payload["source_type"])
            self.assertIsNone(payload["run_id"])
            self.assertEqual("not_requested", payload["analysis_status"])
            self.assertIsNone(payload["suggestion"])
            self.assertEqual(["雨夜", "neon", "street"], payload["draft"]["tags"])
            self.assertEqual(0, owner.model_calls)

    def test_missing_english_is_not_auto_translated(self):
        with tempfile.TemporaryDirectory() as temp:
            node, _ = self.node(Path(temp))
            payload = json.loads(self.call(node, natural_en="")["result"][7])
            self.assertEqual("", payload["draft"]["natural_en"])

    def test_exact_20000_characters_pass_and_one_over_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            node, _ = self.node(Path(temp))
            exact = "稿" * 20_000
            self.assertEqual(exact, self.call(node, natural_zh=exact)["result"][0])
            with self.assertRaises(BridgeError) as raised:
                self.call(node, natural_zh=exact + "稿")
            self.assertEqual("MEDIA_LIMIT_EXCEEDED", raised.exception.code)
            self.assertEqual("MANUAL_DRAFT_CHARACTER_LIMIT", raised.exception.details["subcode"])

    def test_empty_draft_and_empty_fields_export_valid_manual_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            node, _ = self.node(Path(temp))
            response = self.call(node, natural_zh="", natural_en="", image_prompt="",
                                 video_prompt="", tags="", negative="", edit_instruction="")
            payload = json.loads(response["result"][7])
            self.validator.validate(payload)
            self.assertEqual([], payload["warnings"])
            self.assertEqual([], payload["draft"]["tags"])
            self.assertFalse(any(key.startswith(("approval", "nsfw", "content_note")) for key in payload))

    def test_copy_txt_and_json_use_no_model_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            clipboard = RecordingClipboard()
            node, owner = self.node(Path(temp), clipboard)
            self.call(node, action="copy_txt")
            self.call(node, action="copy_json")
            self.assertTrue(clipboard.values[0].startswith("## Natural Chinese"))
            self.validator.validate(json.loads(clipboard.values[1]))
            self.assertEqual(0, owner.model_calls)

    def test_clipboard_failure_does_not_change_draft(self):
        with tempfile.TemporaryDirectory() as temp:
            failing = RecordingClipboard(OSError("clipboard fixture"))
            node, owner = self.node(Path(temp), failing)
            before = self.call(LVWManualPromptOwner(owner=ManualDraftOwner(
                export_root=Path(temp), clipboard=RecordingClipboard(),
                clock=lambda: "2026-10-28T00:00:00Z")))["result"][:7]
            with self.assertRaises(BridgeError) as raised:
                self.call(node, action="copy_json")
            self.assertEqual("NO_USABLE_OUTPUT", raised.exception.code)
            preview = self.call(LVWManualPromptOwner(owner=owner))["result"][:7]
            self.assertEqual(before, preview)
            self.assertEqual(0, owner.model_calls)

    def test_json_and_txt_exports_support_unicode_directory_and_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "中文 输出"
            node, owner = self.node(root)
            json_response = self.call(node, action="export_json", filename="人工稿")
            txt_response = self.call(node, action="export_txt", filename="人工稿")
            exported = json.loads((root / "人工稿.json").read_text(encoding="utf-8"))
            self.validator.validate(exported)
            self.assertIn("霓虹雨夜", (root / "人工稿.txt").read_text(encoding="utf-8"))
            self.assertEqual("人工稿.json", json.loads(json_response["result"][8])["exported_filename"])
            self.assertEqual("人工稿.txt", json.loads(txt_response["result"][8])["exported_filename"])
            self.assertEqual(0, owner.model_calls)

    def test_invalid_export_paths_fail_closed_without_files(self):
        invalid = ("", ".", "..", "../escape", "sub/file", r"sub\file", "/absolute", "C:drive")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            node, _ = self.node(root)
            for value in invalid:
                with self.subTest(value=value), self.assertRaises(BridgeError) as raised:
                    self.call(node, action="export_json", filename=value)
                self.assertEqual("PATH_FORBIDDEN", raised.exception.code)
            self.assertEqual([], list(root.iterdir()))

    def test_windows_reserved_and_trailing_basenames_are_rejected(self):
        invalid = ("CON", "con.txt", "PRN", "AUX.json", "NUL", "COM1", "com9.log",
                   "LPT1", "lpt9.txt", "draft.", "draft ")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            node, _ = self.node(root)
            for value in invalid:
                with self.subTest(value=value), self.assertRaises(BridgeError) as raised:
                    self.call(node, action="export_json", filename=value)
                self.assertEqual("PATH_FORBIDDEN", raised.exception.code)
            self.assertEqual([], list(root.iterdir()))

    def test_symlink_export_root_is_rejected_without_external_write_or_draft_change(self):
        with tempfile.TemporaryDirectory() as temp:
            parent = Path(temp) / "controlled"
            outside = Path(temp) / "outside"
            parent.mkdir()
            outside.mkdir()
            leaf = parent / "lvw_manual"
            try:
                leaf.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"platform cannot create symlink fixture: {exc.winerror if hasattr(exc, 'winerror') else exc.errno}")
            owner = ManualDraftOwner(export_root=leaf, export_parent=parent,
                                     clipboard=RecordingClipboard(),
                                     clock=lambda: "2026-10-28T00:00:00Z")
            node = LVWManualPromptOwner(owner=owner)
            before = self.call(node)["result"][:7]
            with self.assertRaises(BridgeError) as raised:
                self.call(node, action="export_json", filename="人工稿")
            self.assertEqual("PATH_FORBIDDEN", raised.exception.code)
            self.assertEqual("MANUAL_EXPORT_ROOT_FORBIDDEN", raised.exception.details["subcode"])
            self.assertEqual([], list(outside.iterdir()))
            self.assertEqual([], list(parent.glob(".lvw-manual-*.tmp")))
            self.assertEqual(before, self.call(node)["result"][:7])
            self.assertTrue(leaf.is_symlink())

    def test_atomic_replace_failure_preserves_existing_file_and_removes_temp(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "人工稿.json"
            target.write_text("original", encoding="utf-8")
            node, _ = self.node(root)
            with mock.patch.object(manual.os, "replace", side_effect=OSError("disk fixture")):
                with self.assertRaises(BridgeError) as raised:
                    self.call(node, action="export_json", filename="人工稿")
            self.assertEqual("DISK_FULL", raised.exception.code)
            self.assertEqual("original", target.read_text(encoding="utf-8"))
            self.assertEqual([], list(root.glob(".lvw-manual-*.tmp")))

    def test_workflow_is_importable_shape_and_uses_only_project_owner(self):
        workflow = json.loads(WORKFLOW.read_text(encoding="utf-8"))
        self.assertEqual(0.4, workflow["version"])
        self.assertEqual(1, len(workflow["nodes"]))
        self.assertEqual("LVWManualPromptOwner", workflow["nodes"][0]["type"])
        self.assertIn(workflow["nodes"][0]["type"], NODE_CLASS_MAPPINGS)
        self.assertEqual([], workflow["links"])


if __name__ == "__main__":
    unittest.main()
