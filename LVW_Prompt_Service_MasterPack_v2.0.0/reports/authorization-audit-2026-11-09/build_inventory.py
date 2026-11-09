"""Read repository authorization metadata only. Never activates or executes a grant."""
from pathlib import Path
import json,hashlib,collections,time
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent

def classify(path,x):
    name=path.name;schema=str(x.get('schema_version',''));kind=str(x.get('kind',''))
    if name.endswith('.terminal.json'):return 'terminal_receipt_not_new_permission'
    if name in {'authorization-program-v1-local-01.json','authorization-program-v0-local-verification-01.json'}:return 'human_program'
    if 'human-signoff' in name or schema=='lvw.human-signoff/1' or name=='v0-min-acceptance.json':return 'human_experience_or_acceptance'
    if 'change-decision' in name or path.as_posix()=='reports/unified-media/approval.json':return 'scope_contract_or_route_decision'
    if name.endswith('.request.json'):return 'request_not_authorization'
    if any(key in x for key in ['program','source_program_authorization','parent_authorization','source_program']) or 'child' in schema or kind.startswith('V1_FINITE_CHILD') or 'controlled_executor' in str(x.get('issued_by','')):
        return 'automatic_or_delegated_child'
    if x.get('grant_statement') or x.get('statement') or x.get('source')=='Direct user authorization in the active project conversation.':return 'human_grant_record_not_necessarily_separate_chat'
    return 'other_authorization_metadata_needs_context'
rows=[]
for path in sorted((ROOT/'reports').rglob('*.json')):
    rel=path.relative_to(ROOT)
    if rel.parts[1]=='authorization-audit-2026-11-09':continue
    name=path.name
    if not any(w in name for w in ['authorization','human-signoff','change-decision']) and rel.as_posix() not in ['reports/unified-media/approval.json','reports/v0-s1/v0-min-acceptance.json']:continue
    try:x=json.loads(path.read_text())
    except (ValueError,UnicodeError):continue
    if not isinstance(x,dict):continue
    category=classify(rel,x);issued=x.get('status',x.get('decision'))
    effective=issued;terminal=path.with_suffix('.terminal.json')
    terminal_ref=None
    if not name.endswith('.terminal.json') and terminal.is_file():
        t=json.loads(terminal.read_text());effective=t.get('status',t.get('decision','TERMINAL_RECORDED'));terminal_ref=terminal.relative_to(ROOT).as_posix()
    elif isinstance(x.get('expires_at'),(int,float)) and x['expires_at']<time.time():effective='EXPIRED_BY_TIME_OR_TERMINAL'
    if category=='request_not_authorization':effective='REQUEST_ONLY_LOOK_UP_DISTINCT_APPROVAL'
    rows.append({'path':rel.as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'category':category,'authorization_id':x.get('authorization_id'),'request_id':x.get('request_id'),'run_id':x.get('run_id'),'stage_id':x.get('stage_id'),'record_status':issued,'effective_status_hint':effective,'terminal_sidecar':terminal_ref,'program':x.get('program',x.get('source_program_authorization')),'human_text':x.get('grant_statement',x.get('statement',x.get('decision_statement'))),'issued_by':x.get('issued_by',x.get('granted_by',x.get('authorizer',x.get('decided_by'))))})
value={'kind':'READ_ONLY_AUTHORIZATION_DOCUMENT_INVENTORY_NOT_PERMISSION_OR_HUMAN_APPROVAL_COUNT','as_of':'2026-11-09','records':rows,'counts_by_record_category':dict(collections.Counter(x['category'] for x in rows)),'important_limits':['Document counts are not counts of human questions or approvals. Requests, grants, automatic children and terminal snapshots overlap.','An issued ACTIVE snapshot is not proof a one-shot grant remains usable; terminal sidecars take precedence.','A program marked ACTIVE may still lack remaining Stage budget or coverage of a new frozen candidate.','Historical GRANTED records cannot reactivate an expired/scoped run.']}
(OUT/'inventory.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'records':len(rows),'record_categories':value['counts_by_record_category'],'manual_approval_count':'NOT_INFERRED_FROM_FILE_COUNT'},ensure_ascii=False))
