"""Read-only independent AST, retained evidence and source identity audit; no product imports."""
import ast,hashlib,json,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent;PACK=OUT.parents[3];REPO=PACK.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(name,value):(OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
rel='LVW_Prompt_Service_MasterPack_v2.0.0/tools/test_v0_s3_quality_phase.py'
base=subprocess.run(['git','show','44ad8c7a30ee418af41834de6cc87685f80d42fa:'+rel],cwd=REPO,capture_output=True,check=True).stdout
current=(REPO/rel).read_bytes()
def defs(raw):return {n.name:n for n in ast.parse(raw).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
a=defs(base);b=defs(current);old=[n for n in a if n.startswith('test_')];new=[n for n in b if n.startswith('test_') and n not in a]
prior=json.loads((OUT.parent/'independent-p3b-correction-05/suite.receipt.json').read_text());suite=json.loads((OUT/'suite.receipt.json').read_text())
audit={'baseline_revision':'44ad8c7a30ee418af41834de6cc87685f80d42fa','baseline_sha256':hashlib.sha256(base).hexdigest(),'candidate_sha256':hashlib.sha256(current).hexdigest(),'old_definitions':len(old),'identical_old_definitions':[n for n in old if n in b and ast.dump(a[n])==ast.dump(b[n])],'changed_old_definitions':[n for n in old if n in b and ast.dump(a[n])!=ast.dump(b[n])],'deleted_old_definitions':[n for n in old if n not in b],'changed_old_helpers':[n for n in a if not n.startswith('test_') and (n not in b or ast.dump(a[n])!=ast.dump(b[n]))],'old_collected_count':prior['collected_count'],'current_collected_count':suite['collected_count'],'missing_old_nodeids':sorted(set(prior['collected_nodeids'])-set(suite['collected_nodeids'])),'new_collected_nodeids':sorted(set(suite['collected_nodeids'])-set(prior['collected_nodeids'])),'new_tests':[]}
for n in new:
 node=b[n];audit['new_tests'].append({'name':n,'line':node.lineno,'assertions':[ast.unparse(x.test) for x in ast.walk(node) if isinstance(x,ast.Assert)],'fixture_arguments':[x.arg for x in node.args.args],'calls':sorted({ast.unparse(x.func) for x in ast.walk(node) if isinstance(x,ast.Call)}),'decorators':[ast.unparse(x) for x in node.decorator_list]})
write('test-obligation-audit.json',audit)
impl=OUT.parent/'implementation-p3b-correction-06';checks=[]
for line in (impl/'SHA256SUMS').read_text().splitlines():
 expected,path=line.split('  ',1);checks.append({'path':path,'expected':expected,'actual':sha(REPO/path),'matches':sha(REPO/path)==expected})
receipts=[]
for path in sorted(impl.rglob('*.receipt.json')):
 r=json.loads(path.read_text());streams=[]
 for stream in ('stdout','stderr'):
  declared=PACK/r[stream+'_file'] if stream+'_file' in r else None
  retained=path.with_name(path.name.replace('.receipt.json','.'+stream+'.log'))
  streams.append({'stream':stream,'declared_path':str(declared),'declared_path_matches':bool(declared and declared.exists() and sha(declared)==r.get(stream+'_sha256')),'retained_path':str(retained.relative_to(PACK)),'retained_matches':retained.exists() and sha(retained)==r.get(stream+'_sha256')})
 receipts.append({'path':str(path.relative_to(PACK)),'exit':r.get('exit_code'),'streams':streams,'source_unchanged':r.get('source_unchanged_during_run'),'before':r.get('before_source_sha256'),'after':r.get('after_source_sha256'),'runner_before':r.get('runner_sha256_before'),'runner_after':r.get('runner_sha256_after'),'probe_before':r.get('probe_sha256_before'),'probe_after':r.get('probe_sha256_after'),'cleanup':r.get('owned_root_removed'),'imports':r.get('imported_modules')})
paths=['tools/v0_s3_quality_phase.py','tools/test_v0_s3_quality_phase.py','reports/v0-s3/product-gate0/p3b-quality-contract.md','reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json','reports/v0-s3/product-gate0/implementation-p3b-correction-05/run_guarded_checks.py','reports/v0-s3/product-gate0/implementation-p3b-correction-06/probe_correction06_counterexamples.py']
product=ast.parse((PACK/paths[0]).read_text());callers=[]
for n in ast.walk(product):
 if isinstance(n,ast.FunctionDef):
  hits=[x.lineno for x in ast.walk(n) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='_json_fact_equal']
  if hits:callers.append({'function':n.name,'line':n.lineno,'typed_equality_call_lines':hits})
write('static-audit.json',{'checksums':checks,'implementation_receipts':receipts,'current_pins':{p:sha(PACK/p) for p in paths},'typed_equality_all_callers':callers,'root_outline_revision':'08caf9f0e93ff7ff5acee7783c730346fc3c2c9c','product_imports_performed':False})
print(json.dumps({'old_defs':len(old),'identical':len(audit['identical_old_definitions']),'changed':audit['changed_old_definitions'],'deleted':audit['deleted_old_definitions'],'changed_helpers':audit['changed_old_helpers'],'new_defs':len(new),'new_cases':len(audit['new_collected_nodeids']),'missing_nodeids':audit['missing_old_nodeids'],'checksums':len(checks),'mismatches':[x for x in checks if not x['matches']],'retained_streams_mismatch':[r['path'] for r in receipts if any(not s['retained_matches'] for s in r['streams'])],'implementation_exits':[(r['path'],r['exit']) for r in receipts]},indent=2))
