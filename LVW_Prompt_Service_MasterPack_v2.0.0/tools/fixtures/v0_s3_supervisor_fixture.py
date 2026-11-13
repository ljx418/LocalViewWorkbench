#!/usr/bin/env python3
"""The enumerated supervisor fixture of the S3 parent supervision.

This entry is a *synthetic worker* for the bounded offline scenarios of the
parent supervision.  It is not a general execution platform: the scenario is
one member of a closed enumeration, the arguments are a closed set and the
entry never runs a shell, a native executable or a service.

The entry installs its own zero network and zero descendant process guard
*before* it imports the product module, so neither this file nor any module
that it imports afterwards can open a socket, resolve a name or start a
process.  The guard is registered by the ``__main__`` entry only: importing
this file as a module - the parent test process does exactly that - never
registers an audit hook and never closes the process gate of that process.

Every scenario writes the supervision protocol on its standard output and
then stops.  The scenarios exist to show how the *parent* reacts; they never
prove a product behaviour, a native Windows release or a quality result.
"""
import hashlib
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

# The witness of the boundary guard of this module.  Only the one function
# that registers the audit hook sets it, so it can never be true while the
# hook is not really active.
BOUNDARY_GUARD_INSTALLED = False

# The product constants, loaded behind the boundary guard.
_PRODUCT = None

# The outcome of a scenario that has to stay alive until the parent stops it.
BLOCK_FOREVER = 'BLOCK_FOREVER'


def _audit_hook(event, arguments):
    if event in BLOCKED_EVENTS:
        raise FixtureBoundaryViolation('fixture boundary violation: ' + event)


def install_boundary_guard():
    """Install the zero network and zero descendant process guard.

    This call is the only place that registers the audit hook of this
    module.  The ``__main__`` entry performs it *before* the product module
    is imported, so neither this file nor any module that it imports
    afterwards can open a socket, resolve a name or start a process.
    """
    global BOUNDARY_GUARD_INSTALLED
    if BOUNDARY_GUARD_INSTALLED:
        return False
    sys.addaudithook(_audit_hook)
    BOUNDARY_GUARD_INSTALLED = True
    return True


def product():
    """The product constants of the protocol, loaded behind the guard.

    The import is deliberately lazy.  The ``__main__`` entry installs the
    boundary guard first and the guard refuses to be missing, so the product
    code is never imported in a process that could open a socket or start a
    process.  A module import of this file never touches the product code.
    """
    global _PRODUCT
    if _PRODUCT is None:
        if __name__ == '__main__' and not BOUNDARY_GUARD_INSTALLED:
            raise SystemExit('FIXTURE_GUARD_MISSING')
        from tools.v0_s3_supervisor import (MAX_MESSAGE_BYTES, MAX_MESSAGES,
                                            MAX_STREAM_BYTES, MESSAGE_KEYS,
                                            PROTOCOL_SCHEMA)
        _PRODUCT = {'schema': PROTOCOL_SCHEMA, 'message_keys': MESSAGE_KEYS,
                    'max_messages': MAX_MESSAGES,
                    'max_message_bytes': MAX_MESSAGE_BYTES,
                    'max_stream_bytes': MAX_STREAM_BYTES}
    return _PRODUCT


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
        return {'schema': product()['schema'], 'run_id': run_id,
                'candidate_sha': candidate, 'authorization_sha256': authorization,
                'sequence': sequence, 'event': event, 'payload': payload}

    @staticmethod
    def encode(message):
        """The exact wire bytes of one message, without the frame end.

        The encoding is the compact, sorted form of the protocol.  It is a
        pure function of the message, so the wire of a scenario can be
        computed before a single byte is written.
        """
        return json.dumps(message, ensure_ascii=False, sort_keys=True,
                          separators=(',', ':')).encode('utf-8')

    def write(self, message):
        sys.stdout.buffer.write(self.encode(message) + b'\n')
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
    return {'reference': reference, 'bytes': len(raw),
            'sha256': hashlib.sha256(raw).hexdigest()}


def block_forever():
    """Stay alive until the parent stops the held process."""
    while True:
        time.sleep(3600)


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
    return None


