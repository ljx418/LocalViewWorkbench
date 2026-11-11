from pathlib import Path
import ast,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[4];OUT=Path(__file__).resolve().parent;P=ROOT/'reports/v0-s3/product-gate0';E=P/'implementation-p2-binding'
sha=lambda b:hashlib.sha256(b).hexdigest()
base='7e33e6112d9df330ef4385773e41072a7c2f5469';candidate='34de7b54a529a8947d63736c6f1bd345828cad57';tip='210fb1e130ac749e9537bda895472b7a3b5101f9'
def gitfile(commit,path):return subprocess.check_output(['git','show',commit+':'+ROOT.name+'/'+path],cwd=ROOT)
def function(data,name):
 text=data.decode();n=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name==name)
 return '\n'.join(text.splitlines()[n.lineno-1:n.end_lineno]).encode()
pre=json.loads((E/'preflight.json').read_text());files={}
for path in list(pre['source_hashes'])+['tools/test_v0_s3_runtime_binding.py','tools/test_v0_s3_budget_authority.py','LVW_V0_RuntimePatch/tests/test_s3_program_budget.py']:
 raw=(ROOT/path).read_bytes();files[path]={'sha256':sha(raw),'bytes':len(raw),'candidate_equal':raw==gitfile(candidate,path),'tip_equal':raw==gitfile(tip,path)}
protocol='LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py'
unchanged={}
for name in ['authorize_model_action','decode']:
 a=function(gitfile(base,protocol),name);b=function((ROOT/protocol).read_bytes(),name)
 unchanged[name]={'byte_identical_to_P1':a==b,'sha256':sha(b)}
manifest=json.loads((E/'evidence-hashes.json').read_text());evidence={}
for p in sorted(E.iterdir()):
 raw=p.read_bytes()
 if p.suffix=='.json':json.loads(raw)
 evidence[p.name]={'bytes':len(raw),'sha256':sha(raw),'manifest_matches':manifest.get(p.name)==sha(raw) if p.name in manifest else None}
life=json.loads((E/'cross-os-lifecycle.json').read_text());fixture=Path(life['binding']['authority_root'])
# Only metadata of explicitly registered retained fixture tree; no current PID sampling, import or transaction.
tree=[]
if fixture.is_dir():
 for p in fixture.rglob('*'):
  if p.is_file():tree.append({'relative_path':str(p.relative_to(fixture)),'bytes':p.stat().st_size})
  if len(tree)>128:raise ValueError('fixture listing bound')
bound=7*2*1048576+3*2*32768+sum(x['bytes'] for x in tree)+sum(x['bytes'] for x in evidence.values())
result={'candidate':candidate,'evidence_tip':tip,'root':base,'sources':files,'P1_functions':unchanged,'evidence':evidence,'retained_fixture_metadata':tree,'retained_fixture_bytes':sum(x['bytes'] for x in tree),'committed_evidence_bytes':sum(x['bytes'] for x in evidence.values()),'output_conservative_bytes':bound,'output_limit':16777216,'output_bound_explanation':'7 outer commands x 2 x 1MiB plus 3 inner exchanges x 2 x 32768 plus all retained fixture files and committed evidence, deliberately double-counting captured logs; source metadata hashed 169955221 is input, not output','owned_process_upper_bound':28,'process_derivation':'13 fixed owned command/shim launches + 3 conservative native counterparts for Linux interop PIDs + 1 batch owner + 2 run Git children + 3 preflight owner/Git + 6 earlier zero-access preflight/run owner/Git; not OS service census','old_fixture_mutated':False,'current_pid_observations':0}
(OUT/'fingerprints.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['sources','evidence','retained_fixture_metadata']},ensure_ascii=False,indent=2))
assert all(v['candidate_equal'] and v['tip_equal'] for v in files.values())
assert all(v['manifest_matches'] is not False for v in evidence.values())
assert all(v['byte_identical_to_P1'] for v in unchanged.values())
assert bound<16777216
