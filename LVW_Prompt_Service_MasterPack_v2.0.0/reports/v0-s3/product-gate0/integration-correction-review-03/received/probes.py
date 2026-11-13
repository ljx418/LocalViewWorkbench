"""The independent behaviour probes of the S3-P4 integration correction 03.

This file is the adaptation of the independent probes of the received
review of the correction 02.  Every probe of that review is still here:
the two handoffs, the two publication interleavings, the unfinished scope,
the four drain boundaries, the late overflow, the history deadline and the
aggregation negatives.  The probes that reproduced a defect now assert the
corrected behaviour, and the controlled interleavings are still driven by
``sys.monitoring`` - they are neither deleted nor replaced by a
probabilistic loop.

The probes drive the production owners with real pipes, a fake clock and
synthetic files.  They start no process, open no socket and read no
original.
"""
import dis
import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

from tools import v0_s3_coordinator as c
from tools import v0_s3_supervisor as s

O = Path(__file__).resolve().parent
results = {}


class Handle:
    """A fake child with real pipes and no real process."""

    def __init__(self, stopped=True):
        self.r, self.w = os.pipe()
        self.er, self.ew = os.pipe()
        self.stdout = os.fdopen(self.r, 'rb', buffering=0)
        self.stderr = os.fdopen(self.er, 'rb', buffering=0)
        self.stdin = None
        self.pid = None
        self.status = 0 if stopped else None

    def poll(self):
        return self.status

    def terminate(self):
        self.status = -15

    def kill(self):
        self.status = -9

    def wait(self, timeout=None):
        return self.status

    def release(self):
        for name in ('w', 'ew'):
            handle = getattr(self, name)
            if handle is not None:
                os.close(handle)
                setattr(self, name, None)


def plan():
    return s.SealedPlan([{'ordinal': index, 'asset_id': 'I%02d' % index,
                          'media_kind': 'image'} for index in range(1, 17)])


def parent(handle, root=O, clock=time.monotonic, **kwargs):
    return s.ParentSupervisor(command=['fake-no-process'], run_id='syn1',
                              candidate_sha='a' * 40, authorization_sha256='b' * 64,
                              plan=plan(), root=root, spawner=lambda command: handle,
                              clock=clock, **kwargs)


def wire(event, seq=1, payload=None):
    return (s.canonical_json({'schema': s.PROTOCOL_SCHEMA, 'run_id': 'syn1',
                               'candidate_sha': 'a' * 40,
                               'authorization_sha256': 'b' * 64, 'sequence': seq,
                               'event': event, 'payload': payload or {}}) + '\n').encode()


def wait_bytes(reader, wanted):
    end = time.monotonic() + 2
    while reader.total < wanted and time.monotonic() < end:
        time.sleep(0.001)
    assert reader.total >= wanted


def monitor(code, target, callback):
    sys.monitoring.use_tool_id(5, 'independent-interleaving')
    sys.monitoring.register_callback(5, sys.monitoring.events.INSTRUCTION,
                                     lambda code_object, offset:
                                     callback() if offset == target else None)
    sys.monitoring.set_local_events(5, code, sys.monitoring.events.INSTRUCTION)


def off(code):
    sys.monitoring.set_local_events(5, code, 0)
    sys.monitoring.free_tool_id(5)


def consistent(snapshot, raw):
    """The accounts of one snapshot belong to the same moment."""
    assert snapshot['hashed_bytes'] == snapshot['kept_bytes']
    assert snapshot['total_observed'] >= snapshot['kept_bytes']
    assert snapshot['sha256'] == hashlib.sha256(raw[:snapshot['hashed_bytes']]).hexdigest()
    if snapshot['overflow']:
        assert snapshot['hash_scope'] == 'prefix_within_budget'
    elif snapshot['complete']:
        assert snapshot['hash_scope'] == 'all_observed'
    else:
        assert snapshot['hash_scope'] == 'observed_prefix'


