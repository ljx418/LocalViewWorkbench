"""Independent text/AST and evidence audit; no product/test import."""
import ast, hashlib, json, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent;PACK=OUT.parents[3];REPO=PACK.parent
rel='LVW_Prompt_Service_MasterPack_v2.0.0/tools/test_v0_s3_quality_phase.py'
baseline=subprocess.run(['git','show','5de09478a4af6e3dd91410d4dde90c9020a77bfd:'+rel],cwd=REPO,check=True,capture_output=True).stdout
current=(REPO/rel).read_bytes()
def definitions(raw):
    tree=ast.parse(raw);return {x.name:x for x in tree.body if isinstance(x,(ast.FunctionDef,ast.ClassDef))}
a=definitions(baseline);b=definitions(current)
old=[n for n in a if n.startswith('test_')];new=[n for n in b if n.startswith('test_') and n not in a]
suite=json.loads((OUT/'suite.receipt.json').read_text());prior=json.loads((OUT.parent/'independent-p3b-correction-04/suite.receipt.json').read_text())
audit={'baseline_revision':'5de09478a4af6e3dd91410d4dde90c9020a77bfd','baseline_sha256':hashlib.sha256(baseline).hexdigest(),'candidate_sha256':hashlib.sha256(current).hexdigest(),'old_definitions':len(old),'identical_old_definitions':[n for n in old if n in b and ast.dump(a[n])==ast.dump(b[n])],'changed_old_definitions':[n for n in old if n in b and ast.dump(a[n])!=ast.dump(b[n])],'deleted_old_definitions':[n for n in old if n not in b],'changed_old_helpers':[n for n in a if not n.startswith('test_') and (n not in b or ast.dump(a[n])!=ast.dump(b[n]))],'old_collected_count':prior['collected_count'],'current_collected_count':suite['collected_count'],'missing_old_nodeids':sorted(set(prior['collected_nodeids'])-set(suite['collected_nodeids'])),'new_collected_nodeids':sorted(set(suite['collected_nodeids'])-set(prior['collected_nodeids'])),'new_tests':[]}
for n in new:
    node=b[n];audit['new_tests'].append({'name':n,'line':node.lineno,'assertions':[ast.unparse(x.test) for x in ast.walk(node) if isinstance(x,ast.Assert)],'fixture_arguments':[x.arg for x in node.args.args],'calls':sorted({ast.unparse(x.func) for x in ast.walk(node) if isinstance(x,ast.Call)}),'decorators':[ast.unparse(x) for x in node.decorator_list]})
(OUT/'test-obligation-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
impl=OUT.parent/'implementation-p3b-correction-05';checks=[]
for line in (impl/'SHA256SUMS').read_text().splitlines():
    expected,path=line.split('  ',1);checks.append({'path':path,'matches':hashlib.sha256((impl/path).read_bytes()).hexdigest()==expected})
receipts=[]
for path in sorted(impl.rglob('*.receipt.json')):
    r=json.loads(path.read_text());streams=[]
    for stream in ('stdout','stderr'):
        p=PACK/r[stream+'_file'] if stream+'_file' in r else None
        retained = path.parent / (r.get('label', path.name.split('.')[0]) + '.' + stream + '.log')
        streams.append({'stream':stream,'declared_path_matches':bool(p and p.exists() and hashlib.sha256(p.read_bytes()).hexdigest()==r.get(stream+'_sha256')),'retained_path':str(retained.relative_to(impl)), 'retained_matches':retained.exists() and hashlib.sha256(retained.read_bytes()).hexdigest()==r.get(stream+'_sha256')})
    receipts.append({'path':str(path.relative_to(impl)),'exit':r.get('exit_code'),'streams':streams,'source_unchanged':r.get('source_unchanged_during_run'),'before':r.get('before_source_sha256'),'runner_before':r.get('runner_sha256_before'),'runner_after':r.get('runner_sha256_after'),'probe_before':r.get('probe_sha256_before'),'probe_after':r.get('probe_sha256_after'),'cleanup':r.get('owned_root_removed'),'imports':r.get('imported_modules')})
# Selected pins including contract/projection, product, test and immutable evidence code.
paths=['tools/v0_s3_quality_phase.py','tools/test_v0_s3_quality_phase.py','reports/v0-s3/product-gate0/p3b-quality-contract.md','reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json','reports/v0-s3/product-gate0/implementation-p3b-correction-05/run_guarded_checks.py','reports/v0-s3/product-gate0/implementation-p3b-correction-05/probe_correction05_counterexamples.py']
product=ast.parse((PACK/paths[0]).read_text());calls=[]
for node in product.body:
    if isinstance(node,ast.FunctionDef) or isinstance(node,ast.ClassDef):
        if isinstance(node,ast.ClassDef): funcs=[x for x in node.body if isinstance(x,ast.FunctionDef)]
        else:funcs=[node]
        for f in funcs:
            io=[{'line':x.lineno,'call':ast.unparse(x.func)} for x in ast.walk(f) if isinstance(x,ast.Call) and any(k in ast.unparse(x.func) for k in ('read','open','resolve','stat'))]
            if io:calls.append({'owner':(node.name+'.' if isinstance(node,ast.ClassDef) else '')+f.name,'line':f.lineno,'io':io})
payload={'checksums':checks,'implementation_receipts':receipts,'current_pins':{p:hashlib.sha256((PACK/p).read_bytes()).hexdigest() for p in paths},'reader_call_graph':calls,'root_outline_revision':'1da15dee4c1f944aed0e40bbc00eb93a536cd1b1','product_imports_performed':False}
(OUT/'static-audit.json').write_text(json.dumps(payload,indent=2)+'\n')
print(json.dumps({'old_defs':len(old),'identical':len(audit['identical_old_definitions']),'changed_helpers':audit['changed_old_helpers'],'new_defs':len(new),'new_cases':len(audit['new_collected_nodeids']),'missing':audit['missing_old_nodeids'],'checksum_entries':len(checks),'bad_checksums':[x for x in checks if not x['matches']],'implementation_exits':[(x['path'],x['exit']) for x in receipts]},indent=2))
