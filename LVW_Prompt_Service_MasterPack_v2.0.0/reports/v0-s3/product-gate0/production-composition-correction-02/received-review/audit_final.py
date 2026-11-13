from pathlib import Path
import hashlib,json,subprocess,os,stat
D=Path(__file__).parent.resolve();R=D.parents[3];repo=R.parent
sha=lambda b:hashlib.sha256(b).hexdigest()
g=lambda *a:subprocess.check_output(['git',*a],cwd=repo)
initial=json.loads((D/'initial-state.json').read_text());assert g('rev-parse','HEAD').decode()==initial['head']
index=Path(g('rev-parse','--git-path','index').decode().strip());index=index if index.is_absolute() else repo/index
assert index.read_bytes()==(D/'initial-index.bin').read_bytes()
changed=json.loads((D/'source-materialization.json').read_text());allowed={x['path'] for x in changed};assert len(allowed)==6
for x in changed:
 p=repo/x['path'];b=p.read_bytes();expected=g('show','7dc76ffeec685959f5906c612e58f7e1fc081425:'+x['path']);assert b==expected and sha(b)==x['candidate_sha256']
# Preserve all initial status entries except source paths explicitly authorized for materialization and new report.
now=g('status','--porcelain=v1').decode();prefix=str(D.relative_to(repo))+'/'
def others(s):return sorted(line for line in s.splitlines() if line[3:] not in allowed and not line[3:].startswith(prefix))
assert others(now)==others(initial['status']),(others(now),others(initial['status']))
for x in json.loads((D/'candidate-source-comparison.json').read_text()):assert sha((repo/x['path']).read_bytes())==x['work_sha256']
# Received/root archived inputs all remain as read.
inputs=json.loads((D/'input-integrity.json').read_text());checks=[]
for name,e in inputs.items():
 p=Path(name);p=p if p.is_absolute() else repo/p;assert sha(p.read_bytes())==e['sha256'];checks.append(str(p))
archive=json.loads((D/'review-archive-integrity.json').read_text());assert sha(Path(archive['zip']).read_bytes())==archive['sha256']
old=D.parent/'independent-production-composition-01';prior=0
for x in archive['files']:
 p=old/x['path'];b=os.readlink(p).encode() if p.is_symlink() else p.read_bytes();assert sha(b)==x['sha256'];prior+=1
counter=Path('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json').read_bytes();assert counter==(D/'counter-before.json').read_bytes();assert sha(counter)=='acbdb8b154864b6f079ae783d670f11ec138b6be0617d1fa4f56c28c33223b98';(D/'counter-after.json').write_bytes(counter)
for f in D.glob('*.guard.json'):
 a=json.loads(f.read_text());assert a['preimport']
 if f.name=='guard-selftest.guard.json':assert len(a['denials'])==8
 else:assert a['denials']==[]
# Every guarded batch that actually imported the candidate recorded stable FDs and no extra thread at exit.
for f in ['probe-results.json','supplement-results.json','final-results.json','complete-chain-results.json','parse-boundary-results.json']:
 a=json.loads((D/f).read_text());assert set(a['fd_before'])==set(a['fd_after']);assert [x[0] for x in a['threads_after']]==['MainThread']
fifos=[str(p) for p in D.rglob('*') if not p.is_symlink() and stat.S_ISFIFO(p.lstat().st_mode)];assert not fifos
# Source tree scopes + current root governance control remain unchanged relative to read receipts.
root=Path('/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0');gov=json.loads((D/'root-governance-inputs.json').read_text())
for n,v in gov.items():assert sha((root/n).read_bytes())==v['sha256']
control=json.loads((root/'plans/execution-control.json').read_text());old_control=json.loads((D/'root-control-read.json').read_text());old_control.update(coordinate=control['coordinate'],product_status=control['product_status'],current_blocking_gate=control['current_blocking_gate'],stop_report_policy=control['stop_report_policy'],planning_track=control['planning_track']);(D/'root-control-read.json').write_text(json.dumps(old_control,ensure_ascii=False,indent=2))
result={'head':initial['head'].strip(),'head_unchanged':True,'index_unchanged':True,'index_sha256':sha(index.read_bytes()),'source_materialized_exact_candidate':len(changed),'all90_prior_sources_exact_candidate':True,'source_staged_or_committed':False,'status_except_authorized_sources_NEW_report_unchanged':True,'status':now,'old_archive_entries_unchanged':prior,'input_files_unchanged':len(checks),'root_governance_unchanged':True,'counter_sha256':sha(counter),'counter_inactive':not json.loads(counter)['active'],'FD_thread_batches_verified':5,'remaining_fifo':fifos,'stage_pass_claim':False,'product_gate0':False,'candidate_outcome':'CHANGES_REQUIRED','review_task_completed':True}
(D/'final-state.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
# Avoid self-referential manifest hash; hash exact bytes of every report artifact and symlink target, retaining failures.
manifest=[]
for p in sorted(D.rglob('*')):
 if p.name in ('integrity.json','audit-final.stdout.log','audit-final.stderr.log'):continue
 if p.is_symlink():b=os.readlink(p).encode();typ='symlink'
 elif p.is_file():b=p.read_bytes();typ='file'
 else:continue
 manifest.append({'path':str(p.relative_to(D)),'type':typ,'bytes':len(b),'sha256':sha(b)})
(D/'integrity.json').write_text(json.dumps({'algorithm':'sha256','entries':manifest,'excludes':['integrity.json','audit-final.stdout.log','audit-final.stderr.log']},indent=2))
