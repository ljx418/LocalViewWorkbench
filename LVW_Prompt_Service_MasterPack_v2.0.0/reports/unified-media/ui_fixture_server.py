"""CPU-only UI test server. NEVER a product acceptance/provider replacement."""
from pathlib import Path
import sys,asyncio,json,os
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'lvw/backend'));sys.path.insert(0,str(ROOT/'lvw/tests'))
from app.main import create_app
from app.config import Settings
from app.errors import AppError
from test_api import FakeProvider,FakeRuntime
class Provider(FakeProvider):
    async def analyze(self,*args,**kwargs):
        await asyncio.sleep(1.1)
        if kwargs.get('custom_guidance')=='UI_FIXTURE_FAIL':
            error=AppError('PARSE_PARTIAL','UI_FIXTURE failure',status_code=503);error.raw_response='UI_FIXTURE_RAW_FAILURE';raise error
        raw,spec=await super().analyze(*args,**kwargs)
        spec.text_zh='UI_FIXTURE 建议：蓝色图形';spec.text_en='UI_FIXTURE blue geometric object';return raw,spec
    async def analyze_video(self,decoded,**kwargs):
        return await self.analyze(None,**kwargs)
p=Provider();runtime=FakeRuntime();runtime.value['protocol']='lvw.runtime/1';runtime.value['ollama'].update(state='ready',reachable=True,model_ready=True,reason=None)
runtime.value['actions']={'can_start':True,'can_stop':True,'can_reset':True}
async def stop():p.ready=False;runtime.value['ollama']['model_ready']=False;return runtime.value
async def start():p.ready=True;runtime.value['ollama']['model_ready']=True;return runtime.value
runtime.start=start;runtime.reset=start;runtime.stop=stop
app=create_app(Settings.local(data_root=Path(os.environ['LVW_DATA_ROOT']),static_root=ROOT/'lvw/frontend/dist'),provider=p,runtime=runtime)
if __name__=='__main__':
 import uvicorn
 uvicorn.run(app,host='127.0.0.1',port=18781)
