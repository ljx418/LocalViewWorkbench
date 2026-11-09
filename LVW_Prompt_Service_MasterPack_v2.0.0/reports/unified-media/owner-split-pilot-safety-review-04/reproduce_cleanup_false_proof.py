from pathlib import Path
import ast, asyncio, json
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3]
pilot=ROOT/'reports/unified-media/public_owner_pilot.py'
tree=ast.parse(pilot.read_text())
main=next(n for n in tree.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='main')
body=next(n for n in main.body if isinstance(n,ast.Try)).finalbody
mod=ast.Module(body=[ast.AsyncFunctionDef(name='check',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=body,decorator_list=[])],type_ignores=[])
ast.fix_missing_locations(mod)
class P:
 def __truediv__(self,v):return self
 def exists(self):return False
 def write_text(self,v):return len(v)
class A:
 async def close(self):raise RuntimeError('analysis worker cleanup not proved')
class R:
 process=None
 _native=None
 async def close(self):pass
ops=[]
program=SimpleNamespace(settle=lambda run,n:(ops.append(('settle',n)) or {'settled':True}),close_retaining_reservation=lambda run:ops.append(('retain',run)))
ns=dict(asyncio=asyncio,result={'decision':'NO_GO'},provider=SimpleNamespace(_lease=None),app=SimpleNamespace(state=SimpleNamespace(analysis=A())),runtime=R(),temp=P(),temp_claimed=True,out=P(),reserved=True,program=program,run='fake',child={},json=json,listening=lambda:False)
exec(compile(mod,'original-finally','exec'),ns)
asyncio.run(ns['check']())
print(json.dumps({'result':ns['result'],'budget_operations':ops},indent=2))
assert ns['result'].get('cleanup_proven') is True and ops==[('settle',0)], 'expected original cleanup bug no longer reproduced; review fix'
