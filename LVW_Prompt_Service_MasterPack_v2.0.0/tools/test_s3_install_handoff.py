"""Fixed correction oracles; real protected owner and inherited preparation."""
import os
from pathlib import Path
import pytest
from LVW_V0_RuntimePatch.tests.test_s3_installed_runtime import fixture, assert_failure
from tools import v0_incremental_package as package
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory


def foreign_tree(f):
    path = f.root / 'foreign-unregistered'; path.mkdir()
    (path / 'sentinel').write_bytes(b'FOREIGN ORIGINAL')
    return path


def unchanged(foreign):
    assert sorted(p.name for p in foreign.iterdir()) == ['sentinel']
    assert (foreign / 'sentinel').read_bytes() == b'FOREIGN ORIGINAL'


def test_late_child_redirect_after_validation_zero_foreign_writes(fixture, monkeypatch):
    f = fixture; foreign = foreign_tree(f); validate = package._validate_archive; calls = []
    def redirect(*args, **kwargs):
        result = validate(*args, **kwargs); calls.append(type(args[0]).__name__)
        if len(calls) == 2:
            target = f.archive.lease('default')
            (target / 'custom_nodes').rmdir()
            (target / 'custom_nodes').symlink_to(foreign, target_is_directory=True)
        return result
    monkeypatch.setattr(package, '_validate_archive', redirect)
    result = assert_failure(f, InstalledPackageRuntimeFactory(**f.kwargs))
    unchanged(foreign)
    assert calls == ['_SealedArchive', '_SealedArchive']
    assert result['root_retained'] and 'pathname archive deletion forbidden' in result['cleanup_error']


@pytest.mark.parametrize('kind', ['symlink', 'identical-file', 'in-place-write'])
def test_late_archive_identity_change_zero_start(fixture, monkeypatch, kind):
    f = fixture; install = package.command_install
    def swap(args):
        raw = f.archive_path.read_bytes()
        if kind == 'in-place-write':
            f.archive_path.write_bytes(raw)
        else:
            original = f.root / 'original.zip'; f.archive_path.rename(original)
            if kind == 'symlink': f.archive_path.symlink_to(original)
            else: f.archive_path.write_bytes(raw)
        return install(args)
    monkeypatch.setattr(package, 'command_install', swap)
    result = assert_failure(f, InstalledPackageRuntimeFactory(**f.kwargs))
    assert 'archive identity drift' in str(result)
    assert not list(f.directory.glob('lvw-s2-default-*/custom_nodes/lvw_v0_bridge'))


def test_returned_session_mismatch_zero_start_and_original_receipt(fixture, monkeypatch):
    f = fixture; install = package.command_install
    def alter(args):
        receipt = install(args); receipt['session_id'] = 'foreign-session'; return receipt
    monkeypatch.setattr(package, 'command_install', alter)
    result = assert_failure(f, InstalledPackageRuntimeFactory(**f.kwargs))
    assert 'ownership mismatch' in result['error']
    assert result['evidence']['deployment']['install_receipt']['session_id'] == 'foreign-session'
    assert (f.directory / 'default-package-install.json').is_file()


