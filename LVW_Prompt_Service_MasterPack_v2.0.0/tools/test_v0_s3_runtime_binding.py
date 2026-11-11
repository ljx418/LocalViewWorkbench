"""Synthetic boundary checks only. No os.name replacement or installed path reads."""
import copy
import json
from pathlib import Path
import tempfile
import pytest
from tools import v0_s3_runtime_binding as harness
from tools.test_v0_s3_budget_authority import fixture
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import program_budget as budget


def config(f):
    b=copy.deepcopy(f.config)
    root='/tmp/lvw-s3-p2b-中文 Space-Case'
    old=b['authority_root'];b['authority_root']=root
    for k in ('child_path','ledger_path','execution_path','binding_path'):b[k]=b[k].replace(old,root)
    b['transport']='wsl-fixture';b['harness_transport']='local-fixture';b['distribution']='Ubuntu-24.04'
    b['client_binding_path']=budget.fixture_unc(b['binding_path'])
    for role in ('authority','shim'):
        b['tools'][role]['path']=b['tools'][role]['path'].replace(old,root)
    b['tools']['python']['path']='/usr/bin/python3'
    for role in ('authority','shim','python'):
        b['tools'][role]['client_path']=budget.fixture_unc(b['tools'][role]['path'])
    b['tools']['wsl']={'path':'/mnt/c/Windows/System32/wsl.exe','client_path':r'C:\Windows\System32\wsl.exe','sha256':'a'*64}
    return b


def test_mapping_exact_case_unicode_space_and_actual_linux_refusal(fixture):
    b=config(fixture);assert budget.validate_config(b)==b
    assert '中文 Space-Case' in b['client_binding_path']
    with pytest.raises(ValueError,match='actual Windows'):budget._command(b)


@pytest.mark.parametrize('field,value',[
 ('distribution','Ubuntu'),('client_binding_path',r'\\wsl.localhost\Ubuntu-24.04\tmp\wrong'),
 ('authority_root','/mnt/c/lvw-s3-p2b-x'),('ledger_path','/tmp/outside.sqlite'),
 ('child_path','/tmp/lvw-s3-p2b-中文 Space-Case/../escape'),('harness_transport','local-wsl')])
def test_mapping_refusals(fixture,field,value):
    b=config(fixture);b[field]=value
    with pytest.raises(ValueError):budget.validate_config(b)


def test_case_substitution_rejected(fixture):
    b=config(fixture);b['client_binding_path']=b['client_binding_path'].replace('Case','case')
    with pytest.raises(ValueError):budget.validate_config(b)


@pytest.mark.parametrize('path',['tmp/a','/tmp/../a','/tmp//a','/tmp/a\\b'])
def test_unc_noncanonical_rejected(path):
    with pytest.raises(ValueError):budget.fixture_unc(path)


@pytest.mark.parametrize('key',['process_starts','metadata_hash_files','metadata_hash_bytes','output_bytes','synthetic_debits'])
def test_exact_one_over(key):
    meter=harness.Meter();meter.take(key,harness.LIMITS[key])
    with pytest.raises(ValueError):meter.take(key,1)
    assert meter.used[key]==harness.LIMITS[key]


def test_wall_limit(monkeypatch):
    meter=harness.Meter();monkeypatch.setattr(harness.time,'monotonic',lambda:meter.started+1201)
    with pytest.raises(ValueError):meter.check()


def test_product_rejects_wsl_fixture(fixture,monkeypatch):
    b=config(fixture)
    monkeypatch.setattr(budget,'load_binding',lambda *a,**k:(b,'a'*64))
    with pytest.raises(ValueError,match='forbidden in product'):budget.validate_profile({},b['issued_at'])


def test_original_production_samefile_not_bypassed(fixture):
    f=fixture;f.config['transport']='local-wsl';f.config['harness_transport']='local-wsl';f.save()
    with pytest.raises(ValueError):f.shim.debit(f.request())
    assert f.row()['calls']==0


