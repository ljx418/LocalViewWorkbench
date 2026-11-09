from pathlib import Path
import subprocess,json,hashlib,sqlite3,io
from PIL import Image
R=Path.cwd();O=R/'reports/unified-media/independent-source-component-03';h=lambda b:hashlib.sha256(b).hexdigest();read=lambda p:json.loads(p.read_text());prefix=subprocess.check_output(['git','rev-parse','--show-prefix'],text=True).strip();results={}
for run,harness in [('source-frames-probe-03','source_frames_probe.py')]:
 L=R/'reports/unified-media'/run;a=read(L/'authorization.json');r=read(L/'receipt.json');snap=O/'snapshots'/a['candidate_sha'];mism=[]
 for f in a['frozen_files']:
  b=subprocess.check_output(['git','show',a['candidate_sha']+':'+prefix+f['path']]);p=snap/f['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
  if h(b)!=f['sha256']:mism.append(f['path'])
 for name in ['core.py','video_files.py','video_input.py','video_process.py','video_decoder.py']:
  relative='LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/'+name;p=snap/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(subprocess.check_output(['git','show',a['candidate_sha']+':'+prefix+relative]))
 bindings=read(L/'bindings.json');ev=[json.loads(t) for t in (L/'provider.jsonl').read_text().splitlines()];call=next(t for t in ev if t['event']=='provider_call_started');out=r.get('output',{});content=out.get('final_content',r.get('partial_final_content',''))
 data={'candidate_sha':a['candidate_sha'],'snapshot_frozen_mismatches':mism,'harness_sha_matches':h((snap/'reports/unified-media'/harness).read_bytes())==a['harness_sha256'],'sample_hash_matches':[h((R/f['path']).read_bytes())==f['sha256'] for f in a['samples']],'tool_mismatches':[name for name,f in bindings.items() if h(Path(f['path']).read_bytes())!=f['sha256']],'grant_hash_matches':h((R/a['program']).read_bytes())==a['program_sha256'],'grant_request_hash_matches':h((R/'reports/authorization-program-v1-complete-03.request.json').read_bytes())==a['program_request_sha256'],'model_digest_matches':a['model_digest']==r['model_identity']['digest'],'provider_starts':sum(t['event']=='provider_call_started' for t in ev),'lease_releases':sum(t['event']=='lease_released' for t in ev),'calls_inside_child_window':all(a['issued_at']<=t['time_ns']/1e9<=a['expires_at'] for t in ev),'peak_gpu_mib':max(t['gpu_used_mib'] for t in ev if t['event']=='running_resource_sample'),'minimum_ram_mib':min(t['available_ram_mib'] for t in ev if t['event']=='running_resource_sample'),'release_samples':[t for t in ev if t['event']=='lease_release_sample'],'owners':r['owners'],'final_content_sha256':h(content.encode()),'final_hash_matches':h(content.encode())==out.get('final_content_sha256',h(b'')),'wire_sha256':out.get('wire_response_sha256',r.get('wire_response_sha256')),'wire_hash_ledger_agreement':[t['wire_response_sha256'] for t in ev if t['event']=='provider_response_received'],'thinking_count_only':out.get('thinking_character_count'),'done_reason':out.get('done_reason',r.get('done_reason')),'eval_count':out.get('eval_count',r.get('eval_count')),'final_content_present':bool(content),'events':sorted(set(t['event'] for t in ev))}
 stdout='\n'.join(p.read_text(errors='replace') for p in (L/'runtime-evidence').glob('*.stdout.log'));stderr='\n'.join(p.read_text(errors='replace') for p in (L/'runtime-evidence').glob('*.stderr.log'))
 data['original_root_matches_authorization']=a['owned_temp_root']==r['run_root'];data['original_root_absent']=not Path(a['owned_temp_root']).exists();data['root_claimed']=r['run_root_claimed'];data['raw_wire_hash_matches']=h(out['raw_response'].encode())==out['wire_response_sha256'];data['raw_final_exact']=json.loads(out['raw_response'])['message']['content']==content;data['raw_thinking_absent']=not json.loads(out['raw_response'])['message'].get('thinking')
 data['native_chat_request_count']=stdout.count('POST     "/api/chat"');data['native_metadata_request_count']=sum(1 for line in stdout.splitlines() if '| GET ' in line or '"/api/show"' in line);data['native_loopback_no_cloud_witness']='OLLAMA_NO_CLOUD:true' in stderr and '127.0.0.1:11434' in stderr
 data['runtime_temp_paths']=sorted(set(__import__('re').findall(r'/mnt/c/[^\s\]\"\'}]*thinking-[a-f0-9]+',stderr)));data['runtime_temp_paths_exist']={p:Path(p).exists() for p in data['runtime_temp_paths']}
 (O/(run+'-final.json')).write_text(content)
 results[run]=data
# Independent source-pixel truth, using retained PPM only.
truth=[]
for i in range(4):
 im=Image.open(R/f'reports/unified-media/independent-live-14/frame-{i}.ppm').convert('RGB'); red=[(xx,yy) for yy in range(im.height) for xx in range(im.width) if (lambda c:c[0]>180 and c[1]<70 and c[2]<70)(im.getpixel((xx,yy)))];cols=[xx for xx in range(im.width) if sum(min(im.getpixel((xx,yy)))>170 for yy in range(20,60))>35];groups=[]
 for xx in cols:
  if not groups or xx>groups[-1][-1]+1:groups.append([xx])
  else:groups[-1].append(xx)
 truth.append({'frame':i,'red_bbox':[min(x for x,y in red),min(y for x,y in red),max(x for x,y in red),max(y for x,y in red)],'grid_centers':[(g[0]+g[-1])/2 for g in groups]})
con=sqlite3.connect('file:/mnt/c/workSpace/videoWorkLine/.lvw-runtime/lvw-prompt-service/program02.sqlite?mode=ro',uri=True);con.row_factory=sqlite3.Row
for run,data in results.items():
 row=dict(con.execute('select * from children where run=?',(run,)).fetchone());data['ledger_row']=row;L=R/'reports/unified-media'/run;data['ledger_child_hash_matches']=row['child_hash']==h((L/'authorization.json').read_bytes());data['ledger_bindings_hash_matches']=row['bindings_hash']==h((L/'bindings.json').read_bytes())
con.close();(O/'recomputed.json').write_text(json.dumps({'probes':results,'source_truth':truth},indent=2)+'\n');print(json.dumps({'probes':{run:{k:v for k,v in d.items() if k not in ['release_samples','ledger_row']} for run,d in results.items()},'source_truth':truth},indent=2))
