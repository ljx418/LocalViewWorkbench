"""Independent review runner; guards installed before pytest/plugin imports."""
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
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
sys.dont_write_bytecode = True
mode = sys.argv[1]
owned, children, denied = [], [], []

def audit(event, args):
    if event == 'tempfile.mkdtemp':
        owned.append(Path(args[0]).absolute())
    elif event == 'subprocess.Popen':
        executable, argv, cwd, env = args
        effective = Path(cwd or os.getcwd()).resolve()
        if isinstance(argv, list) and '-C' in argv:
            effective = Path(argv[argv.index('-C') + 1]).resolve()
        if not (mode in ('targeted', 'probes', 'gap', 'post', 'latest', 'extra', 'reachable') and isinstance(argv, list)
                and argv[0] == 'git' and executable == 'git'
                and any(p.name.startswith('lvw-p3a-owned-') and effective == p / 'synthetic-git' for p in owned)):
            denied.append({'event': event, 'argv': repr(argv)})
            raise AssertionError('independent review denied subprocess: ' + repr(argv))
        children.append({'argv': argv, 'effective_cwd': str(effective)})
    elif event in ('os.system', 'os.posix_spawn', 'os.exec', 'socket.connect', 'socket.bind', 'socket.getaddrinfo'):
        denied.append({'event': event})
        raise AssertionError('independent review denied action: ' + event)

sys.addaudithook(audit)
import pytest

paths = {
    'targeted': ['LVW_V0_RuntimePatch/tests/test_s3_installed_runtime.py', 'tools/test_s3_install_handoff.py'],
    'regression': ['LVW_V0_RuntimePatch/tests/test_s2_stage_runtime.py', 'LVW_V0_RuntimePatch/tests/test_s2_browser_component.py'],
    'probes': [str(Path(__file__).parent.parent / 'independent-p3a-correction-01/test_fix_and_failure_probes.py')],
    'gap': [str(Path(__file__).parent.parent / 'independent-p3a-correction-02/test_lifecycle_gap.py')],
    'post': [str(Path(__file__).parent.parent / 'independent-p3a-correction-03/test_callback_gaps.py') + '::test_post_prepare_cleanup_adapter_rejects_replacement_before_archive_write'],
    'latest': [str(Path(__file__).parent.parent / 'independent-p3a-correction-04/test_archive_lifetime_gaps.py')],
    'reachable': [str(Path(__file__).with_name('test_reachable_callback_boundaries.py'))],
    'extra': [str(Path(__file__).with_name('test_callback_provenance.py'))],
}

with tempfile.TemporaryDirectory(prefix='lvw-independent-p3a-c05-') as temp:
    result = pytest.main(['-v', '-s', '-p', 'no:cacheprovider', '--basetemp', str(Path(temp) / 'pytest'), *paths[mode]])
record = {'mode': mode, 'exit': result, 'subprocesses': children, 'denied': denied,
          'temporary_roots': [{'path': str(p), 'exists_after': p.exists()} for p in owned]}
Path(__file__).with_name('raw').joinpath(mode + '-guard.json').write_text(json.dumps(record, indent=2) + '\n')
raise SystemExit(result)
