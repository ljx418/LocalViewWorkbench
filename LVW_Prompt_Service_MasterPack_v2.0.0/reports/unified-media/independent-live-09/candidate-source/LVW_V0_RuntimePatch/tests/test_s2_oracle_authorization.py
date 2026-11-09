"""Real temporary Git authority/claim checks; no native target/service access."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import v0_s2_stage_checkpoint as cp
from tools import v0_s2_oracle_authorization as oracle
from tools.v0_s2_checkpoint_oracles import EvidenceError


class OracleAuthorityTests(unittest.TestCase):
    def put(self,path,value):
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(cp.canonical(value))
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def git(self,root,*args):
        return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()

    def commit(self,root):
        self.git(root,'add','.');self.git(root,'-c','user.name=fixture','-c','user.email=fixture@example.invalid','commit','-qm','synthetic fixture')
        return self.git(root,'rev-parse','HEAD')

    def fixture(self,parent,stack):
        root=parent/'pack';root.mkdir();state=parent/'state';state.mkdir()
        spec='.agent-governance/stages/V0-S2/stage-control.json'
        stage=cp.repository_json(spec);stage.pop('oracle_correction_authorization',None)
        self.put(root/spec,stage);self.put(root/cp.PROGRAM,cp.repository_json(cp.PROGRAM))
        control={'coordinate':{'stage_id':'V0-S2'},'external_execution_hold':{'active':False}}
        self.put(root/'plans/execution-control.json',control)
        self.git(root,'init','-q');baseline=self.commit(root)
        request=cp.repository_json(oracle.REQUEST);request['corrected_candidate']=baseline
        request['offline_receipt']='reports/v0-s2/synthetic-offline.json';request['offline_receipt_sha256']=self.put(root/request['offline_receipt'],{'kind':'explicit synthetic offline fixture'})
        request['seed_artifact_sha256']={};request['prior_failed_runs']=[]
        for name in ['full-checkpoint-01','full-recheck-01','full-supplemental-01','full-resource-ready-01']:
            ref='reports/v0-s2/'+name+'/receipt.json';digest=self.put(root/ref,{'decision':'NO_GO'})
            request['prior_failed_runs'].append({'run_id':name,'receipt':ref,'receipt_sha256':digest})
            (state/name).mkdir();(state/name/'lease.closed').write_bytes(b'1')
        cleanup=request['existing_cleanup'];cleanup['receipt_sha256']=self.put(root/cleanup['receipt'],{'decision':'CLEANUP_PROVEN_NOT_PRODUCT_ACCEPTANCE'})
        directory=state/'full-resource-ready-01';owned=directory/'synthetic-owned-absent'
        terminal={'runtime_evidence':{'default':{'owned_run_root':str(owned)}}}
        terminal_sha=self.put(directory/'terminal.json',terminal);manifest_sha=self.put(directory/'default-raw/ARCHIVE_MANIFEST.json',{'synthetic':True})
        self.put(directory/'default-root-lease.json',{'root':str(owned),'run_id':'full-resource-ready-01','candidate_sha':'a'*40})
        facts={'raw_terminal_sha256':terminal_sha,'archive_manifest_sha256':manifest_sha,'owned_cleanup_proven':True,
            'runtime_root_absent':True,'run_id':'full-resource-ready-01','candidate_sha':'a'*40}
        cleanup['resource_ready_fact_sha256']=self.put(root/cleanup['resource_ready_fact_receipt'],facts)
        request_sha=self.put(root/oracle.REQUEST,request)
        grant=cp.repository_json(oracle.APPROVAL);grant.update(status='ACTIVE',issued_at=time.time()-1,expires_at=time.time()+300,
            request_sha256=request_sha,granted_by='project_owner',runtime_execution_allowed_now=True,resume_statement=oracle.RESUME)
        self.put(root/oracle.APPROVAL,grant)
        stage['oracle_correction_authorization']={'approval':oracle.APPROVAL,'request':oracle.REQUEST,'slot':oracle.SLOT,'max_runs':1,'max_rechecks':0}
        self.put(root/spec,stage);candidate=self.commit(root)
        for owner,key,value in [(cp,'ROOT',root),(cp,'STATE_ROOT',state),(oracle,'DOC_REVISION',baseline),(oracle,'REQUEST_SHA',request_sha)]:
            stack.enter_context(patch.object(owner,key,value))
        return root,state,candidate

    def test_real_git_descendant_preserves_scope_and_rejects_product_or_threshold_changes(self):
        for mutation in ('product','contract','docs','threshold'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                self.assertEqual(oracle.REQUEST_SHA,oracle.authority(candidate,require_ready=False)['request_sha256'])
                if mutation=='threshold':
                    p=root/'.agent-governance/stages/V0-S2/stage-control.json';v=json.loads(p.read_text());v['budgets']['corrected_candidate_full_rechecks']=2;self.put(p,v)
                else:self.put(root/({'product':'LVW_V0_RuntimePatch/product.json','contract':'contracts/new.json','docs':'docs/arbitrary.json'}[mutation]),{})
                bad=self.commit(root)
                with self.assertRaises(EvidenceError):oracle.authority(bad,require_ready=False)

    def test_revocation_hold_expiry_request_change_and_budget_broadening_deny_before_git(self):
        for mutation in ('revoked','held','expired','request','budget','resume'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                p=root/oracle.APPROVAL;v=json.loads(p.read_text())
                if mutation=='revoked':v['status']='REVOKED'
                elif mutation=='expired':v['expires_at']=time.time()-1
                elif mutation=='budget':v['complete_runs_approved']=2
                elif mutation=='resume':v['resume_statement']='not an owner resume'
                elif mutation=='held':self.put(root/'plans/execution-control.json',{'external_execution_hold':{'active':True}})
                elif mutation=='request':(root/oracle.REQUEST).write_bytes((root/oracle.REQUEST).read_bytes()+b' ')
                self.put(p,v)
                with patch.object(subprocess,'run') as run,self.assertRaises(EvidenceError):oracle.authority(candidate,require_ready=False)
                run.assert_not_called()

    def test_same_candidate_fresh_readiness_is_mandatory_and_cannot_use_old_slot(self):
        for mutation in ('valid','different-candidate','not-closed','wrong-decision'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                ref='reports/v0-s2/'+oracle.READY+'/receipt.json';digest=self.put(root/ref,{'decision':'NO_GO' if mutation=='wrong-decision' else 'RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE','sample_count':3})
                self.put(root/('reports/v0-s2/authorization-'+oracle.READY+'.json'),{'status':'EXPIRED_RESOURCE_READY','candidate_sha':'b'*40 if mutation=='different-candidate' else candidate,'terminal_receipt':ref,'terminal_receipt_sha256':digest})
                (state/oracle.READY).mkdir();(state/oracle.READY/'lease.closed').write_bytes(b'0' if mutation=='not-closed' else b'1')
                if mutation=='valid':oracle.authority(candidate,require_ready=True)
                else:
                    with self.assertRaises(EvidenceError):oracle.authority(candidate,require_ready=True)

    def test_prior_failure_cleanup_and_original_root_cannot_be_replaced(self):
        for mutation in ('failure','open','cleanup','root','lease'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                root,state,candidate=self.fixture(Path(temp),stack)
                if mutation=='failure':self.put(root/'reports/v0-s2/full-checkpoint-01/receipt.json',{'decision':'PASS'})
                elif mutation=='open':(state/'full-recheck-01/lease.closed').write_bytes(b'0')
                elif mutation=='cleanup':self.put(root/'reports/v0-s2/resource-ready-failure-facts-01.json',{})
                elif mutation=='root':(state/'full-resource-ready-01/synthetic-owned-absent').mkdir()
                else:
                    p=state/'full-resource-ready-01/default-root-lease.json';v=json.loads(p.read_text());v['root']=str(state/'arbitrary-absent');self.put(p,v)
                with self.assertRaises(EvidenceError):oracle.authority(candidate,require_ready=False)

    def test_full_slot_cannot_skip_new_authority_and_unknown_slots_remain_closed(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(cp,'ROOT',Path(temp)),patch.object(cp,'STATE_ROOT',Path(temp)/'state'),patch.object(oracle,'authority',side_effect=EvidenceError('fresh admission missing')) as authority,patch.object(cp,'resolve_installed') as target:
            with self.assertRaises(EvidenceError):cp.prepare(oracle.SLOT,'a'*40,'reports/v0-s2/offline-checkpoint-26/receipt.json')
            authority.assert_called_once_with('a'*40,require_ready=True);target.assert_not_called()
            self.assertFalse(cp.child_path(oracle.SLOT).exists())
        with self.assertRaises(EvidenceError):cp.child_path('full-oracle-correction-02')


if __name__=='__main__':unittest.main()
