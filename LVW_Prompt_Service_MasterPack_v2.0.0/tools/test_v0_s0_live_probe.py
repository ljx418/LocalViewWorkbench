import importlib.util
import inspect
from pathlib import Path
import tempfile
from types import SimpleNamespace
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
    def run_owned_popen_fixture(self, *, ollama_proc=None, comfy_proc=None,
                                ollama_wrapper_pid=None, ollama_stop_after=None,
                                functional_success=False, expected_rc=2):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            sample = temp_path / "fixture.bin"
            sample.write_bytes(b"offline fixture")
            args = SimpleNamespace(
                run_id="fixture-run", candidate_sha="a" * 40, authorization_commit="b" * 40,
                harness_candidate_sha="c" * 40,
                evidence_dir=str(temp_path / "evidence"), receipt_path=str(temp_path / "receipt.json"),
                self_check=False, comfy_root=str(temp_path / "comfy"), comfy_python=str(temp_path / "python.exe"),
                ollama=str(temp_path / "ollama.exe"), test_source=str(temp_path / "samples"),
                powershell="powershell.exe", windows_nvidia_smi="native", wsl_nvidia_smi="wsl",
                spec_version="fixture", workpack_id="WP-FIXTURE")
            owner = probe.Probe(args)
            owner.root = temp_path
            owner.record = lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="commit\n")
            owner.verify_harness_identity = mock.Mock(return_value={"matched": True})
            owner.harness_identity = {"matched": True}
            owner.windows_native_preflight = mock.Mock(return_value={"passed": True})
            owner.reached_checks.update({"harness_identity", "service_preflight"})
            owner.locate_sample = mock.Mock(return_value=sample)
            owner.target_integrity = mock.Mock(return_value=[])
            owner.create_temp = mock.Mock()
            owner.copy_candidate = mock.Mock()
            owner.derive_media = mock.Mock()
            owner.listeners = mock.Mock(return_value=[])

            def start_services():
                owner.ollama_proc = ollama_proc
                owner.comfy_proc = comfy_proc
                owner.ollama_wrapper_pid = ollama_wrapper_pid
                owner.reached_checks.add("no_cloud")
                if functional_success:
                    owner.no_cloud_reported_true = True
                    owner.pre_model_gate = {"passed": True}
                    owner.reached_checks.update({"remote_tcp", "path_conversion"})
                    return
                raise RuntimeError("OLLAMA_NO_CLOUD_TRUE_NOT_OBSERVED_IN_SERVER_RAW")

            owner.start_services = mock.Mock(side_effect=start_services)
            owner.stop_owned = mock.Mock(side_effect=lambda pid, label: {
                "label": label,
                "pid": pid,
                "stop_attempted": bool(pid),
                "after": list(ollama_stop_after or []) if pid == ollama_wrapper_pid and pid else [],
            })
            if functional_success:
                def attempt(kind, index):
                    result = {"kind": kind, "pass": True}
                    owner.attempts[kind].append(result)
                    owner.reached_checks.add(kind + "_route")
                    owner.emit(f"attempt-{kind}-{index}.json", result)
                    return True

                def emit_request_trace():
                    document = {"visual_chat_count": 5, "all_started_calls_cleaned": True}
                    owner.emit("ollama-request-trace.json", document)
                    return document

                owner.attempt = mock.Mock(side_effect=attempt)
                owner.emit_request_trace = mock.Mock(side_effect=emit_request_trace)
            self.assertEqual(owner.run(), expected_rc)
            receipt = probe.json.loads((temp_path / "receipt.json").read_text())
            cleanup = probe.json.loads((temp_path / "evidence" / "cleanup.json").read_text())
            return receipt, cleanup

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

    def test_preflight_persists_only_counts_and_minimal_target_matches(self):
        encoded = "dXNlcj0xMjM0NTY3ODk="
        processes = [
            {"Name": "updater.exe", "ProcessId": 40, "ExecutablePath": r"C:\\Private\\updater.exe",
             "CommandLine": "--user=" + encoded + " --path=QzpcUHJpdmF0ZQ=="},
            {"Name": "ollama.exe", "ProcessId": 43, "ExecutablePath": OLLAMA,
             "CommandLine": OLLAMA + " serve"},
        ]
        result = preflight(processes=processes)
        persisted = probe.canonical(result)
        self.assertEqual(result["windows_process_count"], 2)
        self.assertEqual(result["target_process_count"], 1)
        self.assertEqual(result["target_processes"], [{"process_id": 43, "match_kind": "OLLAMA_TARGET"}])
        self.assertNotIn("CommandLine", persisted)
        self.assertNotIn(encoded, persisted)
        self.assertNotIn("Private", persisted)

    def test_gpu_csv_requires_total_used_free(self):
        self.assertEqual(probe.parse_gpu_csv("24564, 1530, 22609\n"), GPU_CLEAN)
        with self.assertRaisesRegex(ValueError, "GPU_PREFLIGHT_NATIVE_PARSE_FAILED"):
            probe.parse_gpu_csv("24564, 1530\n")

    def test_live_run_orders_preflight_before_any_service_start(self):
        source = inspect.getsource(probe.Probe.run)
        self.assertLess(source.index("self.windows_native_preflight()"), source.index("self.start_services()"))

    def test_powershell_utf8_chinese_process_json_decodes_strictly(self):
        owner = object.__new__(probe.Probe)
        owner.a = SimpleNamespace(powershell="powershell.exe")
        payload = probe.json.dumps([{"Name": "python.exe", "CommandLine": "分析工具"}], ensure_ascii=False).encode("utf-8")
        completed = SimpleNamespace(returncode=0, stdout=payload)
        with mock.patch.object(probe.subprocess, "run", return_value=completed) as run:
            result = owner.ps_json("fixture")
        self.assertEqual(result[0]["CommandLine"], "分析工具")
        self.assertIn("OutputEncoding", run.call_args.args[0][-1])

    def test_powershell_invalid_utf8_returns_stable_failure(self):
        owner = object.__new__(probe.Probe)
        owner.a = SimpleNamespace(powershell="powershell.exe")
        completed = SimpleNamespace(returncode=0, stdout=b'{"Name":"bad\xbb"}')
        with mock.patch.object(probe.subprocess, "run", return_value=completed):
            result = owner.ps_json("fixture")
        self.assertEqual(result["error_code"], "WINDOWS_OWNER_ENUMERATION_FAILED")
        self.assertEqual(result["subcode"], "POWERSHELL_UTF8_DECODE_FAILED")
        self.assertNotIn("raw", result)

    def test_preflight_enumeration_failure_emits_artifact_before_raise(self):
        owner = object.__new__(probe.Probe)
        owner.reached_checks = set()
        owner.a = SimpleNamespace(windows_nvidia_smi="native", wsl_nvidia_smi="wsl",
                                  comfy_python="C:/Comfy/python.exe", ollama="C:/Ollama/ollama.exe")
        gpu = SimpleNamespace(returncode=0, stdout="24564, 1530, 22609\n")
        owner.record = lambda *args, **kwargs: gpu
        owner.ps_json = lambda script: {"error_code": "WINDOWS_OWNER_ENUMERATION_FAILED"}
        owner.listeners = lambda: []
        emitted = {}
        owner.emit = lambda name, value: emitted.__setitem__(name, value)
        with self.assertRaisesRegex(RuntimeError, "WINDOWS_OWNER_ENUMERATION_FAILED"):
            owner.windows_native_preflight()
        artifact = emitted["preflight-baseline.json"]
        self.assertFalse(artifact["passed"])
        self.assertEqual(artifact["service_starts"], 0)
        self.assertEqual(artifact["stop_reasons"], ["WINDOWS_OWNER_ENUMERATION_FAILED"])

    def test_early_preflight_exception_writes_complete_terminal_receipt_with_zero_starts(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            args = SimpleNamespace(
                run_id="fixture-run", candidate_sha="a" * 40, authorization_commit="b" * 40,
                harness_candidate_sha="c" * 40,
                evidence_dir=str(temp_path / "evidence"), receipt_path=str(temp_path / "receipt.json"),
                self_check=False, comfy_root=str(temp_path / "comfy"), comfy_python=str(temp_path / "python.exe"),
                ollama=str(temp_path / "ollama.exe"), test_source=str(temp_path / "samples"),
                powershell="powershell.exe", windows_nvidia_smi="native", wsl_nvidia_smi="wsl",
                spec_version="fixture", workpack_id="WP-FIXTURE")
            owner = probe.Probe(args)
            owner.root = temp_path
            owner.record = lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="commit\n")
            owner.verify_harness_identity = mock.Mock(return_value={"matched": True})
            owner.harness_identity = {"matched": True}
            owner.windows_native_preflight = mock.Mock(side_effect=RuntimeError("WINDOWS_OWNER_ENUMERATION_FAILED"))
            owner.reached_checks.update({"harness_identity", "service_preflight"})
            owner.start_services = mock.Mock()
            owner.listeners = lambda *args, **kwargs: []
            owner.target_integrity = lambda: []
            self.assertEqual(owner.run(), 2)
            receipt = probe.json.loads((temp_path / "receipt.json").read_text())
            self.assertEqual(receipt["decision"], "BLOCKED")
            self.assertEqual(receipt["exact_stop_reason"], "WINDOWS_OWNER_ENUMERATION_FAILED")
            self.assertEqual(receipt["external_actions"]["ollama_process_starts"], 0)
            self.assertEqual(receipt["external_actions"]["comfyui_process_starts"], 0)
            self.assertEqual(receipt["external_actions"]["model_calls"], 0)
            statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
            self.assertEqual(statuses["windows_native_service_preflight"], "FAIL")
            self.assertTrue(all(statuses[name] == "NOT_REACHED" for name in (
                "windows_native_no_cloud_server_raw", "pre_model_remote_tcp_gate",
                "comfy_main_and_cwd_windows_path_conversion", "public_comfy_image_route",
                "public_comfy_video_route", "cleanup_and_target_integrity")))
            self.assertFalse(receipt["cleanup"]["proven"])
            self.assertTrue(receipt["cleanup"]["owned_resources_absent"])
            self.assertEqual(receipt["cleanup"]["target_integrity_comparison"], "NOT_REACHED")
            self.assertFalse(receipt["stage_pass_claim"])
            owner.start_services.assert_not_called()

    def test_primary_preflight_error_survives_secondary_final_cleanup_exceptions(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            args = SimpleNamespace(
                run_id="fixture-run", candidate_sha="a" * 40, authorization_commit="b" * 40,
                harness_candidate_sha="c" * 40,
                evidence_dir=str(temp_path / "evidence"), receipt_path=str(temp_path / "receipt.json"),
                self_check=False, comfy_root=str(temp_path / "comfy"), comfy_python=str(temp_path / "python.exe"),
                ollama=str(temp_path / "ollama.exe"), test_source=str(temp_path / "samples"),
                powershell="powershell.exe", windows_nvidia_smi="native", wsl_nvidia_smi="wsl",
                spec_version="fixture", workpack_id="WP-FIXTURE")
            owner = probe.Probe(args)
            owner.root = temp_path
            owner.record = lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="commit\n")
            owner.verify_harness_identity = mock.Mock(return_value={"matched": True})
            owner.harness_identity = {"matched": True}
            owner.windows_native_preflight = mock.Mock(side_effect=RuntimeError("WINDOWS_OWNER_ENUMERATION_FAILED"))
            owner.reached_checks.update({"harness_identity", "service_preflight"})
            owner.start_services = mock.Mock()
            owner.listeners = mock.Mock(side_effect=RuntimeError("sensitive port detail"))
            owner.target_integrity = mock.Mock(side_effect=RuntimeError("sensitive integrity detail"))
            self.assertEqual(owner.run(), 2)
            receipt = probe.json.loads((temp_path / "receipt.json").read_text())
            cleanup = probe.json.loads((temp_path / "evidence" / "cleanup.json").read_text())
            events = probe.json.loads((temp_path / "evidence" / "events.json").read_text())["events"]
            self.assertEqual(receipt["decision"], "BLOCKED")
            self.assertEqual(receipt["exact_stop_reason"], "WINDOWS_OWNER_ENUMERATION_FAILED")
            self.assertFalse(receipt["cleanup"]["proven"])
            self.assertGreaterEqual(len(cleanup["secondary_cleanup_failures"]), 2)
            self.assertTrue(any(event.get("detail") == "CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN"
                                for event in events))
            statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
            self.assertEqual(statuses["cleanup_and_target_integrity"], "FAIL")
            self.assertEqual(receipt["external_actions"]["ollama_process_starts"], 0)
            self.assertEqual(receipt["external_actions"]["comfyui_process_starts"], 0)
            owner.start_services.assert_not_called()

    def test_harness_identity_mismatch_is_stable_and_starts_no_services(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            executed = temp_path / "executed-probe.py"
            executed.write_bytes(b"executed bytes")
            args = SimpleNamespace(
                run_id="fixture-run", candidate_sha="a" * 40, authorization_commit="b" * 40,
                harness_candidate_sha="c" * 40,
                evidence_dir=str(temp_path / "evidence"), receipt_path=str(temp_path / "receipt.json"),
                self_check=False, comfy_root=str(temp_path / "comfy"), comfy_python=str(temp_path / "python.exe"),
                ollama=str(temp_path / "ollama.exe"), test_source=str(temp_path / "samples"),
                powershell="powershell.exe", windows_nvidia_smi="native", wsl_nvidia_smi="wsl",
                spec_version="fixture", workpack_id="WP-FIXTURE")
            owner = probe.Probe(args)
            owner.root = temp_path
            owner.record = lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="commit\n")
            owner.windows_native_preflight = mock.Mock()
            owner.start_services = mock.Mock()
            owner.listeners = lambda *args, **kwargs: []
            owner.target_integrity = lambda: []

            def git_result(command, **kwargs):
                if command[1] == "show":
                    return SimpleNamespace(returncode=0, stdout=b"different sealed bytes")
                return SimpleNamespace(returncode=0, stdout="d" * 40 + "\n")

            with mock.patch.object(probe, "__file__", str(executed)), \
                    mock.patch.object(probe.subprocess, "run", side_effect=git_result):
                self.assertEqual(owner.run(), 2)
            receipt = probe.json.loads((temp_path / "receipt.json").read_text())
            identity = probe.json.loads((temp_path / "evidence" / "harness-identity.json").read_text())
            self.assertEqual(receipt["exact_stop_reason"], "HARNESS_IDENTITY_MISMATCH")
            self.assertFalse(identity["matched"])
            self.assertEqual(identity["service_starts"], 0)
            self.assertEqual(receipt["harness_identity"], identity)
            statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
            self.assertEqual(statuses["harness_runtime_identity"], "FAIL")
            self.assertTrue(all(status == "NOT_REACHED" for name, status in statuses.items()
                                if name != "harness_runtime_identity"))
            self.assertFalse(receipt["cleanup"]["proven"])
            self.assertTrue(receipt["cleanup"]["owned_resources_absent"])
            self.assertEqual(receipt["cleanup"]["target_integrity_comparison"], "NOT_REACHED")
            owner.windows_native_preflight.assert_not_called()
            owner.start_services.assert_not_called()

    def test_harness_identity_records_matching_commit_blob_and_file_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            executed = Path(temp) / "executed-probe.py"
            executed.write_bytes(b"identical sealed bytes")
            owner = object.__new__(probe.Probe)
            owner.reached_checks = set()
            owner.root = Path(temp)
            owner.harness_candidate_sha = "c" * 40
            owner.commands = []
            emitted = {}
            owner.emit = lambda name, value: emitted.__setitem__(name, value)

            def git_result(command, **kwargs):
                if command[1] == "show":
                    return SimpleNamespace(returncode=0, stdout=b"identical sealed bytes")
                return SimpleNamespace(returncode=0, stdout="d" * 40 + "\n")

            with mock.patch.object(probe, "__file__", str(executed)), \
                    mock.patch.object(probe.subprocess, "run", side_effect=git_result):
                identity = owner.verify_harness_identity()
            self.assertTrue(identity["matched"])
            self.assertEqual(identity["git_blob_sha256"], identity["executed_file_sha256"])
            self.assertEqual(identity["git_blob_object_id"], "d" * 40)
            self.assertEqual(emitted["harness-identity.json"], identity)

    def test_gpu_preflight_stop_marks_only_reached_checks_failed(self):
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            args = SimpleNamespace(
                run_id="fixture-run", candidate_sha="a" * 40, authorization_commit="b" * 40,
                harness_candidate_sha="c" * 40,
                evidence_dir=str(temp_path / "evidence"), receipt_path=str(temp_path / "receipt.json"),
                self_check=False, comfy_root=str(temp_path / "comfy"), comfy_python=str(temp_path / "python.exe"),
                ollama=str(temp_path / "ollama.exe"), test_source=str(temp_path / "samples"),
                powershell="powershell.exe", windows_nvidia_smi="native", wsl_nvidia_smi="wsl",
                spec_version="fixture", workpack_id="WP-FIXTURE")
            owner = probe.Probe(args)
            owner.root = temp_path
            owner.record = lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="commit\n")
            owner.verify_harness_identity = mock.Mock(return_value={"matched": True})
            owner.harness_identity = {"matched": True}
            owner.windows_native_preflight = mock.Mock(
                side_effect=RuntimeError("WINDOWS_NATIVE_PREFLIGHT_FAILED:GPU_PREFLIGHT_USED_ABOVE_4096_MIB"))
            owner.reached_checks.update({"harness_identity", "service_preflight"})
            owner.start_services = mock.Mock()
            owner.listeners = lambda *args, **kwargs: []
            owner.target_integrity = lambda: []
            self.assertEqual(owner.run(), 2)
            receipt = probe.json.loads((temp_path / "receipt.json").read_text())
            statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
            self.assertEqual(receipt["decision"], "NO_GO")
            self.assertEqual(statuses["harness_runtime_identity"], "PASS")
            self.assertEqual(statuses["windows_native_service_preflight"], "FAIL")
            self.assertTrue(all(statuses[name] == "NOT_REACHED" for name in (
                "windows_native_no_cloud_server_raw", "pre_model_remote_tcp_gate",
                "comfy_main_and_cwd_windows_path_conversion", "public_comfy_image_route",
                "public_comfy_video_route", "cleanup_and_target_integrity")))
            self.assertTrue(receipt["cleanup"]["owned_resources_absent"])
            self.assertEqual(receipt["cleanup"]["target_integrity_comparison"], "NOT_REACHED")
            owner.start_services.assert_not_called()

    def test_started_service_actual_failure_remains_fail(self):
        statuses = probe.observable_check_statuses(
            reached_checks={"harness_identity", "service_preflight", "no_cloud"},
            identity_matched=True, preflight_passed=True, no_cloud_passed=False,
            remote_passed=False, path_passed=False, image_passed=False, video_passed=False,
            cleanup_proven=False, owned_service_started=True, owned_resources_absent=True,
            target_integrity_comparison="FAIL")
        self.assertEqual(statuses["windows_native_no_cloud_server_raw"], "FAIL")
        self.assertEqual(statuses["pre_model_remote_tcp_gate"], "NOT_REACHED")
        self.assertEqual(statuses["cleanup_and_target_integrity"], "FAIL")

    def test_successful_cleanup_and_reached_checks_pass(self):
        reached = {"harness_identity", "service_preflight", "no_cloud", "remote_tcp",
                   "path_conversion", "image_route", "video_route"}
        statuses = probe.observable_check_statuses(
            reached_checks=reached, identity_matched=True, preflight_passed=True,
            no_cloud_passed=True, remote_passed=True, path_passed=True,
            image_passed=True, video_passed=True, cleanup_proven=True,
            owned_service_started=True, owned_resources_absent=True,
            target_integrity_comparison="PASS")
        self.assertTrue(all(status == "PASS" for status in statuses.values()))

    def test_lingering_owned_popen_fails_complete_run_cleanup(self):
        proc = mock.Mock()
        proc.wait.side_effect = probe.subprocess.TimeoutExpired(cmd="owned", timeout=5)
        proc.poll.return_value = None
        receipt, cleanup = self.run_owned_popen_fixture(ollama_proc=proc)
        statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
        self.assertEqual(receipt["external_actions"]["ollama_process_starts"], 1)
        self.assertFalse(receipt["cleanup"]["owned_resources_absent"])
        self.assertFalse(receipt["cleanup"]["proven"])
        self.assertEqual(statuses["cleanup_and_target_integrity"], "FAIL")
        self.assertIn("OWNED_POPEN_WAIT_TIMEOUT:owned_ollama_popen", cleanup["secondary_cleanup_failures"])
        self.assertIn("OWNED_POPEN_STILL_RUNNING:owned_ollama_popen", cleanup["secondary_cleanup_failures"])
        self.assertFalse(cleanup["owned_popen_terminal_states"][1]["exited"])
        proc.terminate.assert_called_once_with()
        proc.kill.assert_called_once_with()

    def test_owned_popen_normal_exit_proves_cleanup(self):
        proc = mock.Mock()
        proc.wait.return_value = 0
        proc.poll.return_value = 0
        receipt, cleanup = self.run_owned_popen_fixture(ollama_proc=proc)
        statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
        self.assertEqual(receipt["external_actions"]["ollama_process_starts"], 1)
        self.assertTrue(receipt["cleanup"]["owned_resources_absent"])
        self.assertTrue(receipt["cleanup"]["proven"])
        self.assertEqual(statuses["cleanup_and_target_integrity"], "PASS")
        self.assertEqual(cleanup["secondary_cleanup_failures"], [])
        self.assertTrue(cleanup["owned_popen_terminal_states"][1]["exited"])
        proc.terminate.assert_not_called()
        proc.kill.assert_not_called()

    def test_captured_owned_pid_residual_fails_complete_run_cleanup(self):
        proc = mock.Mock()
        proc.wait.return_value = 0
        proc.poll.return_value = 0
        receipt, cleanup = self.run_owned_popen_fixture(
            ollama_proc=proc, ollama_wrapper_pid=123,
            ollama_stop_after=[{"process_id": 123}],
        )
        statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
        self.assertFalse(receipt["cleanup"]["owned_resources_absent"])
        self.assertFalse(receipt["cleanup"]["proven"])
        self.assertFalse(cleanup["proven"])
        self.assertEqual(statuses["cleanup_and_target_integrity"], "FAIL")
        self.assertEqual(cleanup["target_integrity_comparison"], "PASS")
        self.assertEqual(cleanup["secondary_cleanup_failures"], [])
        self.assertEqual(cleanup["owned_process_stops"][3]["after"], [{"process_id": 123}])

    def test_captured_owned_pid_absent_allows_complete_run_cleanup(self):
        proc = mock.Mock()
        proc.wait.return_value = 0
        proc.poll.return_value = 0
        receipt, cleanup = self.run_owned_popen_fixture(
            ollama_proc=proc, ollama_wrapper_pid=123, ollama_stop_after=[],
        )
        statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
        self.assertTrue(receipt["cleanup"]["owned_resources_absent"])
        self.assertTrue(receipt["cleanup"]["proven"])
        self.assertTrue(cleanup["proven"])
        self.assertEqual(statuses["cleanup_and_target_integrity"], "PASS")
        self.assertEqual(cleanup["target_integrity_comparison"], "PASS")
        self.assertEqual(cleanup["secondary_cleanup_failures"], [])

    def test_function_success_with_captured_pid_residual_is_no_go(self):
        proc = mock.Mock()
        proc.wait.return_value = 0
        proc.poll.return_value = 0
        receipt, cleanup = self.run_owned_popen_fixture(
            ollama_proc=proc, ollama_wrapper_pid=123,
            ollama_stop_after=[{"process_id": 123}],
            functional_success=True, expected_rc=2,
        )
        statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
        self.assertFalse(cleanup["proven"])
        self.assertEqual(statuses["cleanup_and_target_integrity"], "FAIL")
        self.assertEqual(receipt["decision"], "NO_GO")
        self.assertEqual(receipt["exact_stop_reason"], "CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN")
        self.assertNotEqual(receipt["production_path_status"],
                            "PUBLIC_COMFY_IMAGE_AND_VIDEO_TRACE_COMPLETE_READY_FOR_REVIEW")

    def test_function_success_with_clean_cleanup_is_ready(self):
        proc = mock.Mock()
        proc.wait.return_value = 0
        proc.poll.return_value = 0
        receipt, cleanup = self.run_owned_popen_fixture(
            ollama_proc=proc, ollama_wrapper_pid=123, ollama_stop_after=[],
            functional_success=True, expected_rc=0,
        )
        statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
        self.assertTrue(cleanup["proven"])
        self.assertEqual(statuses["cleanup_and_target_integrity"], "PASS")
        self.assertEqual(receipt["decision"], "READY_FOR_REVIEW")
        self.assertEqual(receipt["production_path_status"],
                         "PUBLIC_COMFY_IMAGE_AND_VIDEO_TRACE_COMPLETE_READY_FOR_REVIEW")

    def test_owned_popen_wait_exception_is_secondary_cleanup_failure(self):
        proc = mock.Mock()
        proc.wait.side_effect = [OSError("fixture wait error"), 0]
        proc.poll.side_effect = [None, 0, 0]
        receipt, cleanup = self.run_owned_popen_fixture(ollama_proc=proc)
        statuses = {x["check"]: x["status"] for x in receipt["check_results"]}
        self.assertTrue(receipt["cleanup"]["owned_resources_absent"])
        self.assertFalse(receipt["cleanup"]["proven"])
        self.assertEqual(statuses["cleanup_and_target_integrity"], "FAIL")
        self.assertIn("OWNED_POPEN_WAIT_FAILED:owned_ollama_popen", cleanup["secondary_cleanup_failures"])
        proc.terminate.assert_called_once_with()

    def test_two_owned_popens_require_both_to_exit(self):
        comfy = mock.Mock()
        comfy.wait.return_value = 0
        comfy.poll.return_value = 0
        ollama = mock.Mock()
        ollama.wait.side_effect = probe.subprocess.TimeoutExpired(cmd="owned", timeout=5)
        ollama.poll.return_value = None
        receipt, cleanup = self.run_owned_popen_fixture(ollama_proc=ollama, comfy_proc=comfy)
        states = {item["label"]: item for item in cleanup["owned_popen_terminal_states"]}
        self.assertEqual(receipt["external_actions"]["ollama_process_starts"], 1)
        self.assertEqual(receipt["external_actions"]["comfyui_process_starts"], 1)
        self.assertTrue(states["owned_comfy_popen"]["exited"])
        self.assertFalse(states["owned_ollama_popen"]["exited"])
        self.assertFalse(receipt["cleanup"]["owned_resources_absent"])
        self.assertFalse(receipt["cleanup"]["proven"])


