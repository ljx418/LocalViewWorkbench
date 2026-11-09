import importlib.util,json,pathlib,tempfile,shutil,sys
from unittest.mock import patch
OUT=pathlib.Path(__file__).resolve().parent;BASE=OUT.parents[2]
sys.path.insert(0,str(BASE))
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
a=load('review_program',BASE/'tools/local_program_authority.py');h=load('review_harness_authority',BASE/'reports/unified-media/authority.py')
with tempfile.TemporaryDirectory(dir=OUT) as tmp:
 root=pathlib.Path(tmp);(root/'reports').mkdir();shutil.copyfile(BASE/a.REQUEST,root/a.REQUEST)
 (root/a.APPROVAL).write_text(json.dumps(dict(status='ACTIVE',decision='APPROVED',granted_by='project_owner',authorization_id='AUTH-PROGRAM-V1-LOCAL-02',request_sha256=a.digest(root/a.REQUEST))))
 ledger=root/'private.sqlite';a.reserve('terminal-probe','R1',dict(model_calls=2,full_checkpoints=1),100,True,root=root,ledger=ledger)
 auth=dict(run_id='terminal-probe',budget_ledger=str(ledger),program_sha256=a.digest(root/a.APPROVAL),frozen_files=[],samples=[])
 child=root/'authorization.json';child.write_text(json.dumps(auth));a.bind('terminal-probe',child,ledger=ledger)
 result=dict(decision='NO_GO',api_listener_absent=False,ollama_listener_absent=False,cleanup_error='intentionally unproved cleanup')
 h.terminal(root,auth,result)
 results=dict(terminal=json.loads((root/'authorization.terminal.json').read_text()),receipt=json.loads((root/'receipt.json').read_text()))
 with patch.object(a,'ROOT',root):
  try:a.model_action(child);results['action_after_terminal']='ALLOWED'
  except Exception as e:results['action_after_terminal']=repr(e)
 with a.transaction(ledger) as db:results['ledger_row_after_terminal']=dict(db.execute('select * from children').fetchone())
(OUT/'terminal-results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
