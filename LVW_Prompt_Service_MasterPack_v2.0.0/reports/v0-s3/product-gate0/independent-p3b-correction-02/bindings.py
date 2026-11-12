"""Read-only Git/static bindings; no product import or product execution."""
import ast, hashlib, json, re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];REPO=ROOT.parent;OUT=Path(__file__).parent
PREFIX=ROOT.name+'/'
CAND='9ed09513eac35636175b24a514b05d9d0c180717';EVID='18c950e6e3497c425ddb11fcbb85b75da4ded4b1';PRIOR='5894419833fb2ffab5aadb4cffc6881066befb4c'
commands=[]
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*args,raw=False):
 argv=['git',*args];r=subprocess.run(argv,cwd=REPO,capture_output=True)
 item={'argv':argv,'exit_code':r.returncode,'stdout_bytes':len(r.stdout),'stderr_bytes':len(r.stderr),'stdout_sha256':sha(r.stdout),'stderr_sha256':sha(r.stderr),'stderr':r.stderr.decode()}
 if raw:item['stdout']=r.stdout.decode()
 commands.append(item)
 if r.returncode:raise RuntimeError(item)
 return r.stdout
files=['tools/v0_s3_quality_phase.py','tools/test_v0_s3_quality_phase.py','reports/v0-s3/product-gate0/p3b-quality-contract.md','reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json','reports/v0-s3/product-gate0/p3b-correction-02.adjudication.json','reports/v0-s3/product-gate0/correction01-history-scope-disposition.json','reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py','reports/v0-s3/product-gate0/implementation-p3b/report.md','reports/v0-s3/product-gate0/implementation-p3b/SHA256SUMS','reports/v0-s3/product-gate0/implementation-p3b-correction-01/run_guarded_probe.py','reports/v0-s3/product-gate0/implementation-p3b-correction-02/run_guarded_probe.py','reports/v0-s3/product-gate0/implementation-p3b-correction-02/replay_correction01_probes.py','tools/v0_s2_driver.py','tools/v0_s2_runtime.py','tools/v0_s2_http.py','tools/v0_s2_checkpoint_oracles.py','tools/v0_s2_cancel_evidence.py','tools/v0_s2_measurements.py']
files+=list(json.loads((ROOT/'reports/v0-s3/product-gate0/independent-p3b-correction-01/production-bindings.json').read_text()))
files+=[str(x.relative_to(ROOT)) for x in sorted((ROOT/'.agent-governance/stages/V0-S3/production-quality').iterdir()) if x.is_file()]
files+=[str(x.relative_to(ROOT)) for x in sorted((ROOT/'reports/v0-s3/product-gate0/independent-p3b-correction-01').iterdir()) if x.is_file()]
results={}
for rel in files:
 actual=(ROOT/rel).read_bytes();cand=git('show',CAND+':'+PREFIX+rel);evid=git('show',EVID+':'+PREFIX+rel)
 entry={'sha256':sha(actual),'bytes':len(actual),'matches_candidate':actual==cand,'matches_evidence_head':actual==evid}
 if not rel.startswith('tools/v0_s3_quality_phase') and not rel.startswith('tools/test_v0_s3_quality_phase') and 'implementation-p3b-correction-02' not in rel and 'adjudication' not in rel and 'history-scope-disposition' not in rel:
  old=git('show',PRIOR+':'+PREFIX+rel);entry['matches_prior_review']=old==actual
 results[rel]=entry
