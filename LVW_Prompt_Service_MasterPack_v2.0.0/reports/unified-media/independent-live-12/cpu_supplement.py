"""Independent CPU owner checks; never invokes decoder tools, model or services."""
import sys,json,asyncio,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent/'candidate-source'
sys.path[:0]=[str(ROOT/'lvw/backend'),str(ROOT/'lvw/tests')]
import pytest
from app.video_kernel import VideoKernel,input_module,core
from app.errors import AppError
from app.main import create_app
from app.config import Settings
from test_unified_video import VideoProvider
from test_api import FakeRuntime,upload
from fastapi.testclient import TestClient

@pytest.fixture(autouse=True)
def no_external(monkeypatch):
    def deny(*a,**kw):raise AssertionError('forbidden external primitive')
    monkeypatch.setattr('app.video_kernel.process_module.run_bounded',deny)
    monkeypatch.setattr('app.resources.snapshot',snapshot)
async def snapshot():return {'gpu_used_mib':1000,'available_ram_mib':10000}

def document(**changes):
    d={'format':{'format_name':'mov,mp4','duration':'8'},'streams':[{'index':0,'codec_type':'video','width':320,'height':180,'time_base':'1/1000','start_pts':0,'duration':'8','disposition':{'attached_pic':0}}]}
    for k,v in changes.items():
        (d['format'] if k in {'format_name','duration'} else d['streams'][0])[k]=v
    return d

def test_controlled_probe_negative_owners(tmp_path,monkeypatch):
    cases=[('format_name','avi'),('duration','60.001'),('width',8294401)]
    for i,(key,value) in enumerate(cases):
        def probe(self,path,size):
            try:return input_module.validate_probe(document(**{key:value}),byte_count=size)
            except core.BridgeError as e:raise AppError(e.code,e.message,status_code=422)
        monkeypatch.setattr(VideoKernel,'probe',probe)
        p=VideoProvider();root=tmp_path/str(i);app=create_app(Settings.local(data_root=root),provider=p,runtime=FakeRuntime());c=TestClient(app)
        response=upload(c,b'controlled non-media',name='x.mp4')
        assert response.status_code==422 and not app.state.analysis.jobs and p.calls==0
        assert not list((root/'media').iterdir()) and not list((root/'video-temp').iterdir())

def test_preparing_cancel_cpu_owner(tmp_path,monkeypatch):
    import test_unified_video as t
    monkeypatch.setattr(VideoKernel,'probe',lambda self,path,size:input_module.validate_probe(document(),byte_count=size))
    # Existing test uses an already permitted input's bytes, but no probe or decode executes.
    t.FIXTURES=Path(__file__).resolve().parents[2]/'v0-s2/fixture-preparation-02/fixtures'
    t.test_preparing_cancel_waits_decoder_cleanup_before_terminal(tmp_path,monkeypatch)

def test_less_frames_manifest_owner():
    import hashlib
    probe=input_module.validate_probe(document(),byte_count=10)
    values=[(1000,320,180,b'first'),(3000,320,180,b'second')]
    result=input_module.frame_manifest(probe,values)
    assert len(result)==2 and [x['time_seconds'] for x in result]==[1,3]
    assert [x['sha256'] for x in result]==[hashlib.sha256(x[3]).hexdigest() for x in values]
    with pytest.raises(core.BridgeError):input_module.frame_manifest(probe,[])
    with pytest.raises(core.BridgeError):input_module.frame_manifest(probe,[values[0],values[0]])

def test_frozen_input_exact_one_over_and_empty(tmp_path,monkeypatch):
    assert input_module.validate_probe(document(duration='60'),byte_count=256*1024*1024).duration==60
    assert input_module.validate_probe(document(width=3840,height=2160),byte_count=1).width==3840
    for doc,count in [(document(),256*1024*1024+1),(document(duration='60.001'),1),(document(width=8294401,height=1),1),(document(format_name='avi'),1)]:
        with pytest.raises(core.BridgeError):input_module.validate_probe(doc,byte_count=count)
    p=VideoProvider();app=create_app(Settings.local(data_root=tmp_path),provider=p,runtime=FakeRuntime());c=TestClient(app)
    for name in ['empty.mp4','empty.png']:
        response=upload(c,b'',name=name,key=name)
        assert response.status_code==422 and response.json()['error']['code']=='MEDIA_INVALID'
    assert not app.state.analysis.jobs and p.calls==0
    assert not list((tmp_path/'media').iterdir()) and not list((tmp_path/'video-temp').iterdir())
