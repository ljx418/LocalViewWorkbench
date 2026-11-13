"""Independent original-trigger plus additional zero-process fault matrix.
No real binding runner, child, network, model, service or shared-counter write.
"""
import sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
exec(compile((OUT/'outer_boundary.py').read_bytes(),str(OUT/'outer_boundary.py'),'exec'))
import importlib.util,json,os,copy,threading
PACK=OUT.parents[3]
sys.path.insert(0,str(PACK))
spec=importlib.util.spec_from_file_location('audit02_runner',PACK/'reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
r.install_offline_guard()
from tools import test_v0_s3_supervisor as t
e=t.EXECUTOR_MODULE
results={}

def fresh(name):
 root=OUT/'synthetic'/name;root.mkdir(parents=True,exist_ok=False)
 counter=t.fake_root_counter(root)
 _,digest,_=t.fake_root_binding(root,counter_path=counter)
 ex=t.build_test_executor(root,counter_path=counter,binding_digest=digest)
 t.context_inside(root)
 return root,counter,ex

def action(ex,root,body):
 class Stub:
  PIPE=t._subprocess.PIPE
  @staticmethod
  def Popen(argv,**kwargs):
   sys.audit('subprocess.Popen',sys.executable,list(argv),str(root),None)
   return body()
 original=e.subprocess;e.subprocess=Stub
 try:
  with t.guard_gate(ex):
   try:return ex.spawn(t.executor_prefix()+['clean_terminal']),None
   except BaseException as err:return None,err
 finally:e.subprocess=original

def refuse():sys.audit('os.posix_spawn',sys.executable,['not-executed'],None)
def raiser(err):raise err

def finish_report(root,counter,ex):
 before=json.loads(counter.read_text());owned=root/'owned';owned.mkdir()
 outcome=r.finalize_session(executor=ex,owned=owned,stdout_handle=t.GoodHandle(),stderr_handle=t.GoodHandle(),saved_out=os.dup(1),saved_err=os.dup(2),source_hasher=lambda:{})
 after=json.loads(counter.read_text())
 return {'states_before':[x['state'] for x in before['charges']], 'states_after':[x['state'] for x in after['charges']], 'occupied':ex.counter._occupied(after),'admitted':after['starts_total'],'reserved':after['reserved_wall_seconds'],'open':ex.unsettled_charges(),'ledger':ex.charge_ledger(),'cleanup':outcome['cleanup_proven'],'exit':outcome['exit_code'],'root_retained':owned.exists(),'proofs':outcome['proofs']}

# Original copied-attribute and synthetic old violation triggers remain identical.
for name,gate in [('copied_marker_gate',e.CpuGateError('COPIED_GATE_ERROR')),('marker_wrong_nested',ValueError('wrong nested type')),('old_synthetic_outer',e.CpuGateError('OLD_REFUSAL'))]:
 root,counter,ex=fresh(name)
 err=r.OfflineBoundaryViolation('unrelated prior refusal',before_fork=True,gate_error=gate) if name=='old_synthetic_outer' else RuntimeError('ordinary copied-attribute failure')
 err.lvw_before_fork=True;err.gate_error=gate
 _,caught=action(ex,root,lambda:raiser(err));assert caught is err
 data=finish_report(root,counter,ex);results[name]=data
 assert data['states_after']==['UNKNOWN'] and data['occupied']==1 and data['open'] and not data['cleanup'] and data['exit']!=0 and data['root_retained']

# A real current production callback, no exception manufactured as its proof.
root,counter,ex=fresh('real_then_replay')
_,old=action(ex,root,refuse)
assert isinstance(old,r.OfflineBoundaryViolation)
credential=getattr(old,r.REFUSAL_CREDENTIAL)
assert credential.consumed is True
assert ex.unsettled_charges()==[]
# Copy the *entire* old credential and the same outer class without modifying fields.
copied=r.OfflineBoundaryViolation('copy of entire old proof',before_fork=True,refusal_credential=copy.copy(credential))
_,caught=action(ex,root,lambda:raiser(copied));assert caught is copied
results['copied_entire_old_credential']=finish_report(root,counter,ex)
assert results['copied_entire_old_credential']['states_after']==['REFUSED_BEFORE_FORK','UNKNOWN']
assert results['copied_entire_old_credential']['occupied']==1
# Exact old genuine exception replay into a different executor.
root,counter,ex=fresh('cross_executor_old_real')
_,caught=action(ex,root,lambda:raiser(old));assert caught is old
results['cross_executor_old_real']=finish_report(root,counter,ex)
assert results['cross_executor_old_real']['occupied']==1 and results['cross_executor_old_real']['root_retained']

# Preserve an unconsumed copy captured in the genuine guard callback before unwind.
root,counter,ex=fresh('unconsumed_copy_next_action');captured=[]
def capture():
 try:refuse()
 except r.OfflineBoundaryViolation as err:
  captured.append(copy.copy(getattr(err,r.REFUSAL_CREDENTIAL)))
  raise
_,old=action(ex,root,capture)
assert captured[0].consumed is False
wrapped=RuntimeError('entire copied unconsumed proof, wrong outer class')
setattr(wrapped,r.REFUSAL_CREDENTIAL,captured[0]);wrapped.lvw_before_fork=True;wrapped.gate_error=e.CpuGateError('COPIED')
_,caught=action(ex,root,lambda:raiser(wrapped));assert caught is wrapped
results['unconsumed_copy_next_action']=finish_report(root,counter,ex)
assert results['unconsumed_copy_next_action']['states_after']==['REFUSED_BEFORE_FORK','UNKNOWN']
assert results['unconsumed_copy_next_action']['occupied']==1

# finish returns false or throws: no-handle genuine refusal + one-time consumption,
# ordinary failure, and acquired synthetic handle. Preserve files for diagnostics.
for route in ('genuine_refusal','ordinary_failure','handle'):
 for failure in ('false','gate_error','os_error'):
  name=route+'_'+failure;root,counter,ex=fresh(name);seen=[]
  def fail(*args,**kwargs):
   if failure=='false':return False
   if failure=='gate_error':raise e.CpuGateError('CPU_COUNTER_UNREADABLE')
   raise OSError('independent finish I/O fault')
  def body():
   if route=='handle':return t.SettledChild()
   ex.counter.finish=fail
   if route=='genuine_refusal':
    try:refuse()
    except r.OfflineBoundaryViolation as err:
     seen.append(getattr(err,r.REFUSAL_CREDENTIAL));raise
   raise OSError('ordinary failed start')
  handle,caught=action(ex,root,body)
  if route=='handle':assert handle is not None;ex.counter.finish=fail
  else:assert caught is not None
  data=finish_report(root,counter,ex);results[name]=data
  assert data['occupied']==1 and data['admitted']==1 and data['open'] and not data['cleanup'] and data['exit']!=0 and data['root_retained']
  assert data['states_after']==(['STARTED'] if route=='handle' else ['PENDING'])
  if seen:assert seen[0].consumed is True

# Invocation semantics including all binding controls, without executing a binding.
args=type('Args',(),dict(mode='focused',label='matrix',select='one or two',modules='tools/test_v0_s3_supervisor.py',binding='/never-executed/binding',binding_sha256='c'*64,role='independent_review',candidate_sha='d'*40))()
command=r.build_effective_command(args,OUT)
original=getattr(sys,'orig_argv',None)
inv={}
for kind,value in [('UNKNOWN',[]),('programmatic',['python3','unrelated.py']),('process',[sys.executable,'-B',str(Path(r.__file__).resolve())]+command[3:])]:
 sys.orig_argv=value;inv[kind]=r.invocation_evidence(command);assert inv[kind]['kind']==kind
assert inv['process']['outer_matches_effective'] is True
sys.orig_argv=original
results['invocation']={'command':command,'observations':inv}

# Registration errors are exercised through main, and record import state.
# Test normal idempotence first; then old hook/alias cannot answer fresh registry.
owner=r.install_offline_guard();reg=r.guard_registry();assert r.install_offline_guard()==owner and reg.hook_install_count==1
results['normal_idempotence']={'owner':owner,'count':reg.hook_install_count,'handshakes':reg.handshake_count}
original_add=sys.addaudithook;old_registry=sys.modules[r.GUARD_REGISTRY_MODULE]
fresh_reg=r._GuardRegistry();sys.modules[r.GUARD_REGISTRY_MODULE]=fresh_reg
calls=[]
def explicit_failure(hook):calls.append(hook.__name__);raise RuntimeError('explicit API failure')
sys.addaudithook=explicit_failure
code=r.main(['--mode','guard','--label','explicit-install-failure','--outdir',str(OUT)])
try:r.install_offline_guard();retry='unexpected success'
except r.GuardInstallationError as err:retry=err.code
results['explicit_install_failure']={'exit':code,'retry':retry,'calls':calls,'installed':fresh_reg.hook_installed,'count':fresh_reg.hook_install_count}
assert code==5 and len(calls)==1 and fresh_reg.hook_installed is False
sys.addaudithook=original_add;sys.modules[r.GUARD_REGISTRY_MODULE]=old_registry

# True CPython silent suppression, while already installed old genuine hook exists.
def refuse_registration(event,arguments):
 if event=='sys.addaudithook':raise RuntimeError('existing policy denies new audit hook')
_real_add(refuse_registration)
fresh_reg=r._GuardRegistry();sys.modules[r.GUARD_REGISTRY_MODULE]=fresh_reg
code=r.main(['--mode','guard','--label','silent-install-failure','--outdir',str(OUT)])
try:r.install_offline_guard();retry='unexpected success'
except r.GuardInstallationError as err:retry=err.code
results['silent_install_failure_old_hook_present']={'exit':code,'retry':retry,'installed':fresh_reg.hook_installed,'count':fresh_reg.hook_install_count,'handshakes':fresh_reg.handshake_count,'old_hook_count':old_registry.hook_install_count}
assert code==5 and not fresh_reg.hook_installed and fresh_reg.handshake_count==0
sys.modules[r.GUARD_REGISTRY_MODULE]=old_registry
print(json.dumps(results,indent=2,sort_keys=True))
print('INDEPENDENT_MATRIX_ASSERTIONS_OK')
