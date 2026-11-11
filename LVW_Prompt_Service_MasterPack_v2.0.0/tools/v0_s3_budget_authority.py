"""One bounded stdin debit; uses the sealed authority ROOT, never a worktree default DB."""
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_HASH = '677998fa2ab5b51017b5437fecd07d6ca31c26473a7ac0acede4637f6470f787'
LIMIT = 32768


def module_at(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def debit(request):
    protocol=module_at('_s3_protocol',ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py')
    keys={'schema','request_id','action_kind','payload_sha256','model','binding_path','binding_sha256'}
    if not isinstance(request,dict) or set(request)!=keys or request['schema']!='lvw.s3-debit/1': raise ValueError('request schema')
    if str(uuid.UUID(request['request_id']))!=request['request_id'] or request['action_kind'] not in ('chat','preload'): raise ValueError('request identity/action')
    import re
    if not isinstance(request['payload_sha256'],str) or not re.fullmatch('[0-9a-f]{64}',request['payload_sha256']): raise ValueError('payload digest')
    b=protocol.validate_config(protocol.read_json(request['binding_path'],request['binding_sha256']))
    if b['binding_path']!=request['binding_path'] or Path(b['authority_root']).resolve()!=ROOT or b['model']!=request['model']: raise ValueError('authority identity')
    if Path(b['tools']['shim']['path']).resolve()!=Path(__file__).resolve(): raise ValueError('shim identity')
    if Path(b['tools']['python']['path']).resolve()!=Path(sys.executable).resolve(): raise ValueError('python identity')
    authority_path=ROOT/'tools/local_program_authority.py'
    if protocol.digest(authority_path)!=AUTHORITY_HASH or b['tools']['authority']['sha256']!=AUTHORITY_HASH: raise ValueError('authority implementation drift')
    for item in b['tools'].values():
        if item is not None and protocol.digest(item['path'])!=item['sha256']: raise ValueError('tool drift')
    # Import at its sealed original root: ROOT, frozen_files and approved() all agree.
    authority=module_at('_s3_authority',authority_path)
    if authority.ROOT!=ROOT: raise ValueError('authority root mismatch')
    approval=ROOT/authority.COMPLETE_APPROVAL
    if protocol.digest(approval)!=b['approval_sha256']: raise ValueError('approval drift')
    approved=authority.approved(ROOT)
    if not approved.get('global_only') or approved['authorization_id']!=protocol.PROGRAM: raise ValueError('COMPLETE03 required')
    child_path=Path(b['child_path'])
    child=protocol.read_json(child_path,b['child_sha256'])
    expected={k:v for k,v in b.items() if k!='child_sha256'}
    if (child.get('s3_budget')!=expected or child.get('run_id')!=b['run_id'] or child.get('stage_id')!='V0-S3'
            or child.get('candidate_sha')!=b['candidate_sha'] or child.get('program')!=authority.COMPLETE_APPROVAL
            or child.get('program_sha256')!=b['approval_sha256'] or child.get('budget_ledger')!=b['ledger_path']
            or child.get('execution_bindings_required') is not True or not child.get('frozen_files')):
        raise ValueError('child identity/seal')
    ledger=Path(b['ledger_path'])
    # Never let model_action's CREATE IF NOT EXISTS turn a missing path into capacity.
    if not ledger.is_file(): raise ValueError('original ledger missing')
    if b['transport'] in ('local-fixture','wsl-fixture'):
        # Explicit synthetic roots only; a production binding cannot select this bypass.
        if not ROOT.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not (ROOT/'.s3-synthetic-fixture').is_file(): raise ValueError('fixture root required')
        if not ledger.resolve().is_relative_to(ROOT): raise ValueError('fixture ledger escaped')
    else:
        historical=json.loads((ROOT/'reports/unified-media/live-15/authorization.json').read_text())
        if not ledger.samefile(historical['budget_ledger']): raise ValueError('original ledger identity mismatch')
        if (ROOT/'.s3-synthetic-fixture').exists(): raise ValueError('fixture forbidden in production')
    with sqlite3.connect(ledger.resolve().as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=db.execute('SELECT * FROM children WHERE run=?',(b['run_id'],)).fetchone()
        if (row is None or row['stage']!='V0-S3' or row['active']!=1 or row['cpu']!=0
                or row['child_path']!=str(child_path.resolve()) or row['child_hash']!=b['child_sha256']
                or row['bindings_path']!=b['execution_path'] or row['bindings_hash']!=b['execution_sha256']
                or not row['issued']<=b['issued_at']<b['expires_at']<=row['expires']
                or not 0<row['seconds']<=21600 or not 0<row['cap']<=128): raise ValueError('ledger child binding')
    execution=protocol.read_json(b['execution_path'],b['execution_sha256'])
    for role,item in b['tools'].items():
        if item is not None and execution.get('s3_'+role)!={'path':item['path'],'sha256':item['sha256']}: raise ValueError('execution role binding')
    helper=ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py'
    if execution.get('s3_protocol')!={'path':str(helper),'sha256':protocol.digest(helper)}: raise ValueError('protocol source binding')
    owner=None
    if b['transport']=='wsl-fixture':
        # Path is derived only after all authority, child and source seals pass.
        directory=ROOT/'.s3-owned-requests'
        directory.mkdir(exist_ok=True)
        if directory.is_symlink(): raise ValueError('owner directory symlink')
        owner=directory/(request['request_id']+'.json')
        identity={'request_id':request['request_id'],'binding_sha256':request['binding_sha256'],
                  'pid':os.getpid(),'birth':protocol.process_birth(os.getpid()),'state':'ENTERED'}
        with owner.open('x') as stream: json.dump(identity,stream)
    try:
        authority.model_action(child_path)
    finally:
        if owner is not None:
            identity['state']='RETURNED_FROM_AUTHORITY'
            owner.write_text(json.dumps(identity))
    return dict(request,status='DEBITED',run_id=b['run_id'],child_sha256=b['child_sha256'],authority_sha256=AUTHORITY_HASH)


def main():
    try:
        raw=sys.stdin.buffer.read(LIMIT+1)
        if len(raw)>LIMIT: raise ValueError('stdin limit')
        # Strict duplicate/nonfinite parsing is also used by the client.
        protocol=module_at('_s3_decode',ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py')
        response=debit(protocol.decode(raw))
        encoded=json.dumps(response,separators=(',',':'),allow_nan=False)
        if len(encoded)>LIMIT: raise ValueError('stdout limit')
        sys.stdout.write(encoded+'\n');sys.stdout.flush()
        return 0
    except Exception as error:
        # No payload/path dumps; a failed/uncertain debit is never automatically replayed.
        sys.stderr.write('S3_DEBIT_REFUSED '+type(error).__name__+'\n')
        sys.stdout.write('{"status":"REFUSED"}\n');sys.stdout.flush()
        return 1


if __name__=='__main__': sys.exit(main())
