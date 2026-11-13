"""Independent controlled interleavings; real pipes, no child processes."""
import os,sys,time,threading,dis,json,hashlib
from pathlib import Path
from tools import v0_s3_supervisor as s
O=Path(__file__).resolve().parent
results={}
class Handle:
 def __init__(self,stopped=True):
  r,self.w=os.pipe();er,self.ew=os.pipe();self.stdout=os.fdopen(r,'rb',buffering=0);self.stderr=os.fdopen(er,'rb',buffering=0);self.stdin=None;self.pid=None;self.status=0 if stopped else None
 def poll(self):return self.status
 def terminate(self):self.status=-15
 def kill(self):self.status=-9
 def wait(self,timeout=None):return self.status
 def release(self):
  for n in ('w','ew'):
   f=getattr(self,n)
   if f is not None:os.close(f);setattr(self,n,None)
 def close(self):self.stdout.close();self.stderr.close()
def plan():return s.SealedPlan([{'ordinal':i,'asset_id':'I%02d'%i,'media_kind':'image'} for i in range(1,17)])
def parent(h,root=O,clock=time.monotonic,**kw):return s.ParentSupervisor(command=['fake-no-process'],run_id='syn1',candidate_sha='a'*40,authorization_sha256='b'*64,plan=plan(),root=root,spawner=lambda c:h,clock=clock,**kw)
def wire(event,seq=1,payload=None):return (s.canonical_json(dict(schema=s.PROTOCOL_SCHEMA,run_id='syn1',candidate_sha='a'*40,authorization_sha256='b'*64,sequence=seq,event=event,payload=payload or {}))+'\n').encode()
def wait_bytes(r,n):
 end=time.monotonic()+2
 while r.total<n and time.monotonic()<end:time.sleep(.001)
 assert r.total>=n
def monitor(code,target,callback):
 sys.monitoring.use_tool_id(5,'independent-interleaving')
 sys.monitoring.register_callback(5,sys.monitoring.events.INSTRUCTION,lambda c,o:callback() if o==target else None)
 sys.monitoring.set_local_events(5,code,sys.monitoring.events.INSTRUCTION)
def off(code):sys.monitoring.set_local_events(5,code,0);sys.monitoring.free_tool_id(5)
def barrier():
 paused=threading.Event();release=threading.Event()
 def pause():paused.set();assert release.wait(2)
 return paused,release,pause
raw=wire('STARTED')
# M2: producer paused before retain acquisition; consumer sees empty, then full frame.
h=Handle();p=parent(h);r=s._StreamReader(h.stdout,s.MAX_STREAM_BYTES);p.stdout_reader=r
code=s._StreamReader._retain.__code__;target=next(i.offset for i in dis.get_instructions(code) if i.opname=='CALL');paused,release,pause=barrier();monitor(code,target,pause)
r.start();os.write(h.w,raw);assert paused.wait(2);p._consume_stdout();assert p.state.count==0;release.set();h.release();r.join(2);off(code);p._consume_stdout();assert p.state.count==1 and r.raw()==raw
results['M2_producer_handoff']={'count':p.state.count,'raw_bytes':len(r.raw()),'offset':target};h.close()
# M2: append between captured end and cursor update must remain pending.
h=Handle();p=parent(h);r=s._StreamReader(h.stdout,s.MAX_STREAM_BYTES);p.stdout_reader=r;r.start();code=s._StreamReader.take.__code__;ins=list(dis.get_instructions(code));idx=next(i for i,v in enumerate(ins) if v.opname=='STORE_FAST' and v.argval=='end');target=ins[idx+1].offset
paused,release,pause=barrier();monitor(code,target,pause);t=threading.Thread(target=p._consume_stdout);t.start();assert paused.wait(2);os.write(h.w,raw);wait_bytes(r,len(raw));release.set();t.join(2);off(code);p._consume_stdout();h.release();r.join(2);assert p.state.count==1 and r.raw()==raw
results['M2_consumer_handoff']={'count':p.state.count,'cursor':r._cursor,'blocks':len(r._blocks),'offset':target};h.close()
# S interleaving 1: publication and EOF occur after snapshot captured its state.
h=Handle();r=s._StreamReader(h.stdout,100);r.start();code=s._StreamReader.snapshot.__code__;target=next(i.offset for i in dis.get_instructions(code) if i.opname=='STORE_SUBSCR')
paused,release,pause=barrier();monitor(code,target,pause);box={};t=threading.Thread(target=lambda:box.update(r.snapshot()));t.start();assert paused.wait(2);os.write(h.w,b'hello');h.release();r.join(2);assert r.finished.is_set();release.set();t.join(2);off(code)
assert box['total_observed']==box['hashed_bytes']==0 and not box['complete'] and box['hash_scope']=='observed_prefix'
results['S_snapshot_then_EOF']={'offset':target,'captured':box,'final':r.snapshot()};h.close()
# S interleaving 2: reader has bytes but has not published them.
h=Handle();r=s._StreamReader(h.stdout,100);code=s._StreamReader.run.__code__;target=[i.offset for i in dis.get_instructions(code) if i.opname=='LOAD_ATTR' and i.argval=='_retain'][-1]
paused,release,pause=barrier();monitor(code,target,pause);r.start();os.write(h.w,b'world');assert paused.wait(2);snap=r.snapshot();assert snap['hashed_bytes']==snap['total_observed']==0;release.set();h.release();r.join(2);off(code)
assert r.snapshot()['sha256']==hashlib.sha256(b'world').hexdigest();results['S_before_publication']={'offset':target,'captured':snap,'final':r.snapshot()};h.close()
# In-progress bytes, exact and one-over byte budget, hashes after consumption.
boundaries={}
for name,data,limit,keep_open in [('prefix',b'abc',3,True),('exact',b'abc',3,False),('over',b'abcd',3,False)]:
 h=Handle();r=s._StreamReader(h.stdout,limit);r.start();os.write(h.w,data);wait_bytes(r,len(data))
 if not keep_open:h.release();r.join(2)
 before=r.snapshot();got=r.take();after=r.snapshot();assert got==data[:limit] and after['retained_bytes']==0 and after['sha256']==hashlib.sha256(data[:limit]).hexdigest() and after['hashed_bytes']==min(len(data),limit)
 assert before['hash_scope']==('observed_prefix' if keep_open else ('prefix_within_budget' if len(data)>limit else 'all_observed'))
 boundaries[name]={'before':before,'after_consume':after};h.release();r.join(2);h.close()
