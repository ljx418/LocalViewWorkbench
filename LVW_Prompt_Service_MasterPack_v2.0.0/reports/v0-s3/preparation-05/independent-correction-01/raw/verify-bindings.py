import pathlib,subprocess,json,hashlib,ast
P=pathlib.Path.cwd();O=pathlib.Path(__file__).resolve().parent
base='bee7b345eafb2327b77520664949169d31e055c3';candidate='eef2fe8fc4afc8fc737643185fcd2789f1103195';tip='f409d8c85359b51ce5abfa27fec6e9ae9a1d4da2'
def git(*args):return subprocess.check_output(['git',*args])
def blob(sha,p):return git('show',sha+':'+P.name+'/'+p)
def sha(b):return hashlib.sha256(b).hexdigest()
paths=['tools/s3_sample_preparation.py','tools/test_s3_sample_preparation.py','LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/video_process.py','reports/v0-s3/preparation-05/correction-01.task.md','reports/v0-s3/preparation-05/codex-review-decision-01.json','reports/v0-s3/preparation-05/quality-set.frozen.json','reports/v0-s3/preparation-05/independent-01/prelabels.json','reports/v0-s3/preparation-05/independent-01/selection-proposal.json','reports/v0-s3/preparation-05/implementation/run-01/receipt.json','plans/execution-control.json','reports/v0-s3/preparation-05/stage-packet-preparation-c.md']
r={'base':base,'candidate':candidate,'tip':tip,'hashes':{p:sha((P/p).read_bytes()) for p in paths}}
r['candidate_code_matches']={p:blob(candidate,p)==(P/p).read_bytes() for p in paths[:3]};assert all(r['candidate_code_matches'].values())
old=blob(base,paths[1]);new=(P/paths[1]).read_bytes();assert new.startswith(old)
r['original_test_module_preserved_byte_for_byte_prefix']=True
r['original_tests']=[n.name for n in ast.parse(old).body if isinstance(n,ast.FunctionDef) and n.name.startswith('test_')];assert len(r['original_tests'])==45
oldcode=ast.parse(blob(base,paths[0]));newcode=ast.parse((P/paths[0]).read_bytes())
r['unchanged_render_functions']={name:ast.dump(next(n for n in oldcode.body if isinstance(n,ast.FunctionDef) and n.name==name))==ast.dump(next(n for n in newcode.body if isinstance(n,ast.FunctionDef) and n.name==name)) for name in ['render_thumbnail','render_contact_sheet','render_index']};assert all(r['unchanged_render_functions'].values())
def constants(tree):return {n.targets[0].id:ast.dump(n.value) for n in tree.body if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name)}
r['top_level_constants_unchanged']=constants(oldcode)==constants(newcode);assert r['top_level_constants_unchanged']
r['base_to_tip_changed_files']=git('diff','--name-only',base,tip).decode().splitlines()
for label,ps in [('protected',['contracts','plans','.agent-governance/stages','MANIFEST.sha256','reports/v0-s3/preparation-05/quality-set.frozen.json','reports/v0-s3/preparation-05/independent-01','reports/v0-s3/preparation-05/implementation/run-01'])]:
 d=git('diff',base,tip,'--',*ps);r[label+'_diff_empty']=not d;assert not d
q=json.loads((P/paths[5]).read_text());assert len(q['samples'])==16 and q['preview_source_candidate']=='e1798f33ba51dcadbf9f0333641d62d14a801491'
assert q['independent_prelabels_sha256']==r['hashes'][paths[6]]
r['frozen_sample_count']=16;r['fixed_denominator']=q['fixed_denominator'];r['original_preview_identity']={k:q[k] for k in ['preview_source_candidate','preview_source_run','independent_prelabel_commit']}
r['old_run_same_as_original_evidence_tip']=blob('335a8b973ab9b0fe192c03f59e608f9976658238',paths[8])==(P/paths[8]).read_bytes();assert r['old_run_same_as_original_evidence_tip']
(O/'bindings.json').write_text(json.dumps(r,indent=2)+'\n');(O/'candidate.diff').write_bytes(git('diff',base,candidate,'--',*paths[:2]));print(json.dumps(r,indent=2))
