import importlib.util
import inspect
from pathlib import Path
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("v0_s0_live_probe.py")
SPEC = importlib.util.spec_from_file_location("v0_s0_live_probe", MODULE_PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


GPU_CLEAN = [{"total_mib": 24564, "used_mib": 1530, "free_mib": 22609}]
COMFY = r"C:\ComfyUI-aki-v2\python\python.exe"
OLLAMA = r"C:\Users\USER\AppData\Local\Programs\Ollama\ollama.exe"


def preflight(*, native=None, wsl=None, processes=None, listeners=None):
    return probe.evaluate_windows_preflight(
        native or GPU_CLEAN, wsl or GPU_CLEAN, processes or [], listeners or [],
        comfy_python_win=COMFY, ollama_win=OLLAMA,
    )


class WindowsNativePreflightTests(unittest.TestCase):
    def test_clean_baseline_passes(self):
        result = preflight()
        self.assertTrue(result["passed"])
        self.assertEqual(result["service_starts"], 0)

    def test_used_above_4096_fails_closed(self):
        gpu = [{"total_mib": 24564, "used_mib": 4097, "free_mib": 20467}]
        result = preflight(native=gpu, wsl=gpu)
        self.assertFalse(result["passed"])
        self.assertIn("GPU_PREFLIGHT_USED_ABOVE_4096_MIB", result["stop_reasons"])
        self.assertEqual(result["service_starts"], 0)

    def test_windows_wsl_samples_within_128_mib_tolerance_pass(self):
        wsl = [{"total_mib": 24564, "used_mib": 1658, "free_mib": 22481}]
        result = preflight(wsl=wsl)
        self.assertTrue(result["passed"])
        self.assertEqual(result["windows_wsl_per_gpu_deltas"][0]["used_delta_mib"], 128)
        self.assertEqual(result["windows_wsl_per_gpu_deltas"][0]["free_delta_mib"], 128)

    def test_windows_wsl_samples_over_128_mib_tolerance_fail_closed(self):
        wsl = [{"total_mib": 24564, "used_mib": 1659, "free_mib": 22480}]
        result = preflight(wsl=wsl)
        self.assertFalse(result["passed"])
        self.assertIn("GPU_PREFLIGHT_WINDOWS_WSL_MISMATCH", result["stop_reasons"])

    def test_port_owner_fails_closed(self):
        result = preflight(listeners=[{"LocalPort": 8191, "OwningProcess": 42}])
        self.assertFalse(result["passed"])
        self.assertIn("GPU_PREFLIGHT_AUTHORIZED_PORT_LISTENER_PRESENT", result["stop_reasons"])
        self.assertEqual(result["service_starts"], 0)

    def test_comfy_portable_python_fails_closed(self):
        process = {"Name": "python.exe", "ProcessId": 42, "ExecutablePath": COMFY,
                   "CommandLine": COMFY + r" C:\ComfyUI-aki-v2\ComfyUI\main.py"}
        result = preflight(processes=[process])
        self.assertFalse(result["passed"])
        self.assertIn("GPU_PREFLIGHT_TARGET_PROCESS_PRESENT", result["stop_reasons"])

    def test_ollama_process_fails_closed(self):
        process = {"Name": "ollama.exe", "ProcessId": 43, "ExecutablePath": OLLAMA,
                   "CommandLine": OLLAMA + " serve"}
        result = preflight(processes=[process])
        self.assertFalse(result["passed"])
        self.assertEqual(result["service_starts"], 0)

    def test_gpu_csv_requires_total_used_free(self):
        self.assertEqual(probe.parse_gpu_csv("24564, 1530, 22609\n"), GPU_CLEAN)
        with self.assertRaisesRegex(ValueError, "GPU_PREFLIGHT_NATIVE_PARSE_FAILED"):
            probe.parse_gpu_csv("24564, 1530\n")

    def test_live_run_orders_preflight_before_any_service_start(self):
        source = inspect.getsource(probe.Probe.run)
        self.assertLess(source.index("self.windows_native_preflight()"), source.index("self.start_services()"))


class CleanupCorrelationTests(unittest.TestCase):
    def test_planned_one_with_empty_log_is_not_cleaned(self):
        result = probe.evaluate_request_trace("", planned_calls=1, terminal_ps_empty=True,
                                              final_cleanup_proven=True)
        self.assertFalse(result["all_started_calls_cleaned"])

    def test_normal_chat_then_cleanup(self):
        log = ('[GIN] x | 200 | 1s | 127.0.0.1 | POST     "/api/chat"\n'
               '[GIN] x | 200 | 1ms | 127.0.0.1 | POST     "/api/generate"\n')
        result = probe.evaluate_request_trace(log, planned_calls=1, terminal_ps_empty=True,
                                              final_cleanup_proven=True)
        self.assertTrue(result["all_started_calls_cleaned"])
        self.assertTrue(result["strict_completion_order_chat_then_cleanup"])

    def test_timeout_cleanup_then_chat_499_is_cleaned(self):
        log = ('[GIN] x | 200 | 61ms | 127.0.0.1 | POST     "/api/generate"\n'
               '[GIN] x | 499 | 2m2s | 127.0.0.1 | POST     "/api/chat"\n')
        result = probe.evaluate_request_trace(log, planned_calls=1, terminal_ps_empty=True,
                                              final_cleanup_proven=True)
        self.assertTrue(result["all_started_calls_cleaned"])
        self.assertFalse(result["strict_completion_order_chat_then_cleanup"])
        self.assertEqual([x["http_status"] for x in result["raw_completion_order"]], [200, 499])

    def test_planned_four_partial_one_pair_proves_started_call_cleaned(self):
        log = ('[GIN] x | 200 | 1s | 127.0.0.1 | POST     "/api/chat"\n'
               '[GIN] x | 200 | 1ms | 127.0.0.1 | POST     "/api/generate"\n')
        result = probe.evaluate_request_trace(log, planned_calls=4, terminal_ps_empty=True,
                                              final_cleanup_proven=True)
        self.assertTrue(result["all_started_calls_cleaned"])
        self.assertEqual(result["observed_started_visual_calls"], 1)

    def test_observed_calls_over_plan_is_not_cleaned(self):
        pair = ('[GIN] x | 200 | 1s | 127.0.0.1 | POST     "/api/chat"\n'
                '[GIN] x | 200 | 1ms | 127.0.0.1 | POST     "/api/generate"\n')
        result = probe.evaluate_request_trace(pair * 2, planned_calls=1, terminal_ps_empty=True,
                                              final_cleanup_proven=True)
        self.assertFalse(result["all_started_calls_cleaned"])

    def test_missing_cleanup_fails(self):
        log = '[GIN] x | 200 | 1s | 127.0.0.1 | POST     "/api/chat"\n'
        result = probe.evaluate_request_trace(log, planned_calls=1, terminal_ps_empty=True,
                                              final_cleanup_proven=True)
        self.assertFalse(result["all_started_calls_cleaned"])

    def test_non_200_cleanup_fails(self):
        log = ('[GIN] x | 200 | 1s | 127.0.0.1 | POST     "/api/chat"\n'
               '[GIN] x | 500 | 1ms | 127.0.0.1 | POST     "/api/generate"\n')
        result = probe.evaluate_request_trace(log, planned_calls=1, terminal_ps_empty=True,
                                              final_cleanup_proven=True)
        self.assertFalse(result["all_started_calls_cleaned"])

    def test_nonempty_terminal_ps_fails(self):
        log = ('[GIN] x | 200 | 1s | 127.0.0.1 | POST     "/api/chat"\n'
               '[GIN] x | 200 | 1ms | 127.0.0.1 | POST     "/api/generate"\n')
        result = probe.evaluate_request_trace(log, planned_calls=1, terminal_ps_empty=False,
                                              final_cleanup_proven=True)
        self.assertFalse(result["all_started_calls_cleaned"])


class HistoryFailureTests(unittest.TestCase):
    def test_history_error_preserves_model_timeout_primary_cause(self):
        history = {"outputs": {}, "status": {"messages": [["execution_error", {
            "exception_message": '{"code":"MODEL_TIMEOUT","details":{"subcode":"OLLAMA_TIMEOUT"},'
                                 '"message":"Ollama request timed out"}'
        }]]}}
        failure = probe.history_primary_failure(history)
        self.assertEqual(failure["code"], "MODEL_TIMEOUT")
        self.assertEqual(failure["subcode"], "OLLAMA_TIMEOUT")
        self.assertEqual(failure["failure"], "MODEL_TIMEOUT/OLLAMA_TIMEOUT: Ollama request timed out")

    def test_public_attempt_keeps_history_primary_cause_without_keyerror(self):
        owner = object.__new__(probe.Probe)
        owner.run_id = "fixture-run"
        owner.resource_stop = False
        owner.remote_stop = False
        owner.attempts = {"image": [], "video": []}
        owner.workflow = lambda kind: ({"2": {"class_type": "LVWImagePromptBridge", "inputs": {}}}, "2")
        history = {"outputs": {}, "status": {"messages": [["execution_error", {
            "exception_message": '{"code":"MODEL_TIMEOUT","details":{"subcode":"OLLAMA_TIMEOUT"},'
                                 '"message":"Ollama request timed out"}'
        }]]}}
        responses = iter([
            (200, '{"prompt_id":"fixture-prompt"}'),
            (200, '{"fixture-prompt":' + probe.json.dumps(history) + '}'),
            (200, '{"models":[]}'),
            (200, '{"models":[{"name":"gemma4:26b"}]}'),
        ])
        owner.http = lambda *args, **kwargs: next(responses)
        owner.emit = lambda *args, **kwargs: None
        with mock.patch.object(probe.time, "sleep", return_value=None):
            self.assertFalse(owner.attempt("image", 1))
        attempt = owner.attempts["image"][0]
        self.assertEqual(attempt["failure_code"], "MODEL_TIMEOUT")
        self.assertEqual(attempt["failure_subcode"], "OLLAMA_TIMEOUT")
        self.assertNotIn("KeyError", attempt["failure"])
        self.assertTrue(attempt["cleanup_failure"].startswith("RESOURCE_RELEASE_PENDING"))
        self.assertTrue(attempt["failure"].startswith("MODEL_TIMEOUT/OLLAMA_TIMEOUT"))


if __name__ == "__main__":
    unittest.main()
