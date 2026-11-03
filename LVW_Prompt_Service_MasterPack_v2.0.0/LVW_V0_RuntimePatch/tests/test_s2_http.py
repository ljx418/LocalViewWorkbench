"""Synthetic HTTP boundaries: no service or socket is opened."""
import unittest
import threading
from unittest.mock import MagicMock, patch

from tools.v0_s2_http import ControlError, LoopbackClient,PinnedLoopbackClient,_NoReconnectConnection


class ControlClientTests(unittest.TestCase):
    def connection(self, *, status=200, chunks=(b'{"status":"idle"}', b'')):
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = status
        response.read1.side_effect = chunks
        return connection, response

    def test_public_control_headers_and_terminal_close(self):
        connection, response = self.connection()
        with patch('http.client.HTTPConnection', return_value=connection) as factory:
            self.assertEqual((200, {'status':'idle'}), LoopbackClient('http://127.0.0.1:8191').request('GET','/lvw/v0/video/status'))
        factory.assert_called_once_with('127.0.0.1',8191,timeout=20)
        headers=connection.request.call_args.args[3]
        self.assertEqual('http://127.0.0.1:8191',headers['Origin'])
        self.assertEqual('local-ui',headers['X-LVW-Control'])
        response.close.assert_called_once();connection.close.assert_called_once()

    def test_redirect_is_failure_without_followup_or_body_read(self):
        connection,response=self.connection(status=302)
        with patch('http.client.HTTPConnection',return_value=connection) as factory:
            with self.assertRaisesRegex(ControlError,'HTTP_302'):
                LoopbackClient('http://127.0.0.1:11434').request('GET','/api/ps')
        self.assertEqual(1,factory.call_count)
        response.read1.assert_not_called();connection.close.assert_called_once()

    def test_workbench_is_post_only_and_only_on_comfy_endpoint(self):
        with patch('http.client.HTTPConnection') as factory:
            for endpoint,method in [('http://127.0.0.1:8191','GET'),('http://127.0.0.1:11434','POST')]:
                with self.subTest(endpoint=endpoint),self.assertRaises(ControlError):
                    LoopbackClient(endpoint).request(method,'/lvw/v0/video/workbench')
            factory.assert_not_called()
        connection,response=self.connection(chunks=(b'{"result":{}}',b''))
        with patch('http.client.HTTPConnection',return_value=connection):
            LoopbackClient('http://127.0.0.1:8191').request('POST','/lvw/v0/video/workbench',payload={'action':'preview'})
        self.assertEqual('POST',connection.request.call_args.args[0])
        response.close.assert_called_once();connection.close.assert_called_once()

    def test_detached_close_response_socket_keeps_total_deadline(self):
        connection,response=self.connection()
        owned_socket=connection.sock
        def detach():
            connection.sock=None
            return response
        connection.getresponse.side_effect=detach
        with patch('http.client.HTTPConnection',return_value=connection):
            LoopbackClient('http://127.0.0.1:11434').request('GET','/api/ps')
        self.assertEqual(2,owned_socket.settimeout.call_count)
        self.assertLessEqual(owned_socket.settimeout.call_args.args[0],20)

    def test_response_exact_limit_and_one_over(self):
        for data, valid in [(b'{"x":1}',True),(b'{"x":10}',False)]:
            connection,response=self.connection(chunks=(data,b''))
            with self.subTest(data=data),patch('http.client.HTTPConnection',return_value=connection):
                client=LoopbackClient('http://127.0.0.1:11434',response_limit=7)
                if valid:self.assertEqual({'x':1},client.request('GET','/api/ps')[1])
                else:
                    with self.assertRaisesRegex(ControlError,'RESPONSE_LIMIT'):client.request('GET','/api/ps')
            connection.close.assert_called_once()

    def test_invalid_routes_never_open_socket(self):
        with patch('http.client.HTTPConnection') as factory:
            for endpoint in ['http://localhost:8191','http://127.0.0.1:8191/','https://127.0.0.1:8191','http://example.org']:
                with self.subTest(endpoint=endpoint),self.assertRaises(ControlError):LoopbackClient(endpoint)
            client=LoopbackClient('http://127.0.0.1:8191')
            for method,path in [('POST','/interrupt'),('GET','//example.org'),('GET','/history/../api/ps'),('GET','/api/ps'),('GET','/prompt')]:
                with self.subTest(path=path),self.assertRaises(ControlError):client.request(method,path)
            factory.assert_not_called()

    def test_malformed_response_and_deadline_close(self):
        for chunks,times,error in [((b'[]',b''),[0,0,0], 'RESPONSE_SHAPE'),((b'{}',b''),[0,21], 'DEADLINE')]:
            connection,response=self.connection(chunks=chunks)
            with patch('http.client.HTTPConnection',return_value=connection),patch('time.monotonic',side_effect=times):
                with self.assertRaisesRegex(ControlError,error):LoopbackClient('http://127.0.0.1:11434').request('GET','/api/ps')
            connection.close.assert_called_once()

    def test_pinned_control_uses_one_proven_peer_for_queue_status_and_cancel(self):
        connection,response=self.connection(chunks=(b'{}',b'',b'{}',b'',b'{}',b''))
        connection.sock.fileno.return_value=5;proof={'pid':10,'start_ticks':100}
        with patch('tools.v0_s2_http._NoReconnectConnection',return_value=connection) as factory:
            client=PinnedLoopbackClient('http://127.0.0.1:8191');self.assertEqual(proof,client.pin(lambda:proof))
            client.request('POST','/prompt',payload={'prompt':{}})
            client.request('GET','/lvw/v0/video/status',observer=lambda:None)
            client.request('POST','/lvw/v0/video/cancel',payload={'run_token':'one'},observer=lambda:None)
            connection.close.assert_not_called();client.close()
        self.assertEqual(1,factory.call_count);self.assertEqual(1,connection.connect.call_count)
        self.assertEqual(3,connection.request.call_count);self.assertEqual(1,connection.close.call_count)
        with self.assertRaises(ControlError):client.pin(lambda:proof)

    def test_pinned_owner_change_or_dead_socket_never_sends_cancel_to_replacement(self):
        proof={'pid':10,'start_ticks':100}
        for case in ('root-change','socket-gone','closed-fd','http-error'):
            connection,response=self.connection(status=503 if case=='http-error' else 200)
            connection.sock.fileno.return_value=5
            with self.subTest(case=case),patch('tools.v0_s2_http._NoReconnectConnection',return_value=connection) as factory:
                client=PinnedLoopbackClient('http://127.0.0.1:8191')
                if case=='root-change':
                    checks=iter([proof,{**proof,'start_ticks':101}])
                    with self.assertRaises(ControlError):client.pin(lambda:next(checks))
                else:
                    client.pin(lambda:proof)
                    if case=='socket-gone':connection.sock=None
                    if case=='closed-fd':connection.sock.fileno.return_value=-1
                    with self.assertRaises(ControlError):client.request('GET','/lvw/v0/video/status')
                sent=connection.request.call_count
                with self.assertRaises(ControlError):client.request('POST','/lvw/v0/video/cancel',payload={'run_token':'one'})
                self.assertEqual(sent,connection.request.call_count);self.assertEqual(1,factory.call_count)
                client.close()

    def test_pinned_transport_refuses_http_clients_automatic_reconnect(self):
        with patch('http.client.HTTPConnection.connect') as connect:
            connection=_NoReconnectConnection('127.0.0.1',8191)
            connection.connect()
            with self.assertRaises(ControlError):connection.connect()
        self.assertEqual(1,connect.call_count)

    def test_pinned_observer_abort_closes_only_owned_socket_and_reaps_worker(self):
        connection,response=self.connection();connection.sock.fileno.return_value=5
        stopped=threading.Event();reading=threading.Event();owned_socket=connection.sock
        owned_socket.shutdown.side_effect=lambda *args:stopped.set()
        def read(count):
            reading.set()
            if not stopped.wait(2):raise AssertionError('owned request not interrupted')
            raise OSError('owned interruption')
        response.read1.side_effect=read
        def observer():
            if reading.is_set():raise ControlError('synthetic resource limit')
        with patch('tools.v0_s2_http._NoReconnectConnection',return_value=connection):
            client=PinnedLoopbackClient('http://127.0.0.1:8191');client.pin(lambda:{'pid':10,'start_ticks':100})
            with self.assertRaisesRegex(ControlError,'resource limit'):
                client.request('GET','/lvw/v0/video/status',observer=observer)
            self.assertEqual(0,client.pending_count());self.assertIsNone(client.connection)
            self.assertTrue(stopped.is_set());connection.close.assert_called_once()
            with self.assertRaises(ControlError):client.request('POST','/lvw/v0/video/cancel',payload={'run_token':'one'})
        self.assertEqual(1,connection.request.call_count)

    def test_workbench_409_retains_bounded_actual_error_body_and_closes_connection(self):
        raw=b'{"error":{"code":"ATTEMPT_STALE"}}'
        connection,response=self.connection(status=409,chunks=(raw,b''))
        with patch('http.client.HTTPConnection',return_value=connection),self.assertRaises(ControlError) as raised:
            LoopbackClient('http://127.0.0.1:8191').request('POST','/lvw/v0/video/workbench',payload={'action':'adopt','run_token':'one'})
        self.assertEqual(409,raised.exception.http_status);self.assertEqual(raw,raised.exception.response_raw)
        self.assertEqual('ATTEMPT_STALE',raised.exception.response['error']['code']);connection.close.assert_called_once()


if __name__ == '__main__':unittest.main()
