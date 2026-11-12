"""Read-only Git and text artifact binding checks; no product imports."""
import ast,hashlib,json,subprocess,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]; OUT=Path(__file__).parent; PREFIX=ROOT.name+'/'
commands=[]
def git(*args):
 cmd=['git',*args];p=subprocess.run(cmd,cwd=ROOT,capture_output=True);commands.append({'argv':cmd,'exit_code':p.returncode,'stdout_sha256':sha(p.stdout),'stdout_bytes':len(p.stdout),'stdout':p.stdout.decode() if args[0]!='show' else '<blob omitted: no copied source/prelabels retained>','stderr':p.stderr.decode()});assert p.returncode==0,p.stderr;return p.stdout
def sha(raw):return hashlib.sha256(raw).hexdigest()
base='0c7d27b436abb81042e6ef160ef663ff3e1c4d22'; cand='376ea9283cb7096c2fc35f6eab561919c07b6d1f'; ev='e16274256509078f6a94182196539eb7a43a5dc5'
result={'candidate':cand,'evidence':ev,'head':git('rev-parse','HEAD').decode().strip()}
for commit in [base,cand,ev,'e2294724463efcab1a202a25563f76a24eea798f']:
 git('merge-base','--is-ancestor',commit,'HEAD')
paths=['tools/v0_s3_quality_phase.py','tools/test_v0_s3_quality_phase.py','reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py','reports/v0-s3/product-gate0/implementation-p3b-correction-01/run_guarded_probe.py','reports/v0-s3/product-gate0/implementation-p3b-correction-01/replay_review_probes.py','reports/v0-s3/product-gate0/p3b-quality-contract.md','reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json','reports/v0-s3/preparation-05/quality-set.frozen.json','tools/v0_s2_driver.py','tools/v0_s2_runtime.py','tools/v0_s2_http.py']
result['files']={}
for path in paths:
 raw=(ROOT/path).read_bytes(); result['files'][path]={'sha256':sha(raw),'bytes':len(raw),'matches_candidate':raw==git('show',cand+':'+PREFIX+path),'matches_evidence':raw==git('show',ev+':'+PREFIX+path)}
packet=ROOT/'.agent-governance/stages/V0-S3/production-quality'
result['packet']={}
for line in (packet/'PAYLOAD_MANIFEST.sha256').read_text().splitlines():
 digest,path=line.split(maxsplit=1);raw=(packet/path).read_bytes(); result['packet'][path]={'sha256':sha(raw),'manifest_matches':sha(raw)==digest,'unchanged_from_base':raw==git('show',base+':'+PREFIX+str((packet/path).relative_to(ROOT)))}
result['candidate_changes']=git('diff','--name-status',base,cand).decode()
result['final_evidence_changes']=git('diff','--name-status',cand,ev).decode()
old=ast.parse(git('show',base+':'+PREFIX+'tools/test_v0_s3_quality_phase.py'))
new=ast.parse((ROOT/'tools/test_v0_s3_quality_phase.py').read_text())
oldtests={n.name:ast.dump(n) for n in old.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
newtests={n.name:ast.dump(n) for n in new.body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')}
result['test_obligations']={'original_function_count':len(oldtests),'new_function_count':len(newtests),'removed':sorted(oldtests.keys()-newtests.keys()),'added':sorted(newtests.keys()-oldtests.keys()),'changed_existing':sorted(k for k in oldtests if oldtests[k]!=newtests.get(k))}
result['evidence_hashes']={}
for receiptname in ['correction-directed','full-final','review-probe-replay']:
 folder=ROOT/'reports/v0-s3/product-gate0/implementation-p3b-correction-01';r=json.loads((folder/(receiptname+'.receipt.json')).read_text());checks={}
 for stream in ['stdout','stderr']:
  raw=(ROOT/r[stream+'_file']).read_bytes();checks[stream]={'hash_matches':sha(raw)==r[stream+'_sha256'],'bytes_match':len(raw)==r[stream+'_bytes'],'sha256':sha(raw),'bytes':len(raw)}
 result['evidence_hashes'][receiptname]={'exit_code':r['exit_code'],'streams':checks}
for foldername in ['implementation-p3b-correction-01']:
 folder=ROOT/'reports/v0-s3/product-gate0'/foldername
 entries={}
 for line in (folder/'SHA256SUMS').read_text().splitlines():
  digest,path=line.split(maxsplit=1);path=path.lstrip('*');f=folder/path
  if not f.exists():f=ROOT/path
  entries[path]={'exists':f.exists(),'matches':f.exists() and sha(f.read_bytes())==digest}
 result['implementation_SHA256SUMS']=entries
coord=json.loads(git('show','b1a9386:'+PREFIX+'plans/execution-control.json'));result['current_root_outline']={k:coord[k] for k in ['development_outline','current_stage'] if k in coord}
result['local_outline']={k:v for k,v in json.loads((ROOT/'plans/execution-control.json').read_text()).items() if k in ['development_outline','current_stage']}
root=json.loads((OUT/'owned-suite-root.json').read_text())['path'];p=Path(root);assert p.name.startswith('lvw-independent-p3bc01-f4ad-suite-') and p.parent==Path('/tmp');shutil.rmtree(p);result['cleanup']={'owned_suite_root':root,'removed':not p.exists(),'other_pytest_roots_scanned_or_deleted':False}
(OUT/'binding-results.json').write_text(json.dumps(result,indent=2)+'\n');(OUT/'git-commands.json').write_text(json.dumps(commands,indent=2)+'\n')
print(json.dumps({'tests':result['test_obligations'],'packet_all_match':all(x['manifest_matches'] and x['unchanged_from_base'] for x in result['packet'].values()),'sumchecks':result['implementation_SHA256SUMS'],'outline':result['current_root_outline']},indent=2))
