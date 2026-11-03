from types import SimpleNamespace
import threading
import unittest

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import core
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_request import VideoRequestOwner
from LVW_V0_RuntimePatch.tests.test_s2_video_cancel import Frame, Transport


class Decoder:
    def decode(self, reference, cancel=None):
        return SimpleNamespace(frames=[Frame()] * 4, source_sha256="a" * 64, manifest=[])


class VideoRequestTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(core._RESOURCE_RELEASE_PENDING.clear)

    def owner(self, decoder=None, transport=None):
        return VideoRequestOwner(decoder or Decoder(), bridge=core.BridgeOwner(
            transport=transport or Transport(threading.Event()), encoder=lambda f:"fixture"),
            tensor_builder=lambda f:f, preflight=lambda:{"fixture":True})

    def run_owner(self, owner, token="run-1"):
        return owner.run(token, "clip.mp4", model=core.DEFAULT_MODEL, user_instruction="",
                         mode="realistic", timeout_seconds=120)

    def test_success_has_bound_identity_and_replay_is_rejected(self):
        owner = self.owner(); result = self.run_owner(owner)
        self.assertEqual("run-1", result["run_token"])
        self.assertEqual("succeeded", owner.status("run-1")["status"])
        self.assertEqual("released", owner.status("run-1")["resource_state"])
        with self.assertRaises(core.BridgeError): self.run_owner(owner)
        with self.assertRaises(core.BridgeError): owner.cancel("wrong-token")

    def test_preparation_owns_shared_slot_and_cancel_epoch_is_idempotent(self):
        entered = threading.Event(); finish = threading.Event()
        class BlockingDecoder(Decoder):
            def decode(self, reference, cancel=None):
                entered.set()
                if not finish.wait(3): raise RuntimeError("test release timed out")
                return super().decode(reference, cancel)
        owner = self.owner(BlockingDecoder()); errors = []
        def run():
            try: self.run_owner(owner)
            except BaseException as exc: errors.append(exc)
        thread = threading.Thread(target=run); thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertEqual(1, owner.cancel("run-1")["cancel_epoch"])
            self.assertEqual(1, owner.cancel("run-1")["cancel_epoch"])
            self.assertEqual("releasing", owner.status("run-1")["resource_state"])
            with self.assertRaises(core.BridgeError) as busy:
                self.run_owner(self.owner(), "other")
            self.assertEqual("RESOURCE_BUSY", busy.exception.code)
        finally:
            finish.set(); thread.join(4)
        self.assertFalse(thread.is_alive())
        self.assertEqual("JOB_CANCELLED", errors[0].code)
        self.assertEqual("cancelled", owner.status("run-1")["status"])
        self.assertEqual("released", owner.status("run-1")["resource_state"])

    def test_cleanup_failure_quarantines_all_bridge_entrypoints(self):
        class DirtyTransport(Transport):
            def cleanup(self, model, timeout_seconds):
                raise RuntimeError("cleanup failed")
        owner = self.owner(transport=DirtyTransport(threading.Event()))
        with self.assertRaises(core.BridgeError): self.run_owner(owner)
        self.assertEqual("unknown", owner.status("run-1")["resource_state"])
        self.assertTrue(core._RESOURCE_RELEASE_PENDING.is_set())
        with self.assertRaises(core.BridgeError) as busy:
            self.run_owner(self.owner(), "other")
        self.assertEqual("RESOURCE_BUSY", busy.exception.code)
        with self.assertRaises(core.BridgeError):
            self.owner().bridge.analyze_image([Frame()], model=core.DEFAULT_MODEL, user_instruction="",
                                             mode="realistic", timeout_seconds=120)

    def test_same_thread_reentry_does_not_replace_current_request(self):
        owner = self.owner()
        rejected = []
        def started(token):
            try: self.run_owner(owner, "nested")
            except core.BridgeError as error: rejected.append(error.code)
            self.assertEqual(token, owner.current_status()["run_token"])
        result = owner.run("outer", "clip.mp4", model=core.DEFAULT_MODEL, user_instruction="",
                           mode="realistic", timeout_seconds=120, state_hook=started)
        self.assertEqual(["RESOURCE_BUSY"], rejected)
        self.assertEqual("outer", result["run_token"])
        self.assertEqual("succeeded", owner.status("outer")["status"])


if __name__ == "__main__": unittest.main()
