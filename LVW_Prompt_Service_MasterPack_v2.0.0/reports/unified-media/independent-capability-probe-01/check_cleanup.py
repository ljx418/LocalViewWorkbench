"""CPU-only AST extraction: execute only cleanup block using inert mocks."""
import ast,asyncio,json,hashlib
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];OUT=Path(__file__).resolve().parent
source=ROOT/'reports/unified-media/model_capability_probe.py'
tree=ast.parse(source.read_text());main=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='main')
cleanup=next(n for n in main.body if isinstance(n,ast.Try)).finalbody[0]
assert isinstance(cleanup,ast.Try)
fn=ast.AsyncFunctionDef(name='check',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=[cleanup],decorator_list=[])
module=ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[]))
async def close():pass
class AbsentTemp:
 def exists(self):return False
class Program:
 def __init__(self):self.calls=[]
 def settle(self,run,count):self.calls.append(['settle',run,count]);return {}
 def close_retaining_reservation(self,run):self.calls.append(['retain',run])
results=[]
for label,states in [('clear',[False,False]),('external_listener_race',[False,True])]:
 sequence=iter(states);program=Program();result={}
 namespace={'asyncio':asyncio,'runtime':SimpleNamespace(close=close),'temp':AbsentTemp(),'listening':lambda:next(sequence),'result':result,'program':program,'run':'mock-zero-model','json':json}
 exec(compile(module,str(source),'exec'),namespace)
 asyncio.run(namespace['check']())
 results.append({'case':label,'cleanup_result':result,'program_calls':program.calls})
output={'harness_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'results':results,'real_harness_executed':False,'network':False,'model_calls':0,'ledger_writes':False}
(OUT/'cleanup-mock-results.json').write_text(json.dumps(output,indent=2)+'\n')
print(json.dumps(output,indent=2))