def test_single_consumption_and_preflight_seals(tmp_path,monkeypatch):
    monkeypatch.setattr(harness,'BASE',tmp_path)
    monkeypatch.setattr(harness,'claim_path',lambda child:tmp_path/'shared.claim')
    monkeypatch.setattr(harness.subprocess,'check_output',lambda cmd,**k:'a'*40 if cmd[1]=='rev-parse' else b'')
    child=json.loads((harness.ROOT/harness.CHILD).read_text());child['status']='AUTHORIZED'
    monkeypatch.setattr(harness,'authorized_child',lambda:child)
    value=harness.preflight('a'*40)
    assert value['real_machine_accesses']==0 and value['tools']==harness.FIXED
    (tmp_path/'consumed.json').write_text('{}')
    with pytest.raises(ValueError,match='consumed'):harness.preflight('a'*40)


def test_windows_driver_requires_actual_os():
    with pytest.raises(ValueError,match='actual Windows'):harness.windows()


def test_observation_pid_birth_and_absence(tmp_path):
    directory=tmp_path/'.s3-owned-requests';directory.mkdir()
    import os
    p=directory/'00000000-0000-0000-0000-000000000001.json';p.write_text(json.dumps({'request_id':p.stem,'pid':os.getpid(),'birth':budget.process_birth(os.getpid())}))
    assert harness.owners(tmp_path)[0]['same_birth_alive'] is True
    p.write_text(json.dumps({'request_id':p.stem,'pid':os.getpid(),'birth':{'linux_start_ticks':0}}))
    assert harness.owners(tmp_path)[0]['same_birth_alive'] is False
    p.write_text(json.dumps({'request_id':p.stem,'pid':2147483647,'birth':{'linux_start_ticks':0}}))
    assert harness.owners(tmp_path)[0]['same_birth_alive'] is False


def test_resealed_production_binding_still_requires_original_identity(fixture):
    f=fixture
    f.config['transport']='local-wsl';f.config['harness_transport']='local-wsl'
    child=json.loads(f.child.read_text())
    child['s3_budget']={k:v for k,v in f.config.items() if k!='child_sha256'}
    f.child.write_text(json.dumps(child));f.config['child_sha256']=budget.digest(f.child)
    f.save()  # original identity is checked before the ledger child seal
    with pytest.raises(FileNotFoundError):f.shim.debit(f.request())
    history=f.root/'reports/unified-media/live-15/authorization.json';history.parent.mkdir(parents=True)
    history.write_text(json.dumps({'budget_ledger':str(f.ledger)}))
    with pytest.raises(ValueError,match='fixture forbidden'):f.shim.debit(f.request())
    assert f.row()['calls']==0


def test_shared_claim_cross_checkout_and_concurrent(tmp_path,monkeypatch):
    import concurrent.futures
    shared=tmp_path/'registry'/'claim.json'
    base=tmp_path/'a';base.mkdir();(base/'preflight.json').write_text('{}')
    monkeypatch.setattr(harness,'BASE',base)
    pre={'child_sha256':'b'*64,'candidate':'a'*40}
    def claim():
        try:harness.claim_once(shared,pre);return True
        except FileExistsError:return False
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(lambda _:claim(),range(8)))==1
    other=tmp_path/'b';other.mkdir();(other/'preflight.json').write_text('{}')
    monkeypatch.setattr(harness,'BASE',other)
    assert not claim()
    assert json.loads(shared.read_text())['output_root']==str(base)


def test_claim_symlink_refused(tmp_path,monkeypatch):
    (tmp_path/'link').symlink_to(tmp_path,target_is_directory=True)
    with pytest.raises(ValueError,match='symlink'):
        harness.claim_once(tmp_path/'link'/'claim',{})


@pytest.mark.parametrize('fault',['budget','owners','serialization'])
def test_terminal_survives_finally_errors(tmp_path,monkeypatch,fault):
    monkeypatch.setattr(harness,'BASE',tmp_path)
    (tmp_path/'preflight.json').write_text('{}')
    claim=tmp_path/'claim';claim.write_text('{"status":"RUNNING"}')
    meter=harness.Meter();life={'status':'READY_FOR_REVIEW','cleanup':[]}
    if fault=='budget':monkeypatch.setattr(meter,'check',lambda:(_ for _ in ()).throw(ValueError('wall budget')))
    if fault=='owners':monkeypatch.setattr(harness,'owners',lambda root:(_ for _ in ()).throw(ValueError('observer failed')))
    installed={'invalid':object()} if fault=='serialization' else {}
    harness.terminal({'candidate':'a'*40,'claim_path':str(claim)},meter,life,installed,tmp_path,{})
    assert json.loads(claim.read_text())['status']=='EXPIRED'
    terminal=json.loads((tmp_path/'cross-os-lifecycle.json').read_text())
    assert terminal['status']=='BLOCKED' and terminal['terminal_errors']