# The two handoffs of the closed correction 02 are kept as they are.
handle = Handle()
supervisor = parent(handle)
reader = s._StreamReader(handle.stdout, s.MAX_STREAM_BYTES)
supervisor.stdout_reader = reader
code = s._StreamReader._retain.__code__
target = next(instruction.offset for instruction in dis.get_instructions(code)
              if instruction.opname == 'CALL')
paused = threading.Event()
release = threading.Event()


def pause():
    paused.set()
    assert release.wait(2)


monitor(code, target, pause)
reader.start()
raw = wire('STARTED')
os.write(handle.w, raw)
assert paused.wait(2)
supervisor._consume_stdout()
count_before = supervisor.state.count
release.set()
handle.release()
reader.join(2)
off(code)
supervisor._consume_stdout()
results['reader_append_handoff'] = {'offset': target, 'before': count_before,
                                    'after': supervisor.state.count,
                                    'raw_bytes': len(reader.raw()),
                                    'expected': len(raw),
                                    'finished': reader.finished.is_set()}
assert supervisor.state.count == 1 and reader.raw() == raw
handle.stdout.close()
handle.stderr.close()

handle = Handle()
supervisor = parent(handle)
reader = s._StreamReader(handle.stdout, s.MAX_STREAM_BYTES)
supervisor.stdout_reader = reader
reader.start()
code = s._StreamReader.take.__code__
instructions = list(dis.get_instructions(code))
index = next(position for position, value in enumerate(instructions)
             if value.opname == 'STORE_FAST' and value.argval == 'end')
target = instructions[index + 1].offset
paused = threading.Event()
release = threading.Event()
monitor(code, target, pause)
worker = threading.Thread(target=supervisor._consume_stdout)
worker.start()
assert paused.wait(2)
os.write(handle.w, raw)
wait_bytes(reader, len(raw))
release.set()
worker.join(2)
off(code)
supervisor._consume_stdout()
handle.release()
reader.join(2)
results['parent_cursor_handoff'] = {'offset': target, 'count': supervisor.state.count,
                                    'cursor': reader._cursor, 'blocks': len(reader._blocks),
                                    'raw_bytes': len(reader.raw())}
assert supervisor.state.count == 1 and reader.raw() == raw
handle.stdout.close()
handle.stderr.close()

# Publication interleaving one: the snapshot is paused after it read the
# published state and the reader publishes the bytes and the end of the
# stream in the meantime.  The returned snapshot is one moment.
handle = Handle()
reader = s._StreamReader(handle.stdout, 100)
reader.start()
code = s._StreamReader.snapshot.__code__
target = next(instruction.offset for instruction in dis.get_instructions(code)
              if instruction.opname == 'STORE_SUBSCR')
paused = threading.Event()
release = threading.Event()
monitor(code, target, pause)
box = {}
worker = threading.Thread(target=lambda: box.update(reader.snapshot()))
worker.start()
assert paused.wait(2)
os.write(handle.w, b'hello')
handle.release()
reader.join(2)
assert reader.finished.is_set()
release.set()
worker.join(2)
off(code)
consistent(box, reader.raw())
results['snapshot_completed_publication'] = {
    'offset': target, 'snapshot': box, 'actual_raw_hex': reader.raw().hex(),
    'actual_total': reader.total,
    'actual_sha256': hashlib.sha256(reader.raw()).hexdigest(),
    'mixed_state': bool(box['complete'] and box['hashed_bytes'] != box['total_observed']),
}
assert box['hashed_bytes'] == box['total_observed']
assert not (box['complete'] and box['hashed_bytes'] != box['total_observed'])
final = reader.snapshot()
assert final['complete'] is True and final['hash_scope'] == 'all_observed'
assert final['sha256'] == hashlib.sha256(b'hello').hexdigest()
handle.stdout.close()
handle.stderr.close()

# Publication interleaving two: the reader is paused after it read the
# bytes and before it publishes them.  A snapshot of that moment is the
# older, complete state and never a mixed one.
handle = Handle()
reader = s._StreamReader(handle.stdout, 100)
code = s._StreamReader.run.__code__
targets = [instruction.offset for instruction in dis.get_instructions(code)
           if instruction.opname == 'LOAD_ATTR' and instruction.argval == '_retain']
