"""Reviewer CPU-only probes; never start services, sockets, media tools or models."""
import concurrent.futures, hashlib, importlib.util, json, pathlib, shutil, sys, tempfile
from unittest.mock import patch
BASE=pathlib.Path(__file__).resolve().parents[3]
OUT=pathlib.Path(__file__).resolve().parent
paths=['tools/local_program_authority.py','tools/test_local_program_authority.py','reports/unified-media/authority.py','reports/unified-media/live_checkpoint.py','START_LVW.cmd','lvw/run_local.py','lvw/backend/app/provider.py']
SNAP=OUT/'initial-snapshot';SNAP.mkdir(exist_ok=True)
for p in paths:
 d=SNAP/p;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(BASE/p,d)
spec=importlib.util.spec_from_file_location('review_authority',SNAP/'tools/local_program_authority.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
results={'source_sha256':{p:hashlib.sha256((SNAP/p).read_bytes()).hexdigest() for p in paths}}
def fixture(root):
 (root/'reports').mkdir();shutil.copyfile(BASE/a.REQUEST,root/a.REQUEST)
 (root/a.APPROVAL).write_text(json.dumps(dict(status='ACTIVE',decision='APPROVED',granted_by='project_owner',authorization_id='AUTH-PROGRAM-V1-LOCAL-02',request_sha256=a.digest(root/a.REQUEST))))
 return root/'private.sqlite'
def child(root,ledger,run='probe',cap=2):
 a.reserve(run,'R1',dict(model_calls=cap,provider_calls=cap,full_checkpoints=1),100,True,root=root,ledger=ledger)
 (root/'source.py').write_text('frozen');(root/'sample.bin').write_bytes(b'original authorized sample')
 p=root/(run+'.json');p.write_text(json.dumps(dict(run_id=run,budget_ledger=str(ledger),program_sha256=a.digest(root/a.APPROVAL),frozen_files=[dict(path='source.py',sha256=a.digest(root/'source.py'))],samples=[dict(path='sample.bin',sha256=a.digest(root/'sample.bin'))])))
 a.bind(run,p,ledger=ledger);return p
with tempfile.TemporaryDirectory(dir=OUT) as td:
 root=pathlib.Path(td);ledger=fixture(root);p=child(root,ledger)
 (root/'sample.bin').write_bytes(b'REPLACED SAMPLE')
 with patch.object(a,'ROOT',root):
  try:a.model_action(p);results['sample_changed_before_action']='ALLOWED'
  except Exception as e:results['sample_changed_before_action']=repr(e)
with tempfile.TemporaryDirectory(dir=OUT) as td:
 root=pathlib.Path(td);ledger=fixture(root)
 for i in range(5):
  try:
   a.reserve('startup-'+str(i),'R1',dict(api_starts=1,model_calls=0,provider_calls=0,full_checkpoints=0),100,False,root=root,ledger=ledger)
   a.settle('startup-'+str(i),0,ledger=ledger)
  except ValueError as e:results['zero_attempt_'+str(i)]=str(e)
 with a.transaction(ledger) as db:results['five_production_zero_model_startups']=a.totals(list(db.execute('select * from children')))
with tempfile.TemporaryDirectory(dir=OUT) as td:
 root=pathlib.Path(td);ledger=fixture(root);p=child(root,ledger)
 def action(_):
  try:a.model_action(p);return True
  except ValueError:return False
 with patch.object(a,'ROOT',root):
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:results['concurrent_cap2_16_actions_allowed']=sum(pool.map(action,range(16)))
 with a.transaction(ledger) as db:results['atomic_row']=dict(db.execute('select * from children').fetchone())
with tempfile.TemporaryDirectory(dir=OUT) as td:
 root=pathlib.Path(td);ledger=fixture(root)
 for i,stage in enumerate(['R0','R1a','R1','R2']):a.reserve('aggregate-'+str(i),stage,dict(model_calls=128,full_checkpoints=1),100,True,root=root,ledger=ledger)
 try:a.reserve('over','V0-S2',dict(model_calls=1,full_checkpoints=1),100,True,root=root,ledger=ledger);results['program_513']='ALLOWED'
 except ValueError as e:results['program_513']=str(e)
(OUT/'initial-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
