"""Finite V1 children. Never approves human signatures or a whole R1 Stage."""
from pathlib import Path
import hashlib,json,re,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
PROGRAM='reports/authorization-program-v1-local-01.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def create(run_id,harness,budget,*,port,samples=(),seconds=240,full=False):
    control=json.loads((ROOT/'plans/execution-control.json').read_text())
    if (ROOT/'reports/authorization-program-v1-local-02.approval.json').exists() or control.get('authorization_record') in {'reports/authorization-program-v1-local-02.approval.json','reports/authorization-program-v1-complete-03.approval.json'}:
        return create_program02(run_id,harness,budget,port=port,samples=samples,seconds=seconds,full=full)
    parent=json.loads((ROOT/PROGRAM).read_text());approval=json.loads((ROOT/'reports/unified-media/approval.json').read_text())
    assert parent['status']=='ACTIVE' and 'R1' in parent['stages'] and approval['decision']=='APPROVED'
    assert re.fullmatch('[a-zA-Z0-9._-]+',run_id) and 0<seconds<=1800
    assert all(type(x) is int and x>=0 for x in budget.values())
    assert all(budget.get(x,0)==0 for x in ['downloads','cloud_calls','paid_calls','holdout_model_calls'])
    candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    check=subprocess.run(['git','diff','--exit-code',candidate,'--','lvw/backend','lvw/frontend','lvw/run_local.py','lvw/print_build_id.py','launcher','LVW.exe','START_LVW.cmd','contracts','templates','LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge','.agent-governance/stages/R1'],cwd=ROOT,capture_output=True)
    assert check.returncode==0,'product drift: commit candidate before a real child'
    if full:
        runs=list((ROOT/'reports/unified-media').glob('live-*/authorization.json'))
        consumed=sum(1 for p in runs if not (p.parent/'receipt.json').exists() or json.loads((p.parent/'receipt.json').read_text()).get('stage_checkpoint_consumed',True))
        if run_id in {'live-04','live-05'} or consumed>=2 or len(runs)>=3:
            # A written request is not approval. This exception remains locked until a new
            # explicit human approval binds the complete request hash and exact source tree.
            supplemental_runs={'live-04':('authorization-semantic-correction-01',3),
                               'live-05':('authorization-runtime-transition-01',4)}
            assert run_id in supplemental_runs,'full checkpoint/recheck budget exhausted'
            stem,expected_history=supplemental_runs[run_id]
            assert len(runs)==expected_history,'supplementary attempt cannot be replayed'
            request_path=ROOT/('reports/unified-media/'+stem+'.request.json')
            approval_path=ROOT/('reports/unified-media/'+stem+'.approval.json')
            assert request_path.is_file() and approval_path.is_file(),'WAIT_AUTH: supplementary full recheck requires explicit human approval'
            request=json.loads(request_path.read_text());grant=json.loads(approval_path.read_text())
            assert grant.get('decision')=='APPROVED' and grant.get('request_sha256')==sha(request_path)
            assert grant.get('authorization_id')==request['authorization_id']
            assert request['run_id']==run_id and request['max_full_rechecks']==1
            assert budget==request['budget'] and seconds<=request['max_seconds'] and port==request['port']
            assert [(str(Path(p).relative_to(ROOT)),sha(p)) for p in samples]==[(p['path'],p['sha256']) for p in request['samples']]
            assert sha(harness)==request['harness_sha256']
            assert sha(ROOT/'.agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256')==request['proposed_packet_manifest_sha256'],'approved packet presentation correction not activated'
            packet_root=ROOT/'.agent-governance/stages/R1'
            packet_files=set()
            for line in (packet_root/'PAYLOAD_MANIFEST.sha256').read_text().splitlines():
                digest,name=line.split('  ',1)
                assert name==Path(name).name and name not in packet_files
                assert sha(packet_root/name)==digest,'approved packet file mismatch'
                packet_files.add(name)
            assert {p.name for p in packet_root.iterdir() if p.is_file() and p.name!='PAYLOAD_MANIFEST.sha256'}==packet_files
            assert subprocess.run(['git','merge-base','--is-ancestor',request['candidate_sha'],candidate],cwd=ROOT).returncode==0
            assert subprocess.run(['git','diff','--quiet',request['candidate_sha'],candidate,'--',*request['frozen_paths']],cwd=ROOT).returncode==0
        else:
            assert consumed<2 and len(runs)<3

    out=ROOT/'reports/unified-media'/run_id;out.mkdir(exist_ok=False)
    value={'kind':'V1_FINITE_CHILD_NOT_STAGE_SIGNOFF','status':'ACTIVE_ONE_SHOT','stage_id':'R1','slice':'UNIFIED_MEDIA_EARLY','run_id':run_id,'candidate_sha':candidate,'harness_sha256':sha(harness),'program':PROGRAM,'program_sha256':sha(ROOT/PROGRAM),'packet_manifest_sha256':sha(ROOT/'.agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256'),'ports':[port],'samples':[{'path':str(Path(p).relative_to(ROOT)),'sha256':sha(p)} for p in samples],'budget':budget,'issued_at':time.time(),'expires_at':time.time()+seconds,'process_policy':'Only original handles or PID+birth+unique launch-token proved descendants from this run; never terminate others.','cleanup':'Stop own browser/API/Ollama and remove only this run private temp. Retain receipts/failures.','full_checkpoint':full,'stage_pass_claim':False}
    if full and run_id in {'live-04','live-05'}:
        value['supplemental_authorization']={'request':str(request_path.relative_to(ROOT)),'request_sha256':sha(request_path),'approval':str(approval_path.relative_to(ROOT)),'approval_sha256':sha(approval_path),'authorization_id':request['authorization_id']}
    (out/'authorization.json').write_text(json.dumps(value,indent=2)+'\n');return out,value
