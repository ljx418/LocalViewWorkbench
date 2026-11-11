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
    def observe(root,*args):
        alive=next(values)
        return [{'request_id':rid,'pid':1,'birth':{'linux_start_ticks':10},'binding_sha256':'b','state':'ENTERED','same_birth_alive':alive}]
    monkeypatch.setattr(harness,'owners',observe)
    o=harness.Observer(tmp_path,'b');o.stop.set();o.observe()
    assert o.absent[rid]==2 and len(o.times)==4 and rid in o.entered
    monkeypatch.setattr(harness,'owners',lambda root,*args:[{'request_id':rid,'binding_sha256':'WRONG'}])
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
    finally:
        observation=observer.finish()
        save_observer_raw('owned-helper',observation)
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


@pytest.mark.parametrize('child_id,status',[(harness.CHILD_ID,'DRAFT_NOT_AUTHORIZED'),('S3-P2B-01','AUTHORIZED'),('S3-P2B-CORRECTION-01','AUTHORIZED'),('S3-P2B-CORRECTION-02','AUTHORIZED')])
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


def save_observer_raw(name, observation):
    import os
    directory=os.environ.get('P2B_RAW_DIR')
    if directory:
        path=Path(directory)/(name+'.jsonl')
        with path.open('a') as out:out.write(json.dumps(observation,ensure_ascii=False)+'\n')
    print(json.dumps({'raw_observer':name,'result':observation}),flush=True)


@pytest.mark.parametrize('extra',[-1,0,1])
def test_correction03_reservation_before_digest(tmp_path,monkeypatch,extra):
    paths={r:tmp_path/r for r in harness.FIXED}
    for i,p in enumerate(paths.values(),1):p.write_bytes(b'x'*i)
    monkeypatch.setattr(harness,'FIXED',{r:str(p) for r,p in paths.items()})
    charge=sum(p.stat().st_size*harness.METADATA_READ_BOUNDS[r] for r,p in paths.items())
    monkeypatch.setitem(harness.LIMITS,'metadata_hash_bytes',charge-extra)
    calls=[]
    monkeypatch.setattr(harness,'digest',lambda p:calls.append(p))
    meter=harness.Meter()
    if extra>=0:
        with pytest.raises(ValueError):harness.reserve_metadata(meter)
        assert calls==[] and meter.used['metadata_hash_bytes']==0
    else:
        result=harness.reserve_metadata(meter)
        assert result['charged_bytes']==charge and result['actual_digest_bytes'] is None
        assert result['remaining_budget']==1 and meter.used['metadata_hash_files']==3
        with pytest.raises(ValueError):harness.reserve_metadata(meter)
        assert meter.used['metadata_hash_bytes']==charge


@pytest.mark.parametrize('failure',[PermissionError('read failed'),OSError('partial read')])
def test_correction03_failed_digest_keeps_reservation(tmp_path,monkeypatch,failure):
    paths={r:tmp_path/r for r in harness.FIXED}
    for p in paths.values():p.write_bytes(b'synthetic')
    monkeypatch.setattr(harness,'FIXED',{r:str(p) for r,p in paths.items()})
    meter=harness.Meter();result=harness.reserve_metadata(meter)
    def failed(path):raise failure
    monkeypatch.setattr(harness,'digest',failed)
    with pytest.raises(OSError):harness.digest(paths['wsl'])
    assert meter.used['metadata_hash_bytes']==result['charged_bytes']
    assert result['actual_digest_bytes'] is None


