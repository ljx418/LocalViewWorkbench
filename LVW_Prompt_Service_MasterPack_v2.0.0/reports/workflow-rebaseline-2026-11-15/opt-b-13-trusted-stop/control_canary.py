"""Only the separately frozen supervisor selftest may launch this child."""
import json
import os
from pathlib import Path
import signal
import sys
import time

mode = sys.argv[1]
if mode not in ('normal', 'nonzero', 'term', 'ignore-term'):
    raise ValueError('MODE')
if mode == 'ignore-term':
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
print(json.dumps({'pid': os.getpid(), 'parent': os.getppid(),
                  'session': os.getsid(0), 'group': os.getpgid(0),
                  'birth': Path('/proc/self/stat').read_text().rsplit(')', 1)[1]
                  .split()[19], 'mode': mode, 'ready': True}), flush=True)
if mode in ('normal', 'nonzero'):
    sys.exit(0 if mode == 'normal' else 13)
while True:
    time.sleep(0.05)
