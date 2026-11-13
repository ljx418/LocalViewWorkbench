"""The self test of the independent boundary.

The self test proves that the boundary is armed: every family that the
boundary refuses is really refused, and the refusal is the refusal of the
boundary and not of the tested object.  No candidate is imported here.
"""
import os
import socket
import sqlite3
import subprocess
from pathlib import Path

checks = [
    ('subprocess.Popen', lambda: subprocess.Popen(['/bin/true'])),
    ('subprocess.run', lambda: subprocess.run(['/bin/true'])),
    ('socket', lambda: socket.socket()),
    ('os.fork', lambda: os.fork()),
    ('os.execv', lambda: os.execv('/bin/true', ['true'])),
    ('os.system', lambda: os.system('true')),
    ('sqlite3.connect', lambda: sqlite3.connect(':memory:')),
    ('protected-open', lambda: Path('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/'
                                    'shared-counter.json').read_bytes()),
    ('protected-ledger', lambda: Path('/mnt/c/workspace/videoworkline/localviewworkbench/'
                                      '.lvw-runtime/lvw-prompt-service/program02.sqlite')
     .read_bytes()),
]
confirmed = []
for label, action in checks:
    try:
        action()
    except RuntimeError as error:
        assert 'IMPLEMENTATION_BOUNDARY_DENIED' in str(error), (label, str(error))
        confirmed.append(label)
    except Exception as error:  # noqa: BLE001 - the bypass is the failure
        raise AssertionError('the boundary did not refuse ' + label + ': '
                             + type(error).__name__)
    else:
        raise AssertionError('the boundary was bypassed by ' + label)
print(len(confirmed), 'pre-import boundary denials confirmed; no candidate import: '
      + ','.join(confirmed))
