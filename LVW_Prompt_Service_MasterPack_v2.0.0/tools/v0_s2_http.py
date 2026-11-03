"""Direct, bounded control client for the S2 trusted runner, never a proxy."""
import http.client
import json
import time
from urllib.parse import urlsplit


class ControlError(ValueError):
    pass


class LoopbackClient:
    def __init__(self, endpoint, *, response_limit=4 * 1024 * 1024):
        if endpoint not in {'http://127.0.0.1:8191', 'http://127.0.0.1:11434'}:
            raise ControlError('CONTROL_ENDPOINT_FORBIDDEN')
        if type(response_limit) is not int or not 0 < response_limit <= 16 * 1024 * 1024:
            raise ControlError('CONTROL_RESPONSE_LIMIT_INVALID')
        self.endpoint = endpoint
        self.port = urlsplit(endpoint).port
        self.response_limit = response_limit

    def request(self, method, path, *, payload=None, timeout=20):
        # Fixed services and API families only; caller cannot redirect to URL,
        # filesystem, browser resources, or a global interrupt endpoint.
        exact = {'/object_info', '/prompt', '/api/version', '/api/tags', '/api/ps',
                 '/api/generate', '/lvw/v0/video/status', '/lvw/v0/video/cancel', '/lvw/v0/video/workbench'}
        history = path.startswith('/history/') and len(path) > 9 and all(
            c in '0123456789abcdefABCDEF-' for c in path[9:])
        comfy = path in {'/object_info', '/prompt', '/lvw/v0/video/status', '/lvw/v0/video/cancel', '/lvw/v0/video/workbench'} or history
        if (path not in exact and not history) or (self.port == 8191) != comfy:
            raise ControlError('CONTROL_PATH_FORBIDDEN')
        expected = 'POST' if path in {'/prompt', '/api/generate', '/lvw/v0/video/cancel', '/lvw/v0/video/workbench'} else 'GET'
        if method != expected or (method == 'GET' and payload is not None):
            raise ControlError('CONTROL_METHOD_FORBIDDEN')
        if type(timeout) not in (int, float) or not 0 < timeout <= 120:
            raise ControlError('CONTROL_TIMEOUT_INVALID')
        body = None if payload is None else json.dumps(payload, allow_nan=False).encode('utf-8')
        if body is not None and len(body) > 1024 * 1024:
            raise ControlError('CONTROL_REQUEST_LIMIT')
        deadline = time.monotonic() + timeout
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=timeout)
        response = None
        try:
            connection.request(method, path, body, {'Content-Type':'application/json',
                'Origin':self.endpoint, 'X-LVW-Control':'local-ui'})
            active_socket = connection.sock
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                raise ControlError('CONTROL_HTTP_' + str(response.status))
            raw = bytearray()
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ControlError('CONTROL_DEADLINE')
                # HTTPConnection can detach a close-after-response socket after
                # getresponse(); retain this request's socket for the deadline.
                if active_socket is not None:
                    active_socket.settimeout(remaining)
                chunk = response.read1(min(8192, self.response_limit + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > self.response_limit:
                    raise ControlError('CONTROL_RESPONSE_LIMIT')
            value = json.loads(raw)
            if not isinstance(value, dict):
                raise ControlError('CONTROL_RESPONSE_SHAPE')
            return response.status, value
        finally:
            if response is not None:
                response.close()
            connection.close()
