#!/usr/bin/env python3
"""The guarded runner of the S3-P4 originals correction 05.

Every entry of this batch runs **inside** the pre-import hard guard: the
audit hook of the guard is installed before pytest, before any plugin and
before any candidate module is imported, so neither the pytest startup, nor
a plugin, nor a candidate import can start a host process, open a socket,
open a sqlite database or touch the shared counter or the original ledger
of the batch.

The runner never masks an exit code and never reconstructs a log: the raw
stdout and stderr bytes are captured at the file descriptor level and the
true exit code is written next to them.  The log names of the entries are
their own; they never overwrite the log of another entry and they never
overwrite a historical log of an earlier round.  A log of an earlier
attempt of the same entry is **archived** before the new one is written,
so the raw streams of a failed attempt survive.

The counter of the batch is only read from the outside of the guard: the
runner hashes it before and after the batch and never writes it, never
refunds it and never creates a new one.  The binding runner of the batch
is not started here and the real thirteen scenario runs stay NOT_PROVEN.

The third entry is the **anti false green control**: the same new directed
nodes are run against the *old* source of the baseline
``b27b0d17b71371e37002aabc5f69a030872b9177`` in a separate scratch tree.
That entry has to fail: a zero exit code there would mean that the new
nodes do not test anything.

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
CONTROL_ROOT = Path('/tmp/lvw-oc05-control/LVW_Prompt_Service_MasterPack_v2.0.0')

SOURCES = ('tools/v0_s3_coordinator.py', 'tools/test_v0_s3_integration.py')

# The directed selection of this correction.  It is the narrow one: the
# obligations of the originals that the correction touches, plus the new
# nodes of the re-walk window, and nothing else.  The closed H, C, S and A
# suites, the 186, the 134 and the 257 node sets of the earlier rounds are
# not re-run here.
DIRECTED_NODES = [
    # the existing obligations of the originals that the correction touches
    'tools/test_v0_s3_integration.py::test_parent_seals_the_plan_and_the_originals',
    'tools/test_v0_s3_integration.py::test_parent_refuses_an_ancestor_link_out_of_the_bound_root',
    'tools/test_v0_s3_integration.py::test_parent_refuses_a_link_on_the_artifact_itself',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_changed_after_the_seal',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_was_replaced',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_vanished',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_a_replaced_root',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_ancestor_link_after_the_seal',
    'tools/test_v0_s3_integration.py::test_parent_refuses_a_foreign_or_changed_original',
    'tools/test_v0_s3_integration.py::test_parent_refuses_a_replaced_selected_root',
    'tools/test_v0_s3_integration.py::test_parent_refuses_an_incomplete_plan',
    # the closed read window obligations that must not reopen
    'tools/test_v0_s3_integration.py::test_the_seal_refuses_an_original_that_changes_during_the_read[same_length_rewrite]',
    'tools/test_v0_s3_integration.py::test_the_seal_refuses_an_original_that_changes_during_the_read[same_bytes_rewrite]',
    'tools/test_v0_s3_integration.py::test_the_seal_refuses_an_original_that_changes_during_the_read[growth]',
    'tools/test_v0_s3_integration.py::test_the_seal_refuses_an_original_that_changes_during_the_read[truncation]',
    'tools/test_v0_s3_integration.py::test_the_seal_refuses_an_original_that_changes_during_the_read[object_replacement]',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_changes_during_the_read[same_length_rewrite]',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_changes_during_the_read[same_bytes_rewrite]',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_changes_during_the_read[growth]',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_changes_during_the_read[truncation]',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_changes_during_the_read[object_replacement]',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_ancestor_that_is_replaced_during_the_read',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_a_root_that_is_replaced_during_the_read',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_a_path_that_became_a_link_during_the_read',
    # the closed fifo obligations that must not reopen
    'tools/test_v0_s3_integration.py::test_the_seal_refuses_a_fifo_without_a_writer_and_without_blocking',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_a_fifo_that_replaced_a_sealed_raw',
    'tools/test_v0_s3_integration.py::test_a_refused_original_leaks_no_descriptor',
    # the positive obligations of the originals
    'tools/test_v0_s3_integration.py::test_a_regular_original_has_its_real_hash_and_length',
    'tools/test_v0_s3_integration.py::test_the_size_bound_of_an_original_is_exact_and_one_over',
    'tools/test_v0_s3_integration.py::test_a_platform_without_the_safe_primitives_fails_closed',
    'tools/test_v0_s3_integration.py::test_a_failed_seal_publishes_no_originals',
    # the new obligations of the re-walk window of O1
    'tools/test_v0_s3_integration.py::test_the_seal_refuses_an_original_that_changes_during_the_rewalk[same_length_rewrite]',
    'tools/test_v0_s3_integration.py::test_the_seal_refuses_an_original_that_changes_during_the_rewalk[same_bytes_rewrite]',
    'tools/test_v0_s3_integration.py::test_the_seal_refuses_an_original_that_changes_during_the_rewalk[growth]',
    'tools/test_v0_s3_integration.py::test_the_seal_refuses_an_original_that_changes_during_the_rewalk[truncation]',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_changes_during_the_rewalk[same_length_rewrite]',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_changes_during_the_rewalk[same_bytes_rewrite]',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_changes_during_the_rewalk[growth]',
    'tools/test_v0_s3_integration.py::test_the_manifest_refuses_an_original_that_changes_during_the_rewalk[truncation]',
    'tools/test_v0_s3_integration.py::test_an_original_that_does_not_change_during_the_rewalk_is_accepted[seal]',
    'tools/test_v0_s3_integration.py::test_an_original_that_does_not_change_during_the_rewalk_is_accepted[manifest]',
]

# The nodes of the anti false green control: the eight new obligations of
# the re-walk window and their two positive controls.  They have to fail
# against the old source of the baseline.
CONTROL_NODES = [
    node for node in DIRECTED_NODES
    if 'during_the_rewalk' in node
]

STEPS = (
    {'label': 'owner-probe', 'entry': HERE / 'owner_probe.py', 'args': [],
     'cwd': PACK_ROOT, 'expect_failure': False},
    {'label': 'directed-originals', 'entry': HERE / 'pytest_entry.py',
     'args': ['-q', '-p', 'no:cacheprovider', '--no-header'] + DIRECTED_NODES,
     'cwd': PACK_ROOT, 'expect_failure': False},
    {'label': 'control-old-candidate', 'entry': HERE / 'pytest_entry.py',
     'args': ['-q', '-p', 'no:cacheprovider', '--no-header'] + CONTROL_NODES,
     'cwd': CONTROL_ROOT, 'expect_failure': True},
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


def control_binding():
    """The binding of the scratch tree of the anti false green control.

    The tree has to hold the *old* source of the baseline and the *new*
    test file of this correction.  Both facts are checked here and they
    are part of the receipt, so the control can not be a run of the new
    source by accident.
    """
    old_source = CONTROL_ROOT / 'tools/v0_s3_coordinator.py'
    new_test = CONTROL_ROOT / 'tools/test_v0_s3_integration.py'
    binding = {'root': str(CONTROL_ROOT), 'present': CONTROL_ROOT.is_dir()}
    if not binding['present']:
        return binding
    binding['old_source_sha256'] = digest_of(old_source)
    binding['test_file_sha256'] = digest_of(new_test)
    binding['candidate_test_sha256'] = digest_of(PACK_ROOT / 'tools/test_v0_s3_integration.py')
    binding['test_file_is_the_candidate_test'] = \
        binding['test_file_sha256'] == binding['candidate_test_sha256']
    binding['old_source_differs_from_the_candidate'] = \
        binding['old_source_sha256'] != digest_of(PACK_ROOT / 'tools/v0_s3_coordinator.py')
    return binding


def run_step(step, outdir):
    """Run one entry inside the guard and keep its raw streams.

    The logs of an earlier attempt are **archived, never overwritten**: a
    failed attempt keeps its own raw stdout, its own raw stderr and its
    own guard receipt, and the receipt of this run names the archive.
    """
    label = step['label']
    guard_receipt = outdir / (label + '.guard.json')
    stdout_path = outdir / (label + '.outer.stdout.log')
    stderr_path = outdir / (label + '.outer.stderr.log')
    archive = []
    for path in (stdout_path, stderr_path, guard_receipt):
        if path.exists():
            stamp = int(path.stat().st_mtime)
            archived = outdir / (label + '.archived-' + str(stamp) + '.' + path.name)
            path.rename(archived)
            archive.append(str(archived.relative_to(PACK_ROOT)))
    argv = [sys.executable, '-B', str(GUARD), str(step['entry']), str(guard_receipt)] \
        + [str(item) for item in step['args']]
    begin = time.time()
    with open(stdout_path, 'wb') as out, open(stderr_path, 'wb') as err:
        completed = subprocess.run(argv, cwd=str(step['cwd']), stdout=out, stderr=err,
                                   env=dict(os.environ, PYTHONDONTWRITEBYTECODE='1'))
    elapsed = time.time() - begin
    guard = {}
    if guard_receipt.exists():
        guard = json.loads(guard_receipt.read_text())
    exit_code = completed.returncode
    expected = (exit_code != 0) if step['expect_failure'] else (exit_code == 0)
    return {
        'label': label,
        'argv': argv,
        'cwd': str(step['cwd']),
        'exit_code': exit_code,
        'expect_failure': step['expect_failure'],
        'exit_code_as_expected': expected,
        'elapsed_seconds': round(elapsed, 3),
        'stdout_log': str(stdout_path.relative_to(PACK_ROOT)),
        'stderr_log': str(stderr_path.relative_to(PACK_ROOT)),
        'guard_receipt': str(guard_receipt.relative_to(PACK_ROOT)),
        'archived_logs_of_an_earlier_attempt': archive,
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
        'kind': 'lvw.s3-originals-correction-05-run/1',
        'argv': sys.argv,
        'cwd': os.getcwd(),
        'python': sys.executable,
        'package_root': str(PACK_ROOT),
        'candidate_sources': {name: digest_of(PACK_ROOT / name) for name in SOURCES},
        'report_files': {path.name: digest_of(path) for path in sorted(HERE.glob('*.py'))},
        'counter_before': before,
        'counter_after': after,
        'counter_unchanged': before.get('sha256') == after.get('sha256'),
        'counter_written_by_this_runner': False,
        'binding_runner_started': False,
        'control_binding': control_binding(),
        'directed_nodes': DIRECTED_NODES,
        'control_nodes': CONTROL_NODES,
        'steps': results,
        'all_steps_as_expected': all(step['exit_code_as_expected'] for step in results),
        'all_steps_zero': all(step['exit_code'] == 0 for step in results),
        'guard_denied_nothing': all(not step['guard_denials'] for step in results),
        'stage_pass_claim': False,
        'product_gate0': False,
        'real_execution_performed': False,
    }
    path = outdir / 'run.receipt.json'
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt['all_steps_as_expected'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
