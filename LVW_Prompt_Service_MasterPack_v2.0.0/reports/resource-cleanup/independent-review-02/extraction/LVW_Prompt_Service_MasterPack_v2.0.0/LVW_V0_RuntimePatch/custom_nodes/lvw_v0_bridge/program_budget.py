"""Internal, sealed S3 debit capability. No retries and no public command API."""
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath, PurePosixPath
import re
import subprocess
import threading
import time
import uuid

PROGRAM = 'AUTH-PROGRAM-V1-COMPLETE-03'
SCOPES = {'V0_S3_NATIVE_CHECKPOINT', 'V0_S3_WARM_BENCHMARK'}
LIMIT = 32768
FIELDS = set('schema program approval_sha256 run_id stage_id candidate_sha child_path child_sha256 ledger_path execution_path execution_sha256 authority_root tools issued_at expires_at transport harness_transport distribution binding_path client_binding_path model model_digest ollama_pid ollama_start_ticks'.split())
ROLES = {'authority', 'shim', 'python', 'wsl'}


def refused(reason, **details):
    from .core import BridgeError
    return BridgeError('SCOPE_FORBIDDEN', 'S3 model debit refused', subcode=reason, details=details)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def read_json(path, expected):
    with Path(path).open('rb') as stream: raw = stream.read(LIMIT + 1)
    if len(raw) > LIMIT or hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError('sealed JSON hash/size mismatch')
    return decode(raw)


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value: raise ValueError('duplicate JSON key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def validate_config(b, now=None, *, allow_expired=False):
    now = time.time() if now is None else now
    if not isinstance(b, dict) or set(b) != FIELDS: raise ValueError('binding schema fields')
    if b['schema'] != 'lvw.s3-budget/1' or b['program'] != PROGRAM or b['stage_id'] != 'V0-S3':
        raise ValueError('binding scope')
    for key, length in [('candidate_sha',40), ('approval_sha256',64), ('child_sha256',64), ('execution_sha256',64), ('model_digest',64)]:
        if not isinstance(b[key],str) or not re.fullmatch('[0-9a-f]{%d}' % length,b[key]): raise ValueError('binding digest')
    if not isinstance(b['run_id'],str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}',b['run_id']): raise ValueError('run identity')
    if not isinstance(b['model'],str) or not b['model'] or len(b['model'])>128: raise ValueError('model identity')
    if any(type(b[k]) is not int or b[k]<=0 for k in ('ollama_pid','ollama_start_ticks')): raise ValueError('owner identity')
    issued, expires = b['issued_at'], b['expires_at']
    if (any(type(v) not in (int,float) or not math.isfinite(v) for v in (issued,expires,now))
            or not 0 < expires-issued <= 21600 or now < issued or (not allow_expired and now >= expires)):
        raise ValueError('binding lifetime')
    for key in ('child_path','ledger_path','execution_path','authority_root','binding_path'):
        if not isinstance(b[key],str) or not b[key].startswith('/') or '\x00' in b[key] or '..' in Path(b[key]).parts: raise ValueError('authority path')
    if b['transport'] not in ('wsl','local-wsl','local-fixture','wsl-fixture'): raise ValueError('transport')
    if b['harness_transport'] != ('local-fixture' if b['transport'] in ('local-fixture','wsl-fixture') else 'local-wsl'): raise ValueError('harness transport')
    if not isinstance(b['client_binding_path'],str) or not (Path(b['client_binding_path']).is_absolute() or PureWindowsPath(b['client_binding_path']).is_absolute()): raise ValueError('client path')
    if b['transport'] in ('wsl','wsl-fixture'):
        if not isinstance(b['distribution'],str) or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}',b['distribution']): raise ValueError('distribution')
    elif b['distribution'] is not None: raise ValueError('local distribution')
    if not isinstance(b['tools'],dict) or set(b['tools']) != ROLES: raise ValueError('tool roles')
    for role, item in b['tools'].items():
        if role=='wsl' and b['transport'] not in ('wsl','wsl-fixture'):
            if item is not None: raise ValueError('local wsl role')
            continue
        if not isinstance(item,dict) or set(item)!={'path','client_path','sha256'}: raise ValueError('tool schema')
        if not isinstance(item['path'],str) or not item['path'].startswith('/') or not isinstance(item['client_path'],str): raise ValueError('tool path')
        if not isinstance(item['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',item['sha256']): raise ValueError('tool hash')
    root=Path(b['authority_root'])
    if Path(b['tools']['authority']['path']) != root/'tools/local_program_authority.py' or Path(b['tools']['shim']['path']) != root/'tools/v0_s3_budget_authority.py': raise ValueError('authority root roles')
    if b['transport']=='wsl-fixture':
        validate_fixture_mapping(b)
    return b


def fixture_unc(path):
    p=PurePosixPath(path)
    if not p.is_absolute() or '..' in p.parts or str(p)!=path or '\\' in path:
        raise ValueError('noncanonical fixture path')
    return str(PureWindowsPath(r'\\wsl.localhost\Ubuntu-24.04').joinpath(*p.parts[1:]))


def validate_fixture_mapping(b):
    root=PurePosixPath(b['authority_root'])
    if (root.parent!=PurePosixPath('/tmp') or not root.name.startswith('lvw-s3-p2b-')
            or b['distribution']!='Ubuntu-24.04'):
        raise ValueError('fixed WSL fixture root/distribution')
    for key in ('child_path','ledger_path','execution_path','binding_path'):
        p=PurePosixPath(b[key])
        if not p.is_relative_to(root) or str(p)!=b[key] or '..' in p.parts:
            raise ValueError('fixture path escaped')
    if b['client_binding_path']!=fixture_unc(b['binding_path']): raise ValueError('fixture UNC mapping')
    for role in ('authority','shim','python'):
        item=b['tools'][role]
        if item['client_path']!=fixture_unc(item['path']): raise ValueError('fixture tool mapping')
    if b['tools']['python']['path']!='/usr/bin/python3': raise ValueError('fixture Python')
    wsl=b['tools']['wsl']
    if wsl['path']!='/mnt/c/Windows/System32/wsl.exe' or wsl['client_path']!=r'C:\Windows\System32\wsl.exe':
        raise ValueError('fixture wsl path')


def load_binding(binding=None, *, allow_expired=False):
    # binding is an internal {path, sha256} capability, never an argv/dict of commands.
    ref = binding if binding is not None else {'path':os.environ.get('LVW_S3_BUDGET_BINDING'), 'sha256':os.environ.get('LVW_S3_BUDGET_BINDING_SHA256')}
    if not isinstance(ref,dict) or set(ref)!={'path','sha256'} or not all(isinstance(v,str) and v for v in ref.values()): raise ValueError('missing binding capability')
    b=validate_config(read_json(ref['path'],ref['sha256']),allow_expired=allow_expired)
    expected_path=b['client_binding_path'] if os.name=='nt' else b['binding_path']
    if str(Path(ref['path'])) != expected_path: raise ValueError('substitute client binding path')
    if b['transport']=='wsl-fixture':
        root=Path(fixture_unc(b['authority_root']) if os.name=='nt' else b['authority_root'])
        if not (root/'.s3-synthetic-fixture').is_file(): raise ValueError('fixture marker missing')
    return b, ref['sha256']


def _active_s3_profile():
    # Inspect only the two owned opt-in profiles. Ordinary product use reads nothing.
    for flag, name in [('LVW_NATIVE_CHECKPOINT','lvw-native-profile.json'),('LVW_WARM_BENCHMARK','lvw-warm-profile.json')]:
        if not os.environ.get(flag): continue
        import folder_paths
        with (Path(folder_paths.get_temp_directory())/name).open('rb') as stream: raw=stream.read(4097)
        if len(raw)>4096: raise ValueError('profile size')
        profile=decode(raw)
        if profile.get('scope') in SCOPES or profile.get('program_authorization_id')==PROGRAM: return True
    return False


def validate_profile(profile, now, *, allow_expired=False, binding=None):
    b, seal=load_binding(binding,allow_expired=allow_expired)
    validate_config(b,now,allow_expired=allow_expired)
    if b['transport']=='wsl-fixture': raise ValueError('fixture forbidden in product profile')
    mapping={'candidate_sha':'candidate_sha','authorization_sha256':'child_sha256','child_sha256':'child_sha256',
             'child_path':'child_path','run_id':'run_id','model_digest':'model_digest',
             'ollama_pid':'ollama_pid','ollama_start_ticks':'ollama_start_ticks'}
    if (profile.get('program_authorization_id')!=PROGRAM or profile.get('scope') not in SCOPES
            or profile.get('budget_binding_sha256')!=seal or any(profile.get(k)!=b[v] for k,v in mapping.items())
            or not b['issued_at']<=profile['issued_at']<profile['expires_at']<=b['expires_at']):
        raise ValueError('profile/child identity mismatch')
    return b


def s3_profile(profile, binding):
    b, seal=load_binding(binding)
    value=dict(profile, program_authorization_id=PROGRAM,
               scope=profile['scope'].replace('V0_S2_', 'V0_S3_'),
               child_path=b['child_path'],child_sha256=b['child_sha256'],run_id=b['run_id'],
               budget_binding_sha256=seal,expires_at=b['expires_at'])
    validate_profile(value,time.time(),binding=binding)
    return value


def _command(b):
    roles=b['tools']
    if b['transport'] in ('wsl','wsl-fixture') and os.name=='nt':
        exe=roles['wsl']['client_path']
        if not PureWindowsPath(exe).is_absolute() or PureWindowsPath(exe).name.lower()!='wsl.exe' or digest(exe)!=roles['wsl']['sha256']: raise ValueError('wsl executable')
        return [exe,'-d',b['distribution'],'--exec',roles['python']['path'],'-I','-B',roles['shim']['path']]
    if b['transport']=='wsl-fixture': raise ValueError('wsl-fixture requires actual Windows client')
    if os.name=='nt': raise ValueError('local transport requires Linux/WSL')
    for role in ('python','shim'):
        item=roles[role]
        if item['client_path']!=item['path'] or digest(item['path'])!=item['sha256']: raise ValueError('local executable seal')
    return [roles['python']['path'],'-I','-B',roles['shim']['path']]


def process_birth(pid, process=None):
    """Read only the identity of an already owned process; never terminate by PID."""
    if os.name=='nt':
        import ctypes
        from ctypes import wintypes
        created=wintypes.FILETIME(); exited=wintypes.FILETIME()
        kernel=wintypes.FILETIME(); user=wintypes.FILETIME()
        fn=ctypes.WinDLL('kernel32',use_last_error=True).GetProcessTimes
        fn.argtypes=[wintypes.HANDLE]+[ctypes.POINTER(wintypes.FILETIME)]*4
        fn.restype=wintypes.BOOL
        if process is None or not fn(wintypes.HANDLE(int(process._handle)),ctypes.byref(created),ctypes.byref(exited),ctypes.byref(kernel),ctypes.byref(user)):
            raise OSError('owned process birth unavailable')
        return {'windows_creation_100ns':(created.dwHighDateTime<<32)|created.dwLowDateTime}
    fields=Path('/proc/%d/stat'%pid).read_text().rsplit(')',1)[1].split()
    return {'linux_start_ticks':int(fields[19])}


def _exchange(command, request, timeout):
    """Drain bounded pipes concurrently, reap only our child, retain real exit + error."""
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
    try: birth=process_birth(process.pid, process)
    except OSError: birth=None
    outputs=[bytearray(),bytearray()];errors=[];overflow=threading.Event()
    def read(index, pipe):
        try:
            while True:
                chunk=pipe.read(4096)
                if not chunk: break
                room=LIMIT-len(outputs[index]);outputs[index].extend(chunk[:room])
                if len(chunk)>room: overflow.set();break
        except Exception as error: errors.append(type(error).__name__)
    def write():
        try: process.stdin.write(request);process.stdin.close()
        except Exception as error: errors.append(type(error).__name__)
    threads=[threading.Thread(target=read,args=(0,process.stdout)),threading.Thread(target=read,args=(1,process.stderr)),threading.Thread(target=write)]
    for thread in threads: thread.start()
    error=None;deadline=time.monotonic()+timeout
    try:
        while process.poll() is None or any(t.is_alive() for t in threads):
            if overflow.is_set(): error='OUTPUT_LIMIT';break
            if time.monotonic()>=deadline: error='TIMEOUT';break
            time.sleep(.005)
    finally:
        if process.poll() is None: process.kill()
        exit_code=process.wait(timeout=5)
        for thread in threads: thread.join(timeout=1)
        # Frozen shim spawns no descendants; inherited pipes must not outlive it.
        alive=any(t.is_alive() for t in threads)
        if not alive:
            for pipe in (process.stdin,process.stdout,process.stderr): pipe.close()
    if overflow.is_set(): error=error or 'OUTPUT_LIMIT'
    if errors: error=error or 'PIPE_ERROR'
    if alive: error=error or 'PIPE_NOT_CLOSED'
    result={'pid':process.pid,'birth':birth,'os_name':os.name,'pipe_closed':all(p.closed for p in (process.stdin,process.stdout,process.stderr)), 'thread_alive':[t.is_alive() for t in threads], 'exit_code':exit_code,'error':error,'reaped':process.poll() is not None,'readers_joined':not alive,
            'stdout_sha256':hashlib.sha256(outputs[0]).hexdigest(),'stderr_sha256':hashlib.sha256(outputs[1]).hexdigest()}
    return bytes(outputs[0]),result


def authorize_model_action(action_kind,payload,*,binding=None):
    try:
        required=(binding is not None or bool(os.environ.get('LVW_S3_BUDGET_REQUIRED'))
                  or bool(os.environ.get('LVW_S3_BUDGET_BINDING')) or _active_s3_profile())
        if not required: return None
        if action_kind not in ('chat','preload') or not isinstance(payload,bytes): raise ValueError('action/payload')
        b,seal=load_binding(binding)
        model=decode(payload).get('model')
        if model!=b['model']: raise ValueError('model mismatch')
        request={'schema':'lvw.s3-debit/1','request_id':str(uuid.uuid4()),'action_kind':action_kind,
                 'payload_sha256':hashlib.sha256(payload).hexdigest(),'model':model,
                 'binding_path':b['binding_path'],'binding_sha256':seal}
        raw=json.dumps(request,separators=(',',':')).encode()
        timeout=min(10.,b['expires_at']-time.time())
        if timeout<=0: raise ValueError('expired before bridge')
        output,process=_exchange(_command(b),raw,timeout)
        if process['exit_code']!=0 or process['error'] is not None or not process['reaped'] or not process['readers_joined']:
            raise refused('S3_BRIDGE_PROCESS_FAILED',**process,request_id=request['request_id'])
        try: response=decode(output)
        except (ValueError,UnicodeError) as error:
            raise refused('S3_BRIDGE_RECEIPT_INVALID',**process,request_id=request['request_id']) from error
        expected=dict(request,status='DEBITED',run_id=b['run_id'],child_sha256=b['child_sha256'],authority_sha256=b['tools']['authority']['sha256'])
        if response!=expected: raise refused('S3_BRIDGE_RECEIPT_INVALID',**process,request_id=request['request_id'])
        if time.time()>=b['expires_at']: raise refused('S3_BRIDGE_RECEIPT_EXPIRED',**process,request_id=request['request_id'])
        return dict(response,process=process)
    except (OSError,ValueError,TypeError,KeyError,ImportError,subprocess.SubprocessError) as error:
        raise refused('S3_BUDGET_BINDING_OR_BRIDGE_INVALID',error_type=type(error).__name__) from error