@pytest.mark.parametrize('boundary', ['before-commit', 'inside-commit', 'owner-write', 'staging-cleanup'])
def test_descriptor_mutation_and_error_retention_never_follow_replacement(fixture, monkeypatch, boundary):
    f = fixture; foreign = foreign_tree(f); hit = []
    rename, open_file, rmdir = os.rename, os.open, os.rmdir
    def replace_child():
        root = f.archive.lease('default')
        rename(root / 'custom_nodes', f.root / 'detached-owned-custom-nodes')
        (root / 'custom_nodes').symlink_to(foreign, target_is_directory=True)
        hit.append(boundary)
    def commit(source, target, *args, **kwargs):
        if kwargs.get('dst_dir_fd') is not None and not hit:
            replace_child()
            if boundary == 'before-commit': raise OSError('injected commit interruption')
        return rename(source, target, *args, **kwargs)
    def owner(name, flags, *args, **kwargs):
        if name == package.OWNERSHIP_FILE_NAME and flags & os.O_CREAT and not hit:
            replace_child()
        return open_file(name, flags, *args, **kwargs)
    def cleanup(name, *args, **kwargs):
        if kwargs.get('dir_fd') is not None and not hit:
            replace_child()
        return rmdir(name, *args, **kwargs)
    if boundary in ('before-commit', 'inside-commit'): monkeypatch.setattr(os, 'rename', commit)
    elif boundary == 'owner-write': monkeypatch.setattr(os, 'open', owner)
    else: monkeypatch.setattr(os, 'rmdir', cleanup)
    result = assert_failure(f, InstalledPackageRuntimeFactory(**f.kwargs))
    assert hit == [boundary]
    unchanged(foreign)
    assert result['root_retained']
    assert result['evidence']['deployment']['retention_required']
    assert 'RETAIN_NO_PATHNAME_ROLLBACK' in str(result)


def test_plain_replacement_root_not_deleted_by_inherited_failure_archive(fixture, monkeypatch):
    f = fixture; rename = os.rename; replaced = []
    def move(source, target, *args, **kwargs):
        if kwargs.get('dst_dir_fd') is not None and not replaced:
            root = f.archive.lease('default')
            rename(root, f.root / 'detached-owned-root')
            root.mkdir(); (root / 'foreign-sentinel').write_bytes(b'UNRELATED ROOT')
            replaced.append(root)
        return rename(source, target, *args, **kwargs)
    monkeypatch.setattr(os, 'rename', move)
    result = assert_failure(f, InstalledPackageRuntimeFactory(**f.kwargs))
    assert (replaced[0] / 'foreign-sentinel').read_bytes() == b'UNRELATED ROOT'
    assert result['root_retained'] and 'pathname archive deletion forbidden' in result['cleanup_error']


def test_unsupported_descriptor_platform_fails_before_writes(fixture, monkeypatch):
    f = fixture; monkeypatch.setattr(package, '_protected_supported', lambda: False)
    result = assert_failure(f, InstalledPackageRuntimeFactory(**f.kwargs))
    assert 'POSIX no-follow' in result['error']
    root = Path(result['evidence']['owned_run_root'])
    assert sorted(p.name for p in root.iterdir()) == ['custom_nodes', 'input', 'output', 'temp']
    assert all(not list(p.iterdir()) for p in root.iterdir())


def test_protected_receipt_binds_snapshot_and_session(fixture):
    f = fixture; factory = InstalledPackageRuntimeFactory(**f.kwargs)
    context = factory.prepare_default()
    receipt = factory.evidence['default']['deployment']['install_receipt']
    owner, _ = package._read_ownership_record(context.root)
    assert owner['session_id'] == receipt['session_id']
    proof = receipt['protected_source']
    assert proof['sha256'] == f.kwargs['package_sha256']
    assert proof['bytes'] == f.archive_path.stat().st_size
    assert proof['file_identity'][:2] == [f.archive_path.stat().st_dev, f.archive_path.stat().st_ino]
    assert f.archive(context, context.driver.cleanup())['proven']


@pytest.mark.parametrize('which', ['archive', 'marker'])
def test_late_special_file_refused_without_blocking_or_target_write(fixture, monkeypatch, which):
    f = fixture; enter = package.ProtectedInstall.__enter__
    def replace(handoff):
        path = f.archive_path if which == 'archive' else f.marker
        path.unlink(); os.mkfifo(path)
        return enter(handoff)
    monkeypatch.setattr(package.ProtectedInstall, '__enter__', replace)
    result = assert_failure(f, InstalledPackageRuntimeFactory(**f.kwargs))
    assert 'regular and bounded' in result['error']
    root = Path(result['evidence']['owned_run_root'])
    assert all(not list(p.iterdir()) for p in root.iterdir())
