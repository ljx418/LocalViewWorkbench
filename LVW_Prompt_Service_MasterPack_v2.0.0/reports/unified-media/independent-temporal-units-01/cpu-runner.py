import os,socket,subprocess,sys
os.environ.pop("LVW_AUTHORIZATION_CHILD",None)
os.environ.pop("LVW_REQUIRE_BUDGET",None)
def deny(*a,**k):raise AssertionError("Independent CPU review forbids network/process execution")
socket.socket.connect=deny
socket.socket.connect_ex=deny
subprocess.Popen=deny
import pytest
sys.exit(pytest.main(["-q","-p","no:cacheprovider","lvw/tests/test_provider.py"]))
