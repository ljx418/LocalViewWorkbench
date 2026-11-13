"""The adapted independent owner probe of the S3-P4 originals correction 05.

This probe is the adaptation of the independent probe of the review of the
candidate ``b27b0d17b71371e37002aabc5f69a030872b9177``
(``originals-correction-05/received-review/probe_final.py``) for the one
defect that the review left open:

* **O1 (residual)** - the reference is walked a second time after the
  verified digest, the handle of that second walk is opened without
  following a link and the identity of the object was compared with the
  identity of the first walk only.  The *content state* of the object -
  the size, the change time and the modify time - was not compared, so a
  rewrite of the same length, a rewrite of the same bytes, a growth and a
  truncation inside the re-walk window were accepted and the stale digest
  was published as a verified original.

The probe drives the *production owner* itself - ``ParentOriginalEvidence``
of ``tools/v0_s3_coordinator.py`` - and it uses the same controlled
trigger as the review: a controlled ``os.open`` that changes the artifact
after the kernel opened it and before the descriptor is handed over, so
the change is inside the re-walk window of the production reader.

The oracle of the re-walk cases is a refusal of the owner.  The trigger
has to have fired, the change has to be observable in the state of the
very same object and the published hash has to be the hash of the state
that was actually read.  The probe never accepts an exit code as a
proof.

The probe also re-checks the obligations that the earlier round closed
and that this correction must not reopen: the change during the read
window, the fifo without a write end, the legal case and the fail closed
case of a platform without the safe primitives.

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
BINDING = {'run_id': 'originals-correction-05', 'candidate_sha': 'a' * 40}
BODY = b'ORIGINAL'
FINAL = 'raw.bin'


def refuse(function):
    """The refusal of one owner call, or ``None`` when it was accepted."""
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


def state_of(path):
    """The observable state of one artifact."""
    info = os.lstat(path)
    return {'size': int(info.st_size), 'mtime_ns': int(info.st_mtime_ns),
            'ctime_ns': int(info.st_ctime_ns), 'dev': int(info.st_dev),
            'ino': int(info.st_ino), 'regular': stat.S_ISREG(info.st_mode)}


def controlled_reopen(action):
    """A controlled ``os.open`` that changes the artifact at the re-walk.

    Only the final component of the reference is counted.  Its first
    opening is the verified walk that the digest was taken from, its
    second opening is the re-walk that follows the digest.  The change
    happens after the kernel opened the artifact and before the descriptor
    is handed to the caller, so it is inside the re-walk window of the
    production reader: the ``fstat`` of the returned handle sees it and
    the digest of the first handle can not see it any more.

    The count is kept as the evidence that the procedure does not open
    the artifact a third time.
    """
    real_open = os.open
    state = {'opens': 0, 'fired': False}

    def wrapper(path, flags, *args, **kwargs):
        descriptor = real_open(path, flags, *args, **kwargs)
        if str(path) == FINAL:
            state['opens'] += 1
            if state['opens'] == 2:
                state['fired'] = True
                action()
        return descriptor

    return wrapper, state


def install_reopen(wrapper):
    """Install the controlled opening and keep the platform capability.

    The platform check of the candidate looks at the *identity* of
    ``os.open``, so the controlled opening has to be a member of
    ``os.supports_dir_fd`` as well.  The capability is not widened: the
    real opening of the kernel is the one that is called.
    """
    support = os.supports_dir_fd
    os.supports_dir_fd = set(support) | {wrapper}
    os.open = wrapper


def restore_reopen(real_open, support):
    """Undo the controlled opening of this process."""
    os.open = real_open
    os.supports_dir_fd = support


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


def observe_rewalk(name, root, owner, action, *, seal_first):
    """One controlled change inside the re-walk and the refusal of the owner."""
    if seal_first:
        seal_all(owner)
    target = root / 'temp/raw.bin'
    before = state_of(target)
    real_open = os.open
    support = os.supports_dir_fd
    wrapper, state = controlled_reopen(action)
    install_reopen(wrapper)
    try:
        reason = refuse(owner.manifest if seal_first else lambda: seal_all(owner))
    finally:
        restore_reopen(real_open, support)
    after = state_of(target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    observable = (after['size'] != before['size']
                  or after['mtime_ns'] != before['mtime_ns']
                  or after['ctime_ns'] != before['ctime_ns']
                  or after['ino'] != before['ino'])
    if reason is None or not state['fired'] or not observable:
        raise AssertionError('the owner did not refuse a change of the re-walk: '
                             + name + ' reason=' + str(reason)
                             + ' fired=' + str(state['fired']))
    published = owner.originals.get('raw', [])
    published_hash = published[0]['sha256'] if published else None
    accepted = reason is None
    return {'trigger': name, 'refusal': reason, 'accepted': accepted,
            'trigger_fired': state['fired'],
            'opens_of_the_artifact': state['opens'],
            'state_before': before, 'state_after': after,
            'change_observable_in_the_object': observable,
            'actual_sha256_after_the_trigger': digest,
            'published_sha256': published_hash,
            # a stale hash is only published when the owner *accepted* the
            # call: a refusal leaves the previous seal untouched, which is
            # the whole point of the refusal
            'stale_hash_published': accepted and published_hash is not None
            and published_hash != digest,
            'phase': 'consume' if seal_first else 'seal'}


def controlled_read(target_inode, action, delay=0.02):
    """A controlled ``os.read`` that changes the original exactly once."""
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


def observe_read_window(name, root, owner, action, *, seal_first):
    """One controlled change during the read and the refusal of the owner."""
    if seal_first:
        seal_all(owner)
    target_inode = os.stat(root / 'temp/raw.bin').st_ino
    before = state_of(root / 'temp/raw.bin')
    wrapper, state = controlled_read(target_inode, action)
    real_read = os.read
    os.read = wrapper
    try:
        reason = refuse(owner.manifest if seal_first else lambda: seal_all(owner))
    finally:
        os.read = real_read
    after = state_of(root / 'temp/raw.bin')
    observable = (after['mtime_ns'] != before['mtime_ns']
                  or after['ino'] != before['ino']
                  or not after['regular'])
    if reason is None or not state['fired'] or not observable:
        raise AssertionError('the owner did not refuse a controlled change: '
                             + name + ' reason=' + str(reason))
    return {'trigger': name, 'refusal': reason, 'trigger_fired': state['fired'],
            'change_observable_in_the_object': observable,
            'phase': 'consume' if seal_first else 'seal'}


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


def observe_fifo(name, root, owner, *, seal_first):
    """A real fifo at the place of an original, without a write end."""
    if seal_first:
        seal_all(owner)
    fifo = root / 'temp/raw.bin'
    fifo.unlink()
    os.mkfifo(fifo)
    started = time.monotonic()
    thread, box = bounded(owner.manifest if seal_first else lambda: seal_all(owner))
    blocked = thread.is_alive()
    if blocked:
        # the controlled recovery of a failing probe only: the oracle
        # itself never opens a write end
        release = os.open(fifo, os.O_WRONLY | os.O_NONBLOCK)
        os.close(release)
        thread.join(2.0)
    observation = {'trigger': name, 'blocked_on_the_fifo': blocked,
                   'elapsed_seconds': round(time.monotonic() - started, 3),
                   'thread_settled': not thread.is_alive(),
                   'refusal': getattr(box.get('exception'), 'reason', None),
                   'write_end_opened_by_the_oracle': False,
                   'phase': 'consume' if seal_first else 'seal'}
    fifo.unlink()
    assert not thread.is_alive(), 'the owner blocked on the fifo'
    assert observation['refusal'] is not None, observation
    return observation


def main():
    ROOTS.mkdir(parents=True, exist_ok=True)
    results = {}
    before_descriptors = descriptors()

    # -- O1 (residual): a change of the original inside the re-walk -------
    changes = (
        ('same_length_rewrite', same_length_rewrite),
        ('same_bytes_rewrite', same_bytes_rewrite),
        ('growth', growth),
        ('truncation', truncation),
    )
    rewalk_seal = []
    rewalk_consume = []
    for name, factory in changes:
        root, owner = evidence('rewalk-seal-' + name)
        rewalk_seal.append(observe_rewalk(name, root, owner, factory(root),
                                           seal_first=False))
        root, owner = evidence('rewalk-consume-' + name)
        rewalk_consume.append(observe_rewalk(name, root, owner, factory(root),
                                             seal_first=True))
    results['O1_rewalk_seal'] = rewalk_seal
    results['O1_rewalk_consume'] = rewalk_consume
    for observation in rewalk_seal + rewalk_consume:
        assert observation['opens_of_the_artifact'] == 2, observation
        assert observation['accepted'] is False, observation
        assert observation['stale_hash_published'] is False, observation

    # -- the closed obligations of the read window must not reopen ---------
    read_changes = (
        ('same_length_rewrite', same_length_rewrite),
        ('same_bytes_rewrite', same_bytes_rewrite),
        ('growth', growth),
        ('truncation', truncation),
        ('object_replacement', object_replacement),
    )
    read_seal = []
    read_consume = []
    for name, factory in read_changes:
        root, owner = evidence('read-seal-' + name)
        read_seal.append(observe_read_window(name, root, owner, factory(root),
                                             seal_first=False))
        root, owner = evidence('read-consume-' + name)
        read_consume.append(observe_read_window(name, root, owner, factory(root),
                                               seal_first=True))
    results['O1_read_window_seal'] = read_seal
    results['O1_read_window_consume'] = read_consume

    # -- O2: a fifo at the place of an original ---------------------------
    results['O2_fifo_at_the_seal'] = observe_fifo('fifo', *evidence('fifo-seal'),
                                                   seal_first=False)
    results['O2_fifo_after_the_seal'] = observe_fifo('fifo', *evidence('fifo-consume'),
                                                      seal_first=True)

    # -- the legal case is still legal ------------------------------------
    root, owner = evidence('legal')
    sealed = seal_all(owner)
    manifest = owner.manifest()
    legal = {'sha256': sealed['raw'][0]['sha256'],
             'expected_sha256': hashlib.sha256(BODY).hexdigest(),
             'bytes': sealed['raw'][0]['bytes'],
             'verified': manifest['reverification']['verified'],
             'checked': len(manifest['reverification']['checked']),
             'original_open_primitive': manifest['original_open_primitive'],
             'original_read_boundary': manifest['original_read_boundary']}
    assert sealed['raw'][0]['sha256'] == hashlib.sha256(BODY).hexdigest()
    assert manifest['reverification']['verified'] is True
    results['legal_case'] = legal

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

    # -- the cleanup of the batch -----------------------------------------
    after_descriptors = descriptors()
    results['descriptors'] = {'before': before_descriptors,
                              'after': after_descriptors,
                              'leaked': after_descriptors - before_descriptors}
    assert after_descriptors == before_descriptors, (before_descriptors,
                                                      after_descriptors)
    assert not list(ROOTS.glob('**/*.fifo'))
    results['remaining_fifo'] = False
    results['all_threads_joined'] = True
    results['stage_pass_claim'] = False
    results['product_gate0'] = False
    results['real_execution_performed'] = False
    results['synthetic_only'] = True
    (O / 'owner-observations.json').write_text(
        json.dumps(results, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'rewalk_refusals': [item['refusal']
                                          for item in rewalk_seal + rewalk_consume],
                      'rewalk_stale_hash_published': [item['stale_hash_published']
                                                     for item in
                                                     rewalk_seal + rewalk_consume],
                      'descriptors': results['descriptors']},
                     indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
