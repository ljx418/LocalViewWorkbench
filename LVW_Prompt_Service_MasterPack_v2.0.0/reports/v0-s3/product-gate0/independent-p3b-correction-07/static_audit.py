"""Read-only Git/source AST/retained byte identity audit; no product imports."""
import ast, hashlib, json, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
PACK=OUT.parents[3]
REPO=PACK.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
commands=[]
def show(rev, path):
    command=['git','show',rev+':LVW_Prompt_Service_MasterPack_v2.0.0/'+path]
    result=subprocess.run(command,cwd=REPO,capture_output=True,check=True)
    commands.append(dict(command=command,exit_code=result.returncode))
    return result.stdout
baseline='ba34b1581fc5e8e8b4de6ba469484e8eae416da1'
test='tools/test_v0_s3_quality_phase.py'
before=show(baseline,test); current=(PACK/test).read_bytes()
def definitions(raw):
    return {n.name:n for n in ast.parse(raw).body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
a,b=definitions(before),definitions(current)
old=[n for n in a if n.startswith('test_')]
new=[n for n in b if n.startswith('test_') and n not in a]
prior=json.loads((OUT.parent/'independent-p3b-correction-06/suite.receipt.json').read_text())
suite=json.loads((OUT/'suite.receipt.json').read_text())
audit=dict(baseline_revision=baseline,baseline_sha256=hashlib.sha256(before).hexdigest(),candidate_sha256=hashlib.sha256(current).hexdigest(),
 old_definitions=len(old),identical_old_definitions=[n for n in old if n in b and ast.dump(a[n])==ast.dump(b[n])],
 changed_old_definitions=[n for n in old if n in b and ast.dump(a[n])!=ast.dump(b[n])],deleted_old_definitions=[n for n in old if n not in b],
 changed_old_helpers=[n for n in a if not n.startswith('test_') and (n not in b or ast.dump(a[n])!=ast.dump(b[n]))],
 old_collected_count=prior['collected_count'],current_collected_count=suite['collected_count'],
 missing_old_nodeids=sorted(set(prior['collected_nodeids'])-set(suite['collected_nodeids'])),new_collected_nodeids=sorted(set(suite['collected_nodeids'])-set(prior['collected_nodeids'])),new_tests=[])
for name in new:
    node=b[name]
    audit['new_tests'].append(dict(name=name,line=node.lineno,assertions=[ast.unparse(x.test) for x in ast.walk(node) if isinstance(x,ast.Assert)],calls=sorted({ast.unparse(x.func) for x in ast.walk(node) if isinstance(x,ast.Call)}),decorators=[ast.unparse(x) for x in node.decorator_list]))
(OUT/'test-obligation-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
impl=OUT.parent/'implementation-p3b-correction-07'
checks=[]
for line in (impl/'SHA256SUMS').read_text().splitlines():
    expected,path=line.split('  ',1)
    checks.append(dict(path=path,expected=expected,actual=sha(REPO/path),matches=sha(REPO/path)==expected))
history=[]
for path in sorted(impl.rglob('*.receipt.json')):
    r=json.loads(path.read_text())
    streams=[]
    for stream in ('stdout','stderr'):
        retained=path.with_name(path.name.replace('.receipt.json','.'+stream+'.log'))
        declared=PACK/r[stream+'_file']
        streams.append(dict(stream=stream,retained_path=str(retained.relative_to(PACK)),declared_path=r[stream+'_file'],retained_matches=retained.exists() and sha(retained)==r[stream+'_sha256'],declared_matches=declared.exists() and sha(declared)==r[stream+'_sha256']))
    history.append(dict(path=str(path.relative_to(PACK)),exit_code=r['exit_code'],streams=streams,before=r['before_source_sha256'],after=r['after_source_sha256'],runner_before=r['runner_sha256_before'],runner_after=r['runner_sha256_after'],probe_before=r['probe_sha256_before'],probe_after=r['probe_sha256_after'],imports=r['imported_modules'],cleanup=r['owned_root_removed']))
product='tools/v0_s3_quality_phase.py'
before_product=definitions(show(baseline,product)); after_product=definitions((PACK/product).read_bytes())
unchanged=[n for n in before_product if n in after_product and ast.dump(before_product[n])==ast.dump(after_product[n])]
changed=[n for n in before_product if n in after_product and ast.dump(before_product[n])!=ast.dump(after_product[n])]
qtree=ast.parse((PACK/product).read_text())
callers=[]
for n in ast.walk(qtree):
    if isinstance(n,ast.FunctionDef):
        hits=[x.lineno for x in ast.walk(n) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name) and x.func.id=='_json_fact_equal']
        if hits: callers.append(dict(function=n.name,line=n.lineno,typed_equality_call_lines=hits))
pins=[product,test,'reports/v0-s3/product-gate0/p3b-quality-contract.md','reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json','reports/v0-s3/product-gate0/implementation-p3b-correction-05/run_guarded_checks.py','reports/v0-s3/product-gate0/implementation-p3b-correction-07/probe_correction07_counterexamples.py']
result=dict(checksums=checks,implementation_receipts=history,current_pins={p:sha(PACK/p) for p in pins},unchanged_product_definitions=unchanged,changed_product_definitions=changed,typed_equality_callers=callers,git_commands=commands,product_imports_performed=False)
(OUT/'static-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(old_definitions=len(old),identical=len(audit['identical_old_definitions']),changed=audit['changed_old_definitions'],deleted=audit['deleted_old_definitions'],changed_helpers=audit['changed_old_helpers'],new_definitions=len(new),missing_nodeids=audit['missing_old_nodeids'],checksums=len(checks),mismatches=[c for c in checks if not c['matches']],retained_stream_mismatches=[r['path'] for r in history if any(not s['retained_matches'] for s in r['streams'])],history_exits=[(r['path'],r['exit_code']) for r in history]),indent=2))
