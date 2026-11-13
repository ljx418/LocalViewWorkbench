"""Independent obligation oracles; no author tests imported, no OS business process."""
import json,time,threading,queue,traceback,copy,types,ctypes,argparse,ast
from pathlib import Path
from tools import v0_s3_native_custody as C
from tools import v0_s3_native_broker as B
ROOT=Path(__file__).parent
RESULTS=[]
def doc():
 return dict(schema=C.PLAN_SCHEMA,run_id='independent-n1-02',candidate_sha='a'*40,authorization_sha256='b'*64,lease_expires_at=100000.,max_runtime_seconds=21600,roles=[dict(role='COMFY',tools=[dict(path='C:/x/python.exe',sha256='c'*64),dict(path='C:/x/main.py',sha256='d'*64)],data=dict(user_directory='user'),log='temp/native/comfy.log'),dict(role='OLLAMA',tools=[dict(path='C:/x/ollama.exe',sha256='e'*64)],data={},log='temp/native/ollama.log')])
def plan():return C.validate_launch_plan(doc(),now=1000.)
def check(name,fn):
 try:
  ok,detail=fn(); row=dict(name=name,oracle_pass=bool(ok),detail=detail)
 except BaseException as e:row=dict(name=name,oracle_pass=False,harness_exception=repr(e),traceback=traceback.format_exc())
 RESULTS.append(row); print(json.dumps(row,default=repr),flush=True)
def capture(fn):
 try:return dict(returned=fn())
 except BaseException as e:return dict(exception=type(e).__name__,code=getattr(e,'code',None),detail=getattr(e,'detail',None),traceback=traceback.format_exc())
class F:
 """Synthetic HANDLE allocator: integers never reach kernel; owner records every call."""
 def __init__(self,fail=None):self.live={};self.calls=[];self.n=100;self.fail=fail;self.gate=threading.Event()
 def alloc(self,k):self.n+=1;self.live[self.n]=k;return self.n
 def hit(self,k,*a):
  self.calls.append([k,*a])
  if k==self.fail:raise RuntimeError('ordinary_'+k)
  if k=='assign' and self.fail in ('assign_broker','assign_cancel'):raise (KeyboardInterrupt('cancel') if self.fail=='assign_cancel' else B.BrokerError('BROKER_ASSIGN_FAILED'))
 def create_job(self):self.hit('job');return self.alloc('job')
 def set_job_kill_on_close(self,h):
  self.hit('limits',h)
  if self.fail=='limits_close':raise B.BrokerError('BROKER_JOB_LIMIT_FAILED')
 def create_pipe(self,n):self.hit('pipe',n);return self.alloc('read'),self.alloc('write')
 def create_process_suspended(self,**kw):self.hit('create');return B.CreatedProcess(self.alloc('process'),self.alloc('thread'),4000+self.n,123)
 def assign_process_to_job(self,*a):self.hit('assign',*a)
 def resume_thread(self,*a):self.hit('resume',*a)
 def terminate_job(self,*a):self.hit('terminate_job',*a)
 def terminate_process(self,*a):self.hit('terminate',*a)
 def wait_process(self,*a):self.hit('wait',*a);return True
 def exit_code(self,*a):return 1
 def job_process_ids(self,*a):self.hit('query',*a);return []
 def close_handle(self,h):
  h=getattr(h,'value',h);self.hit('close',h)
  if self.fail=='limits_close':raise B.BrokerError('BROKER_HANDLE_CLOSE_FAILED')
  if h not in self.live:raise AssertionError('foreign_or_double_close')
  del self.live[h]
 def read_stream(self,*a):
  if self.fail=='reader_wait':self.gate.wait(40)
  if self.fail=='reader_error':raise B.BrokerError('BROKER_STREAM_READ_FAILED')
  return b''
 def salvage(self):
  # Explicit synthetic allocator owner only, AFTER product-return snapshot.
  self.gate.set();self.fail=None
  for h in list(self.live):self.close_handle(h)
