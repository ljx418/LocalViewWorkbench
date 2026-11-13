#!/usr/bin/env python3
"""The wire numbers of the message count negative case.

The probe is a zero process probe: it imports the fixture entry as a module
- the fixture never registers its boundary guard outside of its ``__main__``
entry - and it computes the wire of the negative case with the real writer
and the real scenario function of the fixture and with the real constants of
the product.  It starts no process, opens no socket and touches no ledger.

The values are computed, not estimated: the numbers below are the real
lengths of the real bytes.
"""
import importlib.util
import json
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
FIXTURE_PATH = PACK_ROOT / 'tools/fixtures/v0_s3_supervisor_fixture.py'
SUPERVISOR_PATH = PACK_ROOT / 'tools/v0_s3_supervisor.py'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


supervisor = load('lvw_s3_supervisor_probe', SUPERVISOR_PATH)
fixture = load('lvw_s3_supervisor_fixture_probe', FIXTURE_PATH)

ROWS = [{'ordinal': index + 1, 'asset_id': 'SYN-%02d' % (index + 1),
         'media_kind': 'image'} for index in range(16)]


def values(run_id):
    return {'run_id': run_id, 'candidate_sha': 'a' * 40,
            'authorization_sha256': 'b' * 64,
            'root': '/tmp/pytest-of-root/pytest-1/test_message_count0/run',
            'terminal_reference': 'temp/s3-quality/qd-receipt.json', 'plan': ROWS}


def wire(run_id):
    frames = fixture.flood_wire(values(run_id), ROWS)
    return {
        'run_id': run_id,
        'run_id_length': len(run_id),
        'frames': len(frames),
        'total_bytes': sum(len(frame) for frame in frames),
        'longest_frame_bytes': max(len(frame) for frame in frames),
        'shortest_frame_bytes': min(len(frame) for frame in frames),
    }


report = {
    'kind': 'lvw.s3-stream-correction-wire-probe/1',
    'caps': {
        'max_messages': supervisor.MAX_MESSAGES,
        'max_message_bytes': supervisor.MAX_MESSAGE_BYTES,
        'max_stream_bytes': supervisor.MAX_STREAM_BYTES,
    },
    'flood_wire': wire('syn1'),
    'flood_wire_long_identity': wire('synthetic-quality-run'),
    'old_flood_wire': {
        'messages': 1200,
        'note': 'the previous scenario wrote 1200 progress messages; the byte '
                'budget of the stream was reached before the count of the '
                'messages was reached',
    },
    'fixture_guard_installed_in_this_process': fixture.BOUNDARY_GUARD_INSTALLED,
}
report['flood_wire']['inside_message_cap'] = (
    report['flood_wire']['frames'] == supervisor.MAX_MESSAGES + 1)
report['flood_wire']['inside_byte_caps'] = (
    report['flood_wire']['total_bytes'] <= supervisor.MAX_STREAM_BYTES
    and report['flood_wire']['longest_frame_bytes'] <= supervisor.MAX_MESSAGE_BYTES)
report['flood_wire_long_identity']['inside_byte_caps'] = (
    report['flood_wire_long_identity']['total_bytes'] <= supervisor.MAX_STREAM_BYTES)

sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + '\n')
