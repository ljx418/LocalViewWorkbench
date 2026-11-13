import contextlib,io,json,os,errno,threading,hashlib,copy,traceback
from pathlib import Path
import pytest
from tools import test_v0_s3_production_composition as data
from tools import v0_s3_production_controller as c,v0_s3_quality_worker as w,v0_s3_controller_io as safe
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,v):(D/(n+'.json')).write_text(json.dumps(v,indent=2,default=str))
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
 save('M08-'+mode,{**v,'fd_delta_before_probe_cleanup':delta,'disk':disk,'unknown_fd_unchanged':os.fstat(unknown_fd)==unknown_identity,'owned_pipes_at_spawn':getattr(holder.get('seam'),'independent_pipe_identities',[]),'threads_at_return':[t.name for t in threading.enumerate()]})
 # First record real leakage; cleanup only the explicitly captured owner.
 if obj:obj._release_anchors();obj._release_anchors()
 if holder.get('seam'):holder['seam'].close()
 assert os.fstat(unknown_fd)==unknown_identity
 os.close(unknown_fd)
 assert not delta and not v['thread_alive']
 if mode in ('keyboard','system'):
  assert v['exception']==('KeyboardInterrupt' if mode=='keyboard' else 'SystemExit');return
 r=v['receipt'];assert r is not None and v['exit']!=5 and r['state']=='UNKNOWN_RETAINED','terminal ordinary failure escaped or stayed success'
 assert r['cleanup_proven'] is False
 if mode in ('finish','close-observer'):
  assert r['fd_cleanup']['status']=='UNKNOWN' and r['fd_cleanup']['fd_leaked'] is None
  assert r['fd_cleanup_post_release']['fd_leaked']==[]
  assert holder['seam'].independent_pipe_identities
  assert r['owned_resource_release']['worker_thread_alive'] is False
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
D=Path(__file__).parent
CAND='b95de076f37e64d321629c065e5531eba8a5250a'
def live():
 result={}
 for x in os.listdir('/proc/self/fd'):
  try:
   q=os.fstat(int(x));result[int(x)]=[q.st_dev,q.st_ino,q.st_mode]
  except OSError as e:
   if e.errno != errno.EBADF: raise
 return result

def history(m,mode):
 comp=build('history-'+mode);orig=c.ProductionController._record_disk_actions;seen={}
 def action(obj,r):
  p=obj.summary_path;seen['written_bytes_hash']=sha(p.read_bytes());seen['path']=str(p)
  if mode=='move':p.rename(p.with_name('retained-summary.json'));orig(obj,r)
  else:
   statfn=os.stat
   def bad(path,*a,**k):
    if str(path)==str(p):raise OSError(errno.EIO,'independent visibility failure')
    return statfn(path,*a,**k)
   with m.context() as mm: mm.setattr(os,'stat',bad);orig(obj,r)
 m.setattr(c.ProductionController,'_record_disk_actions',action)
 v=run(comp,m);save('history-'+mode,dict(v,observation=seen));r=v['receipt'];a=r['disk_actions']
 assert v['exit']==0 and r['receipt_persisted'] and a['summary_written']
 assert a['summary_sha256']==seen['written_bytes_hash'] and a['summary_current_visibility']['state']=='UNKNOWN'
 assert a['summary_current_visibility']['error']==('EIO' if mode=='stat' else 'ENOENT')

def close_failure(m):
 comp=build('close-failure');held={};orig=c.OfflineCompositionSeam.close;before=live();fd=os.open(D/'initial-state.json',os.O_RDONLY);identity=os.fstat(fd)
 def bad(self):raise OSError('independent owned close failure')
 m.setattr(c.OfflineCompositionSeam,'close',bad)
 v=run(comp,m,holder=held);after=live();r=v['receipt'];save('close-failure',dict(v,fd_before=before,fd_after_before_probe_cleanup=after,unknown_unchanged=os.fstat(fd)==identity,lifecycle=held['seam'].lifecycle()))
 # Evidence precedes test cleanup. Only the captured seam owner is cleaned.
 try:
  assert r['state']=='UNKNOWN_RETAINED' and v['exit']==4 and r['owned_resource_release']['status']=='FAILED'
  assert r['owned_resource_release']['close_failed'] and not v['thread_alive']
  assert any(k not in before and k!=fd and __import__('stat').S_ISFIFO(x[2]) for k,x in after.items())
  assert os.fstat(fd)==identity
 finally:orig(held['seam']);os.close(fd)
 assert live()==before

def cancellation(m,mode):
 p=D/'cases'/('cancel-'+mode);p.mkdir(parents=True)
 fn=data.test_the_cooperative_cancel_stops_the_worker_and_the_thread_is_joined if mode=='cooperative' else data.test_a_worker_that_does_not_cooperate_is_retained_and_the_run_stays_unknown
 original=data._formal_main
 def formal(*a,**k):
  result=original(*a,**k);code,r,seam,errors=result
  save('cancel-'+mode+'-before-probe-cleanup',{'exit':code,'receipt':r,'owned_pipes_at_spawn':getattr(seam,'independent_pipe_identities',[]),'fds':live(),'threads':[t.name for t in threading.enumerate()],'lifecycle':seam.lifecycle()})
  return result
 m.setattr(data,'_formal_main',formal)
 before=live();fn(p,m);after=live();save('cancel-'+mode,{'fd_before':before,'fd_after':after,'threads':[t.name for t in threading.enumerate()],'selected_direct_compat_function':fn.__name__});assert after==before

CASES=[('positive',positive,())]
CASES += [('M08-'+x,terminal,(x,)) for x in ('single','double','keyboard','system','observer','finish','disk-observer','close-observer')]
CASES += [('history-'+x,history,(x,)) for x in ('stat','move')]
CASES += [('close-failure',close_failure,())]
CASES += [('cancel-'+x,cancellation,(x,)) for x in ('cooperative','noncooperative')]
CASES += [('native',native,())]
def main():
 data.CANDIDATE_SHA=CAND;data._helpers().CANDIDATE_SHA=CAND
 before=live();results=[]
 original=c.OfflineCompositionSeam.spawn
 def spawn(self,cmd):
  worker=original(self,cmd);pipes=[]
  for name in ('stdin','stdout','stderr'):
   fd=getattr(getattr(worker,name,None),'_descriptor',None)
   if fd is not None and fd>=0:
    q=os.fstat(fd);pipes.append({'name':name,'fd':fd,'identity':[q.st_dev,q.st_ino,q.st_mode]})
  self.independent_pipe_identities=pipes
  return worker
 c.OfflineCompositionSeam.spawn=spawn
 for name,fn,args in CASES:
  per_before=live()
  with pytest.MonkeyPatch.context() as m:
   try:fn(m,*args);result={'id':name,'assertion':'PASS'}
   except Exception as e:result={'id':name,'assertion':'FAIL','error':type(e).__name__+':'+str(e),'traceback':traceback.format_exc()}
  result['fd_before']=per_before;result['fd_after']=live();results.append(result);print(json.dumps(result),flush=True)
 save('results',results);after=live();save('cleanup',{'before':before,'after':after,'threads':[x.name for x in threading.enumerate()]})
 return 1 if before!=after or any(x['assertion']=='FAIL' for x in results) else 0
if __name__=='__main__':raise SystemExit(main())
