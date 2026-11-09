"""Program02 atomic local budgets. Reservations fail closed across crashes/processes.

No model/server launch occurs here. Execution receipts remain separate from permission.
"""
from pathlib import Path
from contextlib import contextmanager
import hashlib
import json
import math
import re
import sqlite3
import time

ROOT = Path(__file__).resolve().parents[1]
REQUEST = 'reports/authorization-program-v1-local-02.request.json'
APPROVAL = 'reports/authorization-program-v1-local-02.approval.json'
LEDGER = ROOT.parent.parent / '.lvw-runtime/lvw-prompt-service/program02.sqlite'
AMENDMENT = 'reports/unified-media/authorization-residual-recheck-01'
COMPLETE_REQUEST = 'reports/authorization-program-v1-complete-03.request.json'
COMPLETE_APPROVAL = 'reports/authorization-program-v1-complete-03.approval.json'


def complete_selected(root=ROOT):
    control=root/'plans/execution-control.json'
    return (root/COMPLETE_APPROVAL).exists() or (control.is_file() and
        json.loads(control.read_text()).get('authorization_record')==COMPLETE_APPROVAL)


def program_paths(root=ROOT):
    return (COMPLETE_REQUEST,COMPLETE_APPROVAL) if complete_selected(root) else (REQUEST,APPROVAL)


def extra_full_grant(run, stage, *, root=ROOT):
    """One explicit increment only. A continuation instruction/request is not approval."""
    request_path=root/(AMENDMENT+'.request.json')
    grant_path=root/(AMENDMENT+'.approval.json')
    if not request_path.is_file() or not grant_path.is_file():
        raise ValueError('WAIT_BUDGET: explicit one-run amendment absent')
    request=json.loads(request_path.read_text())
    grant=json.loads(grant_path.read_text())
    if not (run=='live-08' and stage=='R1'
            and grant.get('decision')=='APPROVED' and grant.get('status')=='ACTIVE'
            and grant.get('granted_by')=='project_owner'
            and grant.get('authorization_id')==request.get('authorization_id')=='AUTH-BUDGET-V1-R1-RESIDUAL-01'
            and grant.get('request_sha256')==digest(request_path)
            and request.get('parent_approval_sha256')==digest(root/APPROVAL)
            and request.get('run_id')==run and request.get('stage_id')==stage
            and request.get('old_stage_full_limit')==3 and request.get('new_stage_full_limit')==4
            and request.get('additional_full_runs')==1
            and not (root/(AMENDMENT+'.approval.terminal.json')).exists()):
        raise ValueError('WAIT_BUDGET: no exact active one-run amendment')
    return request,{'request':str(request_path.relative_to(root)),'request_sha256':digest(request_path),
                    'approval':str(grant_path.relative_to(root)),'approval_sha256':digest(grant_path)}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def approved(root=ROOT):
    if complete_selected(root):
        request=json.loads((root/COMPLETE_REQUEST).read_text())
        grant=json.loads((root/COMPLETE_APPROVAL).read_text())
        if not (grant.get('status')=='ACTIVE' and grant.get('decision')=='APPROVED'
                and grant.get('granted_by')=='project_owner'
                and grant.get('authorization_id')==request.get('authorization_id')=='AUTH-PROGRAM-V1-COMPLETE-03'
                and grant.get('request_sha256')==digest(root/COMPLETE_REQUEST)
                and request['existing_program_approval_sha256']==digest(root/request['existing_program_approval'])):
            raise ValueError('WAIT_AUTH: complete03 absent/revoked/hash changed; never fall back')
        value=dict(request)
        limits=request['global_cumulative_limits']
        value['global_only']=True
        value['budget_policy']={
            'program_total_model_actions':limits['model_actions'],
            'program_total_effective_full_checkpoints':limits['effective_full_checkpoints'],
            'program_total_production_runtime_seconds':limits['production_runtime_seconds'],
            'per_child_model_actions_ceiling':limits['per_child_model_actions_ceiling'],
            'per_child_wall_seconds_ceiling':limits['per_child_wall_seconds_ceiling']}
        return value
    request = json.loads((root / REQUEST).read_text())
    grant = json.loads((root / APPROVAL).read_text())
    if not (grant.get('status') == 'ACTIVE' and grant.get('decision') == 'APPROVED'
            and grant.get('authorization_id') == request['authorization_id'] == 'AUTH-PROGRAM-V1-LOCAL-02'
            and grant.get('granted_by') == 'project_owner'
            and grant.get('request_sha256') == digest(root / REQUEST)):
        raise ValueError('WAIT_AUTH: absent/revoked/mismatched program02 approval')
    return request


