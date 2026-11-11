import pathlib,subprocess,json,hashlib,ast
P=pathlib.Path.cwd();O=pathlib.Path(__file__).resolve().parent
base='08daf12b87340eb5fcdd64c3d4444ee686ef712b';candidate='9fc71b9551959c351016939196056b98b25a8acc';tip='bc5c0145fce51fbb5204c7eaa2f976ff06be1fb3'
def git(*a):return subprocess.check_output(['git',*a])
def blob(commit,path):return git('show',commit+':'+P.name+'/'+path)
def sha(data):return hashlib.sha256(data).hexdigest()
paths=['tools/s3_sample_preparation.py','tools/test_s3_sample_preparation.py','LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/video_process.py','reports/v0-s3/preparation-05/correction-02.task.md','reports/v0-s3/preparation-05/codex-correction-01-review-decision.json','reports/v0-s3/preparation-05/stage-packet-preparation-c.md','reports/v0-s3/preparation-05/quality-set.frozen.json','reports/v0-s3/preparation-05/independent-01/prelabels.json','reports/v0-s3/preparation-05/implementation/run-01/receipt.json','plans/execution-control.json']
r={'base':base,'candidate':candidate,'tip':tip,'hashes':{p:sha((P/p).read_bytes()) for p in paths},'code_matches_candidate':{p:blob(candidate,p)==(P/p).read_bytes() for p in paths[:3]}}
assert all(r['code_matches_candidate'].values())
old=blob(base,paths[1]);new=(P/paths[1]).read_bytes();r['original_71_module_unchanged_byte_prefix']=new.startswith(old);assert r['original_71_module_unchanged_byte_prefix']
r['original_test_functions']=[n.name for n in ast.parse(old).body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')]
r['prior_71_result']= (P/'reports/v0-s3/preparation-05/independent-correction-01/raw/suite.stdout.log').read_text().splitlines()[-1]
assert '71 passed' in r['prior_71_result']
r['runner_unchanged']=blob(base,paths[2])==(P/paths[2]).read_bytes();assert r['runner_unchanged']
oldtree=ast.parse(blob(base,paths[0]));newtree=ast.parse((P/paths[0]).read_bytes())
r['unchanged_render_functions']={name:ast.dump(next(n for n in oldtree.body if isinstance(n,ast.FunctionDef) and n.name==name))==ast.dump(next(n for n in newtree.body if isinstance(n,ast.FunctionDef) and n.name==name)) for name in ['render_thumbnail','render_contact_sheet','render_index']};assert all(r['unchanged_render_functions'].values())
def constants(tree):return {n.targets[0].id:ast.dump(n.value) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
r['top_level_constants_unchanged']=constants(oldtree)==constants(newtree);assert r['top_level_constants_unchanged']
r['changed_base_to_tip']=git('diff','--name-only',base,tip).decode().splitlines()
protected=['contracts','plans','.agent-governance/stages','MANIFEST.sha256','reports/v0-s3/preparation-05/quality-set.frozen.json','reports/v0-s3/preparation-05/independent-01','reports/v0-s3/preparation-05/independent-correction-01','reports/v0-s3/preparation-05/implementation/run-01']
r['protected_no_diff']=not git('diff',base,tip,'--',*protected);assert r['protected_no_diff']
q=json.loads((P/paths[6]).read_text());assert len(q['samples'])==16 and q['preview_source_candidate']=='e1798f33ba51dcadbf9f0333641d62d14a801491'
assert q['independent_prelabels_sha256']==r['hashes'][paths[7]]
r['frozen_sample_count']=16;r['fixed_denominator']=q['fixed_denominator'];r['original_preview_identity']={k:q[k] for k in ['preview_source_candidate','preview_source_run','independent_prelabel_commit']}
r['old_run_same_as_335a8b97']=blob('335a8b973ab9b0fe192c03f59e608f9976658238',paths[8])==(P/paths[8]).read_bytes();assert r['old_run_same_as_335a8b97']
implementation=P/'reports/v0-s3/preparation-05/implementation/correction-02/raw'
r['implementation_suite_history']={name:(implementation/(name+'.stdout.log')).read_text().splitlines()[-1] for name in ['draft-matrix','first-matrix','first-suite','matrix','suite']}
r['first_suite_real_minus15_preserved']='assert -15 == 0' in (implementation/'first-suite.stdout.log').read_text();assert r['first_suite_real_minus15_preserved']
r['poll_wrapper_review']='wait(timeout=2) waits for actual owned short child after real readers start; original poll returns actual status; production runner unchanged and overflow/reader flags remain real; does not establish natural schedule frequency'
(O/'bindings.json').write_text(json.dumps(r,indent=2)+'\n');(O/'candidate.diff').write_bytes(git('diff',base,candidate,'--',*paths[:2]));print(json.dumps(r,indent=2))
