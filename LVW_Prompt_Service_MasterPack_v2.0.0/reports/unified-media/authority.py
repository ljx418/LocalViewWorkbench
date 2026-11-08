"""Finite V1 children. Never approves human signatures or a whole R1 Stage."""
from pathlib import Path
import hashlib,json,re,subprocess,time
ROOT=Path(__file__).resolve().parents[2]
PROGRAM='reports/authorization-program-v1-local-01.json'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def create(run_id,harness,budget,*,port,samples=(),seconds=240,full=False):
    parent=json.loads((ROOT/PROGRAM).read_text());approval=json.loads((ROOT/'reports/unified-media/approval.json').read_text())
    assert parent['status']=='ACTIVE' and 'R1' in parent['stages'] and approval['decision']=='APPROVED'
    assert re.fullmatch('[a-zA-Z0-9._-]+',run_id) and 0<seconds<=1800
    assert all(type(x) is int and x>=0 for x in budget.values())
    assert all(budget.get(x,0)==0 for x in ['downloads','cloud_calls','paid_calls','holdout_model_calls'])
    candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    check=subprocess.run(['git','diff','--exit-code',candidate,'--','lvw/backend','lvw/frontend','lvw/run_local.py','lvw/print_build_id.py','launcher','LVW.exe','START_LVW.cmd','contracts','.agent-governance/stages/R1'],cwd=ROOT,capture_output=True)
    assert check.returncode==0,'product drift: commit candidate before a real child'
    if full:
        runs=list((ROOT/'reports/unified-media').glob('live-*/authorization.json'))
        consumed=sum(1 for p in runs if not (p.parent/'receipt.json').exists() or json.loads((p.parent/'receipt.json').read_text()).get('stage_checkpoint_consumed',True))
        assert consumed<2,'full checkpoint/recheck Mother budget exhausted'
        assert len(runs)<3,'bounded launcher preflight retry exhausted'
    out=ROOT/'reports/unified-media'/run_id;out.mkdir(exist_ok=False)
    value={'kind':'V1_FINITE_CHILD_NOT_STAGE_SIGNOFF','status':'ACTIVE_ONE_SHOT','stage_id':'R1','slice':'UNIFIED_MEDIA_EARLY','run_id':run_id,'candidate_sha':candidate,'harness_sha256':sha(harness),'program':PROGRAM,'program_sha256':sha(ROOT/PROGRAM),'packet_manifest_sha256':sha(ROOT/'.agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256'),'ports':[port],'samples':[{'path':str(Path(p).relative_to(ROOT)),'sha256':sha(p)} for p in samples],'budget':budget,'issued_at':time.time(),'expires_at':time.time()+seconds,'process_policy':'Only original handles or PID+birth+unique launch-token proved descendants from this run; never terminate others.','cleanup':'Stop own browser/API/Ollama and remove only this run private temp. Retain receipts/failures.','full_checkpoint':full,'stage_pass_claim':False}
    (out/'authorization.json').write_text(json.dumps(value,indent=2)+'\n');return out,value
def terminal(out,auth,result):
    (out/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (out/'authorization.terminal.json').write_text(json.dumps({**auth,'status':'EXPIRED_'+result['decision'],'terminal':'receipt.json'},indent=2)+'\n')
