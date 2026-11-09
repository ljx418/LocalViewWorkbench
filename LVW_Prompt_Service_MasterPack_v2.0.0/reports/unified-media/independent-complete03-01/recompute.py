"""Independent CPU-only audit. All mutable authority fixtures live in TemporaryDirectory."""
from pathlib import Path
from unittest.mock import patch
import concurrent.futures,hashlib,json,sys,tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from tools import local_program_authority as a
ROOT=a.ROOT
results={}
def record(name, fn):
    try:fn();results[name]='PASS'
    except BaseException as e:results[name]={'FAIL':repr(e)}
def fixture():
    t=tempfile.TemporaryDirectory();r=Path(t.name);(r/'reports').mkdir();(r/'plans').mkdir()
    for rel in [a.REQUEST,a.APPROVAL,a.COMPLETE_REQUEST,a.COMPLETE_APPROVAL]:(r/rel).write_bytes((ROOT/rel).read_bytes())
    (r/'plans/execution-control.json').write_text(json.dumps({'authorization_record':a.COMPLETE_APPROVAL}))
    return t,r,r/'private.sqlite'
def reserve(r,l,n,cap=0,seconds=1,full=False,stage='R1',cpu=False):
    a.reserve(n,stage,{'model_calls':cap,'provider_calls':cap,'full_checkpoints':int(full)},seconds,full,ledger=l,root=r,cpu_fixture=cpu)
def denied(fn):
    try:fn()
    except (ValueError,FileNotFoundError):return
    raise AssertionError('unexpectedly allowed')
def history(r,l):
    reserve(r,l,'historical',9,178,True)
    with a.transaction(l) as db:db.execute('UPDATE children SET active=0,calls=9,checkpoint=3,elapsed=178')
def case_global():
    for kind in ['model','full','seconds']:
        t,r,l=fixture()
        with t:
            history(r,l)
            if kind=='model':
                for i in range(7):reserve(r,l,f'r{i}',128)
                reserve(r,l,'exact',119);denied(lambda:reserve(r,l,'over',1))
            elif kind=='full':
                for i in range(21):reserve(r,l,f'r{i}',0,1,True)
                denied(lambda:reserve(r,l,'over',0,1,True))
            else:
                for i in range(7):reserve(r,l,f'r{i}',0,21600)
                reserve(r,l,'exact',0,21422)
                denied(lambda:reserve(r,l,'over'))
                reserve(r,l,'cpu-excluded',0,21600,cpu=True)
            with a.transaction(l) as db:
                row=db.execute('SELECT * FROM children WHERE run="historical"').fetchone()
                assert (row['calls'],row['checkpoint'],row['elapsed'])==(9,3,178)
def case_concurrency():
    t,r,l=fixture()
    with t:
        for i in range(7):reserve(r,l,f'r{i}',128)
        reserve(r,l,'pre',127)
        def attempt(i):
            try:reserve(r,l,f'contender{i}',1);return True
            except ValueError:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:assert sum(pool.map(attempt,range(8)))==1
        with a.transaction(l) as db:assert a.totals(list(db.execute('SELECT * FROM children')))['model']==1024

def case_send():
    for kind in ['absent','revoked','grant-hash','request-hash','source','sample','tool','bindings-absent','child']:
        t,r,l=fixture()
        with t:
            reserve(r,l,'live-08',2,100,True)
            for name in ['source','sample','tool']:(r/name).write_text(name)
            bindings=r/'bindings.json';bindings.write_text(json.dumps({'tool':{'path':str(r/'tool'),'sha256':a.digest(r/'tool')}}))
            child=r/'child.json';child.write_text(json.dumps({'run_id':'live-08','stage_id':'R1','budget_ledger':str(l),'program':a.COMPLETE_APPROVAL,'program_sha256':a.digest(r/a.COMPLETE_APPROVAL),'frozen_files':[{'path':'source','sha256':a.digest(r/'source')}],'samples':[{'path':'sample','sha256':a.digest(r/'sample')}],'execution_bindings_required':True}))
            a.bind('live-08',child,ledger=l)
            if kind!='bindings-absent':a.bind_execution('live-08',bindings,ledger=l)
            if kind=='absent':(r/a.COMPLETE_APPROVAL).unlink()
            elif kind=='revoked':
                grant=json.loads((r/a.COMPLETE_APPROVAL).read_text());grant['status']='REVOKED';(r/a.COMPLETE_APPROVAL).write_text(json.dumps(grant))
            elif kind=='grant-hash':(r/a.COMPLETE_APPROVAL).write_bytes((r/a.COMPLETE_APPROVAL).read_bytes()+b' ')
            elif kind=='request-hash':(r/a.COMPLETE_REQUEST).write_bytes((r/a.COMPLETE_REQUEST).read_bytes()+b' ')
            elif kind in ['source','sample','tool']:(r/kind).write_text('drift')
            elif kind=='child':child.write_bytes(child.read_bytes()+b' ')
            with patch.object(a,'ROOT',r):denied(lambda:a.model_action(child))
            with a.transaction(l) as db:assert db.execute('SELECT calls FROM children').fetchone()[0]==0

def case_child_limits_scope():
    t,r,l=fixture()
    with t:
        reserve(r,l,'ceiling',128,21600)
        denied(lambda:reserve(r,l,'action-over',129))
        denied(lambda:reserve(r,l,'time-over',0,21601))
        denied(lambda:reserve(r,l,'v2',stage='V2'))
        for i in range(30):
            reserve(r,l,f'cpu{i}',cpu=True);a.settle(f'cpu{i}',0,ledger=l)
        for i in range(30):
            a.reserve(f'zero{i}','R1',{'api_starts':1,'headless_browser_starts':1},100,False,ledger=l,root=r)
            a.settle(f'zero{i}',0,ledger=l)

def case_static():
    assert a.LEDGER.name=='program02.sqlite'
    source=(ROOT/'reports/unified-media/authority.py').read_text()
    assert "run_id=='live-08' and not active_program.get('global_only')" in source
    assert "assert full and port==18780 and 0<seconds<=1800" in source
    assert "assert budget==expected" in source and "'provider_calls':8" in source
    assert "'stage_pass_claim':False" in source

for name,fn in [('historical_consumption_and_global_exact_one_over',case_global),('concurrent_reservations_atomic_global_limit',case_concurrency),('nine_send_default_deny_mutations_no_debit',case_send),('per_child_ceiling_scope_and_removed_count_caps',case_child_limits_scope),('same_ledger_and_slice_static_invariants',case_static)]:record(name,fn)
print(json.dumps({'checks':results,'side_effects':{'real_ledger_writes':0,'service_starts':0,'gpu_probes':0,'browsers':0,'model_calls':0,'media_probe_decode':0,'downloads':0}},indent=2))
assert all(v=='PASS' for v in results.values())
