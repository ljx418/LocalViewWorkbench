#!/usr/bin/env python3
"""The baseline proof of the second correction of the streams.

The probe loads the *baseline* supervisor of the candidate 626d37c from a
directory that the shell extracted with ``git show`` and it runs the two
controlled interleavings of the independent review twice: once against the
baseline and once against the candidate of this round.

The first interleaving is the handoff of a frame from the reader to the
parent.  The reader is paused inside the handoff with ``sys.monitoring`` and
the parent takes the pending bytes in that very moment, so the frame that is
in flight is the frame that a swap of the buffer would orphan.

The second interleaving is the final drain.  The handle of the child is gone
but the pipes of the child are still held open, so the end of the streams is
not proven: the exit of the handle says nothing about the end of a stream.

The probe starts no process, opens no socket, touches no ledger and calls no
model.  It exits with 1 when the candidate still shows one of the two
defects, so the probe is a gate and not only a report.

The argument is the directory that holds the baseline ``tools`` package.
"""
import dis
import hashlib
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

BASELINE = Path(sys.argv[1]).resolve()
PACK_ROOT = Path(__file__).resolve().parents[4]
CANDIDATE = PACK_ROOT / 'tools/v0_s3_supervisor.py'
BASELINE_COMMIT = '626d37cf59bfc69324c1a9f886a65cd3f8c56964'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


baseline = load('lvw_s3_baseline_supervisor',
                BASELINE / 'tools/v0_s3_supervisor.py')
candidate = load('lvw_s3_candidate_supervisor', CANDIDATE)

RUN_ID = 'syn1'
CANDIDATE_SHA = 'a' * 40
AUTHORIZATION_SHA = 'b' * 64


def plan_of(module):
    return module.SealedPlan([{'ordinal': ordinal, 'asset_id': 'I%02d' % ordinal,
                               'media_kind': 'image'} for ordinal in range(1, 17)])


def frame_of(module):
    """One real canonical frame of the protocol of the module."""
    return module.canonical_json({
        'schema': module.PROTOCOL_SCHEMA, 'run_id': RUN_ID,
        'candidate_sha': CANDIDATE_SHA, 'authorization_sha256': AUTHORIZATION_SHA,
        'sequence': 1, 'event': 'STARTED', 'payload': {}}).encode() + b'\n'


# --------------------------------------------------------- the handoff of a frame
def handoff_interleaving(module, label):
    """The controlled interleaving of the handoff of one frame.

    The reader is paused at the first call of its handoff, the parent takes
    the pending bytes in that very moment and the reader continues
    afterwards.  The frame has to reach the protocol state of the parent.
    """
    reader_fd, writer_fd = os.pipe()
    stream = os.fdopen(reader_fd, 'rb', buffering=0)
    reader = module._StreamReader(stream, module.MAX_STREAM_BYTES)
    code = module._StreamReader._retain.__code__
    target = next(instruction.offset for instruction in dis.get_instructions(code)
                  if instruction.opname == 'CALL')
    paused = threading.Event()
    release = threading.Event()

    def instruction(code_object, offset):
        if offset == target:
            paused.set()
            release.wait(5)

    sys.monitoring.use_tool_id(5, 'lvw-s3-' + label)
    sys.monitoring.register_callback(5, sys.monitoring.events.INSTRUCTION, instruction)
    sys.monitoring.set_local_events(5, code, sys.monitoring.events.INSTRUCTION)
    try:
        worker = threading.Thread(target=reader.run, daemon=True)
        worker.start()
        raw = frame_of(module)
        os.write(writer_fd, raw)
        is_paused = paused.wait(5)
        parent = module.ParentSupervisor(command=['fake-no-process'], run_id=RUN_ID,
                                         candidate_sha=CANDIDATE_SHA,
                                         authorization_sha256=AUTHORIZATION_SHA,
                                         plan=plan_of(module), root=BASELINE)
        parent.stdout_reader = reader
        # the parent takes the pending bytes while the reader is in the
        # middle of the handoff
        parent._consume_stdout()
        release.set()
        worker.join(5)
        # the frame has to reach the protocol state of the parent
        parent._consume_stdout()
        observation = {
            'label': label,
            'paused': is_paused,
            'target_offset': target,
            'parent_message_count': parent.state.count,
            'expected_message_count': 1,
            'reader_total': reader.total,
            'reader_raw_bytes': len(reader.raw()),
            'reader_error': reader.error,
            'reader_finished': reader.finished.is_set(),
            'frame_bytes': len(raw),
            'frame_lost': parent.state.count != 1,
        }
    finally:
        sys.monitoring.set_local_events(5, code, 0)
        sys.monitoring.free_tool_id(5)
        release.set()
        try:
            os.close(writer_fd)
        except OSError:  # noqa: BLE001 - the pipe may be closed
            pass
        stream.close()
    return observation


