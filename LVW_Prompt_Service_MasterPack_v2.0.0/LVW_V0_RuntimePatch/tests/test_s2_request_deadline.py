import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import core
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.benchmark import WarmBenchmark
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_request import VideoRequestOwner
from LVW_V0_RuntimePatch.tests.test_s2_video_cancel import Frame,Transport
from LVW_V0_RuntimePatch.tests.test_s2_warm_benchmark import binding,WarmTransport


class DeadlineTests(unittest.TestCase):
    def setUp(self):self.addCleanup(core._RESOURCE_RELEASE_PENDING.clear)

    def test_four_frame_calls_share_frozen_request_budget_and_reserve_release(self):
        config=json.loads((Path(__file__).resolve().parents[2]/'config/experience-gates.json').read_text())
        self.assertEqual(config['metrics']['request_seconds_max'],core.MAX_ANALYSIS_SECONDS)
        now=[0];timeouts=[]
        class Slow(Transport):
            def chat(self,payload,timeout):
                timeouts.append(timeout)
                if timeout<119:
                    self.calls+=1;now[0]+=timeout
                    raise core.BridgeError('MODEL_TIMEOUT','bounded provider fixture',subcode='TEST_TIMEOUT')
                raw=super().chat(payload,timeout);now[0]+=119;return raw
            def cleanup(self,model,timeout):
                super().cleanup(model,timeout);now[0]+=10
        transport=Slow(threading.Event());owner=core.BridgeOwner(transport=transport,encoder=lambda frame:'fixture',clock=lambda:now[0])
        with self.assertRaises(core.BridgeError) as error:
            owner.analyze_video([Frame()]*4,model=core.DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120)
        self.assertEqual('MODEL_TIMEOUT',error.exception.code)
        self.assertEqual([120,120,120,3],timeouts)
        self.assertEqual(3,len(error.exception.details['prior_frame_raw_responses']))
        self.assertEqual((4,4),(transport.calls,transport.cleanups));self.assertLessEqual(now[0],420)
        self.assertFalse(core._RESOURCE_RELEASE_PENDING.is_set())

    def test_cpu_preparation_uses_same_budget_and_does_not_start_gpu_admission(self):
        now=[0];checks=[]
        class Decoder:
            def decode(self,reference,cancel=None):
                now[0]=391
                return SimpleNamespace(frames=[Frame()]*4)
        transport=Transport(threading.Event())
        bridge=core.BridgeOwner(transport=transport,encoder=lambda frame:'fixture',clock=lambda:now[0])
        owner=VideoRequestOwner(Decoder(),bridge=bridge,tensor_builder=lambda frames:frames,
            preflight=lambda:checks.append('gpu'),host_preflight=lambda:{})
        with self.assertRaises(core.BridgeError) as error:
            owner.run('deadline','clip.mp4',model=core.DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120)
        self.assertEqual('MODEL_TIMEOUT',error.exception.code);self.assertEqual([],checks)
        self.assertEqual((0,0),(transport.calls,transport.cleanups))
        self.assertEqual('released',owner.current_status()['resource_state'])

    def test_warm_preflight_consumes_budget_and_cleanup_keeps_original_absolute_deadline(self):
        now=[0];events=[]
        def admission():now[0]=391;return {}
        profile=WarmBenchmark(binding(),check_root=lambda:None,admission=admission,sink=events.append,
            clock=lambda:now[0],wall=lambda:1000)
        transport=WarmTransport();owner=core.BridgeOwner(transport=transport,encoder=lambda frame:'fixture',
            benchmark=profile,clock=lambda:now[0])
        with self.assertRaises(core.BridgeError) as error:
            owner.analyze_video([Frame()]*4,model=core.DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120)
        self.assertEqual('MODEL_TIMEOUT',error.exception.code)
        self.assertEqual((0,1),(transport.calls,transport.cleanups))
        self.assertEqual(420,transport.release_deadline)
        self.assertTrue(events[-1]['restored_unloaded'])
        self.assertFalse(core._RESOURCE_RELEASE_PENDING.is_set())


if __name__=='__main__':unittest.main()
