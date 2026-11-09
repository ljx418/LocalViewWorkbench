import json
import threading
import unittest

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import NODE_CLASS_MAPPINGS
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError


class Frame:
    shape = (1, 1, 3)


class Transport:
    endpoint = "http://127.0.0.1:11434/api/chat"
    def __init__(self, cancel, trigger=False):
        self.cancel = cancel; self.trigger = trigger; self.calls = 0; self.cleanups = 0
    def chat(self, payload, timeout_seconds):
        self.calls += 1
        if self.trigger: self.cancel.set()
        content = {"observations":["a red object on a plain background"],"inferences":[],"unknowns":[],
                   "prompt":"red object, plain background, soft light","tags":["red"],"change":"baseline"}
        return json.dumps({"done":True,"done_reason":"stop","message":{"role":"assistant","content":json.dumps(content)}})
    def cleanup(self, model, timeout_seconds): self.cleanups += 1


class VideoCancellationTests(unittest.TestCase):
    def node(self, transport, cancel):
        return NODE_CLASS_MAPPINGS["LVWVideoFramesPromptBridge"](transport=transport,
                            encoder=lambda frame: "fixture", cancel_event=cancel)

    def test_cancel_before_first_frame_has_no_provider_side_effect(self):
        cancel = threading.Event(); cancel.set(); transport = Transport(cancel)
        with self.assertRaises(BridgeError) as error:
            self.node(transport, cancel).analyze([Frame()] * 4)
        self.assertEqual("JOB_CANCELLED", error.exception.code)
        self.assertEqual((0,0), (transport.calls, transport.cleanups))

    def test_cancel_during_call_cleans_and_discards_late_success(self):
        cancel = threading.Event(); transport = Transport(cancel, trigger=True)
        with self.assertRaises(BridgeError) as error:
            self.node(transport, cancel).analyze([Frame()] * 4)
        self.assertEqual("JOB_CANCELLED", error.exception.code)
        self.assertEqual((1,1), (transport.calls, transport.cleanups))
        self.assertEqual(1, len(error.exception.details["prior_frame_raw_responses"]))
        self.assertNotIn("suggestion", error.exception.details)
        # Once the started call and its cleanup actually finish, the shared
        # inference slot can be used by the next request.
        next_cancel = threading.Event(); next_transport = Transport(next_cancel)
        self.node(next_transport, next_cancel).analyze([Frame()] * 4)
        self.assertEqual((4,4), (next_transport.calls, next_transport.cleanups))

    def test_cancel_does_not_release_slot_before_active_call_stops(self):
        cancel = threading.Event(); entered = threading.Event(); release = threading.Event()
        class BlockingTransport(Transport):
            def chat(self, payload, timeout_seconds):
                entered.set()
                if not release.wait(3): raise RuntimeError("test release timed out")
                return super().chat(payload, timeout_seconds)
        transport = BlockingTransport(cancel)
        errors = []
        def work():
            try: self.node(transport, cancel).analyze([Frame()] * 4)
            except BaseException as error: errors.append(error)
        thread = threading.Thread(target=work)
        thread.start()
        try:
            self.assertTrue(entered.wait(2))
            cancel.set()
            other_cancel = threading.Event(); other = Transport(other_cancel)
            with self.assertRaises(BridgeError) as busy:
                self.node(other, other_cancel).analyze([Frame()] * 4)
            self.assertEqual("RESOURCE_BUSY", busy.exception.code)
            self.assertEqual(0, other.calls)
        finally:
            release.set(); thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertEqual("JOB_CANCELLED", errors[0].code)
        self.assertEqual(1, transport.cleanups)


if __name__ == "__main__":
    unittest.main()
