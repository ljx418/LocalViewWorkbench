"""Bounded independent observations, executed only by the preimport guard."""
import copy, errno, hashlib, json, os, shutil, sys, tempfile
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q

OUT = Path(__file__).resolve().parent
ROOT = Path(tempfile.mkdtemp(prefix='lvw-independent-c07-'))
REGISTERED = [str(ROOT)]
RESULTS = []
count = lambda: len(os.listdir('/proc/self/fd'))
def record(name, **values):
    RESULTS.append(dict(name=name, **values))
def prepare(name):
    root = ROOT / name
    REGISTERED.append(str(root))
    phase, driver, projection = t._prepare(root, clock=t.FakeClock(step=0.0))
    receipt = phase.run()
    return phase, driver, receipt, hashlib.sha256(projection).hexdigest()
def score(phase, receipt, sha):
    try:
        value = q.recompute_scores(receipt, phase.directory, t._scores(receipt, sha), independence=t._independence())
        return dict(refused=False, aggregate_pass=value['aggregate_pass'], all_rows_resolved=value['all_rows_resolved'])
    except Exception as error:
        return dict(refused=True, error=type(error).__name__ + ': ' + str(error))
def mutate(target, mode):
    retained = target.with_name(target.name + '-retained')
    target.rename(retained)
    if mode == 'symlink':
        target.symlink_to(retained, target_is_directory=retained.is_dir())
    elif mode == 'plain':
        if retained.is_dir(): target.mkdir()
        else: target.write_bytes(retained.read_bytes())
    return retained

