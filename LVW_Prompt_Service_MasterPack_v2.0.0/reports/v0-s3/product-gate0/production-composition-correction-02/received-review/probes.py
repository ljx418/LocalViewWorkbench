import contextlib,io,json,os,threading,time,hashlib,shutil,stat
from pathlib import Path
import pytest
from tools import test_v0_s3_production_composition as data
from tools import v0_s3_production_controller as c, v0_s3_quality_worker as w, v0_s3_controller_io as safe
D=Path(__file__).parent
CAND='7dc76ffeec685959f5906c612e58f7e1fc081425'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,v):(D/(n+'.json')).write_text(json.dumps(v,indent=2,default=str))
@pytest.fixture
def build(tmp_path,monkeypatch):
 monkeypatch.setattr(data,'CANDIDATE_SHA',CAND);monkeypatch.setattr(data._helpers(),'CANDIDATE_SHA',CAND)
 return lambda **kw:data._build_composition(tmp_path,**kw)
def run(comp,monkeypatch,transition=None,factory=None,clock=None,holder=None,wait=.25):
 seam=c.OfflineCompositionSeam(driver_factory=factory or (lambda ctx:data._helpers().SyntheticDriver(ctx.root,comp['driver_failure'])),context_sha256=comp['worker_context_sha256'],clock=clock,worker_wait_timeout=wait)
 seam.on_transition=transition
 if holder is not None:holder['seam']=seam
 orig=c.ProductionController;held=[]
 class Injected(orig):
  def __init__(self,context):super().__init__(context,seam=seam);held.append(self)
 out=io.StringIO();err=io.StringIO()
 with monkeypatch.context() as m:
  m.setattr(c,'ProductionController',Injected)
  with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):code=c.main(['--context',str(comp['controller_context_path']),'--context-sha256',sha(comp['controller_context_path'].read_bytes())])
 r=json.loads(out.getvalue()) if out.getvalue().strip() else None
 return {'exit':code,'receipt':r,'stderr':err.getvalue(),'spawns':seam.spawns},seam,held[0] if held else None

def test_positive(build,monkeypatch):
 comp=build();v,seam,obj=run(comp,monkeypatch);save('positive',v);r=v['receipt']
 assert v['exit']==0 and r['state']=='SUMMARY_PERSISTED' and r['receipt_persisted']
 assert r['fd_cleanup']['fd_leaked']==[] and not seam._worker._thread.is_alive()
 can=json.loads((comp['root']/'temp/s3-quality/qd-receipt.json').read_bytes());plan=json.loads((comp['root']/'temp/s3-quality/qd-source-plan.json').read_bytes())
 assert can['candidate_sha']==CAND and can['test_counts']['PASS']==16 and len(can['rows'])==16
 assert r['supervision']['message_count']==66 and r['manifest']['reverification']['verified']
 prov=r['summary']['provenance'];assert prov['controller_context']['sha256']==sha(comp['controller_context_path'].read_bytes())
 assert prov['worker_context']['sha256']==comp['worker_context_sha256']
 for cat in ('canonical','source_plan','raw'):
  for x in r['manifest']['originals'][cat]:assert sha((comp['root']/x['reference']).read_bytes())==x['sha256']
 assert r['root_retained'] and r['reservation_retained'] and not r['cleanup_proven']
 assert r['summary']['pass_count']==0
 save('positive-oracle',{'canonical':can,'plan':plan,'rows':comp['rows'],'provenance':prov,'product_scope_not_proven':True})

def test_m01(build):
 comp=build();ctx=c.ControllerContext.load(comp['controller_context_path'],expected_sha256=sha(comp['controller_context_path'].read_bytes()))
 results=[]
 for status,flag,expect in [('PROVEN',True,True),('PROVEN',1,False),('PROVEN','true',False),('FALSE',True,False)]:
  doc=json.loads(json.dumps({'run_id':data.RUN_ID,'candidate_sha':CAND,'status':status,'ok':flag}));reasons=[]
  actual=c._bound_receipt(doc,ctx,label='probe',reasons=reasons,required={'status':'PROVEN','ok':True});results.append([status,flag,actual,reasons]);assert actual is expect
 save('M01',results)

