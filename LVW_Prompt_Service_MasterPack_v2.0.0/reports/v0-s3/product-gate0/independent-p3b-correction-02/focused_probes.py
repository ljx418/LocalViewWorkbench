"""Bounded independent gap probes; observations are not product PASS tests."""
import copy, hashlib, json, os, shutil, tempfile
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT=Path(__file__).parent
owned=Path(tempfile.mkdtemp(prefix='lvw-independent-p3bc02-185ef48a-focused-'))
(OUT/'owned-focused-root.json').write_text(json.dumps({'path':str(owned),'owner':'task_185ef48a77aa'})+'\n')
results=[]
def record(name,**v):results.append(dict(probe=name,**v))
def prepare(name,**kw):return t._prepare(owned/name,**kw)
def observe(name,fn):
 try:record(name,actual=fn())
 except Exception as e:record(name,rejected=type(e).__name__,detail=str(e))
def pad_to(p,doc,target):
 doc['padding']=''
 for _ in range(8):
  raw,_=p._serialized_receipt(doc)
  delta=target-len(raw)
  if delta==0:return raw
  n=len(doc['padding'])+delta
  if n<0:raise AssertionError(('negative padding',target,len(raw)))
  doc['padding']='x'*n
 raise AssertionError('bounded padding did not converge')
