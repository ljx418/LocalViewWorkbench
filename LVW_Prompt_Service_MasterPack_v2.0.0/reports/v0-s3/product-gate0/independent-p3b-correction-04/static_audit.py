"""Text/AST and Git read-only audit, no executable product imports."""
import ast, hashlib, json, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
PACK=OUT.parents[3]
PREFIX=PACK.name+'/'
def git(*args): return subprocess.check_output(['git',*args])
def old(path): return git('show','0d5c023:'+PREFIX+path).decode()
path='tools/test_v0_s3_quality_phase.py'
prior=old(path); current=(PACK/path).read_text()
def funcs(raw):
    tree=ast.parse(raw)
    return {n.name: ast.dump(n,include_attributes=False) for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))}
a,b=funcs(prior),funcs(current)
changed=[k for k in a if a[k]!=b.get(k)]
checks=[]
E=OUT.parent/'implementation-p3b-correction-04'
for line in (E/'SHA256SUMS').read_text().splitlines():
    sha,p=line.split(None,1); p=p.strip(); data=(E/p).read_bytes()
    checks.append({'path':p,'expected':sha,'actual':hashlib.sha256(data).hexdigest(),'matches':hashlib.sha256(data).hexdigest()==sha})
receipts=[]
for p in sorted(E.rglob('*.receipt.json')):
    d=json.loads(p.read_text()); receipts.append({'path':str(p.relative_to(E)), 'exit':d.get('exit_code'),'guard':d.get('guard'),'source_unchanged':d.get('source_unchanged_during_run'),'before':d.get('before_source_sha256'),'after':d.get('after_source_sha256'),'imports':d.get('imported_modules'),'command':d.get('command')})
control=json.loads(git('show','67d5c87:'+PREFIX+'plans/execution-control.json'))
(OUT/'root-current-control.json').write_text(json.dumps(control,ensure_ascii=False,indent=2)+'\n')
files=['tools/v0_s3_quality_phase.py',path,'reports/v0-s3/product-gate0/p3b-quality-contract.md','reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json','reports/v0-s3/product-gate0/implementation-p3b-correction-04/run_guarded_checks.py']
bindings=[]
for f in files:
    raw=(PACK/f).read_bytes(); candidate=git('show','5de09478:'+PREFIX+f)
    bindings.append({'path':f,'working_sha256':hashlib.sha256(raw).hexdigest(),'candidate_sha256':hashlib.sha256(candidate).hexdigest(),'matches':raw==candidate})
report={'changed_prior_definitions':changed,'removed_prior_definitions':sorted(set(a)-set(b)),'new_definitions':sorted(set(b)-set(a)),'prior_test_functions':sum(k.startswith('test_') for k in a),'current_test_functions':sum(k.startswith('test_') for k in b),'checksum_entries':checks,'implementation_attempts':receipts,'bindings':bindings,'head':git('rev-parse','HEAD').decode().strip(),'root_task_commit':git('rev-parse','67d5c87').decode().strip()}
(OUT/'static-audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'changed':changed,'removed':report['removed_prior_definitions'],'checksums':len(checks),'checksums_match':all(x['matches'] for x in checks),'bindings_match':all(x['matches'] for x in bindings),'attempts':[(x['path'],x['exit']) for x in receipts]},indent=2))
