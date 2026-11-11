import sys,pathlib,tempfile,json,hashlib,time,os,resource,subprocess
from unittest.mock import patch
from PIL import Image
P=pathlib.Path.cwd();sys.path.insert(0,str(P/'tools'));import s3_sample_preparation as s
O=pathlib.Path(__file__).resolve().parent
results={};receipts={};cleanups=[]
def save(name,r,extra=None):
 receipts[name]=r;results[name]={'decision':r['decision'],'counts':r['counts'],'budget':r['budget'],'cleanup':r['cleanup'],**(extra or {})}
class Adapter:
 def __init__(self,tick=None,phase=None,advance=0,pad=0):self.run_log=[];self.calls=[];self.tick=tick;self.phase=phase;self.advance=advance;self.pad=pad
 def probe_video(self,*a):
  self.calls.append('probe')
  if self.phase=='probe':self.tick[0]=self.advance
  return {'exit_code':0},{'format':{'format_name':'mp4','duration':4},'streams':[{'codec_type':'video','width':8,'height':8}]}
 def extract_frame(self,p,t,out,label):
  self.calls.append('frame');Image.new('RGB',(8,8),'red').save(out)
  if self.pad:
   with out.open('ab') as h:h.write(b'x'*self.pad)
  if self.phase=='frame':self.tick[0]=self.advance
  return {'exit_code':0}
