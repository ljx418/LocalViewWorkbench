"""Directed child authority/admission tests; no native services or media."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from tools import v0_s2_browser_component as component
from tools import v0_s2_automatic_verification as admission
from tools import v0_verification_authority as authority
from tools import v0_s2_component_clearance as clearance


class ComponentAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.patch=patch.object(component.cp,'ROOT',self.root);self.patch.start()
        def write(name,value):
            p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_text(json.dumps(value));return p
        self.write=write
        self.program={'status':'ACTIVE','authorization_id':'AUTH-PROGRAM-V0-LOCAL-VERIFICATION-01',
            'granted_by':'project_owner','statement':authority.STATEMENT,'stages':['V0-S2'],'stage_pass_claim':False}
        self.program_path=write(authority.PROGRAM,self.program)
        self.control=write('plans/execution-control.json',{'coordinate':{'stage_id':'V0-S2'},'external_execution_hold':{'active':False}})
        self.harness=write(component.HARNESS,{'synthetic':'CPU-only harness fixture'})
        self.stage=write('.agent-governance/stages/V0-S2/stage-control.json',{'synthetic':'frozen packet fixture'})
        self.directory=self.root/'state/browser-component-01';self.directory.mkdir(parents=True)
        child=authority.child(self.program,stage='V0-S2',run_id='browser-component-01',candidate='a'*40,
            harness_sha256=component.cp.file_hash(self.harness),program_sha256=component.cp.file_hash(self.program_path),
            budget={'downloads':0,'paid_calls':0,'cloud_calls':0},max_seconds=120)
        child.update(scope=component.SCOPE,stage_packet_sha256=component.cp.file_hash(self.stage))
        (self.directory/'active-child.json').write_text(json.dumps(child));(self.directory/'claimed-child.json').write_text(json.dumps(child))
        (self.directory/'lease.closed').write_bytes(b'0')
        self.lease=component.Lease(self.directory,child)

    def tearDown(self):self.patch.stop();self.temp.cleanup()

    def test_terminal_replay_revocation_hold_and_expiry_refuse_before_target_work(self):
        self.lease.authorize('component_source_ready');self.assertEqual(self.lease.actions,1)
        (self.directory/'lease.closed').write_bytes(b'1')
        with self.assertRaises(ValueError):self.lease.authorize('start_owned_comfy')
        (self.directory/'lease.closed').write_bytes(b'0')
        self.program['status']='REVOKED';self.program_path.write_text(json.dumps(self.program))
        with self.assertRaises(ValueError):self.lease.authorize('start_owned_ollama')
        self.program['status']='ACTIVE';self.program_path.write_text(json.dumps(self.program))
        self.control.write_text(json.dumps({'coordinate':{'stage_id':'V0-S2'},'external_execution_hold':{'active':True}}))
        with self.assertRaises(ValueError):self.lease.authorize('start_owned_comfy')
        self.assertEqual(self.lease.actions,1)

    def test_changed_harness_packet_and_child_are_not_silently_accepted(self):
        for p in [self.harness,self.stage,self.directory/'active-child.json']:
            before=p.read_bytes();p.write_bytes(before+b' ')
            with self.assertRaises(ValueError):self.lease.authorize('start_owned_comfy')
            p.write_bytes(before)
        self.lease.child['expires_at']=time.time()-1
        with self.assertRaises(ValueError):self.lease.authorize('start_owned_comfy')

    def test_reserved_cleanup_never_grants_new_work_and_product_denominator_fixed(self):
        self.program['status']='REVOKED';self.program_path.write_text(json.dumps(self.program))
        # Factory preparation failure invokes archive before outer finally.
        self.lease.authorize('archive_owned_terminal_root')
        self.lease.authorize('remove_owned_terminal_reparse_fixture')
        self.lease.cleanup_only=True
        with self.assertRaises(ValueError):self.lease.authorize('start_owned_ollama')
        self.lease.authorize('archive_owned_terminal_root')
        self.assertEqual(len(component.CASES),9)
        self.assertEqual(len(set(component.CASES)),9)

    def test_active_or_unclosed_component_blocks_complete_checkpoint_admission(self):
        with patch.object(component.cp,'STATE_ROOT',self.root/'state'):
            with self.assertRaises(ValueError):admission.require_closed_runs()
            (self.directory/'lease.closed').unlink()
            with self.assertRaises(ValueError):admission.require_closed_runs()
            (self.directory/'lease.closed').write_bytes(b'1')
            with self.assertRaises((ValueError,OSError)):admission.require_closed_runs()
            terminal={'kind':component.SCOPE,'run_id':'browser-component-01','candidate_sha':'a'*40,
                'authorization_sha256':component.cp.file_hash(self.directory/'claimed-child.json'),
                'stage_pass_claim':False,'stage_checkpoint_consumed':False,'runtime_evidence':{}}
            (self.directory/'terminal.json').write_text(json.dumps(terminal))
            self.assertTrue(clearance.write_clearance(self.directory)['safe_for_next_runtime']);admission.require_closed_runs()
            terminal['runtime_evidence']={'default':{'owned_run_root':'uncertain'}}
            (self.directory/'terminal.json').write_text(json.dumps(terminal))
            with self.assertRaises(ValueError):admission.require_closed_runs()

    def test_uncertain_cleanup_and_pending_callbacks_cannot_release_admission(self):
        terminal={'kind':component.SCOPE,'run_id':'browser-component-01','candidate_sha':'a'*40,
            'authorization_sha256':component.cp.file_hash(self.directory/'claimed-child.json'),
            'stage_pass_claim':False,'stage_checkpoint_consumed':False,'cleanup':{'proven':False},
            'runtime_evidence':{'default':{'owned_run_root':'unknown'}},
            'browser':{'browser_cleanup_proven':False,'callbacks_pending':1}}
        (self.directory/'terminal.json').write_text(json.dumps(terminal));(self.directory/'lease.closed').write_bytes(b'1')
        self.assertFalse(clearance.write_clearance(self.directory)['safe_for_next_runtime'])
        with patch.object(component.cp,'STATE_ROOT',self.root/'state'),self.assertRaises(ValueError):admission.require_closed_runs()
        record=json.loads((self.directory/'runtime-clearance.json').read_text());record['safe_for_next_runtime']=True
        (self.directory/'runtime-clearance.json').write_text(json.dumps(record))
        with patch.object(component.cp,'STATE_ROOT',self.root/'state'),self.assertRaises(ValueError):admission.require_closed_runs()

    def test_factory_preparation_failure_retains_reserved_archive_after_revocation(self):
        from LVW_V0_RuntimePatch.tests.test_s2_stage_runtime import FactoryTests
        helper=FactoryTests();helper.setUp()
        try:
            helper.archive.authorize=self.lease.authorize
            def guard(action,detail=None):
                if action=='start_owned_ollama':
                    self.program['status']='REVOKED';self.program_path.write_text(json.dumps(self.program))
                return self.lease.authorize(action,detail)
            helper.kwargs['authorize']=guard
            factory=component.StageRuntimeFactory(**helper.kwargs)
            with self.assertRaises(ValueError):factory.prepare_default()
            failure=json.loads((helper.directory/'default-preparation-failure.json').read_text())
            self.assertTrue(failure['archive']['proven']);self.assertFalse(failure['root_retained'])
            self.assertNotIn('ollama-start',helper.events)
        finally:helper.doCleanups()

    def test_full_slot_cannot_be_relabelled_as_directed_component(self):
        with patch.object(component.cp,'repository_json') as read:
            with self.assertRaises(ValueError):component.run('a'*40,'unused','full-v0-auto-99')
            read.assert_not_called()