def scenario_blocking_callback(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    # The scenario blocks exactly like a callback that never returns.  The
    # parent has to stop the process that it holds; it cannot accept a
    # timeout text instead.
    return BLOCK_FOREVER


def scenario_blocking_persistence(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    # A partial line: the message is never terminated, so the protocol is
    # unresolved and the parent has to stop the held process.  The raw byte
    # semantics of ``write_raw`` are kept exactly: the frame stays
    # incomplete on purpose.
    writer.write_raw(b'{"schema":"' + product()['schema'].encode('utf-8') + b'","run_id":"')
    return BLOCK_FOREVER


def scenario_history_replay(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    if rows:
        payload = {'asset_id': rows[0]['asset_id'], 'ordinal': rows[0]['ordinal']}
        writer.write(writer.message('HISTORY_WAIT_STARTED', dict(payload)))
        writer.write(writer.message('HISTORY_WAIT_STARTED', dict(payload)))
    return BLOCK_FOREVER


def scenario_sequence_reversal(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}, sequence=2))
    writer.write(writer.message('PROGRESS', {'rows_finished': 0, 'rows_total': len(rows)},
                                sequence=1))
    return BLOCK_FOREVER


def scenario_duplicate_sequence(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}, sequence=1))
    writer.write(writer.message('PROGRESS', {'rows_finished': 0, 'rows_total': len(rows)},
                                sequence=1))
    return BLOCK_FOREVER


def scenario_oversize_message(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    payload = {'rows_total': len(rows), 'filler': 'x' * 40000}
    writer.write(writer.message('PROGRESS', payload))
    return BLOCK_FOREVER


def scenario_foreign_identity(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'},
                                identity=('foreign-run', 'c' * 40, 'd' * 64)))
    return BLOCK_FOREVER


def scenario_unexpected_field(writer, values, rows):
    message = writer.message('STARTED', {'root': values['root'] or '',
                                          'plan_rows': len(rows),
                                          'driver': 'fixture'})
    message['unexpected'] = True
    writer.write(message)
    return BLOCK_FOREVER


def scenario_nonfinite_number(writer, values, rows):
    """The nonfinite number negative case.

    The frame is *complete*: it carries the whole protocol message and it is
    terminated by the newline of the JSONL protocol.  The parent really
    decodes it and the parser refuses the NaN.  The raw byte semantics of
    ``write_raw`` are not used here and are not changed anywhere else.
    """
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture',
                                             'value': float('nan')}))
    return BLOCK_FOREVER


def scenario_early_exit(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    return None


def flood_messages(values, rows):
    """The exact messages of the message count negative case.

    The list holds exactly ``MAX_MESSAGES + 1`` complete messages: the
    ``STARTED`` message and the progress messages that follow it.  Every
    message is closed, carries the identity of the context document and has
    an empty payload, so the frozen byte budget of the stream cannot hide
    the message count.
    """
    schema = product()['schema']
    count = product()['max_messages'] + 1
    messages = []
    for sequence in range(1, count + 1):
        if sequence == 1:
            event = 'STARTED'
            payload = {'root': values.get('root') or '', 'plan_rows': len(rows),
                       'driver': 'fixture'}
        else:
            event = 'PROGRESS'
            payload = {}
        messages.append({'schema': schema, 'run_id': values['run_id'],
                         'candidate_sha': values['candidate_sha'],
                         'authorization_sha256': values['authorization_sha256'],
                         'sequence': sequence, 'event': event,
                         'payload': payload})
    return messages


def flood_wire(values, rows):
    """The exact wire bytes of the message count negative case.

    The wire is computed before a single byte is written: the number of
    frames, the length of every frame and the total number of bytes are
    real values, not estimates.
    """
    frames = [Writer.encode(message) + b'\n'
              for message in flood_messages(values, rows)]
    return frames


def scenario_message_flood(writer, values, rows):
    """The message count negative case: exactly one message too many.

    The wire is bounded *before* it is written.  If the frames of this
    negative case did not fit into the frozen byte caps, the byte budget
    would hide the message count and the scenario would refuse itself
    instead of proving the wrong reason.
    """
    limits = product()
    frames = flood_wire(values, rows)
    total = sum(len(frame) for frame in frames)
    longest = max(len(frame) for frame in frames)
    if (len(frames) != limits['max_messages'] + 1
            or longest > limits['max_message_bytes']
            or total > limits['max_stream_bytes']):
        raise SystemExit('FIXTURE_WIRE_BUDGET_EXCEEDED')
    for frame in frames:
        writer.write_raw(frame)
    return BLOCK_FOREVER


def scenario_bad_terminal_reference(writer, values, rows):
    writer.write(writer.message('STARTED', {'root': values['root'] or '',
                                             'plan_rows': len(rows),
                                             'driver': 'fixture'}))
    writer.write(writer.message('TERMINAL',
                                {'canonical_receipt': {'reference': '../outside.json',
                                                       'bytes': 10,
                                                       'sha256': '0' * 64},
                                 'decision': 'FIXTURE_TERMINAL'}))
    return BLOCK_FOREVER


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
    outcome = handler(writer, values, rows)
    if outcome == BLOCK_FOREVER:
        block_forever()
    return 0


if __name__ == '__main__':
    # The guard is installed before the product module is imported.
    install_boundary_guard()
    sys.exit(main())
