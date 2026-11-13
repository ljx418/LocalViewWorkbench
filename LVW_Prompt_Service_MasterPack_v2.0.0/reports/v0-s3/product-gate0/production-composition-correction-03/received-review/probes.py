import contextlib,io,json,os,errno,threading,hashlib,copy
from pathlib import Path
import pytest
from tools import test_v0_s3_production_composition as data
from tools import v0_s3_production_controller as c,v0_s3_quality_worker as w,v0_s3_controller_io as safe
D=Path(__file__).parent
CAND='8f375f887f0121ab5a0395f032dd74d8a6f0cf0b'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,v):(D/(n+'.json')).write_text(json.dumps(v,indent=2,default=str))
def live():
 result={}
 for x in os.listdir('/proc/self/fd'):
  try:
   s=os.fstat(int(x));result[int(x)]=[s.st_dev,s.st_ino,s.st_mode]
  except OSError:pass
 return result
def build(n,**kw):
 p=D/'cases'/n;p.mkdir(parents=True)
 return data._build_composition(p,**kw)
def run(comp,m,transition=None,factory=None,holder=None):
 seam=c.OfflineCompositionSeam(driver_factory=factory or (lambda ctx:data._helpers().SyntheticDriver(ctx.root,comp['driver_failure'])),context_sha256=comp['worker_context_sha256']);seam.on_transition=transition
 orig=c.ProductionController;held=[]
 class Injected(orig):
  def __init__(self,ctx):super().__init__(ctx,seam=seam);held.append(self)
 out=io.StringIO();err=io.StringIO();exception=None;code=None
 try:
  with m.context() as mm:
   mm.setattr(c,'ProductionController',Injected)
   with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):code=c.main(['--context',str(comp['controller_context_path']),'--context-sha256',sha(comp['controller_context_path'].read_bytes())])
 except BaseException as e:exception=type(e).__name__
 if holder is not None:holder.update(seam=seam,obj=held[0] if held else None)
 text=out.getvalue();r=json.loads(text) if text.strip() else None
 return {'exit':code,'receipt':r,'stdout':text,'stderr':err.getvalue(),'exception':exception,'thread_alive':bool(seam._worker and seam._worker._thread.is_alive())}
def worker(n):
 comp=build(n);return comp,w.WorkerContext.load(comp['worker_context_path'],expected_sha256=comp['worker_context_sha256'])
def positive(m):
 comp=build('positive');v=run(comp,m);save('positive',v);r=v['receipt'];assert v['exit']==0 and r['state']=='SUMMARY_PERSISTED' and r['receipt_persisted']
 can=json.loads((comp['root']/'temp/s3-quality/qd-receipt.json').read_bytes());assert can['test_counts']['PASS']==16
 for k in ['output_contract','no_overwrite','resource_budget']:assert r['receipts'][k]['status']=='BLOCKED'
 assert r['composition_facts'] and all(x['name'] not in r['receipts'] for x in r['composition_facts'])
 assert r['summary']['pass_count']==0 and r['root_retained'] and not r['cleanup_proven']
 for cat in ['canonical','source_plan','raw']:
  for x in r['manifest']['originals'][cat]:assert sha((comp['root']/x['reference']).read_bytes())==x['sha256']
 prov=r['summary']['provenance'];assert prov['controller_context']['sha256']==sha(comp['controller_context_path'].read_bytes());assert prov['worker_context']['sha256']==comp['worker_context_sha256']
 disk=json.loads(Path(r['receipt_path']).read_bytes());assert 'fd_cleanup_post_release' not in disk and r['fd_cleanup_post_release']['fd_leaked']==[]
 assert r['fd_cleanup']['controller_anchor_descriptors_scope'].startswith('THE_BOUND_ROOT_AND_THE_OUTPUT_DIRECTORY') and not v['thread_alive']
 save('positive-oracle',{'canonical_counts':can['test_counts'],'persisted_keys':list(disk),'provenance':prov,'post_release_only_in_return':True})
