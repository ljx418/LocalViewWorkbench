"""The concentrated directed scope of the production composition correction 02.

The scope is *directed* and it is one batch:

* the five open code findings of the independent review - M04, M05, M06,
  M07 and M08 - are driven one by one through the formal command line
  entry of the controller, through the real worker and through the final
  persistence;
* the one formal positive example of the whole chain - the real
  ``QualityPhase`` with its sixteen rows, the real pipe, the real parent
  reader, the real canonical receipt, the real manifest, the real facts
  and the real blocked summary - is inside the same composition file;
* the compatibility nodes of the frozen owners are the six nodes that the
  correction 01 already froze, because the worker context of the frozen
  owner changed with the declared anchors of the data references.

Nothing of the old denominators is rerun mechanically: the old 60, 71,
123, 84, 13, 41, 186, 257, 449 and 94 node suites are not part of this
scope and are not counted here.

The runner is executed *under* the independent boundary of ``guard.py``,
so the candidate is imported after the boundary is armed.  The runner
writes the machine evidence of the scope:

* ``directed-scope.json`` - the selected nodes, the outcome of every node
  and the separated counts of the cases, of the invocations and of the
  batches;
* ``selection.json`` - the exact selection of this batch;
* ``fd-thread-cleanup.json`` - the descriptors and the threads of the
  runner before and after the batch.

The counts are separated on purpose: a *case* is a distinct node, an
*invocation* is one call of a node and a *batch* is one run of the scope.
"""
import json
import os
import sys
import threading
import time
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

REPORT = Path(__file__).resolve().parent

# The composition scope: the formal entry of the controller, the formal
# entry of the worker, the five directed probes of the open findings and
# the compatibility nodes that the correction 01 already froze.
COMPOSITION = 'tools/test_v0_s3_production_composition.py'

COMPATIBILITY = [
    'tools/test_v0_s3_supervisor.py::test_the_worker_really_invokes_the_quality_phase',
    'tools/test_v0_s3_supervisor.py::test_the_history_wait_is_announced_before_the_row_finishes',
    'tools/test_v0_s3_supervisor.py::test_a_context_with_a_wrong_seal_is_refused',
    'tools/test_v0_s3_supervisor.py::test_a_context_with_an_unknown_key_is_refused',
    'tools/test_v0_s3_supervisor.py::test_the_production_command_is_the_fixed_worker',
    'tools/test_v0_s3_supervisor.py::test_the_production_command_carries_the_pre_sealed_context_hash',
]

# The five directed probes of the open findings and the one formal
# positive example of the whole chain.
DIRECTED = [
    'tools/test_v0_s3_production_composition.py::test_an_actual_worker_reference_is_read_through_its_anchor',
    'tools/test_v0_s3_production_composition.py::test_the_parsed_canonical_receipt_is_bound_to_the_bytes_that_were_hashed',
    'tools/test_v0_s3_production_composition.py::test_the_output_identity_of_the_run_is_bound_before_every_write',
    'tools/test_v0_s3_production_composition.py::test_a_formal_obligation_is_never_a_pass_of_a_synthetic_run',
    'tools/test_v0_s3_production_composition.py::test_an_ordinary_storage_failure_keeps_a_structured_unknown',
    'tools/test_v0_s3_production_composition.py::test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary',
]

# The changed sources of this correction.  Their digests are the identity
# of the candidate.
CHANGED_SOURCES = (
    'tools/v0_s3_controller_io.py',
    'tools/v0_s3_production_controller.py',
    'tools/v0_s3_quality_worker.py',
    'tools/test_v0_s3_production_composition.py',
    'tools/test_v0_s3_supervisor.py',
)


def _fd_snapshot():
    """The open descriptors of this process."""
    try:
        descriptor = os.open('/proc/self/fd', os.O_RDONLY)
    except OSError:
        return None
    try:
        names = os.listdir(descriptor)
    except OSError:
        return None
    finally:
        os.close(descriptor)
    return sorted(int(name) for name in names
                  if name.isdigit() and int(name) != descriptor)


class Capture:
    """The collector of the outcome of every node of the scope."""

    def __init__(self):
        self.collected = []
        self.results = []

    def pytest_collection_finish(self, session):
        self.collected = [item.nodeid for item in session.items]

    def pytest_runtest_logreport(self, report):
        if report.when == 'call' or report.failed:
            self.results.append({'nodeid': report.nodeid, 'when': report.when,
                                 'outcome': report.outcome,
                                 'duration': round(report.duration, 6),
                                 'longrepr': str(report.longrepr) if report.failed else None})


