"""Run the actual worker/QualityPhase in process and validate every emitted frame."""
import json,io,collections
from pathlib import Path
from tools import test_v0_s3_supervisor as t
from tools import v0_s3_supervisor as s
from tools.v0_s3_quality_worker import WorkerContext,ProtocolWriter,run_worker
O=Path(__file__).resolve().parent
temp=O/'worker-sequence-validated';temp.mkdir();root=temp/'run'
clock=t._p3b.FakeClock(step=0.0)
context_path,rows=t.build_worker_context(temp,root,clock=clock)
rows=[dict(row,ordinal=index+1) for index,row in enumerate(rows)]
context=WorkerContext.load(context_path)
state=s.ProtocolState(run_id=context.run_id,candidate_sha=context.candidate_sha,authorization_sha256=context.authorization_sha256,plan=s.SealedPlan(rows))
events=[];stream=io.BytesIO();writer=ProtocolWriter(stream,run_id=context.run_id,candidate_sha=context.candidate_sha,authorization_sha256=context.authorization_sha256)
def emit(event,payload):
 message=writer.emit(event,payload)
 state.accept(s.decode_message((s.canonical_json(message)+'\n').encode()))
 events.append(message)
driver=t._p3b.SyntheticDriver(root,None)
receipt=run_worker(context,driver=driver,emit=emit,clock=clock,sleep=clock.sleep)
counts=collections.Counter(m['event'] for m in events)
assert counts=={'STARTED':1,'ROW_STARTED':16,'HISTORY_WAIT_STARTED':16,'ROW_FINISHED':16,'PROGRESS':16,'TERMINAL':1}
assert len(state.rows_finished)==16 and state.terminal is not None
for row in rows:
 seq=[m['event'] for m in events if m['payload'].get('asset_id')==row['asset_id']]
 assert seq==['ROW_STARTED','HISTORY_WAIT_STARTED','ROW_FINISHED']
result={'all_actual_emissions_accepted':True,'counts':dict(counts),'message_count':state.count,'row_order':'ROW_STARTED -> HISTORY_WAIT_STARTED -> ROW_FINISHED; PROGRESS after each row','actual_QualityPhase_synthetic_driver':True,'native_quality_set':'NOT_PROVEN','stage_pass_claim':False,'events':events}
(O/'worker-sequence.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='events'},indent=2))
