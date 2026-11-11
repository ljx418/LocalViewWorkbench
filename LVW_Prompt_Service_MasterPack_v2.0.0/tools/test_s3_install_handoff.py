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


def lifecycle_fds(monkeypatch):
    opened = []
    original = os.open
    def track(*args, **kwargs):
        fd = original(*args, **kwargs); opened.append(fd); return fd
    monkeypatch.setattr(os, 'open', track)
    return opened


def assert_lifecycle_closed(factory, opened):
    assert factory._parent_fd is None and factory._root_fds == {}
    for fd in set(opened):
        with pytest.raises(OSError): os.fstat(fd)


@pytest.mark.parametrize('boundary', ['receipt', 'post-deploy-copy', 'post-deploy-return'])
def test_failure_lifecycle_stays_on_moved_parent(fixture, monkeypatch, boundary):
    import json
    f = fixture; detached = f.root / 'moved-owned-parent'
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    def move():
        f.directory.rename(detached); f.directory.mkdir()
        (f.directory / 'foreign').write_bytes(b'UNOWNED')
    if boundary == 'receipt':
        save = package.ProtectedInstall.save_receipt
        def injected(handoff, name, receipt):
            move(); return save(handoff, name, receipt)
        monkeypatch.setattr(package.ProtectedInstall, 'save_receipt', injected)
    elif boundary == 'post-deploy-copy':
        def fail(*args, **kwargs):
            move(); raise ValueError('original later copy error')
        monkeypatch.setattr(factory, '_copy', fail)
    else:
        deploy = factory._deploy
        def injected(root):
            deploy(root); move()
        monkeypatch.setattr(factory, '_deploy', injected)
    opened = lifecycle_fds(monkeypatch)
    with pytest.raises((ValueError, OSError, package.PackageError)) as caught:
        factory.prepare_default()
    assert sorted(p.name for p in f.directory.iterdir()) == ['foreign']
    assert (f.directory / 'foreign').read_bytes() == b'UNOWNED'
    record = json.loads((detached / 'default-preparation-failure.json').read_text())
    assert record['error'] == str(caught.value)
    assert record['root_retained'] is True
    assert (detached / record['root_name']).is_dir()
    assert factory.preparation_failures['default']['persistence']['status'] == 'PERSISTED'
    assert not {'comfy-start', 'ollama-start'} & set(f.helper.events)
    assert (detached / 'other-run/keep').read_bytes() == b'OTHER RUN'
    assert_lifecycle_closed(factory, opened)


@pytest.mark.parametrize('failure_kind', ['early', 'deployment', 'conflict', 'open-error', 'write-error', 'fsync-error'])
def test_failure_persistence_preserves_original_error_and_closes(fixture, monkeypatch, failure_kind):
    import json
    f = fixture; factory = InstalledPackageRuntimeFactory(**f.kwargs)
    if failure_kind == 'early':
        def fail(): raise ValueError('original binding failure')
        factory.verify_complete = fail
    else:
        factory.package_sha256 = '0'*64
    filename = f.directory / 'default-preparation-failure.json'
    if failure_kind == 'conflict': filename.write_bytes(b'PREEXISTING FAILURE')
    opened = lifecycle_fds(monkeypatch)
    if failure_kind == 'open-error':
        original = os.open
        def fail_open(name, *args, **kwargs):
            if name == 'default-preparation-failure.json': raise OSError('receipt disk denied')
            return original(name, *args, **kwargs)
        monkeypatch.setattr(os, 'open', fail_open)
    if failure_kind == 'fsync-error':
        original = os.fsync
        def fail_sync(fd):
            if filename.exists() and os.fstat(fd).st_ino == filename.stat().st_ino:
                raise OSError('receipt sync failed')
            return original(fd)
        monkeypatch.setattr(os, 'fsync', fail_sync)
    if failure_kind == 'write-error':
        original_write = os.write
        def fail_write(fd, data):
            if filename.exists() and os.fstat(fd).st_ino == filename.stat().st_ino:
                raise OSError('receipt write failed')
            return original_write(fd, data)
        monkeypatch.setattr(os, 'write', fail_write)
    with pytest.raises((ValueError, OSError, package.PackageError)) as caught:
        factory.prepare_default()
    record = factory.preparation_failures['default']
    assert record['error'] == str(caught.value)
    assert 'receipt disk denied' not in record['error'] and 'receipt sync failed' not in record['error']
    if failure_kind in ('conflict', 'open-error', 'write-error', 'fsync-error'):
        assert record['persistence']['status'] == 'PERSISTENCE_UNPROVEN'
        if failure_kind == 'conflict': assert filename.read_bytes() == b'PREEXISTING FAILURE'
        elif failure_kind == 'open-error': assert not filename.exists()
        elif failure_kind == 'write-error': assert filename.read_bytes() == b''
        else: assert json.loads(filename.read_text())['persistence']['status'] == 'PERSISTENCE_UNPROVEN'
    else:
        assert record['persistence']['status'] == 'PERSISTED'
        assert json.loads(filename.read_text())['error'] == str(caught.value)
    assert record['root_retained'] is (None if failure_kind == 'early' else True)
    assert not {'comfy-start', 'ollama-start'} & set(f.helper.events)
    assert f.sentinel.read_bytes() == b'UNRELATED ORIGINAL'
    assert (f.sibling / 'keep').read_bytes() == b'OTHER RUN'
    assert_lifecycle_closed(factory, opened)