assert targets, 'the reader has no publication point'
target = targets[-1]
paused = threading.Event()
release = threading.Event()
monitor(code, target, pause)
reader.start()
os.write(handle.w, b'world')
assert paused.wait(2)
snapshot = reader.snapshot()
release.set()
handle.release()
reader.join(2)
off(code)
consistent(snapshot, reader.raw())
results['snapshot_before_total_publication'] = {
    'offset': target, 'snapshot': snapshot, 'final_snapshot': reader.snapshot(),
    'mixed_state': bool(snapshot['hashed_bytes'] == 5 and snapshot['total_observed'] == 0),
}
assert not (snapshot['hashed_bytes'] == 5 and snapshot['total_observed'] == 0)
assert snapshot['hashed_bytes'] == snapshot['total_observed']
final = reader.snapshot()
assert final['total_observed'] == 5 and final['complete'] is True
handle.stdout.close()
handle.stderr.close()

# An unfinished stream is only the observed prefix, also when it is empty
# and also when the hashed bytes and the observed bytes are equal.
handle = Handle()
reader = s._StreamReader(handle.stdout, 100)
reader.start()
empty = reader.snapshot()
results['unfinished_scope'] = {'empty': empty}
assert not reader.finished.is_set()
assert empty['hash_scope'] == 'observed_prefix' and empty['complete'] is False
os.write(handle.w, b'later')
wait_bytes(reader, 5)
partial = reader.snapshot()
results['unfinished_scope']['partial'] = partial
assert partial['hash_scope'] == 'observed_prefix' and partial['complete'] is False
consistent(partial, reader.raw())
handle.release()
reader.join(2)
handle.stdout.close()
handle.stderr.close()

# The four drain boundaries and the late overflow of the closed correction 02
# are kept as they are.
for name, phase, child in (('phase_clip', 0.03, 1), ('child_clip', 1, 0.04),
                           ('shared', 2, 2), ('zero_remaining', 0.01, 0.01)):
    root = O / name
    root.mkdir(exist_ok=True)
    canonical = b'{"rows":[]}'
    (root / 'canonical.json').write_bytes(canonical)
    handle = Handle()
    supervisor = parent(handle, root, phase_timeout=phase, child_timeout=child)
    supervisor.start()
    terminal = wire('TERMINAL', payload={'canonical_receipt': {
        'reference': 'canonical.json', 'bytes': len(canonical),
        'sha256': hashlib.sha256(canonical).hexdigest()}})
    os.write(handle.w, terminal)
    wait_bytes(supervisor.stdout_reader, len(terminal))
    if name == 'zero_remaining':
        time.sleep(0.02)
    begin = time.monotonic()
    evidence = supervisor.run()
    elapsed = time.monotonic() - begin
    assert evidence['canonical_receipt_verified']
    assert not evidence['archive_allowed'] and evidence['root_retained']
    assert evidence['unknown_outcome']
    assert not evidence['stdout_drain_complete'] and not evidence['stderr_drain_complete']
    assert elapsed < 0.6
    if name == 'shared':
        writer = threading.Thread(
            target=lambda: os.write(handle.ew, b'x' * (s.MAX_STREAM_BYTES + 1)))
        writer.start()
        supervisor.stderr_reader.join(2)
        writer.join(2)
        assert supervisor.stderr_reader.overflow
        results['late_overflow'] = {'failure': supervisor._stream_failure(),
                                     'returned_archive_allowed': evidence['archive_allowed'],
                                     'returned_hash_scope': evidence['stderr_hash_scope']}
    handle.release()
    supervisor.stdout_reader.join(2)
    supervisor.stderr_reader.join(2)
    handle.stdout.close()
    handle.stderr.close()
    results[name] = {'elapsed': elapsed, 'drain_deadline': supervisor._drain_deadline_value,
                     'phase_deadline': supervisor.effective_phase_deadline,
                     'child_deadline': supervisor.child_deadline, 'evidence': evidence,
                     'settled': not supervisor.stdout_reader.is_alive()
                     and not supervisor.stderr_reader.is_alive()}

