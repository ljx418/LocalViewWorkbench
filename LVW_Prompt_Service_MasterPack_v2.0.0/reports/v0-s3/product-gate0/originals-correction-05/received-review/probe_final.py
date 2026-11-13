"""Independent adaptation of original owner_checks O1/O2; no author probe import."""
import os,json,hashlib,threading,time,copy
from pathlib import Path
from tools import v0_s3_coordinator as c
D=Path(__file__).resolve().parent/'boundary-final';D.mkdir()
rows=[{'ordinal':i,'asset_id':'I%02d'%i,'media_kind':'image','source_sha256':'d'*64,'source_bytes':1} for i in range(1,17)]
results=[]
def setup(name):
 root=D/'synthetic'/name;(root/'sub').mkdir(parents=True)
 for n,b in [('canonical',b'{}'),('source',b'[]'),('raw',b'ORIGINAL')]: (root/'sub'/n).write_bytes(b)
 e=c.ParentOriginalEvidence(run_id='independent-04',candidate_sha='b27b0d17b71371e37002aabc5f69a030872b9177',child_sha256='b'*64,root=root,projection_sha256='c'*64)
 e.seal_plan(rows);s=root.stat();e.seal_root([s.st_dev,s.st_ino]);return root,e
def seal(e):return e.seal_originals(canonical='sub/canonical',source_plan='sub/source',raw=['sub/raw'])
def call(fn):
 try:return {'accepted':True,'result':fn()}
 except c.S3IntegrationError as ex:return {'accepted':False,'reason':str(ex)}
def mutation(root,kind):
 p=root/'sub/raw'
 if kind=='modified':p.write_bytes(b'MODIFIED')
 elif kind=='same':p.write_bytes(b'ORIGINAL')
 elif kind=='grow':p.write_bytes(b'ORIGINALMORE')
 elif kind=='truncate':p.write_bytes(b'ORI')
 elif kind=='replace':q=p.with_name('new');q.write_bytes(b'ORIGINAL');q.replace(p)
 elif kind=='link':p.rename(p.with_name('moved'));p.symlink_to('moved')
 elif kind=='ancestor':(root/'sub').rename(root/'old-sub');(root/'sub').mkdir();p.write_bytes(b'ORIGINAL')
 elif kind=='root':root.rename(root.with_name(root.name+'-old'));(root/'sub').mkdir(parents=True);p.write_bytes(b'ORIGINAL')
startfds=len(os.listdir('/proc/self/fd'))
for phase in ['seal','consume']:
 for kind in ['modified','same','grow','truncate','replace','link','ancestor','root']:
  root,e=setup(phase+'-'+kind)
  if phase=='consume':seal(e)
  previous=copy.deepcopy(e.originals);inode=(root/'sub/raw').stat().st_ino;real=os.read;fired=[]
  def read(fd,n):
   b=real(fd,n)
   if b and os.fstat(fd).st_ino==inode and not fired:
    fired.append(True);mutation(root,kind)
   return b
  os.read=read
  try:out=call(e.manifest if phase=='consume' else lambda:seal(e))
  finally:os.read=real
  assert fired and not out['accepted'],(phase,kind,out)
  assert e.originals==previous
  results.append({'case':phase+'-read-'+kind,'trigger_fired':True,'expected':'refuse without partial publication','actual':out,'originals_unchanged':True})
