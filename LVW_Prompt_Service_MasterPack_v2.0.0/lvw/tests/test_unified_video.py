from __future__ import annotations
import asyncio
from pathlib import Path
import subprocess
import sys
import os
import httpx
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.models import AnalyzeRequest
from test_api import FakeProvider, FakeRuntime, upload
from test_contract import validate_response
ROOT=Path(__file__).resolve().parents[2]
FIXTURES=ROOT/'reports/v0-s2/fixture-preparation-02/fixtures'
class VideoProvider(FakeProvider):
    async def analyze_video(self, decoded, **options):
        self.decoded=decoded
        return await super().analyze(None, **options)
def client(tmp_path, provider=None):
    return TestClient(create_app(Settings.local(data_root=tmp_path),provider=provider or VideoProvider(),runtime=FakeRuntime()))
def test_video_public_upload_analyze_contract_and_real_pts(tmp_path):
    provider=VideoProvider();c=client(tmp_path,provider)
    u=upload(c,(FIXTURES/'vfr.mp4').read_bytes(),name='scene.mp4')
    assert u.status_code==201,u.text
    validate_response('/api/v1/media','post','201',u.json())
    media=u.json()['data'];assert media['kind']=='video' and media['duration_seconds']==8
    submit=c.post('/api/v1/jobs/analyze',headers={'Idempotency-Key':'video'},json={'media_ref_id':media['id'],'mode':'realistic','config_profile':'local-default'})
    job=c.get('/api/v1/jobs/'+submit.json()['data']['id']).json()['data'];assert job['status']=='succeeded'
    run=c.get('/api/v1/model-runs/'+job['result_ref']).json();validate_response('/api/v1/model-runs/{id}','get','200',run)
    value=run['data'];assert value['input_sha256']==media['sha256'] and len(value['frames'])==4
    assert [x['source_pts'] for x in value['frames']]==[14336,38912,63488,87040]
    assert provider.calls==1 and list((tmp_path/'video-temp').iterdir())==[]
def test_video_public_rejections_happen_before_model_and_leave_no_files(tmp_path):
    provider=VideoProvider();c=client(tmp_path,provider)
    for i,name in enumerate(['over-duration.mp4','fake-extension.mp4','corrupt.mp4','truncated.mov']):
        response=upload(c,(FIXTURES/name).read_bytes(),key=str(i),name=name)
        assert response.status_code==422,(name,response.text)
    assert provider.calls==0 and list((tmp_path/'media').iterdir())==[] and list((tmp_path/'video-temp').iterdir())==[]
def test_capabilities_and_same_origin_control(tmp_path):
    c=client(tmp_path);assert c.get('/api/v1/capabilities').json()['data']['media']==['image','video']
    assert c.post('/api/v1/runtime/ollama/start',headers={'Origin':'http://evil.example','X-LVW-Control':'local-ui'}).status_code==403
    assert c.post('/api/v1/jobs/missing/cancel',headers={'Idempotency-Key':'c'}).status_code==403
    assert c.post('/api/v1/jobs/missing/cancel',headers={'Idempotency-Key':'c','X-LVW-Control':'local-ui'}).status_code==404

def test_decoder_has_no_comfy_torch_numpy_import():
    r=subprocess.run([sys.executable,'-B','-c',"import app.video_kernel,sys; assert not {'server','folder_paths','torch','numpy'} & set(sys.modules)"],env={**os.environ,'PYTHONPATH':str(ROOT/'lvw/backend')},capture_output=True)
    assert r.returncode==0,r.stderr.decode()

def test_queued_cancel_is_idempotent_and_never_calls_provider(tmp_path,png_bytes):
    async def scenario():
        p=VideoProvider();app=create_app(Settings.local(data_root=tmp_path),provider=p,runtime=FakeRuntime())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1') as c:
            u=await c.post('/api/v1/media',headers={'Idempotency-Key':'u'},files={'file':('a.png',png_bytes,'image/png')})
            service=app.state.analysis;body=AnalyzeRequest(media_ref_id=u.json()['data']['id'],mode='realistic',config_profile='local-default');j=service.submit(body,'queued')
            for i in range(2):
                r=await c.post(f'/api/v1/jobs/{j.id}/cancel',headers={'Idempotency-Key':'c','X-LVW-Control':'local-ui'});validate_response('/api/v1/jobs/{id}/cancel','post','200',r.json());assert r.json()['data']['cancel_epoch']==1
            await service.run(j.id,body);assert service.get_job(j.id).status=='cancelled' and p.calls==0
    asyncio.run(scenario())

