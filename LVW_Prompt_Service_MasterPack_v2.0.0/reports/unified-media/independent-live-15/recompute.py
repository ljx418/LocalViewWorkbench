from pathlib import Path
from io import BytesIO
import sys,json,hashlib,sqlite3,base64,subprocess
from PIL import Image
ROOT=Path.cwd(); OUT=ROOT/'reports/unified-media/independent-live-15'; E=ROOT/'reports/unified-media/live-15'
sys.path.insert(0,str(ROOT))
from lvw.backend.app import provider as p
from lvw.backend.app.video_temporal import measure_video_evidence,compose_video_spec,temporal_summary
from lvw.backend.app.video_appearance import parse_appearance,appearance_schema
from lvw.backend.app.models import Mode,ContentProfile
from lvw.backend.app.build_info import build_id
J=lambda n:json.loads((E/n).read_text()); H=lambda v:hashlib.sha256(v).hexdigest(); C=lambda v:H(json.dumps(v,sort_keys=True,separators=(',',':')).encode())
checks=[]
def ck(n,v,detail=None):
 checks.append({'check':n,'pass':bool(v),'detail':detail});print(n, bool(v), json.dumps(detail,ensure_ascii=False) if detail is not None else '')
video=J('video-model-run.json');events=[json.loads(l) for l in (E/'runtime-evidence/provider.jsonl').read_text().splitlines()]; starts=[e for e in events if e['event']=='provider_call_started'];vstart=next(x for x in starts if x['lease_job_id']==video['job_id'])
frames=[]; imgs=[]; oracle=[]
for i in range(4):
 b=(ROOT/f'reports/unified-media/independent-live-14/frame-{i}.ppm').read_bytes();frames.append(b);im=Image.open(BytesIO(b)).convert('RGB');buf=BytesIO();im.save(buf,format='PNG');imgs.append(buf.getvalue())
 ck('retained-frame-'+str(i),H(b)==video['frames'][i]['sha256'],{'ppm_sha':H(b),'size':im.size,'pts_seconds':video['frames'][i]['source_pts']/12288})
 pixels=im.load();red=[];grid=[]
 for y in range(im.height):
  for x in range(im.width):
   r,g,bl=pixels[x,y]
   if r>200 and g<60 and bl<60:red.append((x,y))
 # independently measure cyan/blue light grid vertical stripe at y=100, away from red
 for x in range(im.width):
  r,g,bl=pixels[x,100]
  if r>160 and g>160 and bl>160:grid.append(x)
 runs=[]
 for x in grid:
  if not runs or x>runs[-1][-1]+1:runs.append([x])
  else:runs[-1].append(x)
 oracle.append({'index':i,'red_bbox':[min(x for x,y in red),min(y for x,y in red),max(x for x,y in red),max(y for x,y in red)],'row100_grid_centers':[(a[0]+a[-1])/2 for a in runs]})
ck('all-source-lossless-png-hashes', [H(x) for x in imgs]==vstart['payload_image_sha256'],[H(x) for x in imgs]); print('INDEPENDENT_PIXEL_ORACLE',json.dumps(oracle))
temporal=measure_video_evidence(frames); recorded=next(e['evidence'] for e in events if e['event']=='temporal_evidence_prepared' and e['call_id']==video['job_id']);ck('CPU-temporal-every-value',temporal==recorded);ck('sampled-useful-relative-summary',temporal_summary(temporal)['kind']=='apparent_relative_horizontal',temporal_summary(temporal))
messages=p.build_messages('realistic','standard','');messages[0]['content']=p.VIDEO_APPEARANCE_SYSTEM;messages[-1]['content']=str(messages[-1]['content']).replace(p.TEMPLATE_TEXT,p.VIDEO_APPEARANCE_TASK);messages[-1]['content']+='\nActual populated SOURCE image count: 4. Actual frame times (seconds): '+json.dumps([1.0,3.0,5.0,7.0]);messages[-1]['images']=[base64.b64encode(b).decode('ascii') for b in imgs]
payload={'model':'gemma4:26b','messages':messages,'stream':False,'think':False,'format':appearance_schema(4),'options':{'num_ctx':4096,'num_predict':768,'temperature':.2},'keep_alive':0};ck('video-actual-request-sha',C(payload)==vstart['request_payload_sha256'],C(payload));ck('template-sha',p.VIDEO_APPEARANCE_TEMPLATE_SHA256==video['template_sha256']==vstart['request_template_sha256'])
a=parse_appearance(json.loads(video['raw_response']),mode='realistic',frame_times=[1.,3.,5.,7.]);ck('full-composed-spec-every-value',compose_video_spec(a,temporal).model_dump(mode='json')==video['parsed_spec'])
for name in ['image-model-run.json','video-model-run.json']:
 run=J(name);req=next(json.loads(l)['request'] for l in (E/'public-analysis-requests.jsonl').read_text().splitlines() if json.loads(l)['job_id']==run['job_id']);req['video_num_ctx']=4096 if name.startswith('video') else None;ck(name+'-configuration',H(json.dumps(req,sort_keys=True).encode())==run['config_sha256'],H(json.dumps(req,sort_keys=True).encode()));response=next(e for e in events if e['event']=='provider_response_received' and e['lease_job_id']==run['job_id']);ck(name+'-immutable-wire',H(run['raw_response'].encode())==response['wire_response_sha256'])
