"""The static implementation receipt of the correction 19.

The script is **static**: it reads the artifacts of this delivery and it
writes the receipt.  It never imports, collects or executes a module.

The receipt names the **actual** Git identity of the candidate and the
``source_sha256`` of the changed module.  A content hash is never called
``candidate_sha``: the Git commit is the identity of the candidate and
the sha256 is the identity of the **source**.

Usage::

    python3 -I static_implementation_receipt.py <package-root> \
        <candidate-git-commit> <output.json>
"""
import hashlib
import json
import sys
from pathlib import Path

REPORT_DIR = ('reports/v0-s3/product-gate0/'
              'implementation-native-custody-correction-19')
ARTIFACTS = (
    'implementation-boundary-checklist.md',
    'report.md',
    'static_checks.py',
    'static-checks.json',
    'node_identity.py',
    'node-identity.json',
    'source_pins.py',
    'source-pins.json',
    'validation_plan_request.py',
    'validation-plan-request.json',
)


def digest(path):
    data = Path(path).read_bytes()
    return {'sha256': hashlib.sha256(data).hexdigest(),
            'bytes': len(data),
            'lines': data.count(b'\n')}


#: The mapping of EVERY counterexample of the independent review of the
#: correction 18: the trigger, the exact boundary of the candidate and
#: the static check that reads it.
COUNTEREXAMPLES = (
    {'id': 'R1', 'review': 'root check',
     'trigger': 'the first channel of the registry is the channel of the '
                'parent and it is never the child',
     'boundary': 'controlled_custody_channel() selects the entry named '
                 'controlled:channel and proves that it differs from '
                 'controlled_parent_channel',
     'static_check': 'm3-1:the-child-is-named'},
    {'id': 'R2', 'review': 'root check',
     'trigger': 'a failed terminal write advances the ledger',
     'boundary': 'every ledger.pass_/ledger.fail/ledger.finish follows a '
                 'successful terminal write; a failed write leaves the '
                 'name ATTEMPTED for the bounded recovery',
     'static_check': 'm2-1:every-terminal-transition-is-write-guarded'},
    {'id': 'R3', 'review': 'root check',
     'trigger': 'the coordination try begins after the start',
     'boundary': 'the cleanup owning Try contains the construction of the '
                 'endpoint and reader.start() in its body and owns the '
                 'close and the drain in its finally',
     'static_check': 'm3-4:the-endpoint-is-inside-the-cleanup-try'},
    {'id': 'M2.1', 'review': '18-M2.1',
     'trigger': 'a failed terminal persistence advances the ledger and '
                'suppresses the recovery',
     'boundary': 'record_guarded returns None and the caller advances the '
                 'ledger only when the result is not None; the outer '
                 'inventory recovers the ATTEMPTED names once',
     'static_check': 'm2-1:every-terminal-transition-is-write-guarded'},
    {'id': 'M2.2', 'review': '18-M2.2',
     'trigger': 'the early barrier persistence diagnostics disappear',
     'boundary': 'the final document of the phase and the rewrite of the '
                 'barrier document carry barrier_persisted, '
                 'barrier_write_error and the identity of the original '
                 'object',
     'static_check': 'm2-2:the-final-document-carries-barrier_persisted'},
    {'id': 'M2.3', 'review': '18-M2.3',
     'trigger': 'the earlier coordination records PASSED before its '
                'cleanup and never records the cleanup diagnostics',
     'boundary': 'the terminal document of r10-coordination and the '
                 'terminal document of r10-early-salvage are written in '
                 'the finally that owns the drain',
     'static_check': 'm2-3:the-early-verdict-is-after-the-cleanup'},
    {'id': 'M2.4', 'review': '18-M2.4',
     'trigger': 'a nonquiescent drain yields a durable FAIL while the '
                'test continues successfully',
     'boundary': 'the drain returns a proof failure when it is not '
                 'quiescent and every caller requires the quiescence',
     'static_check': 'm2-4:the-drain-fails-on-a-nonquiescent-round'},
    {'id': 'M3.1', 'review': '18-M3.1',
     'trigger': 'the constructor failure driver is unreachable because '
                'the custody lookup returns the parent channel',
     'boundary': 'the exact newly retained child is selected, the identity '
                 'of the target owner is compared with it and the original '
                 'Thread.start is called before the exact failure is '
                 'raised inside the constructor',
     'static_check': 'm3-1:the-child-differs-from-the-parent'},
    {'id': 'M3.2', 'review': '18-M3.2',
     'trigger': 'one container query aborts the traversal and replaces '
                'the owners with an empty list',
     'boundary': 'every query of the registry, of the container, of the '
                 'session, of the channel and of the provenance is '
                 'guarded on its own and the observed thread objects are '
                 'retained as an independent fallback',
     'static_check': 'm3-2:the-traversal-is-guarded-per-query'},
    {'id': 'M3.3', 'review': '18-M3.3',
     'trigger': 'the cancellation identity is replaced, lost or never '
                'rethrown',
     'boundary': 'every caller keeps the exact object and rethrows it '
                 'before the ordinary proof assertion',
     'static_check': 'm3-3:the-cancellation-wins'},
    {'id': 'M3.4', 'review': '18-M3.4',
     'trigger': 'the independent coordination start and constructor '
                'failure bypass its cleanup',
     'boundary': 'the cleanup owning Try starts before the construction '
                 'and before reader.start() and owns the close, the join '
                 'and the drain',
     'static_check': 'm3-4:the-cleanup-try-owns-the-drain'},
    {'id': 'M3.5', 'review': '18-M3.5',
     'trigger': 'the main child cleanup catches only Exception and a '
                'cancellation skips the second close',
     'boundary': 'every close of the child endpoint catches BaseException '
                 'and records the exact cancellation',
     'static_check': 'm3-5:no-close-is-exception-only'},
    {'id': 'M3.6', 'review': '18-M3.6',
     'trigger': 'some finalizers record the quiescence without enforcing '
                'it',
     'boundary': 'the quiescence is part of the proof of the caller and a '
                 'nonquiescent round is a proof failure of the drain',
     'static_check': 'm2-4:the-quiescence-is-enforced-everywhere'},
)


