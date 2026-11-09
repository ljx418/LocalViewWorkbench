"""WDDM capacity admission and strict control-owner proofs; no native I/O."""
import copy
import hashlib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import video_resources as resources,benchmark
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.tests.test_s2_measurements import artifacts
from tools.v0_s2_measurements import hot_record
from tools.v0_s2_checkpoint_oracles import EvidenceError


def xml(mode='WDDM',used=3000,free=21139):
    return (f'<nvidia_smi_log><gpu><driver_model><current_dm>{mode}</current_dm></driver_model>'
            f'<fb_memory_usage><total>24564 MiB</total><used>{used} MiB</used><free>{free} MiB</free></fb_memory_usage>'
            '<processes><process_info><pid>99</pid><type>C+G</type></process_info></processes></gpu></nvidia_smi_log>').encode()


def shared_sample():
    sample=artifacts('image');resource=sample['warm_events'][1]['resource_admission']
    resource.update(resources.validate_snapshot('24564,20000,4564','11\n20\n99',4096,owner_pid=20,warm=True,owned_compute_pids=(11,20),driver_model='WDDM'))
    probe=resource['native_probe'];probe['xml']=probe['xml'].replace('TCC','WDDM').replace('</processes>','<process_info><pid>99</pid></process_info></processes>')
    probe['xml_sha256']=hashlib.sha256(probe['xml'].encode()).hexdigest()
    return sample


class WDDMTests(unittest.TestCase):
    def test_observed_wddm_desktop_is_unowned_but_capacity_safe_not_whitelisted(self):
        result=resources.validate_snapshot('24564,3000,21139','20\n99',4096,owner_pid=20,driver_model='WDDM')
        self.assertEqual([99],result['unowned_compute_pids']);self.assertEqual([20],result['owned_compute_pids'])
        self.assertEqual(1,result['foreign_compute_processes'])
        for mode in (None,'TCC','unknown'):
            with self.subTest(mode=mode),self.assertRaises(BridgeError):
                resources.validate_snapshot('24564,3000,21139','20\n99',4096,owner_pid=20,driver_model=mode)

    def test_shared_mode_never_relaxes_peak_ram_or_invalid_telemetry(self):
        for gpu,ram,warm in [('24564,5017,19122',4096,False),('24564,23552,587',4096,True),('24564,3000,21139',2047,False),('N/A',4096,False)]:
            with self.subTest(gpu=gpu,ram=ram,warm=warm),self.assertRaises(BridgeError):
                resources.validate_snapshot(gpu,'99',ram,owner_pid=20,driver_model='WDDM',warm=warm)

    def test_production_preflight_uses_real_driver_proof_and_conservative_observations(self):
        for mode in ('WDDM','TCC','unknown'):
            with self.subTest(mode=mode),patch('shutil.which',return_value='trusted-probe'), \
                    patch.object(resources,'verify_model_profile') as model,patch.object(resources,'windows_available_ram_mib',return_value=4096),patch.object(resources,'probe_identity',return_value='1'*64), \
                    patch.object(resources,'run_bounded',side_effect=[SimpleNamespace(stdout=b'24564,3100,21039'),SimpleNamespace(stdout=xml(mode))]) as run:
                if mode=='WDDM':
                    observed=resources.resource_preflight();self.assertEqual(3100,observed['gpu_used_mib']);self.assertEqual([99],observed['unowned_compute_pids'])
                else:
                    with self.assertRaises(BridgeError):resources.resource_preflight()
                model.assert_called_once();self.assertEqual(['trusted-probe','-q','-x'],run.call_args.args[0])

    def test_single_gpu_complete_xml_is_required(self):
        for raw in [xml('unknown'),xml().replace(b'<pid>99',b'<pid>0'),xml().replace(b'3000 MiB',b'N/A'),
                    xml().replace(b'</gpu>',b'</gpu><gpu/>'),xml().replace(b'<processes>',b'<wrong>').replace(b'</processes>',b'</wrong>')]:
            with self.subTest(raw=raw[:50]),self.assertRaises(BridgeError):resources.parse_native_snapshot(raw)

    def test_shared_lineage_returns_only_proven_owned_subset_and_root_reuse_still_refused(self):
        binding={'ollama_pid':10,'ollama_start_ticks':100}
        document={'listener_pid':10,'listener_address':'127.0.0.1','listener_port':11434,
                  'processes':[{'pid':10,'parent_pid':1,'start_ticks':100,'name':'ollama.exe'},
                               {'pid':11,'parent_pid':10,'start_ticks':101,'name':'llama-server.exe'}]}
        self.assertEqual((11,20),benchmark.validate_lineage(document,binding,[99,11,20],20,shared_gpu=True))
        with self.assertRaises(BridgeError):benchmark.validate_lineage(document,binding,[99,11,20],20)
        document['processes'][0]['start_ticks']=99
        with self.assertRaises(BridgeError):benchmark.validate_lineage(document,binding,[99,11,20],20,shared_gpu=True)

    def test_warm_checker_receives_shared_mode_only_after_wddm_proof(self):
        seen=[]
        def checker(csv,**kwargs):seen.append((csv,kwargs));return ()
        with patch('shutil.which',return_value='trusted-probe'),patch.object(resources,'windows_available_ram_mib',return_value=4096),patch.object(resources,'probe_identity',return_value='1'*64), \
                patch.object(resources,'run_bounded',side_effect=[SimpleNamespace(stdout=b'24564,20000,4139'),SimpleNamespace(stdout=xml(used=20000,free=4139))]):
            result=resources.resource_preflight(warm=True,owned_pid_checker=checker)
        self.assertEqual([('99',{'shared_gpu':True})],seen);self.assertEqual([99],result['unowned_compute_pids'])

    def test_measurement_recomputes_owned_subset_and_rejects_forged_ownership(self):
        sample=shared_sample();resource=sample['warm_events'][1]['resource_admission']
        hot_record(**sample)
        resource['native_lineage']['verified_compute_pids'].append(99)
        with self.assertRaises(EvidenceError):hot_record(**sample)

    def test_measurement_rejects_missing_or_inconsistent_raw_native_proof(self):
        for change in ('missing','hash','driver-label','pid-list','memory','wrong-tool'):
            with self.subTest(change=change):
                sample=shared_sample();resource=sample['warm_events'][1]['resource_admission']
                if change=='missing':resource.pop('native_probe')
                elif change=='hash':resource['native_probe']['xml_sha256']='0'*64
                elif change=='driver-label':resource['driver_model']='TCC'
                elif change=='pid-list':resource['compute_pids']=[11,20]
                elif change=='memory':resource['gpu_used_mib']=1
                else:resource['native_probe']['nvidia_binary_sha256']='f'*64
                with self.assertRaises(EvidenceError):hot_record(**sample)

    def test_measurement_rejects_every_forged_owned_unowned_or_policy_field(self):
        for key,value in [('owned_compute_pids',[99]),('unowned_compute_pids',[]),('foreign_compute_processes',0),('gpu_process_admission','STRICT_COMPUTE')]:
            with self.subTest(key=key):
                sample=shared_sample();sample['warm_events'][1]['resource_admission'][key]=value
                with self.assertRaises(EvidenceError):hot_record(**sample)


if __name__=='__main__':unittest.main()