def core(f,name):return B.BrokerCore(win32=f,plan=plan(),run_root=ROOT/'synthetic'/name)
def snapshot(k,f):return dict(state=k.state,live=dict(f.live),pending=k._pending.pending(),calls=list(f.calls),evidence=k.evidence())
def core_case(mode):
 f=F(mode);k=core(f,mode or 'success');a=capture(k.arm)
 if not a.get('exception'):a=capture(k.launch)
 if mode=='diagnostic':k._collect_stream_counts=lambda:(_ for _ in ()).throw(RuntimeError('diagnosis'));a=capture(k.stop)
 elif mode not in ('assign_broker','assign_cancel','limits_close'):
  if mode=='stop_ordinary':f.fail='terminate_job'
  a=capture(k.stop)
 s=snapshot(k,f);s['outcome']=a
 expected_cancel=mode!='assign_cancel' or a.get('exception')=='KeyboardInterrupt'
 ok=not f.live and expected_cancel and (mode!='reader_error' or k.state=='UNKNOWN_RETAINED')
 f.salvage()
 for r in k.readers:r.join(1)
 return ok,s
def directory():
 bad=['safe/../../outside','safe\\..\\outside','C:ads','..','a..b','NUL','con.txt','COM1','LPT9','A'*65,'x\n',' user','user.','/abs','a/b','COM¹']
 accepted=[]
 for v in bad:
  d=doc();d['roles'][0]['data']['user_directory']=v
  if 'exception' not in capture(lambda:C.validate_launch_plan(d,now=1000)):accepted.append(v)
 good=[]
 for v in ['user','a'*64,'User_1-2']:
  d=doc();d['roles'][0]['data']['user_directory']=v;good.append('exception' not in capture(lambda:C.validate_launch_plan(d,now=1000)))
 return not accepted and all(good),dict(accepted_bad=accepted,good=good)
def sealing():
 d=doc();p=C.validate_launch_plan(d,now=1000);before=p.sealed_sha256();s=p.sealed;s['roles'][0]['tools'][0]['path']='C:/foreign.exe';d['roles'][0]['data']['user_directory']='foreign'
 cmd=B.role_command(p.roles[0],ROOT,[]);mut=capture(lambda:p.roles[0]['tools'][0].__setitem__('path','C:/foreign.exe'))
 return cmd['executable']=='C:/x/python.exe' and p.sealed_sha256()==before and bool(mut.get('exception')),dict(command=cmd,mutation=mut,seal=p.sealed)
class Prim:
 def __init__(self,k,fn):self.k=k;self.fn=fn;self.argtypes=None;self.restype='UNDECLARED'
 def __call__(self,*a):return self.fn(self.k,*a)
class Kernel:
 def __init__(self,fn):self.fn=fn;self.p={}
 def __getattr__(self,k):
  if k not in self.p:self.p[k]=Prim(k,self.fn)
  return self.p[k]
def table(fn):
 t=B._windows_api_types();k=Kernel(fn);B._declare_windows_primitives(k,t);return B._WindowsApiTable(kernel32=k,types=t)
def abi():
 t=table(lambda *a:1);T=t.types;keys=['CreateJobObjectW','CreateProcessW','CreatePipe','CreateFileW','GetProcessTimes','CloseHandle','InitializeProcThreadAttributeList','UpdateProcThreadAttribute','CancelSynchronousIo','DuplicateHandle'];sizes={k:ctypes.sizeof(T[k]) for k in ['DWORD','BOOL','HANDLE','STARTUPINFOW','STARTUPINFOEXW']};decl={k:[len(getattr(t.kernel32,k).argtypes),repr(getattr(t.kernel32,k).restype)] for k in keys}
 return sizes==dict(DWORD=4,BOOL=4,HANDLE=8,STARTUPINFOW=104,STARTUPINFOEXW=112) and T['JOBOBJECT_BASIC_PROCESS_ID_LIST'].ProcessIdList.offset==8 and all(getattr(t.kernel32,k).argtypes is not None for k in keys),dict(sizes=sizes,declarations=decl)
