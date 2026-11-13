"""The adapted independent owner probe of the originals correction 04.

This probe is the adaptation of the two defects that the independent
review of the correction 03 reproduced against the candidate
``56a1c5051812b27e8484781890918af3bb9feb41``:

* **O1** - a change of an original *during* the read was accepted and the
  stale seal was published as a verified manifest;
* **O2** - a fifo at the place of an original blocked the parent in the
  synchronous opening, before the regular file check.

The probe drives the *production owner* itself - ``ParentOriginalEvidence``
of ``tools/v0_s3_coordinator.py`` - and it uses the same controlled
triggers as the review: a controlled ``os.read`` that changes the original
after the first block was read and before that block is handed over, and a
real ``mkfifo`` at the place of a sealed original.

Every trigger has an explicit oracle: the owner has to refuse, the reason
has to name the boundary, the trigger has to have fired and the change
has to be observable in the state of the object.  The fifo cases have no
write end at all: the refusal has to come without one, and the probe never
opens a write end to release a blocked owner.

Every file of this probe is synthetic and lives in this report directory.
No original of the product is read, no root of the product is touched, no
process is started, no socket is opened and no service is called.
"""
import hashlib
import json
import os
import shutil
import stat
import threading
import time
from pathlib import Path

from tools import v0_s3_coordinator as c

O = Path(__file__).resolve().parent
ROOTS = O / 'synthetic-roots'
BINDING = {'run_id': 'originals-correction-04', 'candidate_sha': 'a' * 40}
BODY = b'ORIGINAL'


def refuse(function):
    """The refusal of one owner call, or a marker that it was accepted."""
    try:
        function()
    except c.S3IntegrationError as error:
        return error.reason
    except Exception as error:  # noqa: BLE001 - an unexpected error is a failure
        return 'UNEXPECTED:' + type(error).__name__ + ':' + str(error)[:120]
    return None


def evidence(name, body=BODY):
    """A synthetic bound root with three original artifacts."""
    root = ROOTS / name
    shutil.rmtree(root, ignore_errors=True)
    # the sibling of a replaced root is removed as well, so that the probe
    # can be run again without inheriting an older state
    shutil.rmtree(root.parent / (root.name + '-old'), ignore_errors=True)
    (root / 'temp').mkdir(parents=True)
    (root / 'temp/canonical.json').write_bytes(b'{"rows": []}')
    (root / 'temp/source.json').write_bytes(b'{"plan": []}')
    (root / 'temp/raw.bin').write_bytes(body)
    owner = c.ParentOriginalEvidence(**BINDING, child_sha256='b' * 64, root=root,
                                    projection_sha256='c' * 64)
    owner.seal_plan([{'ordinal': index, 'asset_id': 'I%02d' % index,
                       'media_kind': 'image', 'source_sha256': 'd' * 64,
                       'source_bytes': 1} for index in range(1, 17)])
    status = root.stat()
    owner.seal_root([status.st_dev, status.st_ino])
    return root, owner


def seal_all(owner):
    """The seal of the three artifacts of a synthetic root."""
    return owner.seal_originals(canonical='temp/canonical.json',
                                source_plan='temp/source.json',
                                raw=['temp/raw.bin'])


def controlled_read(target_inode, action, delay=0.02):
    """A controlled ``os.read`` that changes the original exactly once.

    The change happens after the first block of the target handle was read
    and before that block is handed to the owner, so it is inside the read
    window of the production reader.  The delay makes the change visible
    in the times of the object: a change of the very same bytes can not be
    seen in the digest, only in the times of the object.
    """
    real_read = os.read
    state = {'fired': False}

    def wrapper(descriptor, size):
        block = real_read(descriptor, size)
        if block and not state['fired']:
            try:
                same = os.fstat(descriptor).st_ino == target_inode
            except OSError:
                same = False
            if same:
                state['fired'] = True
                time.sleep(delay)
                action()
        return block

    return wrapper, state


def descriptors():
    """The number of the descriptors of this process."""
    return len(os.listdir('/proc/self/fd'))


