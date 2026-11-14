"""The static implementation receipt of the correction 17.

The script is **static**: it reads the artifacts of this delivery and it
writes the receipt.  It never imports, collects or executes a module.

Usage::

    python3 -I static_implementation_receipt.py <package-root> <output.json>
"""
import hashlib
import json
import sys
from pathlib import Path

REPORT_DIR = ('reports/v0-s3/product-gate0/'
              'implementation-native-custody-correction-17')
ARTIFACTS = (
    'design.md',
    'design-receipt.json',
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


def main(root, output):
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
    candidate = pins['pins']['tools/test_v0_s3_native_custody_correction10.py']
    receipt = {
        'kind': 'lvw.s3-native-custody-correction17-static-implementation-receipt/1',
        'coordinate': 'V1/R1/WP-R1-U3/S3_P4',
        'candidate_base_sha': '4dafa1f316242d8bd348b81c52f375aa37254754',
        'candidate_sha': candidate['after']['sha256'],
        'candidate_sha_note': 'the sha256 of the candidate module '
                              'tools/test_v0_s3_native_custody_correction10.py '
                              'in the committed candidate; the sha of the '
                              'commit is frozen by the root',
        'design': {
            'file': 'reports/v0-s3/product-gate0/'
                    'implementation-native-custody-correction-17/design.md',
            'approved_by_root': True,
            'addendum': 'the correction addendum of the root review D1-D5 '
                        '(design.md section 10) is authoritative over the '
                        'sections it supersedes',
        },
        'changed_files': pins['changed_files'],
        'unchanged_files': pins['unchanged_files'],
        'candidate_module': {
            'path': 'tools/test_v0_s3_native_custody_correction10.py',
            'before': candidate['before'],
            'after': candidate['after'],
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
                    'implementation-native-custody-correction-17/'
                    'static-checks.json',
        },
        'validation_plan_request': {
            'file': 'reports/v0-s3/product-gate0/'
                    'implementation-native-custody-correction-17/'
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
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
