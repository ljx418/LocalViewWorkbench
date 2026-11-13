"""The pre-import hard guard of the S3-P4 integration correction 03.

The guard is installed **before** pytest, before any plugin and before any
candidate module is imported.  Every event that could start a host
process, open a socket or touch the protected state of the original batch
is refused, and the refusal is recorded.

The guard owns one process.  It never starts a process itself, it never
opens a socket and it never reads the shared counter or the original
ledger of the batch: the counter is only hashed by the outer runner, from
outside of the guard.

Usage::

    python3 -B hardguard.py <entry> <receipt> [<argument> ...]
"""
import json
import os
import runpy
import sys
from pathlib import Path

BLOCKED_EVENTS = (
    'socket.connect',
    'socket.connect_ex',
    'socket.bind',
    'socket.getaddrinfo',
    'socket.gethostbyname',
    'socket.gethostbyaddr',
    'socket.getnameinfo',
    'socket.__new__',
    'subprocess.Popen',
    'os.system',
    'os.exec',
    'os.spawn',
    'os.posix_spawn',
    'os.fork',
    'os.forkpty',
    'pty.spawn',
)

PROTECTED_NAMES = ('shared-counter.json',)
PROTECTED_SUFFIXES = ('ledger.sqlite', 'ledger.sqlite3', 'ledger.db')


def _is_protected(name):
    text = str(name)
    if any(text.endswith(item) for item in PROTECTED_NAMES):
        return True
    lowered = text.lower()
    return 'ledger' in lowered and lowered.endswith(PROTECTED_SUFFIXES)


def install():
    """Install the audit hook of this guard and return its record."""
    record = {'installed_before_candidate_import': True, 'denials': [],
              'process_and_network_denied': True,
              'protected_state_denied': True}

    def boundary(event, args):
        if event in BLOCKED_EVENTS or event.startswith(('subprocess.', 'socket.',
                                                        'os.exec', 'os.spawn',
                                                        'os.posix_spawn')):
            record['denials'].append(event)
            raise RuntimeError('S3_CORRECTION_PREIMPORT_DENIED:' + event)
        if event == 'open' and args and _is_protected(args[0]):
            record['denials'].append('protected-open')
            raise RuntimeError('S3_CORRECTION_PROTECTED_STATE_DENIED')

    sys.addaudithook(boundary)
    return record


def main(argv):
    entry, receipt, *arguments = argv
    record = install()
    sys.dont_write_bytecode = True
    os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
    root = Path.cwd()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    sys.argv = [entry] + arguments
    status = 0
    try:
        runpy.run_path(entry, run_name='__main__')
    except SystemExit as error:
        status = int(error.code or 0)
    finally:
        record['entry'] = entry
        record['arguments'] = arguments
        record['exit_code'] = status
        Path(receipt).write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return status


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