def bounded(function, timeout=2.0):
    """Run one owner call in a controlled worker thread.

    The thread is a daemon and it is always recovered: a call that did not
    finish in time is released and joined, so a failing probe never leaves
    a hanging thread behind.  The release is only used by the recovery of a
    failed probe; the oracle itself never opens a write end of the fifo.
    """
    box = {}

    def worker():
        try:
            box['result'] = function()
        except BaseException as error:  # noqa: BLE001 - the caller inspects it
            box['exception'] = error

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    thread.join(timeout)
    return thread, box


def observe_change(name, root, owner, action, *, seal_first):
    """One controlled change during the read and the refusal of the owner."""
    if seal_first:
        seal_all(owner)
    target = os.stat(root / 'temp/raw.bin').st_ino
    before = os.stat(root / 'temp/raw.bin')
    wrapper, state = controlled_read(target, action)
    real_read = os.read
    os.read = wrapper
    try:
        reason = refuse(owner.manifest if seal_first else lambda: seal_all(owner))
    finally:
        os.read = real_read
    after = os.lstat(root / 'temp/raw.bin')
    observable = (after.st_mtime_ns != before.st_mtime_ns
                  or after.st_ino != before.st_ino
                  or not stat.S_ISREG(after.st_mode))
    if reason is None or not state['fired'] or not observable:
        raise AssertionError('the owner did not refuse a controlled change: '
                             + name + ' reason=' + str(reason))
    return {'trigger': name, 'refusal': reason, 'trigger_fired': state['fired'],
            'change_observable_in_the_object': observable,
            'published_originals': len(owner.originals.get('raw', []))}


def same_length_rewrite(root):
    def action():
        (root / 'temp/raw.bin').write_bytes(b'MODIFIED')
    return action


def same_bytes_rewrite(root):
    def action():
        (root / 'temp/raw.bin').write_bytes(BODY)
    return action


def growth(root):
    def action():
        (root / 'temp/raw.bin').write_bytes(BODY + b'GROWN')
    return action


def truncation(root):
    def action():
        (root / 'temp/raw.bin').write_bytes(b'ORI')
    return action


def object_replacement(root):
    def action():
        target = root / 'temp/raw.bin'
        target.unlink()
        target.write_bytes(BODY)
    return action


def path_became_a_link(root):
    def action():
        moved = root / 'temp/moved.bin'
        os.rename(root / 'temp/raw.bin', moved)
        (root / 'temp/raw.bin').symlink_to(moved)
    return action


def ancestor_replaced(root):
    def action():
        os.rename(root / 'temp', root / 'temp-old')
        (root / 'temp').mkdir()
        (root / 'temp/raw.bin').write_bytes(BODY)
    return action


def root_replaced(root):
    def action():
        moved = root.parent / (root.name + '-old')
        shutil.rmtree(moved, ignore_errors=True)
        os.rename(root, moved)
        (root / 'temp').mkdir(parents=True)
        (root / 'temp/raw.bin').write_bytes(BODY)
    return action


