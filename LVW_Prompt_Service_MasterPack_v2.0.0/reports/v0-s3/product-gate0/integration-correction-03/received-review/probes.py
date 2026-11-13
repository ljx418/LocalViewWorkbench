import os,sys,time,threading,dis,json,hashlib
from pathlib import Path
from tools import v0_s3_supervisor as s
O=Path(__file__).resolve().parent
results={}
class Handle:
 def __init__(self, stopped=True):
  self.r,self.w=os.pipe();self.er,self.ew=os.pipe();self.stdout=os.fdopen(self.r,'rb',buffering=0);self.stderr=os.fdopen(self.er,'rb',buffering=0);self.stdin=None;self.pid=None;self.status=0 if stopped else None
 def poll(self):return self.status
 def terminate(self):self.status=-15
 def kill(self):self.status=-9
 def wait(self,timeout=None):return self.status
 def release(self):
  for n in ('w','ew'):
   f=getattr(self,n)
   if f is not None:os.close(f);setattr(self,n,None)
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

# Actual pipe -> production reader -> production parent's protocol state, reader paused before append CALL.
h=Handle();p=parent(h);r=s._StreamReader(h.stdout,s.MAX_STREAM_BYTES);p.stdout_reader=r
code=s._StreamReader._retain.__code__;target=next(i.offset for i in dis.get_instructions(code) if i.opname=='CALL');paused=threading.Event();release=threading.Event()
def pause():paused.set();assert release.wait(2)
monitor(code,target,pause)
r.start();raw=wire('STARTED');os.write(h.w,raw);assert paused.wait(2);p._consume_stdout();count_before=p.state.count;release.set();h.release();r.join(2);off(code);p._consume_stdout()
results['reader_append_handoff']={'offset':target,'before':count_before,'after':p.state.count,'raw_bytes':len(r.raw()),'expected':len(raw),'finished':r.finished.is_set()};assert p.state.count==1 and r.raw()==raw;h.stdout.close();h.stderr.close()
# Parent paused after capturing end; append arrives before slicing/cursor publication.
h=Handle();p=parent(h);r=s._StreamReader(h.stdout,s.MAX_STREAM_BYTES);p.stdout_reader=r;r.start()
code=s._StreamReader.take.__code__;ins=list(dis.get_instructions(code));idx=next(i for i,v in enumerate(ins) if v.opname=='STORE_FAST' and v.argval=='end');target=ins[idx+1].offset
paused=threading.Event();release=threading.Event();monitor(code,target,pause)
t=threading.Thread(target=p._consume_stdout);t.start();assert paused.wait(2);os.write(h.w,raw);wait_bytes(r,len(raw));release.set();t.join(2);off(code);p._consume_stdout();h.release();r.join(2)
results['parent_cursor_handoff']={'offset':target,'count':p.state.count,'cursor':r._cursor,'blocks':len(r._blocks),'raw_bytes':len(r.raw())};assert p.state.count==1 and r.raw()==raw;h.stdout.close();h.stderr.close()
# Snapshot is paused after kept bytes captured, producer publishes bytes/total/EOF before snapshot resumes.
h=Handle();r=s._StreamReader(h.stdout,100);r.start();code=s._StreamReader.snapshot.__code__;ins=list(dis.get_instructions(code));idx=next(i for i,v in enumerate(ins) if v.opname=='STORE_FAST' and v.argval=='kept');target=ins[idx+1].offset
paused=threading.Event();release=threading.Event();monitor(code,target,pause);box={}
t=threading.Thread(target=lambda:box.update(r.snapshot()));t.start();assert paused.wait(2);os.write(h.w,b'hello');h.release();r.join(2);assert r.finished.is_set();release.set();t.join(2);off(code)
results['snapshot_completed_publication']={'offset':target,'snapshot':box,'actual_raw_hex':r.raw().hex(),'actual_total':r.total,'actual_sha256':hashlib.sha256(r.raw()).hexdigest(),'snapshot_corrupt_complete':box['complete'] and box['hashed_bytes']!=box['total_observed']}
assert box['complete'] and box['hashed_bytes']==0 and box['total_observed']==5;h.stdout.close();h.stderr.close()
# Reader paused just before total publication, proving no multi-step atomic update under GIL.
h=Handle();r=s._StreamReader(h.stdout,100);code=s._StreamReader.run.__code__;ins=list(dis.get_instructions(code));targets=[v.offset for v in ins if v.opname=='STORE_ATTR' and v.argval=='total'];target=targets[-1]
paused=threading.Event();release=threading.Event();monitor(code,target,pause);r.start();os.write(h.w,b'world');assert paused.wait(2);snap=r.snapshot();release.set();h.release();r.join(2);off(code)
results['snapshot_before_total_publication']={'offset':target,'snapshot':snap,'final_snapshot':r.snapshot()};assert snap['hashed_bytes']==5 and snap['total_observed']==0;h.stdout.close();h.stderr.close()
# In-flight empty stream cannot honestly mean entire stream even if current kept == observed.
h=Handle();r=s._StreamReader(h.stdout,100);r.start();results['unfinished_scope']=r.snapshot();assert not r.finished.is_set();os.write(h.w,b'later');h.release();r.join(2);h.stdout.close();h.stderr.close()
# Drain with legal terminal + real canonical, held pipes and phase/child clipping plus late real overflow.
for name,phase,child in [('phase_clip',.03,1),('child_clip',1,.04),('shared',2,2),('zero_remaining',.01,.01)]:
 root=O/name;root.mkdir();canon=b'{"rows":[]}';(root/'canonical.json').write_bytes(canon);h=Handle();p=parent(h,root,phase_timeout=phase,child_timeout=child);p.start();terminal=wire('TERMINAL',payload={'canonical_receipt':{'reference':'canonical.json','bytes':len(canon),'sha256':hashlib.sha256(canon).hexdigest()}});os.write(h.w,terminal);wait_bytes(p.stdout_reader,len(terminal))
 if name=='zero_remaining':time.sleep(.02)
 begin=time.monotonic();e=p.run();elapsed=time.monotonic()-begin
 assert e['canonical_receipt_verified'] and not e['archive_allowed'] and e['root_retained'] and e['unknown_outcome'] and not e['stdout_drain_complete'] and not e['stderr_drain_complete'];assert elapsed<.6
 if name=='shared':
  t=threading.Thread(target=lambda:os.write(h.ew,b'x'*(s.MAX_STREAM_BYTES+1)));t.start();p.stderr_reader.join(2);t.join(2);assert p.stderr_reader.overflow
  results['late_overflow']={'failure':p._stream_failure(),'returned_archive_allowed':e['archive_allowed'],'returned_hash_scope':e['stderr_hash_scope']}
 h.release();p.stdout_reader.join(2);p.stderr_reader.join(2);h.stdout.close();h.stderr.close();results[name]={'elapsed':elapsed,'drain_deadline':p._drain_deadline_value,'phase_deadline':p.effective_phase_deadline,'child_deadline':p.child_deadline,'evidence':e,'settled':not p.stdout_reader.is_alive() and not p.stderr_reader.is_alive()}
