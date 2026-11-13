from pathlib import Path
import json,hashlib,subprocess,shutil
P=Path.cwd();O=P/'reports/v0-s3/product-gate0/independent-sequential-correction-02'
root=Path('/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0')
author=Path('/home/administrator/orca/workspaces/LocalViewWorkbench/lvw-v1-d0-implement/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/implementation-integration-sequential-correction-02')
h=lambda b:hashlib.sha256(b).hexdigest()
refs=['AGENTS.md','.agent-governance/README.md','.agent-governance/parallel-execution.md','plans/execution-control.json','docs/24_EXECUTION_MASTER_PLAN.md','reports/v0-s3/product-gate0/s3-integration-offline-contract-01.md','reports/v0-s3/product-gate0/sequential-correction-review-01/root-decision.json','reports/v0-s3/product-gate0/audit-correction-review-02/root-decision.json']
refs+=['reports/v0-s3/product-gate0/sequential-correction-review-01/received/'+x for x in ['review.md','negative_probes.py','idempotency_deadline_probes.py','negative-results.json','idempotency-deadline-results.json','negative.outer.json','idempotency-deadline.outer.json','negative.stdout.log','negative.stderr.log','idempotency-deadline.stdout.log','idempotency-deadline.stderr.log']]
records=[]
for i,r in enumerate(refs):
 p=root/r
 if not p.exists() and r.endswith('s3-integration-offline-contract-01.md'):p=P/r
 if p.exists():
  dest=O/'references'/r;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(p.read_bytes());records.append({'source':str(p),'copy':str(dest.relative_to(O)),'sha256':h(p.read_bytes())})
 else:records.append({'source':str(p),'missing':True})
(O/'references.json').write_text(json.dumps(records,indent=2))
A=O/'author-preserved';A.mkdir();ar=[]
for p in sorted(author.iterdir()):
 if p.is_file():
  (A/p.name).write_bytes(p.read_bytes());ar.append({'name':p.name,'sha256':h(p.read_bytes()),'bytes':p.stat().st_size})
(O/'author-files.json').write_text(json.dumps(ar,indent=2))
checks=[]
for receipt in A.glob('*.receipt.json'):
 d=json.loads(receipt.read_text())
 for kind in ['stdout','stderr']:
  name=d.get(kind+'_file')
  if name:
   p=A/Path(name).name;actual=h(p.read_bytes()) if p.exists() else None
   checks.append({'receipt':receipt.name,'stream':kind,'expected':d.get(kind+'_sha256'),'actual':actual,'matches':actual==d.get(kind+'_sha256')})
(O/'author-receipt-stream-checks.json').write_text(json.dumps(checks,indent=2))
sources=['reports/v0-s3/product-gate0/implementation-integration-01/executor.py','reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py','tools/test_v0_s3_supervisor.py']
bind=[]
for r in sources:
 raw=(P/r).read_bytes();blob=subprocess.check_output(['git','show','01453ee:LVW_Prompt_Service_MasterPack_v2.0.0/'+r]);old=subprocess.check_output(['git','show','4e99904:LVW_Prompt_Service_MasterPack_v2.0.0/'+r])
 bind.append({'path':r,'sha256':h(raw),'matches_candidate_blob':raw==blob,'baseline_sha256':h(old),'unchanged_from_baseline':raw==old})
(O/'candidate-source-hashes.json').write_text(json.dumps(bind,indent=2))
(O/'source.diff').write_bytes(subprocess.check_output(['git','diff','4e99904','01453ee','--','LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/implementation-integration-01/executor.py','LVW_Prompt_Service_MasterPack_v2.0.0/tools/test_v0_s3_supervisor.py']))
c=Path('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json');b=c.read_bytes();before=json.loads((O/'initial.json').read_text())
(O/'counter-after.json').write_text(json.dumps({'sha256':h(b),'unchanged':h(b)==before['counter_sha256'],'counter':json.loads(b)},indent=2))
print('source',bind);print('stream mismatches',[x for x in checks if not x['matches']]);print('counter',h(b))
rows=json.loads((O/'negative-results.json').read_text());print('rows',len(rows));print('final read successes',[r['name'] for r in rows if r['name'].startswith('final_read') and r['final']['cleanup_proven']])
