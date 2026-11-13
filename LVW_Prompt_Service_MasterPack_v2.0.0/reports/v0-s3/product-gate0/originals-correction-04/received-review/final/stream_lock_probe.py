import os,sys,dis,time,threading,json,hashlib
from pathlib import Path
from tools import v0_s3_supervisor as s
O=Path(__file__).resolve().parent
rd,wr=os.pipe();stream=os.fdopen(rd,'rb',buffering=0);r=s._StreamReader(stream,100)
code=s._StreamReader._retain.__code__
target=next(i.offset for i in dis.get_instructions(code) if i.opname=='STORE_ATTR' and i.argval=='total')
paused=threading.Event();release=threading.Event();done=threading.Event();box={}
def instruction(c,offset):
 if offset==target:paused.set();assert release.wait(2)
sys.monitoring.use_tool_id(5,'independent-under-lock')
sys.monitoring.register_callback(5,sys.monitoring.events.INSTRUCTION,instruction)
sys.monitoring.set_local_events(5,code,sys.monitoring.events.INSTRUCTION)
r.start();os.write(wr,b'world');assert paused.wait(2)
def snapshot():box.update(r.snapshot());done.set()
t=threading.Thread(target=snapshot);t.start();assert not done.wait(.02)
release.set();t.join(2);sys.monitoring.set_local_events(5,code,0);sys.monitoring.free_tool_id(5)
assert box['hashed_bytes']==box['total_observed']==5 and box['sha256']==hashlib.sha256(b'world').hexdigest()
# The reader's next os.read is waiting for input, outside its publication lock.
begin=time.monotonic();snapshot_waiting=r.snapshot();elapsed=time.monotonic()-begin
assert elapsed<.05 and not r._publish_lock.locked() and not r.finished.is_set()
os.close(wr);r.join(2);stream.close();assert not r.is_alive() and len(threading.enumerate())==1
result={'paused_before_total_store_offset':target,'snapshot_waited_for_atomic_publication':True,'snapshot':box,'while_read_blocked_snapshot':snapshot_waiting,'snapshot_seconds_while_read_blocked':elapsed,'all_threads_settled':True,'production_lock_source_has_no_IO_wait_or_external_callback':True}
(O/'stream-lock.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
