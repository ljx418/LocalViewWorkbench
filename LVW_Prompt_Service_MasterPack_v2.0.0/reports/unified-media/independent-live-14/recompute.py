from pathlib import Path
import sys, json, hashlib, io, types, sqlite3, os
from PIL import Image,ImageChops,ImageStat
R=Path.cwd(); O=R/'reports/unified-media/independent-live-14'; L=R/'reports/unified-media/live-14'
sha=lambda b:hashlib.sha256(b).hexdigest()
a=json.loads((L/'authorization.terminal.json').read_text());v=json.loads((L/'video-model-run.json').read_text())
x={'frozen_mismatches':[], 'sample_mismatches':[], 'tool_mismatches':[], 'frames':[]}
for category,key in [('frozen','frozen_files'),('sample','samples')]:
 for item in a[key]:
  p=R/item['path']; actual=sha(p.read_bytes())
  if actual!=item['sha256']:x[category+'_mismatches'].append({'path':str(p),'actual':actual,'expected':item['sha256']})
for name,item in json.loads((L/'bindings.json').read_text()).items():
 if sha(Path(item['path']).read_bytes())!=item['sha256']:x['tool_mismatches'].append(name)
sys.path.insert(0,str(R));from lvw.backend.app import provider,build_info
x['build_id']=build_info.build_id();x['video_template']=provider.VIDEO_TEMPLATE_SHA256;x['image_template']=provider.TEMPLATE_SHA256
frames=[]; manifest=[]
for i,ref in enumerate(v['frames']):
 p=R/f'reports/unified-media/independent-live-03/frame-{i}.png';im=Image.open(p).convert('RGB');buf=io.BytesIO();im.save(buf,format='PPM');b=buf.getvalue();frames.append(b);(O/f'frame-{i}.ppm').write_bytes(b)
 rgb=list(im.getdata()); red=[(j%im.width,j//im.width) for j,c in enumerate(rgb) if c[0]>180 and c[1]<70 and c[2]<70]
 box=[min(t[0] for t in red),min(t[1] for t in red),max(t[0] for t in red),max(t[1] for t in red)]
 # White grid columns restricted to top rows, away from red foreground.
 cols=[col for col in range(im.width) if sum(1 for row in range(20,60) if min(im.getpixel((col,row)))>170)>35]
 groups=[]
 for col in cols:
  if not groups or col>groups[-1][-1]+1:groups.append([col])
  else:groups[-1].append(col)
 x['frames'].append({'index':i,'png_sha256':sha(p.read_bytes()),'ppm_sha256':sha(b),'reference_sha256':ref['sha256'],'match':sha(b)==ref['sha256'],'size':im.size,'red_bbox_inclusive':box,'grid_vertical_centers':[(g[0]+g[-1])/2 for g in groups]})
 manifest.append({**ref,'time_seconds':ref['source_pts']*ref['time_base_num']/ref['time_base_den']})
decoded=types.SimpleNamespace(frames=frames,manifest=manifest);sheet=provider.build_temporal_sheet(decoded);(O/'sheet.png').write_bytes(sheet)
x['sheet_sha256']=sha(sheet);x['pixel_measurements']=provider.temporal_pixel_measurements(frames);x['alignment_measurements']=provider.temporal_alignment_measurements(frames)
events=list(map(json.loads,(L/'runtime-evidence/provider.jsonl').read_text().splitlines()));calls=[t for t in events if t['event']=='provider_call_started']; videocall=next(t for t in calls if t['frame_count']==4)
x['sheet_matches']=sha(sheet)==videocall['input_sha256'];x['pixel_metadata_exact']=x['pixel_measurements']==videocall['pixel_measurements'];x['alignment_metadata_exact']=x['alignment_measurements']==videocall['alignment_measurements'];x['provider_calls']=len(calls);x['lease_releases']=sum(t['event']=='lease_released' for t in events)
x['api_original_process_absent']=not Path('/proc/'+str(json.loads((L/'receipt.json').read_text())['api_process']['pid'])).exists()
x['linux_listeners_on_expected_ports']=[line.strip() for name in ['/proc/net/tcp','/proc/net/tcp6'] for line in Path(name).read_text().splitlines()[1:] if line.split()[1].split(':')[-1] in ['495C','2CAA'] and line.split()[3]=='0A']
state=R.parent.parent/'.lvw-runtime/lvw-prompt-service/R1-unified/live-14';x['remaining_state_tree']=[str(p.relative_to(state)) for p in state.rglob('*')]
con=sqlite3.connect('file:/mnt/c/workSpace/videoWorkLine/.lvw-runtime/lvw-prompt-service/program02.sqlite?mode=ro',uri=True);con.row_factory=sqlite3.Row
x['ledger_schema']=[dict(row) for row in con.execute("select name,sql from sqlite_master where type='table'")]
for row in x['ledger_schema']:
 name=row['name']
 if not name.startswith('sqlite_'):
  data=[dict(t) for t in con.execute('select * from "'+name+'"')]
  x['ledger_'+name]=[d for d in data if any(str(val)=='live-14' for val in d.values())]
con.close();(O/'recomputed.json').write_text(json.dumps(x,indent=2)+'\n');print(json.dumps({k:val for k,val in x.items() if not k.startswith('ledger_')},indent=2))
