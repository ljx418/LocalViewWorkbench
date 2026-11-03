import threading
import unittest
from unittest.mock import patch

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_transport import InterruptibleOllamaTransport


class FakeSocket:
    def __init__(self): self.stopped = threading.Event(); self.closed = False
    def dup(self): return self
    def shutdown(self, how): self.stopped.set()
    def close(self): self.closed = True
    def settimeout(self, seconds): pass


class Connection:
    def __init__(self, *args, **kwargs):
        self.sock = FakeSocket(); self.sent = []; self.closed = False
    def connect(self): pass
    def request(self, *args): self.sent.append(args)
    def getresponse(self): return self.response
    def close(self): self.closed = True


class TransportTests(unittest.TestCase):
    def test_unload_needs_positive_empty_inventory_even_after_cancel(self):
        event = threading.Event(); event.set()
        transport = InterruptibleOllamaTransport(); transport.bind_cancel(event)
        values = [{"done":True}, {"models":[{"name":"gemma4:26b"}]}, {"models":[]}]
        with patch.object(transport, "_control_request", side_effect=values) as control, patch("time.sleep"):
            transport.cleanup("gemma4:26b", 120)
        self.assertEqual(["/api/generate", "/api/ps", "/api/ps"], [call.args[1] for call in control.call_args_list])
        self.assertEqual("released", transport.release_evidence["state"])
        self.assertEqual(2, transport.release_evidence["checks"])

    def test_unacknowledged_or_malformed_unload_cannot_claim_release(self):
        for values in ([{"done":False}], [{"done":True}, {}], [{"done":True}, {"models":None}]):
            transport = InterruptibleOllamaTransport()
            with self.subTest(values=values), patch.object(transport, "_control_request", side_effect=values), self.assertRaises(BridgeError):
                transport.cleanup("gemma4:26b", 120)
            self.assertEqual("unproven", transport.release_evidence["state"])

    def test_still_loaded_times_out_without_unloading_other_models(self):
        transport = InterruptibleOllamaTransport()
        with patch.object(transport, "_control_request", side_effect=[{"done":True}, {"models":[{"name":"other"}]}]) as control:
            with patch("time.monotonic", side_effect=[0,0,0,0,31,31]), patch("time.sleep"), self.assertRaises(BridgeError):
                transport.cleanup("gemma4:26b", 120)
        self.assertEqual(1, sum(c.args[0] == "POST" for c in control.call_args_list))
        self.assertEqual(1, sum(c.args[0] == "GET" for c in control.call_args_list))
        self.assertEqual("gemma4:26b", control.call_args_list[0].args[2]["model"])
        self.assertEqual("unproven", transport.release_evidence["state"])

    def test_pre_cancel_sends_nothing(self):
        event = threading.Event(); event.set()
        transport = InterruptibleOllamaTransport(); transport.bind_cancel(event)
        connection = Connection()
        with patch("http.client.HTTPConnection", return_value=connection), self.assertRaises(BridgeError) as error:
            transport.chat({}, 120)
        self.assertEqual("JOB_CANCELLED", error.exception.code)
        self.assertEqual([], connection.sent)

    def test_parent_release_deadline_is_shared_and_late_empty_inventory_cannot_pass(self):
        for observed,passed in [(10,True),(10.001,False)]:
            transport=InterruptibleOllamaTransport()
            with patch.object(transport,'_control_request',side_effect=[{'done':True},{'models':[]}]) as control, \
                 patch('time.monotonic',side_effect=[5,5,6,observed]):
                if passed:transport.cleanup('gemma4:26b',120,release_deadline=10)
                else:
                    with self.assertRaises(BridgeError):transport.cleanup('gemma4:26b',120,release_deadline=10)
            self.assertEqual(5,control.call_args_list[0].args[3])
            self.assertEqual('released' if passed else 'unproven',transport.release_evidence['state'])
        transport=InterruptibleOllamaTransport()
        with patch('time.monotonic',return_value=11),patch.object(transport,'_control_request') as control,self.assertRaises(BridgeError):
            transport.cleanup('gemma4:26b',120,release_deadline=10)
        control.assert_not_called()

    def test_detached_response_keeps_owned_socket_deadline_for_chat_and_control(self):
        from unittest.mock import MagicMock
        for operation in ('chat','control'):
            connection=Connection();owned=connection.sock;owned.settimeout=MagicMock()
            class Response:
                status=200
                def __init__(self):self.chunks=iter([b'{"models":[]}',b'']);self.closed=False
                def read1(self,count):return next(self.chunks)
                def close(self):self.closed=True
            response=Response()
            def detach():connection.sock=None;return response
            connection.getresponse=detach
            transport=InterruptibleOllamaTransport()
            with self.subTest(operation=operation),patch('http.client.HTTPConnection',return_value=connection):
                if operation=='chat':self.assertEqual('{"models":[]}',transport.chat({},5))
                else:self.assertEqual({'models':[]},transport._control_request('GET','/api/ps',None,5))
            self.assertGreaterEqual(owned.settimeout.call_count,2)
            self.assertTrue(all(0<call.args[0]<=5 for call in owned.settimeout.call_args_list))
            self.assertTrue(connection.closed);self.assertTrue(response.closed)

    def test_control_redirect_is_refused_without_followup(self):
        connection = Connection()
        class Redirect:
            status = 302
            def close(self): pass
        connection.response = Redirect()
        transport = InterruptibleOllamaTransport()
        with patch("http.client.HTTPConnection", return_value=connection) as factory, self.assertRaises(BridgeError) as error:
            transport._control_request("GET", "/api/ps", None, 2)
        self.assertEqual("RESOURCE_RELEASE_PENDING", error.exception.code)
        self.assertEqual(1, factory.call_count)
        self.assertEqual(1, len(connection.sent))
        self.assertTrue(connection.closed)

    def test_interrupt_unblocks_only_owned_connection_and_returns_cancel(self):
        event = threading.Event(); entered = threading.Event()
        connection = Connection(); unrelated = FakeSocket()
        class Response:
            status = 200
            def read1(self, count):
                entered.set()
                if not connection.sock.stopped.wait(2): raise RuntimeError("test did not cancel")
                raise OSError("closed socket private path")
            def close(self): pass
        connection.response = Response()
        transport = InterruptibleOllamaTransport(); transport.bind_cancel(event)
        errors = []
        def work():
            try: transport.chat({}, 120)
            except BaseException as exc: errors.append(exc)
        with patch("http.client.HTTPConnection", return_value=connection):
            thread = threading.Thread(target=work); thread.start()
            try:
                self.assertTrue(entered.wait(1)); event.set(); transport.cancel_active()
            finally:
                connection.sock.stopped.set(); thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual("JOB_CANCELLED", errors[0].code)
        self.assertNotIn("private path", str(errors[0]))
        self.assertTrue(connection.closed)
        self.assertTrue(connection.sock.closed)
        self.assertFalse(unrelated.stopped.is_set())
        self.assertIsNone(transport._active)

    def test_success_and_http_error_are_bounded_and_closed(self):
        for status in (200, 503):
            connection = Connection()
            class Response:
                def __init__(self): self.status = status; self.chunks = iter([b'{"done":true}', b''])
                def read1(self, count): return next(self.chunks)
                def close(self): pass
            connection.response = Response()
            transport = InterruptibleOllamaTransport(); transport.bind_cancel(threading.Event())
            with patch("http.client.HTTPConnection", return_value=connection):
                if status == 200: self.assertEqual('{"done":true}', transport.chat({}, 120))
                else:
                    with self.assertRaises(BridgeError): transport.chat({}, 120)
            self.assertTrue(connection.closed)


if __name__ == "__main__": unittest.main()