def m04_ref(m,kind):
 comp,ctx=worker('m04-'+kind);assert getattr(ctx,kind)() is not None
 parent=Path(ctx.document[kind+'_path']).parent;moved=parent.with_name(parent.name+'-moved');parent.rename(moved);parent.symlink_to(moved,target_is_directory=True)
 # target is physically within root but must still refuse any ancestor link
 error=None
 try:getattr(ctx,kind)()
 except w.WorkerError as e:error=e.code
 save('M04-'+kind,{'error':error,'outside_bytes_consumed':error is None});assert error

def m04_external(m,mode):
 comp,ctx=worker('m04-external-'+mode);base=D/'cases'/('m04-external-'+mode);parent=base/'dependency-parent';anchor=parent/'deps';anchor.mkdir(parents=True);f=anchor/'named.txt';f.write_bytes(b'sealed named external dependency')
 doc=copy.deepcopy(ctx.document);doc['reference_anchors'][1]['path']=str(anchor)
 manifest={'schema':data.DEPENDENCY_MANIFEST_SCHEMA,'scope':data.DEPENDENCY_MANIFEST_SCOPE,'path':str(anchor),'files':[{'path':str(f),'sha256':sha(f.read_bytes())}]}
 p=Path(doc['dependency_manifest_path']);p.write_text(json.dumps(manifest));doc['dependency_manifest_sha256']=sha(p.read_bytes());ctx=w.WorkerContext(doc)
 assert ctx.dependency_manifest()==manifest
 if mode=='legal':save('M04-external-legal',manifest);return
 moved=parent.with_name('outside');parent.rename(moved);parent.symlink_to(moved,target_is_directory=True)
 error=None
 try:ctx.dependency_manifest()
 except w.WorkerError as e:error=e.code
 save('M04-external-ancestor',{'error':error,'accepted_outside':error is None,'target':str(moved),'declared_anchor':str(anchor)});assert error,'external anchor parent symlink accepted'

def m04_io(m,mode):
 base=D/'cases'/('io-'+mode);base.mkdir(parents=True);p=base/'file';p.write_bytes(b'x'*16);requests=[];rd=os.read;fst=os.fstat
 if mode in ['over','lying']:p.write_bytes(b'x'*17)
 if mode=='fifo':p.unlink();os.mkfifo(p)
 if mode=='directory':p.unlink();p.mkdir()
 def read(fd,n):requests.append(n);return rd(fd,n)
 m.setattr(safe.os,'read',read)
 if mode=='lying':
  class Size:
   def __init__(self,s):
    for name in dir(s):
     if name.startswith('st_'):setattr(self,name,getattr(s,name))
    self.st_size=16
  m.setattr(safe.os,'fstat',lambda fd:Size(fst(fd)))
 if mode=='unsupported':m.setattr(safe,'safe_open_supported',lambda:False)
 error=None;raw=None
 try:raw=safe.read_bounded_in_root(base,'file',16)
 except safe.ControllerIOError as e:error=e.code
 if mode=='fifo':p.unlink()
 save('M04-io-'+mode,{'error':error,'requests':requests,'length':len(raw) if raw else None})
 assert sum(requests)<=17
 if mode=='exact':assert raw==b'x'*16
 else:assert error

def m05(m,mode):
 comp=build('m05-'+mode);original=c.load_published_execution_receipt;seen={}
 def loader(root,**kw):
  doc=original(root,**kw);seen['boundary']=type(kw.get('boundary')).__name__;seen['old_counts']=dict(doc['test_counts'])
  if mode=='disk-window':
   p=Path(root)/'qd-receipt.json';actual=json.loads(p.read_bytes());actual['test_counts']['PASS']=15;actual['test_counts']['FAIL']=1;actual['rows'][-1]['execution_status']='FAIL';actual['rows'][-1]['error_code']='INDEPENDENT_PARSE_WINDOW';p.write_text(json.dumps(actual));seen['actual_counts']=actual['test_counts'];seen['actual_hash']=sha(p.read_bytes())
  elif mode=='type-bool':doc['rows'][0]['provider_call_count']=True
  elif mode=='invalid-loader':
   # verify the real frozen loader still rejects wrong kind from same boundary bytes
   pass
  return doc
 if mode=='invalid-loader':
  def transition(state,obj):
   if state=='WORKER_SUPERVISED':
    p=comp['root']/'temp/s3-quality/qd-receipt.json';doc=json.loads(p.read_bytes());doc['kind']='independent-invalid';p.write_text(json.dumps(doc))
  v=run(comp,m,transition=transition)
 else:
  m.setattr(c,'load_published_execution_receipt',loader);v=run(comp,m)
 save('M05-'+mode,{**v,'oracle':seen});assert v['receipt']['state']=='UNKNOWN_RETAINED' and not v['receipt']['summary_persisted']
 if mode=='disk-window':assert seen['old_counts']['PASS']==16 and seen['actual_counts']['FAIL']==1

