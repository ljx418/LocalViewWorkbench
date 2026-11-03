"""Direct, bounded control client for the S2 trusted runner, never a proxy."""
import http.client
import json
import time
import socket
import threading
import copy
from urllib.parse import urlsplit


class ControlError(ValueError):
    pass


class _OwnedRequest:
    def __init__(self):
        self.abort=threading.Event();self.done=threading.Event();self.guard=threading.Lock()
        self.sock=None;self.value=None;self.error=None;self.thread=None

    def attach(self,sock):
        with self.guard:
            self.sock=sock
            if self.abort.is_set():
                try:sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass

    def cancel(self):
        self.abort.set()
        with self.guard:
            if self.sock is not None:
                try:self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass


class LoopbackClient:
    def __init__(self, endpoint, *, response_limit=4 * 1024 * 1024):
        if endpoint not in {'http://127.0.0.1:8191', 'http://127.0.0.1:11434'}:
            raise ControlError('CONTROL_ENDPOINT_FORBIDDEN')
        if type(response_limit) is not int or not 0 < response_limit <= 16 * 1024 * 1024:
            raise ControlError('CONTROL_RESPONSE_LIMIT_INVALID')
        self.endpoint = endpoint
        self.port = urlsplit(endpoint).port
        self.response_limit = response_limit
        self._pending=[]

    def pending_count(self):
        self._pending=[handle for handle in self._pending if handle.thread.is_alive()]
        return len(self._pending)

    def reap_pending(self,timeout=2):
        deadline=time.monotonic()+timeout
        for handle in list(self._pending):handle.thread.join(max(0,deadline-time.monotonic()))
        return self.pending_count()

    def request(self,method,path,*,payload=None,timeout=20,observer=None):
        if self.pending_count():raise ControlError('CONTROL_PREVIOUS_REQUEST_PENDING')
        if observer is None:return self._request(method,path,payload=payload,timeout=timeout)
        if not callable(observer):raise ControlError('CONTROL_OBSERVER_INVALID')
        # Validate before observer (which may itself query native resources).
        self._validate(method,path,payload,timeout)
        observer()
        handle=_OwnedRequest()
        def run():
            try:handle.value=self._request(method,path,payload=payload,timeout=timeout,owned=handle)
            except BaseException as error:handle.error=error
            finally:handle.done.set()
        handle.thread=threading.Thread(target=run,name='lvw-owned-control',daemon=True)
        handle.thread.start()
        try:
            while not handle.done.wait(.1):observer()
            observer()
            if handle.error is not None:raise handle.error
            return handle.value
        finally:
            handle.cancel()
            handle.thread.join(2)
            if handle.thread.is_alive():self._pending.append(handle)

    def _validate(self,method,path,payload,timeout):
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
        return body

    def _request(self,method,path,*,payload=None,timeout=20,owned=None):
        body=self._validate(method,path,payload,timeout)
        deadline = time.monotonic() + timeout
        connection = self._make_connection(timeout)
        response = None;successful=False
        try:
            if owned is not None:
                if owned.abort.is_set():raise ControlError('CONTROL_ABORTED')
                self._connect_owned(connection,timeout)
                owned.attach(connection.sock)
                remaining=deadline-time.monotonic()
                if owned.abort.is_set():raise ControlError('CONTROL_ABORTED')
                if remaining<=0:raise ControlError('CONTROL_DEADLINE')
                connection.sock.settimeout(remaining)
            connection.request(method, path, body, {'Content-Type':'application/json',
                'Origin':self.endpoint, 'X-LVW-Control':'local-ui'})
            active_socket = connection.sock
            response = connection.getresponse()
            if not 200 <= response.status < 300:
                raise ControlError('CONTROL_HTTP_' + str(response.status))
            raw = bytearray()
            while True:
                if owned is not None and owned.abort.is_set():raise ControlError('CONTROL_ABORTED')
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
            successful=True
            return response.status, value
        finally:
            if response is not None:
                response.close()
            self._finish_connection(connection,successful)
            if owned is not None:
                with owned.guard:owned.sock=None

    def _make_connection(self,timeout):
        return http.client.HTTPConnection('127.0.0.1',self.port,timeout=timeout)

    def _connect_owned(self,connection,timeout):
        connection.timeout=min(1,timeout);connection.connect()

    def _finish_connection(self,connection,successful):connection.close()


class _NoReconnectConnection(http.client.HTTPConnection):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.initial_connect=True

    def connect(self):
        if not self.initial_connect:raise ControlError('PINNED_CONNECTION_RECONNECT_FORBIDDEN')
        self.initial_connect=False
        super().connect()


class PinnedLoopbackClient(LoopbackClient):
    """One proven Comfy TCP peer, no transparent reconnection to a replacement.

    Pin before queueing work; the expensive native owner proof is then outside
    cancellation's short preparation window. Any broken/closed connection fails
    the phase rather than connecting a cancel request to another process.
    """
    def __init__(self,endpoint,**kwargs):
        super().__init__(endpoint,**kwargs)
        if self.port!=8191:raise ControlError('PINNED_COMFY_ONLY')
        self.connection=None;self.socket=None;self.proof=None;self.used=False

    def pin(self,prove):
        if self.used or not callable(prove):raise ControlError('PINNED_SESSION_REPLAY_OR_PROOF_INVALID')
        self.used=True;before=copy.deepcopy(prove())
        if (not isinstance(before,dict) or any(type(before.get(k)) is not int or before[k]<=0 for k in ('pid','start_ticks'))):
            raise ControlError('PINNED_OWNER_PROOF_INVALID')
        connection=_NoReconnectConnection('127.0.0.1',8191,timeout=2)
        try:
            connection.connect()
            if prove()!=before or connection.sock is None:raise ControlError('PINNED_OWNER_CHANGED')
            self.connection=connection;self.socket=connection.sock;self.proof=before
            return copy.deepcopy(before)
        except BaseException:
            connection.close();raise

    def _make_connection(self,timeout):
        if (self.connection is None or self.connection.sock is not self.socket or self.socket is None
                or self.socket.fileno()<0):raise ControlError('PINNED_CONNECTION_LOST')
        self.connection.timeout=timeout;self.socket.settimeout(timeout)
        return self.connection

    def _connect_owned(self,connection,timeout):pass # Already pinned; never reconnect.

    def _finish_connection(self,connection,successful):
        if not successful or connection.sock is not self.socket:self.close()

    def close(self):
        if self.connection is not None:self.connection.close()
        self.connection=None;self.socket=None
