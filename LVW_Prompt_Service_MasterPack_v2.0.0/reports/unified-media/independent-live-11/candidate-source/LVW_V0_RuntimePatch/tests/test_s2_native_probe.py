from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock,patch

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge._native_av_probe import probe_document
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.native_probe import NativeAvProbe,bundled_ffmpeg
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_input import validate_probe
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_node import default_video_decoder


class NativeProbeTests(unittest.TestCase):
    def av(self,*,origin=0):
        stream=SimpleNamespace(index=0,type='video',disposition=SimpleNamespace(value=0),
            codec_context=SimpleNamespace(width=640,height=480),time_base=Fraction(1,12288),
            start_time=origin,duration=19968)
        container=MagicMock();container.streams=[stream];container.duration=1625000
        container.format.name='mov,mp4,m4a,3gp,3g2,mj2'
        module=SimpleNamespace(open=MagicMock(),time_base=1000000)
        module.open.return_value.__enter__.return_value=container
        return module,container

    def test_native_probe_preserves_rationals_origin_and_forces_local_mov(self):
        module,container=self.av()
        document=probe_document('RUN_TEMP/source.mp4',av_module=module)
        probe=validate_probe(document,byte_count=100)
        self.assertEqual(Fraction(13,8),probe.duration);self.assertEqual(Fraction(1,12288),probe.time_base)
        self.assertEqual(0,probe.origin_pts);self.assertNotIn('RUN_TEMP',str(document))
        module.open.assert_called_once_with('RUN_TEMP/source.mp4',mode='r',format='mov',
            options={'protocol_whitelist':'file,pipe','enable_drefs':'0'})
        container.decode.assert_not_called()
        module.open.return_value.__exit__.assert_called_once()

    def test_unknown_origin_and_excess_streams_do_not_get_fabricated_evidence(self):
        module,container=self.av(origin=None)
        with self.assertRaises(BridgeError):validate_probe(probe_document('owned.mp4',av_module=module),byte_count=100)
        container.streams=container.streams*65
        with self.assertRaisesRegex(ValueError,'stream limit'):probe_document('owned.mp4',av_module=module)
        self.assertEqual(2,module.open.return_value.__exit__.call_count)

    def test_probe_is_one_bounded_isolated_child_with_owned_path(self):
        calls=[];result=SimpleNamespace(stdout=b'{}',stderr=b'',returncode=0);event=object()
        def runner(argv,**kwargs):calls.append((argv,kwargs));return result
        probe=NativeAvProbe('COMFY_PYTHON',runner=runner)
        self.assertIs(result,probe('RUN_TEMP/source.mp4',cancel=event))
        argv,options=calls[0]
        self.assertEqual(['COMFY_PYTHON','-I','-B'],argv[:3]);self.assertTrue(argv[3].endswith('_native_av_probe.py'))
        self.assertEqual('RUN_TEMP/source.mp4',argv[-1])
        self.assertEqual({'timeout_seconds':15,'output_limit':256*1024,'cancel':event},options)

    def test_default_factory_uses_existing_binary_and_lazy_probe_without_importing_packages(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);package=root/'imageio_ffmpeg';binary=package/'binaries';binary.mkdir(parents=True)
            (package/'__init__.py').write_text('raise AssertionError("must not import")')
            executable=binary/'ffmpeg-fixture.exe';executable.write_bytes(b'fixture')
            def spec(name):return SimpleNamespace(origin=str(package/'__init__.py')) if name=='imageio_ffmpeg' else SimpleNamespace(origin='av')
            with patch('importlib.util.find_spec',side_effect=spec),patch('shutil.which',return_value=None), \
                 patch.dict('os.environ',{},clear=True),patch.dict('sys.modules',{'folder_paths':SimpleNamespace(
                     get_input_directory=lambda:root,get_temp_directory=lambda:root)}):
                decoder=default_video_decoder()
                self.assertEqual(str(executable),decoder.ffmpeg);self.assertIsNone(decoder.ffprobe)
                self.assertEqual('ffmpeg-cli/pyav-probe',decoder.backend)
                (binary/'ffmpeg-second.exe').write_bytes(b'fixture')
                self.assertIsNone(bundled_ffmpeg())


if __name__=='__main__':unittest.main()
