"""The pre-import hard guard of the S3-P4 originals correction 04.

The guard is installed **before** pytest, before any plugin and before any
candidate module is imported.  Every event that could start a host
process, open a socket or touch the protected state of the original batch
is refused, and the refusal is recorded.

The guard owns one process.  It never starts a process itself, it never
opens a socket and it never reads the shared counter or the original
ledger of the batch: the counter is only hashed by the outer runner, from
outside of the guard.

The guard allows what the correction needs and nothing else: a pipe, a
thread, a fifo, a fake clock and a fake handle of the same process, and
the synthetic files of this report directory.  There is no fixture
process, no network, no model, no GPU service, no download and no original
of the product in this batch.

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
    'socket.socket',
    'subprocess.Popen',
    'os.system',
    'os.exec',
    'os.spawn',
    'os.posix_spawn',
    'os.fork',
    'os.forkpty',
    'pty.spawn',
    'sqlite3.connect',
    'sqlite3.connect/handle',
)

PROTECTED_NAMES = ('shared-counter.json',)
PROTECTED_SUFFIXES = ('ledger.sqlite', 'ledger.sqlite3', 'ledger.db', 'original.sqlite')


def _is_protected(name):
    """Whether one opened name is the protected state of the batch."""
    text = str(name)
    if any(text.endswith(item) for item in PROTECTED_NAMES):
        return True
    if any(text.endswith(item) for item in PROTECTED_SUFFIXES):
        return True
    lowered = text.lower()
    return 'ledger' in lowered and lowered.endswith(('.sqlite', '.sqlite3', '.db'))


def install():
    """Install the audit hook of this guard and return its record."""
    record = {'installed_before_candidate_import': True, 'denials': [],
              'process_and_network_denied': True,
              'protected_state_denied': True,
              'sqlite_connect_denied': True}

    def boundary(event, args):
        if event in BLOCKED_EVENTS or event.startswith(('subprocess.', 'socket.',
                                                        'os.exec', 'os.spawn',
                                                        'os.posix_spawn', 'sqlite3.')):
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
    except BaseException:  # noqa: BLE001 - the failure is reported, not hidden
        # the receipt is written by the finally below and the raw traceback
        # of the entry stays in the stderr of this run
        status = 1
        raise
    finally:
        record['entry'] = entry
        record['arguments'] = arguments
        record['exit_code'] = status
        Path(receipt).write_text(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return status


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