def test_output_sticky_and_json_cap(tmp_path,monkeypatch):
    m=harness.Meter()
    with pytest.raises(ValueError):m.take('output_bytes',harness.LIMITS['output_bytes']+1)
    with pytest.raises(ValueError):m.check()
    monkeypatch.setattr(harness,'ACTIVE_METER',m)
    with pytest.raises(ValueError):harness.write(tmp_path/'out',{})
    assert not (tmp_path/'out').exists()
    monkeypatch.setattr(harness,'ACTIVE_METER',None)
    with pytest.raises(ValueError):harness.write(tmp_path/'out',{'data':'x'*32768})


@pytest.mark.parametrize('fault',['pipe','join','overflow'])
def test_meter_exit_zero_does_not_hide_pipe_failure(monkeypatch,fault):
    import io
    class Pipe(io.BytesIO):
        def read(self,n):
            if fault=='pipe':raise OSError('synthetic pipe fault')
            return super().read(n)
    class Process:
        pid=123
        stdout=Pipe(b'x'*1048577 if fault=='overflow' else b'ok')
        stderr=Pipe()
        def poll(self):return 0
        def wait(self,timeout):return 0
    monkeypatch.setattr(harness.subprocess,'Popen',lambda *a,**k:Process())
    monkeypatch.setattr(harness,'protocol',lambda root:type('B',(),{'process_birth':lambda *a:{'linux_start_ticks':1}}))
    if fault=='join':
        class Thread:
            def __init__(self,*a,**k):pass
            def start(self):pass
            def join(self,timeout):pass
            def is_alive(self):return True
        monkeypatch.setattr(harness.threading,'Thread',Thread)
        clock=iter(range(100));monkeypatch.setattr(harness.time,'monotonic',lambda:next(clock))
    meter=harness.Meter();meter.seals={'synthetic':'a'}
    with pytest.raises(ValueError):meter.run(['synthetic'])
    assert meter.commands[0]['exit_code']==0 and meter.commands[0]['error']


def test_observer_waits_for_two_absences_and_identity(monkeypatch,tmp_path):
    (tmp_path/'.s3-synthetic-fixture').touch()
    rid='00000000-0000-0000-0000-000000000001'
    values=iter([True,True,False,False])
    def observe(root):
        alive=next(values)
        return [{'request_id':rid,'pid':1,'birth':{'linux_start_ticks':10},'binding_sha256':'b','state':'ENTERED','same_birth_alive':alive}]
    monkeypatch.setattr(harness,'owners',observe)
    o=harness.Observer(tmp_path,'b');o.stop.set();o.observe()
    assert o.absent[rid]==2 and len(o.times)==4 and rid in o.entered
    monkeypatch.setattr(harness,'owners',lambda root:[{'request_id':rid,'binding_sha256':'WRONG'}])
    o=harness.Observer(tmp_path,'b');o.observe();assert 'binding mismatch' in o.error


def test_native_identity_not_interop_field():
    import inspect
    source=inspect.getsource(harness.windows)
    assert "'pid':os.getpid()" in source and 'GetCurrentProcess' in source
    assert 'interop_pid' not in source