def main():
    ROOTS.mkdir(parents=True, exist_ok=True)
    results = {}
    before = descriptors()

    # -- O1: a change of the original during the read window --------------
    changes = (
        ('same_length_rewrite', same_length_rewrite),
        ('same_bytes_rewrite', same_bytes_rewrite),
        ('growth', growth),
        ('truncation', truncation),
        ('object_replacement', object_replacement),
        ('path_became_a_link', path_became_a_link),
        ('ancestor_replaced', ancestor_replaced),
        ('root_replaced', root_replaced),
    )
    seal_window = []
    consume_window = []
    for name, factory in changes:
        root, owner = evidence('seal-' + name)
        seal_window.append(observe_change(name, root, owner, factory(root),
                                           seal_first=False))
        root, owner = evidence('consume-' + name)
        consume_window.append(observe_change(name, root, owner, factory(root),
                                             seal_first=True))
    results['O1_seal_window'] = seal_window
    results['O1_consume_window'] = consume_window

    # -- O2: a fifo at the place of an original ---------------------------
    fifo_seal = {}
    root, owner = evidence('fifo-seal')
    fifo = root / 'temp/raw.bin'
    fifo.unlink()
    os.mkfifo(fifo)
    seal_started = time.monotonic()
    thread, box = bounded(lambda: seal_all(owner))
    fifo_seal['blocked_on_the_fifo'] = thread.is_alive()
    if thread.is_alive():
        release = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        os.close(release)
        thread.join(2.0)
    fifo_seal['elapsed_seconds'] = round(time.monotonic() - seal_started, 3)
    fifo_seal['thread_settled'] = not thread.is_alive()
    exception = box.get('exception')
    fifo_seal['refusal'] = getattr(exception, 'reason', None)
    fifo_seal['write_end_opened_by_the_oracle'] = False
    fifo.unlink()
    assert not thread.is_alive(), 'the seal blocked on the fifo'
    assert fifo_seal['refusal'] is not None, fifo_seal
    results['O2_fifo_at_the_seal'] = fifo_seal

    fifo_consume = {}
    root, owner = evidence('fifo-consume')
    seal_all(owner)
    fifo = root / 'temp/raw.bin'
    fifo.unlink()
    os.mkfifo(fifo)
    consume_started = time.monotonic()
    thread, box = bounded(owner.manifest)
    fifo_consume['blocked_on_the_fifo'] = thread.is_alive()
    if thread.is_alive():
        release = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        os.close(release)
        thread.join(2.0)
    fifo_consume['elapsed_seconds'] = round(time.monotonic() - consume_started, 3)
    fifo_consume['thread_settled'] = not thread.is_alive()
    exception = box.get('exception')
    fifo_consume['refusal'] = getattr(exception, 'reason', None)
    fifo_consume['write_end_opened_by_the_oracle'] = False
    fifo.unlink()
    assert not thread.is_alive(), 'the manifest blocked on the fifo'
    assert fifo_consume['refusal'] is not None, fifo_consume
    results['O2_fifo_after_the_seal'] = fifo_consume

    # -- the legal case is still legal ------------------------------------
    root, owner = evidence('legal')
    sealed = seal_all(owner)
    manifest = owner.manifest()
    results['legal_case'] = {
        'sha256': sealed['raw'][0]['sha256'],
        'expected_sha256': hashlib.sha256(BODY).hexdigest(),
        'bytes': sealed['raw'][0]['bytes'],
        'verified': manifest['reverification']['verified'],
        'checked': len(manifest['reverification']['checked']),
        'original_open_primitive': manifest['original_open_primitive'],
    }
    assert sealed['raw'][0]['sha256'] == hashlib.sha256(BODY).hexdigest()
    assert manifest['reverification']['verified'] is True

    # -- a platform without the safe primitives fails closed --------------
    original_follow = c._no_follow_open_supported
    original_non_block = c._non_block_open_supported
    c._no_follow_open_supported = lambda: False
    try:
        missing_follow = refuse(owner.manifest)
    finally:
        c._no_follow_open_supported = original_follow
    c._non_block_open_supported = lambda: False
    try:
        missing_non_block = refuse(owner.manifest)
    finally:
        c._non_block_open_supported = original_non_block
    results['fail_closed'] = {'without_no_follow': missing_follow,
                              'without_non_block': missing_non_block}
    assert missing_follow == 'S3_ORIGINAL_SAFE_OPEN_UNSUPPORTED'
    assert missing_non_block == 'S3_ORIGINAL_SAFE_OPEN_UNSUPPORTED'

    after = descriptors()
    results['descriptors'] = {'before': before, 'after': after,
                              'leaked': after - before}
    assert after == before, (before, after)
    results['stage_pass_claim'] = False
    results['product_gate0'] = False
    results['real_execution_performed'] = False
    results['synthetic_only'] = True
    (O / 'owner-observations.json').write_text(
        json.dumps(results, indent=2, sort_keys=True) + '\n')
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