def test_cancel_during_provider_rejects_success_after_cancel(tmp_path,png_bytes,monkeypatch):
    async def fixed_snapshot():return {"gpu_used_mib":1000,"available_ram_mib":10000}
    monkeypatch.setattr("app.resources.snapshot",fixed_snapshot)
    class Delayed(VideoProvider):
        def __init__(self):super().__init__();self.started=asyncio.Event();self.released=False
        async def acquire(self,_):pass
        async def release(self,_):self.released=True;return True
        def _record(self,*_,**__):pass
        async def analyze(self,*args,**kwargs):
            self.started.set()
            try:await asyncio.sleep(20)
            except asyncio.CancelledError:pass
            return await super().analyze(*args,**kwargs)
    async def scenario():
        p=Delayed();app=create_app(Settings.local(data_root=tmp_path),provider=p,runtime=FakeRuntime())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1') as c:
            u=await c.post('/api/v1/media',headers={'Idempotency-Key':'u'},files={'file':('a.png',png_bytes,'image/png')})
            submit=asyncio.create_task(c.post('/api/v1/jobs/analyze',headers={'Idempotency-Key':'a'},json={'media_ref_id':u.json()['data']['id'],'mode':'realistic','config_profile':'local-default'}))
            await p.started.wait();id=next(iter(app.state.analysis.jobs));r=await c.post(f'/api/v1/jobs/{id}/cancel',headers={'Idempotency-Key':'c','X-LVW-Control':'local-ui'});assert r.json()['data']['status']=='cancelling'
            await submit;j=(await c.get('/api/v1/jobs/'+id)).json()['data'];assert j['status']=='cancelled' and j['result_ref'] is None and p.released;assert app.state.analysis.runs=={}
    asyncio.run(scenario())

def test_unproven_release_is_unknown_not_success(tmp_path,png_bytes,monkeypatch):
    async def fixed_snapshot():return {"gpu_used_mib":1000,"available_ram_mib":10000}
    monkeypatch.setattr("app.resources.snapshot",fixed_snapshot)
    class Unreleased(VideoProvider):
        async def acquire(self,_):pass
        async def release(self,_):return False
        def _record(self,*_,**__):pass
    c=client(tmp_path,Unreleased());m=upload(c,png_bytes).json()['data'];s=c.post('/api/v1/jobs/analyze',headers={'Idempotency-Key':'a'},json={'media_ref_id':m['id'],'mode':'realistic','config_profile':'local-default'})
    j=c.get('/api/v1/jobs/'+s.json()['data']['id']).json()['data'];assert j['status']=='failed' and j['resource_state']=='unknown' and j['error_code']=='RESOURCE_RELEASE_PENDING'
    if j['result_ref']:assert c.get('/api/v1/model-runs/'+j['result_ref']).json()['data']['parsed_spec'] is None

def test_streamed_http_body_cap_catches_missing_or_false_content_length(tmp_path,monkeypatch):
    monkeypatch.setattr('app.main.MAX_UPLOAD_REQUEST_BYTES',1024)
    async def scenario():
        app=create_app(Settings.local(data_root=tmp_path),provider=VideoProvider(),runtime=FakeRuntime())
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1') as c:
            async def body():
                prefix=b'--abc\r\nContent-Disposition: form-data; name="file"; filename="x.mp4"\r\nContent-Type: video/mp4\r\n\r\n'
                yield prefix+b'x'*(1024-len(prefix))
                yield b'x\r\n--abc--\r\n'
            r=await c.post('/api/v1/media',headers={'Idempotency-Key':'x','Content-Type':'multipart/form-data; boundary=abc','Content-Length':'999'},content=body())
            assert r.status_code==422 and r.json()['error']['code']=='MEDIA_LIMIT_EXCEEDED'
            assert list((tmp_path/'media').iterdir())==[]
    asyncio.run(scenario())

def test_total_analysis_deadline_covers_acquisition_before_any_inference(tmp_path,png_bytes,monkeypatch):
    monkeypatch.setattr('app.service.ANALYSIS_SECONDS',.02)
    class SlowAcquire(VideoProvider):
        async def acquire(self,_):await asyncio.sleep(20)
    c=client(tmp_path,SlowAcquire());m=upload(c,png_bytes).json()['data'];s=c.post('/api/v1/jobs/analyze',headers={'Idempotency-Key':'deadline'},json={'media_ref_id':m['id'],'mode':'realistic','config_profile':'local-default'})
    j=c.get('/api/v1/jobs/'+s.json()['data']['id']).json()['data']
    assert j['status']=='failed' and j['error_code']=='MODEL_TIMEOUT' and j['result_ref'] is None
