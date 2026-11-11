"""Narrow evidence-gap probes; assertions record behavior, not acceptance."""
import json
from pathlib import Path
import pytest
from LVW_V0_RuntimePatch.tests.test_s3_installed_runtime import fixture, assert_failure
from tools import v0_incremental_package as package
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory

def emit(name, value):
    print('INDEPENDENT_OBSERVATION ' + json.dumps({'probe': name, **value}, sort_keys=True))

def test_archive_ancestor_link_before_first_check(fixture):
    f = fixture
    link = f.root / 'alias'
    link.symlink_to(f.root, target_is_directory=True)
    f.kwargs['package_path'] = link / 'payload.zip'
    result = assert_failure(f, InstalledPackageRuntimeFactory(**f.kwargs))
    assert result['error'] == 'binding redirect forbidden'
    emit('initial_archive_ancestor', {'refused': True, 'failure': result})

def test_archive_link_between_validation_and_install(fixture, monkeypatch):
    f = fixture
    install = package.command_install
    def swap(args):
        original = f.root / 'original-archive.zip'
        f.archive_path.rename(original)
        f.archive_path.symlink_to(original)
        return install(args)
    monkeypatch.setattr(package, 'command_install', swap)
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    context = factory.prepare_default()
    assert f.archive_path.is_symlink()
    assert factory.evidence['default']['deployment']['status'] == 'VERIFIED'
    emit('late_archive_link', {'accepted': True, 'fake_comfy_starts': f.helper.events.count('comfy-start'),
                              'deployment': factory.evidence['default']['deployment']})
    assert f.archive(context, context.driver.cleanup())['proven']

def test_child_redirect_during_install_validation(fixture, monkeypatch):
    f = fixture
    validate = package._validate_archive
    calls = 0
    foreign = f.root / 'foreign-unregistered'; foreign.mkdir()
    def redirect(*args, **kwargs):
        nonlocal calls
        result = validate(*args, **kwargs)
        calls += 1
        if calls == 2:
            target = f.archive.lease('default')
            (target / 'custom_nodes').rmdir()
            (target / 'custom_nodes').symlink_to(foreign, target_is_directory=True)
        return result
    monkeypatch.setattr(package, '_validate_archive', redirect)
    result = assert_failure(f, InstalledPackageRuntimeFactory(**f.kwargs))
    written = foreign / 'lvw_v0_bridge/core.py'
    assert written.read_bytes() == f.payload[package.BRIDGE_SOURCE_DIR + '/core.py']
    emit('late_child_redirect', {'foreign_payload_written': True,
                                'foreign_files': sorted(str(p.relative_to(foreign)) for p in foreign.rglob('*') if p.is_file()),
                                'failure': result})

def test_receipt_session_identity(fixture, monkeypatch):
    f = fixture
    install = package.command_install
    def alter(args):
        receipt = install(args)
        receipt['session_id'] = 'foreign-session'
        return receipt
    monkeypatch.setattr(package, 'command_install', alter)
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    context = factory.prepare_default()
    owner, digest = package._read_ownership_record(context.root)
    assert owner['session_id'] != 'foreign-session'
    assert factory.evidence['default']['deployment']['install_receipt']['session_id'] == 'foreign-session'
    emit('receipt_session', {'accepted': True, 'owner_session': owner['session_id'],
                             'receipt_session': 'foreign-session', 'fake_comfy_starts': f.helper.events.count('comfy-start')})
    assert f.archive(context, context.driver.cleanup())['proven']
