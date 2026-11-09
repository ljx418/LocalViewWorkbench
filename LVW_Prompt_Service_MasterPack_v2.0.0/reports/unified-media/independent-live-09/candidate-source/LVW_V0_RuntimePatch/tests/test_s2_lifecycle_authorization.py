"""Real isolated Git/files for finite authorization; no installed/native I/O."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import v0_s2_lifecycle_authorization as auth
from tools import v0_s2_stage_checkpoint as cp
from tools.v0_s2_checkpoint_oracles import EvidenceError


class LifecycleAuthorityTests(unittest.TestCase):
    def put(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(cp.canonical(value))
        return cp.file_hash(path)

    def git(self, root, *args):
        return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()

    def commit(self, root):
        self.git(root,'add','.'); self.git(root,'-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-qm','isolated authority')
        return self.git(root,'rev-parse','HEAD')

    def fixture(self, folder, stack):
        request=cp.repository_json(auth.REQUEST); grant=cp.repository_json(auth.APPROVAL)
        stage=cp.repository_json('.agent-governance/stages/V0-S2/stage-control.json')
        stage.pop('profile_lifecycle_authorization'); stage['authorities'].remove(auth.APPROVAL)
        root=folder/'pack';root.mkdir();state=folder/'state';state.mkdir()
        spec='.agent-governance/stages/V0-S2/stage-control.json'
        self.put(root/spec,stage);self.put(root/cp.PROGRAM,cp.repository_json(cp.PROGRAM))
        self.put(root/'plans/execution-control.json',{'coordinate':{'stage_id':'V0-S2'},'external_execution_hold':{'active':False},'profile_lifecycle_authorization':auth.APPROVAL})
        for ref in request['correction_files_sha256']:
            request['correction_files_sha256'][ref]=self.put(root/ref,{'explicit_synthetic_baseline':True})
        self.git(root,'init','-q');baseline=self.commit(root)
        request.update(corrected_candidate=baseline,seed_artifact_sha256={})
        for ref,key in [(request['offline_receipt'],'offline_receipt_sha256'),(request['failure_recomputation'],'failure_recomputation_sha256')]:
            request[key]=self.put(root/ref,{'synthetic':True})
        for row in request['prior_consumed_full_runs']:
            row['receipt_sha256']=self.put(root/row['receipt'],{'decision':'NO_GO'})
            directory=state/row['run_id'];directory.mkdir();(directory/'lease.closed').write_bytes(b'1')
            row['raw_terminal_sha256']=self.put(directory/'terminal.json',{'decision':'NO_GO','synthetic':True})
        request_sha=self.put(root/auth.REQUEST,request)
        grant.update(status='ACTIVE',request_sha256=request_sha,issued_at=time.time()-1,expires_at=time.time()+300)
        for ref in auth.HISTORICAL:grant['historical_records_sha256'][ref]=self.put(root/ref,{'status':'EXPIRED_NO_GO'})
        self.put(root/auth.APPROVAL,grant)
        self.put(root/auth.HARNESS,{'explicit_synthetic_harness':True})
        stage['authorities'].append(auth.APPROVAL);stage['profile_lifecycle_authorization']=auth.packet_scope()
        self.put(root/spec,stage);candidate=self.commit(root)
        for owner,key,value in [(cp,'ROOT',root),(cp,'STATE_ROOT',state),(auth,'BASELINE',baseline),(auth,'REQUEST_SHA',request_sha)]:
            stack.enter_context(patch.object(owner,key,value))
        return root,state,candidate

    def ready_fixture(self, root, state, candidate):
        from tools import v0_s2_resource_admission as admission
        directory=state/auth.READY;directory.mkdir();(directory/'lease.closed').write_bytes(b'1')
        request=cp.repository_json(auth.REQUEST)
        active={'status':'ACTIVE_ONE_SHOT','run_id':auth.READY,'candidate_sha':candidate,'scope':auth.readiness_scope(),
                'harness_sha256':cp.file_hash(root/auth.HARNESS),'program_sha256':cp.program_authority(),
                'supplemental_authorization':{'approval_sha256':cp.file_hash(root/auth.APPROVAL)},
                'offline_receipt':request['offline_receipt'],'offline_receipt_sha256':request['offline_receipt_sha256']}
        self.put(directory/'active-child.json',active)
        native={'gpu_csv':'0, 24564, 4500, 19639','ram_available_mib':4096,'target_listener_count':0,'target_process_count':0}
        native_sample={**native,'gpus':[[0,24564,4500,19639]]};wsl=[[0,24564,4300,19839]]
        terminal={'run_id':auth.READY,'candidate_sha':candidate,'decision':'RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE',
                  'sample_count':3,'stage_pass_claim':False,'elapsed_seconds':6,'native_command_upper_bound':6,'wsl_commands':3,
                  **dict.fromkeys(('model_calls','service_starts','media_reads','browser_starts','foreign_process_terminations'),0),
                  'commands':[],'samples':[]}
        for i in range(3):
            terminal['samples'].append({'ordinal':i+1,'native':native_sample,'wsl':wsl,'admission':admission.oracle(native_sample,wsl)})
            for offset,kind in enumerate(('native','wsl')):
                n=i*2+offset+1;command={'kind':kind,'argv':['explicit-synthetic-'+kind], 'exit_code':None}
                self.put(directory/('command-'+str(n)+'.json'),command);command=dict(command,exit_code=0)
                for stream,data in [('stdout',(json.dumps(native) if kind=='native' else '0,24564,4300,19839').encode()),('stderr',b'')]:
                    (directory/('command-'+str(n)+'.'+stream+'.log')).write_bytes(data);command[stream+'_sha256']=hashlib.sha256(data).hexdigest()
                terminal['commands'].append(command)
        terminal_sha=self.put(directory/'terminal.json',terminal)
        ref='reports/v0-s2/'+auth.READY+'/receipt.json';digest=self.put(root/ref,{**terminal,'raw_terminal_sha256':terminal_sha})
        child=dict(active,status='EXPIRED_RESOURCE_READY',terminal_receipt=ref,terminal_receipt_sha256=digest)
        self.put(root/('reports/v0-s2/authorization-'+auth.READY+'.json'),child)
        return directory

    def test_valid_child_routing_and_approval_expiry_hold_or_request_change(self):
        for mutation in ['valid','expired','revoke','hold','request']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                if mutation in ('expired','revoke'):
                    v=cp.repository_json(auth.APPROVAL);v.update(expires_at=time.time()-1) if mutation=='expired' else v.update(status='REVOKED');self.put(root/auth.APPROVAL,v)
                elif mutation=='hold':self.put(root/'plans/execution-control.json',{'external_execution_hold':{'active':True}})
                elif mutation=='request':(root/auth.REQUEST).write_bytes((root/auth.REQUEST).read_bytes()+b' ')
                if mutation=='valid':self.assertEqual(auth.APPROVAL,auth.authority(candidate,require_ready=False)['approval'])
                else:
                    with patch.object(subprocess,'run') as execute,self.assertRaises(EvidenceError):auth.authority(candidate,require_ready=False)
                    execute.assert_not_called()

    def test_unapproved_product_contract_and_fixed_obligation_changes_denied(self):
        for mutation in ['product','contract','threshold','budget']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                if mutation in ('product','contract'):
                    self.put(root/('LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py' if mutation=='product' else 'contracts/extra.json'),{})
                else:
                    ref='.agent-governance/stages/V0-S2/stage-control.json';v=cp.repository_json(ref)
                    if mutation=='threshold':v['gpu_admission_policy']['required_free_mib']=1
                    else:v['profile_lifecycle_authorization']['max_complete_claims']=2
                    self.put(root/ref,v)
                candidate=self.commit(root)
                with self.assertRaises(EvidenceError):auth.authority(candidate,require_ready=False)

    def test_prior_failures_expired_authorities_and_single_claim_not_resettable(self):
        for mutation in ['failure','open','oldgrant','claimed','prepared']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                if mutation=='failure':self.put(root/'reports/v0-s2/full-oracle-correction-01/receipt.json',{'decision':'PASS'})
                elif mutation=='open':(state/'full-oracle-correction-01/lease.closed').write_bytes(b'0')
                elif mutation=='oldgrant':self.put(root/next(iter(auth.HISTORICAL)),{'status':'ACTIVE'})
                elif mutation=='claimed':(state/auth.SLOT).mkdir()
                else:self.put(cp.child_path(auth.SLOT),{})
                with self.assertRaises(EvidenceError):auth.authority(candidate,require_ready=False)

    def test_full_route_requires_fresh_matching_complete_readiness(self):
        for mutation in ['missing','valid','oldcandidate','incomplete','open','rawmissing','rawchanged','activechanged','stdoutchanged','commandchanged','oracletampered']:
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                if mutation=='missing':
                    with self.assertRaises(EvidenceError):cp.slot_authority(auth.SLOT,candidate)
                    continue
                directory=self.ready_fixture(root,state,candidate)
                if mutation in ('oldcandidate','incomplete'):
                    path=root/('reports/v0-s2/authorization-'+auth.READY+'.json');v=json.loads(path.read_bytes())
                    if mutation=='oldcandidate':v['candidate_sha']='e'*40
                    else:
                        r=cp.repository_json(v['terminal_receipt']);r['sample_count']=2;v['terminal_receipt_sha256']=self.put(root/v['terminal_receipt'],r)
                    self.put(path,v)
                elif mutation=='open':(directory/'lease.closed').write_bytes(b'0')
                elif mutation=='rawmissing':(directory/'terminal.json').unlink()
                elif mutation=='rawchanged':(directory/'terminal.json').write_bytes((directory/'terminal.json').read_bytes()+b' ')
                elif mutation=='activechanged':self.put(directory/'active-child.json',{})
                elif mutation=='stdoutchanged':(directory/'command-1.stdout.log').write_bytes(b'forged output')
                elif mutation=='commandchanged':self.put(directory/'command-1.json',{'exit_code':0})
                elif mutation=='oracletampered':
                    v=json.loads((directory/'terminal.json').read_bytes());v['samples'][0]['admission']['max_used_mib']=0
                    raw_sha=self.put(directory/'terminal.json',v);ref='reports/v0-s2/'+auth.READY+'/receipt.json'
                    public_sha=self.put(root/ref,{**v,'raw_terminal_sha256':raw_sha});childpath=root/('reports/v0-s2/authorization-'+auth.READY+'.json')
                    child=json.loads(childpath.read_bytes());child['terminal_receipt_sha256']=public_sha;self.put(childpath,child)
                if mutation=='valid':self.assertEqual(auth.APPROVAL,cp.slot_authority(auth.SLOT,candidate)['approval'])
                else:
                    with self.assertRaises(EvidenceError):cp.slot_authority(auth.SLOT,candidate)


if __name__=='__main__':unittest.main()
