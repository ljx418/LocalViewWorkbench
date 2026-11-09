from pathlib import Path
import ast,json,hashlib,subprocess,sys,types,importlib
R=Path.cwd();sys.path.insert(0,str(R));O=R/'reports/unified-media/owner-split-c2-code-review-04/browser-lifecycle';O.mkdir(exist_ok=True);src=R/'reports/unified-media/live_checkpoint.py';before=hashlib.sha256(src.read_bytes()).hexdigest();baseline=subprocess.check_output(['git','show','4a54103aee5dc70c14001dd1d41396661683c5d2:./reports/unified-media/live_checkpoint.py'],text=True);current=src.read_text();authority=importlib.import_module('reports.unified-media.authority');program=importlib.import_module('tools.local_program_authority');rows=[]
def lifecycle_slice(text,new):
 tree=ast.parse(text);body=next(n for n in tree.body if isinstance(n,ast.Try)).body
 start=next(i for i,n in enumerate(body) if isinstance(n,ast.Assign) and ((new and 'browser lifecycle not yet proved' in ast.unparse(n)) or (not new and any(isinstance(t,ast.Name) and t.id=='node' for t in n.targets))))
 end=next(i for i in range(start,len(body)) if isinstance(body[i],ast.For) and ast.unparse(body[i].iter)=="browser['checks']")
 return compile(ast.Module(body=body[start:end],type_ignores=[]),'<source AST browser lifecycle slice>','exec')
for version,text in [('baseline',baseline),('patched',current)]:
 code=lifecycle_slice(text,version=='patched')
 for scenario in ['timeout','crash_missing_json','invalid_json','closed_false','closed_missing','closed_true']:
  out=O/(version+'-'+scenario);out.mkdir(exist_ok=True);file=out/'browser-result.json'
  if file.exists():file.unlink()
  if scenario in ['closed_false','closed_missing','closed_true']:
   body={} if scenario=='closed_missing' else {'browser_closed':scenario=='closed_true'};file.write_text(json.dumps(body))
  elif scenario=='invalid_json':file.write_text('{invalid')
  def run(*args,**kw):
   if scenario=='timeout':raise subprocess.TimeoutExpired('synthetic node command',1200)
   return types.SimpleNamespace(stdout=b'CPU synthetic stdout',stderr=b'',returncode=1 if scenario=='crash_missing_json' else 0)
  result={'decision':'NO_GO','api_listener_absent':True,'ollama_listener_absent':True,'run_root_removed':True};env={'result':result,'subprocess':types.SimpleNamespace(run=run),'SELF':src,'ROOT':R,'out':out,'json':json};error=None
  try:exec(code,env)
  except Exception as exc:error=type(exc).__name__
  # Actual final NO_GO predicate uses cleanup_error. Never execute live cleanup/process control.
  if result.get('cleanup_error'):result['decision']='NO_GO'
  events=[];old_settle=program.settle;old_close=program.close_retaining_reservation
  def settle(*args,**kwargs):events.append('settle');return {'effective_full_checkpoint':False,'actual_model_actions':0}
  def close(*args,**kwargs):events.append('close_retaining_reservation')
  program.settle=settle;program.close_retaining_reservation=close
  try:authority.terminal(out,{'run_id':'cpu-'+version+'-'+scenario,'budget_ledger':'CPU_MEMORY_STUB_NEVER_OPENED'},result)
  finally:program.settle=old_settle;program.close_retaining_reservation=old_close
  if scenario=='invalid_json':
   retained=file.with_name('browser-result.invalid-json.raw');raw_hash=hashlib.sha256(file.read_bytes()).hexdigest();file.replace(retained)
  rows.append({'version':version,'scenario':scenario,'slice_exception':error,'cleanup_error_retained':bool(result.get('cleanup_error')),'settle_called':'settle' in events,'close_retaining_reservation_called':'close_retaining_reservation' in events,'decision':result['decision'],'reservation_retained':result.get('budget_reservation_retained')})
patched=[r for r in rows if r['version']=='patched'];assert all(r['cleanup_error_retained'] and not r['settle_called'] and r['reservation_retained'] and r['decision']=='NO_GO' for r in patched if r['scenario']!='closed_true');assert next(r for r in patched if r['scenario']=='closed_true')['settle_called'];assert all(r['settle_called'] for r in rows if r['version']=='baseline');after=hashlib.sha256(src.read_bytes()).hexdigest();assert before==after
(O/'checks.json').write_text(json.dumps({'source_before_sha256':before,'source_after_sha256':after,'source_unchanged':before==after,'rows':rows,'invalid_input_extension_mapping':[{'original':str(O/(version+'-invalid_json')/'browser-result.json'),'retained':str(O/(version+'-invalid_json')/'browser-result.invalid-json.raw'),'sha256':hashlib.sha256((O/(version+'-invalid_json')/'browser-result.invalid-json.raw').read_bytes()).hexdigest(),'reason':'preserve exact invalid JSON test bytes without violating package JSON validation'} for version in ['baseline','patched']],'stubbed_boundary':'subprocess.run and budget settle/close only; no process, service, browser or real ledger touched'},indent=2)+'\n');print(json.dumps({'cases':len(rows),'patched_failure_cases_block_settlement':5,'source_unchanged':before==after,'source_sha256':before},indent=2))
