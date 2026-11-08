import asyncio,json,tempfile
from pathlib import Path
from app.runtime import OllamaRuntime
from app.errors import AppError
root=Path(tempfile.mkdtemp(prefix='lvw-native-87-review-'))
class Provider:
 async def readiness(self):return {'ready':False,'model':'gemma4:26b','reason':'OLLAMA_UNAVAILABLE','loaded':False}
class Wrapper:
 returncode=1;pid=123
 async def wait(self):return self.returncode
async def probe():
 r=OllamaRuntime(Provider(),root/'ollama.exe',root);w=Wrapper();r.process=w
 owner=root/'owner.json';r._native={'nonce':'review','owner':owner,'stop':root/'stop'}
 for owner_state in ['missing','starting','listening','exited']:
  if owner_state=='missing':owner.unlink(missing_ok=True)
  else:owner.write_text(json.dumps({'nonce':'review','pid':444,'birth_ticks':123456,'state':owner_state,'listener_owned':owner_state=='listening'}))
  for action in (r.close,r.start,r.stop) if owner_state!='exited' else (r.close,):
   try:await action();outcome='success'
   except AppError as e:outcome=e.code
   s=await r.status()
   print(json.dumps({'owner_state':owner_state,'action':action.__name__,'outcome':outcome,'process_retained':r.process is w,'native_retained':r._native is not None,'state':s['ollama']['state'],'can_start':s['actions']['can_start']}))
asyncio.run(probe())
