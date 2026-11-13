"""Independent adaptation of received-review/probe_final.py; no author code imported."""
import os,json,hashlib,copy,threading,time,stat
from pathlib import Path
from tools import v0_s3_coordinator as c
D=Path(__file__).resolve().parent
B=D/'synthetic';B.mkdir()
results=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def setup(name):
 root=B/name;(root/'sub').mkdir(parents=True)
 for n,b in [('canonical',b'{}'),('source',b'[]'),('raw',b'ORIGINAL')]: (root/'sub'/n).write_bytes(b)
 e=c.ParentOriginalEvidence(run_id='independent-05',candidate_sha='07277a6f2f6f730dc7b9383bfeaf8c412126fe16',child_sha256='b'*64,root=root,projection_sha256='c'*64)
 e.seal_plan([{'ordinal':i,'asset_id':'I%02d'%i,'media_kind':'image','source_sha256':'d'*64,'source_bytes':1} for i in range(1,17)])
 s=root.stat();e.seal_root([s.st_dev,s.st_ino]);return root,e
def seal(e):return e.seal_originals(canonical='sub/canonical',source_plan='sub/source',raw=['sub/raw'])
def call(fn):
 try:return {'accepted':True,'result':fn()}
 except c.S3IntegrationError as ex:return {'accepted':False,'reason':str(ex)}
def meta(s):return {'dev':s.st_dev,'ino':s.st_ino,'size':s.st_size,'ctime_ns':s.st_ctime_ns,'mtime_ns':s.st_mtime_ns,'regular':stat.S_ISREG(s.st_mode)}
fd_before=len(os.listdir('/proc/self/fd'))
for phase in ['seal','manifest']:
 for kind in ['modified','same','grow','truncate','unchanged']:
  root,e=setup(phase+'-'+kind)
  if phase=='manifest':seal(e)
  previous=copy.deepcopy(e.originals);target=root/'sub/raw'
  realopen,realfstat,realread,realclose=os.open,os.fstat,os.read,os.close
  count={};fdmap={};observations=[];read_chunks=[];times={};fired=[]
  def op(path,flags,*args,**kwargs):
   fd=realopen(path,flags,*args,**kwargs)
   if str(path) in ['raw','canonical','source']:
    name=str(path);count[name]=count.get(name,0)+1;fdmap[fd]=(name,count[name])
    assert flags & os.O_NOFOLLOW and flags & os.O_NONBLOCK
    if name=='raw' and count[name]==2:
     before=realfstat(fd)
     if kind!='unchanged':target.write_bytes({'modified':b'MODIFIED','same':b'ORIGINAL','grow':b'ORIGINALMORE','truncate':b'ORI'}[kind])
     after=realfstat(fd);times.update(before=meta(before),after=meta(after));fired.append(True)
   return fd
  def fs(fd):
   s=realfstat(fd)
   if fd in fdmap:observations.append({'artifact':fdmap[fd][0],'opening':fdmap[fd][1],'actual_fstat':meta(s)})
   return s
  def rd(fd,n):
   b=realread(fd,n)
   if fdmap.get(fd,('',0))[0]=='raw':read_chunks.append(b)
   return b
  def cl(fd):
   fdmap.pop(fd,None);return realclose(fd)
  support=os.supports_dir_fd;os.supports_dir_fd=set(support)|{op};os.open,os.fstat,os.read,os.close=op,fs,rd,cl
  try:out=call(e.manifest if phase=='manifest' else lambda:seal(e))
  finally:os.open,os.fstat,os.read,os.close=realopen,realfstat,realread,realclose;os.supports_dir_fd=support
  changed=kind!='unchanged';actual=target.read_bytes();consumed=b''.join(read_chunks)
  assert fired and count=={'canonical':2,'source':2,'raw':2},count
  assert out['accepted']==(not changed),out
  assert consumed==b'ORIGINAL'
  rawobs=[s for s in observations if s['artifact']=='raw'];last=rawobs[-1]['actual_fstat']
  assert last==times['after'] and rawobs[-1]['opening']==2
  assert times['before']['dev']==times['after']['dev'] and times['before']['ino']==times['after']['ino']
  if changed:
   assert any(times['before'][k]!=times['after'][k] for k in ['size','ctime_ns','mtime_ns'])
   assert out['reason']=='S3_ORIGINAL_CHANGED:raw'
   assert e.originals==previous
  else:
   entry=out['result'].get('originals',out['result'])['raw'][0]
   assert entry['sha256']==sha(actual)==sha(consumed) and entry['bytes']==8
   if phase=='manifest':assert out['result']['reverification']['verified']
  results.append({'case':phase+'-rewalk-'+kind,'expected':'reject' if changed else 'accept','trigger_fired':True,'same_object':True,'opens':count,'fd_metadata_at_trigger':times,'candidate_actual_fstats':observations,'consumed_bytes':len(consumed),'consumed_sha256':sha(consumed),'actual_sha256':sha(actual),'actual':out,'originals_unchanged_on_rejection':e.originals==previous if changed else None,'partial_or_verified_publication_on_rejection':False if changed else None,'passed':True})
# Small anti-regression checks only: real FIFO without writer, missing no-follow, FD cleanup.
for phase in ['seal','manifest']:
 root,e=setup(phase+'-fifo')
 if phase=='manifest':seal(e)
 target=root/'sub/raw';target.unlink();os.mkfifo(target);box={}
 def run():box.update(call(e.manifest if phase=='manifest' else lambda:seal(e)))
 t=threading.Thread(target=run);t.start();t.join(.5);blocked=t.is_alive();recovery=False
 if blocked:
  w=os.open(target,os.O_WRONLY|os.O_NONBLOCK);os.close(w);t.join(2);recovery=True
 assert not t.is_alive()
 target.unlink()
 assert not blocked and not box['accepted'],box
 results.append({'case':phase+'-fifo','actual':box,'blocked':blocked,'recovery_writer_opened':recovery,'joined':True,'fifo_removed':True,'passed':True})
for phase in ['seal','manifest']:
 root,e=setup(phase+'-unsupported')
 if phase=='manifest':seal(e)
 old=c._no_follow_open_supported;c._no_follow_open_supported=lambda:False
 try:out=call(e.manifest if phase=='manifest' else lambda:seal(e))
 finally:c._no_follow_open_supported=old
 assert not out['accepted'] and out['reason']=='S3_ORIGINAL_SAFE_OPEN_UNSUPPORTED'
 results.append({'case':phase+'-unsupported','actual':out,'passed':True})
fd_after=len(os.listdir('/proc/self/fd'));assert fd_before==fd_after
assert not any(stat.S_ISFIFO(x.lstat().st_mode) for x in B.rglob('*'))
(D/'probe-results.json').write_text(json.dumps({'results':results,'unique_cases':len(results),'executions':len(results),'fd_before':fd_before,'fd_after':fd_after,'all_threads_joined':True,'remaining_fifo':False},indent=2))
print(json.dumps({'passed':len(results),'rejected_changes':8,'unchanged_positives':2,'fd_before':fd_before,'fd_after':fd_after}))