def review_handoff_probe(module, label):
    """The probe of the independent review, byte for byte.

    The review took the pending bytes twice itself and wired the parent
    afterwards.  The probe is kept here so that the difference between the
    two wirings is visible and is not a guess.
    """
    reader_fd, writer_fd = os.pipe()
    stream = os.fdopen(reader_fd, 'rb', buffering=0)
    reader = module._StreamReader(stream, module.MAX_STREAM_BYTES)
    code = module._StreamReader._retain.__code__
    target = next(instruction.offset for instruction in dis.get_instructions(code)
                  if instruction.opname == 'CALL')
    paused = threading.Event()
    release = threading.Event()

    def instruction(code_object, offset):
        if offset == target:
            paused.set()
            release.wait(5)

    sys.monitoring.use_tool_id(5, 'lvw-s3-review-' + label)
    sys.monitoring.register_callback(5, sys.monitoring.events.INSTRUCTION, instruction)
    sys.monitoring.set_local_events(5, code, sys.monitoring.events.INSTRUCTION)
    try:
        worker = threading.Thread(target=reader.run, daemon=True)
        worker.start()
        raw = frame_of(module)
        os.write(writer_fd, raw)
        is_paused = paused.wait(5)
        first = reader.take()
        release.set()
        os.close(writer_fd)
        worker.join(5)
        second = reader.take()
        parent = module.ParentSupervisor(command=['fake-no-process'], run_id=RUN_ID,
                                         candidate_sha=CANDIDATE_SHA,
                                         authorization_sha256=AUTHORIZATION_SHA,
                                         plan=plan_of(module), root=BASELINE)
        parent.stdout_reader = reader
        parent._consume_stdout()
        observation = {
            'label': label,
            'paused': is_paused,
            'target_offset': target,
            'first_take_bytes': len(first),
            'second_take_bytes': len(second),
            'parent_message_count': parent.state.count,
            'reader_total': reader.total,
            'reader_raw_bytes': len(reader.raw()),
            'reader_finished': reader.finished.is_set(),
            'note': 'the probe itself takes the pending bytes twice before it '
                    'wires the parent, so the parent sees only what is left',
        }
    finally:
        sys.monitoring.set_local_events(5, code, 0)
        sys.monitoring.free_tool_id(5)
        release.set()
        try:
            os.close(writer_fd)
        except OSError:  # noqa: BLE001 - the pipe may be closed
            pass
        stream.close()
    return observation


# ------------------------------------------------------------- the final drain
class HeldPipeHandle:
    """A fake child that is gone but whose pipes are still held open."""

    def __init__(self):
        self.r, self.w = os.pipe()
        self.er, self.ew = os.pipe()
        self.stdout = os.fdopen(self.r, 'rb', buffering=0)
        self.stderr = os.fdopen(self.er, 'rb', buffering=0)
        self.pid = None
        self.stdin = None

    def poll(self):
        return 0

    def terminate(self):
        raise AssertionError('a child that is gone must not be terminated')

    def kill(self):
        raise AssertionError('no other handle may be killed')

    def release(self):
        for descriptor in (self.w, self.ew):
            try:
                os.close(descriptor)
            except OSError:  # noqa: BLE001 - the pipe may be closed
                pass


def drain_interleaving(module, label, root):
    """The final drain of a worker whose streams never end."""
    handle = HeldPipeHandle()
    supervisor = module.ParentSupervisor(command=['fake-no-process'], run_id=RUN_ID,
                                         candidate_sha=CANDIDATE_SHA,
                                         authorization_sha256=AUTHORIZATION_SHA,
                                         plan=plan_of(module), root=root,
                                         phase_timeout=0.03, child_timeout=0.04)
    supervisor.spawner = lambda command: handle
    payload = b'{"rows": []}'
    (root / 'canonical.json').write_bytes(payload)
    terminal = module.canonical_json({
        'schema': module.PROTOCOL_SCHEMA, 'run_id': RUN_ID,
        'candidate_sha': CANDIDATE_SHA, 'authorization_sha256': AUTHORIZATION_SHA,
        'sequence': 1, 'event': 'TERMINAL',
        'payload': {'canonical_receipt': {
            'reference': 'canonical.json', 'bytes': len(payload),
            'sha256': hashlib.sha256(payload).hexdigest()}}}).encode() + b'\n'
    supervisor.start()
    os.write(handle.w, terminal)
    end = time.monotonic() + 5.0
    while supervisor.stdout_reader.total < len(terminal) and time.monotonic() < end:
        time.sleep(0.001)
    start = time.monotonic()
    try:
        evidence = supervisor.run()
        elapsed = time.monotonic() - start
    finally:
        handle.release()
    observation = {
        'label': label,
        'elapsed_seconds': elapsed,
        'terminal_received': evidence['terminal_received'],
        'canonical_receipt_verified': evidence['canonical_receipt_verified'],
        'archive_allowed': evidence['archive_allowed'],
        'next_phase_allowed': evidence['next_phase_allowed'],
        'root_retained': evidence['root_retained'],
        'unknown_outcome': evidence['unknown_outcome'],
        'protocol_violation': evidence['protocol_violation'],
        'drain_violation': evidence.get('drain_violation'),
        'stdout_drain_complete': evidence.get('stdout_drain_complete'),
        'stderr_drain_complete': evidence.get('stderr_drain_complete'),
        'cleanup_proven_stopped': evidence['cleanup']['proven_stopped'],
        'defect_reproduced': bool(evidence['archive_allowed']),
    }
    return observation


