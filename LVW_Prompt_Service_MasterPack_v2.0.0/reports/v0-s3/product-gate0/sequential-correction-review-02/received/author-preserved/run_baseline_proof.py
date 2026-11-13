#!/usr/bin/env python3
"""The counter proof of the round two correction.

The new zero process tests of ``tools/test_v0_s3_supervisor.py`` are run
against the **baseline** executor of the candidate ``4e99904`` in an
isolated copy outside the repository.  The tests of the correction must
FAIL there: a test that passes on the baseline does not prove the
correction.

The copy is a plain directory tree with a synthetic ``.git`` whose HEAD is
the baseline commit: the executor only reads the head of the repository to
bind the candidate of its own binding, and the repository itself is never
changed.  The copy is removed at the end of the run and its removal is
recorded.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
PACK_ROOT = OUT.parents[3]
REPOSITORY_ROOT = OUT.parents[4]
BASELINE_SHA = '4e999043d08005829969bf5020048759557ecee9'
EXECUTOR_REPO_RELATIVE = ('LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/'
                          'product-gate0/implementation-integration-01/executor.py')
EXECUTOR_RELATIVE = ('reports/v0-s3/product-gate0/'
                     'implementation-integration-01/executor.py')
SELECTION = 'slot or reconciliation or sequential or finalizer'
LABEL = 'sequential-correction-02-baseline-proof'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_copy(root):
    """An isolated copy of the package with the baseline executor."""
    package = root / 'LVW_Prompt_Service_MasterPack_v2.0.0'
    ignored = shutil.ignore_patterns('reports', '__pycache__', '人工验收视频集',
                                     '*.pyc', '.pytest_cache')
    shutil.copytree(PACK_ROOT, package, ignore=ignored, symlinks=True)
    # The reports of the package are large; only the subtree that the
    # import chain of the tools needs is copied.
    shutil.copytree(PACK_ROOT / 'reports/v0-s1',
                    package / 'reports/v0-s1', symlinks=True)
    # Only the subtree of the executor and of the runner is needed.
    target_dir = package / EXECUTOR_RELATIVE
    target_dir = target_dir.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    runner = PACK_ROOT / ('reports/v0-s3/product-gate0/'
                           'implementation-integration-01/run_guarded_checks.py')
    (target_dir / 'run_guarded_checks.py').write_bytes(runner.read_bytes())
    # The executor of the baseline replaces the executor of the working tree.
    raw = subprocess.check_output(
        ['git', 'show', BASELINE_SHA + ':' + EXECUTOR_REPO_RELATIVE],
        cwd=str(REPOSITORY_ROOT))
    (target_dir / 'executor.py').write_bytes(raw)
    # A synthetic head: the executor only reads it to bind its own candidate.
    git = root / '.git'
    (git / 'refs' / 'heads').mkdir(parents=True, exist_ok=True)
    (git / 'HEAD').write_text('ref: refs/heads/baseline\n')
    (git / 'refs' / 'heads' / 'baseline').write_text(BASELINE_SHA + '\n')
    return package, raw


def main():
    root = Path(tempfile.mkdtemp(prefix='lvw-baseline-4e99904-'))
    record = {'kind': 'LVW_S3_SEQUENTIAL_CORRECTION_02_BASELINE_PROOF/1',
              'baseline_sha': BASELINE_SHA, 'copy_root': str(root)}
    try:
        package, raw = build_copy(root)
        record['baseline_executor_sha256'] = hashlib.sha256(raw).hexdigest()
        record['baseline_executor_source'] = 'git show %s:%s' % (
            BASELINE_SHA, EXECUTOR_REPO_RELATIVE)
        record['test_file_sha256'] = digest(package / 'tools/test_v0_s3_supervisor.py')
        copy_outdir = (package / 'reports/v0-s3/product-gate0/'
                       'implementation-integration-sequential-correction-02')
        copy_outdir.mkdir(parents=True, exist_ok=True)
        command = [sys.executable, '-B',
                   str(package / EXECUTOR_RELATIVE.replace(EXECUTOR_RELATIVE,
                                                          'reports/v0-s3/product-gate0/'
                                                          'implementation-integration-01/'
                                                          'run_guarded_checks.py')),
                   '--mode', 'focused', '--label', LABEL,
                   '--outdir', str(copy_outdir), '--modules', 'tools/test_v0_s3_supervisor.py',
                   '--select', SELECTION]
        stdout_path = OUT / (LABEL + '.outer.stdout.log')
        stderr_path = OUT / (LABEL + '.outer.stderr.log')
        with stdout_path.open('wb') as out, stderr_path.open('wb') as err:
            result = subprocess.run(command, cwd=str(package), stdout=out, stderr=err,
                                    env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        record['command'] = command
        record['working_directory'] = str(package)
        record['outer_returncode'] = result.returncode
        record['outer_returncode_semantics'] = (
            'the true outer exit code of the guarded runner in the isolated copy; '
            'it is not zero because the tests of the correction fail on the '
            'baseline executor')
        record['stdout_file'] = str(stdout_path)
        record['stderr_file'] = str(stderr_path)
        record['stdout_sha256'] = digest(stdout_path)
        record['stderr_sha256'] = digest(stderr_path)
        receipt = copy_outdir / (LABEL + '.receipt.json')
        if receipt.is_file():
            document = json.loads(receipt.read_text())
            record['collected_count'] = document.get('collected_count')
            record['receipt_outcome'] = document.get('outcome')
            record['receipt_exit_code'] = document.get('exit_code')
            record['receipt_sha256'] = digest(receipt)
        pytest_log = copy_outdir / (LABEL + '.stdout.log')
        if pytest_log.is_file():
            text = pytest_log.read_text(encoding='utf-8', errors='replace')
            record['pytest_log_sha256'] = digest(pytest_log)
            summary = [line.strip() for line in text.splitlines()
                       if ' passed' in line or ' failed' in line
                       or ' deselected' in line]
            record['pytest_summary'] = summary[-1] if summary else None
            import re
            failed = []
            for line in text.splitlines():
                match = re.match(r'^_+\s+(test_\S+)\s+_+$', line)
                if match:
                    failed.append(match.group(1))
            record['failed_tests'] = sorted(set(failed))
        for produced in sorted(copy_outdir.glob(LABEL + '*')):
            shutil.copy2(produced, OUT / produced.name)
        record['copy_outdir'] = str(copy_outdir)
        record['real_execution_performed'] = False
        record['root_counter_touched'] = False
        record['stage_pass_claim'] = False
        record['product_gate0'] = False
    finally:
        shutil.rmtree(root, ignore_errors=True)
        record['copy_removed'] = not root.exists()
        record['copy_root_removed'] = record['copy_removed']
    (OUT / (LABEL + '.proof.json')).write_text(
        json.dumps(record, indent=2, sort_keys=True) + '\n')
    sys.stdout.write(json.dumps(record, indent=2, sort_keys=True) + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
