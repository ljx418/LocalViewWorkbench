"""Outer evidence runner: subprocess only starts preimport guarded interpreter, no fixture."""
from pathlib import Path
import subprocess,json,time,sys,hashlib,ast
D=Path(__file__).resolve().parent
P=D.parents[3]
assert (P/'tools').is_dir(),P
path='LVW_Prompt_Service_MasterPack_v2.0.0/tools/test_v0_s3_integration.py'
old=subprocess.check_output(['git','show','b27b0d17b71371e37002aabc5f69a030872b9177:'+path],cwd=P)
new=(P/'tools/test_v0_s3_integration.py').read_bytes()
def defs(b):return {n.name:ast.dump(n) for n in ast.parse(b).body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
a,b=defs(old),defs(new)
added=[n for n in b if n.startswith('test_') and n not in a]
changed=[n for n in a if n.startswith('test_') and b.get(n)!=a[n]]
assert not changed
(D/'ast-selection.json').write_text(json.dumps({'added_test_functions':added,'existing_test_functions_changed':changed,'new_selectors':['tools/test_v0_s3_integration.py::'+n for n in added]},indent=2))
records=[]
for label,entry,args in [('guard-selftest','guard_selftest.py',[]),('independent-boundary','probe.py',[]),('collect-only','collect_and_test.py',['collect']),('new-directed','collect_and_test.py',['test'])]:
 argv=[sys.executable,'-B',str(D/'guard.py'),str(D/entry),str(D/(label+'.guard.json')),*args]
 start=time.monotonic();r=subprocess.run(argv,cwd=P,capture_output=True)
 (D/(label+'.stdout.log')).write_bytes(r.stdout);(D/(label+'.stderr.log')).write_bytes(r.stderr)
 records.append({'argv':argv,'cwd':str(P),'exit_code':r.returncode,'elapsed_seconds':time.monotonic()-start,'stdout':label+'.stdout.log','stderr':label+'.stderr.log','guard':label+'.guard.json'})
 (D/'commands.json').write_text(json.dumps(records,indent=2))
 print(label,r.returncode,r.stdout.decode()[-700:],r.stderr.decode()[-1600:])
 if r.returncode:raise SystemExit(r.returncode)
