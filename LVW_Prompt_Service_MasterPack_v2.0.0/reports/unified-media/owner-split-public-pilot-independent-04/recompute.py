import asyncio,base64,hashlib,json,os,sys
from pathlib import Path
from types import SimpleNamespace
R=Path.cwd();O=R/'reports/unified-media/owner-split-public-pilot-independent-04';P=R/'reports/unified-media/owner-split-public-pilot-04';sys.path.insert(0,str(R/'lvw/backend'))
for key in ('LVW_PROVIDER_LEDGER','LVW_REQUIRE_BUDGET','LVW_AUTHORIZATION_CHILD'):os.environ.pop(key,None)
import httpx
from app.provider import OllamaProvider,VIDEO_APPEARANCE_TEMPLATE_SHA256
from app.video_temporal import measure_video_evidence,compose_video_spec,temporal_summary
from app.models import AnalyzeRequest
run=json.loads((P/'video-model-run.json').read_text());request=json.loads((P/'public-request.json').read_text());receipt=json.loads((P/'receipt.json').read_text());auth=json.loads((P/'authorization.json').read_text());rows=[json.loads(x) for x in (P/'provider.jsonl').read_text().splitlines()]
starts=[x for x in rows if x['event']=='provider_call_started'];assert len(starts)==1;start=starts[0]
frames=[(R/f'reports/unified-media/independent-live-14/frame-{i}.ppm').read_bytes() for i in range(4)]
sha=lambda b:hashlib.sha256(b).hexdigest()
assert [sha(x) for x in frames]==[x['sha256'] for x in run['frames']]==start['source_frame_hashes']
assert run['input_sha256']==auth['samples'][0]['sha256']==json.loads((P/'upload.json').read_text())['data']['sha256']
assert run['job_id']==receipt['job']['id'] and run['id']==receipt['job']['result_ref']
assert [(f['source_pts']*f['time_base_num']/f['time_base_den']) for f in run['frames']]==[1,3,5,7]
assert [f['target_seconds'] for f in run['frames']]==[1,3,5,7] and [f['index'] for f in run['frames']]==list(range(4))
evidence=measure_video_evidence(frames);logged=next(x for x in rows if x['event']=='temporal_evidence_prepared');assert evidence==logged['evidence'] and logged['source_sha256']==run['input_sha256'];assert len(evidence['pixel_pairs'])==len(evidence['alignment_pairs'])==3
wire=run['raw_response'];assert next(x for x in rows if x['event']=='provider_response_received')['wire_response_sha256']==sha(wire.encode())
real=httpx.AsyncClient;captured=[];records=[]
async def handler(req):
    assert req.url.path=='/api/chat';captured.append(json.loads(req.content));return httpx.Response(200,text=wire)
import app.provider as provider_module
provider_module.httpx.AsyncClient=lambda **kw:real(**kw,transport=httpx.MockTransport(handler))
p=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',30);p._record=lambda event,call,**v:records.append({'event':event,**v})
decoded=SimpleNamespace(frames=frames,manifest=[{'time_seconds':v} for v in [1.0,3.0,5.0,7.0]])
raw,appearance=asyncio.run(p.analyze_video(decoded,mode=request['mode']))
assert raw==wire and len(captured)==1
payload=captured[0];assert sha(json.dumps(payload,sort_keys=True,separators=(',',':')).encode())==start['request_payload_sha256']
assert payload['options']=={'num_ctx':4096,'num_predict':768,'temperature':.2} and payload['think'] is False
images=[base64.b64decode(x) for x in payload['messages'][-1]['images']];assert len(images)==4 and [sha(x) for x in images]==start['payload_image_sha256'] and sha(b''.join(images))==start['input_sha256']
assert 'Measured image registration' not in payload['messages'][-1]['content'] and 'Measured adjacent-frame' not in payload['messages'][-1]['content']
assert compose_video_spec(appearance,evidence).model_dump(mode='json')==run['parsed_spec']
normalized={**AnalyzeRequest(**request).model_dump(),'video_num_ctx':4096};assert sha(json.dumps(normalized,sort_keys=True).encode())==run['config_sha256'];assert run['template_sha256']==VIDEO_APPEARANCE_TEMPLATE_SHA256==start['request_template_sha256']
resources=[x for x in rows if x['event']=='running_resource_sample'];baseline=next(x for x in rows if x['event']=='admission_snapshot')['baseline'];assert baseline['gpu_free_mib']>=19047 and baseline['gpu_used_mib']<23552 and baseline['available_ram_mib']>=2048
assert resources and all(x['gpu_used_mib']<23552 and x['available_ram_mib']>=2048 for x in resources)
released=[x for x in rows if x['event']=='lease_release_sample'];assert len(released)==3 and all(x['inventory_empty'] and x['gpu_used_mib']<=baseline['gpu_used_mib']+1024 for x in released)
ownerfile=next((P/'runtime-evidence').glob('*.owner.json'));owner=json.loads(ownerfile.read_text());assert [owner]==receipt['owners'] and owner['state']=='exited' and owner['listener_owned'] is False and owner['pid']==receipt['start']['ollama']['pid'] and owner['birth_ticks']>0
assert (ownerfile.parent/(owner['nonce']+'.stop')).read_text()==owner['nonce'];assert not Path(receipt['run_root']).exists()
ledger=json.loads((O/'readonly-ledger-row.json').read_text());assert ledger['calls']==1 and ledger['full']==ledger['checkpoint']==ledger['active']==0 and ledger['elapsed']==30 and ledger['child_hash']==sha((P/'authorization.json').read_bytes()) and ledger['bindings_hash']==sha((P/'bindings.json').read_bytes())
assert receipt['settlement']['actual_model_actions']==1 and receipt['settlement']['effective_full_checkpoint'] is False
summary={'candidate':auth['candidate_sha'],'source_frames_sha_match':True,'pts_times':[1,3,5,7],'program_evidence_exact_recomputation':True,'program_summary':temporal_summary(evidence)['kind'],'request_payload_sha_matches_reconstruction':True,'one_chat_four_source_png_no_numeric_model_input':True,'raw_wire_hash_matches':True,'parsed_composition_exact_match':True,'config_sha_recomputed':run['config_sha256'],'running_samples':len(resources),'peak_gpu_used_mib':max(x['gpu_used_mib'] for x in resources),'minimum_available_ram_mib':min(x['available_ram_mib'] for x in resources),'terminal_native_pid':owner['pid'],'terminal_birth_ticks':owner['birth_ticks'],'run_root_absent':True,'readonly_ledger':{'calls':ledger['calls'],'full':ledger['full'],'checkpoint':ledger['checkpoint'],'active':ledger['active'],'elapsed':ledger['elapsed']},'reviewer_real_model_network_service_actions':0}
(O/'recomputed-checks.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
