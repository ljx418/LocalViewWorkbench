import os,sys,time,json,threading,hashlib
from pathlib import Path
from tools import v0_s3_supervisor as s
OUT=Path(__file__).resolve().parent
root=OUT/'drain-root';root.mkdir(exist_ok=True);raw=b'{"rows":[]}';(root/'canonical.json').write_bytes(raw)
class Handle:
 def __init__(self):
  self.r,self.w=os.pipe();self.er,self.ew=os.pipe();self.stdout=os.fdopen(self.r,'rb',buffering=0);self.stderr=os.fdopen(self.er,'rb',buffering=0);self.pid=None;self.stdin=None
 def poll(self):return 0
 def terminate(self):raise AssertionError('already exited fake handle must not be terminated')
 def kill(self):raise AssertionError('must not kill another handle')
h=Handle();plan=s.SealedPlan([{'ordinal':i,'asset_id':'I%02d'%i,'media_kind':'image'} for i in range(1,17)])
o=s.ParentSupervisor(command=['fake-no-process'],run_id='syn1',candidate_sha='a'*40,authorization_sha256='b'*64,plan=plan,root=root,spawner=lambda cmd:h,phase_timeout=.03,child_timeout=.04)
terminal=s.canonical_json({'schema':s.PROTOCOL_SCHEMA,'run_id':'syn1','candidate_sha':'a'*40,'authorization_sha256':'b'*64,'sequence':1,'event':'TERMINAL','payload':{'canonical_receipt':{'reference':'canonical.json','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}}}).encode()+b'\n'
o.start();os.write(h.w,terminal)
end=time.monotonic()+1
while o.stdout_reader.total!=len(terminal) and time.monotonic()<end:time.sleep(.001)
assert o.stdout_reader.total==len(terminal)
start=time.monotonic();e=o.run();elapsed=time.monotonic()-start
before={'elapsed':elapsed,'stdout_finished':o.stdout_reader.finished.is_set(),'stderr_finished':o.stderr_reader.finished.is_set(),'after_child_deadline':o.clock()>o.child_deadline,'evidence':e}
assert not before['stdout_finished'] and not before['stderr_finished'] and e['archive_allowed'] and e['next_phase_allowed']
# The original readers remain alive: a late real pipe overrun materializes AFTER the success receipt.
def deliver():
 os.write(h.ew,b'l'*(s.MAX_STREAM_BYTES+1));os.close(h.ew)
t=threading.Thread(target=deliver);t.start();assert o.stderr_reader.finished.wait(2);t.join(2)
after={'stderr_overflow':o.stderr_reader.overflow,'stderr_total':o.stderr_reader.total,'live_failure':o._stream_failure(),'returned_archive_allowed':e['archive_allowed'],'returned_stream_violation':e['stream_violation']}
os.close(h.w);assert o.stdout_reader.finished.wait(2);h.stdout.close();h.stderr.close()
# Completed stream with a trailing partial frame also must not be archived.
assert after['live_failure']==s.STDERR_STREAM_LIMIT_EXCEEDED
result={'before_late_overflow':before,'after_late_overflow':after,'threads_settled_before_probe_exit':not t.is_alive() and o.stdout_reader.finished.is_set() and o.stderr_reader.finished.is_set()}
(OUT/'final-drain-observation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
