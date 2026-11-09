import asyncio,importlib,json,os,pathlib,sys
from unittest.mock import patch
OUT=pathlib.Path(__file__).resolve().parent;BASE=OUT.parents[2]
sys.path[:0]=[str(BASE),str(BASE/'lvw/backend')]
p=importlib.import_module('app.provider')
results={}
class FakeClient:
 def __init__(self,*args,**kwargs):pass
 async def __aenter__(self):return self
 async def __aexit__(self,*args):return False
 async def post(self,*args,**kwargs):
  events.append('send-attempt');raise p.httpx.ConnectError('CPU injected connection error; no network')
def debit(*args):events.append('debit')
async def run(case,env,mode='documentary',record_failure=False):
 global events
 events=[];provider=p.OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',1)
 def record(*args,**kwargs):
  events.append('record:'+args[0])
  if record_failure:raise OSError('CPU injected evidence disk write failure')
 with patch.dict(os.environ,env,clear=True),patch('tools.local_program_authority.model_action',debit),patch.object(p.httpx,'AsyncClient',FakeClient),patch.object(provider,'_record',record):
  try:await provider._analyze_images([b'not-decoded-media'],mode=mode,content_profile='standard',custom_guidance='')
  except Exception as error:results[case]={'events':events.copy(),'error':type(error).__name__+': '+str(error)}
async def main():
 await run('required_child_absent',{'LVW_REQUIRE_BUDGET':'1'})
 await run('invalid_mode_before_send',{'LVW_REQUIRE_BUDGET':'1','LVW_AUTHORIZATION_CHILD':'fake'},mode='invalid')
 await run('connection_failure_send_attempt',{'LVW_REQUIRE_BUDGET':'1','LVW_AUTHORIZATION_CHILD':'fake'})
 await run('evidence_failure_zero_send',{'LVW_REQUIRE_BUDGET':'1','LVW_AUTHORIZATION_CHILD':'fake'},record_failure=True)
asyncio.run(main());assert 'debit' not in results['evidence_failure_zero_send']['events'];assert 'send-attempt' not in results['evidence_failure_zero_send']['events'];(OUT/'provider-results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
