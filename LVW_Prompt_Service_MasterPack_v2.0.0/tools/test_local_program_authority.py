"""Real SQLite transactions in private copies; never issues a project execution child."""
import concurrent.futures
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import local_program_authority as authority


class AuthorityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'reports').mkdir()
        self.request = json.loads((authority.ROOT / authority.REQUEST).read_text())
        (self.root / authority.REQUEST).write_text(json.dumps(self.request))
        self.grant = {'status': 'ACTIVE', 'decision': 'APPROVED', 'granted_by': 'project_owner',
                      'authorization_id': 'AUTH-PROGRAM-V1-LOCAL-02',
                      'request_sha256': authority.digest(self.root / authority.REQUEST)}
        (self.root / authority.APPROVAL).write_text(json.dumps(self.grant))
        self.ledger = self.root / 'state.sqlite'
        self.budget = dict(model_calls=2, provider_calls=2, full_checkpoints=1, api_starts=1)

    def reserve(self, run='test-01', stage='R1', seconds=100, budget=None, full=True):
        authority.reserve(run, stage, budget if budget is not None else self.budget,
                          seconds, full, ledger=self.ledger, root=self.root)

    def child(self, run='test-01'):
        self.reserve(run)
        source = self.root / 'source.py'
        source.write_text('frozen')
        child = self.root / (run + '.json')
        child.write_text(json.dumps(dict(run_id=run, budget_ledger=str(self.ledger),
            program_sha256=authority.digest(self.root / authority.APPROVAL),
            frozen_files=[dict(path='source.py',sha256=authority.digest(source))])))
        authority.bind(run, child, ledger=self.ledger)
        return child

    def action(self, child):
        with patch.object(authority, 'ROOT', self.root):
            return authority.model_action(child)

    def test_absent_revoked_and_hash_changed_approval(self):
        for field, value in [('status','REVOKED'),('decision','PENDING'),('request_sha256','0'*64)]:
            grant = dict(self.grant, **{field:value})
            (self.root / authority.APPROVAL).write_text(json.dumps(grant))
            with self.assertRaises(ValueError): self.reserve()
        (self.root / authority.APPROVAL).unlink()
        with self.assertRaises(FileNotFoundError): self.reserve()
        self.assertFalse(self.ledger.exists())

    def test_exact_action_cap_one_over_and_full_claim_before_send(self):
        child = self.child()
        self.action(child); self.action(child)
        with self.assertRaises(ValueError): self.action(child)
        report = authority.settle('test-01', 2, ledger=self.ledger)
        self.assertTrue(report['effective_full_checkpoint'])
        self.assertEqual(report['actual_model_actions'],2)
        with self.assertRaises(ValueError): self.action(child)
        with self.assertRaises(ValueError): self.reserve()

    def test_zero_model_startup_separate_full_not_consumed(self):
        self.reserve()
        report = authority.settle('test-01',0,ledger=self.ledger)
        self.assertFalse(report['effective_full_checkpoint'])
        self.assertTrue(report['zero_model_startup'])

    def test_no_refund_if_evidence_count_differs(self):
        child = self.child(); self.action(child)
        with self.assertRaises(ValueError): authority.settle('test-01',0,ledger=self.ledger)
        with authority.transaction(self.ledger) as db:
            self.assertEqual(db.execute('SELECT active FROM children').fetchone()[0],1)

    def test_terminal_with_unknown_cleanup_disables_send_keeps_reservation(self):
        child=self.child()
        authority.close_retaining_reservation('test-01',ledger=self.ledger)
        with self.assertRaises(ValueError):self.action(child)
        with authority.transaction(self.ledger) as db:
            rows=list(db.execute('SELECT * FROM children'))
            self.assertEqual(rows[0]['active'],2)
            self.assertEqual(authority.totals(rows)['model'],2)

    def test_source_child_tamper_and_expiry_deny_before_count(self):
        child = self.child(); original=child.read_bytes()
        child.write_bytes(original+b' ')
        with self.assertRaises(ValueError): self.action(child)
        child.write_bytes(original)
        (self.root/'source.py').write_text('drift')
        with self.assertRaises(ValueError): self.action(child)
        (self.root/'source.py').write_text('frozen')
        with authority.transaction(self.ledger) as db:
            db.execute('UPDATE children SET expires=0')
        with self.assertRaises(ValueError): self.action(child)
        with authority.transaction(self.ledger) as db:
            self.assertEqual(db.execute('SELECT calls FROM children').fetchone()[0],0)

    def test_unknown_stage_side_effects_boolean_negative_and_ceiling(self):
        with self.assertRaises(ValueError): self.reserve(stage='R3')
        for budget in (dict(self.budget,downloads=1), dict(self.budget,model_calls=True),
                       dict(self.budget,model_calls=-1),dict(self.budget,model_calls=129),
                       dict(self.budget,unknown=1)):
            with self.assertRaises(ValueError): self.reserve(budget=budget)
        self.reserve(seconds=21600)
        with self.assertRaises(ValueError): self.reserve('other',seconds=21601)

    def test_stage_full_reservations_survive_crash_exact_and_over(self):
        for i in range(3):self.reserve(f'run-{i}')
        with self.assertRaises(ValueError):self.reserve('over')

    def test_zero_startup_limit_exact_and_over(self):
        for i in range(4):
            run=f'zero-{i}';self.reserve(run);authority.settle(run,0,ledger=self.ledger)
        with self.assertRaises(ValueError):self.reserve('zero-over')

    def test_zero_production_start_not_cpu_fixture(self):
        for i in range(4):
            run=f'zero-{i}';self.reserve(run,budget={'api_starts':1},full=False)
            report=authority.settle(run,0,ledger=self.ledger)
            self.assertTrue(report['zero_model_startup'])
        with self.assertRaises(ValueError):self.reserve('over',budget={'api_starts':1},full=False)

    def test_concurrent_action_cap_atomic(self):
        child=self.child()
        def act(_):
            try:authority.model_action(child);return True
            except ValueError:return False
        with patch.object(authority,'ROOT',self.root):
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
                result=list(pool.map(act,range(8)))
        self.assertEqual(sum(result),2)

    def test_program_budget_across_stages(self):
        budget=dict(model_calls=128,provider_calls=128,full_checkpoints=1)
        for i,stage in enumerate(['R0','R1a','R1','R2']):self.reserve(f'run-{i}',stage,budget=budget)
        with self.assertRaises(ValueError):self.reserve('over','V0-S2',budget=budget)

    def test_extra_full_run_requires_exact_one_shot_hash_bound_approval(self):
        for i in range(3):self.reserve(f'used-{i}')
        with self.assertRaises(ValueError):self.reserve('live-08')
        request=dict(authorization_id='AUTH-BUDGET-V1-R1-RESIDUAL-01',run_id='live-08',stage_id='R1',
            parent_approval_sha256=authority.digest(self.root/authority.APPROVAL),
            old_stage_full_limit=3,new_stage_full_limit=4,additional_full_runs=1,budget=self.budget,max_seconds=100)
        path=self.root/(authority.AMENDMENT+'.request.json');path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(request))
        with self.assertRaises(ValueError):self.reserve('live-08')
        grant=dict(authorization_id=request['authorization_id'],decision='APPROVED',status='ACTIVE',
                   granted_by='project_owner',request_sha256=authority.digest(path))
        grant_path=self.root/(authority.AMENDMENT+'.approval.json')
        for field,value in [('decision','PENDING'),('status','REVOKED'),('request_sha256','0'*64),('granted_by','implementer')]:
            grant_path.write_text(json.dumps(dict(grant,**{field:value})))
            with self.assertRaises(ValueError):self.reserve('live-08')
        grant_path.write_text(json.dumps(grant))
        with self.assertRaises(ValueError):self.reserve('live-09')
        with self.assertRaises(ValueError):self.reserve('live-08',seconds=101)
        self.reserve('live-08')
        with self.assertRaises(ValueError):self.reserve('live-08')
        with self.assertRaises(ValueError):self.reserve('live-09')
        grant_path.with_suffix('.terminal.json').write_text('{}')
        with self.assertRaises(ValueError):authority.extra_full_grant('live-08','R1',root=self.root)

    def test_execution_tool_binding_required_and_tamper_rejected(self):
        child=self.child()
        data=json.loads(child.read_text());data['execution_bindings_required']=True
        # Private fixture re-issue before any send, using a new DB to retain immutable bind semantics.
        self.ledger.unlink();self.reserve();child.write_text(json.dumps(data))
        authority.bind('test-01',child,ledger=self.ledger)
        with self.assertRaises(ValueError):self.action(child)
        tool=self.root/'tool';tool.write_text('installed')
        bindings=self.root/'bindings.json'
        bindings.write_text(json.dumps({'tool':{'path':str(tool),'sha256':authority.digest(tool)}}))
        authority.bind_execution('test-01',bindings,ledger=self.ledger)
        self.action(child)
        tool.write_text('changed')
        with self.assertRaises(ValueError):self.action(child)


