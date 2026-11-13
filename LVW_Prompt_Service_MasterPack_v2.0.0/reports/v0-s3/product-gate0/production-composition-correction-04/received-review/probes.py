import contextlib,io,json,os,errno,threading,hashlib,copy,traceback
from pathlib import Path
import pytest
from tools import test_v0_s3_production_composition as data
from tools import v0_s3_production_controller as c,v0_s3_quality_worker as w,v0_s3_controller_io as safe
D=Path(__file__).parent
CAND='6885f7a62b223f5e2c7904a9f929e760396fd88b'
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
 return {'exit':code,'receipt':r,'stdout':text,'stderr':err.getvalue(),'exception':exception,'thread_alive':bool(getattr(seam, '_worker', None) and seam._worker._thread.is_alive())}

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
 save('M06-'+stage+'-'+target,{**v,'oracle':observed,'new_files':new});assert not new,'wrote replacement path';assert not v['receipt']['receipt_persisted'] and not v['receipt']['summary_persisted']; assert v['receipt'].get('receipt_path') is None and v['receipt'].get('summary_path') is None

def m06_create_race(m):
 comp=build('m06-create-race');original=c.ensure_directory_chain;oracle={}
 def swap(*a,**kw):
  fd=original(*a,**kw);p=comp['root']/'temp/s3-production-controller';p.rename(p.with_name('held-output'));p.mkdir();oracle.update(fd_identity=[os.fstat(fd).st_dev,os.fstat(fd).st_ino],path_identity=[p.stat().st_dev,p.stat().st_ino]);return fd
 m.setattr(c,'ensure_directory_chain',swap);v=run(comp,m);save('M06-create-race',{**v,'oracle':oracle,'held_files':[p.name for p in (comp['root']/'temp/held-output').iterdir()]});assert v['receipt']['state'] in ('REFUSED','UNKNOWN_RETAINED') and not v['receipt']['summary_persisted'] and v['receipt'].get('receipt_path') is None and v['receipt'].get('summary_path') is None,'accepted directory chain observed from different object'

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

def external_window(m,mode):
 comp,ctx=worker('external-window-'+mode);base=D/'cases'/('external-window-'+mode);parent=base/'declared-parent';anchor=parent/'deps';leaf=anchor/'nested'/'named.txt';leaf.parent.mkdir(parents=True);leaf.write_bytes(b'fixed external named bytes')
 doc=copy.deepcopy(ctx.document);doc['reference_anchors'][1]['path']=str(anchor)
 manifest={'schema':data.DEPENDENCY_MANIFEST_SCHEMA,'scope':data.DEPENDENCY_MANIFEST_SCOPE,'path':str(anchor),'files':[{'path':str(leaf),'sha256':sha(leaf.read_bytes())}]}
 p=Path(doc['dependency_manifest_path']);p.write_text(json.dumps(manifest));doc['dependency_manifest_sha256']=sha(p.read_bytes());ctx=w.WorkerContext(doc)
 assert ctx.dependency_manifest()==manifest
 original=w.read_bounded_at;fired=[];before=live()
 def read(fd,name,limit):
  raw=original(fd,name,limit)
  if name=='named.txt':
   fired.append(name)
   if mode in ('runtime','keyboard'):raise (RuntimeError if mode=='runtime' else KeyboardInterrupt)('independent read failure')
   victim=parent if mode=='parent' else anchor/'nested';moved=victim.with_name(victim.name+'-held');victim.rename(moved);victim.symlink_to(moved,target_is_directory=True)
  return raw
 m.setattr(w,'read_bounded_at',read);error=None
 try:ctx.dependency_manifest()
 except BaseException as e:error=type(e).__name__+':'+str(e)
 after=live();save('M04-window-'+mode,{'error':error,'read_fired':fired,'before':before,'after':after});assert fired and error and before==after
 if mode=='runtime':assert error.startswith('RuntimeError:')
 if mode=='keyboard':assert error.startswith('KeyboardInterrupt:')

def bounded(m,mode):
 base=D/'cases'/('bounded-'+mode);base.mkdir(parents=True);p=base/'file';p.write_bytes(b'x'*(17 if mode=='over' else 16));reads=[];rd=os.read
 if mode=='fifo':p.unlink();os.mkfifo(p)
 def read(fd,n):
  b=rd(fd,n);reads.append({'request':n,'actual':len(b)});return b
 m.setattr(safe.os,'read',read);raw=None;error=None
 try:raw=safe.read_bounded_in_root(base,'file',16)
 except safe.ControllerIOError as e:error=e.code
 save('M04-bounded-'+mode,{'reads':reads,'actual_total':sum(x['actual'] for x in reads),'error':error,'length':len(raw) if raw is not None else None})
 assert sum(x['actual'] for x in reads)<=17
 if mode=='exact':assert raw==b'x'*16
 else:assert error

