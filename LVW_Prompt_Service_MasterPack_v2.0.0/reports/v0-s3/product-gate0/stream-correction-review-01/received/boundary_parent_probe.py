import os,time,threading,json,hashlib,importlib.util
from pathlib import Path
from tools import v0_s3_supervisor as s
OUT=Path(__file__).resolve().parent;root=OUT/'boundary-root';root.mkdir(exist_ok=True);receipt=b'{"rows":[]}';(root/'canonical.json').write_bytes(receipt)
plan=s.SealedPlan([{'ordinal':i,'asset_id':'I%02d'%i,'media_kind':'image'} for i in range(1,17)])
def frame(event,payload,seq):return s.canonical_json({'schema':s.PROTOCOL_SCHEMA,'run_id':'syn1','candidate_sha':'a'*40,'authorization_sha256':'b'*64,'sequence':seq,'event':event,'payload':payload}).encode()+b'\n'
ref={'canonical_receipt':{'reference':'canonical.json','bytes':len(receipt),'sha256':hashlib.sha256(receipt).hexdigest()}}
start=frame('STARTED',{},1);parts=[start]+[frame('PROGRESS',{'p':'x'*20000},i) for i in range(2,14)];last=frame('TERMINAL',ref,15);base=frame('PROGRESS',{'p':''},14);remaining=s.MAX_STREAM_BYTES-sum(map(len,parts))-len(last)-len(base);assert remaining>0
exact=b''.join(parts)+frame('PROGRESS',{'p':'x'*remaining},14)+last;assert len(exact)==s.MAX_STREAM_BYTES and all(len(x)<=s.MAX_MESSAGE_BYTES for x in exact.splitlines())
class Handle:
 def __init__(self):
  r,self.w=os.pipe();self.stdout=os.fdopen(r,'rb',buffering=0);r,self.ew=os.pipe();self.stderr=os.fdopen(r,'rb',buffering=0);self.stdin=None;self.pid=None;self.rc=None;self.actions=[]
 def poll(self):return self.rc
 def terminate(self):self.actions.append('terminate');self.rc=-15
 def kill(self):self.actions.append('kill');self.rc=-9
 def wait(self,timeout=None):return self.rc
results={}
for channel in ('stdout','stderr'):
 for over in (0,1):
  h=Handle();o=s.ParentSupervisor(command=['sealed-fake'],run_id='syn1',candidate_sha='a'*40,authorization_sha256='b'*64,plan=plan,root=root,spawner=lambda cmd:h,phase_timeout=2,child_timeout=3,grace_seconds=.01);o.start()
  stdout=exact+b'x'*over if channel=='stdout' else start+frame('TERMINAL',ref,2);stderr=b'q'*(s.MAX_STREAM_BYTES+over) if channel=='stderr' else b''
  def deliver():
   os.write(h.w,stdout);os.close(h.w)
   if stderr:os.write(h.ew,stderr)
   os.close(h.ew);h.rc=0
  t=threading.Thread(target=deliver);t.start();assert o.stdout_reader.finished.wait(2) and o.stderr_reader.finished.wait(2);t.join(2);begin=time.monotonic();e=o.run()
  expected=channel.upper()+'_STREAM_LIMIT_EXCEEDED' if over else None;assert e['protocol_violation']==expected and e['archive_allowed']==(not over)
  results[channel+('_over' if over else '_exact')]={'expected':expected,'actual':e['protocol_violation'],'archive_allowed':e['archive_allowed'],'stdout_bytes':e['stdout_bytes'],'stderr_bytes':e['stderr_bytes'],'message_count':e['message_count'],'duration':time.monotonic()-begin,'retained_stdout':len(o.stdout_reader.raw()),'retained_stderr':len(o.stderr_reader.raw()),'consumed_stdout_pending_bytes':e['stdout_bytes_retained'],'wire_sha256':hashlib.sha256(stdout).hexdigest(),'reported_stdout_sha256':e['stdout_sha256'],'only_original_handle_actions':h.actions,'cleanup':e['cleanup']}
  h.stdout.close();h.stderr.close()
# Existing fixed deadlines stay fixed: production defaults, history cannot reset.
h=Handle();now=[10.];o=s.ParentSupervisor(command=['sealed-fake'],run_id='syn1',candidate_sha='a'*40,authorization_sha256='b'*64,plan=plan,root=root,spawner=lambda cmd:h,clock=lambda:now[0]);o.start();o._fix_history_deadline('I01');first=o.history_deadlines['I01'];now[0]=50;o._fix_history_deadline('I01');assert o.history_deadlines['I01']==first
results['deadline_defaults']={'phase':o.phase_timeout,'history':o.history_timeout,'child':o.child_timeout,'phase_deadline':o.phase_deadline,'child_deadline':o.child_deadline,'history_deadline':first,'history_unchanged':o.history_deadlines['I01']==first};os.close(h.w);os.close(h.ew);assert o.stdout_reader.finished.wait(1) and o.stderr_reader.finished.wait(1);h.stdout.close();h.stderr.close()
(OUT/'boundary-parent-observations.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
