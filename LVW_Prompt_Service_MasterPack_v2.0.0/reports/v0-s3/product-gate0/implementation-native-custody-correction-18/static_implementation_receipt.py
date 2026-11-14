"""The static implementation receipt of the correction 18.

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
              'implementation-native-custody-correction-18')
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
        'kind': 'lvw.s3-native-custody-correction18-static-implementation-receipt/1',
        'coordinate': 'V1/R1/WP-R1-U3/S3_P4',
        'candidate_base_sha': '058ee9ff0020a1485ee57ddafe23a1d390159c4a',
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
            'delta_of_correction_18': 'the implementation of the exact '
                                      'residual defects M2 1-5 and M3 1-7 '
                                      'of the independent review of the '
                                      'correction 17; no new generic '
                                      'framework and no new product '
                                      'obligation',
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
            'changed': False,
        },
        'static_checks': {
            'total': checks['total'],
            'failed': len(checks['failed']),
            'ok': checks['ok'],
            'file': 'reports/v0-s3/product-gate0/'
                    'implementation-native-custody-correction-18/'
                    'static-checks.json',
        },
        'validation_plan_request': {
            'file': 'reports/v0-s3/product-gate0/'
                    'implementation-native-custody-correction-18/'
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
