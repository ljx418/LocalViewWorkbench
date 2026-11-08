import pytest
from types import SimpleNamespace
@pytest.fixture(autouse=True)
def block_media_probe_for_preparing_barrier(request,monkeypatch):
    if request.node.name=='test_preparing_cancel_waits_decoder_cleanup_before_terminal':
        monkeypatch.setattr('app.video_kernel.VideoKernel.probe',lambda self,path,size:SimpleNamespace(width=320,height=192,duration=8))
