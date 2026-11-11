"""Correction-only audit runner; no production entry point."""
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
    'probes': ['reports/v0-s3/product-gate0/independent-p3a/test_independent_probes.py'],
}
if mode == 'owner':
    # Only substitute the process boundary; exercise original tests against the
    # unchanged CLI parser/main/real owner in-process, without a Python child.
    from tools import v0_incremental_package as package
    spec = importlib.util.spec_from_file_location('test_v0_incremental_package', ROOT / 'tools/test_v0_incremental_package.py')
    module = importlib.util.module_from_spec(spec); sys.modules[spec.name] = module; spec.loader.exec_module(module)
    def run_cli(*args, cwd=None):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = package.main(list(args))
        text = out.getvalue()
        try: payload = json.loads(text)
        except ValueError: payload = None
        return code, payload, text, err.getvalue()
    module.run_cli = run_cli
    names = ['test_existing_owned_content_conflicts_with_zero_writes',
        'test_install_failure_midway_reverts_committed_owned_items',
        'test_user_modified_install_blocks_rollback_and_preserves_bytes',
        'test_rollback_reports_missing_owned_file_as_conflict', 'test_rollback_never_deletes_non_owned_files',
        'test_production_host_path_is_rejected', 'test_target_outside_sandbox_parent_is_rejected',
        'test_missing_sandbox_marker_is_rejected', 'test_validation_failure_leaves_no_empty_install_dir',
        'test_install_writes_ownership_record_and_rollback_removes_it',
        'test_rollback_rejects_a_missing_ownership_record', 'test_rollback_rejects_a_tampered_ownership_record',
        'test_rollback_rejects_an_ownership_record_with_a_rewritten_owned_list',
        'test_rollback_rejects_a_mismatched_session',
        'test_install_refuses_to_overwrite_an_existing_ownership_record_file',
        'test_failed_install_leaves_no_ownership_record',
        'test_rollback_rejects_a_residual_staging_directory_without_deleting_it']
    paths['owner'] = ['tools/test_v0_incremental_package.py::' + value for value in names]
with tempfile.TemporaryDirectory(prefix='lvw-p3a-correction-tests-') as temporary:
    result = pytest.main(['-v', '-s', '-p', 'no:cacheprovider', '--basetemp', str(Path(temporary) / 'pytest'), *paths[mode]])
record = {'mode': mode, 'exit': result, 'subprocesses': children,
          'temporary_roots': [{'path': str(p), 'exists_after': p.exists()} for p in owned]}
Path(__file__).with_name('raw').joinpath(name + '-guard.json').write_text(json.dumps(record, indent=2) + '\n')
raise SystemExit(result)
