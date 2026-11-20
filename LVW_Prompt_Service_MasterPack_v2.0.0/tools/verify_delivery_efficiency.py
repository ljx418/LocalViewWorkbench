#!/usr/bin/env python3
"""Validate the approved workflow/roadmap overlay, never product readiness."""
from pathlib import Path
import argparse
import copy
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
SPEC='.agent-governance/workflows/delivery-efficiency.spec.json'
PLAN='plans/v1-execution-roadmap.json'


def validate(spec,plan):
    errors=[]
    def need(ok,code):
        if not ok:errors.append(code)
    need(spec.get('status')=='ACTIVE_APPROVED','SPEC_NOT_APPROVED')
    need(spec.get('coordinate_authority')=='plans/execution-control.json','SECOND_AUTHORITY')
    roles=spec.get('roles',{})
    need(roles.get('architect_and_gate')=='Codex' and roles.get('implementation')=='visible ClaudeCode','ROLE_DRIFT')
    need(roles.get('independent_review')!=roles.get('implementation') and 'isolated' in roles.get('independent_review',''),'SELF_REVIEW')
    limits=spec.get('limits',{})
    need(limits.get('agents_per_workspace')==1 and limits.get('agents_per_project')==3 and limits.get('one_product_stage') is True,'WIP_DRIFT')
    need(spec.get('formal_pins')=={'component_nodes':189,'v1_cases':29,'stage_dag_unchanged':True,'human_signatures_retained':True,'budget_reset':False},'FORMAL_GATE_DRIFT')
    need(spec.get('quota429','').startswith('STOP immediately'),'429_RULE_MISSING')
    need(spec.get('runner_convergence',{}).get('no_general_agent_platform') is True,'PLATFORM_SCOPE_CREEP')
    need(plan.get('formal_stage_dag_unchanged') is True and plan.get('one_active_implementation_stage') is True,'STAGE_DAG_DRIFT')
    seen=set()
    for row in plan.get('order',[]):
        need(row['id'] not in seen,'DUPLICATE_STEP')
        need(set(row.get('depends_on',[]))<=seen,'DEPENDENCY_ORDER')
        seen.add(row['id'])
    need([r['id'] for r in plan.get('order',[])]==['RC-FINAL','R1-PERSIST','M1-A','M1-BC','R2-V1-EXIT','V2','V3'],'ROUTE_DRIFT')
    need(plan['order'][0].get('obligations')==['07-1','07-2','07-3'],'CURRENT_DEFECT_SET_DRIFT')
    return errors


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test',action='store_true');args=parser.parse_args()
    spec=json.loads((ROOT/SPEC).read_text());plan=json.loads((ROOT/PLAN).read_text());errors=validate(spec,plan)
    approval=json.loads((ROOT/spec['approval']).read_text());base=json.loads((ROOT/'reports/development-refresh-2026-11-20/baseline.json').read_text());control=json.loads((ROOT/'plans/execution-control.json').read_text())
    if approval.get('change_id')!=spec['change_id'] or approval.get('decision')!='APPROVED_BY_USER':errors.append('APPROVAL_MISSING')
    for path,digest in base['immutable_pins'].items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=digest:errors.append('IMMUTABLE_PIN:'+path)
    if control['development_outline']!=base['development_outline']:errors.append('PROGRESS_INFLATED')
    if control['coordinate']['stage_id']!=base['coordinate']['stage_id']:errors.append('STAGE_SWITCH')
    packet=json.loads((ROOT/plan['order'][0]['packet']).read_text())
    if [r['id'] for r in packet['fault_matrix']]!=['07-1','07-2','07-3'] or packet['status']!='DOC_READY_NOT_EXECUTED':errors.append('PACKET_DRIFT')
    for path in [spec['approval'],plan['extends'],plan['workflow_spec'],'docs/37_DELIVERY_EFFICIENCY_SPEC.md','docs/38_EXECUTION_PLAN_REFRESH.md','plans/packets/rc-review07/next-goal.md']:
        if not (ROOT/path).is_file():errors.append('REFERENCE_MISSING:'+path)
    negative=0
    if args.self_test:
        probes=[]
        def bad_spec(key,value):
            item=copy.deepcopy(spec);item[key]=value;probes.append((item,plan))
        bad_spec('coordinate_authority','second-control.json')
        bad_spec('formal_pins',{**spec['formal_pins'],'v1_cases':28})
        bad_spec('roles',{**spec['roles'],'independent_review':spec['roles']['implementation']})
        bad_spec('limits',{**spec['limits'],'agents_per_project':4})
        bad_spec('quota429','retry silently')
        invalid=copy.deepcopy(plan);invalid['order'][0]['depends_on']=['V3'];probes.append((spec,invalid))
        invalid=copy.deepcopy(plan);invalid['order'][0]['obligations']=[];probes.append((spec,invalid))
        for index,(a,b) in enumerate(probes):
            negative+=1
            if not validate(a,b):errors.append('NEGATIVE_FALSE_GREEN:'+str(index))
    print(json.dumps({'kind':'WORKFLOW_AND_PLAN_ONLY_NOT_PRODUCT_ACCEPTANCE','errors':errors,'negative_cases':negative,'model_or_runtime_executed':False},ensure_ascii=False,indent=2))
    return int(bool(errors))

if __name__=='__main__':raise SystemExit(main())
