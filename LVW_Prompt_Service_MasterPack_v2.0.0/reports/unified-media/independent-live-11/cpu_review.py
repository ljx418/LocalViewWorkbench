import os,sys,socket,subprocess,types,importlib.machinery
from pathlib import Path
R=Path(__file__).resolve().parent/'candidate-source'
os.chdir(R)
os.environ.pop('LVW_AUTHORIZATION_CHILD',None);os.environ.pop('LVW_REQUIRE_BUDGET',None)
sys.path.insert(0,str(R));sys.path.insert(0,str(R/'lvw/backend'));sys.path.insert(0,str(R/'lvw/tests'))
def deny(*a,**k):raise AssertionError('Independent CPU audit forbids external process/socket')
socket.socket.connect=deny;socket.socket.connect_ex=deny;subprocess.Popen=deny
name='LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge'
p=types.ModuleType(name);p.__path__=[str(R/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge')];p.__spec__=importlib.machinery.ModuleSpec(name,loader=None,is_package=True);sys.modules[name]=p;p.NODE_CLASS_MAPPINGS={} # registration not exercised; only test helper import needs this name
import pytest
sys.exit(pytest.main(['-q','-p','no:cacheprovider','lvw/tests/test_provider.py','lvw/tests/test_unified_video.py','LVW_V0_RuntimePatch/tests/test_s2_video_input.py','LVW_V0_RuntimePatch/tests/test_s2_video_files.py','LVW_V0_RuntimePatch/tests/test_s2_video_decoder.py','-k','not public_upload_analyze_contract_and_real_pts and not public_rejections_happen_before_model and not decoder_has_no_comfy_torch_numpy_import and not preparing_cancel_waits_decoder_cleanup']))
