"""Production policy, owner, runtime adapter and catalog boundaries; no native I/O."""
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import resource_policy as policy
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import video_resources as resources
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_transport import InterruptibleOllamaTransport
from tools.v0_s2_runtime import NativeRuntime
from tools.v0_s2_driver import base


class PolicyTests(unittest.TestCase):
    def test_recorded_desktop_case_admits_while_earlier_low_free_case_refuses(self):
        result=policy.admit([[0,24564,4520,19619]],[[0,24564,4308,19831]])
        self.assertEqual(23055,result['projected_total_used_mib']);self.assertEqual(212,result['native_wsl_difference_mib'])
        self.assertEqual([425,425],result['reserved_mib']);self.assertEqual(19047,result['policy']['required_free_mib'])
        self.assertEqual(4520,resources.validate_snapshot('24564,4520,19619','',8913,owner_pid=42)['gpu_used_mib'])
        with self.assertRaises(policy.PolicyError):policy.admit([[0,24564,9649,14490]])

    def test_free_and_total_peak_exact_and_one_over_boundaries(self):
        self.assertEqual(19047,policy.admit([[0,24564,4000,19047]])['min_free_mib'])
        self.assertEqual(23551,policy.admit([[0,24564,5016,19548]])['projected_total_used_mib'])
        for row in [[0,24564,4000,19046],[0,24564,5017,19547]]:
            with self.subTest(row=row),self.assertRaises(policy.PolicyError):policy.admit([row])
        self.assertEqual(23551,policy.admit([[0,24564,23551,1013]],warm=True)['max_used_mib'])
        with self.assertRaises(policy.PolicyError):policy.admit([[0,24564,23552,1012]],warm=True)

    def test_wrong_device_malformed_metrics_and_profile_fail_closed(self):
        for left,right in [([],[]),([[0,24564,1000,23564]],[[1,24564,1000,23564]]),
                ([[0,24564,-1,24565]],None),([[0,24564,1000,24564]],None),([[0,24564,True,10]],None)]:
            with self.subTest(left=left),self.assertRaises(policy.PolicyError):policy.admit(left,right)
        for args in [{'digest':'f'*64},{'model':'other'},{'num_ctx':4096},{'num_ctx':2048.0},{'max_parallel':True},{'image_long_edge':2048}]:
            with self.subTest(args=args),self.assertRaises(policy.PolicyError):policy.profile(**args)
        self.assertEqual(2048,policy.profile()['num_ctx'])

    def test_high_real_baseline_is_retained_but_invalid_types_and_hard_cap_are_not(self):
        for value in [0,4097,4520,23551]:self.assertTrue(policy.valid_baseline(value))
        for value in [-1,23552,True,4520.0,None]:self.assertFalse(policy.valid_baseline(value))
        transport=InterruptibleOllamaTransport();transport.bind_resource_baseline(4520)
        self.assertEqual(4520,transport._gpu_baseline)
        with self.assertRaises(ValueError):transport.bind_resource_baseline(23552)

    def test_catalog_digest_is_proven_before_production_cold_gpu_query(self):
        for mode in ['valid','wrong-digest','duplicate','malformed','status','oversize']:
            with self.subTest(mode=mode):
                connection=MagicMock();response=connection.getresponse.return_value;response.status=503 if mode=='status' else 200
                models=[{'name':policy.MODEL_TAG,'digest':'f'*64 if mode=='wrong-digest' else policy.MODEL_DIGEST}]
                if mode=='duplicate':models*=2
                body=(b'{' if mode=='malformed' else b' '*1048577 if mode=='oversize' else json.dumps({'models':models}).encode())
                response.read1.side_effect=[body,b'']
                result=SimpleNamespace(stdout=b'24564,4520,19619\n')
                with patch('shutil.which',return_value='owned-nvidia'),patch.object(resources.http.client,'HTTPConnection',return_value=connection) as http, \
                     patch.object(resources,'windows_available_ram_mib',return_value=8913), \
                     patch.object(resources,'run_bounded',side_effect=[result,SimpleNamespace(stdout=b'')]) as run:
                    if mode=='valid':self.assertEqual(4520,resources.resource_preflight()['gpu_used_mib']);self.assertEqual(2,run.call_count)
                    else:
                        with self.assertRaises(BridgeError):resources.resource_preflight()
                        run.assert_not_called()
                http.assert_called_once_with('127.0.0.1',11434,timeout=2)
                connection.request.assert_called_once_with('GET','/api/tags');connection.close.assert_called_once()

    def test_native_preflight_uses_current_shared_rule_and_preserves_target_guards(self):
        for mode in ['valid','busy-port','busy-process','low-free']:
            with self.subTest(mode=mode):
                args=SimpleNamespace(max_public_submissions=64,max_loopback_requests=8192,run_id='synthetic',powershell='unused',comfy_python='unused',nvidia_exe='pinned-nvidia')
                driver=NativeRuntime(args,{})
                values=['0,24564,9649,14490' if mode=='low-free' else '0,24564,4520,19619',
                    '[{}]' if mode=='busy-port' else '[]','1' if mode=='busy-process' else '0']
                with patch.object(driver,'_windows_path',return_value='C:/pinned/nvidia-smi.exe'), \
                     patch.object(driver,'_powershell',side_effect=values) as native,patch.object(base,'run_local',return_value=SimpleNamespace(returncode=0,stdout='0,24564,4308,19831')):
                    if mode=='valid':self.assertEqual(4520,driver.preflight()['max_used_mib'])
                    else:
                        with self.assertRaises(base.StopProbe):driver.preflight()
                self.assertIn('C:/pinned/nvidia-smi.exe',native.call_args_list[0].args[0])

    def test_high_baseline_hot_measurement_joins_real_owner_outputs_and_release_samples(self):
        from LVW_V0_RuntimePatch.tests import test_s2_measurements as fixtures
        from tools.v0_s2_measurements import hot_record
        values=fixtures.artifacts('video');values['binding']['baseline_gpu_mib']=4520
        release=values['warm_events'][-1]['resource_release'];release['baseline_gpu_mib']=4520
        for point in release['gpu_samples']:point['gpu_used_mib']=5544
        for point in values['resource_samples']:
            if point['gpu_used_mib']==1124:point['gpu_used_mib']=5544
        record=hot_record(**values)
        self.assertEqual('succeeded',record['outcome']);self.assertEqual(4,record['provider_calls'])
        self.assertFalse(record['oom'])
        release['gpu_samples'][-1]['gpu_used_mib']=5545
        from tools.v0_s2_checkpoint_oracles import EvidenceError
        with self.assertRaises(EvidenceError):hot_record(**values)

    def test_preload_uses_actual_chat_context_and_never_implicit_larger_default(self):
        args=SimpleNamespace(max_public_submissions=64,max_loopback_requests=8192,run_id='synthetic',powershell='unused',comfy_python='unused')
        driver=NativeRuntime(args,{});driver.resource_observer=lambda:None
        with patch.object(driver,'_json_request',return_value=(200,{'done':True})) as request:
            driver.preload(policy.MODEL_TAG)
        self.assertEqual({'num_ctx':2048,'num_predict':768},request.call_args.kwargs['payload']['options'])


if __name__=='__main__':unittest.main()