def m06(m,stage,target):
 n='m06-'+stage+'-'+target;comp=build(n);root=comp['root'];observed={}
 def transition(state,obj):
  if state!=stage:return
  p={'root':root,'temp':root/'temp','controller':root/'temp/s3-production-controller','ancestor':root.parent}[target]
  if not p.exists():p.mkdir()
  moved=p.with_name(p.name+'-retained');p.rename(moved)
  if target=='ancestor':p.symlink_to(moved,target_is_directory=True)
  else:p.mkdir()
  observed.update(path=str(p),retained=str(moved),files_before=sorted(str(x.relative_to(p)) for x in p.rglob('*') if x.is_file()))
 v=run(comp,m,transition=transition)
 p=Path(observed['path']);files=sorted(str(x.relative_to(p)) for x in p.rglob('*') if x.is_file());new=[x for x in files if x not in observed['files_before']]
 save('M06-'+stage+'-'+target,{**v,'oracle':observed,'new_files':new});assert not new,'wrote replacement path';assert not v['receipt']['receipt_persisted'] and not v['receipt']['summary_persisted']

def m06_create_race(m):
 comp=build('m06-create-race');original=c.ensure_directory_chain;oracle={}
 def swap(*a,**kw):
  fd=original(*a,**kw);p=comp['root']/'temp/s3-production-controller';p.rename(p.with_name('held-output'));p.mkdir();oracle.update(fd_identity=[os.fstat(fd).st_dev,os.fstat(fd).st_ino],path_identity=[p.stat().st_dev,p.stat().st_ino]);return fd
 m.setattr(c,'ensure_directory_chain',swap);v=run(comp,m);save('M06-create-race',{**v,'oracle':oracle,'held_files':[p.name for p in (comp['root']/'temp/held-output').iterdir()]});assert v['receipt']['state']=='UNKNOWN_RETAINED' and not v['receipt']['summary_persisted'],'accepted directory chain observed from different object'

def m07_failure(m,mode):
 comp=build('m07-'+mode,driver_failure=mode if mode!='last-release' else None);factory=None
 if mode=='last-release':
  def factory(ctx):
   drv=data._helpers().SyntheticDriver(ctx.root);orig=drv.release_preload;count=[0]
   def release(*a,**kw):
    count[0]+=1
    if count[0]==16:return {'released':False,'reason':'independent-last-release'}
    return orig(*a,**kw)
   drv.release_preload=release;return drv
 v=run(comp,m,factory=factory);r=v['receipt'];can=json.loads((comp['root']/'temp/s3-quality/qd-receipt.json').read_bytes());save('M07-'+mode,{**v,'counts':can['test_counts']});assert can['test_counts']['FAIL']>0
 for name in ['output_contract','no_overwrite','resource_budget']:assert r['receipts'][name]['status']!='PASS'
 assert r['root_retained'] and r['reservation_retained'] and not r['cleanup_proven']