try:
 p,d,_=prepare('qs-baseline');r=p.run();scores=t._scores(r,r['projection_sha256'])
 record('baseline_exact_disk_receipt',memory_equals_disk=r==json.loads((p.directory/'qd-receipt.json').read_bytes()),canonical_bytes_equal=q.canonical_json(r).encode()==(p.directory/'qd-receipt.json').read_bytes(),files_closed=all(x is None for x in [p._owned_root,p._owned_temp,p._owned_phase]))
 # Missing or null uncertainty declarations must not imply known storage/cleanup.
 for name in ['storage_flag_missing','storage_flag_null','cleanup_flag_missing','source_identity_missing','source_path_foreign','release_details_missing']:
  def qs_probe(name=name):
   bad=copy.deepcopy(r);row=bad['rows'][0]
   if name=='storage_flag_missing':bad.pop('storage_unproven')
   elif name=='storage_flag_null':bad['storage_unproven']=None
   elif name=='cleanup_flag_missing':bad.pop('cleanup_unproven')
   elif name=='source_identity_missing':row['source_evidence'].pop('identity')
   elif name=='source_path_foreign':row['source_evidence']['path']='/foreign/not-the-bound-input'
   else:row['release_evidence']={'proven':True,'model_inventory_empty':True}
   result=q.recompute_scores(bad,p.directory,scores,independence=t._independence())
   return {'aggregate_pass':result['aggregate_pass'],'row':result['rows'][0]}
  observe(name,qs_probe)
 bad=copy.deepcopy(r);bad['rows'][0]['execution_status']='FAIL';bad['rows'][0]['error_code']='PUBLIC_EXECUTION_NOT_SUCCESSFUL'
 sc=copy.deepcopy(scores);sc[0]['critical_hallucinations']=3
 result=q.recompute_scores(bad,p.directory,sc,independence=t._independence())
 record('known_failed_critical3',aggregate_pass=result['aggregate_pass'],row=result['rows'][0],thresholds=result['thresholds'])
 # Initially valid proof expires during the short authorized callback before first send.
 for name in ['proof_expires_before_first_send','proof_diminishes_before_first_send']:
  local,driver,_=prepare(name);events=[]
  def authorize(action,subject):
   if action=='quality_public_submit' and not events:
    if name=='proof_expires_before_first_send':local.clock.now=local.parent_budget['expires_monotonic'];local.parent_budget['expires_monotonic']=local.clock.now
    else:local.parent_budget['action_capacity']=0
    events.append({'at':action,'clock':local.clock.now,'proof':copy.deepcopy(local.parent_budget)})
  # Expiry is two seconds away, callback consumes two seconds (under 30s).
  if name=='proof_expires_before_first_send':local.parent_budget['expires_monotonic']=2.0
  local.authorize=authorize
  rr=local.run();record(name,events=events,submissions=driver.submissions,decision=rr['decision'],rows=len(rr['rows']),counts=rr['test_counts'],error=rr.get('error_code'))
 # Real frozen limits, actual owned disk accounting rather than monkeypatched caps.
 for bound in ['artifact','total','files']:
  for over in [0,1]:
   local,driver,_=prepare('actual-cap-'+bound+str(over));local._open_owned_directories()
   try:
    doc={'synthetic':True,'receipt_persisted':True,'receipt_persistence_error':None,'terminal_status':'TERMINAL_RECEIPT_PERSISTED'}
    if bound=='artifact':pad_to(local,doc,q.MAX_ARTIFACT_BYTES+over)
    elif bound=='total':
     for i in range(15):local._artifact('fill-%02d.bin'%i,b'x'*q.MAX_ARTIFACT_BYTES)
     local._artifact('fill-15.bin',b'x'*(q.MAX_ARTIFACT_BYTES-1024))
     pad_to(local,doc,1024+over)
    else:
     for i in range(q.MAX_ARTIFACT_FILES-1+over):local._artifact('fill-%03d.txt'%i,b'')
    raw,_=local._serialized_receipt(doc);before=local._artifact_bytes
    ok=local._write_receipt(doc);files=[f for f in local.directory.rglob('*') if f.is_file()]
    stored=json.loads((local.directory/'qd-receipt.json').read_bytes()) if (local.directory/'qd-receipt.json').exists() else None
    record('actual_'+bound+('_over' if over else '_exact'),persisted=ok,target_receipt_bytes=len(raw),prior_bytes=before,disk_bytes=sum(f.stat().st_size for f in files),disk_files=len(files),stored_equals_returned=stored==doc if stored else None,error=doc.get('receipt_persistence_error'),limits=[q.MAX_ARTIFACT_BYTES,q.MAX_TOTAL_ARTIFACT_BYTES,q.MAX_ARTIFACT_FILES])
   finally:local._close_owned_directories();shutil.rmtree(local.root)
 # Receipt replay must preserve old bytes; fsync failure must not certify persistence.
 local,driver,_=prepare('receipt-failure');local._open_owned_directories()
 try:
  doc={'synthetic':True};original_fsync=q.os.fsync
  def fail_fsync(fd):raise OSError('independent injected receipt fsync failure')
  q.os.fsync=fail_fsync
  try:ok=local._write_receipt(doc)
  finally:q.os.fsync=original_fsync
  path=local.directory/'qd-receipt.json';raw=path.read_bytes();stored=json.loads(raw)
  retry={'retry':True};retryok=local._write_receipt(retry)
  record('receipt_fsync_failure',returned_persisted=ok,memory=doc,disk_persisted=stored.get('receipt_persisted'),disk_terminal=stored.get('terminal_status'),disk_bytes=len(raw),disk_hash=hashlib.sha256(raw).hexdigest(),retry_persisted=retryok,retry_error=retry.get('receipt_persistence_error'),original_bytes_unchanged=path.read_bytes()==raw)
 finally:local._close_owned_directories()
 # Final receipt open has the same descriptor-relative no-follow confinement.
 local,driver,_=prepare('receipt-open-swap');foreign=owned/'receipt-foreign';foreign.mkdir();local._open_owned_directories();original_open=q.os.open;events=[]
 def opening(path,flags,*args,**kwargs):
  if str(path)=='qd-receipt.json' and flags&os.O_CREAT and not events:
   events.append(True);local.directory.rename(local.root/'temp/old-phase');local.directory.symlink_to(foreign,target_is_directory=True)
  return original_open(path,flags,*args,**kwargs)
 q.os.open=opening
 try:
  doc={'synthetic':True};ok=local._write_receipt(doc)
 finally:q.os.open=original_open;local._close_owned_directories()
 record('receipt_final_open_ancestor_swap',triggered=bool(events),persisted=ok,foreign_entries=[str(x.relative_to(foreign)) for x in foreign.rglob('*')],owned_old_files=[str(x.relative_to(local.root/'temp/old-phase')) for x in (local.root/'temp/old-phase').rglob('*')],handles_closed=local._owned_root is None)
finally:
 shutil.rmtree(owned)
print(json.dumps({'results':results,'owned_root':str(owned),'removed':not owned.exists(),'classification':'observations only; no product tests or real execution'},indent=2))
