from probes import *
def test_native_formal_default_main(build,monkeypatch):
 comp=build();calls=[]
 monkeypatch.setattr(w,'build_native_driver',lambda *a,**kw:calls.append('native'))
 monkeypatch.setattr(c.ParentSupervisor,'run',lambda *a,**kw:calls.append('supervisor'))
 out=io.StringIO();err=io.StringIO()
 with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):code=c.main(['--context',str(comp['controller_context_path']),'--context-sha256',sha(comp['controller_context_path'].read_bytes())])
 receipt=json.loads(out.getvalue());save('M02-default-controller-main',{'exit':code,'receipt':receipt,'stderr':err.getvalue(),'calls':calls})
 assert not calls and receipt['spawn_attempts']==0 and 'CONTROLLER_NATIVE_EXECUTION_BACKEND_NOT_READY' in receipt['refusals']
@pytest.mark.parametrize('point',['PRECHECK','PLAN_SEALED'])
def test_reservation_root_objects(build,monkeypatch,point):
 comp=build();old=[]
 def fault(state,obj):
  if state!=point:return
  root=comp['root'];retained=root.with_name('original-held');root.rename(retained);root.mkdir();old.append(retained)
 v,seam,obj=run(comp,monkeypatch,transition=fault);newfiles=[str(p.relative_to(comp['root'])) for p in comp['root'].rglob('*')];save('M06-reservation-'+point,{**v,'new_root_files':newfiles})
 assert old and any('reservation-' in x for x in newfiles) if point=='PRECHECK' else old

def test_command_compat_required_seal():
 from tools.v0_s3_supervisor import build_production_command,SupervisionError
 cmd=build_production_command('/tmp/controlled-context',context_sha256='a'*64)
 assert cmd[-2:]==['--context-sha256','a'*64] and cmd[1:3]==['-I','-B']
 with pytest.raises(SupervisionError,match='WORKER_CONTEXT_HASH_REQUIRED'):build_production_command('/tmp/controlled-context')
 save('M03-command-compat',{'command':cmd,'unsealed_refused':True})
