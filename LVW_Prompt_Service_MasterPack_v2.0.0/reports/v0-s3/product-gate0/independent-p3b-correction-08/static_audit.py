"""Read-only Git, AST and byte binding audit; imports no product/test modules."""
import ast, hashlib, json, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
PACK=OUT.parents[3]; REPO=PACK.parent
BASE='fd96cbc37574b382f483e757e8d7235ed5d2598c'; CAND='6c9a0a07c66060e53b00e690ebdd98047167511d'
def git(*args): return subprocess.run(['git',*args],cwd=REPO,check=True,stdout=subprocess.PIPE).stdout
def show(rev,path): return git('show',rev+':'+str(PACK.relative_to(REPO)/path))
def sha(raw): return hashlib.sha256(raw).hexdigest()
def read(path): return json.loads(path.read_text())
def dump(name,data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,sort_keys=True,indent=2)+'\n')
control=json.loads(show('1b93f17',Path('plans/execution-control.json')))
dump('root-current-control.json',control)
intake=json.loads(show('1b93f17',Path('reports/v0-s3/product-gate0/correction08-intake-01.json')))
dump('root-intake.json',intake)
pins=intake['source_hashes'] | {'reports/v0-s3/product-gate0/p3b-quality-contract.md':'d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3','reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json':'47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3'}
bindings={p:{'expected':h,'actual':sha((PACK/p).read_bytes()),'matches':sha((PACK/p).read_bytes())==h} for p,h in pins.items()}
def definitions(raw):
    return {n.name: n for n in ast.parse(raw).body if isinstance(n,(ast.FunctionDef,ast.ClassDef,ast.AsyncFunctionDef))}
old=definitions(show(BASE,Path('tools/test_v0_s3_quality_phase.py'))); new=definitions((PACK/'tools/test_v0_s3_quality_phase.py').read_bytes())
oldtests=[n for n in old if n.startswith('test_')]
changed=[n for n in old if n in new and ast.dump(old[n])!=ast.dump(new[n])]
missing=sorted(set(old)-set(new)); added=sorted(set(new)-set(old))
newtestaudit=[]
for name in added:
    if name.startswith('test_'):
        node=new[name]
        newtestaudit.append({'name':name,'line':node.lineno,'assertions':[ast.unparse(x.test) for x in ast.walk(node) if isinstance(x,ast.Assert)],
          'calls':sorted(set(ast.unparse(x.func) for x in ast.walk(node) if isinstance(x,ast.Call)))})
oldprod=definitions(show(BASE,Path('tools/v0_s3_quality_phase.py'))); newprod=definitions((PACK/'tools/v0_s3_quality_phase.py').read_bytes())
prodchanged=[n for n in oldprod if ast.dump(oldprod[n])!=ast.dump(newprod[n])]
impl=OUT.parent/'implementation-p3b-correction-08'
checks=[]
for line in (impl/'SHA256SUMS').read_text().splitlines():
    h,p=line.split(maxsplit=1); p=p.lstrip('*')
    options=[PACK/p, REPO/p, impl/p]
    path=next((x for x in options if x.is_file()),None)
    checks.append({'path':p,'expected':h,'actual':sha(path.read_bytes()) if path else None,'matches':path is not None and sha(path.read_bytes())==h})
history=[]
for path in sorted(impl.rglob('*.receipt.json')):
    r=read(path); streams=[]
    for stream in ('stdout','stderr'):
        declared=PACK/r[stream+'_file']; retained=path.with_name(path.name.replace('.receipt.json','.'+stream+'.log'))
        streams.append({'stream':stream,'declared':str(declared),'retained':str(retained),'sha256':sha(retained.read_bytes()),
                        'matches':sha(retained.read_bytes())==r[stream+'_sha256'] and len(retained.read_bytes())==r[stream+'_bytes']})
    history.append({'path':str(path.relative_to(PACK)), 'receipt_sha256':sha(path.read_bytes()), 'label':r['label'],
                    **{k:r.get(k) for k in ('mode','select','argv','candidate_sha_claim','candidate_sha_claim_is_attestation','exit_code','duration_seconds','before_source_sha256','after_source_sha256','runner_sha256_before','runner_sha256_after','probe_sha256_before','probe_sha256_after','imported_modules','owned_root_removed','collected_count')},'streams':streams,
                    'outer_exit':'NOT_RECORDED_IN_INNER_RECEIPT','absolute_start_end_times':'NOT_RECORDED'})
frozen=read(OUT.parent/'independent-p3b-correction-07/suite.receipt.json')['collected_nodeids']
current=read(OUT/'suite.receipt.json')['collected_nodeids']
summary={'pins':bindings,'implementation_checksums':checks,'history':history,'test_audit':{
 'original_definitions':len(oldtests),'candidate_definitions':len([n for n in new if n.startswith('test_')]),
 'old_definitions_changed':changed,'old_definitions_deleted':missing,'old_helpers_changed':[n for n in changed if not n.startswith('test_')],
 'added':added,'new_test_assertions_and_calls':newtestaudit,'frozen_cases':len(frozen),'current_cases':len(current),'missing_nodeids':sorted(set(frozen)-set(current)), 'new_nodeids':sorted(set(current)-set(frozen))},
 'product_changed_top_definitions':prodchanged,'product_added_top_definitions':sorted(set(newprod)-set(oldprod)),
 'git_identity':{'candidate':git('rev-parse',CAND).decode().strip(),'evidence':git('rev-parse','833c847').decode().strip(),'head_before_review_commit':git('rev-parse','HEAD').decode().strip(),'status':git('status','--short').decode()},
 'limitations':['Historical inner receipts bind durations, not absolute timestamps or true outer shell exits','Candidate SHA argument is a claim, actual import paths and hashes are checked separately']}
dump('static-audit.json',summary)
print(json.dumps({'pins_ok':all(x['matches'] for x in bindings.values()),'checksums_ok':all(x['matches'] for x in checks),'checksums':len(checks),'old_tests':len(oldtests),'changed':changed,'deleted':missing,'frozen':len(frozen),'current':len(current),'missing_cases':len(set(frozen)-set(current)),'new_tests':len(newtestaudit),'product_changed':prodchanged},indent=2))
