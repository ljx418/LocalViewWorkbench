"""Production owners; substitute only HTTP/Windows, retain real fixture SQLite."""
import copy
import hashlib
import json
import subprocess
import sys
import time
from types import SimpleNamespace
import pytest
from tools.test_v0_s3_budget_authority import Fixture, fixture
from tools.v0_s2_runtime import NativeRuntime
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import core, program_budget as budget, benchmark, video_evidence, video_transport

class Response:
    status=200
    def __init__(self,raw):self.raw=raw
    def read(self):return self.raw
    def read1(self,n):raw=self.raw[:n];self.raw=self.raw[n:];return raw
    def close(self):pass
    def __enter__(self):return self
    def __exit__(self,*args):pass

def response(body):
    payload=json.loads(body)
    if 'messages' not in payload:return Response(b'{"done":true}')
    value={'observations':['red shape'],'inferences':[],'unknowns':[],'prompt':'red shape','tags':[]}
    if 'change' in payload['format']['properties']:value['change']='unchanged'
    return Response(json.dumps({'done':True,'done_reason':'stop','message':{'content':json.dumps(value)}}).encode())

def transport(monkeypatch,f,kind,sends):
    def sent(body):
        if 'messages' in json.loads(body):
            sends.append(body);assert f.row()['calls']==len(sends)
        return response(body)
    if kind=='default':
        t=core.OllamaLoopbackTransport()
        monkeypatch.setattr(t._opener,'open',lambda request,**kw:sent(request.data))
        return t
    class Socket:
        def dup(self):return self
        def settimeout(self,n):pass
        def close(self):pass
        def shutdown(self,*a):pass
    class Connection:
        debuglevel=0
        def __init__(self,*a,**kw):self.sock=Socket()
        def connect(self):pass
        def request(self,method,path,body,headers):self.response=sent(body)
        def getresponse(self):return self.response
        def close(self):pass
    monkeypatch.setattr(video_transport.http.client,'HTTPConnection',Connection)
    t=video_transport.InterruptibleOllamaTransport()
    monkeypatch.setattr(t,'cleanup',lambda *a,**kw:None)
    return t

@pytest.mark.parametrize('kind',['default','interruptible'])
@pytest.mark.parametrize('frames',[1,4])
def test_owner_one_image_four_frames_no_double_debit(fixture,monkeypatch,kind,frames):
    fixture.enable(monkeypatch);sends=[];t=transport(monkeypatch,fixture,kind,sends)
    owner=core.BridgeOwner(transport=t,encoder=lambda frame:'synthetic-no-media')
    frame=SimpleNamespace(shape=(2,2,3))
    options={'model':'gemma4:26b','user_instruction':'','mode':'realistic','timeout_seconds':120}
    if frames==1:owner.analyze_image([frame],**options)
    else:owner.analyze_video([frame]*4,**options)
    assert len(sends)==fixture.row()['calls']==frames

def test_preload_separate_action_and_exact_wire_bytes(fixture,monkeypatch):
    fixture.enable(monkeypatch)
    runtime=object.__new__(NativeRuntime);runtime.preloads=0;runtime.resource_abort_latched=False;runtime.resource_observer=object()
    sends=[];receipts=[];original=budget.authorize_model_action
    def authorize(*a,**kw):
        result=original(*a,**kw);receipts.append(result);return result
    monkeypatch.setattr(budget,'authorize_model_action',authorize)
    def send(url,*,payload,**kw):
        sends.append(payload);assert fixture.row()['calls']==1
        assert receipts[0]['action_kind']=='preload'
        assert receipts[0]['payload_sha256']==hashlib.sha256(json.dumps(payload,allow_nan=False).encode()).hexdigest()
        return 200,{'done':True}
    runtime._json_request=send
    runtime.preload('gemma4:26b',s3_budget_binding=fixture.ref)
    assert len(sends)==1