results['S_boundaries']=boundaries
# M1: shared bounded EOF drain with held-open actual pipes, clipped by phase/child.
for name,phase,child in [('phase_clip',.03,1),('child_clip',1,.04),('shared',2,2),('zero_remaining',.01,.01)]:
 root=O/name;root.mkdir();canon=b'{"rows":[]}';(root/'canonical.json').write_bytes(canon);h=Handle();p=parent(h,root,phase_timeout=phase,child_timeout=child);p.start();terminal=wire('TERMINAL',payload={'canonical_receipt':{'reference':'canonical.json','bytes':len(canon),'sha256':hashlib.sha256(canon).hexdigest()}});os.write(h.w,terminal);wait_bytes(p.stdout_reader,len(terminal))
 if name=='zero_remaining':time.sleep(.02)
 begin=time.monotonic();e=p.run();elapsed=time.monotonic()-begin
 assert e['canonical_receipt_verified'] and not e['archive_allowed'] and e['root_retained'] and e['unknown_outcome'] and not e['stdout_drain_complete'] and not e['stderr_drain_complete'] and elapsed<.6
 h.release();p.stdout_reader.join(2);p.stderr_reader.join(2);h.close();results['M1_'+name]={'elapsed':elapsed,'evidence':e,'settled':not p.stdout_reader.is_alive() and not p.stderr_reader.is_alive()}
# H: real protocol consumption driven by controlled fake time, preserving first audit.
class Clock:
 now=0
 def __call__(self):return self.now
clock=Clock();h=Handle(False);p=parent(h,clock=clock,phase_timeout=100000,child_timeout=100000);p.start();seq=0
def event(ev,asset,ordinal):
 global seq
 seq+=1;os.write(h.w,wire(ev,seq,{'asset_id':asset,'ordinal':ordinal}));end=time.monotonic()+2
 while p.state.last_sequence<seq and time.monotonic()<end:p._consume_stdout();time.sleep(.001)
 assert p.state.last_sequence==seq
for ev in ('ROW_STARTED','HISTORY_WAIT_STARTED'):event(ev,'I01',1)
clock.now=10;event('ROW_FINISHED','I01',1);clock.now=500
for ev in ('ROW_STARTED','HISTORY_WAIT_STARTED'):event(ev,'I02',2)
checks={}
for now in (600,601,1100,1100.001):clock.now=now;checks[str(now)]=p._deadline_state()
assert checks=={'600':None,'601':None,'1100':None,'1100.001':'HISTORY_DEADLINE_EXCEEDED:I02'}
assert p.history_records['I01']=={'first_start':0,'deadline':600,'completed_at':10}
results['H']={'checks':checks,'records':p.history_records,'completed':sorted(p.history_completed)}
h.release();p.stdout_reader.join(2);p.stderr_reader.join(2);h.close()
assert len(threading.enumerate())==1
(O/'stream-history.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
