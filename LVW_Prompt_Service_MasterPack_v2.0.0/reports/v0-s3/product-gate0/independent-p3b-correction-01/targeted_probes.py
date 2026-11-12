"""Bounded independent observations. Guard is installed by run_guarded_probe first."""
import sys, runpy, json, tempfile, shutil, copy, os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT=Path(__file__).parent
owned=Path(tempfile.mkdtemp(prefix='lvw-independent-p3bc01-f4ad-probes-'))
results=[]
def prep(name,**kw):return t._prepare(owned/name,**kw)
def record(name,**v):results.append(dict(probe=name,**v))
def pin(p):
 p.directory.mkdir();p._phase_identity=p._object_identity(p.directory.lstat())
def attempt(f):
 try:return {'returned':f()}
 except Exception as e:return {'rejected':str(e),'type':type(e).__name__}
try:
 # Independently inspect and reuse the expectation-updated replay, preserving old originals.
 ns=runpy.run_path(str(ROOT/'reports/v0-s3/product-gate0/implementation-p3b-correction-01/replay_review_probes.py'),run_name='review_replay')
 try:
  replay=ns['main']()
  assert len(replay['results'])==13
  (OUT/'replayed-observations.json').write_text(json.dumps(replay,indent=2)+'\n')
 finally:
  shutil.rmtree(ns['ROOT'])
 record('replay_13',count=len(replay['results']),own_cleanup=not ns['ROOT'].exists())
 p,d,_=prep('disk');r=p.run();stored=json.loads((p.directory/'qd-receipt.json').read_bytes())
 files=[x for x in p.directory.rglob('*') if x.is_file()]
 record('persisted_receipt_totals',memory={k:r.get(k) for k in ['receipt_bytes','artifact_files','artifact_bytes','artifact_files_including_receipt','artifact_bytes_including_receipt']},disk={k:stored.get(k) for k in ['receipt_bytes','artifact_files','artifact_bytes','artifact_files_including_receipt','artifact_bytes_including_receipt']},actual_files=len(files),actual_bytes=sum(x.stat().st_size for x in files))
 scores=t._scores(r,r['projection_sha256'])
 for kind in ['PASS_cleanup_unknown','known_FAIL_storage_unknown','known_FAIL_source_unknown']:
  bad=copy.deepcopy(r)
  if kind=='PASS_cleanup_unknown':bad['rows'][0]['release_evidence']=None
  else:
   bad['rows'][0]['execution_status']='FAIL';bad['rows'][0]['error_code']='PUBLIC_EXECUTION_NOT_SUCCESSFUL'
   if 'storage' in kind:bad['storage_unproven']=True;bad['rows'][0]['storage_unproven']=True
   else:bad['rows'][0]['source_evidence']=None
  result=q.recompute_scores(bad,p.directory,scores,independence=t._independence())
  record(kind,aggregate_pass=result['aggregate_pass'],row=result['rows'][0])
 # Pinning inode of phase alone permits replacing temp by a symlink to moved original.
 p,d,_=prep('tempancestor');once=[]
 def replace_temp(action,subject):
  if action=='quality_row_begin' and not once:
   once.append(True);(p.root/'temp').rename(p.root/'old-temp');(p.root/'temp').symlink_to(p.root/'old-temp',target_is_directory=True)
 p.authorize=replace_temp;r=p.run()
 record('temp_ancestor_callback_redirect',submissions=d.submissions,decision=r['decision'],files_in_old_directory=len(list((p.root/'old-temp').rglob('*'))),receipt_in_old=(p.root/'old-temp/s3-quality/qd-receipt.json').exists())
 # Deterministic interposition at actual final open: NOFOLLOW protects leaf, not ancestors.
 p,d,_=prep('openrace');foreign=owned/'openrace-foreign';foreign.mkdir();original_open=q.os.open;swapped=[]
 def racing_open(path,flags,*a,**kw):
  target=Path(path)
  if str(target).startswith(str(p.directory/'rows')) and flags & os.O_CREAT and not swapped:
   swapped.append(True);(p.directory/'rows').rename(p.directory/'rows-original');(p.directory/'rows').symlink_to(foreign,target_is_directory=True)
   (foreign/target.relative_to(p.directory/'rows').parent).mkdir(parents=True,exist_ok=True)
  return original_open(path,flags,*a,**kw)
 q.os.open=racing_open
 try:r=p.run()
 finally:q.os.open=original_open
 record('artifact_open_ancestor_race',foreign_files=[str(x.relative_to(foreign)) for x in foreign.rglob('*') if x.is_file()],submissions=d.submissions,first_error=r['rows'][0]['error_code'])
 # Move phase before initial mkdir through an existing redirect; reject occurs after creation.
 p,d,_=prep('initialredirect');foreign=owned/'initial-foreign';foreign.mkdir();(p.root/'temp').rmdir();(p.root/'temp').symlink_to(foreign,target_is_directory=True);r=p.run()
 record('initial_temp_redirect',foreign_entries=[str(x.relative_to(foreign)) for x in foreign.rglob('*')],submissions=d.submissions,error=r.get('error_code'))
 for name,proof in [('wrong_identity',{'known':True,'action_capacity':34,'run_id':'WRONG','candidate_sha':'0'*40,'authorization_sha256':'0'*64}),('stale',{'known':True,'action_capacity':34,'issued_monotonic':-99999,'expires_monotonic':-1})]:
  p,d,_=prep('proof-'+name,parent_budget=proof);r=p.run();record('parent_proof_'+name,submissions=d.submissions,decision=r['decision'],supplied=proof)
 # No actual wait/hang: callback advances simulated monotonic past whole phase and returns.
 p,d,_=prep('callbackdeadline');events=[]
 def delayed(action,subject):
  if action=='quality_public_submit':p.clock.now+=q.PHASE_TIMEOUT_SECONDS+1;events.append('callback_returned_after_phase_deadline')
 p.authorize=delayed;r=p.run();record('post_return_elapsed_only',events=events,submissions=d.submissions,error=r['rows'][0]['error_code'],clock=p.clock.now)
 # Global monotonic evidence can decrease, while finite values pass all timing checks.
 p,d,_=prep('decreasingclock');n=[0]
 def clock():n[0]+=1;return 100000-n[0]*0.01
 p.clock=clock;r=p.run();record('decreasing_phase_clock',submissions=d.submissions,decision=r['decision'],elapsed=r.get('elapsed_seconds'))
 # Actual receipt caps: exact and one-over per artifact, total, and count including receipt.
 template={'synthetic':True,'receipt_persisted':True,'receipt_persistence_error':None,'terminal_status':'TERMINAL_RECEIPT_PERSISTED','padding':''}
 for bound in ['artifact','total','files']:
  for over in [0,1]:
   p,d,_=prep('receipt-'+bound+str(over));pin(p);doc=copy.deepcopy(template)
   if bound=='artifact':doc['padding']='x'*(q.MAX_ARTIFACT_BYTES-len(q.canonical_json(doc).encode())+over)
   if bound=='total':p._artifact_bytes=q.MAX_TOTAL_ARTIFACT_BYTES-len(q.canonical_json(doc).encode())+over
   if bound=='files':p._artifact_files=q.MAX_ARTIFACT_FILES-1+over
   ok=p._write_receipt(doc);record('receipt_'+bound+('_over' if over else '_exact'),persisted=ok,bytes=p._artifact_bytes,files=p._artifact_files,error=doc.get('receipt_persistence_error'))
finally:
 shutil.rmtree(owned)
print(json.dumps({'results':results,'owned_root':str(owned),'removed':not owned.exists(),'note':'Observations; defect observations are not product PASS; no real/native execution.'},indent=2))
