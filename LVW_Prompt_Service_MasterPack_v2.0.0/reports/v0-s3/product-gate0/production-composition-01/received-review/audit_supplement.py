"""Supplemental static/JSON audit; no candidate import."""
import ast, hashlib, json, pathlib, subprocess
P=pathlib.Path('LVW_Prompt_Service_MasterPack_v2.0.0');O=P/'reports/v0-s3/product-gate0/independent-fixture-result-05';R=pathlib.Path('/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0');G=R/'reports/v0-s3/product-gate0';C='07277a6f2f6f730dc7b9383bfeaf8c412126fe16';OLD='01453ee07b4774a55711c5cf5642c12d0394a35c'
def git(*args):return subprocess.check_output(['git',*args])
def source(f,c=C):return git('show',c+':'+str(P/f)).decode()
def write(n,d):(O/n).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
def sha(b):return hashlib.sha256(b).hexdigest()
a=json.loads((O/'recomputation.json').read_text());write('recomputation-attempt1.json',a)
outer=json.loads((G/'fixture-result-review-05/received/finite-fixture-implementation-05.outer-execution.json').read_text());a['checks']['outer_eleven_pins']=outer['source_pins_verified_before_run']==11 and all(v['expected']==v['candidate_blob']==v['materialized'] for v in json.loads((O/'source-binding.json').read_text()).values());a['audit_schema_erratum']='First audit compared integer source_pins_verified_before_run=11 to a digest map; corrected by checking count11 plus independent per-file blob/materialized hashes. No source or execution evidence changed.';a['failed']=[k for k,v in a['checks'].items() if not v];a['all_pass']=not a['failed'];write('recomputation-final.json',a)
files={'tools/test_v0_s3_supervisor.py':['run_fixture','test_the_fixture_clean_terminal_is_verified_by_the_parent','test_a_blocking_callback_is_actually_stopped','test_a_blocking_persistence_is_actually_stopped','test_a_protocol_violation_is_refused','test_a_bad_terminal_reference_is_refused'], 'tools/fixtures/v0_s3_supervisor_fixture.py':['scenario_nonfinite_number','flood_messages','flood_wire','scenario_message_flood','scenario_blocking_persistence'], 'tools/v0_s3_supervisor.py':['decode_message','_consume_stdout','run','_terminate_owned_worker'], 'tools/v0_s3_quality_worker.py':['run_worker','main'], 'reports/v0-s3/product-gate0/implementation-integration-01/executor.py':['spawn','register_child','reconcile_exited_children','close_owned_children']}
excerpts=[];oracles={}
for f,names in files.items():
 s=source(f);tree=ast.parse(s)
 for n in ast.walk(tree):
  if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name in names:
   excerpts.append(f'\n### {f}:{n.lineno} {n.name}\n\n```python\n'+ '\n'.join(s.splitlines()[n.lineno-1:n.end_lineno])+'\n```\n')
   if n.name.startswith('test_'):
    older=next(x for x in ast.walk(ast.parse(source(f,OLD))) if isinstance(x,ast.FunctionDef) and x.name==n.name)
    asserts=lambda x:[ast.dump(y,include_attributes=False) for y in ast.walk(x) if isinstance(y,ast.Assert)]
    oracles[n.name]={'old_assertions':asserts(older),'current_assertions':asserts(n),'assertions_unchanged':asserts(older)==asserts(n)}
(O/'source-path-and-oracles.md').write_text('Static exact-candidate Git object excerpts; not executed.\n'+''.join(excerpts));caps={}
for c in [OLD,C]:
 tree=ast.parse(source('tools/v0_s3_supervisor.py',c));caps[c]={n.targets[0].id:ast.dump(n.value,include_attributes=False) for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id.startswith('MAX_')}
write('oracle-comparison.json',{'old_candidate':OLD,'current_candidate':C,'oracles':oracles,'all_assertions_unchanged':all(x['assertions_unchanged'] for x in oracles.values()),'caps':caps,'caps_unchanged':caps[OLD]==caps[C]})
# Preserve provenance hashes of governance, parent records, frozen packets and prior independent audits.
inputs=['.agent-governance/README.md','plans/execution-control.json','docs/24_EXECUTION_MASTER_PLAN.md','reports/authorization-program-v1-complete-03.request.json','reports/authorization-program-v1-complete-03.approval.json']
inputs += ['reports/v0-s3/product-gate0/'+f for f in ['s3-integration-offline-contract-01.md','fixture-resume-05/operational-contract-v2.md','fixture-resume-05/budget-amendment.json','fixture-resume-05/grant.json','fixture-resume-05/execution-argv.json','fixture-resume-05/machine-binding.json','fixture-resume-05/component-decision.json','fixture-resume-05/counter-before.json','fixture-resume-05/counter-after-amendment.json','fixture-resume-05/received-review/review.md','originals-correction-04/received-review/i01-i24-audit.json','originals-correction-04/received-review/i01-i24-audit.md','integration-correction-03/received-review/i01-i24-audit.json','integration-correction-03/received-review/i01-i24-audit.md','fixture-result-review-05/terminal-intake.json','fixture-result-review-05/counter-before-terminal.json','fixture-result-review-05/counter-after-terminal.json']]
write('authority-and-prior-input-hashes.json',[{'path':str(R/f),'sha256':sha((R/f).read_bytes()),'bytes':len((R/f).read_bytes())} for f in inputs]);control=json.loads((R/'plans/execution-control.json').read_text());write('development-outline.json',control['development_outline']);write('control-summary.json',{k:control[k] for k in ['coordinate','target_version','next_delivery_target','last_passed_gate','current_blocking_gate','next_owner','next_action','required_authorization']})
# Approved CMD exception remains byte-identical to prior independent seal, normalize CRLF for candidate equivalence.
f='open_lvw_browser.cmd';b=(P/f).read_bytes();candidate=git('show',C+':'+str(P/f));write('cmd-exception.json',{'file':f,'work_sha256':sha(b),'candidate_sha256':sha(candidate),'normalized_equal':b.replace(b'\r\n',b'\n')==candidate.replace(b'\r\n',b'\n'),'executed':False})
print(json.dumps({'all_raw_checks':a['all_pass'],'checks':len(a['checks']),'oracles_unchanged':all(x['assertions_unchanged'] for x in oracles.values()),'caps_unchanged':caps[OLD]==caps[C]}))