# Boundary missed by author nodes: mutate at actual second final open, before fstat.
for phase in ['seal','consume']:
 for kind in ['modified','same','grow','truncate']:
  root,e=setup(phase+'-rewalk-'+kind)
  if phase=='consume':seal(e)
  real=os.open;count=[];fired=[];times={}
  def op(path,flags,*args,**kwargs):
   fd=real(path,flags,*args,**kwargs)
   if str(path)=='raw':
    count.append(fd)
    if len(count)==2:
     before=os.fstat(fd);mutation(root,kind);after=os.fstat(fd);times.update({'before_ctime_ns':before.st_ctime_ns,'after_ctime_ns':after.st_ctime_ns,'before_mtime_ns':before.st_mtime_ns,'after_mtime_ns':after.st_mtime_ns,'before_size':before.st_size,'after_size':after.st_size,'same_identity':(before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)});fired.append(True)
   return fd
  # Python capability set tracks function identity; preserve real supported membership.
  support=os.supports_dir_fd;os.supports_dir_fd=set(support)|{op};os.open=op
  try:out=call(e.manifest if phase=='consume' else lambda:seal(e))
  finally:os.open=real;os.supports_dir_fd=support
  assert fired
  entry=out.get('result',{}).get('originals',out.get('result',{})).get('raw',[{}])[0]
  actual=hashlib.sha256((root/'sub/raw').read_bytes()).hexdigest()
  results.append({'case':phase+'-rewalk-'+kind,'trigger_fired':True,'fd_change_during_rewalk':times,'expected':'refuse change during rewalk before its fstat','actual':out,'actual_sha256':actual,'returned_raw_sha256':entry.get('sha256'),'stale_hash_published':out['accepted'] and actual!=entry.get('sha256')})
for phase in ['seal','consume']:
 root,e=setup(phase+'-fifo')
 if phase=='consume':seal(e)
 p=root/'sub/raw';p.unlink();os.mkfifo(p);box={};before=time.monotonic()
 def run():box.update(call(e.manifest if phase=='consume' else lambda:seal(e)))
 t=threading.Thread(target=run);t.start();t.join(.5);blocked=t.is_alive();recovered=False
 if blocked:
  # Only controlled failure recovery, never counted as successful no-writer rejection.
  w=os.open(p,os.O_WRONLY|os.O_NONBLOCK);os.close(w);t.join(2);recovered=True
 p.unlink();assert not t.is_alive()
 assert not blocked and not box['accepted'],box
 results.append({'case':phase+'-fifo','expected':'nonblocking reject without writer','actual':box,'blocked':blocked,'recovery_writer_opened':recovered,'joined':True,'fifo_removed':not p.exists(),'seconds':time.monotonic()-before})
root,e=setup('regular');seal(e);m=e.manifest();a=m['originals']['raw'][0];assert a['sha256']==hashlib.sha256(b'ORIGINAL').hexdigest() and a['bytes']==8 and m['reverification']['verified'];results.append({'case':'regular','actual':a})
for prim in ['_no_follow_open_supported','_non_block_open_supported']:
 for phase in ['seal','consume']:
  root,e=setup(prim+phase)
  if phase=='consume':seal(e)
  old=getattr(c,prim);setattr(c,prim,lambda:False)
  try:out=call(e.manifest if phase=='consume' else lambda:seal(e))
  finally:setattr(c,prim,old)
  assert not out['accepted'];results.append({'case':prim+phase,'actual':out})
# Tiny controlled cap is a seam, no product threshold is changed on disk.
oldcap=c.MAX_SEALED_ORIGINAL_BYTES;c.MAX_SEALED_ORIGINAL_BYTES=8
try:
 for phase in ['seal','consume']:
  for size in [8,9]:
   root,e=setup('cap-'+phase+str(size));(root/'sub/raw').write_bytes(b'X'*size)
   if phase=='consume':
    c.MAX_SEALED_ORIGINAL_BYTES=9;seal(e);c.MAX_SEALED_ORIGINAL_BYTES=8
   out=call(e.manifest if phase=='consume' else lambda:seal(e));assert out['accepted']==(size==8);results.append({'case':'cap-'+phase+str(size),'actual':out})
finally:c.MAX_SEALED_ORIGINAL_BYTES=oldcap
endfds=len(os.listdir('/proc/self/fd'));assert startfds==endfds
(D/'probe-results.json').write_text(json.dumps({'results':results,'fd_before':startfds,'fd_after':endfds,'all_threads_joined':True,'remaining_fifo':False},indent=2));print(json.dumps({'cases':len(results),'rewalk_accepted':[r['case'] for r in results if 'rewalk' in r['case'] and r['actual']['accepted']],'fd_before':startfds,'fd_after':endfds}))
