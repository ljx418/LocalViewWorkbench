import asyncio,time
from types import SimpleNamespace
from unittest.mock import patch
from app.provider import OllamaProvider
async def scenario():
 p=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',120);p._lease=('job',{'gpu_used_mib':1});p._sent=False
 async def inventory():await asyncio.sleep(20);return []
 p._inventory=inventory
 original_timeout=asyncio.timeout
 started=time.monotonic()
 with patch('app.provider.asyncio',SimpleNamespace(timeout=lambda _:original_timeout(.02),sleep=asyncio.sleep)):
  result=await p.release('job')
 print({'shortened_outer_timeout_seconds':.02,'elapsed_seconds':round(time.monotonic()-started,3),'released':result,'lease_retained':p._lease is not None})
asyncio.run(scenario())