def test_successful_preparation_releases_lifecycle_handles(fixture, monkeypatch):
    f = fixture; factory = InstalledPackageRuntimeFactory(**f.kwargs)
    opened = lifecycle_fds(monkeypatch)
    context = factory.prepare_default()
    assert_lifecycle_closed(factory, opened)
    assert factory.preparation_failures == {}
    assert f.archive(context, context.driver.cleanup())['proven']


@pytest.mark.parametrize('boundary', ['complete-allocation', 'authorize-allocation',
    'archive-authorization', 'register-directories', 'deploy-samples',
    'native-final-evidence', 'error-archive'])
def test_correction03_adjacent_callback_write_audit(fixture, monkeypatch, boundary):
    import json
    from tools import v0_s2_stage_runtime as legacy
    f = fixture; detached = f.root / 'audit-original-parent'
    moved = []; baseline = []; events_at_move = []
    def inventory(path):
        return sorted((p.relative_to(path).as_posix(), p.read_bytes().hex() if p.is_file() else 'DIR')
                      for p in path.rglob('*'))
    def move():
        root = next(f.directory.glob('lvw-s2-default-*'), None)
        f.directory.rename(detached); f.directory.mkdir()
        (f.directory / 'foreign').write_bytes(b'FOREIGN SENTINEL')
        if root is not None:
            fake = f.directory / root.name; fake.mkdir()
            # Supply plausible replacement parents so missing-path errors do
            # not hide a callback-to-write gap.
            if boundary not in ('archive-authorization', 'register-directories'):
                for name in ('input', 'output', 'temp', 'custom_nodes'): (fake / name).mkdir()
        baseline.extend(inventory(f.directory)); moved.append(True)
        events_at_move.extend(f.helper.events)
    kwargs = dict(f.kwargs)
    if boundary == 'authorize-allocation':
        def authorize(action, *args):
            if action == 'prepare_bound_native_runtime': move()
        kwargs['authorize'] = authorize
    if boundary in ('archive-authorization', 'error-archive'):
        def authorize(action, *args):
            wanted = 'register_fresh_archive_root' if boundary == 'archive-authorization' else 'archive_owned_terminal_root'
            if action == wanted: move()
        f.archive.authorize = authorize
    factory = InstalledPackageRuntimeFactory(**kwargs)
    if boundary == 'complete-allocation':
        complete = factory.verify_complete
        def verify():
            proof = complete(); move(); return proof
        factory.verify_complete = verify
    elif boundary == 'register-directories':
        register = factory.archive.register
        def registered(*args):
            result = register(*args); move(); return result
        monkeypatch.setattr(factory.archive, 'register', registered)
    elif boundary == 'deploy-samples':
        deploy = factory._deploy
        def deployed(root):
            deploy(root); move()
        monkeypatch.setattr(factory, '_deploy', deployed)
    elif boundary == 'native-final-evidence':
        native = legacy.NativeRuntime
        def wrapped(args, evidence):
            driver = native(args, evidence)
            summary = driver.ownership_summary
            def finish():
                result = summary(); move(); return result
            driver.ownership_summary = finish
            return driver
        monkeypatch.setattr(legacy, 'NativeRuntime', wrapped)
    elif boundary == 'error-archive':
        def fail(*args, **kwargs): raise ValueError('original later preparation error')
        monkeypatch.setattr(factory, '_copy', fail)
    opened = lifecycle_fds(monkeypatch)
    caught = None
    try:
        factory.prepare_default()
    except (ValueError, OSError, package.PackageError) as error:
        caught = error
    print('ADJACENT_BOUNDARY', json.dumps({'boundary': boundary, 'replacement_before': baseline,
          'replacement_after': inventory(f.directory), 'error': str(caught),
          'events_at_move': events_at_move, 'events_after': f.helper.events}, sort_keys=True))
    assert moved and inventory(f.directory) == baseline
    assert caught is not None
    assert f.helper.events.count('comfy-start') == events_at_move.count('comfy-start')
    assert f.helper.events.count('ollama-start') == events_at_move.count('ollama-start')
    record = json.loads((detached / 'default-preparation-failure.json').read_text())
    assert record['error'] == str(caught)
    assert record['root_retained'] is (None if boundary in ('complete-allocation', 'authorize-allocation') else True)
    assert f.sentinel.read_bytes() == b'UNRELATED ORIGINAL'
    assert (detached / 'other-run/keep').read_bytes() == b'OTHER RUN'
    assert_lifecycle_closed(factory, opened)


