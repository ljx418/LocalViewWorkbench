"""Final-candidate read-only binding and legacy-seam comparison."""
import ast
import copy
import hashlib
import json
from pathlib import Path
import subprocess

R=Path(__file__).resolve().parent; ROOT=R.parents[3]; PREFIX=ROOT.name+'/'
C='e3f9427f17c38def9216813842195b94b490698f'; B='9aa110251c018ecaaefe4870b8047ef504bbc2de'
def sha(raw): return hashlib.sha256(raw).hexdigest()
def git(name,args,save=True):
    cmd=['git',*args]; p=subprocess.run(cmd,cwd=ROOT.parent,capture_output=True)
    if save:
        (R/'raw'/f'{name}.command.json').write_text(json.dumps({'argv':cmd,'cwd':str(ROOT.parent)})+'\n')
        (R/'raw'/f'{name}.stdout.log').write_bytes(p.stdout); (R/'raw'/f'{name}.stderr.log').write_bytes(p.stderr)
        (R/'raw'/f'{name}.exit.log').write_text(str(p.returncode)+'\n')
    assert p.returncode==0,p.stderr
    return p.stdout
def blob(commit,name): return git('blob',['show',commit+':'+PREFIX+name],False)
impl=ROOT/'reports/v0-s3/product-gate0/implementation-p3a-correction-03'
receipt=json.loads((impl/'receipt.json').read_text())
sources=[{'path':name,'actual_sha256':sha((ROOT/name).read_bytes()),'candidate_blob_sha256':sha(blob(C,name))} for name in receipt['changed_source_files']]
hashes=[]
for suffix in ('implementation-p3a-correction-03','independent-p3a-correction-02','independent-p3a-correction-01'):
    directory=ROOT/'reports/v0-s3/product-gate0'/suffix
    for line in (directory/'SHA256SUMS').read_text().splitlines():
        expected,name=line.split(None,1); p=directory/name.strip()
        hashes.append({'path':str(p.relative_to(ROOT)),'expected':expected,'actual':sha(p.read_bytes())})
git('candidate-changes',['diff','--name-status',B,C])
assert not git('candidate-worktree',['diff',C,'--',*[PREFIX+x for x in receipt['changed_source_files']]])
immutable=['tools/v0_incremental_package.py','tools/test_v0_incremental_package.py',
 'LVW_V0_RuntimePatch/tests/test_s3_installed_runtime.py','LVW_V0_RuntimePatch/tests/test_s2_stage_runtime.py',
 'LVW_V0_RuntimePatch/tests/test_s2_browser_component.py','LVW_V0_RuntimePatch/tests/test_s2_stage_archive.py',
 'reports/v0-s3/product-gate0/independent-p3a','reports/v0-s3/product-gate0/independent-p3a-correction-01',
 'reports/v0-s3/product-gate0/independent-p3a-correction-02',
 'reports/v0-s3/product-gate0/implementation-p3a','reports/v0-s3/product-gate0/implementation-p3a-correction-01',
 'reports/v0-s3/product-gate0/implementation-p3a-correction-02',
 'reports/v0-s3/product-gate0/p3-installed-runtime.contract.md','reports/v0-s3/product-gate0/p3a-correction-03.contract.md',
 'AGENTS.md','.agent-governance/README.md','docs/24_EXECUTION_MASTER_PLAN.md']
assert not git('immutable-boundaries',['diff',B,'HEAD','--',*[PREFIX+n for n in immutable]])
handoff='tools/test_s3_install_handoff.py'
assert (ROOT/handoff).read_bytes().startswith(blob(B,handoff)), 'existing tests must be unchanged prefix'
def methods(raw,cls):
    tree=ast.parse(raw); node=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
    return {n.name:n for n in node.body if isinstance(n,ast.FunctionDef)}
