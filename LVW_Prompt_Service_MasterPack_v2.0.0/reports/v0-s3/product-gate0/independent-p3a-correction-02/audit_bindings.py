"""Recompute correction02 bindings and narrowly justify owner17 evidence reuse."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess

R = Path(__file__).resolve().parent
ROOT = R.parents[3]
PREFIX = ROOT.name + '/'
C = 'db607d484e9627b8be8b27d581d9d174ea4a9e63'
B = '1a553726c67c35a0c82aab54d409eb9abcb4ff45'
OLD = '5497bd1860ae895f394ece23a1ddb5e0b22fad92'
def digest(raw): return hashlib.sha256(raw).hexdigest()
def git(name, args, save=True):
    cmd = ['git', *args]
    p = subprocess.run(cmd, cwd=ROOT.parent, capture_output=True)
    if save:
        (R/'raw'/f'{name}.command.json').write_text(json.dumps({'argv':cmd,'cwd':str(ROOT.parent)})+'\n')
        (R/'raw'/f'{name}.stdout.log').write_bytes(p.stdout)
        (R/'raw'/f'{name}.stderr.log').write_bytes(p.stderr)
        (R/'raw'/f'{name}.exit.log').write_text(str(p.returncode)+'\n')
    assert p.returncode == 0, p.stderr
    return p.stdout
def blob(commit, name): return git('blob', ['show', commit+':'+PREFIX+name], False)

impl=ROOT/'reports/v0-s3/product-gate0/implementation-p3a-correction-02'
receipt=json.loads((impl/'receipt.json').read_text())
sources=[]
for name, expected in receipt['source_sha256'].items():
    actual=digest((ROOT/name).read_bytes())
    sources.append({'path':name,'expected':expected,'actual':actual,'candidate_blob':digest(blob(C,name))})
hashes=[]
for directory in (impl, ROOT/'reports/v0-s3/product-gate0/independent-p3a-correction-01'):
    for line in (directory/'SHA256SUMS').read_text().splitlines():
        expected,name=line.split(None,1); path=directory/name.strip()
        hashes.append({'path':str(path.relative_to(ROOT)),'expected':expected,'actual':digest(path.read_bytes())})
git('changes', ['diff','--name-status',B,C])
git('source-worktree', ['diff',C,'--',*[PREFIX+n for n in receipt['source_sha256']]])
immutable=['tools/v0_incremental_package.py','tools/test_v0_incremental_package.py',
 'LVW_V0_RuntimePatch/tests/test_s3_installed_runtime.py',
 'LVW_V0_RuntimePatch/tests/test_s2_stage_runtime.py','LVW_V0_RuntimePatch/tests/test_s2_browser_component.py',
 'reports/v0-s3/product-gate0/independent-p3a','reports/v0-s3/product-gate0/independent-p3a-correction-01',
 'reports/v0-s3/product-gate0/implementation-p3a','reports/v0-s3/product-gate0/implementation-p3a-correction-01',
 'reports/v0-s3/product-gate0/p3-installed-runtime.contract.md','reports/v0-s3/product-gate0/p3a-correction-02.contract.md',
 'AGENTS.md','.agent-governance/README.md','docs/24_EXECUTION_MASTER_PLAN.md']
assert not git('immutable-boundaries',['diff',B,'HEAD','--',*[PREFIX+n for n in immutable]])
reuse_source=[]
for name in ('tools/v0_incremental_package.py','tools/test_v0_incremental_package.py'):
    raw=(ROOT/name).read_bytes(); old=blob(OLD,name)
    reuse_source.append({'path':name,'old_candidate_sha256':digest(old),'current_sha256':digest(raw),'byte_identical':raw==old})
reuse=[]
prior=ROOT/'reports/v0-s3/product-gate0/independent-p3a-correction-01'
for name in ('raw/owner.command.json','raw/owner.stdout.log','raw/owner.stderr.log','raw/owner.exit.log','raw/owner-guard.json','receipt.json','guarded_checks.py'):
    p=prior/name
    reuse.append({'path':str(p.relative_to(ROOT)),'sha256':digest(p.read_bytes())})
owner17={'reused_count':17,'fresh_count':0,'independent_commit':'e9c910e881572691449dc70da569abee0dc4b195',
 'source':reuse_source,'evidence':reuse,'justification':'Pure selected default installer/rollback owner cases import unchanged package; base/subclass lifecycle changes are not invoked by their in-process CLI adapter; original assertions/test file unchanged.'}
(R/'raw/owner17-reuse.json').write_text(json.dumps(owner17,indent=2)+'\n')
def methods(raw):
    tree=ast.parse(raw); cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='StageRuntimeFactory')
    return {n.name:n for n in cls.body if isinstance(n,ast.FunctionDef)}
old=methods(blob(B,'tools/v0_s2_stage_runtime.py')); new=methods((ROOT/'tools/v0_s2_stage_runtime.py').read_bytes())
changed=[n for n in old if ast.dump(old[n])!=ast.dump(new[n])]
old_handler=old['_prepare'].body[-1].handlers[0]
new_handler=new['_prepare'].body[-1].handlers[0]
old_handler.body[-3:-1]=new_handler.body[-2:-1]
seam_only=ast.dump(old['_prepare'])==ast.dump(new['_prepare'])
coord_raw=blob('abe960a','plans/execution-control.json'); coord=json.loads(coord_raw)
(R/'raw/coordinate-extract.json').write_text(json.dumps({k:coord[k] for k in ('coordinate','development_outline','last_passed_gate','current_blocking_gate')},indent=2,ensure_ascii=False)+'\n')
history=[]
for p in sorted((impl/'raw').glob('*.stdout.log')):
    if p.name.split('-')[0] in ('targeted','regression','probes'):
        history.append({'run':p.name,'summary':p.read_text().splitlines()[-1],
            'exit':int(p.with_name(p.name.replace('.stdout.log','.exit.log')).read_text())})
result={'sources':sources,'checksum_entries':hashes,'all_match':all(x['expected']==x['actual'] for x in sources+hashes) and all(x['actual']==x['candidate_blob'] for x in sources),
 'changed_existing_base_methods':changed,'base_prepare_change_only_failure_hook':seam_only,'coordinate_sha256':digest(coord_raw),'historical_raw':history}
(R/'raw/binding-recomputation.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['all_match'] and seam_only and changed==['_prepare'] and all(x['byte_identical'] for x in reuse_source)
print(json.dumps({'sources':len(sources),'checksums':len(hashes),'all_match':result['all_match'],'seam_only':seam_only,'reused_owner':17,'fresh_owner':0,'historical':history,'coordinate':coord['coordinate']},indent=2))