@pytest.mark.parametrize('scenario',['enoent','esrch','reuse','returned','permission','bad-json','binding','identity','deadline','no-identity','thread-error','stop'])
def test_correction03_observer_matrix(tmp_path,monkeypatch,scenario):
    import errno
    from types import SimpleNamespace
    (tmp_path/'.s3-synthetic-fixture').touch()
    d=tmp_path/'.s3-owned-requests';d.mkdir()
    rid='00000000-0000-0000-0000-000000000001'
    path=d/(rid+'.json')
    value=dict(request_id=rid,pid=123,birth={'linux_start_ticks':10},binding_sha256='b',state='ENTERED')
    if scenario=='returned':value['state']='FAULT_HELPER_RETURNED'
    if scenario=='binding':value['binding_sha256']='wrong'
    if scenario!='no-identity':path.write_text('{' if scenario=='bad-json' else json.dumps(value))
    count=[0]
    def birth(pid):
        count[0]+=1
        if scenario=='permission':raise PermissionError(errno.EACCES,'synthetic denied')
        if scenario=='thread-error':raise RuntimeError('synthetic thread failure')
        if scenario=='identity' and count[0]==1:
            value['birth']['linux_start_ticks']=11;path.write_text(json.dumps(value))
        if scenario=='reuse':return {'linux_start_ticks':11}
        if scenario in ('returned','stop') or count[0]>1:
            raise OSError(errno.ESRCH if scenario=='esrch' else errno.ENOENT,'synthetic disappearance')
        return {'linux_start_ticks':10}
    monkeypatch.setattr(harness,'protocol',lambda root:SimpleNamespace(process_birth=birth))
    clock=[100.0]
    monkeypatch.setattr(harness.time,'monotonic',lambda:clock[0])
    monkeypatch.setattr(harness.time,'sleep',lambda seconds:clock.__setitem__(0,clock[0]+(31 if scenario=='deadline' else seconds)))
    o=harness.Observer(tmp_path,'b');o.stop.set();o.thread.start()
    try:result=o.finish()
    finally:
        if 'result' not in locals():result={'samples':o.samples,'error':o.error,'times':o.times}
        save_observer_raw('matrix-'+scenario,result)
    if scenario in ('enoent','esrch','reuse','returned','stop'):
        assert result['two_absences'] and result['joined'] and result['error'] is None
        assert result['absence_counts'][rid]==2 and result['sample_count']>=2
    else:
        assert not result['two_absences'] and result['joined']
        assert result['deadline_reason'] in ('ERROR','DEADLINE','SAMPLE_LIMIT')
    if scenario=='binding':assert count[0]==0
    if scenario=='identity':assert count[0]==1