def test_correction03_registration_writer_uses_original_descriptor(fixture, monkeypatch):
    import json
    f = fixture; detached = f.root / 'registration-original-parent'
    persist = f.archive._persist_registration
    def move(directory, label, record, **kwargs):
        f.directory.rename(detached); f.directory.mkdir()
        (f.directory / 'foreign').write_bytes(b'FOREIGN')
        return persist(directory, label, record, **kwargs)
    monkeypatch.setattr(f.archive, '_persist_registration', move)
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    opened = lifecycle_fds(monkeypatch)
    with pytest.raises(ValueError): factory.prepare_default()
    assert sorted(p.name for p in f.directory.iterdir()) == ['foreign']
    assert (detached / 'default-root-lease.json').is_file()
    record = json.loads((detached / 'default-preparation-failure.json').read_text())
    assert record['root_retained'] is True
    assert record['root_retention_observation']['archive_registered'] is True
    assert not {'comfy-start', 'ollama-start'} & set(f.helper.events)
    assert_lifecycle_closed(factory, opened)


def test_correction03_allocation_collisions_are_finite_and_preserved(fixture, monkeypatch):
    from tools import v0_s3_stage_runtime as runtime
    f = fixture; name = 'lvw-s2-default-' + 'a'*16
    existing = f.directory / name; existing.mkdir(); (existing / 'keep').write_bytes(b'OTHER')
    attempts = []
    def token(size): attempts.append(size); return 'a'*16
    monkeypatch.setattr(runtime.secrets, 'token_hex', token)
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    with pytest.raises(ValueError, match='collision budget exhausted'): factory.prepare_default()
    assert len(attempts) == 8
    assert (existing / 'keep').read_bytes() == b'OTHER'
    assert factory.preparation_failures['default']['root_retained'] is None
    assert not f.archive.leases


def test_correction03_allocation_open_failure_is_unknown_without_cleanup(fixture, monkeypatch):
    f = fixture; original = os.open
    def refuse(name, *args, **kwargs):
        if isinstance(name, str) and name.startswith('lvw-s2-default-'):
            raise OSError('allocation open failed')
        return original(name, *args, **kwargs)
    monkeypatch.setattr(os, 'open', refuse)
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    with pytest.raises(OSError, match='allocation open failed'): factory.prepare_default()
    monkeypatch.setattr(os, 'open', original)  # Restore before the owning fixture removes its retained root.
    assert len(list(f.directory.glob('lvw-s2-default-*'))) == 1
    assert factory.preparation_failures['default']['root_retained'] is None
    assert factory.preparation_failures['default']['persistence']['status'] == 'PERSISTED'
    assert not f.archive.leases
    assert not {'comfy-start', 'ollama-start'} & set(f.helper.events)


def test_correction03_archive_cleanup_callback_cannot_write_replacement(fixture, monkeypatch):
    import json
    from tools import v0_s2_stage_runtime as legacy
    f = fixture; detached = f.root / 'cleanup-original-parent'; native = legacy.NativeRuntime
    def boundary(args, evidence):
        driver = native(args, evidence); remove = driver.remove_owned_reparse_fixture
        def moved(root):
            result = remove(root)
            f.directory.rename(detached); f.directory.mkdir()
            (f.directory / 'foreign').write_bytes(b'FOREIGN')
            return result
        driver.remove_owned_reparse_fixture = moved
        return driver
    monkeypatch.setattr(legacy, 'NativeRuntime', boundary)
    factory = InstalledPackageRuntimeFactory(**f.kwargs)
    def fail(*args): raise ValueError('original final evidence failure')
    monkeypatch.setattr(factory, '_persist_preparation_evidence', fail)
    opened = lifecycle_fds(monkeypatch)
    with pytest.raises(ValueError, match='original final evidence failure'): factory.prepare_default()
    after = sorted(p.name for p in f.directory.iterdir())
    print('ARCHIVE_CLEANUP_BOUNDARY', json.dumps({'replacement_entries': after}))
    assert after == ['foreign']
    record = json.loads((detached / 'default-preparation-failure.json').read_text())
    assert record['root_retained'] is True
    assert record['error'] == 'original final evidence failure'
    assert (detached / 'other-run/keep').read_bytes() == b'OTHER RUN'
    assert_lifecycle_closed(factory, opened)
