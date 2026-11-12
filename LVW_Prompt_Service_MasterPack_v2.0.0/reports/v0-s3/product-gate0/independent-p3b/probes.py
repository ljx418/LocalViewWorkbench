"""Independent synthetic counterexamples; launch only via audit_runner.py probes."""
import copy, json, tempfile, shutil
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
out=[]
root=Path(tempfile.mkdtemp(prefix='lvw-independent-p3b-probes-139573-'))
def record(name, **values):out.append(dict(probe=name,**values))
def prep(name):return t._prepare(root/name)
def brief(r):return {k:r.get(k) for k in ('decision','public_submissions','provider_calls_reserved','test_counts','storage_unproven','receipt_persisted')}
try:
 p,d,_=prep('baseline');r=p.run();scores=t._scores(r,r['projection_sha256']);ar=p.directory
 record('baseline',**brief(r))
 ind=t._independence(reviewers=[{'reviewer_id':'A','session_id':'SA','role':'INDEPENDENT_REVIEWER'},{'reviewer_id':'B','session_id':'SB','role':'INDEPENDENT_REVIEWER'}])
 ss=copy.deepcopy(scores)
 for s in ss:s.update(reviewer_id='A',session_id='SB')
 rr=q.recompute_scores(r,ar,ss,independence=ind)
 record('cross_paired_reviewer_session',aggregate_pass=rr['aggregate_pass'])
 bad=copy.deepcopy(r);bad['rows'][0]['raw_bytes']+=123
 rr=q.recompute_scores(bad,ar,scores,independence=t._independence())
 record('execution_raw_length_mismatch',aggregate_pass=rr['aggregate_pass'],declared=bad['rows'][0]['raw_bytes'],actual=rr['rows'][0]['raw_bytes'])
 bad=copy.deepcopy(r);bad['rows'][0]['execution_status']='FAIL';ss=copy.deepcopy(scores);ss[0]['critical_hallucinations']=3
 rr=q.recompute_scores(bad,ar,ss,independence=t._independence())
 record('failed_row_critical_evidence',aggregate_pass=rr['aggregate_pass'],thresholds=rr['thresholds'],row=rr['rows'][0])
 ss[0]['critical_hallucinations']=0
 rr=q.recompute_scores(bad,ar,ss,independence=t._independence())
 record('known_failed_independently_scored',aggregate_pass=rr['aggregate_pass'],thresholds_met=rr['thresholds_met'],all_rows_resolved=rr['all_rows_resolved'])
 p,d,_=prep('writefail');original=p._artifact
 def failraw(relative, raw):
  if relative.endswith('/raw.txt'):raise q.QualityContractError('ARTIFACT_WRITE_FAILED:'+relative)
  return original(relative,raw)
 p._artifact=failraw;rr=p.run();record('raw_persistence_failure',**brief(rr),first_error=rr['rows'][0]['error_code'],raw_preserved=[x.get('raw_preserved') for x in rr['rows']])
 p,d,_=prep('sourcecallback');before=d.submit;sent=[]
 def auth(action,asset):
  if action=='quality_public_submit' and not sent:
   f=p.root/'input/synthetic-image-00.png';f.write_bytes(t._tiny_png(9))
 def submit(g):sent.append(g);return before(g)
 p.authorize=auth;d.submit=submit;rr=p.run();record('source_mutation_in_authorize',**brief(rr),first_error=rr['rows'][0]['error_code'],sent=len(sent))
 p,d,_=prep('submitfailure')
 def badsubmit(graph):d.submissions+=1;raise RuntimeError('synthetic transport failure after reservation')
 d.submit=badsubmit;rr=p.run();record('failed_submit_counter',**brief(rr),driver_attempts=d.submissions)
 p,d,_=prep('residueexception')
 def badresidue():raise OSError('synthetic inaccessible snapshot root')
 d.video_snapshot_residue=badresidue
 try:rr=p.run();record('residue_exception',returned=True,**brief(rr))
 except Exception as e:record('residue_exception',returned=False,error=type(e).__name__,receipt=p.receipt,submissions=d.submissions)
 p,d,_=prep('receipttotal');p.directory.mkdir();p._artifact_bytes=q.MAX_TOTAL_ARTIFACT_BYTES
 ok=p._write_receipt({'synthetic':True});record('receipt_total_cap',persisted=ok,cap=q.MAX_TOTAL_ARTIFACT_BYTES,actual_accounted=p._artifact_bytes)
 p,d,_=prep('ancestorredirect');p.directory.mkdir();outside=root/'redirect-target';outside.mkdir();(p.directory/'rows').symlink_to(outside,target_is_directory=True)
 try:p._artifact('rows/asset/raw.txt',b'synthetic');record('artifact_ancestor_redirect',escaped=(outside/'asset/raw.txt').exists())
 except Exception as e:record('artifact_ancestor_redirect',error=str(e))
 p,d,_=prep('nanrelease');old=d.release_preload
 def nanrelease(*a):v=old(*a);v['elapsed_seconds']=float('nan');v['gpu_samples'][1]['monotonic_seconds']=float('nan');return v
 d.release_preload=nanrelease
 try:ev=p._release_evidence({'asset_id':'probe'});record('nonfinite_release',accepted=ev['proven'])
 except Exception as e:record('nonfinite_release',error=str(e))
finally:
 shutil.rmtree(root)
print(json.dumps({'kind':'INDEPENDENT_SYNTHETIC_PROBES','results':out,'owned_fixture_root':str(root),'own_fixture_cleanup':not root.exists(),'real_execution':False},ensure_ascii=False,indent=2))
