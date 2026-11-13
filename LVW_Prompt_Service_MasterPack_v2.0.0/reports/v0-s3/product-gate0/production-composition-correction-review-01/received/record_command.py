"""Record one real command of this run.

The record holds the real argument vector, the working directory, the
beginning, the end and the exit code of the command.  The record is
written by the *outer* layer of the run, after the command has really
ended, so the log of the run is never a promise but a fact.
"""
import json
import sys
from pathlib import Path

path = Path(__file__).resolve().parent / 'commands.json'
existing = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
existing.append(json.loads(sys.argv[1]))
path.write_text(json.dumps(existing, indent=2), encoding='utf-8')
print('recorded', existing[-1].get('label'))
