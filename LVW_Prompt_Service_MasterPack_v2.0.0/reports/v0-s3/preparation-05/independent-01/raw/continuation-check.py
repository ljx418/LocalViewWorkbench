"""Read only retained evidence; synthetic counterexamples only in owned TemporaryDirectory."""
import hashlib,json,pathlib,sys,tempfile,subprocess,re,types
P=pathlib.Path(__file__).resolve().parents[5]
O=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(P/'tools'))
import s3_sample_preparation as s
from PIL import Image
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())
R=P/'reports/v0-s3/preparation-05/implementation/run-01'
r=read(R/'receipt.json'); pf=read(R/'preflight.json')
# Explicit runtime argument: never follow source paths from receipt.
T=pathlib.Path(sys.argv[1]); assert T.name=='run-01' and T.parent.name=='s3-preview-c01'
result={'scope':'retained derivatives/text/Git/installed binaries plus owned synthetic fixtures; no original media access','bindings':{},'synthetic':{}}
for key,rel in [('child',s.CHILD_REL),('catalog',s.CATALOG_REL),('holdout',s.HOLDOUT_REL),('packet',s.PACKET_REL),('script',s.SCRIPT_REL),('test',s.TEST_REL),('runner',s.BRIDGE_RUNNER_REL),('execution_control','plans/execution-control.json'),('docs24','docs/24_EXECUTION_MASTER_PLAN.md')]:
 result['bindings'][key]={'path':rel,'sha256':sha((P/rel).read_bytes())}
for rel in [s.SCRIPT_REL,s.TEST_REL,s.BRIDGE_RUNNER_REL]:
 blob=subprocess.check_output(['git','show','e1798f33ba51dcadbf9f0333641d62d14a801491:'+P.name+'/'+rel],cwd=P)
 assert blob==(P/rel).read_bytes()
result['candidate_blobs_match']=True
result['root_ancestor']=subprocess.run(['git','merge-base','--is-ancestor','20e408db8371a1058a5c44c059d1601caf964d85','335a8b973ab9b0fe192c03f59e608f9976658238'],cwd=P).returncode==0
for name in ['python','ffmpeg','ffprobe']:
 tool=pf['tools'][name]; assert sha(pathlib.Path(tool['real_path']).read_bytes())==tool['sha256']
result['installed_executable_hashes_match']=True
pillow_image=pathlib.Path(pf['tools']['pillow']['package_path']).with_name('Image.py')
result['pillow_image_module_match']=sha(pillow_image.read_bytes())==pf['tools']['pillow']['image_module_sha256']
child=read(P/s.CHILD_REL); freeze=read(P/s.HOLDOUT_REL)
v={x['video_sha256'] for x in freeze['videos']}; h=set(child['holdout_content_sha256'])
result['holdout']={'videos':len(v),'listed':len(h),'missing':sorted(v-h),'extras_are_metadata':h-v=={freeze['expected_sha256'],freeze['assets_manifest_sha256']}}
files=[]
for f in r['runtime']['files']:
 rel=pathlib.Path(f['path']).relative_to(r['runtime']['relative_path']); assert '..' not in rel.parts
 data=(T/rel).read_bytes(); assert sha(data)==f['sha256'] and len(data)==f['bytes']
 files.append({'relative_path':str(rel),'sha256':sha(data),'bytes':len(data)})
result['retained_tree']={'verified':len(files),'bytes':sum(x['bytes'] for x in files),'files':files,'staging_absent':not (T/'staging').exists()}
links=re.findall(r'(?:href|src)="([^"]+)"',(T/'index.html').read_text())
assert all(not x.startswith(('/', 'http:', 'https:', 'file:')) and '..' not in pathlib.Path(x).parts and (T/x).is_file() for x in links)
result['relative_links_verified']=len(links)
for item in r['raw_evidence']['commands']:
 prefix='%03d-%s'%(item['index'],item['label'])
 cmd=(T/'raw'/(prefix+'.command.log')).read_bytes().rstrip(b'\n');assert sha(cmd)==item['command_sha256']
 for stream in ['stdout','stderr']:
  data=(R/'raw'/(prefix+'.'+stream+'.log')).read_bytes(); assert sha(data)==item[stream+'_sha256'] and len(data)==item[stream+'_bytes']
 assert (R/'raw'/(prefix+'.exit.log')).read_text().strip()=='0'