def test_m02_complete_chain_and_defaults(build,monkeypatch):
 comp=build();ctx=c.ControllerContext.load(comp['controller_context_path'],expected_sha256=sha(comp['controller_context_path'].read_bytes()))
 admission=json.loads((comp['root']/'contexts/admission.json').read_bytes())
 for name in c.ADMISSION_REFERENCE_KEYS:
  doc={'run_id':data.RUN_ID,'candidate_sha':CAND,'authorization_sha256':data.AUTHORIZATION_SHA,'status':'PROVEN','descendant_handles_closed':True,'native_services_stopped':True,'gpu_released':True,'installed':True,'rollback_verified':True,'grant_active':True,'expires_at':0,'budget':0,'scope':'not-authorized','files':[]}
  p=comp['root']/'contexts'/('untrusted-'+name+'.json');p.write_text(json.dumps(doc));admission['admission_references'][name]={'path':str(p),'sha256':sha(p.read_bytes())}
 rep=c.verify_native_admission(ctx,admission);assert not rep['accepted'] and rep['primary_reason']=='NATIVE_EXECUTION_BACKEND_NOT_READY'
 native=[]
 if hasattr(w,'build_native_driver'):monkeypatch.setattr(w,'build_native_driver',lambda *a,**kw:native.append('driver'))
 obj=c.ProductionController(ctx);r=obj.run();err=io.BytesIO();exit=w.main(['--context',str(comp['worker_context_path']),'--context-sha256',comp['worker_context_sha256']],error_stream=err)
 save('M02',{'admission':rep,'controller':r,'worker_exit':exit,'worker_stderr':err.getvalue().decode(),'native_calls':native})
 assert r['spawn_attempts']==0 and not native and exit==2 and b'NATIVE_EXECUTION_BACKEND_NOT_READY' in err.getvalue()

@pytest.mark.parametrize('field',['driver_arguments','source_identity_path','projection_path'])
def test_m03_drift(build,monkeypatch,field):
 comp=build()
 def factory(ctx):
  p=comp['worker_context_path'];doc=json.loads(p.read_bytes())
  if field=='driver_arguments':doc[field]={**doc[field],next(iter(doc[field])):'changed'}
  else:doc[field]=str(comp['root']/'not-original')
  p.write_text(json.dumps(doc));return data._helpers().SyntheticDriver(ctx.root)
 v,seam,obj=run(comp,monkeypatch,factory=factory);save('M03-'+field,v)
 assert v['receipt']['state']=='UNKNOWN_RETAINED' and not v['receipt']['summary_persisted'] and not seam._worker._thread.is_alive()

def test_m03_cli_hash(build):
 comp=build();records=[]
 for args in [[],['--context-sha256','f'*64]]:
  err=io.StringIO()
  with contextlib.redirect_stderr(err):code=c.main(['--context',str(comp['controller_context_path']),*args])
  records.append({'exit':code,'stderr':err.getvalue()});assert code!=0
 save('M03-cli',records)

