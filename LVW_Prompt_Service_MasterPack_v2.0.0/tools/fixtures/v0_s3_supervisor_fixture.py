#!/usr/bin/env python3
"""The enumerated supervisor fixture of the S3 parent supervision.

This entry is a *synthetic worker* for the bounded offline scenarios of the
parent supervision.  It is not a general execution platform: the scenario is
one member of a closed enumeration, the arguments are a closed set and the
entry never runs a shell, a native executable or a service.

The entry installs its own zero network and zero descendant process guard
*before* it imports anything, so neither this file nor any module that it
imports afterwards can open a socket, resolve a name or start a process.

Every scenario writes the supervision protocol on its standard output and
then stops.  The scenarios exist to show how the *parent* reacts; they never
prove a product behaviour, a native Windows release or a quality result.
"""
import json
import os
import sys
import time

PACK_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PACK_ROOT not in sys.path:
    sys.path.insert(0, PACK_ROOT)


class FixtureBoundaryViolation(RuntimeError):
    """Raised when the fixture boundary would be crossed."""


BLOCKED_EVENTS = (
    'socket.connect',
    'socket.connect_ex',
    'socket.bind',
    'socket.getaddrinfo',
    'socket.gethostbyname',
    'socket.gethostbyaddr',
    'socket.getnameinfo',
    'subprocess.Popen',
    'os.system',
    'os.exec',
    'os.spawn',
    'os.posix_spawn',
    'os.fork',
    'os.forkpty',
)


def _audit_hook(event, arguments):
    if event in BLOCKED_EVENTS:
        raise FixtureBoundaryViolation('fixture boundary violation: ' + event)


# The guard is installed before every import of this entry.
sys.addaudithook(_audit_hook)

from tools.v0_s3_supervisor import MESSAGE_KEYS, PROTOCOL_SCHEMA  # noqa: E402

SCENARIOS = (
    'clean_terminal',
    'blocking_callback',
    'blocking_persistence',
    'history_replay',
    'sequence_reversal',
    'duplicate_sequence',
    'oversize_message',
    'foreign_identity',
    'unexpected_field',
    'nonfinite_number',
    'early_exit',
    'message_flood',
    'bad_terminal_reference',
)

# The environment variable of the machine binding that names the context
# document of the scenario.
CONTEXT_ENVIRONMENT_VARIABLE = 'LVW_S3_FIXTURE_CONTEXT'


def parse_arguments(argv):
    """The only argument of this entry is the enumerated scenario.

    The identity, the plan and the bound root of a scenario come from one
    context document whose path is named by the environment variable of the
    machine binding.  The argument vector therefore stays exactly the frozen
    prefix plus one enumerated scenario.
    """
    values = {'scenario': None, 'run_id': 'fixture-run', 'candidate_sha': 'a' * 40,
              'authorization_sha256': 'b' * 64, 'plan': None, 'root': None,
              'terminal_reference': 'temp/s3-quality/qd-receipt.json'}
    index = 0
    while index < len(argv):
        key = argv[index]
        if key != '--scenario':
            raise SystemExit('FIXTURE_ARGUMENT_UNKNOWN')
        if index + 1 >= len(argv):
            raise SystemExit('FIXTURE_ARGUMENT_MISSING_VALUE')
        values['scenario'] = argv[index + 1]
        index += 2
    if values['scenario'] not in SCENARIOS:
        raise SystemExit('FIXTURE_SCENARIO_UNKNOWN')
    context_path = os.environ.get(CONTEXT_ENVIRONMENT_VARIABLE)
    if context_path:
        with open(context_path, 'rb') as stream:
            context = json.loads(stream.read().decode('utf-8'))
        if not isinstance(context, dict):
            raise SystemExit('FIXTURE_CONTEXT_INVALID')
        for key in ('run_id', 'candidate_sha', 'authorization_sha256', 'root',
                    'terminal_reference'):
            if key in context:
                values[key] = context[key]
        if isinstance(context.get('plan'), list):
            values['plan'] = context['plan']
    return values


class Writer:
    """The protocol writer of the fixture."""

    def __init__(self, values):
        self.values = values
        self.sequence = 0

    def message(self, event, payload, *, sequence=None, identity=None):
        if sequence is None:
            self.sequence += 1
            sequence = self.sequence
        else:
            self.sequence = max(self.sequence, sequence)
        run_id, candidate, authorization = identity or (
            self.values['run_id'], self.values['candidate_sha'],
            self.values['authorization_sha256'])
        return {'schema': PROTOCOL_SCHEMA, 'run_id': run_id, 'candidate_sha': candidate,
                'authorization_sha256': authorization, 'sequence': sequence,
                'event': event, 'payload': payload}

    def write(self, message):
        raw = json.dumps(message, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':')).encode('utf-8')
        sys.stdout.buffer.write(raw + b'\n')
        sys.stdout.buffer.flush()

    def write_raw(self, raw):
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()


def load_plan(rows):
    if not rows:
        return []
    if not isinstance(rows, list):
        raise SystemExit('FIXTURE_PLAN_INVALID')
    for row in rows:
        if (not isinstance(row, dict) or not isinstance(row.get('asset_id'), str)
                or not isinstance(row.get('ordinal'), int)):
            raise SystemExit('FIXTURE_PLAN_INVALID')
    return rows


