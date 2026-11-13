"""The compatibility regression of the frozen owners.

The correction touched the controller, the quality worker, the fixed
production command of the supervisor and their tests.  The compatibility
regression runs the suites of the frozen owners and archives the real
exit code and both streams of every batch.

The batches are separate on purpose: the offline guard of the quality
phase suite is a *process wide* guard of its own session, so a suite that
really wants a host subprocess and that suite have to run in separate
sessions.  This is a property of the frozen test suites and not of this
correction.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
REPORT = Path(__file__).resolve().parent

BATCHES = (
    ('compat-supervisor', ['tools/test_v0_s3_supervisor.py']),
    ('compat-integration-quality-phase',
     ['tools/test_v0_s3_integration.py', 'tools/test_v0_s3_quality_phase.py']),
    ('compat-budget-authority', ['tools/test_v0_s3_budget_authority.py']),
    ('compat-runtime-binding', ['tools/test_v0_s3_runtime_binding.py']),
)


def main():
    records = []
    for label, targets in BATCHES:
        argv = [sys.executable, '-m', 'pytest', '-q', '-p', 'no:cacheprovider',
                '--tb=line'] + targets
        started = time.time()
        process = subprocess.run(argv, cwd=str(PACK_ROOT), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, check=False)
        ended = time.time()
        (REPORT / (label + '.stdout.log')).write_bytes(process.stdout)
        (REPORT / (label + '.stderr.log')).write_bytes(process.stderr)
        records.append({
            'label': label,
            'argv': argv,
            'cwd': str(PACK_ROOT),
            'targets': targets,
            'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(started)),
            'ended_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(ended)),
            'duration_seconds': round(ended - started, 3),
            'exit_code': process.returncode,
            'stdout_log': label + '.stdout.log',
            'stderr_log': label + '.stderr.log',
            'is_part_of_the_directed_scope': False,
            'note': ('compatibility regression of the frozen owners; the '
                     'machine gate of the fixture process tests is not bound, so '
                     'those nodes are skipped and no host process was started'),
        })
        print(label, 'exit', process.returncode)
    (REPORT / 'compat-regression.json').write_text(json.dumps({
        'kind': 'lvw.s3-production-composition-correction-compat/1',
        'batches': records,
        'cases_are_not_the_directed_scope': True,
        'the_old_denominators_are_not_counted_here': True,
    }, indent=2), encoding='utf-8')
    return 0 if all(record['exit_code'] == 0 for record in records) else 1


if __name__ == '__main__':
    raise SystemExit(main())
