"""S3 synthetic roots + real SQLite transactions; no original ledger access."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time
import uuid

import pytest
from tools import local_program_authority as original
from tools.v0_s3_budget_authority import module_at
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import program_budget as budget

ROOT=Path(__file__).resolve().parents[1]


class Fixture:
    def __init__(self, root, cap=8, seconds=600):
        self.root=root;root.mkdir()
        (root/'.s3-synthetic-fixture').touch()
        for name in ('tools/local_program_authority.py','tools/v0_s3_budget_authority.py',
                     'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py',
                     original.REQUEST,original.APPROVAL,original.COMPLETE_REQUEST,original.COMPLETE_APPROVAL):
            target=root/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(ROOT/name,target)
        self.authority=module_at('_fixture_authority',root/'tools/local_program_authority.py')
        self.shim=module_at('_fixture_shim',root/'tools/v0_s3_budget_authority.py')
        self.ledger=root/'original.sqlite';self.child=root/'child.json';self.binding=root/'binding.json';self.execution=root/'execution.json'
        self.authority.reserve('synthetic','V0-S3',{'model_calls':cap,'full_checkpoints':1},seconds,True,ledger=self.ledger,root=root)
        self.source=root/'frozen-source';self.source.write_text('fixture source')
        def role(path):return {'path':str(path),'client_path':str(path),'sha256':budget.digest(path)}
        roles={'authority':role(root/'tools/local_program_authority.py'),'shim':role(root/'tools/v0_s3_budget_authority.py'),
               'python':role(Path(sys.executable).resolve()),'wsl':None}
        ex={'s3_'+k:{'path':v['path'],'sha256':v['sha256']} for k,v in roles.items() if v is not None}
        helper=root/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py'
        ex['s3_protocol']={'path':str(helper),'sha256':budget.digest(helper)}
        self.execution.write_text(json.dumps(ex))
        now=time.time()
        self.config={'schema':'lvw.s3-budget/1','program':budget.PROGRAM,'approval_sha256':budget.digest(root/original.COMPLETE_APPROVAL),
            'run_id':'synthetic','stage_id':'V0-S3','candidate_sha':'a'*40,'child_path':str(self.child),'child_sha256':'0'*64,
            'ledger_path':str(self.ledger),'execution_path':str(self.execution),'execution_sha256':budget.digest(self.execution),
            'authority_root':str(root),'tools':roles,'issued_at':now,'expires_at':now+seconds-100,
            'transport':'local-fixture','harness_transport':'local-fixture','distribution':None,'binding_path':str(self.binding),'client_binding_path':str(self.binding),
            'model':'gemma4:26b','model_digest':'b'*64,'ollama_pid':123,'ollama_start_ticks':456}
        child={'run_id':'synthetic','stage_id':'V0-S3','candidate_sha':'a'*40,'budget_ledger':str(self.ledger),
               'program':original.COMPLETE_APPROVAL,'program_sha256':self.config['approval_sha256'],
               'frozen_files':[{'path':'frozen-source','sha256':budget.digest(self.source)}],
               'execution_bindings_required':True,'s3_budget':{k:v for k,v in self.config.items() if k!='child_sha256'}}
        self.child.write_text(json.dumps(child));self.config['child_sha256']=budget.digest(self.child)
        self.authority.bind('synthetic',self.child,ledger=self.ledger)
        self.authority.bind_execution('synthetic',self.execution,ledger=self.ledger)
        self.save()

    def save(self):
        self.binding.write_text(json.dumps(self.config))
        self.ref={'path':str(self.binding),'sha256':budget.digest(self.binding)}
        return self.ref

    def row(self):
        with sqlite3.connect(self.ledger.as_uri()+'?mode=ro',uri=True) as db:
            db.row_factory=sqlite3.Row
            return dict(db.execute('SELECT * FROM children WHERE run="synthetic"').fetchone())

    def request(self):
        return {'schema':'lvw.s3-debit/1','request_id':str(uuid.uuid4()),'action_kind':'chat','payload_sha256':'c'*64,
                'model':'gemma4:26b','binding_path':str(self.binding),'binding_sha256':self.ref['sha256']}

    def enable(self, monkeypatch):
        monkeypatch.setenv('LVW_S3_BUDGET_REQUIRED','1');monkeypatch.setenv('LVW_S3_BUDGET_BINDING',str(self.binding))
        monkeypatch.setenv('LVW_S3_BUDGET_BINDING_SHA256',self.ref['sha256'])


@pytest.fixture
def fixture(tmp_path):
    value=Fixture(tmp_path/'authority')
    try:yield value
    finally:shutil.rmtree(value.root)



def test_real_subprocess_debit_and_exact_cap(fixture):
    f=fixture
    body=b'{"model":"gemma4:26b"}'
    for count in range(1,9):
        receipt=budget.authorize_model_action('chat',body,binding=f.ref)
        assert receipt['status']=='DEBITED' and receipt['process']['exit_code']==0 and receipt['process']['error'] is None
        assert receipt['payload_sha256']==hashlib.sha256(body).hexdigest()
        assert f.row()['calls']==count and f.row()['checkpoint']==1
    with pytest.raises(Exception):budget.authorize_model_action('chat',body,binding=f.ref)
    assert f.row()['calls']==8


def test_concurrent_transactions_one_over(fixture):
    def action(_):
        try:fixture.shim.debit(fixture.request());return True
        except ValueError:return False
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:results=list(pool.map(action,range(12)))
    assert sum(results)==8 and fixture.row()['calls']==8


@pytest.mark.parametrize('fault',['source','child','tool','execution','approval','expiry','candidate','ledger','root','unknown','missing'])
def test_refusal_zero_debits_and_no_new_ledger(fixture,fault):
    f=fixture
    if fault=='source':f.source.write_text('changed')
    elif fault=='child':f.child.write_text(f.child.read_text()+' ')
    elif fault=='tool':(f.root/'tools/local_program_authority.py').write_text('# altered')
    elif fault=='execution':f.execution.write_text('{}')
    elif fault=='approval':(f.root/original.COMPLETE_APPROVAL).write_text('{}')
    elif fault=='expiry':
        with sqlite3.connect(f.ledger) as db:db.execute('UPDATE children SET expires=0')
    elif fault=='candidate':f.config['candidate_sha']='d'*40;f.save()
    elif fault=='ledger':f.config['ledger_path']=str(f.root/'substitute.sqlite');f.save()
    elif fault=='root':f.config['authority_root']=str(f.root.parent);f.save()
    elif fault=='unknown':f.config['argv']=['sh'];f.save()
    elif fault=='missing':del f.config['tools'];f.save()
    with pytest.raises((ValueError,FileNotFoundError,KeyError)):f.shim.debit(f.request())
    assert f.row()['calls']==0 and not (f.root/'substitute.sqlite').exists()


def test_missing_original_file_cannot_recreate(fixture):
    fixture.ledger.unlink()
    with pytest.raises(ValueError,match='ledger missing'):fixture.shim.debit(fixture.request())
    assert not fixture.ledger.exists()


def test_original_history_retained_and_no_refund(fixture):
    f=fixture
    with sqlite3.connect(f.ledger) as db:
        db.execute("INSERT INTO children(run,stage,cap,seconds,full,cpu,starts,issued,expires,calls,checkpoint,active,elapsed) VALUES('history','R1',29,1506,1,0,'{}',0,1,29,8,0,1506)")
    f.shim.debit(f.request())
    with sqlite3.connect(f.ledger) as db:assert db.execute('SELECT SUM(calls),SUM(checkpoint) FROM children').fetchone()==(30,9)
    f.authority.close_retaining_reservation('synthetic',ledger=f.ledger)
    with pytest.raises(ValueError):f.shim.debit(f.request())
    assert f.row()['active']==2 and f.row()['calls']==1


def test_invalid_parent_never_falls_back_even_when_resealed(fixture):
    f=fixture;grant=f.root/original.COMPLETE_APPROVAL
    value=json.loads(grant.read_text());value['status']='REVOKED';grant.write_text(json.dumps(value))
    f.config['approval_sha256']=budget.digest(grant);f.save()
    with pytest.raises(ValueError,match='complete03'):f.shim.debit(f.request())
    assert f.row()['calls']==0


def test_wire_rejects_duplicate_oversize_and_reports_nonzero(fixture):
    for raw in (b'{"schema":1,"schema":2}',b'x'*32769):
        output,process=budget._exchange(budget._command(fixture.config),raw,2)
        assert process['exit_code']==1 and json.loads(output)['status']=='REFUSED'
        assert process['reaped'] and process['readers_joined']
    assert fixture.row()['calls']==0
