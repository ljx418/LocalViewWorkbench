"""Independent bootstrap boundary; candidate gets first refusal, hard fallback stays active."""
import sys
_real_add = sys.addaudithook
_state = {'fallback': False}
_PROCESS = {'subprocess.Popen','os.system','os.exec','os.spawn','os.posix_spawn','os.fork','os.forkpty'}
def bootstrap(event, args):
    if not _state['fallback'] and (event.startswith('socket.') or event in _PROCESS):
        raise RuntimeError('INDEPENDENT_BOOTSTRAP_DENIAL:'+event)
_real_add(bootstrap)
def fallback(event, args):
    if event == 'independent.audit02.fallback.handshake':
        _state['fallback'] = True
    if event.startswith('socket.') and event != 'socket.__new__':
        raise RuntimeError('INDEPENDENT_NETWORK_DENIAL:'+event)
    if event in _PROCESS:
        caller = sys._getframe(1)
        # Only explicit synthetic sys.audit calls in reviewed test/diagnostic code
        # can pass. Real subprocess internals and every other caller fail closed.
        name = caller.f_code.co_filename
        if event in ('subprocess.Popen','os.posix_spawn') and (name.endswith('/tools/test_v0_s3_supervisor.py') or name.endswith('/independent-sequential-correction-02/negative_probes.py')):
            return
        raise RuntimeError('INDEPENDENT_PROCESS_DENIAL:'+event)
def guarded_add(hook):
    result = _real_add(hook)
    if not _state['fallback']:
        _real_add(fallback)
        sys.audit('independent.audit02.fallback.handshake')
    return result
sys.addaudithook = guarded_add
