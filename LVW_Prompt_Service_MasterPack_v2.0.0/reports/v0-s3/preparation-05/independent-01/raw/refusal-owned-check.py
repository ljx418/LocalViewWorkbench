import pathlib,sys,tempfile,json,types,contextlib,io,subprocess
O=pathlib.Path(__file__).resolve().parent;P=O.parents[4];sys.path.insert(0,str(P/'tools'))
import s3_sample_preparation as s
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import video_process as runner
result={};calls=[]
old_prepare=s.prepare;old_resolve=s.resolve_source_path
s.prepare=lambda **kw:calls.append('prepare')
s.resolve_source_path=lambda *a:calls.append('resolve_source')
with tempfile.TemporaryDirectory(prefix='s3-review-refusal-') as td:
 root=pathlib.Path(td);pf=root/'preflight.json'
 args=types.SimpleNamespace(child='does-not-exist.json',candidate='a'*40,preflight=str(pf),receipt=str(root/'receipt.json'),runtime_output=str(root/'runtime'))
 for name,text in [('rejected',json.dumps({'decision':'PREFLIGHT_REJECTED'})),('malformed','{'),('candidate_drift',json.dumps({'decision':'PREFLIGHT_PASSED','candidate':{'sha':'b'*40}}))]:
  pf.write_text(text);err=io.StringIO()
  with contextlib.redirect_stderr(err):
   try:code=s.command_run(args,package_root=root);exception=None
   except Exception as exc:code=None;exception=type(exc).__name__
  result[name]={'exit':code,'exception':exception,'source_boundary_calls':list(calls),'runtime_created':(root/'runtime').exists()}
 assert not calls
 s.prepare=old_prepare;s.resolve_source_path=old_resolve
 # Actual direct child timeout/reap, no decoder/model/service.
 created=[];original=runner.subprocess.Popen
 def capture(*a,**kw):
  p=original(*a,**kw);created.append(p);return p
 runner.subprocess.Popen=capture
 try:
  try:runner.run_bounded([sys.executable,'-B','-c','import time;time.sleep(30)'],timeout_seconds=.05)
  except Exception as exc:reason=getattr(exc,'code',type(exc).__name__)
 finally:runner.subprocess.Popen=original
 result['owned_process']={'started':len(created),'terminal_returncodes':[p.poll() for p in created],'all_reaped':all(p.poll() is not None for p in created),'reason':reason,'foreign_processes_signalled':0,'purpose':'synthetic timeout of one directly owned Python sleeper; no decoder'}
result['owned_temp_absent_after']=not root.exists()
(O/'refusal-owned-check.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