@pytest.mark.parametrize('kind',['default','interruptible','preload'])
@pytest.mark.parametrize('fault',['missing','bad_hash','wrong_nonce','bad_json','exit_error','exit_zero_error','lost_receipt','timeout','overflow'])
def test_send_boundaries_fail_closed(fixture,monkeypatch,kind,fault):
    f=fixture;f.enable(monkeypatch);sends=[]
    if fault=='missing':monkeypatch.delenv('LVW_S3_BUDGET_BINDING')
    elif fault=='bad_hash':monkeypatch.setenv('LVW_S3_BUDGET_BINDING_SHA256','0'*64)
    else:
        original=budget._exchange
        def exchange(command,raw,timeout):
            if fault in ('timeout','overflow'):
                code='import time; time.sleep(30)' if fault=='timeout' else 'import sys; sys.stdout.buffer.write(b"x"*100000); sys.stdout.flush()'
                return original([sys.executable,'-I','-B','-c',code],raw,.15)
            output,process=original(command,raw,timeout)
            if fault=='wrong_nonce':value=json.loads(output);value['request_id']='0'*36;output=json.dumps(value).encode()
            elif fault=='bad_json':output=b'not-json'
            elif fault=='exit_error':
                return original([sys.executable,'-I','-B','-c','import sys; sys.stdout.write(sys.argv[1]); sys.stderr.write("owned failure"); sys.exit(7)',output.decode()],raw,timeout)
            elif fault=='exit_zero_error':process['error']='PIPE_ERROR'
            elif fault=='lost_receipt':output=b''
            return output,process
        monkeypatch.setattr(budget,'_exchange',exchange)
    if kind=='preload':
        runtime=object.__new__(NativeRuntime);runtime.preloads=0;runtime.resource_abort_latched=False;runtime.resource_observer=object()
        runtime._json_request=lambda *a,**k:sends.append(k)
        action=lambda:runtime.preload('gemma4:26b')
    else:
        t=transport(monkeypatch,f,kind,sends)
        action=lambda:t.chat({'model':'gemma4:26b','messages':[]},10)
    with pytest.raises(core.BridgeError):action()
    assert sends==[]
    assert f.row()['calls']==(0 if fault in ('missing','bad_hash','timeout','overflow') else 1)
    assert f.row()['active']==1

def test_owned_timeout_reaps_and_joins_and_preserves_exit(monkeypatch):
    original=subprocess.Popen;children=[]
    def launch(*args,**kw):
        child=original(*args,**kw);children.append(child);return child
    monkeypatch.setattr(budget.subprocess,'Popen',launch)
    output,result=budget._exchange([sys.executable,'-I','-B','-c','import time; time.sleep(30)'],b'{}',.1)
    assert result['error']=='TIMEOUT' and result['exit_code']!=0
    assert result['reaped'] and result['readers_joined'] and children[0].poll() is not None
    assert all(p.closed for p in (children[0].stdin,children[0].stdout,children[0].stderr))

def profile(f,scope):
    b=f.config
    return {'program_authorization_id':budget.PROGRAM,'scope':scope,'candidate_sha':b['candidate_sha'],
        'authorization_sha256':b['child_sha256'],'child_sha256':b['child_sha256'],'child_path':b['child_path'],
        'run_id':b['run_id'],'budget_binding_sha256':f.ref['sha256'],'model_digest':b['model_digest'],
        'ollama_pid':b['ollama_pid'],'ollama_start_ticks':b['ollama_start_ticks'],
        'issued_at':b['issued_at'],'expires_at':b['expires_at'],'max_runs':64,'max_requests':20,'baseline_gpu_mib':100}

@pytest.mark.parametrize('scope',['V0_S3_NATIVE_CHECKPOINT','V0_S3_WARM_BENCHMARK'])
def test_profile_exact_binding_and_legacy_lifetime(fixture,monkeypatch,scope):
    f=fixture;f.enable(monkeypatch);p=profile(f,scope)
    validator=video_evidence.validate_binding if 'NATIVE' in scope else benchmark.validate_binding
    validator(p,time.time())
    for key in ('child_path','child_sha256','candidate_sha','model_digest','ollama_pid','ollama_start_ticks','budget_binding_sha256','run_id'):
        changed=copy.deepcopy(p);changed[key]=0 if isinstance(p[key],int) else 'bad'
        with pytest.raises(core.BridgeError):validator(changed,time.time())
    for key,value in [('max_runs',65),('max_requests',21),('expires_at',f.config['expires_at']+1)]:
        if (key=='max_runs' and 'WARM' in scope) or (key=='max_requests' and 'NATIVE' in scope):continue
        with pytest.raises(core.BridgeError):validator(dict(p,**{key:value}),time.time())
    legacy=dict(p,program_authorization_id='AUTH-PROGRAM-V1-LOCAL-01',scope=scope.replace('S3','S2'))
    validator(legacy,time.time())
    with pytest.raises(core.BridgeError):validator(dict(legacy,expires_at=legacy['issued_at']+7201),time.time())

def test_profile_generation_binds_child_and_owner(fixture,monkeypatch,tmp_path):
    f=fixture;f.enable(monkeypatch)
    runtime=object.__new__(NativeRuntime)
    runtime.owned_listener_birth=lambda port:{'pid':123,'start_ticks':456}
    runtime.native_clock=lambda:{'wall_seconds':time.time()}
    root=tmp_path/'native';(root/'temp').mkdir(parents=True)
    common={'candidate_sha':f.config['candidate_sha'],'authorization_sha256':f.config['child_sha256'],'model_digest':f.config['model_digest'],'s3_budget_binding':f.ref}
    p=runtime.write_native_binding(root,max_runs=64,**common);video_evidence.validate_binding(p,time.time())
    p=runtime.write_warm_binding(root,nvidia_sha256='c'*64,baseline_gpu_mib=100,**common);benchmark.validate_binding(p,time.time())
    runtime.owned_listener_birth=lambda port:{'pid':999,'start_ticks':456}
    with pytest.raises(ValueError):runtime.write_native_binding(root,max_runs=64,**common)

