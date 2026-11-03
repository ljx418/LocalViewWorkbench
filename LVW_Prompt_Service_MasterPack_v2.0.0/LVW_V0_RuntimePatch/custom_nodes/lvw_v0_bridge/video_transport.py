"""Interrupt only this request's literal-loopback HTTP connection."""
import http.client
import hashlib
import json
import math
import socket
import threading
import time
from urllib.parse import urlsplit

from .core import BridgeError, OllamaLoopbackTransport, validate_loopback_endpoint
from .video_resources import gpu_used_mib


class InterruptibleOllamaTransport(OllamaLoopbackTransport):
    def __init__(self, *,require_gpu_release=False,gpu_probe=None, **kwargs):
        super().__init__(**kwargs)
        self._guard = threading.Lock()
        self._active = None
        self._active_socket = None
        self._cancel = None
        self.release_evidence = {"state":"unproven"}
        self._require_gpu_release=require_gpu_release
        self._gpu_probe=gpu_probe or gpu_used_mib
        self._gpu_baseline=None;self._audit=None;self._audit_token=None;self._audit_call=None

    def bind_audit(self,audit,token):
        with self._guard:
            if self._active is not None:raise ValueError('active connection cannot change audit')
            self._audit=audit;self._audit_token=token;self._audit_call=None
            self.release_evidence={'state':'not_requested'}

    def _evidence(self,event,**fields):
        if self._audit is not None:self._audit.event(self._audit_token,event,call_index=self._audit_call,**fields)

    def bind_resource_baseline(self,value):
        if type(value) is not int or not 0<=value<=4096:raise ValueError('invalid cold GPU baseline')
        self._gpu_baseline=value

    def _control_request(self, method, path, payload, timeout):
        """Fixed internal control paths, no redirects, proxies or arbitrary URL."""
        validate_loopback_endpoint(self.endpoint)
        if path not in {"/api/generate", "/api/ps"}:
            raise ValueError("invalid internal control path")
        if self._audit is not None:
            control_deadline=time.monotonic()+timeout
            self._audit.before_control(self._audit_token)
            timeout=control_deadline-time.monotonic()
            if timeout<=0:raise BridgeError('RESOURCE_RELEASE_PENDING','ownership proof exhausted control deadline',subcode='NATIVE_OWNER_PROOF_TIMEOUT')
        parsed = urlsplit(self.endpoint)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
        response = None
        deadline = time.monotonic() + timeout
        try:
            body = None if payload is None else json.dumps(payload).encode()
            connection.request(method, path, body, {"Content-Type":"application/json"})
            request_socket = connection.sock
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError("control HTTP failure")
            raw = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                if request_socket is not None:
                    request_socket.settimeout(remaining)
                data = response.read1(min(8192, 256 * 1024 - len(raw) + 1))
                if not data:
                    break
                raw.extend(data)
                if len(raw) > 256 * 1024:
                    raise ValueError("control response limit")
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ValueError("control response shape")
            return value
        except (OSError, http.client.HTTPException, ValueError, RecursionError) as exc:
            raise BridgeError("RESOURCE_RELEASE_PENDING", "model release control is unproven",
                              subcode="OLLAMA_RELEASE_UNPROVEN") from exc
        finally:
            if response is not None:
                response.close()
            connection.close()

    def cleanup(self, model, timeout_seconds, *, release_deadline=None):
        # Cleanup deliberately ignores the cancel event: release must complete
        # even after the chat connection has been interrupted.
        started = time.monotonic()
        self.release_evidence = {"state":"unproven", "checks":0,"started_monotonic_seconds":started}
        deadline = started + 30
        if release_deadline is not None:
            if type(release_deadline) not in (int,float) or not math.isfinite(release_deadline):
                raise ValueError('invalid release deadline')
            deadline = min(deadline,release_deadline)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise BridgeError('RESOURCE_RELEASE_PENDING','release deadline expired',subcode='OLLAMA_RELEASE_UNPROVEN')
        unloaded = self._control_request("POST", "/api/generate", {"model":model,"keep_alive":0},
                                         min(timeout_seconds, 15, remaining))
        if unloaded.get("done") is not True:
            raise BridgeError("RESOURCE_RELEASE_PENDING", "model unload not acknowledged", subcode="OLLAMA_RELEASE_UNPROVEN")
        self._evidence('unload_acknowledged',response=unloaded)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BridgeError("RESOURCE_RELEASE_PENDING", "models remain loaded after unload",
                                  subcode="OLLAMA_RELEASE_UNPROVEN")
            state = self._control_request("GET", "/api/ps", None, min(remaining, 2))
            models = state.get("models")
            self.release_evidence["checks"] += 1
            observed = time.monotonic()
            if observed > deadline:
                raise BridgeError('RESOURCE_RELEASE_PENDING','release confirmation arrived after deadline',subcode='OLLAMA_RELEASE_UNPROVEN')
            if not isinstance(models, list):
                raise BridgeError("RESOURCE_RELEASE_PENDING", "model inventory is invalid", subcode="OLLAMA_RELEASE_UNPROVEN")
            if not models:
                self.release_evidence.update(state="model_unloaded",loaded_models=0,model_inventory_empty_monotonic=observed)
                self._evidence('model_inventory_empty',observed_monotonic_seconds=observed,api_ps=state)
                if self._gpu_baseline is None:
                    if self._require_gpu_release:
                        raise BridgeError('RESOURCE_RELEASE_PENDING','cold GPU baseline missing',subcode='GPU_RELEASE_UNPROVEN')
                    self.release_evidence['elapsed_seconds']=observed-started
                    return
                samples=[];stable=0
                self.release_evidence.update(baseline_gpu_mib=self._gpu_baseline,gpu_samples=samples)
                while time.monotonic()<deadline:
                    try:used=self._gpu_probe(deadline)
                    except Exception as error:
                        raise BridgeError('RESOURCE_RELEASE_PENDING','GPU release observation unavailable',subcode='GPU_RELEASE_UNPROVEN') from error
                    now=time.monotonic()
                    if type(used) is not int or used<0 or now>deadline:break
                    samples.append({'elapsed_seconds':now-started,'gpu_used_mib':used})
                    stable=stable+1 if used<=self._gpu_baseline+1024 else 0
                    if stable>=3:
                        self.release_evidence.update(state='released',elapsed_seconds=now-started)
                        self._evidence('physical_release',release=dict(self.release_evidence))
                        return
                    time.sleep(min(1,max(0,deadline-time.monotonic())))
                raise BridgeError('RESOURCE_RELEASE_PENDING','GPU did not return to stable baseline',subcode='GPU_RELEASE_UNPROVEN')
            # Other loaded models are observed only, never unloaded or killed.
            time.sleep(min(.1, max(0, deadline - time.monotonic())))

    def bind_cancel(self, event):
        with self._guard:
            if self._active is not None:
                raise BridgeError("RESOURCE_BUSY", "request connection is active", subcode="OLLAMA_CONNECTION_BUSY")
            self._cancel = event

    def cancel_active(self):
        with self._guard:
            active_socket = self._active_socket
            if active_socket is not None:
                try:
                    active_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

    def _cancelled(self):
        return self._cancel is not None and self._cancel.is_set()

    def chat(self, payload, timeout_seconds):
        validate_loopback_endpoint(self.endpoint)
        if self._audit is not None:
            original_deadline=time.monotonic()+timeout_seconds
            timeout_seconds=self._audit.before_provider(self._audit_token,payload,timeout_seconds)
            self._audit_call=self._audit.attempts-1
            timeout_seconds=min(timeout_seconds,original_deadline-time.monotonic())
            if timeout_seconds<=0:raise BridgeError('MODEL_TIMEOUT','native ownership checks exhausted provider budget',subcode='NATIVE_PROVIDER_DEADLINE')
        parsed = urlsplit(self.endpoint)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=min(timeout_seconds, 1))
        with self._guard:
            if self._cancelled():
                raise BridgeError("JOB_CANCELLED", "request cancelled", subcode="OLLAMA_REQUEST_CANCELLED")
            self._active = connection
        response = None
        deadline = time.monotonic() + timeout_seconds
        try:
            connection.connect()
            with self._guard:
                if self._cancelled():
                    raise BridgeError("JOB_CANCELLED", "request cancelled", subcode="OLLAMA_REQUEST_CANCELLED")
                self._active_socket = connection.sock.dup()
                request_socket = connection.sock
                connection.sock.settimeout(max(.001, deadline - time.monotonic()))
            if self._audit is not None:self._audit.verify_provider_owner(self._audit_token)
            if self._cancelled():raise BridgeError('JOB_CANCELLED','request cancelled before send',subcode='OLLAMA_REQUEST_CANCELLED')
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            request_socket.settimeout(remaining)
            connection.request("POST", parsed.path, body, {"Content-Type":"application/json"})
            self._evidence('provider_request_sent')
            response = connection.getresponse()
            if response.status != 200:
                raise BridgeError("MODEL_UNAVAILABLE", "Ollama HTTP request failed", subcode="OLLAMA_HTTP_STATUS")
            output = bytearray()
            while True:
                if self._cancelled():
                    raise BridgeError("JOB_CANCELLED", "request cancelled", subcode="OLLAMA_REQUEST_CANCELLED")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                if request_socket is not None:
                    request_socket.settimeout(remaining)
                chunk = response.read1(min(8192, 4 * 1024 * 1024 - len(output) + 1))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > 4 * 1024 * 1024:
                    raise BridgeError("PARSE_PARTIAL", "Ollama response exceeds limit", subcode="OLLAMA_RESPONSE_LIMIT")
            value=output.decode("utf-8", "strict")
            self._evidence('provider_response',raw_sha256=hashlib.sha256(output).hexdigest())
            return value
        except (OSError, http.client.HTTPException) as exc:
            if self._cancelled():
                raise BridgeError("JOB_CANCELLED", "request connection interrupted", subcode="OLLAMA_REQUEST_CANCELLED") from exc
            code = "MODEL_TIMEOUT" if isinstance(exc, TimeoutError) else "MODEL_UNAVAILABLE"
            raise BridgeError(code, "Ollama local connection failed", subcode="OLLAMA_TRANSPORT_ERROR") from exc
        except UnicodeError as exc:
            raise BridgeError("PARSE_PARTIAL", "Ollama response encoding invalid", subcode="INVALID_RESPONSE_ENCODING") from exc
        finally:
            if response is not None:
                response.close()
            connection.close()
            with self._guard:
                if self._active_socket is not None:
                    self._active_socket.close()
                    self._active_socket = None
                self._active = None
            self._evidence('provider_connection_closed')