def job_case(assigned,listed,length):
 def fn(k,*a):
  if k=='QueryInformationJobObject':
   payload=assigned.to_bytes(4,'little')+listed.to_bytes(4,'little')+b''.join(x.to_bytes(8,'little') for x in range(111,111+listed));ctypes.memmove(a[2],payload,min(len(payload),a[3]));a[4]._obj.value=length;return 1
  return 1
 api=B.WindowsApi(table(fn));out=capture(lambda:api.job_process_ids(123));valid=(assigned==listed and 0<=listed<=17 and 8+listed*8<=length<=8+18*8)
 return bool(out.get('exception'))!=valid,dict(assigned=assigned,listed=listed,returned_length=length,outcome=out)
def create_case(mode):
 calls=[];live={501:'null'};observed={}
 def fn(k,*a):
  calls.append(k)
  if k=='CreateFileW':observed['nul_inherit']=a[3]._obj.bInheritHandle;return 501
  if k=='InitializeProcThreadAttributeList':a[3]._obj.value=64;return 1
  if k=='UpdateProcThreadAttribute':observed['whitelist']=list(a[3]);return 1
  if k=='CreateProcessW':
   observed.update(cb=a[8]._obj.cb,flags=a[5],inherit=a[4]);info=a[9]._obj;info.hProcess=502;info.hThread=503;info.dwProcessId=4001;live.update({502:'process',503:'thread'});return 1
  if k=='DeleteProcThreadAttributeList' and mode=='attribute_exception':raise RuntimeError('delete_after_creation')
  if k=='GetProcessTimes':return 0 if mode.startswith('birth') else 1
  if k=='CloseHandle':
   h=getattr(a[0],'value',a[0]);
   if mode=='birth_close_failure' and h in (502,503):return 0
   live.pop(h,None);return 1
  if k=='WaitForSingleObject':return 258 if mode=='birth_close_failure' else 0
  return 1
 api=B.WindowsApi(table(fn));out=capture(lambda:api.create_process_suspended(executable='C:/x/python.exe',arguments=['main.py'],working_directory='C:/x',stdout_handle=601,stderr_handle=602,environment=None));s=dict(mode=mode,calls=calls,live=dict(live),observed=observed,outcome=out)
 if mode=='normal':ok=observed==dict(nul_inherit=1,whitelist=[601,602,501],cb=112,flags=0x80404,inherit=True) and set(live)=={502,503}
 else:ok=not live
 # Only the synthetic kernel allocator owns these local identifiers.
 live.clear();return ok,s
class Peer:
 channel_deadline_aware=True
 def __init__(self,p,n,kinds=('READY','STATUS'),facts=None):self.p=p;self.n=n;self.q=queue.Queue();self.seq=0;self.closed=0;self.facts=facts;self.pid=123;self.reader_finished=True;self.sent=[];[self.emit(k) for k in kinds]
 def emit(self,k):
  self.seq+=1;state={'READY':'ARMED','STATUS':'RUNNING','REFUSED':'UNKNOWN_RETAINED','STOPPED':'RELEASED'}[k];self.q.put(json.dumps(dict(schema=C.CHANNEL_SCHEMA,kind=k,run_id=self.p.run_id,candidate_sha=self.p.candidate_sha,authorization_sha256=self.p.authorization_sha256,nonce=self.n,sequence=self.seq,state=state,detail={})).encode()+b'\n')
 def bind_channel_deadline(self,d):self.deadline=d
 def write(self,raw,d):
  self.sent.append([json.loads(raw),d])
  if json.loads(raw)['command']=='STOP':self.emit('STOPPED')
 def read(self,t):
  try:return self.q.get(timeout=min(t,.02))
  except queue.Empty:return None
 def close(self):self.closed+=1;return self.facts
class Clock:
 def __init__(self):self.v=1000.
 def __call__(self):return self.v
def session(facts=None,kinds=('READY','STATUS')):
 cl=Clock();hold={}
 def launch(p,r,n):hold['peer']=Peer(p,n,kinds,facts);return hold['peer']
 s=C.NativeCustodySession(plan=doc(),run_root=ROOT/'synthetic/session',parent_child_remaining_seconds=21600,launcher=launch,clock=cl,wall=cl);return s,hold,cl