@pytest.fixture
def factory_pair(monkeypatch):
    # Same factory + real SQLite; substitute only external OS tool metadata.
    original_module=harness.module
    def module(name,path):
        value=original_module(name,path)
        if Path(path).name=='local_program_authority.py':
            digest=value.digest
            value.digest=lambda p:'c'*64 if str(p)==harness.FIXED['wsl'] else digest(p)
        return value
    monkeypatch.setattr(harness,'module',module)
    original_open=Path.open
    def guarded_open(path,*args,**kwargs):
        assert not str(path).startswith('/mnt/c/'), 'offline test accessed host path'
        return original_open(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',guarded_open)
    with tempfile.TemporaryDirectory(prefix='lvw-s3-p2b-normal-',dir='/tmp') as n, tempfile.TemporaryDirectory(prefix='lvw-s3-p2b-helper-',dir='/tmp') as h:
        normal,helper=Path(n),Path(h);normal.rmdir();helper.rmdir()
        pre={'candidate':'a'*40,'source_hashes':{s:harness.digest(harness.ROOT/s) for s in harness.SOURCES},'wsl_sha256':'c'*64}
        cfg,plan=harness.make_fixture(normal,pre)
        bad,badplan=harness.make_fixture(helper,pre,'bad-receipt')
        yield normal,helper,pre,cfg,plan,bad,badplan
    assert not normal.exists() and not helper.exists()


def test_correction02_factory_admission_and_owned_helper(factory_pair,monkeypatch):
    import hashlib
    import sys
    normal,helper,pre,cfg,plan,bad,badplan=factory_pair
    admitted=harness.admit_case_plan(normal,helper,pre)
    assert len(admitted)==5
    record=next(x for x in admitted if x['case']=='bad-receipt')
    assert record['driver_root']==str(normal) and record['observer_root']==str(helper)
    assert harness.digest(normal/'tools/v0_s3_budget_authority.py')==pre['source_hashes']['tools/v0_s3_budget_authority.py']
    ref={'path':bad['binding_path'],'sha256':badplan['binding']['sha256']}
    assert budget.load_binding(ref)[0]==bad
    real_exchange=budget._exchange;captured={}
    def exchange(command,raw,timeout):
        output,process=real_exchange(command,raw,timeout)
        captured.update(request=json.loads(raw),response=json.loads(output),process=process)
        return output,process
    # Only OS launch adaptation: the unchanged client still loads the actual factory binding.
    monkeypatch.setattr(budget,'_command',lambda b:[sys.executable,'-I','-B',b['tools']['shim']['path']])
    monkeypatch.setattr(budget,'_exchange',exchange)
    observer=harness.Observer(helper,ref['sha256']);observer.thread.start()
    try:
        with pytest.raises(Exception) as error:
            budget.authorize_model_action('chat',b'{"model":"synthetic-no-model"}',binding=ref)
    finally:observation=observer.finish()
    assert error.value.details['subcode']=='S3_BRIDGE_RECEIPT_INVALID'
    request=captured['request'];response=captured['response'];process=captured['process']
    expected=dict(request,status='DEBITED',run_id=bad['run_id'],child_sha256=bad['child_sha256'],authority_sha256=bad['tools']['authority']['sha256'])
    assert {k for k in expected if response[k]!=expected[k]}=={'request_id'}
    assert set(response)==set(expected)
    assert process['exit_code']==0 and process['error'] is None and process['reaped'] and process['readers_joined'] and process['pipe_closed']
    journal=harness.owners(helper)[0]
    assert journal['request_id']==request['request_id'] and journal['binding_sha256']==ref['sha256']
    assert journal['pid']==process['pid'] and journal['birth']==process['birth'] and not journal['same_birth_alive']
    assert journal['state']=='FAULT_HELPER_RETURNED'
    print(json.dumps({'helper_observation':observation,'helper_process':process}))
    assert observation['joined'] and observation['two_absences'] and observation['entered'] and observation['error'] is None
    life={};assert harness.observe_debits(life,helper)==0 and harness.observe_debits(life,normal)==0
    print(json.dumps({'case_admission':admitted,'owned_helper':captured,'journal':journal,'observer':observation,'debits':life},ensure_ascii=False))


@pytest.mark.parametrize('fault',['phase','source','helper-source','marker','execution','child','ledger','unc','candidate','alias'])
def test_correction02_factory_rejects_drift(factory_pair,fault):
    normal,helper,pre,cfg,plan,bad,badplan=factory_pair
    if fault=='phase':plan['phase']='timeout';harness.write(normal/'driver-plan.json',plan)
    elif fault=='source':(normal/harness.HARNESS).write_text('changed')
    elif fault=='helper-source':(helper/'tools/v0_s3_budget_authority.py').write_text('changed')
    elif fault=='marker':(helper/'.s3-synthetic-fixture').unlink()
    elif fault=='execution':Path(bad['execution_path']).write_text('{}')
    elif fault=='child':Path(bad['child_path']).write_text('{}')
    elif fault=='ledger':
        import sqlite3
        with sqlite3.connect(bad['ledger_path']) as db:db.execute("UPDATE children SET child_hash='bad'")
    else:
        if fault=='unc':bad['client_binding_path']=cfg['client_binding_path']
        elif fault=='candidate':bad['candidate_sha']='b'*40
        elif fault=='alias':bad['tools']['shim']['path']=str(helper/'tools/bad_receipt_fixture.py')
        harness.write(Path(bad['binding_path']),bad)
        badplan['binding']['sha256']=harness.digest(bad['binding_path']);harness.write(helper/'driver-plan.json',badplan)
    with pytest.raises(ValueError):harness.admit_case_plan(normal,helper,pre)


@pytest.mark.parametrize('child_id,status',[(harness.CHILD_ID,'DRAFT_NOT_AUTHORIZED'),('S3-P2B-01','AUTHORIZED'),('S3-P2B-CORRECTION-01','AUTHORIZED')])
def test_correction02_draft_retired_zero_external_access(tmp_path,monkeypatch,child_id,status):
    root=tmp_path/'candidate';root.mkdir();(root/'child.json').write_text(json.dumps({'child_id':child_id,'status':status}))
    monkeypatch.setattr(harness,'ROOT',root);monkeypatch.setattr(harness,'CHILD','child.json')
    monkeypatch.setattr(harness,'BASE',tmp_path/'absent-output')
    def forbidden(*a,**k):raise AssertionError('external access before authorization')
    monkeypatch.setattr(harness,'claim_path',forbidden);monkeypatch.setattr(harness,'claim_once',forbidden)
    monkeypatch.setattr(harness.subprocess,'check_output',forbidden);monkeypatch.setattr(harness.subprocess,'Popen',forbidden)
    monkeypatch.setattr(harness,'digest',forbidden)
    for action in (lambda:harness.preflight('a'*40),harness.run):
        with pytest.raises(ValueError,match='not authorized'):action()
    assert not harness.BASE.exists()


def test_correction02_debits_unknown_and_last_observed(factory_pair):
    import sqlite3
    normal,helper,*_=factory_pair
    life={}
    assert harness.observe_debits(life,normal)==0
    with sqlite3.connect(normal/'fixture.sqlite') as db:db.execute('UPDATE children SET calls=1')
    assert harness.observe_debits(life,normal)==1
    assert life['synthetic_debits']==1
    harness.mark_exchange(life,normal)
    assert life['synthetic_debits'] is None and life['debit_observations'][str(normal)]['last_observed']==1
    (normal/'fixture.sqlite').unlink()
    with pytest.raises(sqlite3.OperationalError):harness.observe_debits(life,normal)
    assert life['synthetic_debits'] is None and life['debit_observations'][str(normal)]['last_observed']==1
    assert harness.observe_debits(life,helper)==0 and life['synthetic_debits'] is None


def test_correction02_terminal_registers_every_root(factory_pair,tmp_path,monkeypatch):
    normal,helper,*_=factory_pair
    monkeypatch.setattr(harness,'BASE',tmp_path)
    (tmp_path/'preflight.json').write_text('{}')
    life={'status':'BLOCKED','fixtures':[str(normal),str(helper)],'cleanup':[],'synthetic_debits':None}
    harness.terminal({'candidate':'a'*40,'claim_path':str(tmp_path/'claim')},harness.Meter(),life,{},normal,{})
    assert {x['fixture'] for x in life['cleanup']}=={str(normal),str(helper)}
    assert all(x['state']=='FAILED_RETAINED' and x['reason'] for x in life['cleanup'])
    assert json.loads((tmp_path/'cross-os-lifecycle.json').read_text())['synthetic_debits'] is None