def m08(m,mode):
 comp=build('m08-'+mode);holder={};before=live()
 if mode in ['direct-double','direct-only','cancel-keyboard','cancel-system']:
  if mode=='direct-double':m.setattr(c.ProductionController,'_bind_receipts',lambda self:(_ for _ in ()).throw(ValueError('primary-independent')))
  exc={'cancel-keyboard':KeyboardInterrupt,'cancel-system':SystemExit}.get(mode,RuntimeError)
  m.setattr(c.ProductionController,'_persist_receipt',lambda *a:(_ for _ in ()).throw(exc('terminal-independent')))
 elif mode=='write-double':
  orig=c.write_exclusive_at
  def fail(fd,name,raw):
   if name.startswith('reservation-'):return orig(fd,name,raw)
   raise RuntimeError('independent-storage')
  m.setattr(c,'write_exclusive_at',fail)
 elif mode=='observer-runtime':m.setattr(c.ProductionController,'_record_post_release_cleanup',lambda *a:(_ for _ in ()).throw(RuntimeError('observer-independent')))
 v=run(comp,m,holder=holder);after=live();delta={k:v for k,v in after.items() if k not in before};save('M08-'+mode,{**v,'fd_new':delta})
 # Cleanup only explicitly owned held controller descriptors after recording evidence.
 obj=holder.get('obj')
 if obj:obj._release_anchors()
 if mode.startswith('cancel-'):assert v['exception']==('KeyboardInterrupt' if mode=='cancel-keyboard' else 'SystemExit') and not delta and not v['thread_alive']
 else:
  assert v['receipt'] is not None and v['receipt']['state']=='UNKNOWN_RETAINED' and not v['receipt']['receipt_persisted'] and not delta
  if mode in ['direct-double','write-double']:assert v['receipt']['unknown_reason'] and v['receipt']['receipt_persistence_error']

def fd(m,mode):
 before=c._fd_snapshot();p=D/'fd-owned.txt';p.write_bytes(b'owned fd');f=os.open(p,os.O_RDONLY)
 try:
  if mode=='real':
   during=c._fd_snapshot();assert f in during['open'];os.close(f);f=None;after=c._fd_snapshot();assert not (set(after['open'])-set(before['open']));save('FD-real',{'before':before,'during':during,'after':after});return
  if mode=='unknown':
   orig=os.fstat
   def unknown(n):
    if n==f:raise OSError(errno.EACCES,'independent unknown fd')
    return orig(n)
   m.setattr(c.os,'fstat',unknown);snapshot=c._fd_snapshot();save('FD-unknown',snapshot);assert f in snapshot['open'] and any(x['fd']==f for x in snapshot['unverified_entries'])
  if mode=='enumeration':
   m.setattr(c.os,'listdir',lambda *a:(_ for _ in ()).throw(OSError(errno.EIO,'independent enumeration')));snapshot=c._fd_snapshot();save('FD-enumeration',snapshot);assert snapshot is None
 finally:
  if f is not None:os.close(f)

CASES=[('positive',positive,())]
CASES += [('M04-reference-'+x,m04_ref,(x,)) for x in ['projection','source_identity','parent_budget','binding','dependency_manifest']]
CASES += [('M04-external-'+x,m04_external,(x,)) for x in ['legal','ancestor']]
CASES += [('M04-io-'+x,m04_io,(x,)) for x in ['exact','over','lying','fifo','directory','unsupported']]
CASES += [('M05-'+x,m05,(x,)) for x in ['disk-window','type-bool','invalid-loader']]
CASES += [('M06-'+s+'-'+x,m06,(s,x)) for s in ['PRECHECK','RECEIPTS_BOUND'] for x in ['root','temp','controller','ancestor']]
CASES += [('M06-create-race',m06_create_race,())]
CASES += [('M07-'+x,m07_failure,(x,)) for x in ['provider-refusal','last-release']]
CASES += [('M08-'+x,m08,(x,)) for x in ['direct-double','direct-only','write-double','cancel-keyboard','cancel-system','observer-runtime']]
CASES += [('FD-'+x,fd,(x,)) for x in ['real','unknown','enumeration']]

def main():
 data.CANDIDATE_SHA=CAND;data._helpers().CANDIDATE_SHA=CAND
 before=live();results=[]
 for name,fn,args in CASES:
  with pytest.MonkeyPatch.context() as m:
   try:fn(m,*args);result={'id':name,'assertion':'PASS'}
   except Exception as e:result={'id':name,'assertion':'FAIL','error':type(e).__name__+':'+str(e)}
   results.append(result);print(json.dumps(result),flush=True)
 save('results',results);save('cleanup',{'before':before,'after':live(),'threads':[x.name for x in threading.enumerate()]})
 return 1 if any(x['assertion']=='FAIL' for x in results) else 0
if __name__=='__main__':raise SystemExit(main())
