import asyncio,json,tempfile
from pathlib import Path
from unittest.mock import patch
import httpx
from app.provider import OllamaProvider
from app.media import MediaStore
from app.service import AnalysisService
from app.models import AnalyzeRequest
from fastapi import UploadFile
from io import BytesIO
from PIL import Image

async def scenario():
    real=httpx.AsyncClient
    async def handler(request):return httpx.Response(200,text='RAW MALFORMED RESPONSE',request=request)
    root=Path(tempfile.mkdtemp(prefix='lvw-review-'))
    store=MediaStore(root); b=BytesIO();Image.new('RGB',(2,2)).save(b,format='PNG')
    m=await store.ingest(UploadFile(filename='x.png',file=BytesIO(b.getvalue())))
    provider=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',1)
    # No lease hardware probe: only exercise real HTTP parser and real publication.
    async def acquire(_):pass
    async def release(_):return True
    async def snapshot():return {'gpu_used_mib':1,'available_ram_mib':9999}
    provider.acquire=acquire;provider.release=release
    service=AnalysisService(store,provider); body=AnalyzeRequest(media_ref_id=m.id,mode='realistic',config_profile='local-default')
    job=service.submit(body,'raw')
    with patch('app.provider.httpx.AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(handler))),patch('app.resources.snapshot',snapshot):
        await service.run(job.id,body)
    print('invalid_envelope_publication',json.dumps(service.get_job(job.id).model_dump()))
    print('retained_runs',len(service.runs))

asyncio.run(scenario())
