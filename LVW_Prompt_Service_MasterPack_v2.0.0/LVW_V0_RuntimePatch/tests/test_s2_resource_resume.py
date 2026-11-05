"""One extra admission restores an unclaimed slot; real own-file/Git boundaries."""
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
from LVW_V0_RuntimePatch.tests import test_s2_oracle_authorization as authority_fixtures


class ResourceResumeTests(unittest.TestCase):
    def fixture(self,parent,stack):
        request=cp.repository_json(oracle.RESUME_REQUEST);approval=cp.repository_json(oracle.RESUME_APPROVAL)
        helper=authority_fixtures.OracleAuthorityTests();root,state,original_candidate=helper.fixture(parent,stack)
        grant=json.loads((root/oracle.APPROVAL).read_text());grant['status']='EXPIRED_NO_GO';helper.put(root/oracle.APPROVAL,grant)
        request['original_approved_request_sha256']=oracle.REQUEST_SHA;request['corrected_candidate']=original_candidate
        offline=root/'reports/v0-s2/resume-offline-fixture.json';request['offline_receipt']=str(offline.relative_to(root));request['offline_receipt_sha256']=helper.put(offline,{'synthetic_offline':True})
        run=state/oracle.READY;run.mkdir();(run/'lease.closed').write_bytes(b'1')
        raw_sha=helper.put(run/'terminal.json',{'synthetic_native_not_run':True,'decision':'NO_GO'})
        ref='reports/v0-s2/'+oracle.READY+'/receipt.json';digest=helper.put(root/ref,{'decision':'NO_GO','raw_terminal_sha256':raw_sha,'model_calls':0,'service_starts':0,'media_reads':0,'browser_starts':0})
        request['prior_resource_failure'].update(receipt=ref,receipt_sha256=digest)
        helper.put(root/('reports/v0-s2/authorization-'+oracle.READY+'.json'),{'status':'EXPIRED_NO_GO','candidate_sha':original_candidate,'terminal_receipt':ref,'terminal_receipt_sha256':digest})
        new_sha=helper.put(root/oracle.RESUME_REQUEST,request)
        approval.update(issued_at=time.time()-1,expires_at=time.time()+300,request_sha256=new_sha,
            previous_grant_sha256=hashlib.sha256((root/oracle.APPROVAL).read_bytes()).hexdigest())
        helper.put(root/oracle.RESUME_APPROVAL,approval)
        p=root/'plans/execution-control.json';value=json.loads(p.read_text());value['resource_resume_authorization']=oracle.RESUME_APPROVAL;helper.put(p,value)
        p=root/'.agent-governance/stages/V0-S2/stage-control.json';stage=json.loads(p.read_text());stage['resource_resume_authorization']={'approval':oracle.RESUME_APPROVAL,'request':oracle.RESUME_REQUEST,
            'slot':oracle.SLOT,'readiness_slot':oracle.RESUME_READY,'max_new_readiness':1,'max_complete_claims':1,'max_extra_complete_runs':0,'max_rechecks':0};helper.put(p,stage)
        candidate=helper.commit(root);stack.enter_context(patch.object(oracle,'RESUME_SHA',new_sha))
        return helper,root,state,candidate

    def test_only_closed_old_admission_and_unclaimed_complete_slot_can_be_restored(self):
        for change in ('valid','old-open','old-success','old-grant-active','claim','prepared','raw-change'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                helper,root,state,candidate=self.fixture(Path(temp),stack)
                if change=='old-open':(state/oracle.READY/'lease.closed').write_bytes(b'0')
                elif change=='old-success':helper.put(root/('reports/v0-s2/authorization-'+oracle.READY+'.json'),{'status':'EXPIRED_RESOURCE_READY'})
                elif change=='old-grant-active':
                    p=root/oracle.APPROVAL;v=json.loads(p.read_text());v['status']='ACTIVE';helper.put(p,v)
                elif change=='claim':(state/oracle.SLOT).mkdir()
                elif change=='prepared':helper.put(cp.child_path(oracle.SLOT),{})
                elif change=='raw-change':helper.put(state/oracle.READY/'terminal.json',{'decision':'PASS'})
                if change=='valid':
                    refs=oracle.resume_authority(candidate,require_ready=False);self.assertEqual(oracle.RESUME_APPROVAL,refs['approval'])
                    self.assertEqual('EXPIRED_NO_GO',json.loads((root/oracle.APPROVAL).read_text())['status'])
                else:
                    with self.assertRaises(EvidenceError):oracle.resume_authority(candidate,require_ready=False)

    def test_expiry_revocation_extra_runs_and_rewritten_request_deny_without_commands(self):
        for change in ('expiry','revoked','budget','request','statement'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                helper,root,state,candidate=self.fixture(Path(temp),stack)
                p=root/oracle.RESUME_APPROVAL;v=json.loads(p.read_text())
                if change=='expiry':v['expires_at']=time.time()-1
                elif change=='revoked':v['status']='REVOKED'
                elif change=='budget':v['amendment']['additional_complete_native_runs']=1
                elif change=='statement':v['statement']='not explicit owner approval'
                elif change=='request':(root/oracle.RESUME_REQUEST).write_bytes((root/oracle.RESUME_REQUEST).read_bytes()+b' ')
                helper.put(p,v)
                with patch.object(subprocess,'run') as run,self.assertRaises(EvidenceError):oracle.resume_authority(candidate,require_ready=False)
                run.assert_not_called()

    def test_new_same_candidate_admission_is_required_before_original_full_prepare(self):
        for change in ('valid','wrong-candidate','not-closed'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                helper,root,state,candidate=self.fixture(Path(temp),stack)
                ref='reports/v0-s2/'+oracle.RESUME_READY+'/receipt.json';digest=helper.put(root/ref,{'decision':'RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE','sample_count':3})
                helper.put(root/('reports/v0-s2/authorization-'+oracle.RESUME_READY+'.json'),{'status':'EXPIRED_RESOURCE_READY','candidate_sha':'a'*40 if change=='wrong-candidate' else candidate,'terminal_receipt':ref,'terminal_receipt_sha256':digest})
                (state/oracle.RESUME_READY).mkdir();(state/oracle.RESUME_READY/'lease.closed').write_bytes(b'0' if change=='not-closed' else b'1')
                if change=='valid':self.assertEqual(oracle.RESUME_APPROVAL,cp.slot_authority(oracle.SLOT,candidate)['approval'])
                else:
                    with self.assertRaises(EvidenceError):cp.slot_authority(oracle.SLOT,candidate)

    def test_restore_still_rejects_product_or_fixed_threshold_changes(self):
        for change in ('product','threshold'):
            with self.subTest(change=change),tempfile.TemporaryDirectory() as temp,ExitStack() as stack:
                helper,root,state,candidate=self.fixture(Path(temp),stack)
                if change=='product':helper.put(root/'LVW_V0_RuntimePatch/changed-product.json',{})
                else:
                    p=root/'.agent-governance/stages/V0-S2/stage-control.json';v=json.loads(p.read_text());v['budgets']['stage_checkpoints']=2;helper.put(p,v)
                candidate=helper.commit(root)
                with self.assertRaises(EvidenceError):oracle.resume_authority(candidate,require_ready=False)


if __name__=='__main__':unittest.main()
