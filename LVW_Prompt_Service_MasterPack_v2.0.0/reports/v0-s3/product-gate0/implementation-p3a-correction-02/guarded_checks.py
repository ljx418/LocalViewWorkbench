"""Correction02-only audit runner; no production entry point."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
mode, name = sys.argv[1:3]
owned, children = [], []
def audit(event, args):
    if event == 'tempfile.mkdtemp': owned.append(Path(args[0]).absolute())
    elif event == 'subprocess.Popen':
        executable, argv, cwd, env = args
        cwd = Path(cwd or os.getcwd()).resolve()
        if isinstance(argv, list) and '-C' in argv: cwd = Path(argv[argv.index('-C') + 1]).resolve()
        if not (mode in ('targeted', 'probes') and isinstance(argv, list) and argv[0] == 'git'
                and any(p.name.startswith('lvw-p3a-owned-') and cwd == p / 'synthetic-git' for p in owned)):
            raise AssertionError('correction subprocess denied: ' + repr(argv))
        children.append({'argv': argv, 'cwd': str(cwd)})
    elif event in ('os.system', 'os.posix_spawn', 'os.exec', 'socket.connect', 'socket.bind'):
        raise AssertionError('correction action denied: ' + event)
sys.addaudithook(audit)
import pytest
paths = {
    'targeted': ['LVW_V0_RuntimePatch/tests/test_s3_installed_runtime.py', 'tools/test_s3_install_handoff.py'],
    'regression': ['LVW_V0_RuntimePatch/tests/test_s2_stage_runtime.py', 'LVW_V0_RuntimePatch/tests/test_s2_browser_component.py'],
    'probes': ['reports/v0-s3/product-gate0/independent-p3a-correction-01/test_fix_and_failure_probes.py'],
}
with tempfile.TemporaryDirectory(prefix='lvw-p3a-correction02-tests-') as temporary:
    result = pytest.main(['-v', '-s', '-p', 'no:cacheprovider', '--basetemp', str(Path(temporary) / 'pytest'), *paths[mode]])
record = {'mode': mode, 'exit': result, 'subprocesses': children,
          'temporary_roots': [{'path': str(p), 'exists_after': p.exists()} for p in owned]}
Path(__file__).with_name('raw').joinpath(name + '-guard.json').write_text(json.dumps(record, indent=2) + '\n')
raise SystemExit(result)
