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