result['commands']={'total':len(r['raw_evidence']['commands']),'ffprobe':sum(x['kind']=='ffprobe' for x in r['raw_evidence']['commands']),'ffmpeg':sum(x['kind']=='ffmpeg' for x in r['raw_evidence']['commands']),'all_hashes_and_exits_match':True}
result['recorded_budget']=r['budget'];result['recorded_counts']=r['counts']
assert len(r['candidates'])==32
for row,original in zip(r['candidates'],child['selected_files']):
 assert row['file_id']==original['file_id'] and row['source_sha256_observed']==original['sha256']
result['source_hashes_status']='32 receipt values match child; originals NOT rehashed'
result['tests']={'prior_stdout':(O/'pytest-run-01.stdout.log').read_text(),'prior_exit':(O/'pytest-run-01.exit.log').read_text(),'test_function_count':len(re.findall(r'^def test_', (P/s.TEST_REL).read_text(),re.M)),'suite_rerun':False}
# No subprocess decoder calls in counterexamples.
with tempfile.TemporaryDirectory(prefix='s3-independent-continuation-') as tmp:
 base=pathlib.Path(tmp); src=base/'source';src.mkdir()
 def entry(name,kind='image'):
  q=src/name;return {'file_id':sha(name.encode()),'relative_path':name,'media_kind':kind,'bytes':q.stat().st_size,'sha256':sha(q.read_bytes())}
 def run(name,entries,adapter,clock=lambda:0,limit=None):
  limits=dict(s.EXPECTED_LIMITS)
  if limit is not None:limits['output_bytes']=limit
  return s.prepare(package_root=base,child={'selected_files':entries,'source_root':str(src),'limits':limits},runtime_root=base/name,adapter=adapter,receipt_path=base/(name+'.json'),clock=clock)
 blank=types.SimpleNamespace(run_log=[])
 for n in ['a.jpg','b.jpg']:Image.new('RGB',(8,8),'red').save(src/n)
 a,b=entry('a.jpg'),entry('b.jpg');(src/'a.jpg').write_bytes((src/'a.jpg').read_bytes()+b'changed')
 out=run('size-change',[a,b],blank)
 result['synthetic']['size_change']={'decision':out['decision'],'reasons':[x['reason'] for x in out['candidates']],'hash_calls':out['budget']['source_files_hashed'],'image_decodes':out['budget']['image_decode_calls'],'expected':'SOURCE_CHANGED terminal; no later candidate access','defect_reproduced':out['budget']['image_decode_calls']==1}
 (src/'fake.mp4').write_bytes(b'synthetic-not-a-real-video');video=entry('fake.mp4','video');time=[0];calls=[]
 class Fake:
  run_log=[]
  def probe_video(self,path,label):
   time[0]=1201;calls.append('probe');return {'exit_code':0},{'format':{'format_name':'mp4','duration':'4'},'streams':[{'codec_type':'video','width':8,'height':8}]}
  def extract_frame(self,path,offset,output,label):
   calls.append('frame_after_deadline');Image.new('RGB',(8,8),'blue').save(output);return {'exit_code':0}
 out=run('deadline',[video],Fake(),clock=lambda:time[0])
 result['synthetic']['deadline']={'decision':out['decision'],'wall_seconds_used':out['budget']['wall_seconds_used'],'calls':calls,'defect_reproduced':len(calls)==5 and out['decision']=='PREPARATION_COMPLETE_READY_FOR_REVIEW'}
 # Terminal output budget ignores already removed staging at final verdict.
 # Tiny fake clip writes bounded synthetic frames; set cap from observed staging+retained values.
 result['synthetic']['size_change']['staging_removed']=not (base/'size-change/staging').exists()
 result['synthetic']['deadline']['staging_removed']=not (base/'deadline/staging').exists()
 result['owned_cleanup']={'entries_before':len(list(base.rglob('*'))),'bytes_before':sum(x.stat().st_size for x in base.rglob('*') if x.is_file())}
result['owned_cleanup']['temporary_root_absent_after']=not base.exists()
result['owned_cleanup']['historical_or_original_artifacts_deleted']=0
(O/'continuation-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='retained_tree'},ensure_ascii=False,indent=2))
print('retained files',len(files),'bytes',sum(x['bytes'] for x in files))
