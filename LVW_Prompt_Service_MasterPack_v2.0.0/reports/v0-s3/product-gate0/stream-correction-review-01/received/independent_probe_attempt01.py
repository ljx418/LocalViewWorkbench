"""Zero subprocess independent adversarial cases through real production owners."""
import sys,os,json,time,threading,hashlib,io,contextlib,dis,importlib.util
from pathlib import Path
from tools import v0_s3_supervisor as s
OUT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('independent_fixture',Path(s.__file__).parent/'fixtures/v0_s3_supervisor_fixture.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)
RUN='syn1';C='a'*40;A='b'*64
rows=[{'ordinal':i,'asset_id':'I%02d'%i,'media_kind':'image' if i<11 else 'video'} for i in range(1,17)]
plan=s.SealedPlan(rows)
results={}
def capture(name,value):
 results[name]=value
 print(name,json.dumps(value,sort_keys=True),flush=True)
def values(root=''):
 return {'run_id':RUN,'candidate_sha':C,'authorization_sha256':A,'root':root,'terminal_reference':'canonical.json','plan':rows}
def wire(event,payload,seq=1):
 return f.Writer.encode(f.Writer(values()).message(event,payload,sequence=seq))+b'\n'
class Output:
 def __init__(self):self.buffer=io.BytesIO()
 def flush(self):pass
def scenario(name):
 stream=Output()
 with contextlib.redirect_stdout(stream):
  f.SCENARIO_FUNCTIONS[name](f.Writer(values()),values(),rows)
 return stream.buffer.getvalue()
class Handle:
 def __init__(self,with_stderr=True):
  r,self.w=os.pipe();self.stdout=os.fdopen(r,'rb',buffering=0)
  if with_stderr:
   r,self.ew=os.pipe();self.stderr=os.fdopen(r,'rb',buffering=0)
  else:self.stderr=None;self.ew=None
  self.stdin=None;self.pid=None;self.returncode=None;self.actions=[];self.on_stop=None
 def poll(self):return self.returncode
 def wait(self,timeout=None):return self.returncode
 def terminate(self):
  self.actions.append('terminate');self.returncode=-15
  if self.on_stop:self.on_stop()
 def kill(self):self.actions.append('kill');self.returncode=-9
 def close_writer(self,which='stdout'):
  attr='w' if which=='stdout' else 'ew';fd=getattr(self,attr)
  if fd is not None:os.close(fd);setattr(self,attr,None)
 def close_all(self):
  self.close_writer();self.close_writer('stderr')
  for stream in (self.stdout,self.stderr):
   if stream is not None:stream.close()
def supervisor(handle,root,**kw):
 obj=s.ParentSupervisor(command=['sealed-fake-only'],run_id=RUN,candidate_sha=C,authorization_sha256=A,plan=plan,root=root,spawner=lambda command:handle,phase_timeout=kw.get('phase_timeout',2),child_timeout=kw.get('child_timeout',3),grace_seconds=.01)
 obj.poll_interval=.001
 return obj
def compact(e):
 return {k:e[k] for k in ('protocol_violation','stream_violation','message_count','stdout_bytes','stderr_bytes','stdout_bytes_retained','stderr_bytes_retained','stdout_sha256','stderr_sha256','stdout_overflow','stderr_overflow','canonical_receipt_verified','unknown_outcome','root_retained','archive_allowed','next_phase_allowed','cleanup')}
def pipe_case(name,raw,err=b'',**kw):
 h=Handle();o=supervisor(h,OUT,**kw);o.start()
 def writer():
  try:
   if raw:os.write(h.w,raw)
   h.close_writer()
   if err:os.write(h.ew,err)
   h.close_writer('stderr');h.returncode=0
  except OSError:pass
 t=threading.Thread(target=writer);t.start();start=time.monotonic();e=o.run();t.join(3)
 for reader in (o.stdout_reader,o.stderr_reader):reader.finished.wait(1)
 h.close_all();v=compact(e);v['elapsed']=time.monotonic()-start;v['writer_settled']=not t.is_alive();capture(name,v);return e
# Generated NaN, unchanged raw output, real parent read and count oracle.
nan=scenario('nonfinite_number');assert nan.endswith(b'\n') and len(nan.splitlines())==1
try:s.decode_message(nan[:-1]);raise AssertionError('NaN accepted')
except s.SupervisionError as error:assert error.code=='MESSAGE_NONFINITE_NUMBER'
assert pipe_case('nan_real_pipe',nan)['protocol_violation']=='MESSAGE_NONFINITE_NUMBER'
raw=scenario('message_flood');frames=raw.splitlines();assert len(frames)==1025
for i,line in enumerate(frames,1):
 m=s.decode_message(line);assert set(m)==s.MESSAGE_KEYS and m['sequence']==i and (m['run_id'],m['candidate_sha'],m['authorization_sha256'])==(RUN,C,A)
state=s.ProtocolState(run_id=RUN,candidate_sha=C,authorization_sha256=A,plan=plan)
for line in frames[:1024]:state.accept(s.decode_message(line))
try:state.accept(s.decode_message(frames[1024]));raise AssertionError('count accepted')
except s.SupervisionError as error:assert error.code=='MESSAGE_COUNT_EXCEEDED'
capture('wire_calculation',{'frames':len(frames),'exact_1024_wire':sum(len(x)+1 for x in frames[:1024]),'over_1025_wire':len(raw),'longest_frame_with_newline':max(len(x)+1 for x in frames),'identity_lengths':[len(RUN),len(C),len(A)],'complete':raw.endswith(b'\n')})
assert pipe_case('flood_real_pipe',raw)['protocol_violation']=='MESSAGE_COUNT_EXCEEDED'
partial=scenario('blocking_persistence');assert not partial.endswith(b'\n')
capture('blocking_partial',{'bytes':len(partial),'complete_frames':partial.count(b'\n'),'incomplete_preserved':True})
# Read stream exact/over through production _StreamReader, awaiting completion explicitly.
for channel in ('stdout','stderr'):
 for over in (0,1):
  data=b'z'*(s.MAX_STREAM_BYTES+over);r,w=os.pipe();stream=os.fdopen(r,'rb',buffering=0);reader=s._StreamReader(stream,s.MAX_STREAM_BYTES);reader.start()
  def deliver():os.write(w,data);os.close(w)
  t=threading.Thread(target=deliver);t.start();assert reader.finished.wait(3);t.join();stream.close()
  h=Handle(False);o=supervisor(h,OUT);setattr(o,channel+'_reader',reader)
  expected=(channel.upper()+'_STREAM_LIMIT_EXCEEDED') if over else None
  assert o._stream_failure()==expected
  capture(channel+('_over_reader' if over else '_exact_reader'),{'total':reader.total,'retained_raw':len(reader.raw()),'overflow':reader.overflow,'oracle':o._stream_failure(),'reported_digest':hashlib.sha256(reader.raw()).hexdigest(),'all_observed_digest':hashlib.sha256(data).hexdigest(),'hash_matches_all_observed':reader.raw()==data})
  h.close_all()
# Parent stream cap oracle with a legal terminal: stdout payload padded as legal progress frames.
root=OUT/'synthetic-root';root.mkdir(exist_ok=True);receipt=b'{"rows":[]}';(root/'canonical.json').write_bytes(receipt)
terminal=wire('TERMINAL',{'canonical_receipt':{'reference':'canonical.json','bytes':len(receipt),'sha256':hashlib.sha256(receipt).hexdigest()}})
# Valid bounded success: use production wire and actual receipt, closed pipe EOF.
e=pipe_case('closed_success',terminal) # reference root differs; separate proper root cases below
# Fake handle using real pipes; terminal immediately available, keep writers open past final drain.
def terminal_case(name,late=None,pending=False,tail=b''):
 h=Handle();o=supervisor(h,root,phase_timeout=.03,child_timeout=.04);o.start();os.write(h.w,terminal+tail)
 if not pending:
  h.close_writer()
  if late:
   h.on_stop=lambda:late(o,h)
  else:h.close_writer('stderr')
 else:h.returncode=0
 start=time.monotonic();e=o.run();elapsed=time.monotonic()-start
 snap=compact(e);snap.update({'elapsed':elapsed,'stdout_finished_at_return':o.stdout_reader.finished.is_set(),'stderr_finished_at_return':o.stderr_reader.finished.is_set(),'remaining_stdout_buffer':len(o.stdout_buffer),'child_deadline':o.child_deadline,'returned_after_child_deadline':o.clock()>o.child_deadline,'only_owned_actions':h.actions})
 h.close_writer();h.close_writer('stderr')
 assert o.stdout_reader.finished.wait(2) and o.stderr_reader.finished.wait(2)
 h.close_all();capture(name,snap);return e
assert terminal_case('terminal_closed_success')['archive_allowed'] is True
assert terminal_case('terminal_unfinished_real_pipes',pending=True)['archive_allowed'] is True # observed contract breach
terminal_case('terminal_trailing_partial',tail=b'{"unfinished":')
# Late stderr overflow released by cleanup, before drain completes.
def late_over(o,h):
 def deliver():os.write(h.ew,b'e'*(s.MAX_STREAM_BYTES+1));h.close_writer('stderr')
 t=threading.Thread(target=deliver);t.start()
e=terminal_case('terminal_late_stderr_overflow',late=late_over);assert e['protocol_violation']==s.STDERR_STREAM_LIMIT_EXCEEDED and not e['archive_allowed']
# Stable read errors on actual production reader run, not a fabricated overflow flag.
class BadStream:
 def fileno(self):raise OSError('controlled descriptor error')
for channel in ('stdout','stderr'):
 h=Handle();getattr(h,channel).close();setattr(h,channel,BadStream())
 # retain other writer until termination closes it; original fake handle remains custody owner.
 h.on_stop=lambda h=h:(h.close_writer(),h.close_writer('stderr'))
 o=supervisor(h,root);e=o.run();assert e['protocol_violation']==channel.upper()+'_STREAM_READ_FAILED';capture(channel+'_parent_read_error',compact(e))
 h.close_writer();h.close_writer('stderr')
 other=o.stderr_reader if channel=='stdout' else o.stdout_reader;assert other.finished.wait(2)
# Late read failure in final drain via controlled finished.wait, not real I/O latency.
class LateReader:
 def __init__(self,kind):self.overflow=False;self.error=None;self.total=0;self.kind=kind;self.finished=self
 def wait(self,timeout=None):
  if self.kind=='overflow':self.overflow=True
  else:self.error='OSError'
  return True
 def take(self):return b''
 def raw(self):return b''
 def retained(self):return 0
for channel in ('stdout','stderr'):
 for kind in ('overflow','read_error'):
  o=supervisor(Handle(False),root);o.state.accept(s.decode_message(terminal[:-1]));o.terminal_receipt=json.loads(terminal)['payload']['canonical_receipt'];setattr(o,channel+'_reader',LateReader(kind));o._drain_streams();o._verify_terminal_receipt();e=o.evidence();expected=channel.upper()+('_STREAM_LIMIT_EXCEEDED' if kind=='overflow' else '_STREAM_READ_FAILED');assert e['protocol_violation']==expected and not e['archive_allowed'];capture('late_'+channel+'_'+kind,compact(e));o.process=None
# Priority of simultaneous malformed protocol and stream overrun is protocol first.
h=Handle(False);o=supervisor(h,root);reader=LateReader('overflow');reader.overflow=True;reader.take=lambda: b'invalid\n';o.stdout_reader=reader
try:o._consume_stdout()
except s.SupervisionError as error:o.violation=error.code
capture('simultaneous_priority',{'protocol':o.violation,'stream':o._stream_failure()});h.close_all()
# Controlled opcode schedule of actual _retain/take through a real pipe.
# Stop after loading the bound append method, before CALL; consumer swaps the empty list.
r,w=os.pipe();stream=os.fdopen(r,'rb',buffering=0);reader=s._StreamReader(stream,s.MAX_STREAM_BYTES)
paused=threading.Event();release=threading.Event();calls=[i for i in dis.get_instructions(s._StreamReader._retain) if i.opname=='CALL'];target=calls[0].offset
code=s._StreamReader._retain.__code__
def trace(frame,event,arg):
 if frame.f_code is code:
  frame.f_trace_opcodes=True
  if event=='opcode' and frame.f_lasti==target:
   paused.set();assert release.wait(3)
 return trace
threading.settrace(trace);reader.start();threading.settrace(None)
one=wire('STARTED',{});os.write(w,one);assert paused.wait(3)
first=reader.take();release.set();os.close(w);assert reader.finished.wait(3);second=reader.take()
h=Handle(False);o=supervisor(h,root);o.stdout_reader=reader;o._consume_stdout()
capture('controlled_handoff_schedule',{'paused_opcode':target,'first_take_bytes':len(first),'second_take_bytes':len(second),'raw_received_bytes':len(reader.raw()),'total':reader.total,'message_count_after_parent_consume':o.state.count,'expected_message_count':1,'evidence_digest_matches_full_wire':hashlib.sha256(reader.raw()).hexdigest()==hashlib.sha256(one).hexdigest(),'stream_error':reader.error,'overflow':reader.overflow})
assert not first and not second and reader.raw()==one and o.state.count==0
h.close_all();stream.close()
# Deadline defaults and immutable history/phase clocks, no fixture process.
h=Handle(False);clock=[10.0];o=s.ParentSupervisor(command=['sealed-fake'],run_id=RUN,candidate_sha=C,authorization_sha256=A,plan=plan,root=root,spawner=lambda cmd:h,clock=lambda:clock[0]);o.start();o._fix_history_deadline('I01');d=o.history_deadlines['I01'];clock[0]=50;o._fix_history_deadline('I01');assert o.history_deadlines['I01']==d
capture('frozen_deadlines',{'phase':o.phase_timeout,'history':o.history_timeout,'child':o.child_timeout,'history_not_extended':o.history_deadlines['I01']==d});h.close_writer();assert o.stdout_reader.finished.wait(1);h.close_all()
(OUT/'independent-observations.json').write_text(json.dumps(results,indent=2,sort_keys=True)+'\n')