def test_correction03_fixed_call_graph_spy(tmp_path,monkeypatch):
    """Execute factory/admission/native command/shim/authority with synthetic exe bytes."""
    import hashlib
    import sys
    import uuid
    from types import SimpleNamespace
    from collections import Counter
    synthetic={r:tmp_path/r for r in harness.FIXED}
    for i,p in enumerate(synthetic.values(),1):p.write_bytes(bytes([i])*i)
    seals={r:hashlib.sha256(p.read_bytes()).hexdigest() for r,p in synthetic.items()}
    aliases={v:k for k,v in harness.FIXED.items()}
    aliases[r'C:\Windows\System32\wsl.exe']='wsl'
    counts=Counter();phase=['installed'];raw=[]
    def wrap(original):
        def spy(path):
            role=aliases.get(str(path))
            if role:
                counts[(phase[0],role)]+=1
                raw.append(dict(phase=phase[0],role=role,synthetic_bytes=synthetic[role].stat().st_size))
                return original(synthetic[role])
            return original(path)
        return spy
    original_module=harness.module
    def load(name,path):
        m=original_module(name,path)
        if hasattr(m,'digest'):m.digest=wrap(m.digest)
        return m
    monkeypatch.setattr(harness,'module',load)
    monkeypatch.setattr(harness,'digest',wrap(harness.digest))
    for path in harness.FIXED.values():harness.digest(path)
    with tempfile.TemporaryDirectory(prefix='lvw-s3-p2b-spy-normal-',dir='/tmp') as parent, tempfile.TemporaryDirectory(prefix='lvw-s3-p2b-spy-helper-',dir='/tmp') as helper:
        roots=[Path(parent),Path(helper)]
        for root in roots:root.rmdir()
        pre=dict(candidate='a'*40,source_hashes={s:harness.digest(harness.ROOT/s) for s in harness.SOURCES},wsl_sha256=seals['wsl'])
        phase[0]='factory-normal';cfg,plan=harness.make_fixture(roots[0],pre)
        phase[0]='factory-helper';bad,badplan=harness.make_fixture(roots[1],pre,'bad-receipt')
        phase[0]='admission';harness.admit_case_plan(*roots,pre)
        # Use isolated module OS view only; never change process os.name or launch WSL.
        b=harness.protocol(roots[0]);b.os=SimpleNamespace(name='nt')
        for label,c in [('client-normal',cfg),('client-helper',bad),('client-timeout',cfg)]:
            phase[0]=label;assert b._command(c)[0]==r'C:\Windows\System32\wsl.exe'
        phase[0]='client-bad-binding'
        with pytest.raises(ValueError):b.load_binding(dict(path=cfg['binding_path'],sha256='0'*64))
        shim=load('_spy_shim',roots[0]/'tools/v0_s3_budget_authority.py')
        shim.module_at=load;shim.sys=SimpleNamespace(executable='/usr/bin/python3')
        for label in ('shim-normal-and-authority','shim-timeout-and-authority'):
            phase[0]=label
            request=dict(schema='lvw.s3-debit/1',request_id=str(uuid.uuid4()),action_kind='chat',payload_sha256='c'*64,
                         model=cfg['model'],binding_path=cfg['binding_path'],binding_sha256=plan['binding']['sha256'])
            assert shim.debit(request)['status']=='DEBITED'
        # Every prefix ending in a failed/partial digest is bounded by these full paths;
        # no source function has a digest retry loop. Exercise first failing shim read.
        before=sum(counts.values());phase[0]='failed-shim'
        def failing_load(name,path):
            m=load(name,path)
            if hasattr(m,'digest'):
                original=m.digest
                def fail(p):
                    if str(p) in aliases:
                        original(p);raise OSError('synthetic partial digest failure')
                    return original(p)
                m.digest=fail
            return m
        shim.module_at=failing_load
        with pytest.raises(OSError):shim.debit(dict(request,request_id=str(uuid.uuid4())))
        assert sum(counts.values())==before+1
    table={row[0]:dict(zip(('windows_python','wsl','python'),row[1:])) for row in harness.METADATA_CALL_TABLE}
    for (label,role),n in counts.items():
        if label=='admission':assert n==table['admission-normal'][role]+table['admission-helper'][role]
        elif label!='failed-shim':assert n==table[label][role]
    totals={r:sum(n for (label,role),n in counts.items() if role==r and label!='failed-shim') for r in harness.FIXED}
    save_observer_raw('metadata-spy',dict(attempts=raw,totals=totals,table=harness.METADATA_CALL_TABLE,measured_synthetic_only=True))
    assert totals=={'windows_python':1,'wsl':10,'python':11}
    assert all(totals[r]<=harness.METADATA_READ_BOUNDS[r] for r in totals)
    assert not Path(parent).exists()