def main(root, candidate, output):
    root = Path(root)
    report = root / REPORT_DIR
    checks = json.loads((report / 'static-checks.json').read_text(
        encoding='utf-8'))
    identity = json.loads((report / 'node-identity.json').read_text(
        encoding='utf-8'))
    pins = json.loads((report / 'source-pins.json').read_text(
        encoding='utf-8'))
    plan = json.loads((report / 'validation-plan-request.json').read_text(
        encoding='utf-8'))
    artifacts = {name: digest(report / name) for name in ARTIFACTS}
    module = pins['pins']['tools/test_v0_s3_native_custody_correction10.py']
    receipt = {
        'kind': 'lvw.s3-native-custody-correction19-static-implementation-receipt/1',
        'coordinate': 'V1/R1/WP-R1-U3/S3_P4',
        'candidate_base_sha': '208f0c604345fd417f98f3a86e5a65835179d175',
        'candidate_git_commit': candidate,
        'candidate_git_commit_note': 'the actual Git identity of the '
                                     'committed static candidate of this '
                                     'correction',
        'source_sha256': module['after']['sha256'],
        'source_sha256_note': 'the sha256 of the CONTENT of the changed '
                              'module tools/test_v0_s3_native_custody_'
                              'correction10.py in the committed candidate; '
                              'it is a content hash and it is never called '
                              'candidate_sha',
        'candidate_sha': 'NOT_USED_A_CONTENT_HASH_IS_NOT_A_CANDIDATE_IDENTITY',
        'design': {
            'file': 'reports/v0-s3/product-gate0/'
                    'implementation-native-custody-correction-17/design.md',
            'approved_by_root': True,
            'authoritative_section': 'section 10 (the correction addendum '
                                     'of the root review D1-D5) and the '
                                     'binding clarifications 1-6 of the '
                                     'root design ACK',
            'delta_of_correction_19': 'the implementation of the exact '
                                      'residual defects M2 1-4 and M3 1-6 '
                                      'of the independent review of the '
                                      'correction 18 and of the three root '
                                      'checks; no new generic framework and '
                                      'no new product obligation',
            'independent_review': 'reports/v0-s3/product-gate0/'
                                   'native-custody-correction-18/test-review-01/'
                                   'review-result',
        },
        'changed_files': pins['changed_files'],
        'unchanged_files': pins['unchanged_files'],
        'candidate_module': {
            'path': 'tools/test_v0_s3_native_custody_correction10.py',
            'before': module['before'],
            'after': module['after'],
        },
        'denominator': {
            'count': identity['denominator']['count'],
            'unique': identity['denominator']['unique'],
            'frozen_order': True,
            'order_unchanged': identity.get('order_unchanged'),
            'order_reference': identity.get('order_reference'),
            'changed': False,
        },
        'assertion_equivalence': {
            'baseline_total': checks['assertion_equivalence']['baseline_total'],
            'candidate_total': checks['assertion_equivalence']['candidate_total'],
            'removed': checks['assertion_equivalence']['removed'],
            'added': checks['assertion_equivalence']['added'],
            'note': 'No predicate of the baseline of the correction 18 is '
                    'removed.  The seven added predicates are the checks of '
                    'the residual defects of the independent review of the '
                    'correction 18; none of them replaces an oracle of the '
                    'baseline.',
        },
        'counterexample_mapping': COUNTEREXAMPLES,
        'static_checks': {
            'total': checks['total'],
            'failed': len(checks['failed']),
            'ok': checks['ok'],
            'file': 'reports/v0-s3/product-gate0/'
                    'implementation-native-custody-correction-19/'
                    'static-checks.json',
        },
        'validation_plan_request': {
            'file': 'reports/v0-s3/product-gate0/'
                    'implementation-native-custody-correction-19/'
                    'validation-plan-request.json',
            'commands': len(plan['commands']),
            'batches_max': plan['batches_max'],
            'max_seconds': plan['max_seconds'],
            'node_count': plan['node_count'],
            'requested_not_executed': True,
        },
        'artifacts': artifacts,
        'execution_audit': {
            'candidate_import': False,
            'candidate_collect': False,
            'pytest': False,
            'ctypes': False,
            'runtime_probe': False,
            'native_call': False,
            'os_business_process': False,
            'model_gpu': False,
            'service_network': False,
            'media_db': False,
            'ledger_counter': False,
            'candidate_executed': False,
            'methods_used': [
                'text reads of the seven sources of the denominator',
                'ast.parse of the five test modules and of the two '
                'production sources',
                'symtable of the edited module (the global names that it '
                'reads)',
                'in-memory compile of the edited module',
                'sha256 of the sources and of the artifacts',
                'read-only git show of the baseline blobs',
            ],
            '429_or_approval_refusal': False,
        },
        'non_claims': {
            'major_closure_claimed': False,
            'stage_pass': False,
            'native': 'NOT_PROVEN',
            'dynamic15': 'NOT_RUN',
            'dynamic16': 'NOT_RUN',
            'dynamic17': 'NOT_RUN',
            'dynamic18': 'NOT_RUN',
            'dynamic19': 'NOT_RUN',
            'product_acceptance': False,
            'human_signoff': False,
            'runtime_plan_acked': False,
            'candidate_executed': False,
        },
    }
    Path(output).write_text(json.dumps(receipt, indent=1, sort_keys=True),
                             encoding='utf-8')
    print(json.dumps({'static_checks': receipt['static_checks'],
                      'denominator': receipt['denominator']['count'],
                      'artifacts': len(artifacts)}, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1], sys.argv[2], sys.argv[3]))