def terminal(m,mode):
 comp=build('terminal-'+mode);holder={};before=live();unknown_fd=os.open(D/'initial-state.json',os.O_RDONLY);unknown_identity=os.fstat(unknown_fd)
 def throw(exc):
  def action(*args,**kwargs):raise exc('independent terminal '+mode)
  return action
 if mode=='double':m.setattr(c.ProductionController,'_bind_receipts',throw(ValueError))
 if mode in ('single','double','keyboard','system'):
  m.setattr(c.ProductionController,'_persist_receipt',throw({'keyboard':KeyboardInterrupt,'system':SystemExit}.get(mode,RuntimeError)))
 elif mode=='observer':m.setattr(c.ProductionController,'_record_post_release_cleanup',throw(RuntimeError))
 elif mode=='finish':m.setattr(c.ProductionController,'_finish',throw(RuntimeError))
 elif mode=='disk-observer':m.setattr(c.ProductionController,'_record_disk_actions',throw(RuntimeError))
 elif mode=='close-observer':
  original=c._fd_snapshot;count=[0]
  def snapshot():
   count[0]+=1
   if count[0]==2:raise RuntimeError('independent cleanup snapshot')
   return original()
  m.setattr(c,'_fd_snapshot',snapshot)
 v=run(comp,m,holder=holder);after=live();delta={k:x for k,x in after.items() if k not in before and k!=unknown_fd};obj=holder.get('obj');files=list((comp['root']/'temp/s3-production-controller').glob('*.json'));disk={x.name:json.loads(x.read_bytes()) for x in files}
 save('M08-'+mode,{**v,'fd_delta_before_probe_cleanup':delta,'disk':disk,'unknown_fd_unchanged':os.fstat(unknown_fd)==unknown_identity})
 # First record real leakage; cleanup only the explicitly captured owner.
 if obj:obj._release_anchors();obj._release_anchors()
 assert os.fstat(unknown_fd)==unknown_identity
 os.close(unknown_fd)
 assert not delta and not v['thread_alive']
 if mode in ('keyboard','system'):
  assert v['exception']==('KeyboardInterrupt' if mode=='keyboard' else 'SystemExit');return
 r=v['receipt'];assert r is not None and v['exit']!=5 and r['state']=='UNKNOWN_RETAINED','terminal ordinary failure escaped or stayed success'
 assert r['cleanup_proven'] is False
 if mode in ('single','double'):
  assert not r['receipt_persisted'] and r['receipt_persistence_error'] and r['disk_actions']['receipt_written'] is False
  assert r['secondary_failures']
  if mode=='single':assert r['disk_actions']['summary_written'] and any(n.startswith('summary-') for n in disk)
  else:assert 'ValueError' in r['unknown_reason'] and 'RuntimeError' in r['secondary_failure']
 if mode=='observer':
  assert r['fd_cleanup_post_release']['fd_leaked'] is None
  persisted=[x for n,x in disk.items() if n.startswith('receipt-')][0]
  assert persisted['state']=='SUMMARY_PERSISTED' and 'fd_cleanup_post_release' not in persisted and r['persisted_receipt_state']==persisted['state']

def native(m):
 comp=build('native');out=io.StringIO();err=io.StringIO()
 with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):code=c.main(['--context',str(comp['controller_context_path']),'--context-sha256',sha(comp['controller_context_path'].read_bytes())])
 r=json.loads(out.getvalue());p=comp['root']/'temp/s3-production-controller';files=[str(x) for x in p.rglob('*') if x.is_file()];save('native',{'exit':code,'receipt':r,'empty_output_exists':p.is_dir(),'files':files});assert p.is_dir() and not files and r['spawn_attempts']==0 and not r['receipt_persisted'] and not r['summary_persisted']

def reservation(m):
 comp=build('reservation');a=run(comp,m);originals={p.name:sha(p.read_bytes()) for p in (comp['root']/'temp/s3-production-controller').glob('*.json')};b=run(comp,m);now={p.name:sha(p.read_bytes()) for p in (comp['root']/'temp/s3-production-controller').glob('*.json')};save('reservation',{'first':a,'second':b,'before_hashes':originals,'after_hashes':now});assert a['receipt']['receipt_persisted'] and b['receipt']['spawn_attempts']==0 and not b['receipt']['receipt_persisted'] and originals==now

CASES=[('positive',positive,()),('M04-external-legal',m04_external,('legal',)),('M04-external-parent-link',m04_external,('ancestor',))]
CASES += [('M04-window-'+x,external_window,(x,)) for x in ('parent','nested','runtime','keyboard')]
CASES += [('M04-bounded-'+x,bounded,(x,)) for x in ('exact','over','fifo')]
CASES += [('M06-PRECHECK-'+x,m06,('PRECHECK',x)) for x in ('root','temp','controller','ancestor')]
CASES += [('M06-create-race',m06_create_race,())]
CASES += [('M08-'+x,terminal,(x,)) for x in ('single','double','keyboard','system','observer','finish','disk-observer','close-observer')]
CASES += [('M05-seal-window',m05,('disk-window',)),('FD-real',fd,('real',)),('native',native,()),('reservation',reservation,())]
def main():
 data.CANDIDATE_SHA=CAND;data._helpers().CANDIDATE_SHA=CAND
 before=live();results=[]
 for name,fn,args in CASES:
  with pytest.MonkeyPatch.context() as m:
   try:fn(m,*args);result={'id':name,'assertion':'PASS'}
   except Exception as e:result={'id':name,'assertion':'FAIL','error':type(e).__name__+':'+str(e),'traceback':traceback.format_exc()}
   results.append(result);print(json.dumps(result),flush=True)
 save('results',results);save('cleanup',{'before':before,'after':live(),'threads':[x.name for x in threading.enumerate()]})
 return 1 if any(x['assertion']=='FAIL' for x in results) else 0
if __name__=='__main__':raise SystemExit(main())
