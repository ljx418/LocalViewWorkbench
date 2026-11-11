"""Independent correction assertions; failure assertions are not observation PASS."""
import errno
import json
import os
from pathlib import Path
import pytest
from LVW_V0_RuntimePatch.tests.test_s3_installed_runtime import fixture
from tools import v0_incremental_package as package
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory

def emit(name, **values):
    print('INDEPENDENT_ASSERTION ' + json.dumps({'probe': name, **values}, sort_keys=True))

def run_failure(f):
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    with pytest.raises((package.PackageError, OSError, ValueError)) as caught:
        factory.prepare_default()
    assert not {'comfy-start', 'ollama-start'} & set(f.helper.events)
    assert f.sentinel.read_bytes() == b'UNRELATED ORIGINAL'
    result = json.loads((f.directory / 'default-preparation-failure.json').read_text())
    assert result['error'] == str(caught.value)
    assert result['evidence']['deployment']['status'] == 'FAILED'
    assert result['evidence']['deployment']['retention_required'] is True
    assert 'pathname archive deletion forbidden' in result['cleanup_error']
    return factory, result

def track_closure(monkeypatch):
    captured = []
    close = package.ProtectedInstall.__exit__
    def inspect(handoff, *args):
        captured.extend(handoff.fds)
        return close(handoff, *args)
    monkeypatch.setattr(package.ProtectedInstall, '__exit__', inspect)
    return captured

def assert_closed(fds):
    assert fds
    for fd in fds:
        with pytest.raises(OSError) as error:
            os.fstat(fd)
        assert error.value.errno == errno.EBADF

def test_M01_late_child_redirect_refused_with_zero_foreign_writes(fixture, monkeypatch):
    f = fixture
    destination = f.root / 'review-foreign'; destination.mkdir()
    (destination / 'keep').write_bytes(b'foreign unchanged')
    original = package._validate_archive
    calls = []
    def redirect(value, *args, **kwargs):
        result = original(value, *args, **kwargs)
        calls.append(type(value).__name__)
        if len(calls) == 2:
            root = f.archive.lease('default')
            (root / 'custom_nodes').rmdir()
            (root / 'custom_nodes').symlink_to(destination, target_is_directory=True)
        return result
    monkeypatch.setattr(package, '_validate_archive', redirect)
    fds = track_closure(monkeypatch)
    factory, record = run_failure(f)
    assert sorted(p.name for p in destination.iterdir()) == ['keep']
    assert (destination / 'keep').read_bytes() == b'foreign unchanged'
    assert calls == ['_SealedArchive', '_SealedArchive']
    assert record['root_retained'] is True
    assert_closed(fds)
    emit('P3A-M01', foreign_writes=0, service_starts=0, validation_inputs=calls, closed_fds=len(fds), failure=record)

@pytest.mark.parametrize('change', ['symlink', 'same_bytes_new_inode'])
def test_M02_late_archive_identity_refused(fixture, monkeypatch, change):
    f = fixture
    install = package.command_install
    original_bytes = f.archive_path.read_bytes()
    def replace(args):
        moved = f.root / 'review-original.zip'
        f.archive_path.rename(moved)
        if change == 'symlink':
            f.archive_path.symlink_to(moved)
        else:
            f.archive_path.write_bytes(original_bytes)
        return install(args)
    monkeypatch.setattr(package, 'command_install', replace)
    factory, record = run_failure(f)
    root = Path(record['evidence']['owned_run_root'])
    assert not (root / package.BRIDGE_INSTALL_DIR).exists()
    assert not (root / package.WORKFLOWS_INSTALL_DIR).exists()
    assert 'archive identity drift' in str(record)
    emit('P3A-M02-' + change, service_starts=0, installed_payloads=0, failure=record)

def test_m01_receipt_session_refused_and_original_record_retained(fixture, monkeypatch):
    f = fixture
    install = package.command_install
    def mismatch(args):
        receipt = install(args)
        receipt['session_id'] = 'independent-foreign-session'
        return receipt
    monkeypatch.setattr(package, 'command_install', mismatch)
    # EvidenceError inherits ValueError and is included in run_failure's catch.
    factory, record = run_failure(f)
    owner, digest = package._read_ownership_record(Path(record['evidence']['owned_run_root']))
    persisted = json.loads((f.directory / 'default-package-install.json').read_text())
    assert persisted['session_id'] == 'independent-foreign-session' != owner['session_id']
    assert record['error'] == 'installed deployment ownership mismatch'
    emit('P3A-m01', service_starts=0, rejected_receipt_preserved=True, failure=record)

def test_failure_receipt_must_not_write_to_replacement_parent(fixture, monkeypatch):
    f = fixture
    save = package.ProtectedInstall.save_receipt
    detached = f.root / 'review-detached-owned-parent'
    def move_before_receipt(handoff, name, receipt):
        f.directory.rename(detached)
        f.directory.mkdir()
        (f.directory / 'foreign-sentinel').write_bytes(b'REPLACEMENT IS NOT OWNED')
        return save(handoff, name, receipt)
    monkeypatch.setattr(package.ProtectedInstall, 'save_receipt', move_before_receipt)
    fds = track_closure(monkeypatch)
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    with pytest.raises(package.PackageError):
        factory.prepare_default()
    assert not {'comfy-start', 'ollama-start'} & set(f.helper.events)
    assert f.sentinel.read_bytes() == b'UNRELATED ORIGINAL'
    assert (detached / 'other-run/keep').read_bytes() == b'OTHER RUN'
    assert (f.directory / 'foreign-sentinel').read_bytes() == b'REPLACEMENT IS NOT OWNED'
    assert_closed(fds)
    unexpected = sorted(p.name for p in f.directory.iterdir() if p.name != 'foreign-sentinel')
    misplaced = f.directory / 'default-preparation-failure.json'
    failure = json.loads(misplaced.read_text()) if misplaced.exists() else None
    emit('failure_receipt_replaced_parent', replacement_writes=unexpected, service_starts=0,
         failure_at_original_parent=(detached / 'default-preparation-failure.json').exists(),
         closed_fds=len(fds), misplaced_failure=failure)
    assert unexpected == [], 'failure writer must remain anchored to original parent; replacement writes observed'