# Completed row's deadline must not govern later rows; real protocol consumption with fake clock.
class Clock:
 now=0
 def __call__(self):return self.now
clock=Clock();h=Handle(False);p=parent(h,clock=clock,phase_timeout=1000,child_timeout=2000);p.start()
seq=0
def event(ev,asset,ordinal):
 global seq
 seq+=1;raw=wire(ev,seq,{'asset_id':asset,'ordinal':ordinal});os.write(h.w,raw);wait_bytes(p.stdout_reader,p.stdout_reader.total+len(raw)) if False else None
 end=time.monotonic()+2
 while p.state.last_sequence<seq and time.monotonic()<end:p._consume_stdout();time.sleep(.001)
 assert p.state.last_sequence==seq
for ev in ('ROW_STARTED','HISTORY_WAIT_STARTED'):event(ev,'I01',1)
clock.now=10;event('ROW_FINISHED','I01',1);clock.now=500
for ev in ('ROW_STARTED','HISTORY_WAIT_STARTED'):event(ev,'I02',2)
clock.now=601;h.release();p.stdout_reader.join(2);p.stderr_reader.join(2);e=p.run()
results['history_completed_row_expiry']={'now':601,'history_deadlines':p.history_deadlines,'events':p.messages,'evidence':e};assert e['protocol_violation']=='HISTORY_DEADLINE_EXCEEDED:I01';assert p.history_deadlines['I02']==1000
# Aggregator old nine and absent independent QS remain non-green.
from tools import v0_s3_coordinator as c
old=c.aggregate_twelve_keys(receipts={'old_s2':{'status':'PASS','passed':9}},binding={'run_id':'syn1','candidate_sha':'a'*40})
receipts={name:{'kind':c.AGGREGATE_RECEIPT_KIND,'status':'PASS','run_id':'syn1','candidate_sha':'a'*40,'stage_pass_claim':False,'real_isolation':True,'cleanup_proven':True} for req in c.TWELVE_REQUIREMENTS.values() for name in req}
receipts.pop('independent_score',None);missing=c.aggregate_twelve_keys(receipts=receipts,binding={'run_id':'syn1','candidate_sha':'a'*40})
results['aggregator_negative']={'old_nine':old,'missing_independent':missing};assert old['pass_count']==0 and missing['keys']['V0-A11']['status']!='PASS' and missing['keys']['V0-A12']['status']!='PASS'
(O/'observations.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2));assert len(threading.enumerate())==1
