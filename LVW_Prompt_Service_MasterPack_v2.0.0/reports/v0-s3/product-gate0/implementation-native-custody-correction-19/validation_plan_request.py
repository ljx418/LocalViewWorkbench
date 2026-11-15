"""The frozen validation plan REQUEST of the correction 19.

The script is **static**: it reads the identity of the nodes and the
pins of the sources and it writes the request of the finite validation.
It never imports, collects or executes a module.

Usage::

    python3 -I validation_plan_request.py <package-root> <output.json>
"""
import hashlib
import json
import sys
from pathlib import Path

REPORT_DIR = ('reports/v0-s3/product-gate0/'
              'implementation-native-custody-correction-19')
WORKSPACE = ('/home/administrator/orca/workspaces/LocalViewWorkbench/'
             'lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0')
PACKAGE = ('/mnt/c/workspace/videoworkline/localviewworkbench/'
           'LVW_Prompt_Service_MasterPack_v2.0.0')
FROZEN_TOOLS = PACKAGE + ('/reports/v0-s3/product-gate0/'
                           'native-custody-correction-14/validation-plan-01')


def main(root, output):
    root = Path(root)
    identity = json.loads((root / REPORT_DIR / 'node-identity.json')
                          .read_text(encoding='utf-8'))
    pins = json.loads((root / REPORT_DIR / 'source-pins.json')
                      .read_text(encoding='utf-8'))
    nodeids = identity['denominator']['frozen_order']
    sourcepins = {name: item['after']['sha256']
                  for name, item in pins['pins'].items()}
    environment = {
        'LVW_N1_F5_EVIDENCE_DIR': WORKSPACE + '/' + REPORT_DIR + '/f5-evidence',
        'PYTHONDONTWRITEBYTECODE': '1',
    }
    attempt = WORKSPACE + '/' + REPORT_DIR + '/attempt01'
    commands = [
        {'label': 'counter-absence-before',
         'argv': ['/usr/bin/python3.12', '-I', '-B',
                  FROZEN_TOOLS + '/outer_counter_observe.py',
                  '/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json',
                  attempt + '/counter-absence-before.json'],
         'cwd': WORKSPACE,
         'environment': dict(environment)},
        {'label': 'guarded-validation',
         'argv': ['/usr/bin/python3.12', '-I', '-B',
                  FROZEN_TOOLS + '/guard.py',
                  FROZEN_TOOLS + '/runner.py',
                  attempt + '/native-custody-correction-18.guard.json'],
         'cwd': WORKSPACE,
         'environment': dict(environment)},
        {'label': 'counter-absence-after',
         'argv': ['/usr/bin/python3.12', '-I', '-B',
                  FROZEN_TOOLS + '/outer_counter_observe.py',
                  '/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json',
                  attempt + '/counter-absence-after.json'],
         'cwd': WORKSPACE,
         'environment': dict(environment)},
    ]
    document = {
        'kind': 'lvw.s3-native-custody-frozen-validation-plan-request/1',
        'coordinate': 'V1/R1/WP-R1-U3/S3_P4',
        'workpack': 'WP-R1-U3',
        'stage': 'S3_P4_OFFLINE_INTEGRATION_PREPARATION',
        'gate': 'S3_P4_N1_CORRECTION19_STATIC_RESIDUALS',
        'candidate_base_sha': '208f0c604345fd417f98f3a86e5a65835179d175',
        'candidate_git_commit': 'FROZEN_BY_THE_ROOT_AFTER_THIS_DELIVERY',
        'request_note': (
            'This is a REQUEST and not an execution.  Nothing of this '
            'plan was run: the candidate was never imported, never '
            'collected, never executed with pytest and no native call, '
            'no operating system business process, no model, no GPU, no '
            'service, no network, no medium, no database, no ledger and '
            'no counter was touched.  The root freezes the plan (the '
            'pins, the node ids and the order) and ACKs it before any '
            'command of it may run.'),
        'real_execution_performed': False,
        'admission_produced': False,
        'batches_max': 1,
        'max_seconds': 300,
        'node_count': len(nodeids),
        'node_order_is_binding': True,
        'nodeids': nodeids,
        'nodeids_note': (
            'The 189 frozen node ids in their frozen order.  The order is '
            'binding: the frozen runner refuses the batch when the '
            'collected order differs.  No node was added, no node was '
            'removed, no node was renamed and no node was skipped.'),
        'commands': commands,
        'commands_note': (
            'Only these three absolute argv with the explicitly bound '
            'per-command environment.  One batch of at most 300 s.  No '
            'wrapper, no extra test, no rerun, no fourth command and no '
            'rerun of the failed batch of the correction 13, 14, 15, 16 '
            'or 17.  The three residuals of the correction 19 run inside '
            'these 189 nodes: the public zero expiry and the retention '
            'oracle of N10-R07, the evidence of the barrier and the phase '
            'inventory of N10-R10 and the registry, the drain and the '
            'unwinding of the owners of the fixture of N10-R07.'),
        'cwd': WORKSPACE,
        'environment': environment,
        'report_dir': WORKSPACE + '/' + REPORT_DIR,
        'preparation_dir': attempt,
        'dependency_root': PACKAGE,
        'dependency_pins': sourcepins,
        'dependency_pins_count': len(sourcepins),
        'sourcepins': sourcepins,
        'sourcepins_count': len(sourcepins),
        'sourcepins_note': (
            'The pins of the seven sources of the denominator and of the '
            'production.  Only the test module of the correction 10 '
            'changed; the two production sources and the four other test '
            'modules are byte identical to the baseline '
            '208f0c604345fd417f98f3a86e5a65835179d175.'),
        'integrity_only_nodes': [],
        'f5_evidence': WORKSPACE + '/' + REPORT_DIR + '/f5-evidence',
        'external_guard': {
            'tool': FROZEN_TOOLS + '/guard.py',
            'tool_sha256': hashlib.sha256(
                Path(FROZEN_TOOLS + '/guard.py').read_bytes()).hexdigest(),
            'note': 'The guard is the frozen one of the correction 14; it '
                    'is not modified by the correction 19.',
        },
        'counter': {
            'policy': 'LSTAT_ONLY_ABSENCE_MODE_OUTSIDE_THE_GUARDED_BATCH',
            'path': '/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json',
            'observed_before_the_batch_by': 'outer_counter_observe.py',
            'observed_after_the_batch_by': 'outer_counter_observe.py',
            'counter_content_read': False,
            'counter_created': False,
            'counter_written': False,
            'counter_reset': False,
            'counter_refunded': False,
            'new_counter_created': False,
            'historical_counter_continuity': 'UNAVAILABLE_NOT_PROVEN',
            'old_grant': 'EXPIRED_NO_REPLAY',
            'note': 'The absence mode of the correction 08 is inherited as '
                    'it is.  The outer observation only lstats the exact '
                    'counter and its parent and it requires both of them '
                    'to be MISSING.',
        },
        'counter_missing_limitation': (
            'The old temporary historical fixture counter is gone.  Two '
            'exact metadata observations prove continued absence only; '
            'they do not prove historical content continuity, a ledger '
            'balance or a revived grant.'),
        'stop_rules': [
            'The first HTTP 429 of any command stops the batch '
            'immediately: the state is WAIT_BUDGET, the batch is not '
            'retried, no other route is taken and the root does not take '
            'the batch over.',
            'The first refusal or the first timeout of an approval stops '
            'the batch: there is no bypass and no configuration change.',
            'A failing batch is recorded as it is: the failures are '
            'reported and the batch is not rerun.',
        ],
        'failure_policy': (
            'The batch is one attempt.  A failure is reported with the '
            'receipt of the attempt; it is never hidden by a summary and '
            'it is never replaced by a rerun.'),
        'not_proven': [
            'native_execution_proven',
            'native_cleanup_proven',
            'gpu_released_proven',
            'port_released_proven',
            'production_released_proven',
            'stage_pass',
        ],
        'stage_pass_claim': False,
        'product_gate0': False,
        'grant_authority': 'NOT_VERIFIED',
        'trusted_tools': [
            FROZEN_TOOLS + '/guard.py',
            FROZEN_TOOLS + '/runner.py',
            FROZEN_TOOLS + '/outer_counter_observe.py',
        ],
        'observations_before_the_batch': [
            'the git status of the worktree is clean except for the '
            'delivery of this correction',
            'the pins of the seven sources match the pins of this request',
            'the identity of the 189 nodes matches the identity of this '
            'request',
        ],
    }
    Path(output).write_text(json.dumps(document, indent=1, sort_keys=True),
                             encoding='utf-8')
    print(json.dumps({'node_count': len(nodeids),
                      'commands': len(commands),
                      'max_seconds': document['max_seconds'],
                      'batches_max': document['batches_max']},
                     sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