def test_active_s3_profile_requires_binding_without_flag(fixture,monkeypatch,tmp_path):
    for name in ('LVW_S3_BUDGET_REQUIRED','LVW_S3_BUDGET_BINDING','LVW_S3_BUDGET_BINDING_SHA256'):monkeypatch.delenv(name,raising=False)
    monkeypatch.setenv('LVW_NATIVE_CHECKPOINT','run-owned-v1')
    monkeypatch.setitem(sys.modules,'folder_paths',SimpleNamespace(get_temp_directory=lambda:str(tmp_path)))
    (tmp_path/'lvw-native-profile.json').write_text(json.dumps(profile(fixture,'V0_S3_NATIVE_CHECKPOINT')))
    with pytest.raises(core.BridgeError):budget.authorize_model_action('chat',b'{"model":"gemma4:26b"}')

def test_no_s3_ordinary_use_and_rejected_media_do_not_debit(fixture,monkeypatch):
    for name in ('LVW_S3_BUDGET_REQUIRED','LVW_S3_BUDGET_BINDING','LVW_NATIVE_CHECKPOINT','LVW_WARM_BENCHMARK'):monkeypatch.delenv(name,raising=False)
    assert budget.authorize_model_action('chat',b'{}') is None
    fixture.enable(monkeypatch)
    owner=core.BridgeOwner(encoder=lambda frame:'unused')
    with pytest.raises(core.BridgeError):owner.analyze_image([],model='gemma4:26b',user_instruction='',mode='realistic',timeout_seconds=120)
    assert fixture.row()['calls']==0

def test_windows_command_is_fixed_and_no_shell(fixture,monkeypatch):
    b=copy.deepcopy(fixture.config);b['transport']='wsl';b['distribution']='Frozen-WSL'
    b['tools']['wsl']={'path':'/sealed/wsl.exe','client_path':r'C:\Windows\System32\wsl.exe','sha256':'c'*64}
    monkeypatch.setattr(budget.os,'name','nt');monkeypatch.setattr(budget,'digest',lambda p:'c'*64)
    assert budget._command(b)==[b['tools']['wsl']['client_path'],'-d','Frozen-WSL','--exec',b['tools']['python']['path'],'-I','-B',b['tools']['shim']['path']]


def test_s3_long_profile_preserves_per_child_ceiling(tmp_path,monkeypatch):
    import shutil
    f=Fixture(tmp_path/'long-authority',seconds=21600)
    try:
        f.enable(monkeypatch)
        for scope,validator in [('V0_S3_NATIVE_CHECKPOINT',video_evidence.validate_binding),('V0_S3_WARM_BENCHMARK',benchmark.validate_binding)]:
            value=profile(f,scope);validator(value,time.time())
            assert value['expires_at']-value['issued_at']>7200
            with pytest.raises(core.BridgeError):validator(dict(value,expires_at=value['issued_at']+21601),time.time())
        f.shim.debit(f.request());assert f.row()['calls']==1
    finally:shutil.rmtree(f.root)


def test_wsl_harness_uses_authority_path_and_fixed_local_command(fixture,monkeypatch):
    f=fixture;b=f.config
    b['transport']='wsl';b['harness_transport']='local-wsl';b['distribution']='Frozen-WSL'
    b['client_binding_path']=r'C:\owned\binding.json'
    b['tools']['wsl']={'path':'/sealed/wsl.exe','client_path':r'C:\Windows\System32\wsl.exe','sha256':'c'*64}
    f.save()
    loaded,_=budget.load_binding(f.ref)
    assert loaded['client_binding_path']!=loaded['binding_path']
    assert budget._command(loaded)==[b['tools']['python']['path'],'-I','-B',b['tools']['shim']['path']]


def test_cancel_after_debit_retains_charge_without_send(fixture,monkeypatch):
    import threading
    f=fixture;f.enable(monkeypatch);sends=[];t=transport(monkeypatch,f,'interruptible',sends)
    cancelled=threading.Event();t.bind_cancel(cancelled);original=budget.authorize_model_action
    def authorize(*a,**kw):
        receipt=original(*a,**kw);cancelled.set();return receipt
    monkeypatch.setattr(budget,'authorize_model_action',authorize)
    with pytest.raises(core.BridgeError):t.chat({'model':'gemma4:26b','messages':[]},10)
    assert sends==[] and f.row()['calls']==1 and f.row()['active']==1
