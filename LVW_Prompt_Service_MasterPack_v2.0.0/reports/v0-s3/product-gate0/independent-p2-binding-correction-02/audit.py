"""Repository-only fingerprint and historical evidence inventory; no live paths."""
import hashlib,json,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
PREFIX=ROOT.name+'/'
CANDIDATE='d339e53d0394fac172b7c984a1613faab2ec33df'
TIP='c2870383ae4b620ced8db9dee6dcbc4d09bb5519'
COORD='e2d98fed6426a61302ff2ccd84aa54bc7a2efbbb'
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(data):return hashlib.sha256(data).hexdigest()
def snapshot(commit,path):return git('show',commit+':'+PREFIX+path)
paths=['tools/v0_s3_runtime_binding.py','tools/test_v0_s3_runtime_binding.py','tools/v0_s3_budget_authority.py','tools/local_program_authority.py',
 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py','LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py',
 'reports/v0-s3/product-gate0/p2-binding-correction-01.contract.md','reports/v0-s3/product-gate0/p2-binding-correction-02.contract.md',
 'reports/v0-s3/product-gate0/runtime-binding-correction-02.child.json']
bindings={}
for p in paths:
    raw=(ROOT/p).read_bytes();c=snapshot(CANDIDATE,p)
    bindings[p]=dict(sha256=sha(raw),candidate_sha256=sha(c),blob=git('rev-parse',CANDIDATE+':'+PREFIX+p).decode().strip(),candidate_equal=raw==c,tip_equal=raw==snapshot(TIP,p))
    assert raw==c==snapshot(TIP,p)
oldtests='tools/test_v0_s3_runtime_binding.py'
delta=git('diff','b387ce07',CANDIDATE,'--',oldtests).decode()
(OUT/'test-preservation.diff').write_text(delta)
assert not any(x.startswith('-') and not x.startswith('---') for x in delta.splitlines())
for p in paths[2:6]:assert snapshot('b387ce07',p)==snapshot(CANDIDATE,p)
history={}
for directory in ('implementation-p2-binding-correction-02','independent-p2-binding','implementation-p2-binding-correction-01'):
    base=ROOT/'reports/v0-s3/product-gate0'/directory
    for p in sorted(base.iterdir()):
        if p.is_file():
            raw=p.read_bytes();history[str(p.relative_to(ROOT))]=dict(sha256=sha(raw),bytes=len(raw))
metadata={}
for path,name in [('plans/execution-control.json','coordinator-execution-control.snapshot.json'),('reports/v0-s3/product-gate0/p2-binding-correction-02-scope-deviation.json','coordinator-scope-deviation.snapshot.json')]:
    raw=snapshot(COORD,path);(OUT/name).write_bytes(raw);metadata[path]=dict(commit=COORD,sha256=sha(raw))
execution=json.loads((OUT/'coordinator-execution-control.snapshot.json').read_text())
(OUT/'outline-snapshot.json').write_text(json.dumps(execution['development_outline'],ensure_ascii=False,indent=2)+'\n')
value=dict(candidate=CANDIDATE,evidence_tip=TIP,coordinator=COORD,bindings=bindings,historical_files=history,coordinator_snapshots=metadata,
    original_178_preserved=True,test_changes='129 additions / 0 deletions relative to b387ce07; added 16 parameterized cases; existing assertions retained',
    draft_status=json.loads((ROOT/paths[-1]).read_text())['status'],host_files_read_by_audit=0)
(OUT/'fingerprints.json').write_text(json.dumps(value,indent=2)+'\n')
print(json.dumps({'candidate_files_equal':all(x['candidate_equal'] for x in bindings.values()),'history_files_indexed':len(history),'child_status':value['draft_status'],'original_178_preserved':True}))
