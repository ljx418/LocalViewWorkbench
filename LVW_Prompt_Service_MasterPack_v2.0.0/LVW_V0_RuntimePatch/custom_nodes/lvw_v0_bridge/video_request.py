"""One request owns video preparation, model inference and terminal publication."""
import copy
import threading

from . import core
from .core import BridgeError, BridgeOwner
from .video_node import comfy_frames
from .video_transport import InterruptibleOllamaTransport


class VideoRequestOwner:
    def __init__(self, decoder, *, bridge=None, tensor_builder=None):
        self.decoder = decoder
        self.bridge = bridge or BridgeOwner(transport=InterruptibleOllamaTransport())
        self.tensor_builder = tensor_builder or comfy_frames
        self._guard = threading.Lock()
        self._cancel = None
        self._state = None
        self._used_tokens = set()

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
                    self._state["cancel_epoch"] += 1
                    self._cancel.set()
                    interrupt = getattr(self.bridge.transport, "cancel_active", None)
                    if interrupt is not None:
                        interrupt()
                self._state.update(status="cancelling", resource_state="releasing")
            return copy.deepcopy(self._state)

    def run(self, token, reference, *, model, user_instruction, mode, timeout_seconds, preview_hook=None, state_hook=None):
        if not isinstance(token, str) or not token or len(token) > 128:
            raise BridgeError("CONTRACT_UNSUPPORTED", "bounded run token required", subcode="VIDEO_RUN_TOKEN_REQUIRED")
        with self._guard:
            if token in self._used_tokens:
                raise BridgeError("ATTEMPT_STALE", "run token cannot be replayed", subcode="VIDEO_RUN_STALE")
            if len(self._used_tokens) >= 1024:
                raise BridgeError("RESOURCE_BUSY", "video session token capacity exhausted", subcode="VIDEO_SESSION_FULL")
            if core._RESOURCE_RELEASE_PENDING.is_set() or not core._INFERENCE_LOCK.acquire(blocking=False):
                raise BridgeError("RESOURCE_BUSY", "inference resource unavailable", subcode="LVW_BRIDGE_LOCKED")
            self._used_tokens.add(token)
            self._cancel = threading.Event()
            self._state = {"run_token":token, "cancel_epoch":0, "status":"preparing",
                           "resource_state":"busy", "error_code":None}
            cancel = self._cancel
        pending = False
        try:
            if state_hook is not None:
                state_hook(token)
            bind = getattr(self.bridge.transport, "bind_cancel", None)
            if bind is not None:
                bind(cancel)
            decoded = self.decoder.decode(reference, cancel=cancel)
            if preview_hook is not None and not cancel.is_set():
                preview_hook(token, decoded)
            with self._guard:
                if cancel.is_set():
                    raise BridgeError("JOB_CANCELLED", "video request cancelled", subcode="VIDEO_ANALYSIS_CANCELLED")
                self._state["status"] = "running"
            raw, suggestion = self.bridge.analyze_video(self.tensor_builder(decoded.frames), model=model,
                user_instruction=user_instruction, mode=mode, timeout_seconds=timeout_seconds, cancel_event=cancel)
            with self._guard:
                if cancel.is_set():
                    raise BridgeError("JOB_CANCELLED", "late video suggestion discarded", subcode="VIDEO_ANALYSIS_CANCELLED")
                self._state["status"] = "succeeded"
                return {"raw_response":raw, "suggestion":suggestion, "source_sha256":decoded.source_sha256,
                        "frames":decoded.manifest, "run_token":token, "cancel_epoch":self._state["cancel_epoch"]}
        except BaseException as exc:
            pending = isinstance(exc, BridgeError) and (exc.code == "RESOURCE_RELEASE_PENDING" or bool(exc.details.get("cleanup_error")))
            with self._guard:
                self._state.update(status="cancelled" if cancel.is_set() else "failed",
                                   error_code=exc.code if isinstance(exc, BridgeError) else "MEDIA_INVALID")
            raise
        finally:
            # Failed cleanup quarantines the shared slot for all bridge owners.
            # Recovery requires separate positive resource-release evidence.
            if pending:
                core._RESOURCE_RELEASE_PENDING.set()
            with self._guard:
                self._state["resource_state"] = "unknown" if pending else "released"
            core._INFERENCE_LOCK.release()
