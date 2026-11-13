import sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
exec(compile((OUT/'outer_boundary.py').read_bytes(),str(OUT/'outer_boundary.py'),'exec'))
import importlib.util,json
path=OUT.parents[3]/'reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py'
spec=importlib.util.spec_from_file_location('early_runner',path)
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
results={}
def imports():return sorted(k for k in sys.modules if k=='pytest' or k.startswith(('pytest.','_pytest','tools.','lvw_s3_finite_cpu_executor')))
assert imports()==[]
original_add=sys.addaudithook
calls=[]
def explicit(hook):calls.append(hook.__name__);raise RuntimeError('independent registration fault')
sys.addaudithook=explicit
before=imports();code=r.main(['--mode','guard','--label','early-explicit-install-failure','--outdir',str(OUT)])
results['explicit']={'before':before,'after':imports(),'exit':code,'calls':calls,'installed':r.guard_registry().hook_installed}
assert code==5 and imports()==[] and not r.guard_registry().hook_installed
sys.addaudithook=original_add
fresh=r._GuardRegistry();sys.modules[r.GUARD_REGISTRY_MODULE]=fresh
owner=r.install_offline_guard();assert r.install_offline_guard()==owner
# Load an alias; it must share the current registry and install just once.
spec=importlib.util.spec_from_file_location('early_alias',path)
alias=importlib.util.module_from_spec(spec);spec.loader.exec_module(alias)
assert alias.install_offline_guard()==owner and alias.guard_registry() is fresh and fresh.hook_install_count==1
results['normal_alias']={'count':fresh.hook_install_count,'handshakes':fresh.handshake_count,'imports':imports()}
def reject(event,args):
 if event=='sys.addaudithook':raise RuntimeError('real CPython silently suppresses registration')
_real_add(reject)
new=r._GuardRegistry();sys.modules[r.GUARD_REGISTRY_MODULE]=new
before=imports();code=alias.main(['--mode','guard','--label','early-silent-install-failure','--outdir',str(OUT)])
results['silent_old_alias_hook']={'before':before,'after':imports(),'exit':code,'installed':new.hook_installed,'new_handshakes':new.handshake_count,'new_count':new.hook_install_count,'old_count':fresh.hook_install_count}
assert code==5 and imports()==[] and new.handshake_count==0 and not new.hook_installed
print(json.dumps(results,indent=2))
