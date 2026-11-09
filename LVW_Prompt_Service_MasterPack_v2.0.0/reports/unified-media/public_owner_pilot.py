"""One actual public-owner video pilot; real decode/model, not a full checkpoint or browser acceptance."""
from pathlib import Path
import asyncio, hashlib, json, shutil, socket, subprocess, sys, time, uuid, os
from importlib.metadata import version
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/'lvw/backend')]
from tools import local_program_authority as program
from app.provider import OllamaProvider
from app.runtime import OllamaRuntime
from app import resources
from app.errors import AppError
from app.main import create_app
from app.config import Settings
from .acceptance_recipe import load as load_recipe
from .checkpoint_checks import verify_configs
import httpx

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def listening():
    with socket.socket() as connection:
        connection.settimeout(.2)
        return connection.connect_ex(('127.0.0.1',11434))==0

async def main():
    run='owner-split-public-pilot-04';out=ROOT/'reports/unified-media'/run
    assert not out.exists(),'one-shot identity already used'
    assert not listening(),'existing service belongs to another run; leave it untouched'
    candidate=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    paths=['lvw/backend/app','templates','tools/local_program_authority.py',str(Path(__file__).relative_to(ROOT)),
        '.agent-governance/stages/R1','reports/unified-media/acceptance_recipe.py',
        'reports/unified-media/checkpoint_checks.py','LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge']
    assert subprocess.run(['git','diff','--quiet',candidate,'--',*paths],cwd=ROOT).returncode==0
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','--',*paths],cwd=ROOT,text=True).splitlines()
    assert not [p for p in untracked if '__pycache__' not in Path(p).parts],'uncommitted production sources'
    binding=json.loads((ROOT/'reports/unified-media/live-14/bindings.json').read_text())
    executable=Path(binding['native_ollama']['path'])
    for name in ('native_ollama','powershell'):
        assert sha(binding[name]['path'])==binding[name]['sha256'],'tool drift'
    recipe=load_recipe(ROOT,program.approved())
    samples=[ROOT/recipe['positive_samples'][1]['path']]
    budget={'ollama_starts':1,'model_calls':1,'provider_calls':1,'full_checkpoints':0}
    out.mkdir()
    temp=ROOT.parent.parent/'.lvw-runtime/lvw-prompt-service'/('owner-pilot-'+uuid.uuid4().hex)
    result={'decision':'NO_GO','retained_source_frames_used':0,'new_video_decode':True,
        'stage_pass_claim':False,'internal_thinking_persisted':False,'run_root':str(temp),
        'environment':{'python':sys.version,'Pillow':version('Pillow'),'httpx':version('httpx'),'pydantic':version('pydantic')}}
    reserved=False;provider=None;runtime=None;app=None;temp_claimed=False
    child={'run_id':run,'candidate_sha':candidate,'stage_pass_claim':False}
    try:
        program.reserve(run,'R1',budget,600,False)
        reserved=True
        temp.mkdir(parents=True,exist_ok=False);temp_claimed=True
        program_request,program_approval=program.program_paths()
        tracked=subprocess.check_output(['git','ls-files','--',*paths],cwd=ROOT,text=True).splitlines()
        now=time.time()
        child={'run_id':run,'stage_id':'R1','issued_at':now,'expires_at':now+600,
            'frozen_files':[{'path':name,'sha256':sha(ROOT/name)} for name in tracked if (ROOT/name).is_file()],
            'tool_bindings':{name:binding[name] for name in ('native_ollama','powershell')},
            'model':'gemma4:26b','model_digest':json.loads((ROOT/'reports/unified-media/live-14/actual-model-identity.json').read_text())['digest'],
            'candidate_sha':candidate,'status':'ACTIVE_ONE_SHOT','program':program_approval,
            'program_sha256':sha(ROOT/program_approval),'program_request_sha256':sha(ROOT/program_request),
            'harness_sha256':sha(__file__),'ports':[11434],'owned_temp_root':str(temp),
            'budget_ledger':str(program.LEDGER),'execution_bindings_required':True,
            'samples':[{'path':str(p.relative_to(ROOT)),'sha256':sha(p)} for p in samples],'budget':budget,
            'metadata_requests_limit':200,'gpu_queries_limit':450,'sample_read_limit':16,
            'wall_seconds_limit':600,'model_sends_limit':1,'inference_config':{'thinking':False,'num_ctx':4096,'num_predict':768,'temperature':0.2,'appearance_only':True,'full_source_images':True},
            'scope':'One originaltracking public upload/analyze/readModelRun via in-process ASGI production owners plus actual native model; no mock responses, no browser/fullUM10 claim, no holdouts',
            'cleanup':'Only the fresh runtime original native handle/nonce; retain evidence then remove own temp.',
            'stage_pass_claim':False}
        (out/'authorization.json').write_text(json.dumps(child,indent=2)+'\n');program.bind(run,out/'authorization.json')
        bindings={name:binding[name] for name in ('native_ollama','powershell')}
        bindings.update({name:{'path':path,'sha256':sha(path)} for name,path in [(name,shutil.which(name)) for name in ('ffmpeg','ffprobe')]})
        bindings['python']={'path':sys.executable,'sha256':sha(sys.executable)}
        gpu_tool=shutil.which('nvidia-smi');assert gpu_tool,'missing GPU telemetry tool'
        bindings['gpu_telemetry']={'path':gpu_tool,'sha256':sha(gpu_tool)}
        (out/'bindings.json').write_text(json.dumps(bindings,indent=2)+'\n');program.bind_execution(run,out/'bindings.json')
        os.environ['LVW_AUTHORIZATION_CHILD']=str(out/'authorization.json');os.environ['LVW_REQUIRE_BUDGET']='1'
        provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',420,ledger_path=out/'provider.jsonl')
        runtime=OllamaRuntime(provider,executable,temp)
        app=create_app(Settings.local(data_root=temp),provider=provider,runtime=runtime)
        for name in ('ffmpeg','ffprobe'):
            assert getattr(app.state.media.video,name)==bindings[name]['path'],'actual decoder tool differs from binding'
        # Start/status are bounded metadata GETs; inference requires a later lease and debit.
        result['start']=await asyncio.wait_for(runtime.start(),timeout=65)
        assert result['start']['ollama']['managed'] and runtime._native,'metadata only on owned native runtime'
        from app.native_runtime import proof
        assert proof(runtime._native).get('listener_owned') is True,'owned native listener not confirmed'
        async with httpx.AsyncClient(timeout=10,trust_env=False) as client:
            tags=await client.get('http://127.0.0.1:11434/api/tags');tags.raise_for_status()
            identities=[v for v in tags.json()['models'] if v.get('name')=='gemma4:26b']
            assert len(identities)==1
            expected=json.loads((ROOT/'reports/unified-media/live-14/actual-model-identity.json').read_text())
            assert identities[0]['digest']==expected['digest'],'installed model drift'
            result['model_identity']=identities[0]
        # ASGI routes are actual public production owners, not mocked replies or internal direct analyze calls.
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1',timeout=450,trust_env=False) as client:
            upload=await client.post('/api/v1/media',headers={'Idempotency-Key':'pilot-upload'},files={'file':('tracking.mov',samples[0].read_bytes(),'video/quicktime')})
            assert upload.status_code==201,upload.text
            media=upload.json()['data']
            (out/'upload.json').write_text(json.dumps(upload.json(),indent=2)+'\n')
            request={'media_ref_id':media['id'],'mode':'realistic','config_profile':'local-default'}
            (out/'public-request.json').write_text(json.dumps(request,indent=2)+'\n')
            submitted=await asyncio.wait_for(client.post('/api/v1/jobs/analyze',headers={'Idempotency-Key':'pilot-analysis'},json=request),timeout=455)
            assert submitted.status_code==202,submitted.text
            job=(await client.get('/api/v1/jobs/'+submitted.json()['data']['id'])).json()['data']
            result['job']=job
            assert job['resource_state']=='released','physical release unconfirmed'
            if job['result_ref']:
                response=await client.get('/api/v1/model-runs/'+job['result_ref']);assert response.status_code==200
                model_run=response.json()['data']
                (out/'video-model-run.json').write_text(json.dumps(model_run,ensure_ascii=False,indent=2)+'\n')
                result['config_recomputation']=verify_configs([{'job_id':job['id'],'request':request}],[model_run])
                assert model_run['input_sha256']==sha(samples[0]) and len(model_run['frames'])==4
                assert model_run['raw_response'],'raw response lost'
            assert job['status']=='succeeded',job
            assert model_run['parsed_spec']['template_version']=='1.8.0'
            result['decision']='PUBLIC_OWNER_PILOT_COMPLETE_INDEPENDENT_SEMANTICS_PENDING'
    except Exception as error:
        detail=getattr(error,'code',str(error))
        result['error']=type(error).__name__+': '+detail
        if 'WAIT_BUDGET' in detail:result['decision']='WAIT_BUDGET'
        elif 'WAIT_AUTH' in detail:result['decision']='WAIT_AUTH'
        raw=getattr(error,'raw_response','')
        if raw:
            result['wire_response_sha256']=hashlib.sha256(raw.encode()).hexdigest()
            try:
                body=json.loads(raw);message=body.get('message',{})
                result['partial_final_content']=message.get('content','')
                result['thinking_field_present']=bool(message.get('thinking'))
                result['thinking_character_count']=len(message.get('thinking',''))
                result['done_reason']=body.get('done_reason');result['eval_count']=body.get('eval_count')
            except (ValueError,AttributeError):result['wire_envelope_parse_failed']=True
    finally:
        try:
            service_cleanup_proven=app is None
            result['service_cleanup_proven']=service_cleanup_proven
            result['lease_released']=provider is None or provider._lease is None
            try:
                if app is not None:
                    await asyncio.wait_for(app.state.analysis.close(),timeout=40)
                    owner=app.state.analysis
                    assert not any(not task.done() for task in owner._tasks),'analysis tasks still active'
                    assert not any(job.status in {'queued','preparing','running','cancelling'} for job in owner.jobs.values()),'active job remains'
                    assert all(job.resource_state=='released' for job in owner.jobs.values()),'job resource cleanup remains unproved'
                    service_cleanup_proven=True
                    result['service_cleanup_proven']=True
                if provider is not None and provider._lease is not None:
                    result['lease_released']=await asyncio.wait_for(provider.release(provider._lease[0]),timeout=32)
                else:
                    result['lease_released']=True
            except Exception as error:
                result['lease_release_error']=type(error).__name__
                result['lease_released']=False
            finally:
                if runtime is not None:
                    await asyncio.wait_for(runtime.close(),timeout=25)
            owners=list((temp/'runtime').glob('*.owner.json')) if temp_claimed and temp.exists() else []
            result['owners']=[json.loads(p.read_text()) for p in owners]
            assert (not owners and (runtime is None or (runtime.process is None and runtime._native is None))) or (len(owners)==1 and result['owners'][0]['state']=='exited' and result['owners'][0]['listener_owned'] is False)
            assert not listening(),'native listener remains'
            assert service_cleanup_proven,'service cleanup unproved; preserve temp and reservation'
            if temp_claimed and temp.exists():
                if (temp/'runtime').exists():shutil.copytree(temp/'runtime',out/'runtime-evidence')
                shutil.rmtree(temp)
            result['run_root_claimed']=temp_claimed
            result['run_root_removed']=not temp_claimed or not temp.exists()
            result['cleanup_proven']=service_cleanup_proven and result['run_root_removed'] and not listening() and result['lease_released']
            assert result['cleanup_proven'],'final cleanup proof failed; retain reservation'
            ledger=out/'provider.jsonl'
            calls=sum(json.loads(line)['event']=='provider_call_started' for line in ledger.read_text().splitlines()) if ledger.exists() else 0
            if reserved:result['settlement']=program.settle(run,calls)
            else:result['no_reservation_issued']=True
        except Exception as error:
            result['decision']='NO_GO_CLEANUP_PENDING';result['cleanup_error']=type(error).__name__+': '+str(error)
            if reserved:program.close_retaining_reservation(run)
        (out/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        (out/'authorization.terminal.json').write_text(json.dumps({**child,'status':'EXPIRED_'+result['decision']},indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':asyncio.run(main())
