"""Interrupt only this request's literal-loopback HTTP connection."""
import http.client
import json
import socket
import threading
import time
from urllib.parse import urlsplit

from .core import BridgeError, OllamaLoopbackTransport, validate_loopback_endpoint


class InterruptibleOllamaTransport(OllamaLoopbackTransport):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._guard = threading.Lock()
        self._active = None
        self._active_socket = None
        self._cancel = None
        self.release_evidence = {"state":"unproven"}

    def _control_request(self, method, path, payload, timeout):
        """Fixed internal control paths, no redirects, proxies or arbitrary URL."""
        validate_loopback_endpoint(self.endpoint)
        if path not in {"/api/generate", "/api/ps"}:
            raise ValueError("invalid internal control path")
        parsed = urlsplit(self.endpoint)
        connection = http.client.HTTPConnection(parsed.hostname, parsed.port, timeout=timeout)
        response = None
        deadline = time.monotonic() + timeout
        try:
            body = None if payload is None else json.dumps(payload).encode()
            connection.request(method, path, body, {"Content-Type":"application/json"})
            response = connection.getresponse()
            if response.status != 200:
                raise ValueError("control HTTP failure")
            raw = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError()
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
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

    def cleanup(self, model, timeout_seconds):
        # Cleanup deliberately ignores the cancel event: release must complete
        # even after the chat connection has been interrupted.
        started = time.monotonic()
        self.release_evidence = {"state":"unproven", "checks":0}
        unloaded = self._control_request("POST", "/api/generate", {"model":model,"keep_alive":0},
                                         min(timeout_seconds, 15))
        if unloaded.get("done") is not True:
            raise BridgeError("RESOURCE_RELEASE_PENDING", "model unload not acknowledged", subcode="OLLAMA_RELEASE_UNPROVEN")
        deadline = started + 30
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise BridgeError("RESOURCE_RELEASE_PENDING", "models remain loaded after unload",
                                  subcode="OLLAMA_RELEASE_UNPROVEN")
            state = self._control_request("GET", "/api/ps", None, min(remaining, 2))
            models = state.get("models")
            self.release_evidence["checks"] += 1
            if not isinstance(models, list):
                raise BridgeError("RESOURCE_RELEASE_PENDING", "model inventory is invalid", subcode="OLLAMA_RELEASE_UNPROVEN")
            if not models:
                self.release_evidence.update(state="released", elapsed_seconds=time.monotonic() - started,
                                             loaded_models=0)
                return
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
                connection.sock.settimeout(max(.001, deadline - time.monotonic()))
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
            connection.request("POST", parsed.path, body, {"Content-Type":"application/json"})
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
                if connection.sock is not None:
                    connection.sock.settimeout(remaining)
                chunk = response.read1(min(8192, 4 * 1024 * 1024 - len(output) + 1))
                if not chunk:
                    break
                output.extend(chunk)
                if len(output) > 4 * 1024 * 1024:
                    raise BridgeError("PARSE_PARTIAL", "Ollama response exceeds limit", subcode="OLLAMA_RESPONSE_LIMIT")
            return output.decode("utf-8", "strict")
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
