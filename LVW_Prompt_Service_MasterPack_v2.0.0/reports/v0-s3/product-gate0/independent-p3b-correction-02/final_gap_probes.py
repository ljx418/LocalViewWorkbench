"""Last bounded timing and real terminal-error-path observations; no hung calls."""
import json, tempfile, shutil, os
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT=Path(__file__).parent
owned=Path(tempfile.mkdtemp(prefix='lvw-independent-p3bc02-185ef48a-lastgap-'))
(OUT/'owned-final-gap-root.json').write_text(json.dumps({'path':str(owned),'owner':'task_185ef48a77aa'})+'\n')
rows=[]
try:
 # Simulated preparatory work ends just inside deadline; callback returns two seconds later.
 p,d,_=t._prepare(owned/'phase-deadline');p.parent_budget['expires_monotonic']=20000.0
 load=p._load_workflows
 def load_near_deadline():
  result=load();p.clock.now=10799.0;return result
 p._load_workflows=load_near_deadline
 events=[]
 def authorize(action,subject):
  if action=='quality_public_submit':p.clock.now+=2.0;events.append({'action':action,'returned_at':p.clock.now,'phase_deadline':p._phase_deadline})
 p.authorize=authorize;r=p.run()
 rows.append({'probe':'cooperative_phase_deadline_before_send','events':events,'submissions':d.submissions,'first_error':r['rows'][0]['error_code'],'decision':r['decision'],'counts':r['test_counts'],'hard_timing_blocker':r['hard_timing_blocker']})
 # Inject fsync failure only for the final receipt FD in actual QualityPhase.run.
 p,d,_=t._prepare(owned/'actual-run-fsync');original_open=q.os.open;original_fsync=q.os.fsync;receiptfd=[]
 def opening(path,flags,*a,**kw):
  fd=original_open(path,flags,*a,**kw)
  if str(path)=='qd-receipt.json' and flags&os.O_CREAT:receiptfd.append(fd)
  return fd
 def sync(fd):
  if receiptfd and fd==receiptfd[-1]:raise OSError('independent final receipt fsync failure')
  return original_fsync(fd)
 q.os.open=opening;q.os.fsync=sync
 try:r=p.run()
 finally:q.os.open=original_open;q.os.fsync=original_fsync
 stored=json.loads((p.directory/'qd-receipt.json').read_bytes())
 rows.append({'probe':'actual_run_receipt_fsync_failure','trigger_reached':bool(receiptfd),'submissions':d.submissions,'returned':{k:r.get(k) for k in ['decision','receipt_persisted','terminal_status','storage_unproven','error_code']},'disk':{k:stored.get(k) for k in ['decision','receipt_persisted','terminal_status','storage_unproven','error_code']},'handles_closed':all(x is None for x in [p._owned_root,p._owned_temp,p._owned_phase])})
 for name,value in [('nonfinite',float('nan')),('boolean',True)]:
  p,d,_=t._prepare(owned/('clock-'+name));p.clock=lambda:value;r=p.run()
  rows.append({'probe':'clock_'+name,'submissions':d.submissions,'rows':len(r['rows']),'error':r['error_code']})
finally:shutil.rmtree(owned)
print(json.dumps({'results':rows,'owned_root':str(owned),'removed':not owned.exists(),'classification':'counterexample observations; not product passing tests'},indent=2))
