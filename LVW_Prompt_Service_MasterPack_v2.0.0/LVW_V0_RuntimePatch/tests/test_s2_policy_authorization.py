"""Approved correction authority and exact slot routing, real own Git/files only."""
from contextlib import ExitStack
import json
import hashlib
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import v0_s2_stage_checkpoint as cp
from tools import v0_s2_policy_authorization as auth
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import profile
from tools.v0_s2_checkpoint_oracles import EvidenceError


class PolicyAuthorityTests(unittest.TestCase):
    def put(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(cp.canonical(value))
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def git(self,root,*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
    def commit(self,root):
        self.git(root,'add','.');self.git(root,'-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-qm','synthetic policy fixture')
        return self.git(root,'rev-parse','HEAD')

    def fixture(self,parent,stack):
        stage=cp.repository_json('.agent-governance/stages/V0-S2/stage-control.json');program=cp.repository_json(cp.PROGRAM)
        request=cp.repository_json(auth.REQUEST);grant=cp.repository_json(auth.APPROVAL);decision=cp.repository_json(auth.DECISION)
        original=cp.repository_json(auth.ORIGINAL);original['seed_artifact_sha256']={}
        stage.pop('gpu_admission_policy',None);stage.pop('policy_correction_authorization',None)
        stage['authorities'].remove(auth.DECISION)
        root=parent/'pack';root.mkdir();state=parent/'state';state.mkdir();spec='.agent-governance/stages/V0-S2/stage-control.json'
        self.put(root/spec,stage);self.put(root/cp.PROGRAM,program)
        self.put(root/'plans/execution-control.json',{'coordinate':{'stage_id':'V0-S2'},'external_execution_hold':{'active':False},'policy_correction_authorization':auth.APPROVAL})
        self.git(root,'init','-q');baseline=self.commit(root)
        request['evidence']='reports/v0-s2/synthetic-profile-evidence.json';request['evidence_sha256']=self.put(root/request['evidence'],{'synthetic':True})
        request_sha=self.put(root/auth.REQUEST,request);decision['request_sha256']=request_sha
        self.put(root/auth.DECISION,decision);self.put(root/auth.ORIGINAL,original)
        grant.update(status='ACTIVE',issued_at=time.time()-1,expires_at=time.time()+300,request_sha256=request_sha,
            baseline_commit=baseline,decision_sha256=cp.file_hash(root/auth.DECISION))
        for row in grant['prior_failures']:
            row['receipt_sha256']=self.put(root/row['receipt'],{'decision':'NO_GO'})
            folder=state/row['run_id'];folder.mkdir();(folder/'lease.closed').write_bytes(b'1')
            row['raw_terminal_sha256']=self.put(folder/'terminal.json',{'decision':'NO_GO','synthetic':True})
        for ref in grant['prior_expired_grants']:
            grant['prior_expired_grants'][ref]=self.put(root/ref,{'status':'EXPIRED_NO_GO'})
        self.put(root/auth.APPROVAL,grant)
        stage['authorities'].append(auth.DECISION);stage['gpu_admission_policy']=profile()
        stage['policy_correction_authorization']={'approval':auth.APPROVAL,'request':auth.REQUEST,'slot':auth.SLOT,
            'readiness_slot':auth.READY,'max_new_readiness':1,'max_complete_claims':1,'max_extra_complete_runs':0,'max_rechecks':0}
        self.put(root/spec,stage);candidate=self.commit(root)
        for owner,key,value in [(cp,'ROOT',root),(cp,'STATE_ROOT',state),(auth,'BASELINE',baseline),(auth,'REQUEST_SHA',request_sha)]:
            stack.enter_context(patch.object(owner,key,value))
        return root,state,candidate

    def test_real_git_scope_accepts_correction_but_rejects_unapproved_contract_or_core_change(self):
        for mutation in ('valid','contract','core','frozen','profile'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                if mutation in ('contract','core'):
                    self.put(root/('contracts/changed.json' if mutation=='contract' else 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py'),{})
                    candidate=self.commit(root)
                elif mutation in ('frozen','profile'):
                    p=root/'.agent-governance/stages/V0-S2/stage-control.json';v=json.loads(p.read_text())
                    if mutation=='frozen':v['budgets']['stage_checkpoints']=2
                    else:v['gpu_admission_policy']['required_free_mib']=1
                    self.put(p,v);candidate=self.commit(root)
                if mutation=='valid':self.assertEqual(auth.APPROVAL,auth.authority(candidate,require_ready=False)['approval'])
                else:
                    with self.assertRaises(EvidenceError):auth.authority(candidate,require_ready=False)

    def test_revocation_expiry_hold_scope_and_request_change_deny_before_commands(self):
        for mutation in ('revoke','expiry','scope','request','hold'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack);p=root/auth.APPROVAL;v=json.loads(p.read_text())
                if mutation=='revoke':v['status']='REVOKED'
                elif mutation=='expiry':v['expires_at']=time.time()-1
                elif mutation=='scope':v['execution_amendment']['additional_complete_native_runs']=1
                elif mutation=='request':(root/auth.REQUEST).write_bytes((root/auth.REQUEST).read_bytes()+b' ')
                else:self.put(root/'plans/execution-control.json',{'external_execution_hold':{'active':True}})
                self.put(p,v)
                with patch.object(subprocess,'run') as run,self.assertRaises(EvidenceError):auth.authority(candidate,require_ready=False)
                run.assert_not_called()

    def test_old_failure_denominator_closure_and_unclaimed_original_slot_are_required(self):
        for mutation in ('failure','denominator','open','grant','claimed','prepared'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                if mutation=='failure':self.put(root/'reports/v0-s2/full-checkpoint-01/receipt.json',{'decision':'PASS'})
                elif mutation=='open':(state/'full-checkpoint-01/lease.closed').write_bytes(b'0')
                elif mutation=='denominator':
                    p=root/auth.APPROVAL;v=json.loads(p.read_text());v['prior_failures'].pop();self.put(p,v)
                elif mutation=='grant':self.put(root/'reports/v0-s2/authorization-s2-resource-resume-01.approval.json',{'status':'ACTIVE'})
                elif mutation=='claimed':(state/auth.SLOT).mkdir()
                else:self.put(cp.child_path(auth.SLOT),{})
                with self.assertRaises(EvidenceError):auth.authority(candidate,require_ready=False)

    def test_original_slot_routes_only_after_new_same_candidate_readiness(self):
        for mutation in ('valid','other-candidate','open'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                ref='reports/v0-s2/'+auth.READY+'/receipt.json';digest=self.put(root/ref,{'decision':'RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE','sample_count':3})
                self.put(root/('reports/v0-s2/authorization-'+auth.READY+'.json'),{'status':'EXPIRED_RESOURCE_READY','candidate_sha':'b'*40 if mutation=='other-candidate' else candidate,
                    'terminal_receipt':ref,'terminal_receipt_sha256':digest,'scope':auth.readiness_scope()})
                (state/auth.READY).mkdir();(state/auth.READY/'lease.closed').write_bytes(b'0' if mutation=='open' else b'1')
                if mutation=='valid':self.assertEqual(auth.APPROVAL,cp.slot_authority(auth.SLOT,candidate)['approval'])
                else:
                    with self.assertRaises(EvidenceError):cp.slot_authority(auth.SLOT,candidate)


if __name__=='__main__':unittest.main()
