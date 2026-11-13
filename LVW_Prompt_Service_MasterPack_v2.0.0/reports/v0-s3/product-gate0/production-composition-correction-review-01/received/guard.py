"""The independent zero-process boundary of this implementation run.

The hook of this module is installed *before* the candidate is imported.
The candidate therefore never has the chance to leave the offline
boundary, and the boundary does not rely on a monkeypatch of the
candidate: it is an audit hook of the interpreter, so a call that the
candidate makes through any path is seen.

The boundary refuses:

* every operating system child process - ``subprocess``, ``os.system``,
  ``os.fork``, ``os.forkpty``, ``os.exec*``, ``os.spawn*`` and
  ``os.posix_spawn``;
* every socket - the creation of a socket and every socket operation;
* every database connection - ``sqlite3.connect``;
* every read of the protected state - the shared counter of the root and
  the original ledger of the product.

The guard writes a receipt with every attempt that it refused, so the
evidence can state that the boundary was never crossed *and* that the
boundary was armed.

The receipt is written in a ``finally`` block: a refusal that ends the
run is still recorded.
"""
import json
import os
import runpy
import sys
from pathlib import Path

# The protected state of the root.  The shared counter is read by the
# outer layer only and the original ledger of the product is never read at
# all.  The ledger of the product lives in the runtime state of the root
# (``.lvw-runtime``) and is named ``program02.sqlite``.
PROTECTED_EXACT = ('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json',)
PROTECTED_NAMES = ('shared-counter.json', 'program02.sqlite')
PROTECTED_PARTS = ('.lvw-runtime',)

entry, receipt, *rest = sys.argv[1:]
denials = []

# The synthetic root of this run.  A file that a test creates inside this
# root is a synthetic artefact of this run and not the protected state of
# the product, so it is not refused.  Everything else that carries a
# protected name is refused.
SYNTHETIC_ROOTS = tuple(str(Path(__file__).resolve().parent / name)
                        for name in ('pytest-temp', 'run-root'))


def _deny(reason):
    denials.append(reason)
    raise RuntimeError('IMPLEMENTATION_BOUNDARY_DENIED:' + reason)


def _inside_synthetic_root(name):
    return any(name == root or name.startswith(root + os.sep) for root in SYNTHETIC_ROOTS)


def _protected(name):
    if name in PROTECTED_EXACT:
        return True
    path = Path(name)
    if any(part in PROTECTED_PARTS for part in path.parts):
        return True
    if path.name in PROTECTED_NAMES:
        return True
    if path.name.startswith('original.') and path.suffix in ('.sqlite', '.sqlite3', '.db') \
            and not _inside_synthetic_root(name):
        return True
    return False


def audit(event, args):
    if event.startswith('subprocess.') or event.startswith('socket.'):
        _deny(event)
    if event in ('os.system', 'os.fork', 'os.forkpty', 'pty.spawn',
                 'os.posix_spawn', 'sqlite3.connect'):
        _deny(event)
    if event.startswith('os.exec') or event.startswith('os.spawn'):
        _deny(event)
    if event == 'open' and args:
        name = str(args[0])
        if _protected(name):
            _deny('protected-open:' + name)


sys.addaudithook(audit)
sys.dont_write_bytecode = True
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
sys.path.insert(0, str(Path.cwd()))
sys.argv = [entry] + rest
try:
    runpy.run_path(entry, run_name='__main__')
finally:
    Path(receipt).write_text(json.dumps({
        'boundary': 'implementation-production-composition-correction-01',
        'installed_before_the_candidate_import': True,
        'entry': entry,
        'arguments': rest,
        'denials': denials,
        'denial_count': len(denials),
        'refused_families': ['subprocess', 'socket', 'os.fork', 'os.exec',
                             'os.spawn', 'os.system', 'sqlite3.connect',
                             'protected_state'],
        'zero_fixture_process_permission': True,
        'zero_download_permission': True,
        'zero_gpu_permission': True,
        'zero_model_permission': True,
    }, indent=2), encoding='utf-8')