try:
    for name, target_kind, mode, completion in [
        ('earlier_canonical_missing', 'canonical', 'missing', False),
        ('earlier_seal_plain', 'seal', 'plain', False),
        ('earlier_seal_symlink', 'seal', 'symlink', False),
        ('earlier_raw_leaf_plain', 'raw0', 'plain', False),
        ('earlier_raw_leaf_missing', 'raw0', 'missing', False),
        ('earlier_raw_parent_missing', 'parent0', 'missing', False),
        ('earlier_raw_parent_symlink', 'parent0', 'symlink', False),
        ('final_seal_missing', 'seal', 'missing', True),
        ('final_raw_parent_plain', 'parent0', 'plain', True),
    ]:
        phase, driver, receipt, sha = prepare(name)
        before_receipt = copy.deepcopy(receipt)
        paths = {'canonical': phase.directory / q.CANONICAL_RECEIPT_NAME,
                 'seal': phase.directory / receipt['source_plan']['path'],
                 'raw0': phase.directory / receipt['rows'][0]['raw_artifact'],
                 'raw1': phase.directory / receipt['rows'][1]['raw_artifact']}
        paths['parent0'] = paths['raw0'].parent
        target = paths[target_kind]
        original_leaf = paths['raw0'] if target_kind == 'parent0' else target
        original_hash = hashlib.sha256(original_leaf.read_bytes()).hexdigest()
        state = {'fired': 0}
        def action():
            state['fired'] += 1
            state['retained'] = mutate(target, mode)
        original_read, original_verify = q.os.read, q._ArtifactBoundary.verify
        trigger = paths['raw1' if target_kind in ('raw0', 'parent0') else 'raw0'].stat().st_ino
        def hooked_read(fd, size):
            value = original_read(fd, size)
            if not state['fired'] and os.fstat(fd).st_ino == trigger: action()
            return value
        def hooked_verify(self):
            if not state['fired'] and sys._getframe(1).f_code.co_name == 'recompute_scores': action()
            return original_verify(self)
        before_fd = count()
        try:
            if completion: q._ArtifactBoundary.verify = hooked_verify
            else: q.os.read = hooked_read
            result = score(phase, receipt, sha)
        finally:
            q.os.read, q._ArtifactBoundary.verify = original_read, original_verify
        retained_leaf = state['retained'] / paths['raw0'].name if target_kind == 'parent0' else state['retained']
        record(name, observation=result, hook_fired=state['fired'], original_bytes_unchanged=hashlib.sha256(retained_leaf.read_bytes()).hexdigest() == original_hash,
               caller_receipt_unchanged=receipt == before_receipt, fds_before=before_fd, fds_after=count())

    phase, driver, receipt, sha = prepare('full_shape')
    before_fd = count()
    boundary = q._ArtifactBoundary(phase.directory)
    names = [q.CANONICAL_RECEIPT_NAME, receipt['source_plan']['path']] + [row['raw_artifact'] for row in receipt['rows']]
    first = [boundary.read(name, q.MAX_ARTIFACT_BYTES) for name in names]
    during = count()
    identities = [(e['parent_fd'], e['name'], e['identity'], e['fd'], e['kind']) for e in boundary._custody.entries()]
    for _ in range(3):
        assert first == [boundary.read(name, q.MAX_ARTIFACT_BYTES) for name in names]
    boundary.verify()
    after_repeat = count()
    entries = boundary._custody.count()
    same = identities == [(e['parent_fd'], e['name'], e['identity'], e['fd'], e['kind']) for e in boundary._custody.entries()]
    boundary.close(); boundary.close()
    record('full16_shape_repeat_and_normal_cleanup', rows=len(receipt['rows']), submissions=driver.submissions, reserved=receipt['provider_calls_reserved'], entries=entries, limit=q._CUSTODY_ENTRY_LIMIT,
           fds_before=before_fd, fds_during=during, fds_after_repeat=after_repeat, fds_after_close=count(), registry_unchanged=same)

    tiny = ROOT / 'tiny' / 'temp' / 's3-quality'
    tiny.mkdir(parents=True)
    for i in range(73): (tiny / ('f' + str(i))).write_bytes(b'abcd')
    before_fd = count()
    boundary = q._ArtifactBoundary(tiny)
    for i in range(72): assert boundary.read('f' + str(i), 4) == b'abcd'
    exact = count()
    state = {'opens': 0, 'peak': exact}
    original_open = q.os.open
    def track_open(*args, **kwargs):
        fd = original_open(*args, **kwargs)
        state['opens'] += 1
        state['peak'] = max(state['peak'], count())
        return fd
    q.os.open = track_open
    try:
        try: boundary.read('f72', 4); error = None
        except Exception as exc: error = type(exc).__name__ + ': ' + str(exc)
    finally: q.os.open = original_open
    all_old = boundary._custody.count() == 72
    boundary.verify()
    boundary.close()
    record('exact72_oneover73_admission', exact_fds=exact, error=error, extra_opens=state['opens'], peak_fds=state['peak'], old_entries_retained=all_old,
           fds_before=before_fd, fds_after_close=count())

    # Repeat the same-name lookup after replacement: the first object must
    # remain pinned and its new named replacement must never become authority.
    for mode in ('plain', 'missing', 'symlink'):
        target = tiny / 'reuse'
        target.write_bytes(b'abcd')
        boundary = q._ArtifactBoundary(tiny)
        boundary.read('reuse', 4)
        entry = dict(boundary._custody.entries()[0])
        retained = mutate(target, mode)
        try: boundary.read('reuse', 4); error = None
        except Exception as exc: error = type(exc).__name__ + ': ' + str(exc)
        record('dedup_replaced_' + mode, error=error, registry_identity_unchanged=entry == boundary._custody.entries()[0], held_original_identity=(os.fstat(entry['fd']).st_ino == entry['identity'][1]))
        boundary.close()
        if mode != 'missing': target.unlink()
        retained.unlink()

    # Inject one ordinary OS metadata failure after a successful open.  The
    # probe explicitly closes any leaked descriptor only AFTER measuring it.
    for kind in ('leaf', 'directory'):
        (tiny / 'nested').mkdir(exist_ok=True)
        (tiny / 'nested' / 'file').write_bytes(b'abcd')
        before_fd = count()
        boundary = q._ArtifactBoundary(tiny)
        original_open, original_fstat = q.os.open, q.os.fstat
        state = {'fd': None, 'fired': 0}
        target_name = 'f0' if kind == 'leaf' else 'nested'
        def tracking_open(name, *args, **kwargs):
            fd = original_open(name, *args, **kwargs)
            if str(name) == target_name: state['fd'] = fd
            return fd
        def failing_fstat(fd):
            if fd == state['fd'] and not state['fired']:
                state['fired'] += 1
                raise OSError(errno.EIO, 'independent injected metadata failure')
            return original_fstat(fd)
        q.os.open, q.os.fstat = tracking_open, failing_fstat
        try:
            try: boundary.read('f0' if kind == 'leaf' else 'nested/file', 4); error = None
            except Exception as exc: error = type(exc).__name__ + ': ' + str(exc)
        finally: q.os.open, q.os.fstat = original_open, original_fstat
        boundary.close()
        after_close = count()
        try: original_fstat(state['fd']); leaked = True
        except OSError: leaked = False
        if leaked: os.close(state['fd'])
        record('postopen_fstat_error_' + kind, hook_fired=state['fired'], error=error, fds_before=before_fd, fds_after_boundary_close=after_close,
               opened_descriptor_still_live=leaked, fds_after_probe_remediation=count())

    before_fd = count()
    broken = ROOT / 'broken'
    broken.mkdir(); (broken / 'temp').write_bytes(b'bad')
    try: q._ArtifactBoundary(broken / 'temp' / 's3-quality'); error = None
    except Exception as exc: error = str(exc)
    record('constructor_error_cleanup', error=error, fds_before=before_fd, fds_after=count())

    for stage in ('read', 'lseek', 'stat'):
        before_fd = count()
        boundary = q._ArtifactBoundary(tiny)
        boundary.read('f0', 4)
        original = getattr(q.os, stage)
        state = {'fired': 0}
        def failing(*args, **kwargs):
            state['fired'] += 1
            raise OSError(errno.EIO, 'independent injected ' + stage + ' failure')
        setattr(q.os, stage, failing)
        try:
            try: boundary.read('f0', 4); error = None
            except Exception as exc: error = str(exc)
        finally: setattr(q.os, stage, original)
        boundary.close()
        record('retained_' + stage + '_error_cleanup', hook_fired=state['fired'], error=error, fds_before=before_fd, fds_after_close=count())
finally:
    shutil.rmtree(ROOT)

payload = dict(count=len(RESULTS), observations=RESULTS, registered_roots=REGISTERED, owned_root=str(ROOT), removed=not ROOT.exists(), note='Observations are not extra product tests; exit0 means capture completed, including defects.')
(OUT / 'targeted-observations.json').write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
print(json.dumps(payload, indent=2, sort_keys=True))