def trailing_partial(module, label, root):
    """A stream that ends in the middle of a frame after the terminal."""
    payload = b'{"rows": []}'
    (root / 'canonical.json').write_bytes(payload)
    terminal = module.canonical_json({
        'schema': module.PROTOCOL_SCHEMA, 'run_id': RUN_ID,
        'candidate_sha': CANDIDATE_SHA, 'authorization_sha256': AUTHORIZATION_SHA,
        'sequence': 1, 'event': 'TERMINAL',
        'payload': {'canonical_receipt': {
            'reference': 'canonical.json', 'bytes': len(payload),
            'sha256': hashlib.sha256(payload).hexdigest()}}}).encode() + b'\n'
    reader_fd, writer_fd = os.pipe()
    error_fd, error_writer_fd = os.pipe()
    stdout = os.fdopen(reader_fd, 'rb', buffering=0)
    stderr = os.fdopen(error_fd, 'rb', buffering=0)

    class Handle:
        pid = None
        stdin = None

        def poll(self):
            return 0

        def terminate(self):
            raise AssertionError('a child that is gone must not be terminated')

        def kill(self):
            raise AssertionError('no other handle may be killed')

    handle = Handle()
    handle.stdout = stdout
    handle.stderr = stderr
    supervisor = module.ParentSupervisor(command=['fake-no-process'], run_id=RUN_ID,
                                         candidate_sha=CANDIDATE_SHA,
                                         authorization_sha256=AUTHORIZATION_SHA,
                                         plan=plan_of(module), root=root)
    supervisor.spawner = lambda command: handle
    supervisor.start()
    os.write(writer_fd, terminal + b'{"schema":"lvw.s3')
    os.close(writer_fd)
    os.close(error_writer_fd)
    evidence = supervisor.run()
    stdout.close()
    stderr.close()
    return {
        'label': label,
        'terminal_received': evidence['terminal_received'],
        'canonical_receipt_verified': evidence['canonical_receipt_verified'],
        'archive_allowed': evidence['archive_allowed'],
        'protocol_violation': evidence['protocol_violation'],
        'incomplete_frame': evidence.get('incomplete_frame'),
        'defect_reproduced': bool(evidence['archive_allowed']),
    }


def main():
    baseline_root = BASELINE / 'baseline-root'
    candidate_root = BASELINE / 'candidate-root'
    for root in (baseline_root, candidate_root):
        root.mkdir(parents=True, exist_ok=True)
    report = {
        'kind': 'lvw.s3-stream-correction-02-baseline-probe/1',
        'baseline_commit': BASELINE_COMMIT,
        'baseline_source': str(baseline.__file__),
        'candidate_source': str(candidate.__file__),
        'handoff': {
            'baseline': handoff_interleaving(baseline, 'baseline'),
            'candidate': handoff_interleaving(candidate, 'candidate'),
        },
        'review_probe': {
            'baseline': review_handoff_probe(baseline, 'baseline'),
            'candidate': review_handoff_probe(candidate, 'candidate'),
        },
        'drain': {
            'baseline': drain_interleaving(baseline, 'baseline', baseline_root),
            'candidate': drain_interleaving(candidate, 'candidate', candidate_root),
        },
        'trailing_partial': {
            'baseline': trailing_partial(baseline, 'baseline', baseline_root),
            'candidate': trailing_partial(candidate, 'candidate', candidate_root),
        },
    }
    report['summary'] = {
        'baseline_frame_lost': report['handoff']['baseline']['frame_lost'],
        'candidate_frame_lost': report['handoff']['candidate']['frame_lost'],
        'baseline_drain_defect': report['drain']['baseline']['defect_reproduced'],
        'candidate_drain_defect': report['drain']['candidate']['defect_reproduced'],
        'baseline_trailing_defect': report['trailing_partial']['baseline']['defect_reproduced'],
        'candidate_trailing_defect': report['trailing_partial']['candidate']['defect_reproduced'],
    }
    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
    sys.stdout.flush()
    failures = []
    if not report['summary']['baseline_frame_lost']:
        failures.append('the baseline did not lose the frame, the probe is not valid')
    if report['summary']['candidate_frame_lost']:
        failures.append('the candidate still loses the frame')
    if not report['summary']['baseline_drain_defect']:
        failures.append('the baseline did not archive an unproven drain')
    if report['summary']['candidate_drain_defect']:
        failures.append('the candidate still archives an unproven drain')
    if not report['summary']['baseline_trailing_defect']:
        failures.append('the baseline did not archive a trailing partial frame')
    if report['summary']['candidate_trailing_defect']:
        failures.append('the candidate still archives a trailing partial frame')
    if failures:
        sys.stderr.write('\n'.join(failures) + '\n')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
