#!/usr/bin/env python3
"""Read-only governance checks; eligibility is not evidence or product PASS."""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
TRUE_FIELDS = ('missing_detail_only', 'canonical_result_verified', 'cleanup_verified',
               'binding_verified', 'authorization_verified', 'original_error_preserved',
               'raw_results_preserved', 'does_not_change_product_contract', 'not_product_owner')
FALSE_FIELDS = ('false_green_risk', 'product_safety_impact', 'unknown_cleanup',
                'missing_required_result', 'fixed_set_drift', 'authority_bypass',
                'implementation_self_approval')
HARD_BLOCKERS = {'product_safety_or_privacy', 'resource_or_file_cleanup_unknown',
                 'false_green_or_missing_required_result', 'fixed_set_or_threshold_drift',
                 'candidate_or_evidence_identity_unverified', 'authorization_or_budget_boundary',
                 'production_entry_bypass', 'required_human_signature_absent'}


def minor_review_eligible(finding):
    """Only proposes independent review; callers must verify every fact."""
    return (finding.get('affected_layer') == 'auxiliary_diagnostic'
            and finding.get('run_state') == 'FAIL'
            and all(finding.get(k) is True for k in TRUE_FIELDS)
            and all(finding.get(k) is False for k in FALSE_FIELDS))


def negative_checks():
    valid = {'affected_layer': 'auxiliary_diagnostic', 'run_state': 'FAIL',
             **{k: True for k in TRUE_FIELDS}, **{k: False for k in FALSE_FIELDS}}
    rows = [('fully_proved_auxiliary_failure_only', minor_review_eligible(valid))]
    for key in TRUE_FIELDS + FALSE_FIELDS:
        bad = dict(valid)
        bad[key] = not bad[key]
        rows.append(('reject_' + key, not minor_review_eligible(bad)))
        del bad[key]
        rows.append(('reject_missing_' + key, not minor_review_eligible(bad)))
    for state in ('PASS', 'BLOCKED', 'NOT_RUN', 'UNKNOWN'):
        rows.append(('reject_state_' + state,
                     not minor_review_eligible(dict(valid, run_state=state))))
    rows.append(('reject_product_owner', not minor_review_eligible(
        dict(valid, affected_layer='production'))))
    rows.append(('reject_truthy_string', not minor_review_eligible(
        dict(valid, cleanup_verified='true'))))
    rows.append(('reject_empty', not minor_review_eligible({})))
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    rows = []
    def check(name, value):
        rows.append((name, bool(value)))
    def read(name):
        return json.loads((ROOT / name).read_text(encoding='utf-8'))
    try:
        policy = read('plans/v1-delivery-workflow.json')
        approval = read(policy['approval'])
        base = read('reports/workflow-rebaseline-2026-11-15/baseline.json')
        coordinate = read('plans/execution-control.json')
        plan = read('plans/v1-revised-plan.json')
        dev = read('plans/v1-workpack-development-map.json')
        packet = read(policy['next_packet'])
        check('user_approval', approval['decision'] == 'APPROVED_BY_USER'
              and approval['change_id'] == policy['change_id'] == packet['change_id'])
        check('version', policy['schema_version'] == 'lvw.delivery-flow/1')
        check('fixed_component189', policy['scope']['fixed_component_node_count'] == 189
              and packet['full_checkpoint_node_count'] == 189)
        check('fixed_product29', policy['scope']['fixed_v1_case_count'] == 29
              and len(plan['v1_required_cases']) == len(set(plan['v1_required_cases'])) == 29)
        check('no_budget_reset', policy['scope']['budget_reset'] is False)
        check('all_hard_blockers', set(policy['hard_blockers']) == HARD_BLOCKERS)
        rule = policy['auxiliary_minor_eligibility']
        check('all_required_positive_facts', tuple(rule['required_true']) == TRUE_FIELDS)
        check('all_forbidden_impacts', tuple(rule['required_false']) == FALSE_FIELDS)
        check('unknown_fail_closed', rule['on_missing_or_unknown'] == 'BLOCKING_UNTIL_PROVEN')
        check('no_self_certification', rule['decision'] == 'ELIGIBLE_FOR_INDEPENDENT_MINOR_REVIEW_ONLY'
              and rule['historical_major_auto_close'] is False)
        for name, digest in base['immutable_pins'].items():
            target = ROOT / name
            check('immutable:' + name, target.is_file()
                  and hashlib.sha256(target.read_bytes()).hexdigest() == digest)
        check('policy_pins_equal_baseline', policy['immutable_pins'] == base['immutable_pins'])
        adoption_phase = coordinate.get('delivery_rebaseline', {}).get('phase')
        check('adoption_phase_declared', adoption_phase in
              ('DOCUMENT_PREPARATION', 'SCOPED_EXECUTION'))
        # Initial documentation work cannot claim product progress. Later actual
        # progress belongs to product receipts, not this policy snapshot checker.
        if adoption_phase == 'DOCUMENT_PREPARATION':
            check('stage_id_unchanged', coordinate['coordinate']['stage_id']
                  == base['product_coordinate_before']['stage_id'])
            check('progress_not_inflated', coordinate['development_outline']
                  == base['development_outline_before'])
        check('same_formal_stage_dag', policy['formal_stage_dependencies_unchanged'] is True
              and dev['formal_stage_dag_unchanged'] is True)
        check('base_plan_bound', dev['base_plan_sha256']
              == base['immutable_pins'][dev['base_plan']])
        check('no_runtime_granted_by_docs', policy['scope']['product_runtime_authorized'] is False
              and packet['runtime_authorized'] is False and packet['targeted_execution_ack'] is None)
        check('guard_before_import', policy['execution_boundaries']['root_ack_before_any_candidate_import'] is True
              and policy['execution_boundaries']['guard_before_candidate_and_plugins'] is True)
        check('targeted_not_full_checkpoint', policy['execution_boundaries']['targeted_results_never_count_as_full189'] is True)
        check('single_stage_writer', dev['one_active_implementation_stage'] is True)
        check('policy_bound_by_packet', packet['policy_sha256'] == hashlib.sha256(
            (ROOT / packet['policy']).read_bytes()).hexdigest())
        component_dir = (ROOT / policy['next_packet']).parent
        for row in (component_dir / 'PAYLOAD_MANIFEST.sha256').read_text().splitlines():
            digest, name = row.split('  ', 1)
            check('component_manifest:' + name, name in
                  ('contract.json', 'obligation-review.json') and hashlib.sha256(
                      (component_dir / name).read_bytes()).hexdigest() == digest)
        steps = policy['workpack_route']
        seen = set()
        for step in steps:
            check('ordered_dependencies:' + step['id'], set(step['depends_on']) <= seen)
            check('unique_workpack:' + step['id'], step['id'] not in seen)
            seen.add(step['id'])
        for path in (policy['adr'], policy['approval'], policy['next_packet'],
                     'docs/36_DELIVERY_WORKFLOW_REBASELINE.md'):
            check('reference:' + path, (ROOT / path).is_file())
        if args.self_test:
            rows.extend(negative_checks())
    except (OSError, ValueError, KeyError, TypeError) as error:
        rows.append(('INPUT_ERROR:' + str(error), False))
    failed = [name for name, okay in rows if not okay]
    print(json.dumps({'kind': 'GOVERNANCE_STRUCTURE_NOT_PRODUCT_ACCEPTANCE',
                      'checks': len(rows), 'passed': len(rows) - len(failed),
                      'failed': len(failed), 'errors': failed,
                      'candidate_or_runtime_executed': False,
                      'historical_finding_closed': False}, ensure_ascii=False, indent=2))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
