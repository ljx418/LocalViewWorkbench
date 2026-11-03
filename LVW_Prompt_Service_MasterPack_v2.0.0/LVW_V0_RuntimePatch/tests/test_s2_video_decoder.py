from pathlib import Path
import json
import tempfile
import unittest
import threading

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_decoder import VideoDecoder, parse_ppm
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_process import ProcessResult
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.native_probe import NativeAvProbe
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_request import VideoRequestOwner
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_workbench import project
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeOwner,DEFAULT_MODEL
from LVW_V0_RuntimePatch.tests.test_s2_video_cancel import Transport,Frame


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

    def test_native_probe_adapter_feeds_the_same_four_frame_owner(self):
        decoder=VideoDecoder(input_root=self.root,temp_parent=self.runs,ffprobe=None,ffmpeg='trusted-ffmpeg',
            runner=self.runner,probe_runner=NativeAvProbe('trusted-python',runner=self.runner))
        result=decoder.decode('clip.mp4')
        self.assertEqual('ffmpeg-cli/pyav-probe',result.decoder_backend)
        self.assertEqual(4,len(result.frames));self.assertEqual(5,len(self.calls))
        self.assertEqual('trusted-python',self.calls[0][0][0])
        for argv,_ in self.calls[1:]:
            self.assertEqual('mov',argv[argv.index('-f')+1])
            self.assertEqual('0',argv[argv.index('-enable_drefs')+1])
        self.assertEqual([],list(self.runs.iterdir()))

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

    def sparse_runner(self,points):
        values=iter(points)
        def run(argv,**kwargs):
            self.calls.append((argv,kwargs))
            if len(self.calls)==1:return ProcessResult(json.dumps(self.metadata).encode(),b'',0)
            point=next(values)
            if point is None:return ProcessResult(b'',b'config in time_base: 1/1000, frame_rate: 0/0\nOutput file is empty, nothing was encoded\n',0)
            ppm=b'P6\n2 1\n255\n'+bytes([point%251])*6
            return ProcessResult(ppm,f'config in time_base: 1/1000\nn: 0 pts: {point} pts_time: 0\n'.encode(),0)
        return run

    def test_sparse_windows_deduplicate_the_same_pts_without_copying_or_extra_calls(self):
        result=self.decoder(self.sparse_runner([4100,4100,6100,7100])).decode('clip.mp4')
        self.assertEqual([4100,6100,7100],[f['pts'] for f in result.manifest]);self.assertEqual(3,len(result.frames))
        self.assertEqual(5,len(self.calls));self.assertEqual([],list(self.runs.iterdir()))
        self.assertTrue(all('-xerror' in argv for argv,_ in self.calls[1:]))

    def test_eof_omits_later_windows_and_single_frame_fallback_remains_within_four_processes(self):
        result=self.decoder(self.sparse_runner([1100,3100,None])).decode('clip.mp4')
        self.assertEqual([1100,3100],[f['pts'] for f in result.manifest]);self.assertEqual(4,len(self.calls))
        self.calls=[]
        result=self.decoder(self.sparse_runner([None,100])).decode('clip.mp4')
        self.assertEqual([100],[f['pts'] for f in result.manifest]);self.assertEqual(3,len(self.calls))
        filters=self.calls[-1][0][self.calls[-1][0].index('-vf')+1]
        self.assertIn('gte(pts,100)',filters);self.assertEqual(0,result.manifest[0]['time_seconds'])
        self.assertEqual([],list(self.runs.iterdir()))

    def test_empty_selection_needs_explicit_eof_and_valid_timestamp_basis(self):
        for stderr in (b'',b'Output file is empty, nothing was encoded',
                       b'config in time_base: 1/2\nOutput file is empty, nothing was encoded',
                       b'config in time_base: 1/1000\nn: 0 pts: 100 pts_time: 0\nOutput file is empty, nothing was encoded'):
            self.calls=[]
            def run(argv,**kwargs):
                self.calls.append((argv,kwargs))
                return ProcessResult(json.dumps(self.metadata).encode(),b'',0) if len(self.calls)==1 else ProcessResult(b'',stderr,0)
            with self.subTest(stderr=stderr),self.assertRaises(BridgeError):self.decoder(run).decode('clip.mp4')
            self.assertEqual(2,len(self.calls));self.assertEqual([],list(self.runs.iterdir()))
        self.calls=[]
        with self.assertRaises(BridgeError):self.decoder(self.sparse_runner([None,None])).decode('clip.mp4')
        self.assertEqual(3,len(self.calls));self.assertEqual([],list(self.runs.iterdir()))

    def test_single_sample_uses_one_provider_and_exports_a_truthful_warning(self):
        transport=Transport(threading.Event())
        owner=VideoRequestOwner(self.decoder(self.sparse_runner([None,100])),
            bridge=BridgeOwner(transport=transport,encoder=lambda frame:'synthetic'),tensor_builder=lambda values:[Frame() for _ in values],
            host_preflight=lambda:{},preflight=lambda:{})
        run=owner.run('short','clip.mp4',model=DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120)
        self.assertEqual(1,transport.calls);self.assertEqual(1,len(json.loads(run['raw_response'])['frame_raw_responses']))
        exported=project({'action':'adopt','run_token':'short'},owner)['result']
        self.assertEqual(1,len(exported['source']['frames']));self.assertIn('1 sampled frames',exported['warnings'][0])
        self.assertIn('no frame was copied',exported['warnings'][1]);self.assertEqual([],list(self.runs.iterdir()))

    def test_same_pts_with_changed_bytes_and_backward_samples_remain_fail_closed(self):
        for kind in ('changed-bytes','backward'):
            self.calls=[];inner=self.sparse_runner([4100,4100] if kind=='changed-bytes' else [6100,4100])
            def run(argv,**kwargs):
                value=inner(argv,**kwargs)
                if kind=='changed-bytes' and len(self.calls)==3:return ProcessResult(value.stdout[:-6]+b'xxxxxx',value.stderr,0)
                return value
            with self.subTest(kind=kind),self.assertRaises(BridgeError) as error:self.decoder(run).decode('clip.mp4')
            self.assertEqual('VIDEO_PTS_INVALID',error.exception.details['subcode'])
            self.assertEqual(3,len(self.calls));self.assertEqual([],list(self.runs.iterdir()))


if __name__ == "__main__":
    unittest.main()