old=methods(blob(B,'tools/v0_s2_stage_runtime.py'),'StageRuntimeFactory')
new=methods((ROOT/'tools/v0_s2_stage_runtime.py').read_bytes(),'StageRuntimeFactory')
old_prepare=old['_prepare']; old_try=next(n for n in old_prepare.body if isinstance(n,ast.Try))
root_alloc=next(n for n in old_prepare.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='root' for t in n.targets))
directory_loop=old_try.body[1]
evidence_write=old_try.body[-2]
class Normalize(ast.NodeTransformer):
    def visit_Expr(self,node):
        if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and isinstance(node.value.func.value,ast.Name) and node.value.func.value.id=='self':
            name=node.value.func.attr
            if name=='_preparation_boundary': return None
            if name=='_prepare_directories': return copy.deepcopy(directory_loop)
            if name=='_persist_preparation_evidence': return copy.deepcopy(evidence_write)
        return self.generic_visit(node)
    def visit_Assign(self,node):
        if isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and node.value.func.attr=='_allocate_preparation_root': return copy.deepcopy(root_alloc)
        return self.generic_visit(node)
normalized=Normalize().visit(copy.deepcopy(new['_prepare']))
seams_equal=ast.dump(normalized)==ast.dump(old_prepare)
base_changed=[n for n in old if ast.dump(old[n])!=ast.dump(new[n])]
oa=methods(blob(B,'tools/v0_s2_stage_archive.py'),'OwnedArchive'); na=methods((ROOT/'tools/v0_s2_stage_archive.py').read_bytes(),'OwnedArchive')
archive_changed=[n for n in oa if ast.dump(oa[n])!=ast.dump(na[n])]
prior=ROOT/'reports/v0-s3/product-gate0/independent-p3a-correction-01'
reuse={'count':17,'fresh_count':0,'independent_commit':'e9c910e881572691449dc70da569abee0dc4b195','source':[],'evidence':[],
 'dependency_reason':'Selected owner tests use unchanged package main/parser/install/rollback in process; no StageRuntimeFactory or OwnedArchive dependency.'}
for name in ('tools/v0_incremental_package.py','tools/test_v0_incremental_package.py'):
    old_raw=blob('5497bd1860ae895f394ece23a1ddb5e0b22fad92',name); current=(ROOT/name).read_bytes()
    reuse['source'].append({'path':name,'prior_sha256':sha(old_raw),'current_sha256':sha(current),'byte_identical':old_raw==current})
for name in ('raw/owner.command.json','raw/owner.stdout.log','raw/owner.stderr.log','raw/owner.exit.log','raw/owner-guard.json','receipt.json','guarded_checks.py'):
    p=prior/name; reuse['evidence'].append({'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())})
(R/'raw/owner17-reuse.json').write_text(json.dumps(reuse,indent=2)+'\n')
coord_raw=blob('e28b660','plans/execution-control.json'); coord=json.loads(coord_raw)
(R/'raw/coordinate-extract.json').write_text(json.dumps({k:coord[k] for k in ('coordinate','development_outline','current_blocking_gate','last_passed_gate')},indent=2,ensure_ascii=False)+'\n')
history=[]
for p in sorted((impl/'raw').glob('*.stdout.log')):
    if p.name.split('-')[0] in ('audit','targeted','regression','archive','probes','gap','cleanup'):
        lines=p.read_text().splitlines()
        history.append({'run':p.name,'last_line':lines[-1] if lines else '', 'exit':int(p.with_name(p.name.replace('.stdout.log','.exit.log')).read_text())})
result={'sources':sources,'checksums':hashes,'all_match':all(v['actual_sha256']==v['candidate_blob_sha256'] for v in sources) and all(v['expected']==v['actual'] for v in hashes),
 'base_changed_existing_methods':base_changed,'normalized_default_prepare_equal':seams_equal,'archive_changed_existing_methods':archive_changed,
 'prior_handoff_tests_prefix_unchanged':True,'coordinate_sha256':sha(coord_raw),'historical_results':history}
(R/'raw/binding-recomputation.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['all_match'] and seams_equal and base_changed==['_prepare'] and archive_changed==['register']
assert all(x['byte_identical'] for x in reuse['source'])
print(json.dumps({'source_blobs':len(sources),'checksum_entries':len(hashes),'all_match':True,'normalized_default_prepare_equal':seams_equal,'archive_existing_changed':archive_changed,'reuse_not_fresh':17,'history':history},indent=2))
