"""The pre-import boundary of the round two probes.

The candidate is imported **after** this file has run, so no real child
process and no network socket can be created by the import of the
candidate, of its test helpers or of the probes themselves.

The shape of this boundary is the one of the independent review of the
first round (``sequential-correction-review-01/received/outer_boundary.py``):
the candidate gets the first refusal and the hard fallback stays active
after the handshake.  Only the explicit synthetic audit events of the
reviewed test file may pass; every other caller fails closed.
"""
import sys

_real_add = sys.addaudithook
_state = {'fallback': False}
_PROCESS = {'subprocess.Popen', 'os.system', 'os.exec', 'os.spawn',
            'os.posix_spawn', 'os.fork', 'os.forkpty'}


def bootstrap(event, args):
    """The refusal that is active before the candidate is imported."""
    if not _state['fallback'] and (event.startswith('socket.') or event in _PROCESS):
        raise RuntimeError('ROUND_TWO_BOOTSTRAP_DENIAL:' + event)


_real_add(bootstrap)


def fallback(event, args):
    """The hard fallback: it stays active for the whole run."""
    if event == 'round_two.audit.fallback.handshake':
        _state['fallback'] = True
    if event.startswith('socket.') and event != 'socket.__new__':
        raise RuntimeError('ROUND_TWO_NETWORK_DENIAL:' + event)
    if event in _PROCESS:
        caller = sys._getframe(1)
        # Only an explicit synthetic audit call of the reviewed test file
        # may pass.  The internals of a real process creation and every
        # other caller fail closed.
        name = caller.f_code.co_filename
        if event in ('subprocess.Popen', 'os.posix_spawn') and \
                name.endswith('/tools/test_v0_s3_supervisor.py'):
            return
        raise RuntimeError('ROUND_TWO_PROCESS_DENIAL:' + event)


def guarded_add(hook):
    result = _real_add(hook)
    if not _state['fallback']:
        _real_add(fallback)
        sys.audit('round_two.audit.fallback.handshake')
    return result


sys.addaudithook = guarded_add
