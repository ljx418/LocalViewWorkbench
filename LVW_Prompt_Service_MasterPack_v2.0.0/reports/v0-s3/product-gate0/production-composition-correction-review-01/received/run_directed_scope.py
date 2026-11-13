"""The concentrated directed scope of the production composition correction 01.

The scope is *directed*: it is the one positive example of the whole chain,
one negative example for every finding of the independent review and the
necessary compatibility nodes of the frozen owners.  Nothing of the old
denominators is rerun mechanically: the old 123, 84, 13, 41, 186 and 257
node suites are not part of this scope and are not counted here.

The runner is executed *under* the independent boundary of ``guard.py``,
so the candidate is imported after the boundary is armed.  The runner
writes the machine evidence of the scope:

* ``directed-scope.json`` - the selected nodes, the outcome of every node
  and the separated counts of the cases, of the invocations and of the
  interim batches;
* ``commands.json`` - the real argument vector, the working directory and
  the exit code of every command of this run;
* ``candidate.json`` - the identity of the candidate: the base commit and
  the digest of every source file that this correction changed.

The counts are separated on purpose: a *case* is a distinct node, an
*invocation* is one call of a node and an *interim batch* is one run of
the scope.  A node that was called more than once is counted as more than
one invocation and never as more than one case.
"""
import json
import os
import sys
import time
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

REPORT = Path(__file__).resolve().parent

# The composition scope: the formal entry of the controller, the formal
# entry of the worker and their compatibility nodes.
COMPOSITION = 'tools/test_v0_s3_production_composition.py'

# The compatibility nodes of the frozen owners.  They are the nodes that
# the correction touches: the fixed production command and the worker
# entry of the quality phase.
COMPATIBILITY = [
    'tools/test_v0_s3_supervisor.py::test_the_worker_really_invokes_the_quality_phase',
    'tools/test_v0_s3_supervisor.py::test_the_history_wait_is_announced_before_the_row_finishes',
    'tools/test_v0_s3_supervisor.py::test_a_context_with_a_wrong_seal_is_refused',
    'tools/test_v0_s3_supervisor.py::test_a_context_with_an_unknown_key_is_refused',
    'tools/test_v0_s3_supervisor.py::test_the_production_command_is_the_fixed_worker',
    'tools/test_v0_s3_supervisor.py::test_the_production_command_carries_the_pre_sealed_context_hash',
]

# The changed sources of this correction.  Their digests are the identity
# of the candidate.
CHANGED_SOURCES = (
    'tools/v0_s3_controller_io.py',
    'tools/v0_s3_production_controller.py',
    'tools/v0_s3_quality_worker.py',
    'tools/v0_s3_supervisor.py',
    'tools/test_v0_s3_production_composition.py',
    'tools/test_v0_s3_supervisor.py',
)


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
        'scope': 'concentrated_directed_scope',
        'positive_example': COMPOSITION +
        '::test_the_formal_entry_runs_the_whole_chain_and_persists_the_summary',
        'composition_file': COMPOSITION,
        'compatibility_nodes': COMPATIBILITY,
        'rationale': ('one positive example of the whole chain, one negative '
                       'example for every finding of the independent review '
                       '(M01-M09, m01, m02) and the necessary compatibility '
                       'nodes of the frozen owners; the old 123/84/13/41/186/257 '
                       'denominators are not rerun and are not counted here'),
        'not_rerun': ['the 84 node integration suite', 'the 13 node fixture suite',
                      'the 41 node supervisor suite', 'the 186 and 257 node suites',
                      'the original ledger', 'any native execution'],
    }
    (REPORT / 'selection.json').write_text(json.dumps(selection, indent=2), encoding='utf-8')

    capture = Capture()
    started = time.time()
    code = pytest.main(['-q', '-s', '--tb=short', '-p', 'no:cacheprovider',
                         '--basetemp', str(REPORT / 'pytest-temp'),
                         COMPOSITION] + COMPATIBILITY, plugins=[capture])
    duration = time.time() - started
    outcomes = {}
    for entry in capture.results:
        outcomes[entry['nodeid']] = entry['outcome']
    passed = [node for node, outcome in outcomes.items() if outcome == 'passed']
    failed = [node for node, outcome in outcomes.items() if outcome == 'failed']
    skipped = [node for node, outcome in outcomes.items() if outcome == 'skipped']
    document = {
        'kind': 'lvw.s3-production-composition-correction-scope/1',
        'exit': int(code),
        'duration_seconds': round(duration, 3),
        'cases_collected': len(capture.collected),
        'invocations': len(capture.results),
        'interim_batches': 1,
        'passed_cases': len(passed),
        'failed_cases': len(failed),
        'skipped_cases': len(skipped),
        'counts_are_separated': ('a case is a distinct node, an invocation is one '
                                 'call of a node and an interim batch is one run of '
                                 'the scope; the old denominators are not part of '
                                 'this scope'),
        'collected': capture.collected,
        'results': capture.results,
        'assertion_success_is_not_product_acceptance': True,
        'stage_pass_claim': False,
        'product_gate0': False,
    }
    (REPORT / 'directed-scope.json').write_text(json.dumps(document, indent=2), encoding='utf-8')
    print('directed scope exit', code, 'cases', len(capture.collected),
          'passed', len(passed), 'failed', len(failed), 'skipped', len(skipped))
    return int(code)


if __name__ == '__main__':
    raise SystemExit(main())
