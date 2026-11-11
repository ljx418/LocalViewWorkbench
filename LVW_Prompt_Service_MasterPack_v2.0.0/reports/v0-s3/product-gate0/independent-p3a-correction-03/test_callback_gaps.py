"""Independent error-oracle coverage for newly changed registration/adapter seams."""
import json
import os
import pytest
from LVW_V0_RuntimePatch.tests.test_s3_installed_runtime import fixture
from tools import v0_s2_stage_runtime as legacy
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory

def track_descriptors(monkeypatch):
    opened = []
    original = os.open
    def track(*args, **kwargs):
        fd = original(*args, **kwargs); opened.append(fd); return fd
    monkeypatch.setattr(os, 'open', track)
    return opened

def closed(factory, opened):
    assert factory._parent_fd is None and factory._root_fds == {}
    for fd in set(opened):
        with pytest.raises(OSError): os.fstat(fd)

@pytest.mark.parametrize('fault', ['write-zero', 'fsync'])
def test_failed_registration_preserves_original_and_does_not_register(fixture, monkeypatch, fault):
    f = fixture
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    opened = track_descriptors(monkeypatch)
    receipt = f.directory / 'default-root-lease.json'
    write, sync = os.write, os.fsync
    def is_registration(fd):
        return receipt.exists() and os.fstat(fd).st_ino == receipt.stat().st_ino
    def fail_write(fd, raw):
        if is_registration(fd): return 0
        return write(fd, raw)
    def fail_sync(fd):
        if is_registration(fd): raise OSError('independent registration fsync failure')
        return sync(fd)
    monkeypatch.setattr(os, 'write' if fault == 'write-zero' else 'fsync', fail_write if fault == 'write-zero' else fail_sync)
    with pytest.raises(OSError) as error:
        factory.prepare_default()
    expected = 'registration write made no progress' if fault == 'write-zero' else 'independent registration fsync failure'
    assert str(error.value) == expected
    record = json.loads((f.directory / 'default-preparation-failure.json').read_text())
    assert record['error'] == expected
    assert record['root_retained'] is True
    assert record['root_retention_observation']['archive_registered'] is False
    assert record['persistence']['status'] == 'PERSISTENCE_UNPROVEN'
    assert factory.preparation_failures['default']['persistence']['status'] == 'PERSISTED'
    assert f.archive.leases == {}
    roots = list(f.directory.glob('lvw-s2-default-*'))
    assert len(roots) == 1 and list(roots[0].iterdir()) == []
    assert not {'comfy-start', 'ollama-start'} & set(f.helper.events)
    assert f.sentinel.read_bytes() == b'UNRELATED ORIGINAL'
    assert (f.sibling / 'keep').read_bytes() == b'OTHER RUN'
    closed(factory, opened)
    print('INDEPENDENT_REGISTRATION_FAILURE ' + json.dumps({'fault':fault,'failure':record,'closed_descriptors':len(opened)},sort_keys=True))

def test_cleanup_adapter_preserves_unproven_result_and_original_failure(fixture, monkeypatch):
    f = fixture
    native = legacy.NativeRuntime
    called = []
    def wrapped(args, evidence):
        driver = native(args, evidence)
        remove = driver.remove_owned_reparse_fixture
        def unproven(root):
            result = remove(root)
            called.append({'root':str(root),'original_proven':result.get('proven')})
            return {**result, 'proven':False}
        driver.remove_owned_reparse_fixture = unproven
        return driver
    monkeypatch.setattr(legacy, 'NativeRuntime', wrapped)
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    def fail(*args): raise ValueError('independent final evidence failure')
    monkeypatch.setattr(factory, '_persist_preparation_evidence', fail)
    opened = track_descriptors(monkeypatch)
    with pytest.raises(ValueError, match='independent final evidence failure'):
        factory.prepare_default()
    record = json.loads((f.directory / 'default-preparation-failure.json').read_text())
    assert len(called) == 1
    assert record['error'] == 'independent final evidence failure'
    assert record['cleanup']['proven'] is True
    assert record['cleanup_error'] == 'EvidenceError:native junction cleanup unproven'
    assert record['root_retained'] is True
    assert not (f.directory / 'default-raw').exists()
    assert f.archive.used == {'default'}  # Original owner still enforces no replay.
    assert f.sentinel.read_bytes() == b'UNRELATED ORIGINAL'
    assert (f.sibling / 'keep').read_bytes() == b'OTHER RUN'
    closed(factory, opened)
    print('INDEPENDENT_CLEANUP_ADAPTER ' + json.dumps({'called':called,'failure':record,'closed_descriptors':len(opened)},sort_keys=True))

def test_post_prepare_cleanup_adapter_rejects_replacement_before_archive_write(fixture, monkeypatch):
    f = fixture
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    context = factory.prepare_default()
    assert factory._parent_fd is None and factory._root_fds == {}
    cleanup = context.driver.cleanup()
    remove = context.driver.remove_owned_reparse_fixture
    detached = f.root / 'review-completed-original-parent'
    calls = []
    def move_after_native_cleanup(root):
        result = remove(root)
        f.directory.rename(detached)
        f.directory.mkdir()
        (f.directory / 'foreign').write_bytes(b'UNOWNED')
        calls.append(str(root))
        return result
    monkeypatch.setattr(context.driver, 'remove_owned_reparse_fixture', move_after_native_cleanup)
    with pytest.raises((ValueError, OSError)) as error:
        factory.archive(context, cleanup)
    assert len(calls) == 1
    assert (f.directory / 'foreign').read_bytes() == b'UNOWNED'
    assert (detached / 'other-run/keep').read_bytes() == b'OTHER RUN'
    assert (detached / context.root.name).is_dir()
    unexpected = sorted(p.name for p in f.directory.iterdir() if p.name != 'foreign')
    print('INDEPENDENT_POST_PREPARE_CLEANUP ' + json.dumps({'replacement_writes':unexpected,
          'error_type':type(error.value).__name__, 'error':str(error.value),
          'adapter_invoked':True,'lifecycle_parent_fd':factory._parent_fd,
          'original_root_retained':True,'cleanup_proven':cleanup['proven']},sort_keys=True))
    assert unexpected == [], 'inactive cleanup guard allowed archive output into replacement parent'