# The history deadline of a finished row does not interrupt the later rows.
class Clock:
    now = 0

    def __call__(self):
        return self.now


clock = Clock()
handle = Handle(False)
root = O / 'history'
root.mkdir(exist_ok=True)
canonical = b'{"rows":[]}'
(root / 'canonical.json').write_bytes(canonical)
supervisor = parent(handle, root, clock=clock, phase_timeout=1000, child_timeout=2000)
supervisor.start()
sequence = 0


def event(name, asset, ordinal):
    global sequence
    sequence += 1
    raw = wire(name, sequence, {'asset_id': asset, 'ordinal': ordinal})
    os.write(handle.w, raw)
    end = time.monotonic() + 2
    while supervisor.state.last_sequence < sequence and time.monotonic() < end:
        supervisor._consume_stdout()
        time.sleep(0.001)
    assert supervisor.state.last_sequence == sequence


for name in ('ROW_STARTED', 'HISTORY_WAIT_STARTED'):
    event(name, 'I01', 1)
clock.now = 10
event('ROW_FINISHED', 'I01', 1)
clock.now = 500
for name in ('ROW_STARTED', 'HISTORY_WAIT_STARTED'):
    event(name, 'I02', 2)
clock.now = 601
state_at_601 = supervisor._deadline_state()
terminal = wire('TERMINAL', sequence + 1, payload={'canonical_receipt': {
    'reference': 'canonical.json', 'bytes': len(canonical),
    'sha256': hashlib.sha256(canonical).hexdigest()}})
before = supervisor.stdout_reader.total
os.write(handle.w, terminal)
wait_bytes(supervisor.stdout_reader, before + len(terminal))
handle.release()
handle.status = 0
supervisor.stdout_reader.join(2)
supervisor.stderr_reader.join(2)
evidence = supervisor.run()
results['history_completed_row_expiry'] = {
    'now': 601, 'state_at_601': state_at_601,
    'history_deadlines': supervisor.history_deadlines,
    'history_records': supervisor.history_records,
    'history_completed': sorted(supervisor.history_completed),
    'events': supervisor.messages, 'evidence': evidence}
assert state_at_601 is None
assert supervisor.history_deadlines['I02'] == 1000
assert supervisor.history_deadlines['I01'] == 600
assert supervisor.history_completed == {'I01'}
assert evidence['protocol_violation'] is None
assert evidence['canonical_receipt_verified'] is True
assert evidence['history_completed_rows'] == ['I01']

# The old nine keys and a missing independent score stay non green.
old = c.aggregate_twelve_keys(receipts={'old_s2': {'status': 'PASS', 'passed': 9}},
                              binding={'run_id': 'syn1', 'candidate_sha': 'a' * 40})
required = {name for names in c.TWELVE_REQUIREMENTS.values() for name in names}
receipts = {name: {'kind': c.AGGREGATE_RECEIPT_KIND, 'status': 'PASS', 'run_id': 'syn1',
                   'candidate_sha': 'a' * 40, 'stage_pass_claim': False,
                   'real_isolation': True, 'independent': True, 'cleanup_proven': True}
            for name in required}
# the same receipts without the cleanup receipt of the run
without_cleanup_receipts = {name: value for name, value in receipts.items()
                            if name != 'cleanup'}
without_cleanup = c.aggregate_twelve_keys(receipts=without_cleanup_receipts,
                                           binding={'run_id': 'syn1',
                                                    'candidate_sha': 'a' * 40})
receipts.pop('independent_score', None)
missing = c.aggregate_twelve_keys(receipts=receipts,
                                   binding={'run_id': 'syn1', 'candidate_sha': 'a' * 40})
results['aggregator_negative'] = {'old_nine': old, 'without_cleanup': without_cleanup,
                                   'missing_independent': missing}
assert old['pass_count'] == 0
assert without_cleanup['pass_count'] == 0 and without_cleanup['not_run_count'] == 12
assert missing['keys']['V0-A11']['status'] != 'PASS'
assert missing['keys']['V0-A12']['status'] != 'PASS'

(O / 'observations.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
assert len(threading.enumerate()) == 1