@contextmanager
def transaction(ledger):
    ledger = Path(ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(ledger, timeout=30)
    db.row_factory = sqlite3.Row
    try:
        db.execute('CREATE TABLE IF NOT EXISTS children (run TEXT PRIMARY KEY, stage TEXT, '
                   'cap INTEGER, seconds INTEGER, full INTEGER, cpu INTEGER, starts TEXT, '
                   'issued REAL, expires REAL, calls INTEGER DEFAULT 0, checkpoint INTEGER DEFAULT 0, '
                   'active INTEGER DEFAULT 1, elapsed INTEGER DEFAULT 0, child_path TEXT, child_hash TEXT, '
                   'bindings_path TEXT, bindings_hash TEXT)')
        db.execute('BEGIN IMMEDIATE')
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def totals(rows):
    value = dict(model=0, seconds=0, full=0, zero=0, cpu=0)
    for row in rows:
        active = row['active']
        value['model'] += row['cap'] if active else row['calls']
        value['seconds'] += row['seconds'] if active else row['elapsed']
        value['full'] += row['full'] if active else row['checkpoint']
        value['zero'] += int(not row['cpu'] and (active or row['calls'] == 0))
        value['cpu'] += row['cpu']
    return value


def reserve(run, stage, budget, seconds, full, *, ledger=LEDGER, root=ROOT, cpu_fixture=False):
    request = approved(root)
    policy = request['budget_policy']
    allowed_keys = {'api_starts', 'ollama_starts', 'comfy_starts', 'headless_browser_starts',
                    'provider_calls', 'full_checkpoints', 'model_calls', 'downloads',
                    'cloud_calls', 'paid_calls', 'holdout_model_calls'}
    if (stage not in request['stages'] or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', run)
            or not isinstance(budget, dict) or set(budget) - allowed_keys
            or any(type(v) is not int or v < 0 for v in budget.values())
            or any(budget.get(k, 0) for k in ('downloads', 'cloud_calls', 'paid_calls', 'holdout_model_calls'))
            or type(seconds) is not int or not 0 < seconds <= policy['per_child_wall_seconds_ceiling']
            or type(full) is not bool):
        raise ValueError('WAIT_AUTH: child scope/budget invalid')
    cap = max(budget.get('model_calls', 0), budget.get('provider_calls', 0))
    if cap > policy['per_child_model_actions_ceiling'] or budget.get('full_checkpoints', 0) != int(full):
        raise ValueError('WAIT_BUDGET: child ceiling')
    if cpu_fixture and (full or cap or any(budget.get(k,0) for k in ('api_starts','ollama_starts','comfy_starts'))):
        raise ValueError("CPU fixture cannot claim model actions/full acceptance")
    cpu = int(cpu_fixture)
    starts = {k: budget.get(k, 0) for k in ('api_starts', 'ollama_starts', 'comfy_starts', 'headless_browser_starts')}
    now = time.time()
    proposed = dict(cap=cap, seconds=seconds, full=int(full), cpu=cpu, calls=0,
                    checkpoint=0, active=1, elapsed=0)
    with transaction(ledger) as db:
        if db.execute('SELECT 1 FROM children WHERE run=?', (run,)).fetchone():
            raise ValueError('child identity already used; terminal grants cannot replay')
        rows = list(db.execute('SELECT * FROM children'))
        stage_rows = [r for r in rows if r['stage'] == stage]
        if request.get('global_only'):
            charged=totals([*rows,proposed])
            production_seconds=sum((r['seconds'] if r['active'] else r['elapsed'])
                                   for r in [*rows,proposed] if not r['cpu'])
            if (charged['model']>policy['program_total_model_actions']
                    or charged['full']>policy['program_total_effective_full_checkpoints']
                    or production_seconds>policy['program_total_production_runtime_seconds']):
                raise ValueError('WAIT_BUDGET: complete03 global allowance exhausted')
            db.execute('INSERT INTO children(run,stage,cap,seconds,full,cpu,starts,issued,expires) '
                       'VALUES(?,?,?,?,?,?,?,?,?)', (run, stage, cap, seconds, int(full), cpu, json.dumps(starts), now, now + seconds))
            return
        for group, limits in ((rows, {'model': policy['program_total_model_actions'],
                     'seconds': policy['program_total_production_runtime_seconds'],
                     'full': policy['program_total_effective_full_checkpoints'],
                     'zero': policy['program_total_zero_model_startup_attempts']}),
                (stage_rows, {'full': policy['per_stage_effective_full_checkpoints'],
                     'zero': policy['per_stage_zero_model_startup_attempts'],
                     'cpu': policy['per_stage_cpu_fixture_or_offline_browser_children']})):
            charged = totals([*group, proposed])
            for key,limit in limits.items():
                # CPU checks never add a full checkpoint, including after an approved extra run.
                if group is stage_rows and key=='full' and not full:
                    continue
                if charged[key] > limit:
                    if group is stage_rows and key=='full' and charged[key]==4:
                        amendment,_=extra_full_grant(run,stage,root=root)
                        if budget!=amendment['budget'] or seconds>amendment['max_seconds']:
                            raise ValueError('amendment child budget mismatch')
                    else:
                        raise ValueError('WAIT_BUDGET: cumulative or reserved allowance exhausted')
        for key, count in starts.items():
            if count + sum(json.loads(r['starts'])[key] for r in stage_rows) > policy['per_stage_production_starts_per_engine']:
                raise ValueError('WAIT_BUDGET: process starts exhausted')
        db.execute('INSERT INTO children(run,stage,cap,seconds,full,cpu,starts,issued,expires) '
                   'VALUES(?,?,?,?,?,?,?,?,?)', (run, stage, cap, seconds, int(full), cpu, json.dumps(starts), now, now + seconds))


def bind(run, child, *, ledger=LEDGER):
    with transaction(ledger) as db:
        row = db.execute('SELECT * FROM children WHERE run=?', (run,)).fetchone()
        if row is None or row['active'] != 1 or row['child_hash']:
            raise ValueError('unreserved/already bound child')
        db.execute('UPDATE children SET child_path=?,child_hash=? WHERE run=?',
                   (str(Path(child).resolve()), digest(child), run))


def model_action(child_path):
    """Debit before every inference/preload send, including failures and cancellation."""
    child_path = Path(child_path)
    child = json.loads(child_path.read_text())
    request=approved(ROOT)
    _,grant_path=program_paths(ROOT)
    if child.get('program') not in (None,grant_path) or child['program_sha256'] != digest(ROOT / grant_path):
        raise ValueError('program changed after child issue')
    if child.get('run_id')=='live-08' and not request.get('global_only'):
        _,binding=extra_full_grant(child['run_id'],child['stage_id'],root=ROOT)
        if binding!=child.get('budget_amendment'):
            raise ValueError('amendment changed after child issue')
    with transaction(child['budget_ledger']) as db:
        row = db.execute('SELECT * FROM children WHERE run=?', (child['run_id'],)).fetchone()
        if (row is None or row['active'] != 1 or row['expires'] <= time.time()
                or row['child_path'] != str(child_path.resolve()) or row['child_hash'] != digest(child_path)
                or row['calls'] >= row['cap']):
            raise ValueError('WAIT_BUDGET: expired, altered or exhausted child')
        for item in child['frozen_files']:
            if digest(ROOT / item['path']) != item['sha256']:
                raise ValueError('production source drift before model send')
        for item in child.get('samples', []):
            if digest(ROOT / item['path']) != item['sha256']:
                raise ValueError('sample drift before model send')
        if child.get('execution_bindings_required'):
            if not row['bindings_path'] or digest(row['bindings_path']) != row['bindings_hash']:
                raise ValueError('execution bindings absent or changed')
            for item in json.loads(Path(row['bindings_path']).read_text()).values():
                if digest(item['path']) != item['sha256']:
                    raise ValueError('runtime tool identity drift')
        db.execute('UPDATE children SET calls=calls+1,checkpoint=full WHERE run=?', (child['run_id'],))


def bind_execution(run, bindings_path, *, ledger=LEDGER):
    """Seal read-only installed tool discovery before starting any production process."""
    for item in json.loads(Path(bindings_path).read_text()).values():
        if digest(item['path']) != item['sha256']:
            raise ValueError('runtime tool identity mismatch before start')
    with transaction(ledger) as db:
        row=db.execute('SELECT * FROM children WHERE run=?',(run,)).fetchone()
        if row is None or row['active'] != 1 or row['calls'] or row['bindings_path']:
            raise ValueError('execution bindings already sealed or child inactive')
        db.execute('UPDATE children SET bindings_path=?,bindings_hash=? WHERE run=?',
                   (str(Path(bindings_path).resolve()),digest(bindings_path),run))


def settle(run, observed_calls, *, ledger=LEDGER):
    """Call only after original owned processes exit and raw evidence is archived.

    Unsettled/crashed children retain their entire reservation; never refund uncertainty.
    """
    with transaction(ledger) as db:
        row = db.execute('SELECT * FROM children WHERE run=?', (run,)).fetchone()
        if row is None or row['active'] != 1 or type(observed_calls) is not int or observed_calls != row['calls']:
            raise ValueError('unproved terminal or model action count mismatch')
        elapsed = math.ceil(time.time() - row['issued'])
        if elapsed > row['seconds']:
            raise ValueError('WAIT_BUDGET: wall allowance exceeded; retain reservation')
        db.execute('UPDATE children SET active=0,elapsed=? WHERE run=?', (elapsed, run))
        return {'run_id': run, 'actual_model_actions': row['calls'],
                'effective_full_checkpoint': bool(row['checkpoint']),
                'zero_model_startup': not row['cpu'] and row['calls'] == 0,
                'elapsed_seconds': elapsed, 'program_still_active': True}


def close_retaining_reservation(run, *, ledger=LEDGER):
    """Terminal always disables sends; unknown cleanup keeps reserved capacity charged."""
    with transaction(ledger) as db:
        db.execute('UPDATE children SET active=2 WHERE run=? AND active=1', (run,))