@pytest.mark.parametrize('kind',['exact','oneover','fifo','device','leaflink','ancestorlink','rootlink','changed_read','lying_size'])
def test_m04_io(tmp_path,monkeypatch,kind):
 root=tmp_path/'root';root.mkdir();(root/'sub').mkdir();p=root/'sub/a';p.write_bytes(b'x'*16);limit=16
 if kind=='oneover':p.write_bytes(b'x'*17)
 if kind=='fifo':p.unlink();os.mkfifo(p)
 if kind=='device':p.unlink();p.symlink_to('/dev/null')
 if kind=='leaflink':p.unlink();p.symlink_to(root/'real');(root/'real').write_bytes(b'x')
 if kind=='ancestorlink':(root/'sub').rename(root/'real-sub');(root/'sub').symlink_to(root/'real-sub',target_is_directory=True)
 if kind=='rootlink':root.rename(tmp_path/'real-root');root.symlink_to(tmp_path/'real-root',target_is_directory=True)
 realread=os.read;requests=[];mutated=[]
 def read(fd,n):
  requests.append(n);b=realread(fd,n)
  if kind=='changed_read' and b and not mutated:p.write_bytes(b'y'*16);mutated.append(1)
  return b
 monkeypatch.setattr(safe.os,'read',read)
 if kind=='lying_size':
  p.write_bytes(b'x'*17);realstat=os.fstat
  class Hint:
   def __init__(self,s):self.__dict__.update({n:getattr(s,n) for n in dir(s) if n.startswith('st_')});self.st_size=16
  monkeypatch.setattr(safe.os,'fstat',lambda fd:Hint(realstat(fd)))
 before=set(os.listdir('/proc/self/fd'));actual=None;error=None
 try:actual=safe.read_bounded_in_root(root,'sub/a',limit)
 except safe.ControllerIOError as e:error=e.code
 after=set(os.listdir('/proc/self/fd'));save('M04-'+kind,{'error':error,'bytes':len(actual) if actual else None,'requests':requests,'fd_delta':sorted(after-before)})
 assert before==after and sum(requests)<=limit+1
 if kind=='exact':assert actual==b'x'*16
 else:assert error
 # Never leave a FIFO behind.
 if kind=='fifo':p.unlink()

def test_m04_direct_device():
 with pytest.raises(safe.ControllerIOError,match='FILE_NOT_A_REGULAR_FILE'):safe.read_bounded_regular('/dev/null',16)

@pytest.mark.parametrize('stage',['ORIGINALS_VERIFIED','RECEIPTS_BOUND'])
@pytest.mark.parametrize('target',['raw','canonical','sourceplan','rootlink','rootobject'])
def test_m05_consumer(build,monkeypatch,stage,target):
 comp=build();changed=[]
 def fault(state,obj):
  if state!=stage:return
  root=comp['root']
  if target in ('rootlink','rootobject'):
   moved=root.with_name('retained-original');root.rename(moved)
   if target=='rootlink':root.symlink_to(moved,target_is_directory=True)
   else:root.mkdir()
  else:
   cat={'raw':'raw','canonical':'canonical','sourceplan':'source_plan'}[target];p=root/obj.manifest['originals'][cat][0]['reference'];p.write_bytes(p.read_bytes()+b' ')
  changed.append(target)
 v,seam,obj=run(comp,monkeypatch,transition=fault);save('M05-'+stage+'-'+target,v)
 assert changed and v['receipt']['state']=='UNKNOWN_RETAINED' and not v['receipt']['summary_persisted'] and not seam._worker._thread.is_alive()

@pytest.mark.parametrize('target',['dirlink','dirobject','templink','rootlink','rootobject'])
def test_m06_write_identity(build,monkeypatch,tmp_path,target):
 comp=build();outside=tmp_path/'outside';outside.mkdir();old=comp['root']/'temp/s3-production-controller';moved=[]
 def fault(state,obj):
  if state!='RECEIPTS_BOUND':return
  if target in ('dirlink','dirobject'):
   retain=comp['root']/'temp/old-controller';old.rename(retain);moved.append(retain)
   if target=='dirlink':old.symlink_to(outside,target_is_directory=True)
   else:old.mkdir()
  elif target=='templink':
   retain=comp['root']/'old-temp';(comp['root']/'temp').rename(retain);(comp['root']/'temp').symlink_to(outside,target_is_directory=True);moved.append(retain)
  else:
   retain=comp['root'].with_name('old-root');comp['root'].rename(retain);moved.append(retain)
   if target=='rootlink':comp['root'].symlink_to(outside,target_is_directory=True)
   else:comp['root'].mkdir()
 v,seam,obj=run(comp,monkeypatch,transition=fault);external=[str(x.relative_to(outside)) for x in outside.rglob('*')];newfiles=[str(x.relative_to(comp['root'])) for x in comp['root'].rglob('receipt-*.json')] if target=='rootobject' else []
 save('M06-'+target,{**v,'external':external,'new_root_receipts':newfiles,'original_held':moved})
 assert not external
 # Root object replacement is a reproduction of a remaining defect: receipt was written into a new unbound root.
 if target=='rootobject':assert newfiles and v['receipt']['receipt_persisted']
 else:assert not v['receipt']['summary_persisted']

