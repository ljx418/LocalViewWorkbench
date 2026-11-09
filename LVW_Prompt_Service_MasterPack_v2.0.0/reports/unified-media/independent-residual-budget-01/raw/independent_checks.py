"""CPU-only synthetic Git/SQLite evidence. No production ledger/service/media access."""
import importlib.util,json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import local_program_authority as p
BASE=p.ROOT
spec=importlib.util.spec_from_file_location('reviewed_authority',BASE/'reports/unified-media/authority.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
class Checks(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.r=Path(self.tmp.name);self.db=self.r/'private.sqlite'
  self.b={'api_starts':1,'ollama_starts':1,'headless_browser_starts':1,'provider_calls':8,'full_checkpoints':1,'model_calls':8,'downloads':0,'cloud_calls':0,'paid_calls':0,'holdout_model_calls':0}
  self.put(p.REQUEST,json.loads((BASE/p.REQUEST).read_text()));self.put(p.APPROVAL,{'status':'ACTIVE','decision':'APPROVED','granted_by':'project_owner','authorization_id':'AUTH-PROGRAM-V1-LOCAL-02','request_sha256':p.digest(self.r/p.REQUEST)})
  self.put('source.py','baseline');self.put('tools/local_program_authority.py','synthetic authority');self.put('reports/unified-media/live_checkpoint.py','synthetic harness');self.put('.agent-governance/stages/R1/packet.json',{})
  self.put('.agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256',p.digest(self.r/'.agent-governance/stages/R1/packet.json')+'  packet.json\n')
  self.put('reports/unified-media/authorization-runtime-transition-01.request.json',{'samples':[],'proposed_packet_manifest_sha256':p.digest(self.r/'.agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256'),'frozen_paths':['source.py','reports/unified-media/live_checkpoint.py']})
  self.git('init','-q');self.git('config','user.email','review@example.invalid');self.git('config','user.name','Isolated review');self.git('add','.');self.git('commit','-qm','synthetic baseline');self.c=self.git('rev-parse','HEAD').strip()
  self.req={'authorization_id':'AUTH-BUDGET-V1-R1-RESIDUAL-01','run_id':'live-08','stage_id':'R1','parent_approval_sha256':p.digest(self.r/p.APPROVAL),'old_stage_full_limit':3,'new_stage_full_limit':4,'additional_full_runs':1,'budget':self.b,'max_seconds':1800,'candidate_sha':self.c,'frozen_paths':['source.py','tools/local_program_authority.py','reports/unified-media/live_checkpoint.py','.agent-governance/stages/R1']}
  self.put(p.AMENDMENT+'.request.json',self.req)
  # Simulate consumed full checkpoints directly in a private ledger, no model sends.
  with p.transaction(self.db) as db:
   for i in range(3):db.execute('INSERT INTO children(run,stage,cap,seconds,full,cpu,starts,issued,expires,calls,checkpoint,active,elapsed) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(f'old-{i}','R1',8,1800,1,0,json.dumps({k:1 for k in ['api_starts','ollama_starts','comfy_starts','headless_browser_starts']}),0,0,3,1,0,10))
  old_approved=p.approved;old_reserve=p.reserve;old_bind=p.bind;old_extra=p.extra_full_grant
  for obj,name,value in [(a,'ROOT',self.r),(p,'ROOT',self.r),(p,'LEDGER',self.db),(p,'approved',lambda *args:old_approved(self.r)),(p,'extra_full_grant',lambda run,stage,**kwargs:old_extra(run,stage,root=self.r)),(p,'reserve',lambda run,stage,budget,seconds,full:old_reserve(run,stage,budget,seconds,full,root=self.r,ledger=self.db)),(p,'bind',lambda run,child:old_bind(run,child,ledger=self.db))]:
   q=patch.object(obj,name,value);q.start();self.addCleanup(q.stop)
 def put(self,name,value):
  q=self.r/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_text(json.dumps(value) if isinstance(value,(dict,list)) else value);return q
 def git(self,*args):return subprocess.check_output(['git',*args],cwd=self.r,text=True,stderr=subprocess.DEVNULL)
 def grant(self,**changes):return self.put(p.AMENDMENT+'.approval.json',dict({'authorization_id':self.req['authorization_id'],'decision':'APPROVED','status':'ACTIVE','granted_by':'project_owner','request_sha256':p.digest(self.r/(p.AMENDMENT+'.request.json'))},**changes))
 def create(self,run='live-08'):return a.create_program02(run,self.r/'reports/unified-media/live_checkpoint.py',self.b,port=18780,samples=[],seconds=1800,full=True)
 def ready(self):
  self.grant();out,child=self.create();tool=self.put('synthetic-tool','tool');bindings=self.put('bindings.json',{'tool':{'path':str(tool),'sha256':p.digest(tool)}});p.bind_execution('live-08',bindings,ledger=self.db);return out,child
 def test_missing_approval_request_only(self):
  with self.assertRaises(ValueError):self.create()
  self.assertFalse((self.r/'reports/unified-media/live-08').exists())
 def test_forged_actor_wrong_hash_revoked(self):
  for fields in ({'granted_by':'implementer'},{'request_sha256':'0'*64},{'status':'REVOKED'},{'decision':'PENDING'}):
   self.grant(**fields)
   with self.assertRaises(ValueError):self.create()
 def test_wrong_run_stage(self):
  self.grant()
  with self.assertRaises(ValueError):self.create('live-09')
  with self.assertRaises(ValueError):p.extra_full_grant('live-08','R2',root=self.r)
 def test_dirty_candidate(self):
  self.grant();self.put('source.py','dirty')
  with self.assertRaises(AssertionError):self.create()
 def test_untracked_frozen_file(self):
  self.grant();self.put('.agent-governance/stages/R1/extra.py','untracked')
  with self.assertRaises(AssertionError):self.create()
 def test_frozen_descendant_diff(self):
  self.grant();self.put('source.py','changed');self.git('add','source.py');self.git('commit','-qm','changed source')
  with self.assertRaises(AssertionError):self.create()
 def test_nonancestor_candidate(self):
  self.req['candidate_sha']='0'*40;self.put(p.AMENDMENT+'.request.json',self.req);self.grant()
  with self.assertRaises(AssertionError):self.create()
 def test_evidence_descendant_allowed_bound(self):
  self.put('docs/evidence.md','synthetic evidence');self.git('add','docs');self.git('commit','-qm','evidence only');out,child=self.ready();self.assertEqual(child['budget_amendment']['approval_sha256'],p.digest(self.r/(p.AMENDMENT+'.approval.json')));p.model_action(out/'authorization.json')
 def test_send_grant_revocation_and_hash_drift(self):
  out,_=self.ready();g=self.r/(p.AMENDMENT+'.approval.json');original=g.read_bytes()
  for change in ('revoked','hash'):
   if change=='revoked':data=json.loads(original);data['status']='REVOKED';g.write_text(json.dumps(data))
   else:g.write_bytes(original+b' ')
   with self.assertRaises(ValueError):p.model_action(out/'authorization.json')
  with p.transaction(self.db) as db:self.assertEqual(db.execute("SELECT calls FROM children WHERE run='live-08'").fetchone()[0],0)
 def test_source_drift_before_send(self):
  out,_=self.ready();self.put('source.py','drift')
  with self.assertRaises(ValueError):p.model_action(out/'authorization.json')
 def test_terminal_autoexpiration_and_replay(self):
  out,child=self.ready();a.terminal(out,child,{'decision':'NO_GO','api_listener_absent':True,'ollama_listener_absent':True,'run_root_removed':True});self.assertTrue((self.r/(p.AMENDMENT+'.approval.terminal.json')).exists())
  with self.assertRaises(ValueError):p.model_action(out/'authorization.json')
  with self.assertRaises(ValueError):self.create()
 def test_global_model_budget_preserved(self):
  self.grant()
  with p.transaction(self.db) as db:db.execute("UPDATE children SET calls=170")
  with self.assertRaises(ValueError):self.create()
 def test_global_full_budget_preserved(self):
  self.grant()
  with p.transaction(self.db) as db:
   for i in range(5):db.execute("INSERT INTO children(run,stage,cap,seconds,full,cpu,starts,issued,expires,calls,checkpoint,active,elapsed) VALUES(?, 'R2',0,1,1,0,'{}',0,0,0,1,0,0)",(f'global-{i}',))
  with self.assertRaises(ValueError):self.create()
 def test_global_time_budget_preserved(self):
  self.grant()
  with p.transaction(self.db) as db:db.execute('UPDATE children SET elapsed=28800')
  with self.assertRaises(ValueError):self.create()
if __name__=='__main__':unittest.main(verbosity=2)
