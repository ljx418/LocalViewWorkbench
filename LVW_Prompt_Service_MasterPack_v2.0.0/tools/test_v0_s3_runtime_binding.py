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
