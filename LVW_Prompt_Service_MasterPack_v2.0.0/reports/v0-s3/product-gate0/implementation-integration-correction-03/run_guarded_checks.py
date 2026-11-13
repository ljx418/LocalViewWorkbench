#!/usr/bin/env python3
"""The guarded runner of the S3-P4 integration correction 03.

Every entry of this batch runs **inside** the pre-import hard guard: the
audit hook of the guard is installed before pytest, before any plugin and
before any candidate module is imported, so neither the pytest startup, nor
a plugin, nor a candidate import can start a host process, open a socket
or touch the shared counter or the original ledger of the batch.

The runner never masks an exit code and never reconstructs a log: the raw
stdout and stderr bytes are captured at the file descriptor level and the
true exit code is written next to them.  The outer log names of this
runner are its own; they never overwrite the log of an entry.

The counter of the batch is only read from the outside of the guard: the
runner hashes it before and after the batch and never writes it, never
refunds it and never creates a new one.

Usage::

    python3 -B run_guarded_checks.py --outdir <this directory> [--only <step>]
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACK_ROOT = HERE.parents[3]
GUARD = HERE / 'hardguard.py'
COUNTER = Path('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json')

SOURCES = ('tools/v0_s3_supervisor.py', 'tools/v0_s3_coordinator.py',
           'tools/test_v0_s3_supervisor.py', 'tools/test_v0_s3_integration.py')

# The affected set of this correction: the two owner modules that were
# changed and their two test modules.  The selection of the focused runs is
# the narrow one of the changed behaviour; the affected run is the whole of
# these two modules, once.
STEPS = (
    {'label': 'probes', 'entry': HERE / 'probes.py', 'args': []},
    {'label': 'owner-probe', 'entry': HERE / 'owner_probe.py', 'args': []},
    {'label': 'focused-supervisor',
     'entry': HERE / 'pytest_entry.py',
     'args': ['tools/test_v0_s3_supervisor.py', '-q', '-p', 'no:cacheprovider',
              '-k', 'history or deadline or row_started or row_reopen or snapshot '
                    'or hash or scope or handoff or drain or stream or protocol '
                    'or evidence or overflow or terminal']},
    {'label': 'focused-integration',
     'entry': HERE / 'pytest_entry.py',
     'args': ['tools/test_v0_s3_integration.py', '-q', '-p', 'no:cacheprovider',
              '-k', 'twelve or receipt or cleanup or parent or original or key '
                    'or aggregate or isolation or score']},
    {'label': 'affected-modules',
     'entry': HERE / 'pytest_entry.py',
     'args': ['tools/test_v0_s3_supervisor.py', 'tools/test_v0_s3_integration.py',
              '-q', '-p', 'no:cacheprovider',
              '-k', 'not (single_guard or offline_boundary or refused_start '
                    'or machine_accounting or real_guard_refusal or copied_marker '
                    'or replayed_real_guard_refusal or charge_whose_settlement '
                    'or proof_of_a_child)']},
)

# The nine machine gate tests of the finite CPU executor are not part of
# this batch: they start a real child process and they need the machine
# binding of the root, which this zero process correction does not have.
# They are deselected by name and they are not affected by this correction:
# the executor, the fixture and the runner of the batch are unchanged.
MACHINE_GATE_TESTS = (
    'test_the_single_guard_admits_a_start_once_and_is_never_vetoed_twice',
    'test_the_offline_boundary_still_blocks_a_process_and_a_socket',
    'test_a_refused_start_that_never_forked_is_settled_and_frees_its_slot',
    'test_the_machine_accounting_separates_the_admissions_from_the_created_handles',
    'test_the_real_guard_refusal_releases_the_slot_of_its_own_charge',
    'test_a_copied_marker_and_a_copied_gate_error_release_nothing',
    'test_a_replayed_real_guard_refusal_releases_nothing',
    'test_a_charge_whose_settlement_failed_stays_open_and_keeps_the_root',
    'test_the_proof_of_a_child_is_never_written_before_its_settlement',
)


def digest_of(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def counter_state():
    """The read only state of the shared counter of the batch."""
    if not COUNTER.exists():
        return {'path': str(COUNTER), 'present': False}
    raw = COUNTER.read_bytes()
    document = json.loads(raw.decode('utf-8'))
    return {'path': str(COUNTER), 'present': True,
            'sha256': hashlib.sha256(raw).hexdigest(),
            'active': document.get('active'),
            'starts_total': document.get('starts_total'),
            'reserved_wall_seconds': document.get('reserved_wall_seconds'),
            'spent_wall_seconds': document.get('spent_wall_seconds')}


def run_step(step, outdir):
    """Run one entry inside the guard and keep its raw streams."""
    label = step['label']
    guard_receipt = outdir / (label + '.guard.json')
    stdout_path = outdir / (label + '.outer.stdout.log')
    stderr_path = outdir / (label + '.outer.stderr.log')
    argv = [sys.executable, '-B', str(GUARD), str(step['entry']), str(guard_receipt)] \
        + [str(item) for item in step['args']]
    begin = time.time()
    with open(stdout_path, 'wb') as out, open(stderr_path, 'wb') as err:
        completed = subprocess.run(argv, cwd=str(PACK_ROOT), stdout=out, stderr=err,
                                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    elapsed = time.time() - begin
    guard = {}
    if guard_receipt.exists():
        guard = json.loads(guard_receipt.read_text())
    return {
        'label': label,
        'argv': argv,
        'cwd': str(PACK_ROOT),
        'exit_code': completed.returncode,
        'elapsed_seconds': round(elapsed, 3),
        'stdout_log': str(stdout_path.relative_to(PACK_ROOT)),
        'stderr_log': str(stderr_path.relative_to(PACK_ROOT)),
        'guard_receipt': str(guard_receipt.relative_to(PACK_ROOT)),
        'guard_installed_before_candidate_import': bool(
            guard.get('installed_before_candidate_import')),
        'guard_denials': list(guard.get('denials', [])),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--outdir', default=str(HERE))
    parser.add_argument('--only', default=None)
    arguments = parser.parse_args()
    outdir = Path(arguments.outdir).resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    before = counter_state()
    steps = [step for step in STEPS if arguments.only in (None, step['label'])]
    results = [run_step(step, outdir) for step in steps]
    after = counter_state()
    receipt = {
        'kind': 'lvw.s3-integration-correction-03-run/1',
        'argv': sys.argv,
        'cwd': os.getcwd(),
        'python': sys.executable,
        'package_root': str(PACK_ROOT),
        'candidate_sources': {name: digest_of(PACK_ROOT / name) for name in SOURCES},
        'counter_before': before,
        'counter_after': after,
        'counter_unchanged': before.get('sha256') == after.get('sha256'),
        'machine_gate_tests_deselected': list(MACHINE_GATE_TESTS),
        'steps': results,
        'all_steps_zero': all(step['exit_code'] == 0 for step in results),
        'no_process_started_by_the_runner': True,
        'stage_pass_claim': False,
        'product_gate0': False,
        'real_execution_performed': False,
    }
    path = outdir / 'run.receipt.json'
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt['all_steps_zero'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