def parent_refused():
 s,h,cl=session(kinds=('REFUSED',),facts=dict(channel_closed=True,process_exited=True,process_handle_released=True));o=capture(s.start);return h['peer'].closed==1 and s.broker is None,dict(outcome=o,closed=h['peer'].closed,evidence=s.evidence())
def parent_bad_close(facts):
 s,h,cl=session(facts=facts);s.start();o=capture(s.stop);e=s.evidence();return s.state=='UNKNOWN_RETAINED' and s.broker is h['peer'],dict(outcome=o,evidence=e,peer_closed=h['peer'].closed)
def parent_thread_start():
 s,h,cl=session();s._start_heartbeat=lambda:(_ for _ in ()).throw(RuntimeError('thread_start_failed'));o=capture(s.start);e=s.evidence();ret=dict(outcome=o,evidence=e,peer_closed=h['peer'].closed,threads=[t.name for t in threading.enumerate()]);ok=h['peer'].closed==1
 # Explicit session owner performs a later recovery after the snapshot.
 capture(s._close_broker);return ok,ret
def heartbeat():
 s,h,cl=session(facts=dict(channel_closed=True,process_exited=True,process_handle_released=True));s.start();deadline=s._deadline_mono;s._last_heartbeat=1000.;cl.v=1060.;s._heartbeat_step();count=len(h['peer'].sent);cl.v=deadline+1;s._heartbeat_step();after=len(h['peer'].sent);s._frames_sent=0;s._frames_received=1024
 reply=json.dumps(dict(schema=C.CHANNEL_SCHEMA,kind='STATUS',run_id=s.plan.run_id,candidate_sha=s.plan.candidate_sha,authorization_sha256=s.plan.authorization_sha256,nonce=s._nonce,sequence=100,state='RUNNING',detail={})).encode();budget=capture(lambda:s._decode_reply(reply));e=s.evidence();capture(s.stop)
 return after==count and bool(budget.get('exception')),dict(deadline=deadline,deadline_after=s._deadline_mono,sends_before=count,sends_after=after,budget=budget,evidence=e)
def heartbeat_failure():
 s,h,cl=session(facts=dict(channel_closed=True,process_exited=True,process_handle_released=True));s.start();s._last_heartbeat=1000.;cl.v=1060.;h['peer'].write=lambda *a:(_ for _ in ()).throw(B.BrokerError('BROKER_PIPE_WRITE_FAILED'));s._heartbeat_step();e=s.evidence();ok=s.state=='UNKNOWN_RETAINED' and h['peer'].closed==1;capture(s.stop);return ok,dict(evidence=e,closed_at_failure=0)
def close_budget():
 cl=Clock();calls=[]
 class Chan:
  reader_finished=True
  def close(self):calls.append(['channel',cl.v]);cl.v+=4;return dict(write_end_closed=True,read_end_closed=True)
 class Proc:
  pid=1;returncode=None
  stdin=types.SimpleNamespace(close=lambda:None);stdout=types.SimpleNamespace(close=lambda:None)
  def wait(self,timeout):calls.append(['wait',cl.v,timeout]);cl.v+=timeout;raise TimeoutError()
  def terminate(self):calls.append(['terminate',cl.v])
 old=B.time.monotonic;B.time.monotonic=cl
 try:
  p=B.BrokerProcess(Proc(),'x','a'*64,Chan());p.write_deadline=1005.;facts=p.close();return cl.v<=1005.,dict(calls=calls,finish=cl.v,deadline=1005.,facts=facts)
 finally:B.time.monotonic=old
class Endpoint:
 def __init__(self,blocks):self.blocks=list(blocks);self.max_buffer=0;self.closed=False
 def read(self,*a):return self.blocks.pop(0) if self.blocks else b''
 def write(self,*a):return 1
 def close(self):self.closed=True;return dict(closed=True)
def framing():
 ep=Endpoint([b'x'*(32768*2),b'y'*32768]);ch=B.StreamChannel(None,None,read_endpoint=ep,write_endpoint=Endpoint([]));ch._thread.join(1);out=capture(lambda:ch.read(0));s=dict(buffer_length=len(ch._buffer),overflow=ch.overflow,error=ch._error,outcome=out);facts=ch.close();s['facts']=facts;return ch.overflow and len(ch._buffer)<=C.MAX_FRAME_BYTES,s
