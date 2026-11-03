"""Opt-in, run-owned native checkpoint telemetry; no public business API."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import threading
import time

from .core import BridgeError,DEFAULT_MODEL


def refused(reason):return BridgeError('SCOPE_FORBIDDEN','native checkpoint binding refused',subcode=reason)


def validate_binding(value,now,*,allow_expired=False):
    if not isinstance(value,dict):raise refused('NATIVE_BINDING_INVALID')
    for key,length in [('candidate_sha',40),('authorization_sha256',64),('model_digest',64)]:
        if not isinstance(value.get(key),str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}',value[key]):raise refused('NATIVE_BINDING_INVALID')
    if (value.get('program_authorization_id')!='AUTH-PROGRAM-V1-LOCAL-01' or value.get('scope')!='V0_S2_NATIVE_CHECKPOINT'
            or type(value.get('max_runs')) is not int or not 1<=value['max_runs']<=64
            or any(type(value.get(k)) is not int or value[k]<=0 for k in ('ollama_pid','ollama_start_ticks'))):
        raise refused('NATIVE_BINDING_INVALID')
    issued,expires=value.get('issued_at'),value.get('expires_at')
    if (any(type(v) not in (int,float) or not math.isfinite(v) for v in (issued,expires,now))
            or not 0<expires-issued<=7200 or now<issued or (not allow_expired and now>=expires)):
        raise refused('NATIVE_BINDING_EXPIRED')


class NativeAudit:
    def __init__(self,binding,*,sink,check_root,check_binding=lambda:None,clock=time.monotonic,wall=time.time):
        validate_binding(binding,wall())
        self.binding=dict(binding);self.sink=sink;self.root=check_root;self.check_binding=check_binding
        self.clock=clock;self.wall=wall;self.guard=threading.Lock();self.active=None;self.runs=0;self.attempts=0;self.used=set()

    def ensure(self,*,cleanup=False):
        self.check_binding();validate_binding(self.binding,self.wall(),allow_expired=cleanup)

    def event(self,token,event,**fields):
        if set(fields)&{'event','run_token','run_number','owner_pid','candidate_sha','authorization_sha256','monotonic_seconds','wall_seconds'}:
            raise refused('NATIVE_EVENT_HEADER_OVERRIDE')
        with self.guard:
            if self.active!=token:raise refused('NATIVE_EVENT_TOKEN_STALE')
            record={'event':event,'run_token':token,'run_number':self.runs,'owner_pid':os.getpid(),
                'candidate_sha':self.binding['candidate_sha'],'authorization_sha256':self.binding['authorization_sha256'],
                'monotonic_seconds':self.clock(),'wall_seconds':self.wall(),**fields}
            self.sink(record)

    def start(self,token):
        self.ensure()
        with self.guard:
            if (self.active is not None or token in self.used or self.runs>=self.binding['max_runs']
                    or not isinstance(token,str) or not re.fullmatch('[A-Za-z0-9_-]{1,128}',token)):
                raise refused('NATIVE_RUN_BUDGET_OR_TOKEN_INVALID')
            self.active=token;self.used.add(token);self.runs+=1;self.attempts=0
        self.event(token,'run_started')

    def before_provider(self,token,payload,timeout):
        self.ensure();proof=self.root();self.ensure()
        if payload.get('model')!=DEFAULT_MODEL:raise refused('NATIVE_MODEL_NOT_BOUND')
        with self.guard:
            if self.active!=token or self.attempts>=4:raise refused('NATIVE_PROVIDER_BUDGET_OR_TOKEN_INVALID')
            index=self.attempts;self.attempts+=1
        raw=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
        self.event(token,'provider_attempt',call_index=index,payload_sha256=hashlib.sha256(raw).hexdigest(),root_proof=proof)
        return min(timeout,self.binding['expires_at']-self.wall())

    def verify_provider_owner(self,token):
        self.ensure();proof=self.root();self.ensure()
        self.event(token,'provider_owner_verified',call_index=self.attempts-1,root_proof=proof)

    def before_control(self,token):
        # Expiry stops new work, never the release reserved by the old run.
        self.ensure(cleanup=True);proof=self.root()
        self.event(token,'release_owner_verified',root_proof=proof)

    def finish(self,token,*,status,resource_state,error_code,cancel_epoch,cancel_accepted_at,release):
        if status=='succeeded' and (not 1<=self.attempts<=4 or not isinstance(release,dict) or release.get('state')!='released'):
            raise refused('NATIVE_SUCCESS_EVIDENCE_INCOMPLETE')
        if cancel_accepted_at is not None:
            self.event(token,'cancel_accepted',observed_monotonic_seconds=cancel_accepted_at,cancel_epoch=cancel_epoch)
        self.event(token,'run_finished',status=status,resource_state=resource_state,error_code=error_code,
            cancel_epoch=cancel_epoch,provider_attempts=self.attempts,result_published=status=='succeeded',resource_release=release)
        with self.guard:self.active=None


_AUDIT=None
_CONFIG_GUARD=threading.Lock()


def configured_native_audit():
    flag=os.environ.get('LVW_NATIVE_CHECKPOINT')
    if not flag:return None
    if flag!='run-owned-v1' or os.environ.get('LVW_WARM_BENCHMARK'):raise refused('NATIVE_AUDIT_MODE_CONFLICT')
    global _AUDIT
    with _CONFIG_GUARD:
        if _AUDIT is not None:return _AUDIT
        import folder_paths
        directory=Path(folder_paths.get_temp_directory())
        def plain(path):
            if path.is_symlink() or getattr(path.stat(),'st_file_attributes',0)&0x400:raise refused('NATIVE_REPARSE_FORBIDDEN')
        for path in (directory,*directory.parents):plain(path)
        binding_file=directory/'lvw-native-profile.json'
        def read():
            plain(binding_file)
            if binding_file.stat().st_size>4096:raise refused('NATIVE_BINDING_LIMIT')
            raw=binding_file.read_bytes()
            if len(raw)>4096:raise refused('NATIVE_BINDING_LIMIT')
            return raw
        try:raw=read();binding=json.loads(raw);validate_binding(binding,time.time())
        except (OSError,ValueError,UnicodeError) as error:raise refused('NATIVE_BINDING_UNAVAILABLE') from error
        def unchanged():
            if read()!=raw:raise refused('NATIVE_BINDING_CHANGED')
        log=directory/'lvw-native-events.jsonl'
        try:
            with log.open('x',encoding='utf-8'):pass
        except OSError as error:raise refused('NATIVE_LOG_SLOT_UNAVAILABLE') from error
        def sink(value):
            plain(log)
            encoded=json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n'
            if log.stat().st_size+len(encoded.encode())>8*1024*1024:raise refused('NATIVE_LOG_LIMIT')
            with log.open('a',encoding='utf-8') as stream:
                stream.write(encoded);stream.flush()
                if value['event']=='run_finished':os.fsync(stream.fileno())
        from .benchmark import native_lineage
        _AUDIT=NativeAudit(binding,sink=sink,check_root=lambda:native_lineage(binding,[],with_evidence=True),check_binding=unchanged)
        return _AUDIT
