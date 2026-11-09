"""CPU-only controlled boundary fixture. Never starts Ollama or claims model acceptance."""
from pathlib import Path
import sys,os,asyncio
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'lvw/backend'),str(ROOT/'lvw/tests')]
from app.main import create_app
from app.config import Settings
from test_api import FakeProvider,FakeRuntime
from fastapi import HTTPException
provider=FakeProvider(ready=False)
class HeldRuntime(FakeRuntime):
    def __init__(self):
        super().__init__();self.gate=asyncio.Event();self.action=None
        self.value['protocol']='lvw.runtime/1'
    def publish(self,ready):
        provider.ready=ready
        self.value['ollama'].update(state='ready' if ready else 'stopped',reachable=ready,
            model_ready=ready,managed=ready,reason=None if ready else 'OLLAMA_UNAVAILABLE')
        self.value['actions']={'can_start':not ready,'can_reset':ready,'can_stop':ready}
    async def transition(self,action):
        self.action=action
        # Deliberately expose ready while the real AnalysisService still holds its controller lock.
        self.publish(True)
        try:
            await self.gate.wait()
            self.publish(action!='stop')
            return self.value
        finally:self.action=None
    async def start(self):return await self.transition('start')
    async def reset(self):return await self.transition('reset')
    async def stop(self):return await self.transition('stop')
runtime=HeldRuntime()
app=create_app(Settings.local(data_root=Path(os.environ['LVW_DATA_ROOT']),static_root=ROOT/'lvw/frontend/dist'),provider=provider,runtime=runtime)
@app.post('/__fixture/arm')
async def arm():
    if runtime.action:raise HTTPException(409,'fixture transition already pending')
    runtime.gate=asyncio.Event();return {'armed':True}
@app.post('/__fixture/release')
async def release():runtime.gate.set();return {'released':True}
@app.get('/__fixture/state')
async def state():return {'action':runtime.action,'ready':provider.ready,'provider_calls':provider.calls,'jobs':len(app.state.analysis.jobs),'runs':len(app.state.analysis.runs)}
# Test control routes must precede the product's catch-all static mount.
controls=[r for r in app.router.routes if getattr(r,'path','').startswith('/__fixture/')]
app.router.routes[:]=controls+[r for r in app.router.routes if r not in controls]
if __name__=='__main__':
    import uvicorn
    uvicorn.run(app,host='127.0.0.1',port=18781)