def windows_worker():
 allocated=[];closed=[]
 class Api:
  def duplicate_current_thread_handle(self):allocated.append(700);return 700
  def cancel_synchronous_io(self,h):return 'NOT_FOUND'
  def close_handle(self,h):closed.append(h)
 w=B._WindowsPipeWorker(Api(),701,kind='read',action=lambda x:b'',name='independent-win-worker');w.start();w.submit(None);w.done.wait(1);w.stop();w.join(1)
 ok=closed==allocated;detail=dict(allocated_thread_handles=list(allocated),closed=list(closed),alive=w.is_alive());w.api.close_handle(700);return ok,detail
def sampler():
 role=dict(role='SAMPLER',tools=[dict(path='C:/x/python.exe',sha256='a'*64),dict(path='C:/x/sampler.py',sha256='b'*64)],data=dict(nvidia_exe='C:/x/nvidia.exe',nvidia_sha256='c'*64,max_seconds=60),log='temp/native/sampler.log')
 args=B.role_command(role,ROOT,[4001,4002])['arguments'];parser=argparse.ArgumentParser(add_help=False);parser.add_argument('--private-pids',type=int,nargs='+');parsed,rest=parser.parse_known_args(args);return parsed.private_pids==[4001,4002],dict(arguments=args,pids=parsed.private_pids)
def nonce():
 s=C.NativeCustodySession(plan=doc(),run_root=ROOT/'synthetic/nonce',parent_child_remaining_seconds=21600);out=capture(s.start);invalid=[]
 for n in ['','custody-'+'a'*32,'A'*32,'a'*31,'a'*33]:invalid.append(bool(capture(lambda:C.NativeCustodySession(plan=doc(),run_root=ROOT/'synthetic/nonce',parent_child_remaining_seconds=21600,nonce=n)).get('exception')))
 return len(s._nonce)==32 and all(invalid) and not (ROOT/'synthetic/nonce').exists() and not out.get('exception'),dict(nonce=s._nonce,invalid_rejected=invalid,outcome=out,state=s.state,failures=s._failures,side_effect=(ROOT/'synthetic/nonce').exists())
def reader_owner():
 f=F('reader_wait');k=core(f,'retained-reader');k.arm();k.launch();o=capture(k.stop);snap=snapshot(k,f);alive=[r for r in k.readers if r.is_alive()];held={r.handle for r in alive};ok=bool(alive) and held.issubset(f.live) and all(r in k.readers for r in alive) and k.state=='UNKNOWN_RETAINED'
 # Actual reader owner is preserved by Core.readers, even though pending table omits it.
 f.gate.set()
 for r in k.readers:r.join(1)
 recovery=capture(k._close_readers);snap.update(outcome=o,retained_reader_handles=list(held),recovery=recovery,after_owner_recovery=dict(f.live));f.salvage();return ok,snap

def loop_case(stage):
 f=F();k=core(f,'loop-'+stage);cl=Clock();calls=[]
 class Ch:
  def bind_deadline(self,d):calls.append(['bound',d])
  def write(self,raw):
   kind=json.loads(raw)['kind'];calls.append(['write',kind,cl.v])
   if kind==stage:raise BrokenPipeError(stage)
  def read(self,t):return C.encode_command('STOP',run_id=k.plan.run_id,candidate_sha=k.plan.candidate_sha,authorization_sha256=k.plan.authorization_sha256,nonce='a'*32,sequence=1)
 if stage=='arm_deadline':
  old=f.create_job
  def delayed():
   result=old();cl.v+=22000;return result
  f.create_job=delayed
 loop=B.BrokerLoop(core=k,transport=Ch(),plan=k.plan,nonce='a'*32,clock=cl,wall=lambda:1000.)
 out=capture(loop.run);snap=snapshot(k,f);snap.update(outcome=out,channel=calls,mono_deadline=loop._deadline_mono)
 ok=not f.live
 if stage=='arm_deadline':ok=ok and not any(x[0]=='create' for x in f.calls)
 f.salvage()
 for r in k.readers:r.join(1)
 return ok,snap