class CleanupCorrelationTests(unittest.TestCase):
    def test_cleanup_proof_authority_invariant(self):
        cases = [
            (True, "PASS", [], True),
            (False, "PASS", [], False),
            (True, "FAIL", [], False),
            (True, "NOT_REACHED", [], False),
            (True, "PASS", ["SECONDARY"], False),
        ]
        for absent, integrity, secondary, expected in cases:
            with self.subTest(absent=absent, integrity=integrity, secondary=secondary):
                proven = probe.derive_cleanup_proven(
                    owned_resources_absent=absent,
                    target_integrity_comparison=integrity,
                    secondary_cleanup_failures=secondary,
                )
                self.assertEqual(proven, expected)
                if proven:
                    self.assertTrue(absent)
                    self.assertEqual(integrity, "PASS")
                    self.assertEqual(secondary, [])

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
        owner.reached_checks = set()
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


class VideoOracleTests(unittest.TestCase):
    def video_values(self, motion):
        envelope = {"done": True, "done_reason": "stop", "message": {"content": probe.json.dumps({
            "observations": ["A visible subject."], "inferences": [], "unknowns": [],
            "prompt": "A concrete visible subject."})}}
        raw = probe.json.dumps({"frame_raw_responses": [probe.json.dumps(envelope)] * 4})
        suggestion = probe.json.dumps({"technical": {"camera_motion": motion},
                                       "domains": {"observation": ["Four ordered frames."]}})
        return raw, suggestion

    def test_nonempty_string_camera_motion_passes(self):
        owner = object.__new__(probe.Probe)
        result = owner.oracle("video", *self.video_values("No visible change can be established."))
        self.assertTrue(result["pass"])
        self.assertEqual(result["envelope_count"], 4)

    def test_list_camera_motion_is_rejected(self):
        owner = object.__new__(probe.Probe)
        with self.assertRaisesRegex(ValueError, "video suggestion has no camera_motion"):
            owner.oracle("video", *self.video_values(["pan left"]))

    def test_empty_string_camera_motion_is_rejected(self):
        owner = object.__new__(probe.Probe)
        with self.assertRaisesRegex(ValueError, "video suggestion has no camera_motion"):
            owner.oracle("video", *self.video_values("  "))


if __name__ == "__main__":
    unittest.main()
