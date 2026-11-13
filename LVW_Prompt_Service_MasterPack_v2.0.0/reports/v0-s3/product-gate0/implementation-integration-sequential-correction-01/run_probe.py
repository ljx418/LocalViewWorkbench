#!/usr/bin/env python3
"""Outer shell equivalent of the sequential slot correction: no candidate import.

The outer runner extracts the **baseline** executor of the candidate 7ed2116
from the git objects, runs the zero process probe against the baseline and
against the executor of the working tree and writes the two receipts next
to their raw output streams.

The outer runner never imports a candidate module: the probe is a separate
process that installs its own boundary before its first candidate import.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
PACK_ROOT = OUT.parents[3]
REPOSITORY_ROOT = OUT.parents[4]
BASELINE_SHA = '7ed2116373d2b3a88ef55b6c8c7ebc15f03142c0'
EXECUTOR_RELATIVE = ('reports/v0-s3/product-gate0/'
                     'implementation-integration-01/executor.py')
EXECUTOR_REPO_RELATIVE = ('LVW_Prompt_Service_MasterPack_v2.0.0/'
                           + EXECUTOR_RELATIVE)
PROBE_RELATIVE = ('LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/'
                  'product-gate0/implementation-integration-sequential-correction-01/'
                  'sequential_slot_probe.py')


def run_probe(label, executor_path):
    """Run the probe once and keep its raw streams and its outer exit code."""
    command = [sys.executable, '-B', str(OUT / 'sequential_slot_probe.py'),
               '--executor', str(executor_path), '--out', str(OUT / (label + '.probe.json')),
               '--label', label]
    stdout_path = OUT / (label + '.probe.stdout.log')
    stderr_path = OUT / (label + '.probe.stderr.log')
    with stdout_path.open('wb') as out, stderr_path.open('wb') as err:
        result = subprocess.run(command, cwd=str(PACK_ROOT), stdout=out, stderr=err,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    record = {'label': label, 'command': command, 'returncode': result.returncode,
              'executor_path': str(executor_path),
              'stdout_file': str(stdout_path), 'stderr_file': str(stderr_path),
              'stdout_sha256': hashlib.sha256(stdout_path.read_bytes()).hexdigest(),
              'stderr_sha256': hashlib.sha256(stderr_path.read_bytes()).hexdigest()}
    return record


def main():
    baseline_executor = OUT / 'baseline-7ed2116.executor.py'
    raw = subprocess.check_output(['git', 'show', BASELINE_SHA + ':' + EXECUTOR_REPO_RELATIVE],
                                   cwd=str(REPOSITORY_ROOT))
    baseline_executor.write_bytes(raw)
    records = [run_probe('sequential-slot-baseline-7ed2116', baseline_executor),
               run_probe('sequential-slot-current', PACK_ROOT / EXECUTOR_RELATIVE)]
    comparison = {
        'kind': 'LVW_S3_SEQUENTIAL_SLOT_PROBE_COMPARISON/1',
        'baseline_sha': BASELINE_SHA,
        'baseline_executor_sha256': hashlib.sha256(raw).hexdigest(),
        'current_executor_sha256': hashlib.sha256(
            (PACK_ROOT / EXECUTOR_RELATIVE).read_bytes()).hexdigest(),
        'runs': records}
    (OUT / 'probe-comparison.json').write_text(
        json.dumps(comparison, indent=2, sort_keys=True) + '\n')
    for record in records:
        sys.stdout.write('%s returncode=%s\n' % (record['label'], record['returncode']))
    return 0 if all(record['returncode'] == 0 for record in records) else 1


if __name__ == '__main__':
    sys.exit(main())
