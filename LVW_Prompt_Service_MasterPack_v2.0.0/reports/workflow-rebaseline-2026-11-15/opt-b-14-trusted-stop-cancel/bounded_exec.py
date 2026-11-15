"""Trusted Linux single-child deadline owner; not a candidate or tree sandbox.

REQUEST is hash-frozen externally. The caller's wait/background behavior supplies
no stop guarantee. This process owns waitpid and signals only its unreaped child.
Parent SIGKILL/crash, hostile native code and descendants are outside this tool's
claim. Production use requires the existing guard's no-spawn boundary.
"""
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def exclusive_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')


def birth(pid):
    try:
        # comm may contain spaces and parentheses; field22 follows final ')'.
        data = Path('/proc/%d/stat' % pid).read_text()
        return data[data.rfind(')') + 2:].split()[19]
    except (OSError, IndexError):
        return None


def main(request_path, *, popen_factory=subprocess.Popen):
    request = json.loads(request_path.read_text())
    required = {'kind', 'argv', 'cwd', 'environment', 'output_dir',
                'wall_seconds', 'term_grace_seconds', 'kill_grace_seconds'}
    if set(request) != required or request['kind'] != 'LVW_BOUNDED_CHILD/1':
        raise ValueError('REQUEST_SCHEMA')
    if sys.platform != 'linux':
        raise ValueError('LINUX_SINGLE_CHILD_ONLY')
    argv = request['argv']
    if (not isinstance(argv, list) or not argv or
            not all(isinstance(v, str) and '\x00' not in v for v in argv) or
            not Path(argv[0]).is_absolute()):
        raise ValueError('ARGV')
    environment = request['environment']
    if (not isinstance(environment, dict) or
            not all(isinstance(k, str) and isinstance(v, str) and
                    k and '=' not in k and '\x00' not in k + v
                    for k, v in environment.items())):
        raise ValueError('ENVIRONMENT')
    for key, maximum in [('wall_seconds', 290), ('term_grace_seconds', 1),
                         ('kill_grace_seconds', 1)]:
        number = request[key]
        if (isinstance(number, bool) or not isinstance(number, (int, float)) or
                not math.isfinite(number) or not 0 < number <= maximum):
            raise ValueError('BOUND:' + key)
    cwd, output = Path(request['cwd']), Path(request['output_dir'])
    if not cwd.is_absolute() or not cwd.is_dir() or not output.is_absolute():
        raise ValueError('PATH')
    output.mkdir(mode=0o700, exist_ok=False)
    exclusive_json(output / 'intent.json', request)
    facts = {'kind': 'OWNED_SINGLE_CHILD_CONTROL_RECEIPT', 'argv': argv,
             'cwd': str(cwd), 'environment': environment, 'signals': [],
             'pid': None, 'birth': None, 'session': None, 'process_group': None,
             'timed_out': False, 'reaped': False, 'returncode': None,
             'status': 'NOT_STARTED', 'errors': [], 'cancel_signals': [],
             'descendant_tree_claim': False, 'parent_crash_claim': False,
             'product_or_checkpoint_pass': False}
    proc = None
    started = time.monotonic()
    deadline = started + request['wall_seconds']

    def cancel(signum, _frame):
        # Do not throw across Popen construction or entry to mandatory cleanup.
        # The exact owner must first reach local proc and its recovery journal.
        facts['cancel_signals'].append(signum)

    # Avoid inherited SIGCHLD=SIG_IGN auto-reaping and PID reuse before waitpid.
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    try:
        if facts['cancel_signals']:
            facts['status'] = 'CANCELLED'
            return 1
        with (output / 'stdout.log').open('xb') as stdout, \
                (output / 'stderr.log').open('xb') as stderr:
            # CLI always uses the real Popen. The source-frozen regression may
            # observe its real return at this seam; it must return that same
            # actual object, never a replacement process or simulated owner.
            proc = popen_factory(argv, cwd=str(cwd), env=environment,
                                 stdin=subprocess.DEVNULL, stdout=stdout,
                                 stderr=stderr, close_fds=True,
                                 start_new_session=True)
            facts['pid'] = proc.pid
            facts['birth'] = birth(proc.pid)
            try:
                facts['session'] = os.getsid(proc.pid)
                facts['process_group'] = os.getpgid(proc.pid)
            except ProcessLookupError:
                pass  # A fast exited child is still owned until waitpid.
            exclusive_json(output / 'child.json',
                           {k: facts[k] for k in ['pid', 'birth', 'session',
                                                  'process_group']})
            while True:
                if facts['cancel_signals']:
                    facts['status'] = 'CANCELLED'
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    facts['timed_out'] = True
                    facts['status'] = 'DEADLINE_EXPIRED'
                    break
                try:
                    proc.wait(timeout=min(0.05, remaining))
                    facts['reaped'] = True
                    facts['status'] = ('CANCELLED' if facts['cancel_signals']
                                       else 'EXITED_ZERO' if proc.returncode == 0
                                       else 'EXITED_NONZERO')
                    break
                except subprocess.TimeoutExpired:
                    continue
    except BaseException as error:
        facts['errors'].append(repr(error))
        facts['status'] = 'CONTROLLER_ERROR'
    finally:
        # The nonthrowing handler remains installed during cleanup. Repeated
        # ordinary cancellation cannot bypass cleanup entry or its bounded waits.
        if proc is not None and not facts['reaped']:
            for name, grace in [('SIGTERM', request['term_grace_seconds']),
                                ('SIGKILL', request['kill_grace_seconds'])]:
                try:
                    if proc.poll() is None:
                        facts['signals'].append({'signal': name,
                                                 'at': time.monotonic()})
                        proc.send_signal(getattr(signal, name))
                    proc.wait(timeout=grace)
                    facts['reaped'] = True
                    break
                except subprocess.TimeoutExpired:
                    continue
                except BaseException as error:
                    facts['errors'].append(repr(error))
                    break
        if proc is not None:
            facts['returncode'] = proc.returncode
        if proc is not None and not facts['reaped']:
            facts['status'] = 'STOP_UNPROVEN'
        facts['elapsed_seconds'] = time.monotonic() - started
        facts['deadline_seconds'] = request['wall_seconds']
        facts['cleanup_grace_seconds'] = (request['term_grace_seconds'] +
                                           request['kill_grace_seconds'])
        facts['limitations'] = ('Single owned child only; no descendants, '
                               'adversarial/native or parent-crash guarantee. '
                               'OS scheduling/process-start latency is not a '
                               'hard real-time guarantee. Unknown reap fails.')
        exclusive_json(output / 'receipt.json', facts)
    return 0 if (facts['status'] == 'EXITED_ZERO' and facts['reaped']
                 and not facts['cancel_signals']) else 1


if __name__ == '__main__':
    sys.exit(main(Path(sys.argv[1])))
