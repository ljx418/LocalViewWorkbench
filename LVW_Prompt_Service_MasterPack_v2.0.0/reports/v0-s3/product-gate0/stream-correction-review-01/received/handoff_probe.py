import sys,threading,os,dis,json
from pathlib import Path
from tools import v0_s3_supervisor as s
out=Path(__file__).resolve().parent
r,w=os.pipe();stream=os.fdopen(r,'rb',buffering=0);reader=s._StreamReader(stream,s.MAX_STREAM_BYTES)
paused=threading.Event();release=threading.Event();code=s._StreamReader._retain.__code__;target=next(i.offset for i in dis.get_instructions(s._StreamReader._retain) if i.opname=='CALL');seen=[]
def instruction(code_object,offset):
 if len(seen)<40:seen.append(offset)
 if offset==target:
  paused.set();release.wait(3)
sys.monitoring.use_tool_id(5,'independent-handoff-schedule')
sys.monitoring.register_callback(5,sys.monitoring.events.INSTRUCTION,instruction)
sys.monitoring.set_local_events(5,code,sys.monitoring.events.INSTRUCTION)
def producer():reader.run()
worker=threading.Thread(target=producer);worker.start();raw=s.canonical_json({'schema':s.PROTOCOL_SCHEMA,'run_id':'syn1','candidate_sha':'a'*40,'authorization_sha256':'b'*64,'sequence':1,'event':'STARTED','payload':{}}).encode()+b'\n';os.write(w,raw)
is_paused=paused.wait(1)
first=reader.take();release.set();os.close(w);worker.join(3);second=reader.take();stream.close()
sys.monitoring.set_local_events(5,code,0);sys.monitoring.free_tool_id(5)
plan=s.SealedPlan([{'ordinal':i,'asset_id':'I%02d'%i,'media_kind':'image'} for i in range(1,17)])
parent=s.ParentSupervisor(command=['fake-no-spawn'],run_id='syn1',candidate_sha='a'*40,authorization_sha256='b'*64,plan=plan,root=out)
parent.stdout_reader=reader;parent._consume_stdout()
result={'parent_message_count':parent.state.count,'expected_message_count':1,'target_opcode':target,'trace_events':seen,'paused':is_paused,'reader_error':reader.error,'finished':reader.finished.is_set(),'first':len(first),'second':len(second),'received':len(reader.raw()),'total':reader.total,'raw':reader.raw().decode()}
print(json.dumps(result,indent=2));(out/'handoff-observation.json').write_text(json.dumps(result,indent=2)+'\n')