@pytest.mark.parametrize('failure',['release-unproven','residue','provider-refusal','last-release'])
def test_m07_rows(build,monkeypatch,failure):
 comp=build(driver_failure=failure if failure!='last-release' else None)
 factory=None
 if failure=='last-release':
  def factory(ctx):
   drv=data._helpers().SyntheticDriver(ctx.root);original=drv.release_preload;n=[0]
   def release(*a,**kw):
    n[0]+=1
    if n[0]==16:return {'released':False,'reason':'independent-last-release'}
    return original(*a,**kw)
   drv.release_preload=release;return drv
 v,seam,obj=run(comp,monkeypatch,factory=factory);r=v['receipt'];can=json.loads((comp['root']/'temp/s3-quality/qd-receipt.json').read_bytes());save('M07-'+failure,{**v,'counts':can['test_counts']})
 assert can['test_counts']['FAIL']>0
 if failure=='last-release':assert can['test_counts']['PASS']==15 and can['test_counts']['FAIL']==1
 for k in ('output_contract','resource_budget','no_overwrite'):assert r['receipts'][k]['status']!='PASS'
 assert r['root_retained'] and r['reservation_retained'] and not r['cleanup_proven']

@pytest.mark.parametrize('where',['bind','verify','fsync'])
def test_m08_exception(build,monkeypatch,where):
 comp=build();before=set(os.listdir('/proc/self/fd'));origfs=os.fsync
 if where=='bind':monkeypatch.setattr(c.ProductionController,'_bind_receipts',lambda self:(_ for _ in ()).throw(ValueError('independent-ordinary')))
 if where=='verify':monkeypatch.setattr(c.ProductionController,'_verify_originals',lambda self:(_ for _ in ()).throw(OSError('independent-io')))
 def fault(state,obj):
  if where=='fsync' and state=='RECEIPTS_BOUND':monkeypatch.setattr(safe.os,'fsync',lambda fd:(_ for _ in ()).throw(OSError('independent-fsync')))
 v,seam,obj=run(comp,monkeypatch,transition=fault);monkeypatch.setattr(safe.os,'fsync',origfs);save('M08-'+where,{**v,'fd_delta':sorted(set(os.listdir('/proc/self/fd'))-before)})
 r=v['receipt'];assert r['state']=='UNKNOWN_RETAINED' and r['reservation_retained'] and not seam._worker._thread.is_alive() and set(os.listdir('/proc/self/fd'))==before
 if where=='fsync':assert not r['receipt_persisted'] and r['receipt_persistence_error']
 else:assert r['receipt_persisted']

@pytest.mark.parametrize('exc',[KeyboardInterrupt,SystemExit])
def test_m08_baseexception(build,monkeypatch,exc):
 comp=build();monkeypatch.setattr(c.ProductionController,'_bind_receipts',lambda self:(_ for _ in ()).throw(exc('controlled-cancel')))
 before=set(os.listdir('/proc/self/fd'))
 with pytest.raises(exc):run(comp,monkeypatch)
 assert set(os.listdir('/proc/self/fd'))==before and not any(t.name=='s3-composition-worker' and t.is_alive() for t in threading.enumerate())

@pytest.mark.parametrize('existing',['summary','reservation'])
def test_m09_existing(build,monkeypatch,existing):
 comp=build();d=comp['root']/'temp/s3-production-controller';d.mkdir();p=d/(existing+'-'+data.RUN_ID+'.json');p.write_bytes(b'prior')
 v,seam,obj=run(comp,monkeypatch);save('M09-'+existing,v);assert v['spawns']==0 and p.read_bytes()==b'prior'

