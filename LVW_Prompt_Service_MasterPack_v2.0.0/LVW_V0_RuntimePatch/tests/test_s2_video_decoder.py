from pathlib import Path
import json
import tempfile
import unittest

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_decoder import VideoDecoder, parse_ppm
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_process import ProcessResult


class VideoDecoderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "input"; self.root.mkdir()
        self.runs = Path(self.temp.name) / "runs"; self.runs.mkdir()
        (self.root / "clip.mp4").write_bytes(b"synthetic video bytes")
        self.calls = []
        self.metadata = {"format":{"format_name":"mov,mp4", "duration":"8"},
                         "streams":[{"index":0,"codec_type":"video","width":640,"height":480,
                                     "time_base":"1/1000","start_pts":100,"duration":"8"}]}

    def runner(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        if len(self.calls) == 1:
            return ProcessResult(json.dumps(self.metadata).encode(), b"", 0)
        pts = 1100 + 2000 * (len(self.calls) - 2)
        ppm = b"P6\n2 1\n255\n" + bytes([len(self.calls)]) * 6
        log = f"[showinfo] config in time_base: 1/1000, frame_rate: 0/0\n[showinfo] n: 0 pts: {pts} pts_time: 1\n"
        return ProcessResult(ppm, log.encode(), 0)

    def decoder(self, runner=None):
        return VideoDecoder(input_root=self.root, temp_parent=self.runs,
                            ffprobe="trusted-ffprobe", ffmpeg="trusted-ffmpeg", runner=runner or self.runner)

    def test_production_owner_composition_and_bounded_pipe_commands(self):
        result = self.decoder().decode("clip.mp4")
        self.assertEqual([1100,3100,5100,7100], [f["pts"] for f in result.manifest])
        self.assertEqual([1,3,5,7], [f["time_seconds"] for f in result.manifest])
        self.assertEqual(4, len(result.frames))
        self.assertEqual([], list(self.runs.iterdir()))
        self.assertEqual(5, len(self.calls))
        for argv, options in self.calls:
            self.assertIn("file,pipe", argv)
            self.assertLessEqual(options["output_limit"], 3 * 1024 * 1024)
            self.assertNotIn(str(self.root / "clip.mp4"), argv)
        for argv, _ in self.calls[1:]:
            self.assertEqual("pipe:1", argv[-1])
            self.assertIn("-copyts", argv)

    def test_invalid_probe_stops_before_frame_decode_and_cleans(self):
        self.metadata["format"]["duration"] = "61"
        with self.assertRaises(BridgeError): self.decoder().decode("clip.mp4")
        self.assertEqual(1, len(self.calls))
        self.assertEqual([], list(self.runs.iterdir()))

    def test_missing_or_wrong_time_base_does_not_fabricate_pts(self):
        def runner(argv, **kwargs):
            value = self.runner(argv, **kwargs)
            if len(self.calls) > 1:
                return ProcessResult(value.stdout, b"config in time_base: 1/2\nn: 0 pts: 1100 pts_time: 1", 0)
            return value
        with self.assertRaises(BridgeError): self.decoder(runner).decode("clip.mp4")
        self.assertEqual(2, len(self.calls))
        self.assertEqual([], list(self.runs.iterdir()))

    def test_ppm_rejects_truncation_trailing_data_and_excess_dimensions(self):
        for value in (b"", b"P6\n1 1\n255\nxx", b"P6\n1 1\n255\nxxxx", b"P6\n769 1\n255\n"):
            with self.subTest(value=value), self.assertRaises(BridgeError): parse_ppm(value)

    def test_decoder_failure_does_not_leak_snapshot(self):
        def fail(argv, **kwargs):
            raise BridgeError("JOB_CANCELLED", "cancelled", subcode="TEST_CANCEL")
        with self.assertRaises(BridgeError): self.decoder(fail).decode("clip.mp4")
        self.assertEqual([], list(self.runs.iterdir()))


if __name__ == "__main__":
    unittest.main()
