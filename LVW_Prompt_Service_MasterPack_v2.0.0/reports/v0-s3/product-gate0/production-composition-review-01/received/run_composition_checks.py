"""The directed evidence runner of the S3-P4 production composition 01.

The runner creates **no operating system child process**.  It installs the
hard offline guard before the candidate is imported, it runs the production
composition once in this process and it runs the directed acceptance scope
in this process as well.  The raw log of the acceptance scope, the node
results, the source hashes, the argv, the exit code and the read only
observation of the shared counter are written next to this script.

The shared counter of the outer pool is *read* before and after the run and
is never written, refunded or reset.  No new counter is created.
"""
import hashlib
import io
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

REPORT_ROOT = Path(__file__).resolve().parent
SHARED_COUNTER = Path('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json')
CANDIDATE_SHA = 'c6bce90eeac384d534ebb7601193693840b5b70d'
SOURCE_FILES = (
    'tools/v0_s3_production_controller.py',
    'tools/v0_s3_quality_worker.py',
    'tools/v0_s3_quality_phase.py',
    'tools/v0_s3_supervisor.py',
    'tools/v0_s3_coordinator.py',
    'tools/test_v0_s3_production_composition.py',
)
DIRECTED_SCOPE = (
    ['tools/test_v0_s3_production_composition.py'],
    ['tools/test_v0_s3_integration.py'],
    ['tools/test_v0_s3_supervisor.py', '-k',
     'worker or context or production_command'],
)


# --------------------------------------------------------------------------
# the hard guard, installed before the candidate is imported
# --------------------------------------------------------------------------
class OfflineGuardError(RuntimeError):
    """Raised when the runner tries to leave the offline boundary."""


GUARD_ATTEMPTS = []


def _blocked(name):
    def refuse(*args, **kwargs):
        GUARD_ATTEMPTS.append(name)
        raise OfflineGuardError('the offline boundary blocks ' + name)
    return refuse


def _install_guard():
    for name in ('Popen', 'run', 'call', 'check_call', 'check_output'):
        setattr(subprocess, name, _blocked('subprocess.' + name))
    for name in ('system', 'popen', 'fork', 'forkpty'):
        if hasattr(os, name):
            setattr(os, name, _blocked('os.' + name))
    for name in ('execv', 'execve', 'execvp', 'execvpe', 'execl', 'execle',
                 'execlp', 'execlpe', 'spawnv', 'spawnve', 'spawnvp', 'spawnvpe'):
        if hasattr(os, name):
            setattr(os, name, _blocked('os.' + name))
    socket.socket.connect = _blocked('socket.connect')
    socket.socket.connect_ex = _blocked('socket.connect_ex')
    socket.socket.bind = _blocked('socket.bind')
    socket.create_connection = _blocked('socket.create_connection')
    socket.getaddrinfo = _blocked('socket.getaddrinfo')
    sqlite3.connect = _blocked('sqlite3.connect')


_install_guard()


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def digest_of(path):
    try:
        return sha256_bytes(Path(path).read_bytes())
    except OSError:
        return None


def source_digests():
    digests = {}
    for relative in SOURCE_FILES:
        digests[relative] = digest_of(PACK_ROOT / relative)
    return digests


def counter_observation():
    """The read only observation of the shared counter of the outer pool."""
    if not SHARED_COUNTER.is_file():
        return {'present': False}
    raw = SHARED_COUNTER.read_bytes()
    try:
        document = json.loads(raw.decode('utf-8'))
    except (UnicodeDecodeError, ValueError):
        return {'present': True, 'sha256': sha256_bytes(raw), 'parsed': False}
    return {'present': True,
            'sha256': sha256_bytes(raw),
            'parsed': True,
            'active': document.get('active'),
            'starts_total': document.get('starts_total'),
            'starts_by_role': document.get('starts_by_role'),
            'reserved_wall_seconds': document.get('reserved_wall_seconds'),
            'spent_wall_seconds': document.get('spent_wall_seconds'),
            'budget_id': document.get('budget_id')}


class NodeRecorder:
    """The per node result recorder of the directed scope."""

    def __init__(self):
        self.results = []

    def pytest_runtest_logreport(self, report):
        if report.when == 'setup' and report.outcome == 'skipped':
            self.results.append({'nodeid': report.nodeid,
                                 'outcome': 'skipped',
                                 'duration_seconds': round(report.duration, 6),
                                 'longrepr': str(report.longrepr)[:400] if report.longrepr else None})
            return
        if report.when != 'call':
            return
        self.results.append({'nodeid': report.nodeid,
                             'outcome': report.outcome,
                             'duration_seconds': round(report.duration, 6),
                             'longrepr': None if report.passed else str(report.longrepr)[:400]})

    def pytest_runtest_logfinish(self, nodeid, location):
        return None