def test_m09_concurrent(build,monkeypatch):
 comp=build();ctx=c.ControllerContext.load(comp['controller_context_path'],expected_sha256=sha(comp['controller_context_path'].read_bytes()));barrier=threading.Barrier(2);calls=[];results=[]
 class Contender(c.ProductionController):
  def _precheck(self):super()._precheck();barrier.wait(5)
  def _supervise(self):calls.append(threading.current_thread().name);return super()._supervise()
 def start():
  seam=c.OfflineCompositionSeam(driver_factory=lambda ctx:data._helpers().SyntheticDriver(ctx.root),context_sha256=comp['worker_context_sha256']);results.append(Contender(ctx,seam=seam).run())
 ts=[threading.Thread(target=start,name='contender-'+str(i)) for i in range(2)]
 for t in ts:t.start()
 for t in ts:t.join(15)
 save('M09-concurrent',{'send_owners':calls,'results':results,'threads_alive':[t.is_alive() for t in ts]})
 assert len(calls)==1 and not any(t.is_alive() for t in ts)

def test_m01_cancel_cooperative(build,monkeypatch):
 comp=build();holder={};calls=[]
 def factory(ctx):
  drv=data._helpers().SyntheticDriver(ctx.root);orig=drv.submit
  def submit(graph):calls.append(1);value=orig(graph);holder['seam'].cancel();return value
  drv.submit=submit;return drv
 v,seam,obj=run(comp,monkeypatch,factory=factory,holder=holder);save('m01-cooperative',{**v,'submit_count':len(calls),'actual_alive':seam._worker._thread.is_alive()})
 assert len(calls)==1 and not seam._worker._thread.is_alive() and v['receipt']['fd_cleanup']['worker_thread_finished']

def test_m01_cancel_noncooperative(build,monkeypatch):
 comp=build();entered=threading.Event();release=threading.Event();holder={};late=[];baseline=time.monotonic()
 class Blocking(data._helpers().SyntheticDriver):
  def submit(self,graph):
   entered.set();release.wait(15);late.append('callback-resumed');return super().submit(graph)
 try:
  v,seam,obj=run(comp,monkeypatch,factory=lambda ctx:Blocking(ctx.root),holder=holder,clock=lambda:baseline+22000 if entered.is_set() else time.monotonic(),wait=.05)
  lifecycle=v['receipt']['fd_cleanup']['worker_lifecycle'];save('m01-noncooperative-before-release',{**v,'late':list(late),'actual_alive':seam._worker._thread.is_alive()})
  assert v['receipt']['state']=='UNKNOWN_RETAINED' and lifecycle['worker_thread_retained'] and lifecycle['late_write_after_return_is_possible']
 finally:
  release.set();seam=holder.get('seam')
  if seam:seam.release_and_join(5);seam.close()
 save('m01-test-control-cleanup',{'late':late,'actual_alive':seam._worker._thread.is_alive(),'product_cleanup_proof':False})
 assert not seam._worker._thread.is_alive()

@pytest.mark.parametrize('binary',[True,False])
def test_m02_error_stream(build,monkeypatch,binary):
 comp=build();err=io.BytesIO() if binary else io.StringIO();monkeypatch.setattr(w.WorkerContext,'load',lambda *a,**kw:(_ for _ in ()).throw(w.WorkerError('INDEPENDENT_ACCURATE_CODE')))
 code=w.main(['--context',str(comp['worker_context_path']),'--context-sha256',comp['worker_context_sha256']],driver=object(),stream=io.BytesIO(),error_stream=err);value=err.getvalue();value=value.decode() if binary else value;save('m02-'+str(binary),{'exit':code,'stderr':value});assert code==2 and 'INDEPENDENT_ACCURATE_CODE' in value and 'TypeError' not in value
