from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch
import os

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_files import reject_redirect, resolve_video, stage_video


class VideoFileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "input"; self.root.mkdir()
        self.runs = self.base / "runs"; self.runs.mkdir()
        self.source = self.root / "样本 clip.MOV"; self.source.write_bytes(b"synthetic fixture")

    def test_snapshot_hash_original_unchanged_and_owned_cleanup(self):
        original = self.source.read_bytes()
        unrelated = self.runs / "other-run"; unrelated.mkdir()
        with stage_video(self.root, self.source.name, self.runs) as value:
            self.assertNotEqual(self.source, value.path)
            self.assertEqual(original, value.path.read_bytes())
            self.assertEqual(sha256(original).hexdigest(), value.source_sha256)
            path = value.path
        self.assertFalse(path.exists())
        self.assertEqual(original, self.source.read_bytes())
        self.assertEqual([unrelated], list(self.runs.iterdir()))

    def test_consumer_failure_also_removes_only_owned_directory(self):
        with self.assertRaisesRegex(RuntimeError, "decoder failed"):
            with stage_video(self.root, self.source.name, self.runs):
                raise RuntimeError("decoder failed")
        self.assertEqual([], list(self.runs.iterdir()))
        self.assertTrue(self.source.exists())

    def test_exact_and_one_over_snapshot_limit(self):
        self.source.write_bytes(b"1234")
        with stage_video(self.root, self.source.name, self.runs, max_bytes=4) as value:
            self.assertEqual(4, value.byte_count)
        self.source.write_bytes(b"12345")
        with self.assertRaises(BridgeError) as error:
            with stage_video(self.root, self.source.name, self.runs, max_bytes=4):
                self.fail("over-limit file reached consumer")
        self.assertEqual("MEDIA_LIMIT_EXCEEDED", error.exception.code)
        self.assertEqual([], list(self.runs.iterdir()))

    def test_path_unc_url_stream_and_traversal_rejected(self):
        for reference in ("../x.mp4", "/x.mp4", "C:/x.mp4", "//server/x.mp4",
                          "https://host/a.mp4", "a.mp4:stream", "a\\b.mp4", "a/../b.mp4", "a//b.mp4", "a/./b.mp4", ""):
            with self.subTest(reference=reference), self.assertRaises(BridgeError):
                resolve_video(self.root, reference)
        self.assertEqual([], list(self.runs.iterdir()))

    def test_symlink_files_and_directories_rejected(self):
        (self.root / "link.mp4").symlink_to(self.source)
        (self.root / "redirect").symlink_to(self.root, target_is_directory=True)
        for name in ("link.mp4", "redirect/" + self.source.name):
            with self.subTest(name=name), self.assertRaises(BridgeError):
                resolve_video(self.root, name)

    def test_windows_reparse_attribute_rejected(self):
        with self.assertRaises(BridgeError):
            reject_redirect(SimpleNamespace(st_mode=0o100644, st_file_attributes=0x400))

    def test_empty_wrong_extension_and_directory_rejected(self):
        self.source.write_bytes(b"")
        with self.assertRaises(BridgeError):
            with stage_video(self.root, self.source.name, self.runs):
                self.fail("empty video reached consumer")
        for name in ("file.jpg", "folder.mp4"):
            (self.root / name).mkdir()
            with self.assertRaises(BridgeError):
                resolve_video(self.root, name)
        self.assertEqual([], list(self.runs.iterdir()))

    def test_growth_during_copy_never_reaches_decoder_or_leaves_snapshot(self):
        real_read = os.read
        changed = False
        def read(descriptor, count):
            nonlocal changed
            if not changed:
                changed = True
                with self.source.open("ab") as output:
                    output.write(b"extra bytes")
            return real_read(descriptor, count)
        with patch("LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_files.os.read", side_effect=read):
            with self.assertRaises(BridgeError) as error:
                with stage_video(self.root, self.source.name, self.runs):
                    self.fail("mutating file reached decoder")
        self.assertEqual("VIDEO_READ_RACE", error.exception.details["subcode"])
        self.assertEqual([], list(self.runs.iterdir()))


if __name__ == "__main__":
    unittest.main()