def terminal_reference(values):
    """The real length and hash of the canonical receipt of the bound root."""
    reference = values['terminal_reference']
    root = values['root']
    if not root:
        return {'reference': reference, 'bytes': 1, 'sha256': '0' * 64}
    path = os.path.join(root, reference)
    with open(path, 'rb') as stream:
        raw = stream.read()
    import hashlib
    return {'reference': reference, 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def scenario_clean_terminal(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    for row in rows:
        payload = {'asset_id': row['asset_id'], 'ordinal': row['ordinal']}
        writer.write(writer.message('ROW_STARTED', dict(payload)))
        writer.write(writer.message('HISTORY_WAIT_STARTED', dict(payload)))
        writer.write(writer.message('ROW_FINISHED', dict(payload,
                                                          execution_status='PASS',
                                                          quality_status='PASS')))
    writer.write(writer.message('PROGRESS', {'rows_finished': len(rows),
                                              'rows_total': len(rows)}))
    writer.write(writer.message('TERMINAL',
                                {'canonical_receipt': terminal_reference(values),
                                 'decision': 'FIXTURE_TERMINAL'}))


def scenario_blocking_callback(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    # The scenario blocks exactly like a callback that never returns.  The
    # parent has to stop the process that it holds; it cannot accept a
    # timeout text instead.
    while True:
        time.sleep(3600)


def scenario_blocking_persistence(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    # A partial line: the message is never terminated, so the protocol is
    # unresolved and the parent has to stop the held process.
    writer.write_raw(b'{"schema":"' + PROTOCOL_SCHEMA.encode('utf-8') + b'","run_id":"')
    while True:
        time.sleep(3600)


def scenario_history_replay(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    if rows:
        payload = {'asset_id': rows[0]['asset_id'], 'ordinal': rows[0]['ordinal']}
        writer.write(writer.message('HISTORY_WAIT_STARTED', dict(payload)))
        writer.write(writer.message('HISTORY_WAIT_STARTED', dict(payload)))
    while True:
        time.sleep(3600)


def scenario_sequence_reversal(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}, sequence=2))
    writer.write(writer.message('PROGRESS', {'rows_finished': 0, 'rows_total': len(rows)},
                                sequence=1))
    while True:
        time.sleep(3600)


def scenario_duplicate_sequence(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}, sequence=1))
    writer.write(writer.message('PROGRESS', {'rows_finished': 0, 'rows_total': len(rows)},
                                sequence=1))
    while True:
        time.sleep(3600)


def scenario_oversize_message(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    payload = {'rows_total': len(rows), 'filler': 'x' * 40000}
    writer.write(writer.message('PROGRESS', payload))
    while True:
        time.sleep(3600)


def scenario_foreign_identity(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'},
                                identity=('foreign-run', 'c' * 40, 'd' * 64)))
    while True:
        time.sleep(3600)


def scenario_unexpected_field(writer, values, rows):
    message = writer.message('STARTED', {'root': values['root'] or '',
                                          'plan_rows': len(rows),
                                          'driver': 'fixture'})
    message['unexpected'] = True
    writer.write(message)
    while True:
        time.sleep(3600)


def scenario_nonfinite_number(writer, values, rows):
    writer.write_raw(b'{"schema":"' + PROTOCOL_SCHEMA.encode('utf-8') + b'",'
                     b'"run_id":"' + values['run_id'].encode('utf-8') + b'",'
                     b'"candidate_sha":"' + values['candidate_sha'].encode('utf-8') + b'",'
                     b'"authorization_sha256":"'
                     + values['authorization_sha256'].encode('utf-8') + b'",'
                     b'"sequence":1,"event":"STARTED","payload":{"value":NaN}}')
    while True:
        time.sleep(3600)


def scenario_early_exit(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    return 0


def scenario_message_flood(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    for index in range(1200):
        writer.write(writer.message('PROGRESS', {'rows_finished': index,
                                                  'rows_total': len(rows)}))
    while True:
        time.sleep(3600)


def scenario_bad_terminal_reference(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    writer.write(writer.message('TERMINAL',
                                {'canonical_receipt': {'reference': '../outside.json',
                                                       'bytes': 10,
                                                       'sha256': '0' * 64},
                                 'decision': 'FIXTURE_TERMINAL'}))
    while True:
        time.sleep(3600)


SCENARIO_FUNCTIONS = {
    'clean_terminal': scenario_clean_terminal,
    'blocking_callback': scenario_blocking_callback,
    'blocking_persistence': scenario_blocking_persistence,
    'history_replay': scenario_history_replay,
    'sequence_reversal': scenario_sequence_reversal,
    'duplicate_sequence': scenario_duplicate_sequence,
    'oversize_message': scenario_oversize_message,
    'foreign_identity': scenario_foreign_identity,
    'unexpected_field': scenario_unexpected_field,
    'nonfinite_number': scenario_nonfinite_number,
    'early_exit': scenario_early_exit,
    'message_flood': scenario_message_flood,
    'bad_terminal_reference': scenario_bad_terminal_reference,
}


def main(argv=None):
    values = parse_arguments(list(sys.argv[1:] if argv is None else argv))
    rows = load_plan(values['plan'])
    writer = Writer(values)
    handler = SCENARIO_FUNCTIONS[values['scenario']]
    handler(writer, values, rows)
    return 0


if __name__ == '__main__':
    sys.exit(main())
