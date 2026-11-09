import asyncio,json,os,sys
from pathlib import Path
R=Path.cwd();sys.path[:0]=[str(R),str(R/'lvw/backend')]
import httpx
import app.provider as p
from tools import local_program_authority as program
os.environ['LVW_REQUIRE_BUDGET']='1';os.environ['LVW_AUTHORIZATION_CHILD']='fake-child';os.environ.pop('LVW_PROVIDER_LEDGER',None)
events=[];capabilities=[];real=httpx.AsyncClient
program.model_action=lambda _:events.append('debit')
async def handler(req):
    events.append(req.url.path)
    if req.url.path=='/api/show':return httpx.Response(200,json={'capabilities':capabilities})
    assert events[-2:] == ['debit','/api/chat']
    payload=json.loads(req.content);assert payload['think'] is True
    return httpx.Response(200,json={'done':False,'message':{'content':'','thinking':'synthetic-not-persisted'}})
p.httpx.AsyncClient=lambda **kw:real(**kw,transport=httpx.MockTransport(handler))
async def invoke():
    try:await p.OllamaProvider('http://127.0.0.1:11434/api/chat','synthetic',30)._analyze_images([b'synthetic'],mode='realistic',content_profile='standard',custom_guidance='',thinking=True)
    except p.AppError:return
    raise AssertionError('expected capability or partial parse rejection')
asyncio.run(invoke());assert events==['/api/show']
capabilities.append('thinking');asyncio.run(invoke());assert events==['/api/show','/api/show','debit','/api/chat']
print(json.dumps({'events':events,'unsupported_zero_debits_and_chats':True,'supported_debit_before_chat':True,'real_network_ledger_model_actions':0},indent=2))
