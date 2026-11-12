"""Read-only Git/source/evidence bindings; never executes candidate code."""
import hashlib,json,subprocess
from pathlib import Path
R=Path(__file__).resolve().parent; ROOT=R.parents[3]; PREFIX=ROOT.name+'/'
C='00b63d97e8a860ea1bf4759b04da0cf8045423a7'; B='ae4dbc48ec4c58d09f7df460ced4bad68a91275d'
def sha(b):return hashlib.sha256(b).hexdigest()
def git(name,args,save=True):
 cmd=['git',*args];p=subprocess.run(cmd,cwd=ROOT.parent,capture_output=True)
 if save:
  (R/'raw'/f'{name}.command.json').write_text(json.dumps({'argv':cmd,'cwd':str(ROOT.parent)})+'\n')
  for suffix,data in [('stdout.log',p.stdout),('stderr.log',p.stderr),('exit.log',f'{p.returncode}\n'.encode())]:(R/'raw'/f'{name}.{suffix}').write_bytes(data)
 assert p.returncode==0,p.stderr
 return p.stdout
def blob(c,n):return git('blob',['show',c+':'+PREFIX+n],False)
changed=['tools/v0_s3_stage_runtime.py','tools/test_s3_install_handoff.py']
sources=[{'path':n,'sha256':sha((ROOT/n).read_bytes()),'candidate_blob_sha256':sha(blob(C,n))} for n in changed]
assert all(x['sha256']==x['candidate_blob_sha256'] for x in sources)
git('candidate-changes',['diff','--name-status',B,C])
assert not git('tracked-worktree',['diff','HEAD','--',PREFIX])
# All preexisting paths except the two explicitly authorized implementation files are immutable.
changes=git('immutable-boundaries',['diff','--name-only',B,'HEAD']).decode().splitlines()
assert all(p in [PREFIX+n for n in changed] or p.startswith(PREFIX+'reports/v0-s3/product-gate0/implementation-p3a-correction-04/') for p in changes),changes
assert (ROOT/changed[1]).read_bytes().startswith(blob(B,changed[1]))
checks=[]
for suffix in ['implementation-p3a-correction-04','independent-p3a-correction-03','independent-p3a-correction-02','independent-p3a-correction-01']:
 d=ROOT/'reports/v0-s3/product-gate0'/suffix
 for line in (d/'SHA256SUMS').read_text().splitlines():
  expected,name=line.split(None,1);p=d/name.strip();actual=sha(p.read_bytes());assert actual==expected,str(p)
  checks.append({'path':str(p.relative_to(ROOT)),'sha256':actual})
reuse=[]
for label,count,ref,prior,code in [
 ('owner',17,'5497bd1860ae895f394ece23a1ddb5e0b22fad92','independent-p3a-correction-01',['tools/v0_incremental_package.py','tools/test_v0_incremental_package.py']),
 ('archive',9,'e3f9427f17c38def9216813842195b94b490698f','independent-p3a-correction-03',['tools/v0_s2_stage_archive.py','tools/v0_s2_execution_bindings.py','tools/v0_s2_checkpoint_oracles.py','LVW_V0_RuntimePatch/tests/test_s2_stage_archive.py'])]:
 item={'kind':label,'reused_checks':count,'fresh_checks':0,'source_commit':ref,'sources':[],'evidence':[]}
 for n in code:
  raw=(ROOT/n).read_bytes();old=blob(ref,n);assert raw==old
  item['sources'].append({'path':n,'prior_sha256':sha(old),'current_sha256':sha(raw),'identical':True})
 d=ROOT/'reports/v0-s3/product-gate0'/prior
 for n in [f'raw/{label}.command.json',f'raw/{label}.stdout.log',f'raw/{label}.stderr.log',f'raw/{label}.exit.log',f'raw/{label}-guard.json','receipt.json','guarded_checks.py']:
  p=d/n;item['evidence'].append({'path':str(p.relative_to(ROOT)),'sha256':sha(p.read_bytes())})
 item['dependency_scope']=('Direct in-process package owner main/parser tests do not call S3 factory; unchanged owner and tests.' if label=='owner' else 'Standalone OwnedArchive tests and its bindings/oracles unchanged; only owner-internal regression reused, new S3 wrapper integration is proved separately by fresh targeted and post tests.')
 reuse.append(item)
unchanged=[]
for n in ['tools/v0_s2_stage_runtime.py','tools/v0_s2_stage_archive.py','tools/v0_incremental_package.py','tools/v0_s2_stage_sequence.py']:
 raw=(ROOT/n).read_bytes();assert raw==blob(B,n);unchanged.append({'path':n,'sha256':sha(raw),'unchanged_from_contract':True})
coordraw=blob('e718c87','plans/execution-control.json');coord=json.loads(coordraw)
(R/'raw/coordinate-extract.json').write_text(json.dumps({k:coord[k] for k in ['coordinate','development_outline','current_blocking_gate','last_passed_gate']},ensure_ascii=False,indent=2)+'\n')
history=[]
impl=ROOT/'reports/v0-s3/product-gate0/implementation-p3a-correction-04/raw'
for p in sorted(impl.glob('*.stdout.log')):
 exitfile=p.with_name(p.name.replace('.stdout.log','.exit.log'))
 if exitfile.exists():history.append({'path':str(p.relative_to(ROOT)),'last_line':p.read_text().splitlines()[-1:] ,'exit':int(exitfile.read_text())})
result={'candidate':C,'contract':B,'sources':sources,'immutable_boundaries':True,'unchanged_owners':unchanged,'old_test_prefix_unchanged':True,'checksums_verified':checks,'reused_not_fresh':reuse,'coordinate_sha256':sha(coordraw),'implementation_history':history}
(R/'raw/binding-recomputation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'source_files':len(sources),'checksum_entries':len(checks),'immutable':True,'reused_not_fresh':26,'history':history},indent=2))
