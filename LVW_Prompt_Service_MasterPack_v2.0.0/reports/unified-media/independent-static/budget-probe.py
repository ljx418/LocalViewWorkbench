import asyncio
from types import SimpleNamespace
from unittest.mock import patch
from app.provider import OllamaProvider
async def scenario():
 p=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',120)
 p._lease=('review-job',{'gpu_used_mib':1000});p._sent=False
 clock=[0];events=[]
 async def inventory():
  clock[0]+=31;events.append('inventory_returned_at_31');return ['still-loaded']
 async def snapshot():events.append('snapshot_after_deadline');return {'gpu_used_mib':1000}
 p._inventory=inventory
 with patch('app.provider.time',SimpleNamespace(monotonic=lambda:clock[0])),patch('app.resources.snapshot',snapshot):
  result=await p.release('review-job')
 print({'release_budget_seconds':30,'virtual_seconds_at_end':clock[0],'released':result,'lease_retained':p._lease is not None,'events':events})
asyncio.run(scenario())