def fixture(root,video=False):
 src=root/'source';src.mkdir(parents=True);rows=[]
 for i in range(2):
  p=src/(str(i)+('.mp4' if video else '.jpg'))
  if video:p.write_bytes(b'synthetic')
  else:Image.new('RGB',(8,8),'red').save(p)
  rows.append({'file_id':str(i)*64,'relative_path':p.name,'media_kind':'video' if video else 'image','bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
 return src,rows
def run(root,src,rows,a=None,tick=None,limit=83886080):
 return s.prepare(package_root=root,child={'source_root':str(src),'selected_files':rows,'limits':dict(s.EXPECTED_LIMITS,output_bytes=limit)},runtime_root=root/'run',receipt_path=root/'receipt.json',adapter=a or Adapter(),clock=(lambda:tick[0]) if tick is not None else (lambda:0))
with tempfile.TemporaryDirectory(prefix='s3-independent-probes-') as td:
 base=pathlib.Path(td)
 for mutation in ['size','missing','during_read','same_size_hash']:
  root=base/mutation;src,rows=fixture(root);first=src/rows[0]['relative_path'];second=src/rows[1]['relative_path'];calls=dict(resolve=0,stat=0,hash=0,decode=0)
  if mutation=='size':first.write_bytes(first.read_bytes()+b'x')
  if mutation=='missing':first.unlink()
  if mutation=='same_size_hash':first.write_bytes(b'x'*first.stat().st_size)
  oldres=s.resolve_source_path;oldstat=pathlib.Path.stat;oldhash=s.sha256_file;oldopen=open;oldrender=s.render_thumbnail
  def resolve(rt,rel):
   if rel==second.name:calls['resolve']+=1
   return oldres(rt,rel)
  def stat(p,*a,**kw):
   if p==second:calls['stat']+=1
   return oldstat(p,*a,**kw)
  def hashing(p,*a,**kw):
   if p==second:calls['hash']+=1
   return oldhash(p,*a,**kw)
  class Reader:
   def __init__(self,h):self.h=h;self.done=False
   def __enter__(self):return self
   def __exit__(self,*a):self.h.close()
   def fileno(self):return self.h.fileno()
   def read(self,n):
    data=self.h.read(n)
    if not self.done:
     self.done=True
     with oldopen(first,'ab') as w:w.write(b'x')
    return data
  def opening(p,*a,**kw):
   h=oldopen(p,*a,**kw)
   return Reader(h) if isinstance(p,(str,os.PathLike)) and pathlib.Path(p)==first and mutation=='during_read' and a and a[0]=='rb' else h
  def render(p,*a,**kw):
   if p==second:calls['decode']+=1
   return oldrender(p,*a,**kw)
  with patch.object(s,'resolve_source_path',resolve),patch.object(pathlib.Path,'stat',stat),patch.object(s,'sha256_file',hashing),patch('builtins.open',opening),patch.object(s,'render_thumbnail',render):r=run(root,src,rows)
  assert r['decision']=='SOURCE_CHANGED_TERMINAL' and not any(calls.values()) and r['candidates'][1]['status']=='not_run'
  assert r['cleanup']['staging_removed'] and r['cleanup']['cleanup_process']['reaped']
  save(mutation,r,{'second_source_calls':calls})
 for phase in ['probe','frame']:
  for advance in [1200,1201]:
   name=phase+str(advance);root=base/name;src,rows=fixture(root,True);tick=[0];a=Adapter(tick,phase,advance);r=run(root,src,rows,a,tick)
   assert a.calls==(['probe'] if phase=='probe' else ['probe','frame']) and r['decision']=='BUDGET_EXHAUSTED'
   save(name,r,{'calls':a.calls})
 root=base/'staging';src,rows=fixture(root,True);a=Adapter(pad=100000);r=run(root,src,rows,a,limit=100000)
 assert r['decision']=='PREPARATION_FAILED_OUTPUT_BUDGET_EXCEEDED' and r['budget']['output_bytes_staging']>100000 and r['cleanup']['staging_removed']
 save('staging',r,{'calls':a.calls})
 # Video exact/one-under allowance includes both staging and retained, including index.
 root=base/'video_baseline';src,rows=fixture(root,True);r=run(root,src,rows);cap=r['budget']['output_bytes_cumulative'];save('video_baseline',r)
 for delta in [0,1]:
  name='video_cap_minus_'+str(delta);root=base/name;src,rows=fixture(root,True);r=run(root,src,rows,limit=cap-delta)
  assert r['decision']==('PREPARATION_COMPLETE_READY_FOR_REVIEW' if delta==0 else 'PREPARATION_FAILED_OUTPUT_BUDGET_EXCEEDED')
  assert r['budget']['output_bytes_cumulative']<=cap-delta
  save(name,r)
 # Real CPU write cap with staging already charged; inspect parent resource limit.
 parent_limit=resource.getrlimit(resource.RLIMIT_FSIZE)
 for over in [0,1]:
  target=base/('write'+str(over));b=s.OutputAccountant(1024,100,lambda:0);b.add_staging(128)
  def writer():
   with target.open('wb') as h:
    for _ in range(896+over):h.write(b'x');h.flush()
  error=None
  try:b.render(writer,target)
  except s.BudgetStop as e:error=str(e)
  assert target.stat().st_size==896 and b.total==1024 and error==('output_budget_exhausted' if over else None)
  assert resource.getrlimit(resource.RLIMIT_FSIZE)==parent_limit
  results['growth'+str(over)]={'error':error,'staging':128,'retained':target.stat().st_size,'total':b.total,'processes':b.processes,'parent_rlimit_unchanged':True}
 # Each actual CPU phase is constrained by real owned timeout; no model/decoder media.
 for phase in ['render_thumbnail','render_contact_sheet','render_index']:
  root=base/('cpu_'+phase);src,rows=fixture(root)
  original=getattr(s,phase)
  def slow(*a,**kw):time.sleep(30)
  old=s.OutputAccountant.render
  def short(b,fn,*a,**kw):
   if fn is slow:b.deadline=b.clock()+.05
   return old(b,fn,*a,**kw)
  with patch.object(s,phase,slow),patch.object(s.OutputAccountant,'render',short):r=run(root,src,rows)
  assert r['decision']=='BUDGET_EXHAUSTED' and all(p['reaped'] for p in r['cleanup']['cpu_processes'])
  save('cpu_'+phase,r)
 # Real direct child: remaining timeout propagated, process reaped, no next start.
 captured=[];oldp=subprocess.Popen
 def popen(*a,**kw):
  p=oldp(*a,**kw);captured.append(p);return p
 adapter=s.MediaAdapter(pathlib.Path('/unused'),pathlib.Path('/unused'));adapter.budget=s.OutputAccountant(deadline=time.monotonic()+.08)
 with patch.object(subprocess,'Popen',popen):
  for n in range(2):
   try:adapter._run('ffmpeg',[sys.executable,'-B','-c','import time; time.sleep(30)'],45,'owned-timeout')
   except s.BudgetStop:pass
 assert len(captured)==1 and captured[0].poll() is not None and 0<adapter.run_log[0]['timeout_seconds']<=.08
 results['real_decoder_timeout']={'pid':captured[0].pid,'returncode':captured[0].returncode,'reaped':True,'starts':len(captured),'log':adapter.run_log}
 # Real streaming flood has bounded capture, no media in log and sticky failure.
 adapter=s.MediaAdapter(pathlib.Path('/unused'),pathlib.Path('/unused'));adapter.budget=s.OutputAccountant(1024,100,lambda:0)
 try:adapter._run('ffmpeg',[sys.executable,'-B','-c','import os\nwhile True: os.write(1,b"x"*4096)'],2,'owned-flood')
 except s.BudgetStop:pass
 e=adapter.run_log[0];assert adapter.budget.failure=='output_budget_exhausted' and e['stdout_text']=='' and '_frame_bytes' not in e and e['decoder_stdout_bytes']<=1024
 results['flood']={'sticky_failure':adapter.budget.failure,'log':adapter.run_log}
 # Failed real decoder emitting otherwise valid image must not write a frame.
 exe=base/'bad-decoder';exe.write_text('#!'+sys.executable+'\nimport sys\nfrom PIL import Image\nImage.new("RGB",(8,8),"red").save(sys.stdout.buffer,format="JPEG")\nsys.stdout.flush()\nsys.exit(7)\n');exe.chmod(0o700)
 adapter=s.MediaAdapter(exe,exe);adapter.budget=s.OutputAccountant(100000,100,lambda:0);out=base/'failed-frame.jpg';e=adapter.extract_frame(base/'unused.mp4',0,out,'failed')
 assert e['exit_code']==7 and not out.exists();results['failed_decoder']={'entry':e,'frame_exists':out.exists()}
 cleanups.append({'owned_root':str(base),'entries_before':len(list(base.rglob('*'))),'bytes_before':sum(p.stat().st_size for p in base.rglob('*') if p.is_file())})
cleanups[-1]['absent_after']=not base.exists()
(O/'probe-results.json').write_text(json.dumps(results,indent=2)+'\n');(O/'probe-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n');(O/'probe-cleanup.json').write_text(json.dumps(cleanups,indent=2)+'\n')
print(json.dumps({'checks':len(results),'all_assertions_passed':True,'cleanup':cleanups},indent=2))
