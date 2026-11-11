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
    p=directory/'one.json';p.write_text(json.dumps({'pid':os.getpid(),'birth':budget.process_birth(os.getpid())}))
    assert harness.owners(tmp_path)[0]['same_birth_alive'] is True
    p.write_text(json.dumps({'pid':os.getpid(),'birth':{'linux_start_ticks':0}}))
    assert harness.owners(tmp_path)[0]['same_birth_alive'] is False
    p.write_text(json.dumps({'pid':2147483647,'birth':{'linux_start_ticks':0}}))
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
