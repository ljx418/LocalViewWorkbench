from probes import *
def test_complete_diagnostic_chain_still_refuses(build,monkeypatch,tmp_path):
 from tools.v0_s3_coordinator import budget,PROTOCOL_SOURCE
 from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import MODEL_DIGEST
 comp=build();root=tmp_path/'shape-authority';root.mkdir()
 for name in ('tools/local_program_authority.py','tools/v0_s3_budget_authority.py',PROTOCOL_SOURCE):
  p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((data.PACK_ROOT/name).read_bytes())
 py=root/'synthetic-python';py.write_bytes(b'never executed synthetic python role')
 def role(p):return {'path':str(p),'client_path':str(p),'sha256':sha(p.read_bytes())}
 roles={'authority':role(root/'tools/local_program_authority.py'),'shim':role(root/'tools/v0_s3_budget_authority.py'),'python':role(py),'wsl':None}
 ex={'s3_'+k:{'path':v['path'],'sha256':v['sha256']} for k,v in roles.items() if v};ex['s3_protocol']={'path':str(root/PROTOCOL_SOURCE),'sha256':sha((root/PROTOCOL_SOURCE).read_bytes())}
 ep=root/'execution.json';ep.write_text(json.dumps(ex));bp=root/'binding.json';now=time.time()
 binding={'schema':'lvw.s3-budget/1','program':budget.PROGRAM,'approval_sha256':'c'*64,'run_id':data.RUN_ID,'stage_id':'V0-S3','candidate_sha':CAND,'child_path':str(root/'child.json'),'child_sha256':data.AUTHORIZATION_SHA,'ledger_path':str(root/'original.sqlite'),'execution_path':str(ep),'execution_sha256':sha(ep.read_bytes()),'authority_root':str(root),'tools':roles,'issued_at':now,'expires_at':now+3600,'transport':'local-fixture','harness_transport':'local-fixture','distribution':None,'binding_path':str(bp),'client_binding_path':str(bp),'model':'gemma4:26b','model_digest':MODEL_DIGEST,'ollama_pid':4242,'ollama_start_ticks':99}
 bp.write_text(json.dumps(binding));admission=json.loads((comp['root']/'contexts/admission.json').read_bytes());admission.update(model_digest=MODEL_DIGEST,authority_root=str(root),ledger_path=str(root/'original.sqlite'))
 fields={'native_custody':['descendant_handles_closed','native_services_stopped'],'gpu_release':['gpu_released'],'install':['installed'],'rollback':['rollback_verified'],'grant':['grant_active']}
 for n in c.ADMISSION_REFERENCE_KEYS:
  if n=='budget_binding':p=bp
  else:
   doc={'run_id':data.RUN_ID,'candidate_sha':CAND,'status':'PROVEN',**{f:True for f in fields.get(n,[])}}
   if n=='tool_closure':doc['files']=[{'path':str(py),'sha256':sha(py.read_bytes())}]
   p=root/(n+'.json');p.write_text(json.dumps(doc))
  admission['admission_references'][n]={'path':str(p),'sha256':sha(p.read_bytes())}
 ap=comp['root']/'contexts/admission.json';ap.write_text(json.dumps(admission));cp=comp['controller_context_path'];cd=json.loads(cp.read_bytes());cd['admission']={'path':str(ap),'sha256':sha(ap.read_bytes())};cp.write_text(json.dumps(cd));ctx=c.ControllerContext.load(cp,expected_sha256=sha(cp.read_bytes()))
 rep=c.verify_native_admission(ctx,admission);assert set(rep['verified'])==set(c.ADMISSION_REFERENCE_KEYS) and rep['reasons']==['NATIVE_EXECUTION_BACKEND_NOT_READY'] and not rep['accepted']
 calls=[];monkeypatch.setattr(w,'build_native_driver',lambda *a,**kw:calls.append('driver'));monkeypatch.setattr(c.ParentSupervisor,'run',lambda *a,**kw:calls.append('spawn'))
 out=io.StringIO()
 with contextlib.redirect_stdout(out):code=c.main(['--context',str(cp),'--context-sha256',sha(cp.read_bytes())])
 r=json.loads(out.getvalue());save('M02-all-seven-diagnostic-proofs',{'report':rep,'default_main_exit':code,'receipt':r,'calls':calls,'ledger_file_created':(root/'original.sqlite').exists(),'synthetic_python_never_executed':True})
 assert not calls and r['spawn_attempts']==0 and not (root/'original.sqlite').exists()