assert results['tools/v0_s3_quality_phase.py']['sha256']=='d2c12745dcb56230175f2ac6b113dd9beac956f4e6fb0d6be598b7dcfc8db0b4'
assert results['tools/test_v0_s3_quality_phase.py']['sha256']=='a721d75ec70581d875bf22fb5f182b249e94a7bf68e0a3abc70f5a9e83fce8ab'
assert all(x['matches_candidate'] and x['matches_evidence_head'] for x in results.values())
# The restored original report/checksum are intentionally different from the prior supplied history.
history=json.loads((ROOT/'reports/v0-s3/product-gate0/correction01-history-scope-disposition.json').read_text())
for item in history['restored_files']:assert results[item['path']]['sha256']==item['restored_sha256']
# Audit preserved test functions and assertions statically, then bind to actual once-only collected IDs.
def testnodes(source):return {n.name:n for n in ast.walk(ast.parse(source)) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')}
oldsrc=git('show',PRIOR+':'+PREFIX+'tools/test_v0_s3_quality_phase.py').decode();newsrc=(ROOT/'tools/test_v0_s3_quality_phase.py').read_text();old=testnodes(oldsrc);new=testnodes(newsrc)
checks=[]
for name,n in old.items():
 nn=new[name]
 a=[ast.dump(x,include_attributes=False) for x in ast.walk(n) if isinstance(x,ast.Assert)]
 b=[ast.dump(x,include_attributes=False) for x in ast.walk(nn) if isinstance(x,ast.Assert)]
 checks.append({'test':name,'old_assert_count':len(a),'new_assert_count':len(b),'assertions_identical':a==b,'old_assertions_sha256':sha(json.dumps(a).encode()),'new_assertions_sha256':sha(json.dumps(b).encode()),'function_identical':ast.dump(n,include_attributes=False)==ast.dump(nn,include_attributes=False)})
stdout=(OUT/'suite.stdout.log').read_text();ids=re.findall(r'^tools/test_v0_s3_quality_phase.py::(\S+) PASSED',stdout,re.M)
prior_ids=[x for x in ids if x.split('[')[0] in old];newids=[x for x in ids if x.split('[')[0] not in old]
assert len(ids)==112 and len(prior_ids)==95 and len(newids)==17
newtests=sorted(set(new)-set(old));assert all(n.startswith('test_correction02_') for n in newtests)
(OUT/'test-obligation-audit.json').write_text(json.dumps({'old_function_count':len(old),'new_function_count':len(new),'preserved_collected':95,'added_collected':17,'total_collected':112,'preserved_tests':checks,'new_functions':newtests,'actual_collected_ids':ids,'note':'Assertions are compared explicitly, not presumed unchanged. Changed assertions are adjudicated in report.md.'},indent=2)+'\n')
for args in [('status','--short'),('rev-parse','HEAD'),('diff','--name-status',PRIOR,CAND),('diff','--name-status','237760b',CAND),('diff','--name-status',CAND,EVID)]:git(*args,raw=True)
coordinate=json.loads(git('show','8bb9701:'+PREFIX+'plans/execution-control.json'))
(OUT/'coordinate.json').write_text(json.dumps(coordinate,indent=2,ensure_ascii=False)+'\n')
# Earlier short-lived read-only coordinate capture is owned exclusively by this task.
tmp=Path('/tmp/lvw-p3bc02-185ef48a-coordinate-read.json');tmphash=sha(tmp.read_bytes());tmp.unlink()
(OUT/'coordinate-temp-cleanup.json').write_text(json.dumps({'path':str(tmp),'created_by':'this review shell git-show only','sha256':tmphash,'removed':not tmp.exists()})+'\n')
# Raw stream lengths/hashes and real child exits independently re-derived.
streams={}
for label in ['guard','suite','replay','focused','final-gap']:
 cmd=json.loads((OUT/(label+'.command.json')).read_text());item={'process_exit':cmd['exit_code']}
 for suffix in ['stdout.log','stderr.log','runner.stdout.log','runner.stderr.log']:
  p=OUT/(label+'.'+suffix)
  if p.exists():raw=p.read_bytes();item[suffix]={'bytes':len(raw),'sha256':sha(raw)}
 streams[label]=item
(OUT/'bindings.json').write_text(json.dumps({'candidate':CAND,'evidence':EVID,'prior_review':PRIOR,'files':results,'streams':streams,'history_restoration_intact':True},indent=2)+'\n')
(OUT/'git-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
print(json.dumps({'bindings':len(results),'tests':len(ids),'old95':len(prior_ids),'new17':len(newids),'changed_assertion_functions':[x['test'] for x in checks if not x['assertions_identical']],'new_functions':len(newtests)},indent=2))