def run_directed_scope():
    """Run the directed acceptance scope in this process.

    Every group of the scope is a separate invocation, so the selector of
    one group never reaches the nodes of another group.
    """
    import pytest
    recorder = NodeRecorder()
    output = io.StringIO()
    errors = io.StringIO()
    groups = []
    exit_code = 0
    with redirect_stdout(output), redirect_stderr(errors):
        for group in DIRECTED_SCOPE:
            code = pytest.main(['-q', '-p', 'no:cacheprovider'] + list(group),
                                plugins=[recorder])
            groups.append({'arguments': list(group), 'exit_code': int(code)})
            if int(code) != 0:
                exit_code = int(code)
    (REPORT_ROOT / 'directed-scope.stdout.log').write_text(output.getvalue(), 'utf-8')
    (REPORT_ROOT / 'directed-scope.stderr.log').write_text(errors.getvalue(), 'utf-8')
    (REPORT_ROOT / 'directed-scope.node-results.json').write_text(
        canonical_json(recorder.results) + '\n', 'utf-8')
    passed = sum(1 for item in recorder.results if item['outcome'] == 'passed')
    failed = sum(1 for item in recorder.results if item['outcome'] == 'failed')
    skipped = len(recorder.results) - passed - failed
    return {'exit_code': exit_code, 'nodes': len(recorder.results),
            'passed': passed, 'failed': failed, 'skipped_or_other': skipped,
            'groups': groups,
            'scope': [list(group) for group in DIRECTED_SCOPE],
            'stdout_log': 'directed-scope.stdout.log',
            'stderr_log': 'directed-scope.stderr.log',
            'node_results': 'directed-scope.node-results.json'}


def run_the_composition():
    """Run the production composition once, in this process.

    The run root is kept next to this script, so the reviewer can read the
    real artefacts of the run: the plan, the canonical receipt, the source
    plan, the raw artefacts, the parent manifest and the summary.
    """
    from tools import test_v0_s3_production_composition as suite
    run_root = REPORT_ROOT / 'run-root'
    if run_root.exists():
        return {'status': 'REFUSED', 'reason': 'RUN_ROOT_ALREADY_EXISTS'}
    composition = suite._build_composition(run_root.parent, name='run-root')
    context = suite._controller_context(composition['controller_context_path'])
    seam = suite._seam(composition)
    from tools import v0_s3_production_controller as controller
    instance = controller.ProductionController(context, seam=seam)
    receipt = instance.run()
    (REPORT_ROOT / 'composition.receipt.json').write_text(
        canonical_json(receipt) + '\n', 'utf-8')
    return {'status': receipt['state'], 'receipt': 'composition.receipt.json',
            'run_root': str(run_root),
            'summary_path': receipt.get('summary_path'),
            'summary_sha256': receipt.get('summary_sha256'),
            'plan_sha256': receipt['plan']['plan_sha256'],
            'canonical_sha256': receipt['summary']['provenance']['canonical']['sha256'],
            'source_plan_sha256': receipt['summary']['provenance']['source_plan']['sha256'],
            'manifest_sha256': receipt['summary']['provenance']['manifest']['sha256'],
            'key_count': receipt['summary']['key_count'],
            'pass_count': receipt['summary']['pass_count'],
            'node_id': receipt['node_id'],
            'fd_cleanup': receipt['fd_cleanup']}


def main():
    started = time.time()
    counter_before = counter_observation()
    composition = run_the_composition()
    scope = run_directed_scope()
    counter_after = counter_observation()
    receipt = {
        'kind': 'lvw.s3-production-composition-receipt/1',
        'label': 'implementation-production-composition-01',
        'run_id': 's3-p4-production-composition-01',
        'candidate_sha': CANDIDATE_SHA,
        'candidate_sha_claim_is_attestation': True,
        'node_id': composition.get('node_id'),
        'execution_attempts': 1,
        'argv': list(sys.argv),
        'exit_code': scope['exit_code'],
        'started_wall': started,
        'duration_seconds': round(time.time() - started, 3),
        'source_sha256': source_digests(),
        'composition': composition,
        'directed_scope': scope,
        'guard': {'installed_before_candidate_import': True,
                  'attempts': list(GUARD_ATTEMPTS),
                  'blocked': ['subprocess', 'socket', 'fork', 'exec', 'system',
                              'sqlite3.connect']},
        'counter': {'path': str(SHARED_COUNTER),
                    'before': counter_before,
                    'after': counter_after,
                    'written_by_this_run': False,
                    'refunded_or_reset_by_this_run': False,
                    'new_counter_created_by_this_run': False,
                    'unchanged': counter_before.get('sha256') == counter_after.get('sha256')},
        'outcome': 'PASS' if (scope['failed'] == 0 and scope['exit_code'] == 0
                              and composition.get('status') == 'SUMMARY_PERSISTED') else 'FAILED',
        'real_execution_performed': False,
        'native_admission_accepted': False,
        'stage_pass_claim': False,
        'product_gate0': False,
        'ready_for_review': True,
    }
    (REPORT_ROOT / 'composition-run.receipt.json').write_text(
        canonical_json(receipt) + '\n', 'utf-8')
    sys.stdout.write(canonical_json(receipt) + '\n')
    return 0 if receipt['outcome'] == 'PASS' else 1


if __name__ == '__main__':
    sys.exit(main())
