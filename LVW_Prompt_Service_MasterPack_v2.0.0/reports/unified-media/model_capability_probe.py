"""Finite metadata-only native model diagnostic; never sends inference or media."""
from pathlib import Path
import asyncio, hashlib, json, shutil, socket, subprocess, sys, time, uuid
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'lvw/backend')]
from tools import local_program_authority as program
from app.provider import OllamaProvider
from app.runtime import OllamaRuntime
import httpx

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def listening():
    with socket.socket() as connection:
        connection.settimeout(.2)
        return connection.connect_ex(('127.0.0.1',11434))==0

async def main():
    run='model-capability-probe-01';out=ROOT/'reports/unified-media'/run
    assert not out.exists(),'one-shot identity already used'
    assert not listening(),'existing service belongs to another run; leave it untouched'
    candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    paths=['lvw/backend/app','templates','tools/local_program_authority.py',str(Path(__file__).relative_to(ROOT))]
    assert subprocess.run(['git','diff','--quiet',candidate,'--',*paths],cwd=ROOT).returncode==0
    assert not subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*paths],cwd=ROOT,text=True).strip()
    binding=json.loads((ROOT/'reports/unified-media/live-14/bindings.json').read_text())
    executable=Path(binding['native_ollama']['path'])
    for name in ('native_ollama','powershell'):
        assert sha(binding[name]['path'])==binding[name]['sha256'],'tool drift'
    budget={'ollama_starts':1,'model_calls':0,'provider_calls':0,'full_checkpoints':0}
    program.reserve(run,'R1',budget,180,False)
    out.mkdir()
    temp=ROOT.parent.parent/'.lvw-runtime/lvw-prompt-service'/('metadata-'+uuid.uuid4().hex)
    program_request,program_approval=program.program_paths()
    tracked=subprocess.check_output(['git','ls-files','--',*paths],cwd=ROOT,text=True).splitlines()
    now=time.time()
    child={'run_id':run,'stage_id':'R1','issued_at':now,'expires_at':now+180,
        'frozen_files':[{'path':name,'sha256':sha(ROOT/name)} for name in tracked if (ROOT/name).is_file()],
        'tool_bindings':{name:binding[name] for name in ('native_ollama','powershell')},
        'candidate_sha':candidate,'status':'ACTIVE_ONE_SHOT','program':program_approval,
        'program_sha256':sha(ROOT/program_approval),'program_request_sha256':sha(ROOT/program_request),
        'harness_sha256':sha(__file__),'ports':[11434],'samples':[],'budget':budget,
        'metadata_requests_limit':200,'wall_seconds_limit':180,'no_media_or_inference':True,
        'cleanup':'Only the fresh runtime original native handle/nonce; retain evidence then remove own temp.',
        'stage_pass_claim':False}
    (out/'authorization.json').write_text(json.dumps(child,indent=2)+'\n');program.bind(run,out/'authorization.json')
    provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',10)
    runtime=OllamaRuntime(provider,executable,temp);result={'decision':'NO_GO','model_calls':0,'media_reads':0,'stage_pass_claim':False}
    try:
        # start/status are bounded readiness GETs; this diagnostic never acquires a model lease.
        result['start']=await asyncio.wait_for(runtime.start(),timeout=65)
        assert result['start']['ollama']['managed'] and runtime._native,'metadata only on owned native runtime'
        from app.native_runtime import proof
        assert proof(runtime._native).get('listener_owned') is True,'owned native listener not confirmed'
        async with httpx.AsyncClient(timeout=10,trust_env=False) as client:
            response=await client.post('http://127.0.0.1:11434/api/show',json={'model':'gemma4:26b','verbose':False})
            response.raise_for_status();body=response.content;show=response.json()
            template=show.get('template','');info=show.get('model_info',{})
            result['show']={'http_status':response.status_code,'response_sha256':hashlib.sha256(body).hexdigest(),
                'capabilities':show.get('capabilities',[]),'details':show.get('details',{}),
                'template_sha256':hashlib.sha256(template.encode()).hexdigest(),
                'template_has_think_reference':'think' in template.lower(),
                'template_has_image_reference':'image' in template.lower(),
                'model_info':{k:v for k,v in info.items() if k=='general.architecture' or
                    any(term in k.lower() for term in ('vision','image','projector','context_length'))},
                'private_or_internal_thinking_saved':False,'raw_template_or_system_saved':False}
            inventory=await client.get('http://127.0.0.1:11434/api/ps');inventory.raise_for_status()
            assert inventory.json().get('models')==[],'metadata unexpectedly loaded a model'
            result['loaded_models_after_show']=[]
        result['decision']='METADATA_DISCOVERY_COMPLETE_NOT_QUALITY_ACCEPTANCE'
    except Exception as error:
        result['error']=type(error).__name__+': '+str(error)
    finally:
        try:
            await asyncio.wait_for(runtime.close(),timeout=25)
            owners=list((temp/'runtime').glob('*.owner.json')) if temp.exists() else []
            result['owners']=[json.loads(p.read_text()) for p in owners]
            assert (not owners and not temp.exists()) or (len(owners)==1 and result['owners'][0]['state']=='exited' and result['owners'][0]['listener_owned'] is False)
            assert not listening(),'native listener remains'
            if temp.exists():
                shutil.copytree(temp/'runtime',out/'runtime-evidence')
                shutil.rmtree(temp)
            result['cleanup_proven']=not temp.exists() and not listening()
            assert result['cleanup_proven'],'final cleanup proof failed; retain reservation'
            result['settlement']=program.settle(run,0)
        except Exception as error:
            result['decision']='NO_GO_CLEANUP_PENDING';result['cleanup_error']=type(error).__name__+': '+str(error)
            program.close_retaining_reservation(run)
        (out/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        (out/'authorization.terminal.json').write_text(json.dumps({**child,'status':'EXPIRED_'+result['decision']},indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':asyncio.run(main())