@pytest.mark.parametrize('fault',[None,'phase2','phase3','observer','cleanup','detail','serialization','native','output'])
def test_correction04_public_run_maximum(tmp_path,monkeypatch,fault):
    """Public owner, real factory/roles/SQLite/claim; synthetic host process boundary."""
    import io
    import os
    import threading
    from types import SimpleNamespace
    base=tmp_path/'evidence';base.mkdir()
    monkeypatch.setattr(harness,'BASE',base)
    monkeypatch.setattr(harness,'ACTIVE_METER',None)
    original_digest=harness.digest
    host=set(harness.FIXED.values())-{'/usr/bin/python3'}
    seals={r:('c'*64 if p in host else original_digest(p)) for r,p in harness.FIXED.items()}
    monkeypatch.setattr(harness,'digest',lambda p:'c'*64 if str(p) in host else original_digest(p))
    original_module=harness.module
    def load(name,path):
        m=original_module(name,path)
        if Path(path).name=='local_program_authority.py':
            original=m.digest
            m.digest=lambda p:'c'*64 if str(p) in host else original(p)
        return m
    monkeypatch.setattr(harness,'module',load)
    stat=Path.stat
    monkeypatch.setattr(Path,'stat',lambda p,*a,**k:SimpleNamespace(st_size=1) if str(p) in host else stat(p,*a,**k))
    read=Path.read_text
    monkeypatch.setattr(Path,'read_text',lambda p,*a,**k:json.dumps({'tools':{r:{'sha256':v} for r,v in seals.items()}}) if p==harness.ROOT/harness.OLD_SEAL else read(p,*a,**k))
    opened=Path.open
    def guarded(p,*a,**k):
        assert not str(p).startswith('/mnt/c/'),str(p)
        return opened(p,*a,**k)
    monkeypatch.setattr(Path,'open',guarded)
    monkeypatch.setattr(harness.subprocess,'check_output',lambda c,**k:'a'*40 if c[1]=='rev-parse' else b'')
    child=json.loads((harness.ROOT/harness.CHILD).read_text());child['status']='AUTHORIZED'
    monkeypatch.setattr(harness,'authorized_child',lambda:child)
    monkeypatch.setattr(harness,'claim_path',lambda child:tmp_path/'shared.claim')
    pre=harness.preflight('a'*40)
    created=[];factory=harness.make_fixture
    def make(root,pre,case='normal'):
        created.append(root)
        return factory(root,pre,case)
    monkeypatch.setattr(harness,'make_fixture',make)
    counts={};phase=[0]
    def owners(root,binding_hash=None,identities=None,exclude=()):
        if fault=='cleanup' and binding_hash is None and phase[0]==3:raise OSError('synthetic cleanup unknown')
        if binding_hash is None:return []
        key=(str(root),id(identities))
        counts[key]=counts.get(key,0)+1
        n=counts[key]
        if fault=='observer' and phase[0]==2 and n>3:raise OSError('synthetic observer error')
        return [dict(request_id=f'00000000-0000-0000-0000-{i+1:012d}',pid=123456+i,
            birth={'linux_start_ticks':10+i},binding_sha256=binding_hash,state='ENTERED',
            same_birth_alive=n<159,owned_path=str(root/('中文 空格'*24))) for i in range(4)]
    monkeypatch.setattr(harness,'owners',owners)
    sleep=harness.time.sleep
    monkeypatch.setattr(harness.time,'sleep',lambda n:sleep(.0001 if threading.current_thread() is not threading.main_thread() else n))
    protocol=harness.protocol
    def proto(root):
        m=protocol(root);birth=m.process_birth
        m.process_birth=lambda pid,*a:{'linux_start_ticks':99} if pid==987654 else birth(pid,*a)
        return m
    monkeypatch.setattr(harness,'protocol',proto)
    class Process:
        pid=987654
        def __init__(self):
            self.stdout=io.BytesIO(bytes(range(256))*1024)
            self.stderr=io.BytesIO(b'error metadata\xff\x00'*16000)
        def poll(self):return 0
        def wait(self,timeout):return 0
    def popen(command,**kw):
        assert command[0]==harness.FIXED['windows_python'] and command[-1]=='--windows'
        phase[0]+=1;root=created[0];label=('normal','bad-receipt','timeout')[phase[0]-1]
        if fault=='phase2' and phase[0]==2:raise OSError('synthetic phase2 boundary')
        if fault=='phase3' and phase[0]==3:raise OSError('synthetic phase3 boundary')
        native=dict(pid=123,birth={'windows_creation_time_100ns':456},os_name='nt',synthetic=True)
        if fault!='native' or phase[0]!=2:harness.write(root/('native-'+label+'.json'),native)
        result={'status':'DEBITED'} if phase[0]==1 else {'details':{'exit_code':0,'subcode':'S3_BRIDGE_RECEIPT_INVALID'}} if phase[0]==2 else {'details':{'error':'TIMEOUT'}}
        harness.write(root/'windows-result.json',dict(os_name='nt',native_identity=native,cases=[{'result':result}]))
        if phase[0]==1:
            import sqlite3
            with sqlite3.connect(root/'fixture.sqlite') as db:db.execute('UPDATE children SET calls=1')
        process=Process()
        if fault=='output' and phase[0]==2:process.stdout=io.BytesIO(b'x'*262145)
        return process
    monkeypatch.setattr(harness.subprocess,'Popen',popen)
    save=harness.EvidenceStore.save
    def save_fault(store,kind,value=None,raw=None):
        if phase[0]==2 and kind=='phase' and fault=='detail':raise OSError('synthetic detail failure')
        if phase[0]==2 and kind=='phase' and fault=='serialization':value={'bad':object()}
        return save(store,kind,value,raw)
    monkeypatch.setattr(harness.EvidenceStore,'save',save_fault)
    try:
        life=harness.run()
        terminal=json.loads((base/'cross-os-lifecycle.json').read_text())
        assert life['terminal_persisted'] and (base/'cross-os-lifecycle.json').stat().st_size<=16384
        assert terminal['status']==('READY_FOR_REVIEW' if fault is None else 'BLOCKED')
        claim=json.loads((tmp_path/'shared.claim').read_text())
        assert claim['status']=='EXPIRED' and claim['terminal_sha256']==original_digest(base/'cross-os-lifecycle.json')
        refs=terminal['artifact_refs'];total=0;observations=[]
        for ref in refs:
            path=base/ref['path'];assert path.stat().st_size==ref['bytes']<=1048576
            assert original_digest(path)==ref['sha256'];total+=ref['bytes']
            if ref['kind']=='observer':observations.append(json.loads(path.read_bytes()))
        assert total==terminal['detail_actual_bytes']<=terminal['detail_reserved_bytes']
        assert total<terminal['counters']['output_bytes']<=16777216
        if fault is None:
            assert len(observations)==6 and all(o['sample_count']==160 for o in observations)
            assert set(terminal['phase_verdicts'])=={'normal','bad-receipt','timeout'}
        assert any(ref['kind']=='phase' and json.loads((base/ref['path']).read_bytes())['phase']=='normal' for ref in refs)
        assert any(o['sample_count']==160 and all(len(s['owners'])==4 for s in o['samples']) for o in observations)
        assert len(json.dumps(life,ensure_ascii=False).encode())>32768
        if fault in ('phase2','phase3','detail','serialization','output','native'):assert terminal['synthetic_debits'] is None
        directory=os.environ.get('P2B_RAW_DIR')
        if directory:
            import shutil
            shutil.copytree(base,Path(directory)/('public-'+str(fault)))
            for i,root in enumerate(created):shutil.copytree(root,Path(directory)/('factory-'+str(fault)+'-'+str(i)))
            (Path(directory)/('life-'+str(fault)+'.json')).write_text(json.dumps(life,ensure_ascii=False))
    finally:
        monkeypatch.setattr(harness,'ACTIVE_METER',None)
        import shutil
        for root in created:shutil.rmtree(root)
        assert all(not root.exists() for root in created)
        save_observer_raw('public-cleanup-'+str(fault),dict(roots=[str(r) for r in created],absent=True,synthetic=True))


@pytest.mark.parametrize('fault',['tamper','missing','symlink','bound','output'])
def test_correction04_store_integrity_and_sticky_bounds(tmp_path,fault):
    meter=harness.Meter();store=harness.EvidenceStore(tmp_path,meter)
    ref=store.save('phase',{'phase':'normal'})
    path=tmp_path/ref['path']
    if fault=='tamper':path.write_bytes(b'changed')
    elif fault=='missing':path.unlink()
    elif fault=='symlink':
        path.unlink();path.symlink_to(tmp_path/'outside')
    elif fault=='bound':
        store.save('response',raw=b'x'*1048576)
        with pytest.raises(ValueError):store.save('response',raw=b'x'*1048577)
        store.verify();return
    else:
        meter.take('output_bytes',harness.LIMITS['output_bytes']-meter.used['output_bytes'])
        with pytest.raises(ValueError):meter.take('output_bytes',1)
        store.save('phase',{'failure_prefix':'preserved inside prepaid envelope'})
        with pytest.raises(ValueError):meter.take('output_bytes',0)
        assert path.exists();return
    with pytest.raises((ValueError,OSError)):store.verify()
