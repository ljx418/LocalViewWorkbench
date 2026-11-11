"""Review-only runner: install an audit guard before importing pytest or tests."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
mode = sys.argv[1]
owned = []
children = []

def audit(event, args):
    if event == 'tempfile.mkdtemp':
        path = Path(args[0]).absolute()
        owned.append(path)
    elif event == 'subprocess.Popen':
        executable, argv, cwd, env = args
        cwd = Path(cwd or os.getcwd()).resolve()
        if isinstance(argv, list) and '-C' in argv:
            cwd = Path(argv[argv.index('-C') + 1]).resolve()
        allowed = (mode != 'regression' and isinstance(argv, list) and argv[0] == 'git'
                   and any(p.name.startswith('lvw-p3a-owned-') and cwd == p / 'synthetic-git' for p in owned))
        if not allowed:
            raise AssertionError('REVIEW subprocess denied: ' + repr((executable, argv, str(cwd))))
        if '-C' in argv:
            assert Path(argv[argv.index('-C') + 1]).resolve() == cwd
        children.append({'argv': argv, 'cwd': str(cwd)})
    elif event in ('os.system', 'os.posix_spawn', 'os.exec', 'socket.connect', 'socket.bind'):
        raise AssertionError('REVIEW forbidden action: ' + event)

sys.addaudithook(audit)
import pytest
paths = {
    'targeted': ['LVW_V0_RuntimePatch/tests/test_s3_installed_runtime.py'],
    'regression': ['LVW_V0_RuntimePatch/tests/test_s2_stage_runtime.py', 'LVW_V0_RuntimePatch/tests/test_s2_browser_component.py'],
    'probes': [str(Path(__file__).with_name('test_independent_probes.py'))],
}[mode]
exit_code = pytest.main(['-v', '-s', '-p', 'no:cacheprovider', *paths])
cleanup = {'mode': mode, 'exit': exit_code, 'subprocesses': children,
           'temporary_roots': [{'path': str(p), 'exists_after': p.exists()} for p in owned]}
Path(__file__).with_name('raw').joinpath(mode + '-guard.json').write_text(json.dumps(cleanup, indent=2) + '\n')
raise SystemExit(exit_code)
