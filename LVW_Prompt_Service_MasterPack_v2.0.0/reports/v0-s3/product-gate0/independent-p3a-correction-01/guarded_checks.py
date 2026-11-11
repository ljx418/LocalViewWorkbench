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
        if not (mode in ('targeted', 'probes') and isinstance(argv, list)
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
    'probes': [str(Path(__file__).with_name('test_fix_and_failure_probes.py'))],
}
if mode == 'owner':
    # Keep existing tests/assertions; replace only their external process helper.
    from tools import v0_incremental_package as package
    spec = importlib.util.spec_from_file_location('test_v0_incremental_package', ROOT / 'tools/test_v0_incremental_package.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    def run_cli(*args, cwd=None):
        assert cwd is None, 'selected owner cases must not require cwd substitution'
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = package.main(list(args))
        try:
            payload = json.loads(out.getvalue())
        except ValueError:
            payload = None
        return code, payload, out.getvalue(), err.getvalue()
    module.run_cli = run_cli
    names = [
        'test_existing_owned_content_conflicts_with_zero_writes',
        'test_install_failure_midway_reverts_committed_owned_items',
        'test_user_modified_install_blocks_rollback_and_preserves_bytes',
        'test_rollback_reports_missing_owned_file_as_conflict',
        'test_rollback_never_deletes_non_owned_files',
        'test_production_host_path_is_rejected',
        'test_target_outside_sandbox_parent_is_rejected',
        'test_missing_sandbox_marker_is_rejected',
        'test_validation_failure_leaves_no_empty_install_dir',
        'test_install_writes_ownership_record_and_rollback_removes_it',
        'test_rollback_rejects_a_missing_ownership_record',
        'test_rollback_rejects_a_tampered_ownership_record',
        'test_rollback_rejects_an_ownership_record_with_a_rewritten_owned_list',
        'test_rollback_rejects_a_mismatched_session',
        'test_install_refuses_to_overwrite_an_existing_ownership_record_file',
        'test_failed_install_leaves_no_ownership_record',
        'test_rollback_rejects_a_residual_staging_directory_without_deleting_it',
    ]
    paths['owner'] = ['tools/test_v0_incremental_package.py::' + n for n in names]

with tempfile.TemporaryDirectory(prefix='lvw-independent-p3a-c01-') as temp:
    result = pytest.main(['-v', '-s', '-p', 'no:cacheprovider', '--basetemp', str(Path(temp) / 'pytest'), *paths[mode]])
record = {'mode': mode, 'exit': result, 'subprocesses': children, 'denied': denied,
          'temporary_roots': [{'path': str(p), 'exists_after': p.exists()} for p in owned]}
Path(__file__).with_name('raw').joinpath(mode + '-guard.json').write_text(json.dumps(record, indent=2) + '\n')
raise SystemExit(result)