def parent_fault(mode):
 s,h,cl=session(facts=dict(channel_closed=True,process_exited=True,process_handle_released=True));original=s._launcher
 def launch(p,r,n):
  peer=original(p,r,n)
  if mode=='parse':peer.q=queue.Queue();peer.q.put(b'{bad json}\n')
  else:
   def bad(t):raise KeyboardInterrupt('cancel') if mode=='cancel' else RuntimeError('read_failed')
   peer.read=bad
  return peer
 s._launcher=launch;o=capture(s.start);snap=dict(outcome=o,evidence=s.evidence(),closed=h['peer'].closed);ok=h['peer'].closed==1 and s.state=='UNKNOWN_RETAINED' and (mode!='cancel' or o.get('exception')=='KeyboardInterrupt');capture(s._close_broker);return ok,snap

def windows_endpoint_methods():
 # Pure Python methods on the production endpoint, injected original-handle facade.
 # Do not call its Windows-only msvcrt constructor or modify platform identity.
 closed=[];writes=[]
 class Api:
  def duplicate_current_thread_handle(self):return 701
  def write_stream(self,h,data):writes.append(bytes(data));return 1
  def cancel_synchronous_io(self,h):return 'NOT_FOUND'
  def close_handle(self,h):closed.append(h)
 ep=B._WindowsPipeEndpoint.__new__(B._WindowsPipeEndpoint);ep._api=Api();ep._file=types.SimpleNamespace(close=lambda:closed.append('file'));ep._name='inprocess';ep._handle=702;ep._clock=time.monotonic;ep._reader=None;ep._writer=None;ep._closed=False;ep._retained=[];ep.facts={}
 out=capture(lambda:ep.write(b'abcdef',time.monotonic()+1));facts=ep.close();snap=dict(outcome=out,writes=writes,closed=list(closed),facts=dict(facts),workers_alive=bool(ep._writer and ep._writer.is_alive()));ok=out.get('returned')==6 and writes==[b'abcdef',b'bcdef',b'cdef',b'def',b'ef',b'f'] and 701 in closed
 # The endpoint owns the worker; retain that exact reference for recovery.
 if ep._writer:ep._writer.stop();ep._writer.join(1);ep._api.close_handle(701)
 return ok,snap

CASES=[('M01_directory',directory),('m01_sealed',sealing),('M02_M03_declaration',abi),('M03_create_normal',lambda:create_case('normal')),('M03_attribute_cleanup_exception',lambda:create_case('attribute_exception')),('M03_birth_failure',lambda:create_case('birth')),('M03_birth_close_failure',lambda:create_case('birth_close_failure'))]
CASES += [('M04_job_'+str(x),lambda x=x:job_case(*x)) for x in [(2,2,24),(2,1,16),(0,1,16),(0,0,0),(1,1,0),(18,18,152),(1,1,999)]]
CASES += [('M05_M06_M09_'+str(m),lambda m=m:core_case(m)) for m in [None,'assign_broker','assign_cancel','diagnostic','stop_ordinary','limits_close','reader_error']]
CASES += [('M07_refused',parent_refused),('M07_thread_start',parent_thread_start),('M09_close_false',lambda:parent_bad_close(dict(process_exited=False,channel_closed=False))),('M09_close_unknown',lambda:parent_bad_close(None)),('M08_heartbeat_and_budget',heartbeat),('M08_heartbeat_failure',heartbeat_failure),('M08_shared_cleanup',close_budget),('M08_unterminated_frame',framing),('M08_M09_thread_handle',windows_worker),('M10_parser',sampler),('M11_nonce_mapping',nonce)]
CASES += [('M05_actual_retained_reader_owner',reader_owner)]
CASES += [('M06_M08_loop_'+v,lambda v=v:loop_case(v)) for v in ['READY','STATUS','STOPPED','arm_deadline']]
CASES += [('M07_fault_'+v,lambda v=v:parent_fault(v)) for v in ['parse','ordinary','cancel']]
CASES += [('M08_M09_windows_endpoint_methods',windows_endpoint_methods)]
def run():
 for n,f in CASES:check(n,f)
 return RESULTS