def terminal(out,auth,result):
    if auth.get('budget_ledger'):
        from tools.local_program_authority import settle,close_retaining_reservation
        ledger=out/'runtime-evidence/provider.jsonl'
        calls=sum(json.loads(line).get('event')=='provider_call_started' for line in ledger.read_text().splitlines()) if ledger.exists() else 0
        if (result.get('api_listener_absent') and result.get('ollama_listener_absent')
                and not result.get('cleanup_error') and result.get('run_root_removed',True)):
            try:
                result['program02_budget_settlement']=settle(auth['run_id'],calls,ledger=auth['budget_ledger'])
                result['stage_checkpoint_consumed']=result['program02_budget_settlement']['effective_full_checkpoint']
            except ValueError as error:
                result['decision']='NO_GO';result['budget_error']=str(error)
        else:
            result['budget_reservation_retained']='cleanup unproved; no automatic refund'
        close_retaining_reservation(auth['run_id'],ledger=auth['budget_ledger'])
    (out/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (out/'authorization.terminal.json').write_text(json.dumps({**auth,'status':'EXPIRED_'+result['decision'],'terminal':'receipt.json'},indent=2)+'\n')
    if auth.get('budget_amendment'):
        grant=ROOT/auth['budget_amendment']['approval']
        grant.with_suffix('.terminal.json').write_text(json.dumps({'status':'EXPIRED_'+result['decision'],'run_id':auth['run_id'],'terminal':str((out/'receipt.json').relative_to(ROOT))},indent=2)+'\n')

def create_program02(run_id,harness,budget,*,port,samples,seconds,full):
    from tools import local_program_authority as program
    active_program=program.approved()
    program_request,program_approval=program.program_paths()
    assert re.fullmatch(r'live-(?:0[5-9]|[1-9][0-9]+)',run_id),'new unique live identity required'
    assert full and port==18780 and 0<seconds<=1800
    expected={'api_starts':1,'ollama_starts':1,'headless_browser_starts':1,'provider_calls':8,
              'full_checkpoints':1,'model_calls':8,'downloads':0,'cloud_calls':0,'paid_calls':0,'holdout_model_calls':0}
    assert budget==expected,'frozen unified packet budget cannot expand'
    request=json.loads((ROOT/'reports/unified-media/authorization-runtime-transition-01.request.json').read_text())
    assert [(str(Path(p).relative_to(ROOT)),sha(p)) for p in samples]==[(p['path'],p['sha256']) for p in request['samples']]
    packet_root=ROOT/'.agent-governance/stages/R1'
    assert sha(packet_root/'PAYLOAD_MANIFEST.sha256')==request['proposed_packet_manifest_sha256']
    leaves=set()
    for line in (packet_root/'PAYLOAD_MANIFEST.sha256').read_text().splitlines():
        digest,name=line.split('  ',1)
        assert name==Path(name).name and name not in leaves and sha(packet_root/name)==digest
        leaves.add(name)
    assert {p.name for p in packet_root.iterdir() if p.is_file() and p.name!='PAYLOAD_MANIFEST.sha256'}==leaves
    paths=[*request['frozen_paths'],'tools/local_program_authority.py','.agent-governance/stages/R1']
    candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    amendment_binding=None
    if run_id=='live-08' and not active_program.get('global_only'):
        amendment,amendment_binding=program.extra_full_grant(run_id,'R1')
        assert subprocess.run(['git','merge-base','--is-ancestor',amendment['candidate_sha'],candidate],cwd=ROOT).returncode==0
        assert subprocess.run(['git','diff','--quiet',amendment['candidate_sha'],candidate,'--',*amendment['frozen_paths']],cwd=ROOT).returncode==0
    assert subprocess.run(['git','diff','--quiet',candidate,'--',*paths],cwd=ROOT).returncode==0,'commit candidate before child'
    extra=subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*paths],cwd=ROOT,text=True).splitlines()
    assert not [p for p in extra if '__pycache__' not in Path(p).parts],'uncommitted production files'
    tracked=subprocess.check_output(['git','ls-files','--',*paths],cwd=ROOT,text=True).splitlines()
    files=[{'path':p,'sha256':sha(ROOT/p)} for p in tracked if (ROOT/p).is_file()]
    out=ROOT/'reports/unified-media'/run_id
    assert not out.exists(),'terminal identity cannot replay'
    program.reserve(run_id,'R1',budget,seconds,full)
    out.mkdir(exist_ok=False)
    now=time.time()
    value={'kind':'V1_FINITE_CHILD_NOT_STAGE_SIGNOFF','status':'ACTIVE_ONE_SHOT','stage_id':'R1',
       'slice':'UNIFIED_MEDIA_EARLY','run_id':run_id,'candidate_sha':candidate,'harness_sha256':sha(harness),
       'program':program_approval,'program_sha256':sha(ROOT/program_approval),
       'program_request_sha256':sha(ROOT/program_request),'budget_ledger':str(program.LEDGER),'execution_bindings_required':True,
       'packet_manifest_sha256':sha(packet_root/'PAYLOAD_MANIFEST.sha256'),'frozen_files':files,
       'ports':[port,11434],'samples':[{'path':str(Path(p).relative_to(ROOT)),'sha256':sha(p)} for p in samples],
       'budget':budget,'issued_at':now,'expires_at':now+seconds,'full_checkpoint':full,'stage_pass_claim':False,
       'model':'gemma4:26b; bind actual model identity in runtime receipt',
       'process_policy':'Only original handles or PID+birth+nonce proved descendants from this run.',
       'cleanup':'Cancel own jobs, archive evidence, stop owned runtime/API/browser and prove original exit/temp/listener cleanup.'}
    if amendment_binding:value['budget_amendment']=amendment_binding
    (out/'authorization.json').write_text(json.dumps(value,indent=2)+'\n')
    program.bind(run_id,out/'authorization.json')
    return out,value
