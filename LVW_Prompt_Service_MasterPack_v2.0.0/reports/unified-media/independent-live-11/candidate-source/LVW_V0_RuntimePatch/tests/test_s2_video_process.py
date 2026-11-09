import sys
import threading
import time
import unittest
from unittest.mock import patch

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_process import run_bounded


class VideoProcessTests(unittest.TestCase):
    def run_child(self, code, **kwargs):
        return run_bounded([sys.executable, "-c", code], timeout_seconds=kwargs.pop("timeout_seconds", 5), **kwargs)

    def test_exact_combined_output_and_one_over(self):
        result = self.run_child("import os;os.write(1,b'1234');os.write(2,b'5678')", output_limit=8)
        self.assertEqual((b"1234", b"5678", 0), (result.stdout, result.stderr, result.returncode))
        with self.assertRaises(BridgeError) as error:
            self.run_child("import os;os.write(1,b'123456789')", output_limit=8)
        self.assertEqual("VIDEO_PROCESS_OUTPUT_LIMIT", error.exception.details["subcode"])

    def test_nonzero_exit_does_not_become_success(self):
        with self.assertRaises(BridgeError) as error:
            self.run_child("import sys;sys.exit(3)")
        self.assertEqual("VIDEO_PROCESS_FAILED", error.exception.details["subcode"])

    def test_internal_receipt_observes_actual_failed_child_after_reaping(self):
        receipts=[]
        with self.assertRaises(BridgeError):
            self.run_child("import sys;print('raw-out');print('raw-error',file=sys.stderr);sys.exit(7)",on_result=receipts.append)
        self.assertEqual(1,len(receipts));self.assertEqual(7,receipts[0].returncode)
        self.assertEqual(b'raw-out\n',receipts[0].stdout);self.assertEqual(b'raw-error\n',receipts[0].stderr)
        with patch('subprocess.Popen') as spawn,self.assertRaises(ValueError):self.run_child('pass',on_result=1)
        spawn.assert_not_called()

    def test_small_overflow_is_detected_before_child_finishes(self):
        start = time.monotonic()
        with self.assertRaises(BridgeError) as error:
            self.run_child("import os,time;os.write(2,b'123456789');time.sleep(20)", output_limit=8)
        self.assertEqual("VIDEO_PROCESS_OUTPUT_LIMIT", error.exception.details["subcode"])
        self.assertLess(time.monotonic() - start, 3)

    def test_pre_cancel_does_not_spawn(self):
        cancel = threading.Event(); cancel.set()
        with patch("subprocess.Popen") as spawn, self.assertRaises(BridgeError) as error:
            self.run_child("pass", cancel=cancel)
        spawn.assert_not_called()
        self.assertEqual("JOB_CANCELLED", error.exception.code)

    def test_timeout_reaps_its_child(self):
        import subprocess
        real_spawn = subprocess.Popen
        children = []
        def spawn(*args, **kwargs):
            child = real_spawn(*args, **kwargs); children.append(child); return child
        with patch("subprocess.Popen", side_effect=spawn), self.assertRaises(BridgeError) as error:
            self.run_child("import time;time.sleep(20)", timeout_seconds=.1)
        self.assertEqual("VIDEO_PROCESS_TIMEOUT", error.exception.details["subcode"])
        self.assertIsNotNone(children[0].poll())

    def test_running_cancel_reaps_child_with_bounded_feedback(self):
        import subprocess
        real_spawn = subprocess.Popen
        children = []
        cancel = threading.Event()
        def spawn(*args, **kwargs):
            child = real_spawn(*args, **kwargs); children.append(child); cancel.set(); return child
        started = time.monotonic()
        with patch("subprocess.Popen", side_effect=spawn), self.assertRaises(BridgeError) as error:
            self.run_child("import time;time.sleep(20)", cancel=cancel)
        self.assertEqual("JOB_CANCELLED", error.exception.code)
        self.assertIsNotNone(children[0].poll())
        self.assertLess(time.monotonic() - started, 3)

    def test_invalid_limits_and_start_failure(self):
        for limit in (0, -1, True, 16 * 1024 * 1024 + 1):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                self.run_child("pass", output_limit=limit)
        with patch("subprocess.Popen", side_effect=OSError("sensitive path")), self.assertRaises(BridgeError) as error:
            self.run_child("pass")
        self.assertNotIn("sensitive path", str(error.exception))


if __name__ == "__main__":
    unittest.main()
