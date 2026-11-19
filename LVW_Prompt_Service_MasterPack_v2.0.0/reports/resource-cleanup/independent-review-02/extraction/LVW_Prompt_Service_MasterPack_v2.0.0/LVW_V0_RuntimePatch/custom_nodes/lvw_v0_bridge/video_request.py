"""One request owns video preparation, model inference and terminal publication."""
import copy
import threading
import time

from . import core
from .core import BridgeError
from .video_node import comfy_frames
from .video_resources import resource_preflight, host_resource_preflight


class VideoRequestOwner:
    def __init__(self, decoder, *, bridge=None, tensor_builder=None, preflight=None,
                 host_preflight=host_resource_preflight,clock=None,audit=None):
        from .video_evidence import configured_native_audit
        self.audit=audit if audit is not None else configured_native_audit()
        self.decoder = decoder
        if bridge is None:
            from .benchmark import runtime_bridge
            bridge = runtime_bridge(interruptible=True)
        self.bridge = bridge
        self.clock=clock if clock is not None else getattr(bridge,'clock',time.monotonic)
        self.tensor_builder = tensor_builder or comfy_frames
        benchmark = getattr(self.bridge, 'benchmark', None)
        if self.audit is not None and benchmark is not None:
            raise BridgeError('SCOPE_FORBIDDEN','native and warm modes cannot overlap',subcode='NATIVE_AUDIT_MODE_CONFLICT')
        self.preflight = preflight if preflight is not None else (
            benchmark.admission if benchmark is not None else resource_preflight)
        self.host_preflight = host_preflight
        self._guard = threading.Lock()
        self._cancel = None
        self._state = None
        self._used_tokens = set()
        self._completed_result = None
        self._cancel_accepted_at=None

    def completed_result(self, token):
        with self._guard:
            self._require_current(token)
            if (self._state['status'] != 'succeeded' or self._state['resource_state']!='released' or self._cancel.is_set()
                    or self._completed_result is None or self._completed_result['run_token'] != token):
                raise BridgeError('ATTEMPT_STALE', 'no current successful video result', subcode='VIDEO_RUN_STALE')
            return copy.deepcopy(self._completed_result)

    def status(self, token):
        with self._guard:
            self._require_current(token)
            return copy.deepcopy(self._state)

    def current_status(self):
        with self._guard:
            return copy.deepcopy(self._state) if self._state else {"status":"idle", "resource_state":"released", "run_token":None}

    def _require_current(self, token):
        if self._state is None or self._state["run_token"] != token:
            raise BridgeError("ATTEMPT_STALE", "video request token is not current", subcode="VIDEO_RUN_STALE")

    def cancel(self, token):
        with self._guard:
            self._require_current(token)
            if self._state["status"] in {"preparing", "running", "cancelling"}:
                if not self._cancel.is_set():
                    self._cancel_accepted_at=self.clock()
                    self._state["cancel_epoch"] += 1
                    self._cancel.set()
                    interrupt = getattr(self.bridge.transport, "cancel_active", None)
                    if interrupt is not None:
                        interrupt()
                self._state.update(status="cancelling", resource_state="releasing")
            return copy.deepcopy(self._state)

    def run(self, token, reference, *, model, user_instruction, mode, timeout_seconds, preview_hook=None, state_hook=None):
        deadline=self.clock()+core.MAX_ANALYSIS_SECONDS
        if not isinstance(token, str) or not token or len(token) > 128:
            raise BridgeError("CONTRACT_UNSUPPORTED", "bounded run token required", subcode="VIDEO_RUN_TOKEN_REQUIRED")
        with self._guard:
            if token in self._used_tokens:
                raise BridgeError("ATTEMPT_STALE", "run token cannot be replayed", subcode="VIDEO_RUN_STALE")
            if self._state is not None and self._state["resource_state"] != "released":
                raise BridgeError("RESOURCE_BUSY", "current video request has not released resources", subcode="VIDEO_REQUEST_ACTIVE")
            if len(self._used_tokens) >= 1024:
                raise BridgeError("RESOURCE_BUSY", "video session token capacity exhausted", subcode="VIDEO_SESSION_FULL")
            if core._RESOURCE_RELEASE_PENDING.is_set() or not core._INFERENCE_LOCK.acquire(blocking=False):
                raise BridgeError("RESOURCE_BUSY", "inference resource unavailable", subcode="LVW_BRIDGE_LOCKED")
            self._used_tokens.add(token)
            self._completed_result = None
            self._cancel = threading.Event()
            self._cancel_accepted_at=None
            self._state = {"run_token":token, "cancel_epoch":0, "status":"preparing",
                           "resource_state":"busy", "error_code":None}
            cancel = self._cancel
        pending = False;audit_started=False
        try:
            if self.audit is not None:
                self.audit.start(token);audit_started=True
                audit_binder=getattr(self.bridge.transport,'bind_audit',None)
                if audit_binder is None:raise BridgeError('SCOPE_FORBIDDEN','native audit requires interruptible transport',subcode='NATIVE_TRANSPORT_REQUIRED')
                audit_binder(self.audit,token)
            if state_hook is not None:
                state_hook(token)
            bind = getattr(self.bridge.transport, "bind_cancel", None)
            if bind is not None:
                bind(cancel)
            resource_evidence = {"before_prepare":self.host_preflight()}
            decoded = self.decoder.decode(reference, cancel=cancel)
            if self.audit is not None:
                self.audit.event(token,'source_prepared',source_sha256=decoded.source_sha256,frames=list(decoded.manifest))
            if preview_hook is not None and not cancel.is_set():
                preview_hook(token, decoded)
            with self._guard:
                if cancel.is_set():
                    raise BridgeError("JOB_CANCELLED", "video request cancelled", subcode="VIDEO_ANALYSIS_CANCELLED")
                self._state["status"] = "running"
            frames=self.tensor_builder(decoded.frames)
            if cancel.is_set():
                raise BridgeError('JOB_CANCELLED','video request cancelled',subcode='VIDEO_ANALYSIS_CANCELLED')
            if self.clock() >= deadline-core.RELEASE_RESERVE_SECONDS:
                raise BridgeError('MODEL_TIMEOUT','video preparation exhausted request budget',subcode='VIDEO_REQUEST_DEADLINE')
            if self.audit is not None:self.audit.event(token,'gpu_admission_started')
            resource_evidence["before_model"] = self.preflight()
            if self.audit is not None:self.audit.event(token,'gpu_admission_completed',snapshot=resource_evidence['before_model'])
            baseline=getattr(self.bridge.transport,'bind_resource_baseline',None)
            if baseline is not None and getattr(self.bridge,'benchmark',None) is None:
                baseline(resource_evidence['before_model']['gpu_used_mib'])
            raw, suggestion = self.bridge.analyze_video(frames, model=model,
                user_instruction=user_instruction, mode=mode, timeout_seconds=timeout_seconds, cancel_event=cancel,
                request_deadline=deadline)
            with self._guard:
                if cancel.is_set():
                    raise BridgeError("JOB_CANCELLED", "late video suggestion discarded", subcode="VIDEO_ANALYSIS_CANCELLED")
                self._state["status"] = "succeeded"
                result = {"raw_response":raw, "suggestion":suggestion, "source_sha256":decoded.source_sha256,
                        "decoder_backend":getattr(decoded,'decoder_backend',None),
                        "frames":decoded.manifest, "resource_preflight":resource_evidence,
                        "run_token":token, "cancel_epoch":self._state["cancel_epoch"]}
                result['resource_release']=copy.deepcopy(getattr(self.bridge.transport,'release_evidence',None))
                result['model_tag'] = model
                result['source'] = {
                    'id': 'video_' + decoded.source_sha256[:32], 'sha256': decoded.source_sha256,
                    'kind': 'video', 'display_name': 'Local video',
                    'bytes': decoded.byte_count, 'width': decoded.width,
                    'height': decoded.height, 'duration_seconds': decoded.duration_seconds,
                    'source_root_id': None, 'relative_path': None, 'availability': 'available',
                    'frames': [{'index': f['index'], 'target_seconds': f['time_seconds'], 'source_pts': f['pts'],
                                'time_base_num': f['time_base_num'], 'time_base_den': f['time_base_den'],
                                'sha256': f['sha256'], 'time_basis': 'decoded_pts'} for f in decoded.manifest]}
                self._completed_result = copy.deepcopy(result)
                return result
        except BaseException as exc:
            pending = isinstance(exc, BridgeError) and (exc.code == "RESOURCE_RELEASE_PENDING" or bool(exc.details.get("cleanup_error")))
            with self._guard:
                self._state.update(status="cancelled" if cancel.is_set() else "failed",
                                   error_code=exc.code if isinstance(exc, BridgeError) else "MEDIA_INVALID")
            raise
        finally:
            # Failed cleanup quarantines the shared slot for all bridge owners.
            # Recovery requires separate positive resource-release evidence.
            pending = pending or core._RESOURCE_RELEASE_PENDING.is_set()
            if pending:
                core._RESOURCE_RELEASE_PENDING.set()
            try:
                with self._guard:
                    self._state["resource_state"] = "unknown" if pending else ("releasing" if audit_started else "released")
                    terminal=copy.deepcopy(self._state);accepted=self._cancel_accepted_at
                    if not pending:terminal['resource_state']='released'
                if audit_started:
                    self.audit.finish(token,status=terminal['status'],resource_state=terminal['resource_state'],
                        error_code=terminal['error_code'],cancel_epoch=terminal['cancel_epoch'],cancel_accepted_at=accepted,
                        release=copy.deepcopy(getattr(self.bridge.transport,'release_evidence',None)))
                    with self._guard:self._state['resource_state']=terminal['resource_state']
            except BaseException as error:
                core._RESOURCE_RELEASE_PENDING.set()
                with self._guard:
                    self._state.update(status='failed',resource_state='unknown',error_code='RESOURCE_RELEASE_PENDING')
                    self._completed_result=None
                if isinstance(error,(KeyboardInterrupt,SystemExit)):raise
                raise BridgeError('RESOURCE_RELEASE_PENDING','native evidence terminal could not be persisted',subcode='NATIVE_EVIDENCE_INCOMPLETE') from error
            finally:core._INFERENCE_LOCK.release()