recipe=json.loads((ROOT/'.agent-governance/stages/R1/09-real-acceptance-recipe.json').read_text())
for n in J('negative-results.json')['cases']:
 raw=(E/(n['id']+'-response.raw')).read_bytes();r=json.loads(raw);expected=next(v for v in recipe['negative_cases'] if v['id']==n['id']);ck(n['id'],n['actual_status']==expected['expected_status'] and r['error']['code']==expected['expected_error'] and H(raw)==n['raw_response_sha256'] and n['before']==n['after']=={'media_and_temp':[],'owned_open_files':[]} and n['model_calls']==0 and n['published_media_ref'] is False)
for c in J('cancellation-results.json')['cases']:
 job=c['job_id']; sent=[x for x in starts if x['lease_job_id']==job];ck('cancel-'+c['phase'],c['terminal']['status']=='cancelled' and c['terminal']['result_ref'] is None and c['terminal']['resource_state']=='released' and (not sent if c['phase']!='running' else len(sent)==1),{'provider_calls':len(sent),'feedback_ms':c.get('feedback_ms',c.get('cancel_response',{}).get('feedback_ms'))})
for s in starts:
 job=s['lease_job_id'];end=next((e for e in events if e['event']=='provider_call_completed' and e['lease_job_id']==job),s);release=next(e for e in events if e['event']=='lease_released' and e['call_id']==job);ck('release-'+job,(release['time_ns']-end['time_ns'])/1e9<=30,{'release_seconds_after_call':(release['time_ns']-end['time_ns'])/1e9})
samples=[x for x in events if 'gpu_used_mib'in x];ck('hard-resources',max(x['gpu_used_mib'] for x in samples)<23552 and min(x['available_ram_mib'] for x in samples)>=2048,{'peak_gpu_mib':max(x['gpu_used_mib'] for x in samples),'minimum_ram_mib':min(x['available_ram_mib'] for x in samples)})
ck('source-build-id',build_id()==J('receipt.json')['source_build_id']==J('windows-health.json')['data']['build_id'],build_id())
auth=J('authorization.json');bind=J('bindings.json');ck('bindings-hash',H((E/'bindings.json').read_bytes())==J('authorization.terminal.json')['bindings_sha256'],H((E/'bindings.json').read_bytes()))
for key,val in bind.items():ck('executable-'+key,H(Path(val['path']).read_bytes())==val['sha256'])
for val in auth['frozen_files']:ck('bound-source-'+val['path'],H(Path(val['path']).read_bytes())==val['sha256'])
c=sqlite3.connect('file:/mnt/c/workSpace/videoWorkLine/.lvw-runtime/lvw-prompt-service/program02.sqlite?mode=ro',uri=True);c.row_factory=sqlite3.Row;row=dict(c.execute('select * from children where run=?',('live-15',)).fetchone());allrows=[dict(r) for r in c.execute('select run,calls,checkpoint,active,elapsed from children')];c.close();(OUT/'readonly-ledger.json').write_text(json.dumps({'live15':row,'all_rows':allrows},indent=2));ck('ledger-terminal',row['calls']==3 and row['checkpoint']==1 and row['active']==0 and row['elapsed']==72,row);ck('ledger-bindings',row['child_hash']==H((E/'authorization.json').read_bytes()) and row['bindings_hash']==H((E/'bindings.json').read_bytes()))
state=ROOT.parent.parent/'.lvw-runtime/lvw-prompt-service/R1-unified/live-15'; ck('private-data-roots-removed',not list(state.rglob('lvw-user-*')) and not [x for x in state.rglob('*') if x.is_file()],{'remaining_empty_directories':[str(x) for x in state.rglob('*') if x.is_dir()]});ck('api-original-pid-absent',not Path('/proc/'+str(J('receipt.json')['api_process']['pid'])).exists())
(OUT/'recomputed.json').write_text(json.dumps({'checks':checks,'pixel_oracle':oracle,'temporal':temporal,'failed':[x for x in checks if not x['pass']]},indent=2,ensure_ascii=False));print('FAILED',sum(not x['pass'] for x in checks))
