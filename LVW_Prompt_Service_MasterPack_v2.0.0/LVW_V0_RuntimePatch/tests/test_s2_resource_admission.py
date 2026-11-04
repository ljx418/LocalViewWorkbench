"""Finite admission oracle and actual child receipts; native outputs are synthetic."""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import v0_s2_stage_checkpoint as cp
from tools import v0_s2_resource_admission as admission
from tools import v0_s2_execution_bindings as bindings
from tools.v0_s2_checkpoint_oracles import EvidenceError


class AdmissionTests(unittest.TestCase):
    def metrics(self,used=4096,ram=2048):
        rows=[[0,24564,used,24564-used]]
        return {'gpus':rows,'ram_available_mib':ram,'target_listener_count':0,'target_process_count':0},copy.deepcopy(rows)

    def test_exact_and_one_over_gpu_ram_and_disagreement_boundaries(self):
        native,wsl=self.metrics();self.assertEqual(4096,admission.oracle(native,wsl)['max_used_mib'])
        for used,ram in [(4097,2048),(4096,2047)]:
            with self.subTest(used=used,ram=ram),self.assertRaises(EvidenceError):admission.oracle(*self.metrics(used,ram))
        for difference in [128,129]:
            native,wsl=self.metrics(1000);wsl[0][2]+=difference;wsl[0][3]-=difference
            if difference==128:admission.oracle(native,wsl)
            else:
                with self.assertRaises(EvidenceError):admission.oracle(native,wsl)

    def test_ports_processes_empty_and_malformed_data_are_not_ready(self):
        for field in ['target_listener_count','target_process_count']:
            native,wsl=self.metrics();native[field]=1
            with self.subTest(field=field),self.assertRaises(EvidenceError):admission.oracle(native,wsl)
        for native,wsl in [(None,[]),({},[]),({'gpus':[]},[]),(*self.metrics(),)]:
            if isinstance(native,dict) and native.get('gpus'):continue
            with self.assertRaises(EvidenceError):admission.oracle(native,wsl)

    def test_unapproved_or_revoked_authority_stops_before_any_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for name in [admission.REQUEST,admission.APPROVAL]:
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((cp.ROOT/name).read_bytes())
            value=json.loads((root/admission.APPROVAL).read_text());value['status']='REVOKED';(root/admission.APPROVAL).write_text(json.dumps(value))
            with patch.object(cp,'ROOT',root),patch.object(subprocess,'run') as run,self.assertRaises(EvidenceError):
                admission.authority('a'*40,require_ready=False)
            run.assert_not_called()

    def test_full_slot_requires_successful_admission_and_unknown_slots_stay_closed(self):
        with tempfile.TemporaryDirectory() as temporary,patch.object(cp,'ROOT',Path(temporary)), \
                patch.object(cp,'STATE_ROOT',Path(temporary)/'state'), \
                patch.object(admission,'authority',side_effect=EvidenceError('readiness missing')) as authority:
            with self.assertRaises(EvidenceError):cp.prepare(admission.SLOT,'a'*40,'reports/v0-s2/offline-checkpoint-23/receipt.json')
            authority.assert_called_once_with('a'*40,require_ready=True)
            self.assertFalse(cp.child_path(admission.SLOT).exists())
        with self.assertRaises(EvidenceError):cp.child_path('full-resource-ready-02')

    def test_real_claim_raw_evidence_expiry_replay_and_disk_failure(self):
        policy=cp.repository_json(admission.REQUEST)['readiness_child']
        for mode in ['ready','busy','mismatch','ram','port','process','command-failure','disk-full']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory() as temporary,ExitStack() as stack:
                parent=Path(temporary).resolve();root=parent/'pack';root.mkdir();state=parent/'state';state.mkdir()
                request=cp.canonical({'readiness_child':policy});request_sha=hashlib.sha256(request).hexdigest()
                for name,data in [(admission.REQUEST,request),(admission.APPROVAL,b'{}'),(admission.HARNESS,b'fixture code identity')]:
                    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
                tools={}
                for key in ['powershell','nvidia_exe','wsl_nvidia']:
                    path=parent/key;path.write_bytes(key.encode());tools[key]={'path':str(path),'sha256':hashlib.sha256(key.encode()).hexdigest()}
                nvidia_fixture=Path(tools['nvidia_exe']['path']);tools['nvidia_exe']['path']='/mnt/c/WINDOWS/system32/nvidia-smi.exe'
                refs={'request':admission.REQUEST,'request_sha256':request_sha,'approval':admission.APPROVAL,
                    'approval_sha256':hashlib.sha256(b'{}').hexdigest(),'expires_at':time.time()+3600}
                offline=root/'reports/v0-s2/offline-checkpoint-23/receipt.json';offline.parent.mkdir(parents=True);offline.write_bytes(b'{}')
                stack.enter_context(patch.object(cp,'ROOT',root));stack.enter_context(patch.object(cp,'STATE_ROOT',state))
                stack.enter_context(patch.object(admission,'REQUEST_SHA',request_sha))
                stack.enter_context(patch.object(admission,'authority',return_value=refs));stack.enter_context(patch.object(admission,'expected_tools',return_value=tools))
                stack.enter_context(patch.object(cp,'source_gate',return_value={'payload_sha256':'1'*64}))
                stack.enter_context(patch.object(cp,'program_authority',return_value='0'*64))
                real_plain=bindings.plain
                stack.enter_context(patch.object(bindings,'plain',side_effect=lambda path:nvidia_fixture if str(path)==tools['nvidia_exe']['path'] else real_plain(path)))
                sleep=stack.enter_context(patch.object(time,'sleep'))
                def native(argv,**kwargs):
                    if mode=='command-failure':return subprocess.CompletedProcess(argv,1,b'',b'explicit synthetic failure')
                    used=4097 if mode=='busy' else 1000
                    if argv[0]==tools['powershell']['path']:
                        script=argv[-1];self.assertIn('[Environment]::NewLine',script)
                        self.assertNotIn('Stop-Process',script);self.assertNotIn('SetEnvironmentVariable',script)
                        value={'gpu_csv':f'0,24564,{used},{24564-used}', 'ram_available_mib':2047 if mode=='ram' else 8192,
                            'target_listener_count':int(mode=='port'),'target_process_count':int(mode=='process')}
                        data=json.dumps(value).encode()
                    else:
                        if mode=='mismatch':used+=1000
                        data=f'0,24564,{used},{24564-used}\n'.encode()
                    return subprocess.CompletedProcess(argv,0,data,b'')
                run=stack.enter_context(patch.object(subprocess,'run',side_effect=native))
                admission.prepare('a'*40,'reports/v0-s2/offline-checkpoint-23/receipt.json')
                if mode=='disk-full':
                    writer=cp.write_new
                    def fail_public(path,value):
                        if path==root/'reports/v0-s2/resource-admission-01/receipt.json':raise OSError('synthetic disk full')
                        return writer(path,value)
                    stack.enter_context(patch.object(cp,'write_new',side_effect=fail_public))
                    with self.assertRaises(OSError):admission.probe()
                else:
                    result=admission.probe()
                    self.assertEqual('RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE' if mode=='ready' else 'NO_GO',result['decision'])
                    self.assertLessEqual(result['native_command_upper_bound'],6);self.assertLessEqual(result['wsl_commands'],3)
                    self.assertEqual(0,result['model_calls']);self.assertEqual(0,result['service_starts'])
                    if mode=='busy':self.assertEqual(4097,result['samples'][0]['native']['gpus'][0][2])
                auth=json.loads((root/'reports/v0-s2/authorization-resource-admission-01.json').read_text())
                self.assertEqual('EXPIRED_RESOURCE_READY' if mode=='ready' else 'EXPIRED_NO_GO',auth['status'])
                self.assertEqual(b'1',(state/admission.READY/'lease.closed').read_bytes())
                before=run.call_count
                with self.assertRaises(EvidenceError):admission.probe()
                self.assertEqual(before,run.call_count)
                if mode in ['ready','disk-full']:
                    self.assertEqual(6,before);self.assertEqual(2,sleep.call_count)
                self.assertFalse((state/admission.SLOT).exists())


if __name__=='__main__':unittest.main()
