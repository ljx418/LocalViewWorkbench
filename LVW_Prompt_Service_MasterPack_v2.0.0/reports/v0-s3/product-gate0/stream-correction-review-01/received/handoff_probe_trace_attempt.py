import sys,threading,os,dis,json
from pathlib import Path
from tools import v0_s3_supervisor as s
out=Path(__file__).resolve().parent
r,w=os.pipe();stream=os.fdopen(r,'rb',buffering=0);reader=s._StreamReader(stream,s.MAX_STREAM_BYTES)
paused=threading.Event();release=threading.Event();code=s._StreamReader._retain.__code__;target=next(i.offset for i in dis.get_instructions(s._StreamReader._retain) if i.opname=='CALL');seen=[]
def trace(frame,event,arg):
 if frame.f_code is code:
  frame.f_trace_opcodes=True
  if len(seen)<40:seen.append((event,frame.f_lasti))
  if event=='opcode' and frame.f_lasti==target:
   paused.set();release.wait(3)
 return trace
def producer():
 sys.settrace(trace)
 reader.run()
worker=threading.Thread(target=producer);worker.start();raw=b'real-pipe-wire\n';os.write(w,raw)
is_paused=paused.wait(1)
first=reader.take();release.set();os.close(w);worker.join(3);second=reader.take();stream.close()
result={'target_opcode':target,'trace_events':seen,'paused':is_paused,'reader_error':reader.error,'finished':reader.finished.is_set(),'first':len(first),'second':len(second),'received':len(reader.raw()),'total':reader.total,'raw':reader.raw().decode()}
print(json.dumps(result,indent=2));(out/'handoff-observation.json').write_text(json.dumps(result,indent=2)+'\n')
