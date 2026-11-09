import unittest
from types import SimpleNamespace
from unittest.mock import patch

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_resources import validate_snapshot, resource_preflight, gpu_used_mib
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_request import VideoRequestOwner


class ResourceTests(unittest.TestCase):
    def test_resource_budget_and_ram_limits(self):
        result = validate_snapshot("24564,4096,20468", "42\n", 2048, owner_pid=42)
        self.assertEqual(4096,result["gpu_used_mib"])
        self.assertEqual(0,result["foreign_compute_processes"])

    def test_projected_peak_boundary_and_one_under_ram_are_busy(self):
        for gpu,ram in [("24564,5017,19547",2048),("24564,4096,20468",2047)]:
            with self.subTest(gpu=gpu,ram=ram),self.assertRaises(BridgeError) as error:
                validate_snapshot(gpu,"",ram,owner_pid=42)
            self.assertEqual("RESOURCE_BUSY",error.exception.code)

    def test_foreign_process_unknown_telemetry_and_multiple_devices_rejected(self):
        for gpu,pids,ram in [("24564,1000,23564","99",4096),("N/A","",4096),
                             ("24564,0,24564\n24564,0,24564","",4096),
                             ("24564,1000,23564","N/A",4096),
                             ("24564,1000,23564","",float("nan"))]:
            with self.subTest(gpu=gpu,pids=pids),self.assertRaises(BridgeError):
                validate_snapshot(gpu,pids,ram,owner_pid=42)

    def test_missing_probe_fails_before_any_subprocess(self):
        with patch("shutil.which",return_value=None),patch("subprocess.Popen") as spawn,self.assertRaises(BridgeError):
            resource_preflight()
        spawn.assert_not_called()

    def test_release_probe_is_bounded_and_rejects_unusable_or_multiple_gpu_rows(self):
        for raw,expected in [(b'1124\n',1124),(b'0\n',0),(b'1124\n1124\n',None),(b'N/A\n',None)]:
            with self.subTest(raw=raw),patch('shutil.which',return_value='pinned-by-parent'), \
                 patch('time.monotonic',return_value=5), \
                 patch('LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_resources.run_bounded',return_value=SimpleNamespace(stdout=raw)) as run:
                if expected is None:
                    with self.assertRaises(BridgeError):gpu_used_mib(7)
                else:self.assertEqual(expected,gpu_used_mib(7))
            self.assertEqual(2,run.call_args.kwargs['timeout_seconds'])
        with patch('time.monotonic',return_value=8),patch('shutil.which',return_value='unused'), \
             patch('LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_resources.run_bounded') as run, self.assertRaises(BridgeError):
            gpu_used_mib(7)
        run.assert_not_called()

    def test_request_refuses_before_decoder_when_resources_unproven(self):
        class Decoder:
            calls=0
            def decode(self,*args,**kwargs): self.calls+=1;raise AssertionError("must not decode")
        def denied(): raise BridgeError("RESOURCE_BUSY","occupied",subcode="TEST_FOREIGN")
        decoder=Decoder();owner=VideoRequestOwner(decoder,host_preflight=denied)
        with self.assertRaises(BridgeError):
            owner.run("resource-test","clip.mp4",model="gemma4:26b",user_instruction="",mode="realistic",timeout_seconds=120)
        self.assertEqual(0,decoder.calls)
        self.assertEqual("failed",owner.status("resource-test")["status"])

    def test_new_contention_after_decode_blocks_model_call(self):
        class Decoder:
            calls=0
            def decode(self,*args,**kwargs):
                self.calls+=1
                return SimpleNamespace(frames=[],manifest=[],source_sha256="a"*64)
        snapshots=iter([{"idle":True},None])
        def preflight():
            value=next(snapshots)
            if value is None: raise BridgeError("RESOURCE_BUSY","new occupancy",subcode="TEST_FOREIGN")
            return value
        decoder=Decoder();owner=VideoRequestOwner(decoder,preflight=preflight,
            host_preflight=preflight,tensor_builder=lambda frames:frames)
        with patch.object(owner.bridge,"analyze_video") as model,self.assertRaises(BridgeError):
            owner.run("race-test","clip.mp4",model="gemma4:26b",user_instruction="",mode="realistic",timeout_seconds=120)
        self.assertEqual(1,decoder.calls)
        model.assert_not_called()


if __name__ == "__main__": unittest.main()