def main():
    import pytest
    selection = {
        'scope': 'concentrated_directed_scope_correction_02',
        'batches': 1,
        'positive_example': COMPOSITION +
        '::test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary',
        'directed_probes': DIRECTED,
        'composition_file': COMPOSITION,
        'compatibility_nodes': COMPATIBILITY,
        'rationale': ('the five open code findings of the independent review are '
                       'driven one by one through the formal entry, the one formal '
                       'positive example of the whole chain is inside the same '
                       'composition file, and the compatibility nodes of the frozen '
                       'owners are the six nodes that the correction 01 already '
                       'froze, because the worker context of the frozen owner changed '
                       'with the declared anchors of the data references; the old '
                       '60/71/123/84/13/41/186/257/449/94 denominators are not rerun '
                       'and are not counted here'),
        'not_rerun': ['the 60 node author suite', 'the 71 node review suite',
                      'the 84 node integration suite', 'the 13 node fixture suite',
                      'the 41 node supervisor suite', 'the 186 and 257 node suites',
                      'the 449 and 94 node compatibility batches',
                      'the original ledger', 'any native execution',
                      'any model, GPU, service, download or user media'],
    }
    (REPORT / 'selection.json').write_text(json.dumps(selection, indent=2), encoding='utf-8')

    fd_before = _fd_snapshot()
    threads_before = sorted(thread.name for thread in threading.enumerate())
    capture = Capture()
    started = time.time()
    code = pytest.main(['-q', '-s', '--tb=short', '-p', 'no:cacheprovider',
                         '--basetemp', str(REPORT / 'pytest-temp'),
                         COMPOSITION] + COMPATIBILITY, plugins=[capture])
    duration = time.time() - started
    fd_after = _fd_snapshot()
    threads_after = sorted(thread.name for thread in threading.enumerate())
    outcomes = {}
    for entry in capture.results:
        outcomes[entry['nodeid']] = entry['outcome']
    passed = [node for node, outcome in outcomes.items() if outcome == 'passed']
    failed = [node for node, outcome in outcomes.items() if outcome == 'failed']
    skipped = [node for node, outcome in outcomes.items() if outcome == 'skipped']
    document = {
        'kind': 'lvw.s3-production-composition-correction-scope/1',
        'correction': 'correction-02',
        'exit': int(code),
        'duration_seconds': round(duration, 3),
        'batches': 1,
        'cases_collected': len(capture.collected),
        'invocations': len(capture.results),
        'passed_cases': len(passed),
        'failed_cases': len(failed),
        'skipped_cases': len(skipped),
        'directed_probes_present': {node: any(item.startswith(node) for item in capture.collected)
                                    for node in DIRECTED},
        'counts_are_separated': ('a case is a distinct node, an invocation is one '
                                 'call of a node and a batch is one run of the scope; '
                                 'the old denominators are not part of this scope'),
        'collected': capture.collected,
        'results': capture.results,
        'assertion_success_is_not_product_acceptance': True,
        'stage_pass_claim': False,
        'product_gate0': False,
    }
    (REPORT / 'directed-scope.json').write_text(json.dumps(document, indent=2), encoding='utf-8')
    cleanup = {
        'kind': 'lvw.s3-production-composition-correction-cleanup/1',
        'fd_before': fd_before,
        'fd_after': fd_after,
        'fd_leaked': (sorted(set(fd_after) - set(fd_before))
                      if fd_before is not None and fd_after is not None else None),
        'threads_before': threads_before,
        'threads_after': threads_after,
        'threads_leaked': sorted(set(threads_after) - set(threads_before)),
        'only_the_main_thread_remains': threads_after == ['MainThread'],
        'stage_pass_claim': False,
        'product_gate0': False,
    }
    (REPORT / 'fd-thread-cleanup.json').write_text(json.dumps(cleanup, indent=2), encoding='utf-8')
    print('directed scope exit', code, 'cases', len(capture.collected),
          'passed', len(passed), 'failed', len(failed), 'skipped', len(skipped))
    return int(code)


if __name__ == '__main__':
    raise SystemExit(main())
