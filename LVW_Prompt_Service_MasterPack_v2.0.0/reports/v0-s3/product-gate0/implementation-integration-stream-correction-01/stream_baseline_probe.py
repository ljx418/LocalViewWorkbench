#!/usr/bin/env python3
"""The baseline proof of the stream correction.

The probe loads the *baseline* sources of the candidate 01453ee from a
directory that the shell extracted with ``git show`` and it measures the two
refusals that the finite fixture run reported.  It starts no process, opens
no socket and touches no ledger.  The two scenarios of the baseline block
forever by design, so they run in a daemon thread and the probe reads the
bytes that they wrote.

The argument is the directory that holds the baseline ``tools`` package.
"""
import importlib.util
import io
import json
import sys
import threading
from pathlib import Path

BASELINE = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(BASELINE))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fixture = load('lvw_s3_baseline_fixture',
               BASELINE / 'tools/fixtures/v0_s3_supervisor_fixture.py')
supervisor = load('lvw_s3_baseline_supervisor',
                  BASELINE / 'tools/v0_s3_supervisor.py')


class CapturedStdout:
    def __init__(self):
        self.buffer = io.BytesIO()

    def flush(self):
        return None

    def write(self, text):
        return self.buffer.write(text.encode('utf-8'))


VALUES = {'run_id': 'synthetic-quality-run', 'candidate_sha': 'a' * 40,
          'authorization_sha256': 'b' * 64,
          'root': '/tmp/pytest-of-root/pytest-1/test_message_count0/run',
          'terminal_reference': 'temp/s3-quality/qd-receipt.json', 'plan': []}
ROWS = []


def scenario_wire(scenario):
    """The wire that the baseline scenario wrote, in a bounded thread."""
    captured = CapturedStdout()
    original = sys.stdout
    sys.stdout = captured
    try:
        writer = fixture.Writer(VALUES)
        handler = fixture.SCENARIO_FUNCTIONS[scenario]
        thread = threading.Thread(target=handler, args=(writer, VALUES, ROWS),
                                  daemon=True)
        thread.start()
        thread.join(timeout=2.0)
    finally:
        sys.stdout = original
    return captured.buffer.getvalue()


nonfinite = scenario_wire('nonfinite_number')
flood = scenario_wire('message_flood')
flood_frames = [line for line in flood.split(b'\n') if line]

report = {
    'kind': 'lvw.s3-stream-correction-baseline-probe/1',
    'baseline': '01453ee07b4774a55711c5cf5642c12d0394a35c',
    'nonfinite_number': {
        'bytes': len(nonfinite),
        'ends_with_newline': nonfinite.endswith(b'\n'),
        'complete_jsonl_frame': nonfinite.endswith(b'\n'),
        'note': 'the baseline wrote the NaN line without its frame end, so '
                'the parent never decoded it and the refusal fell back to '
                'the phase deadline',
    },
    'message_flood': {
        'frames': len(flood_frames),
        'total_bytes': len(flood),
        'stream_byte_cap': supervisor.MAX_STREAM_BYTES,
        'inside_stream_byte_cap': len(flood) <= supervisor.MAX_STREAM_BYTES,
        'note': 'the baseline wrote more messages than the cap allows; the '
                'byte budget of the stream was reached before the count of '
                'the messages was reached',
    },
    'supervisor': {
        'has_stream_failure_detection': hasattr(supervisor.ParentSupervisor,
                                                '_stream_failure'),
        'stable_codes': sorted(
            name for name in dir(supervisor)
            if name.endswith(('STREAM_LIMIT_EXCEEDED', 'STREAM_READ_FAILED'))),
        'max_messages': supervisor.MAX_MESSAGES,
        'max_stream_bytes': supervisor.MAX_STREAM_BYTES,
    },
}
sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
