from pathlib import Path
import subprocess,json,hashlib,stat
P=Path('LVW_Prompt_Service_MasterPack_v2.0.0');D=P/'reports/v0-s3/product-gate0/independent-originals-correction-05';R=Path('/mnt/c/workspace/videoworkline/localviewworkbench')/P;G=R/'reports/v0-s3/product-gate0';old=P/'reports/v0-s3/product-gate0/independent-originals-correction-04';author=G/'originals-correction-review-05/received';received=G/'originals-correction-05/received-review'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,v):(D/n).write_text(json.dumps(v,indent=2))
def git(*args):return subprocess.check_output(['git',*args])
# Bind root authoritative original independent inputs, author received raw, and frozen controls.
inputs={}
for base in [author,received]:
 for f in base.rglob('*'):
  if f.is_file() and not f.is_symlink():inputs[str(f)]={'sha256':sha(f.read_bytes()),'bytes':f.stat().st_size}
for f in [G/'originals-correction-05/root-decision.json',P/'AGENTS.md',P/'.agent-governance/README.md',P/'.agent-governance/parallel-execution.md',P/'plans/execution-control.json',P/'docs/24_EXECUTION_MASTER_PLAN.md',P/'reports/v0-s3/product-gate0/s3-integration-offline-contract-01.md']:
 inputs[str(f)]={'sha256':sha(f.read_bytes()),'bytes':f.stat().st_size}
save('input-integrity.json',inputs)
manifest=json.loads((old/'integrity.json').read_text());bad=[]
for name,info in manifest['entries'].items():
 f=old/name
 if sha(f.read_bytes())!=info['sha256']:bad.append(name)
assert not bad,bad
save('prior-integrity-check.json',{'regular_entries_verified':len(manifest['entries']),'mismatches':bad,'root_received_probe_matches_local_prior':(received/'probe_final.py').read_bytes()==(old/'probe_final.py').read_bytes(),'root_received_review_matches_local_prior':(received/'review.md').read_bytes()==(old/'review.md').read_bytes()})
assert (received/'probe_final.py').read_bytes()==(old/'probe_final.py').read_bytes()
receipt=json.loads((author/'run.receipt.json').read_text());nodes=json.loads((D/'collected-nodes.json').read_text())['nodes'];prior=json.loads((old/'selection.json').read_text());new=[n for n in nodes if n not in prior]
assert len(nodes)==len(set(nodes))==41 and len(prior)==31 and len(new)==10
assert set(nodes)==set(receipt['directed_nodes']) and set(new)==set(receipt['control_nodes'])
reportbind={}
for f in author.rglob('*'):
 if f.is_file() and not f.is_symlink():
  rel=f.relative_to(author);path=P/'reports/v0-s3/product-gate0/implementation-originals-correction-05'/rel
  reportbind[str(rel)]=f.read_bytes()==git('show','07277a6f2f6f730dc7b9383bfeaf8c412126fe16:'+str(path))
assert all(reportbind.values())
for f,h in receipt['candidate_sources'].items():assert sha((P/f).read_bytes())==h
save('author-crosscheck.json',{'received_regular_files_match_exact_candidate':reportbind,'sources_match_receipt':True,'ast_added_test_functions':json.loads((D/'ast-selection.json').read_text())['added_test_functions'],'existing_tests_ast_unchanged':True,'unique_collected_nodes':41,'prior_nodes':31,'new_nodes':new,'new_nodes_count':10,'new_negative_count':8,'new_positive_count':2,'report_31_plus_12_equals_41_is_incorrect':True,'old_control_is_not_candidate_PASS':{'exit':receipt['steps'][2]['exit_code'],'stdout_tail':(author/'control-old-candidate.outer.stdout.log').read_text()[-500:]},'current_step_exits':{s['label']:s['exit_code'] for s in receipt['steps']},'archived_nonempty_error_logs':{f.name:f.read_text() for f in author.glob('*.archived-*.stderr.log') if f.stat().st_size},'historical_missing_stderr_not_recovered':True,'scratch_worktree_creation_removal_disclosed_deviation_not_repeated':True})
control=json.loads((R/'plans/execution-control.json').read_text());save('development-outline.json',control['development_outline']);save('root-control-summary.json',{k:control[k] for k in ['coordinate','target_version','next_delivery_target','last_passed_gate','current_blocking_gate','stop_report_policy']})
cmd=P/'tools/open_lvw_browser.cmd';actual=cmd.read_bytes();blob=git('show','07277a6f2f6f730dc7b9383bfeaf8c412126fe16:'+str(cmd));assert actual.replace(b'\r\n',b'\n')==blob;assert not git('diff','--',str(cmd))
save('cmd-exception.json',{'path':str(cmd),'work_sha256':sha(actual),'candidate_sha256':sha(blob),'normalized_equal':True,'git_diff_empty':True,'executed':False,'previously_approved':True})
counter=Path('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json').read_bytes();assert counter==(D/'counter-before.json').read_bytes();assert sha(counter)=='8f12beb38c78378e51d3164cf02f54e54d619f55f2286a8d128b81249dc0fb18';(D/'counter-after.json').write_bytes(counter)
initial=json.loads((D/'initial-state.json').read_text());idx=Path(git('rev-parse','--git-path','index').decode().strip());assert idx.read_bytes()==(D/'initial-index.bin').read_bytes();assert git('rev-parse','HEAD').decode().strip()==initial['HEAD']
sources=json.loads((D/'source-binding.json').read_text())['sources']
for f,h in sources.items():assert sha((P/f).read_bytes())==h and (P/f).read_bytes()==git('show','07277a6f2f6f730dc7b9383bfeaf8c412126fe16:'+str(P/f))
# Match pre-existing status entries after removing precisely this new report directory.
now=git('status','--porcelain=v2','--untracked-files=all').decode();nowold='\n'.join(x for x in now.splitlines() if str(D)+'/' not in x)+'\n';initialold='\n'.join(x for x in initial['status'].splitlines() if str(D)+'/' not in x)+'\n';assert nowold==initialold
for label in ['independent-boundary','collect-only','new-directed']:assert json.loads((D/(label+'.guard.json')).read_text())['denials']==[]
assert len(json.loads((D/'guard-selftest.guard.json').read_text())['denials'])==9
assert not any(stat.S_ISFIFO(f.lstat().st_mode) for f in D.rglob('*'))
save('final-state.json',{'head':initial['HEAD'],'head_unchanged':True,'index_bytes_unchanged':True,'index_sha256':sha(idx.read_bytes()),'four_sources_exact_candidate':True,'status_excluding_new_report_unchanged':True,'status':now,'counter_sha256':sha(counter),'all_guarded_steps_successful':True,'no_remaining_fifo':True,'source_hashes':sources})
print(json.dumps({'prior_integrity_entries':len(manifest['entries']),'author_raw_files_verified':len(reportbind),'collected':len(nodes),'new_nodes':len(new),'HEAD_index_status_counter_preserved':True}))