class CompleteProgramTests(unittest.TestCase):
    def setUp(self):
        self.fixture=AuthorityTests(methodName='runTest')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.ledger=self.fixture.ledger
        request=json.loads((authority.ROOT/authority.COMPLETE_REQUEST).read_text())
        request['existing_program_approval_sha256']=authority.digest(self.root/authority.APPROVAL)
        (self.root/authority.COMPLETE_REQUEST).write_text(json.dumps(request))
        self.save_grant()

    def save_grant(self):
        grant=dict(status='ACTIVE',decision='APPROVED',granted_by='project_owner',
                   authorization_id='AUTH-PROGRAM-V1-COMPLETE-03',
                   request_sha256=authority.digest(self.root/authority.COMPLETE_REQUEST))
        (self.root/authority.COMPLETE_APPROVAL).write_text(json.dumps(grant))

    def test_same_ledger_history_not_reset_and_live08_no_second_grant(self):
        for i in range(3):
            self.fixture.reserve(f'history-{i}')
            with authority.transaction(self.ledger) as db:
                db.execute('UPDATE children SET calls=3,cap=8,checkpoint=1,active=0,elapsed=60 WHERE run=?',(f'history-{i}',))
        self.fixture.reserve('live-08')
        with authority.transaction(self.ledger) as db:
            rows=list(db.execute('SELECT * FROM children'))
            self.assertEqual(authority.totals(rows)['model'],11)
            self.assertEqual(authority.totals(rows)['full'],4)
            self.assertEqual(len(rows),4)

    def test_no_stage_start_cpu_or_zero_model_count_caps(self):
        for i in range(18):
            run=f'cpu-{i}'
            authority.reserve(run,'R1',{},1,False,ledger=self.ledger,root=self.root,cpu_fixture=True)
            authority.settle(run,0,ledger=self.ledger)
        for i in range(14):
            run=f'zero-{i}'
            self.fixture.reserve(run,budget={'api_starts':1},full=False)
            authority.settle(run,0,ledger=self.ledger)

    def test_global_full_exact_and_one_over(self):
        for i in range(24):self.fixture.reserve(f'full-{i}')
        with self.assertRaises(ValueError):self.fixture.reserve('full-over')

    def test_global_model_exact_and_one_over(self):
        for i in range(8):self.fixture.reserve(f'model-{i}',budget={'model_calls':128,'full_checkpoints':1})
        with self.assertRaises(ValueError):self.fixture.reserve('model-over')

    def test_global_production_seconds_excludes_cpu(self):
        for i in range(8):self.fixture.reserve(f'time-{i}',seconds=21600)
        with self.assertRaises(ValueError):self.fixture.reserve('time-over')
        authority.reserve('cpu','R1',{},100,False,ledger=self.ledger,root=self.root,cpu_fixture=True)

    def test_cutover_marker_blocks_missing_new_grant_old_grant_not_fallback(self):
        (self.root/'plans').mkdir()
        (self.root/'plans/execution-control.json').write_text(json.dumps({'authorization_record':authority.COMPLETE_APPROVAL}))
        (self.root/authority.COMPLETE_APPROVAL).unlink()
        with self.assertRaises(FileNotFoundError):self.fixture.reserve()

    def test_revocation_hash_change_and_scope_rejected(self):
        grant=json.loads((self.root/authority.COMPLETE_APPROVAL).read_text())
        for key,value in [('status','REVOKED'),('request_sha256','0'*64),('granted_by','implementer')]:
            (self.root/authority.COMPLETE_APPROVAL).write_text(json.dumps(dict(grant,**{key:value})))
            with self.assertRaises(ValueError):self.fixture.reserve()
        self.save_grant()
        with self.assertRaises(ValueError):self.fixture.reserve(stage='R3')
        with self.assertRaises(ValueError):self.fixture.reserve(budget={'model_calls':129,'full_checkpoints':1})
        with self.assertRaises(ValueError):self.fixture.reserve(budget={'model_calls':1,'full_checkpoints':1,'downloads':1})

    def test_send_binds_new_grant_and_no_live08_amendment_needed(self):
        self.fixture.reserve('live-08')
        source=self.root/'source';source.write_text('source')
        child=self.root/'live08.json'
        child.write_text(json.dumps(dict(run_id='live-08',stage_id='R1',budget_ledger=str(self.ledger),
            program=authority.COMPLETE_APPROVAL,program_sha256=authority.digest(self.root/authority.COMPLETE_APPROVAL),
            frozen_files=[{'path':'source','sha256':authority.digest(source)}])))
        authority.bind('live-08',child,ledger=self.ledger)
        with patch.object(authority,'ROOT',self.root):authority.model_action(child)
        result=authority.settle('live-08',1,ledger=self.ledger)
        self.assertTrue(result['effective_full_checkpoint'])


if __name__ == '__main__':unittest.main()
