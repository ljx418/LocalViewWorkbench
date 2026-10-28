import argparse
import contextlib
import importlib.util
from io import StringIO
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import NODE_CLASS_MAPPINGS
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import prompt_spec
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.state import transition


PACK_ROOT = Path(__file__).resolve().parents[2]
HARNESS_PATH = PACK_ROOT / "reports" / "v0-s1" / "wp-s1-03-phase-a" / "live_probe.py"
SPEC = importlib.util.spec_from_file_location("s1_wp03_live_probe", HARNESS_PATH)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class FakeDriver:
    instances = []
    fail_image = False
    cleanup_proven = True

    def __init__(self, args, evidence):
        self.args = args
        self.submissions = 0
        self.graphs = {}
        self.unloads = 0
        self.ollama_stopped = False
        self.__class__.instances.append(self)

    def target_hashes(self):
        return {"main": "same", "python": "same"}

    def preflight(self):
        return {"gpu_count": 1, "max_used_mib": 1024, "process_match_count": 0, "target_listener_count": 0}

    def start_ollama(self, path):
        path.write_text("OLLAMA_NO_CLOUD=true\n", encoding="utf-8")

    def no_cloud_remote_gate(self):
        return {"ollama_no_cloud": True, "duration_seconds_min": 10,
                "samples": [{"nonloopback_count": 0}] * 5}

    def start_comfy(self, base, path):
        path.write_text("registered LVW nodes\n", encoding="utf-8")

    def registry(self):
        return {name: {} for name in probe.REQUIRED_NODES}

    def ownership_summary(self):
        return {"11434": {"lineage_proven": True}, "8191": {"lineage_proven": True}}

    def verify_model(self):
        return {"model": probe.MODEL, "local_exact_match_count": 1, "digest": "fixture"}

    def submit(self, graph):
        self.submissions += 1
        prompt_id = f"prompt-{self.submissions}"
        self.graphs[prompt_id] = graph
        return prompt_id

    def history(self, prompt_id):
        graph = self.graphs[prompt_id]
        node = graph["1"]["class_type"]
        if node == "LVWControlledImageInput":
            if self.fail_image:
                return {prompt_id: {"status": {"status_str": "error", "messages": ["fixture"]}, "outputs": {}}}
            raw = json.dumps({"done": True, "message": {"content": "fixture"}})
            suggestion = json.dumps(prompt_spec(mode="realistic", observations=["visible subject"], inferences=[],
                                                unknowns=[], creative_prompt="visible subject in soft light", tags=[]))
            outputs = {"2": {"text": [raw, suggestion]}}
        elif node == "LVWDraftStateOwner":
            inputs = graph["1"]["inputs"]
            value = transition(inputs["state"], action=inputs["action"], run_token=inputs["run_token"],
                               raw_response=inputs["raw_response"], suggestion_payload=inputs["suggestion_payload"],
                               draft_payload=inputs["draft_payload"],
                               error_code=inputs["error_code"])
            outputs = {"1": {"text": [json.dumps(value, ensure_ascii=False)]}}
        else:
            outputs = {"1": {"text": ["preview_json", '{"analysis_status":"not_requested"}']}}
        return {prompt_id: {"status": {"status_str": "success", "messages": []}, "outputs": outputs}}

    def runtime_guard(self):
        return {"max_gpu_used_mib": 2048, "nonloopback_count": 0}

    def unload(self):
        self.unloads += 1
        return {"cleanup_http_status": 200, "terminal_api_ps_model_count": 0}

    def stop_ollama(self):
        self.ollama_stopped = True

    def cleanup(self):
        return {"proven": self.cleanup_proven, "failures": [], "final_target_listener_count": 0}


def live_args(repo, sample, temp_parent):
    return argparse.Namespace(
        authorization_id=probe.AUTHORIZATION_ID, candidate_sha="1" * 40,
        harness_relative="reports/v0-s1/wp-s1-03-phase-a/live_probe.py", harness_sha256="2" * 64,
        repo=str(repo), sample=str(sample), sample_sha256=probe.AUTHORIZED_SAMPLE_SHA256,
        comfy_main="COMFY_ROOT/main.py", comfy_python="COMFY_PYTHON", ollama_exe="OLLAMA_EXE",
        powershell="powershell.exe", temp_parent=str(temp_parent), evidence_root="unused", run_id="offline-fixture",
    )


class WorkflowAndHarnessTests(unittest.TestCase):
    def setUp(self):
        FakeDriver.instances.clear()
        FakeDriver.fail_image = False
        FakeDriver.cleanup_proven = True

    def test_ui_and_api_workflows_are_same_registered_project_graph(self):
        ui = json.loads((PACK_ROOT / "LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.ui.json").read_text())
        api = json.loads((PACK_ROOT / "LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json").read_text())
        ui_classes = {node["type"] for node in ui["nodes"]}
        api_classes = {node["class_type"] for node in api.values()}
        self.assertEqual(ui_classes, api_classes)
        self.assertEqual({"LVWControlledImageInput", "LVWImagePromptBridge"}, ui_classes)
        self.assertTrue(ui_classes <= set(NODE_CLASS_MAPPINGS))
        self.assertEqual(["1", 0], api["2"]["inputs"]["image"])
        self.assertEqual([[1, 1, 0, 2, 0, "IMAGE"]], ui["links"])

    def test_semantic_oracle_requires_real_frozen_prompt_spec_shape(self):
        raw = json.dumps({"done": True})
        fake = json.dumps({"observations": ["visible"], "prompt": "fake top-level shape"})
        with self.assertRaises(probe.StopProbe) as raised:
            probe.validate_image_result([raw, fake])
        self.assertEqual("PUBLIC_IMAGE_SEMANTIC_ORACLE_FAILED", raised.exception.reason)

    def test_self_check_is_offline_and_default_entry_refuses_live(self):
        with mock.patch.object(probe.subprocess, "run", side_effect=AssertionError("external command")), \
                mock.patch.object(probe.urllib.request, "urlopen", side_effect=AssertionError("network")):
            value = probe.self_check()
            self.assertEqual(0, value["live_actions"])
            self.assertEqual("C:/ComfyUI-aki-v2/ComfyUI/main.py", value["authorized_targets"]["comfy_main"])
            self.assertEqual("reports/v0-s1/wp-s1-03-live-02", value["authorized_evidence_relative"])
            self.assertEqual("v0-s1-wp-s1-03-live-02", value["authorized_run_id"])
            output = StringIO()
            with contextlib.redirect_stdout(output):
                code = probe.main([])
        self.assertEqual(2, code)
        self.assertEqual("LIVE_FLAG_REQUIRED", json.loads(output.getvalue())["exact_stop_reason"])

    def test_expired_authorization_id_is_rejected_before_driver_creation(self):
        args = live_args(PACK_ROOT, "unused-sample", "/mnt/c/unused-temp")
        args.authorization_id = "AUTH-V0-S1-2026-10-28-01"
        with mock.patch.object(probe, "validate_live_boundaries", return_value={}):
            code, result = probe.execute(args, driver_factory=lambda *_: self.fail("driver must not be created"))
        self.assertEqual(2, code)
        self.assertEqual("AUTHORIZATION_ID_MISMATCH", result["exact_stop_reason"])
        self.assertEqual({"ollama": 0, "comfy": 0}, result["service_starts"])

    def test_authorized_paths_evidence_reservation_and_existing_refusal(self):
        if os.name == "nt":
            self.skipTest("live harness is launched from WSL; Windows-native interpreter has no /mnt/c namespace")
        with tempfile.TemporaryDirectory(dir="/mnt/c") as temp:
            root = Path(temp)
            repo = root / "repo"
            (repo / "reports/v0-s1").mkdir(parents=True)
            runtime = root / "runtime"
            runtime.mkdir()
            args = live_args(repo, root / "sample.png", runtime)
            args.comfy_main = "/mnt/c/ComfyUI-aki-v2/ComfyUI/main.py"
            args.comfy_python = "/mnt/c/ComfyUI-aki-v2/python/python.exe"
            args.run_id = "v0-s1-wp-s1-03-live-02"
            args.evidence_root = str(repo / "reports/v0-s1/wp-s1-03-live-01")
            with self.assertRaises(probe.StopProbe) as old_slot:
                probe.validate_live_boundaries(args, reserve_evidence=True)
            self.assertEqual("EVIDENCE_ROOT_OUTSIDE_AUTHORIZED_BOUNDARY", old_slot.exception.reason)
            args.evidence_root = str(repo / "reports/v0-s1/wp-s1-03-live-02")
            value = probe.validate_live_boundaries(args, reserve_evidence=True)
            self.assertEqual(probe.AUTHORIZED_COMFY_MAIN, value["comfy_main"])
            with self.assertRaises(probe.StopProbe) as raised:
                probe.validate_live_boundaries(args, reserve_evidence=True)
            self.assertEqual("EVIDENCE_ROOT_ALREADY_EXISTS", raised.exception.reason)
            for forbidden in ("/mnt/c/ComfyUI/ComfyUI/main.py",
                              "/mnt/c/ComfyUI-aki-v2/python/Lib/lib2to3/main.py"):
                with self.subTest(forbidden=forbidden):
                    args.comfy_main = forbidden
                    with self.assertRaises(probe.StopProbe) as mismatch:
                        probe.validate_live_boundaries(args, reserve_evidence=False)
                    self.assertEqual("AUTHORIZED_COMFY_MAIN_MISMATCH", mismatch.exception.reason)
            args.comfy_main = "/mnt/c/ComfyUI-aki-v2/ComfyUI/main.py"
            args.comfy_python = "/mnt/c/ComfyUI/python/python.exe"
            with self.assertRaises(probe.StopProbe) as old_python:
                probe.validate_live_boundaries(args, reserve_evidence=False)
            self.assertEqual("AUTHORIZED_COMFY_PYTHON_MISMATCH", old_python.exception.reason)
            args.comfy_python = "/mnt/c/ComfyUI-aki-v2/python/python.exe"
            args.run_id = "v0-s1-wp-s1-03-live-01"
            with self.assertRaises(probe.StopProbe) as old_run:
                probe.validate_live_boundaries(args, reserve_evidence=False)
            self.assertEqual("AUTHORIZED_RUN_ID_MISMATCH", old_run.exception.reason)

    def test_wrapper_commands_are_quoted_locked_down_and_pid_bound(self):
        ollama = probe.ollama_wrapper_text("C:\\Program Files\\Ollama\\ollama.exe", "C:\\Temp\\ollama.pid")
        comfy = probe.comfy_wrapper_text(probe.AUTHORIZED_COMFY_PYTHON, probe.AUTHORIZED_COMFY_MAIN,
                                         "C:\\Temp\\run", "C:\\Temp\\comfy.pid")
        self.assertIn("OLLAMA_NO_CLOUD='1'", ollama)
        self.assertNotIn("$args", ollama)
        for flag in ("--disable-auto-launch", "--disable-api-nodes", "--disable-all-custom-nodes",
                     "--whitelist-custom-nodes lvw_v0_bridge"):
            self.assertIn(flag, comfy)
        self.assertIn("$PID | Set-Content", ollama)
        self.assertIn("$PID | Set-Content", comfy)

    def test_listener_pid_without_wrapper_lineage_is_rejected(self):
        args = mock.Mock()
        driver = probe.SystemDriver(args, {})
        with tempfile.TemporaryDirectory() as temp:
            pid_file = Path(temp, "wrapper.pid")
            pid_file.write_text("100", encoding="ascii")
            row = json.dumps({"ProcessId": 200, "ParentProcessId": 50, "ExecutablePath": "C:/Ollama/ollama.exe"})
            with mock.patch.object(driver, "_listener_pid", return_value=200), \
                    mock.patch.object(driver, "_powershell", return_value=row), \
                    self.assertRaises(probe.StopProbe) as raised:
                driver._prove_listener_owned(11434, pid_file, "ollama.exe")
        self.assertEqual("LISTENER_OWNERSHIP_NOT_PROVEN", raised.exception.reason)
        self.assertEqual(set(), driver.listener_pids)

    def test_cleanup_revalidates_lineage_and_never_stops_takeover_pid(self):
        driver = probe.SystemDriver(mock.Mock(), {})
        commands = []
        with tempfile.TemporaryDirectory() as temp:
            pid_file = Path(temp, "wrapper.pid")
            pid_file.write_text("100", encoding="ascii")
            driver.listener_proofs[8191] = {"wrapper_pid_file": pid_file, "executable_name": "python.exe"}
            wrong = json.dumps({"ProcessId": 200, "ParentProcessId": 50,
                                "ExecutablePath": "C:/Windows/System32/not-owned.exe"})

            def powershell(command):
                commands.append(command)
                if "Get-CimInstance" in command:
                    return wrong
                return "1"

            with mock.patch.object(driver, "_listener_pid_values", return_value=[200]), \
                    mock.patch.object(driver, "_listener_pid", return_value=200), \
                    mock.patch.object(driver, "_powershell", side_effect=powershell):
                result = driver.cleanup()
        self.assertFalse(result["proven"])
        self.assertEqual(1, result["final_target_listener_count"])
        self.assertFalse(any("Stop-Process" in command for command in commands))

    def test_cleanup_treats_already_exited_wrapper_as_clean(self):
        driver = probe.SystemDriver(mock.Mock(), {})
        process = mock.Mock()
        process.poll.return_value = 0
        stream = mock.Mock()
        driver.owned.append(("ollama_wrapper", process, stream))
        with mock.patch.object(driver, "_powershell", return_value="0"):
            result = driver.cleanup()
        self.assertTrue(result["proven"])
        process.terminate.assert_not_called()
        process.wait.assert_not_called()
        stream.close.assert_called_once()

    def test_missing_exact_local_model_fails_without_download(self):
        driver = probe.SystemDriver(mock.Mock(), {})
        with mock.patch.object(driver, "_json_request", return_value=(200, {"models": [{"name": "other:tag"}]})), \
                self.assertRaises(probe.StopProbe) as raised:
            driver.verify_model()
        self.assertEqual("AUTHORIZED_MODEL_NOT_LOCALLY_PRESENT", raised.exception.reason)

    def test_target_integrity_covers_frozen_critical_set_without_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "comfy").mkdir()
            for relative in ("main.py", "folder_paths.py", "nodes.py", "comfy/cli_args.py"):
                (root / relative).write_text(relative, encoding="utf-8")
            driver = probe.SystemDriver(mock.Mock(comfy_main=str(root / "main.py")), {})
            value = driver.target_hashes()
        self.assertEqual({"main.py", "folder_paths.py", "nodes.py", "comfy/cli_args.py",
                          "extra_model_paths.yaml", "prompt_assistant_state"}, set(value))
        self.assertFalse(any(str(root) in str(item) for item in value.values()))

    def test_candidate_identity_rejects_outside_allowlist(self):
        completed = lambda code, stdout=b"": subprocess_result(code, stdout)
        outside = (PACK_ROOT.parent.name + "/contracts/errors.json\n").encode()
        with mock.patch.object(probe, "run_local", side_effect=[completed(0, str(PACK_ROOT.parent).encode()),
                                                                 completed(0), completed(0), completed(0, outside)]):
            with self.assertRaises(probe.StopProbe) as raised:
                probe.candidate_identity(PACK_ROOT, "1" * 40, "reports/v0-s1/wp-s1-03-phase-a/live_probe.py", "2" * 64)
        self.assertEqual("CANDIDATE_CHANGED_FILE_OUTSIDE_ALLOWLIST", raised.exception.reason)

    def test_candidate_identity_binds_committed_blob_to_executed_harness(self):
        completed = lambda code, stdout=b"": subprocess_result(code, stdout)
        relative = "reports/v0-s1/wp-s1-03-phase-a/live_probe.py"
        git_path = PACK_ROOT.name + "/" + relative
        blob = HARNESS_PATH.read_bytes()
        changed = (git_path + "\n").encode()
        blob_result = mock.Mock(returncode=0, stdout=blob)
        with mock.patch.object(probe, "run_local", side_effect=[
                completed(0, str(PACK_ROOT.parent).encode()), completed(0), completed(0), completed(0, changed)]), \
                mock.patch.object(probe.subprocess, "run", side_effect=[blob_result, blob_result]):
            value = probe.candidate_identity(PACK_ROOT, "1" * 40, relative, probe.sha256_bytes(blob))
        self.assertTrue(value["identity_match"])
        self.assertEqual(probe.sha256_bytes(blob), value["file_sha256"][relative])

    def test_success_route_enforces_one_attempt_state_adopt_manual_and_cleanup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sample = root / "sample.png"
            sample.write_bytes(b"synthetic")
            args = live_args(PACK_ROOT, sample, root)
            with mock.patch.object(probe, "candidate_identity", return_value={"identity_match": True}), \
                    mock.patch.object(probe, "sha256_file", return_value=probe.AUTHORIZED_SAMPLE_SHA256), \
                    mock.patch.object(probe, "validate_live_boundaries", return_value={}):
                code, result = probe.execute(args, driver_factory=FakeDriver)
        driver = FakeDriver.instances[0]
        self.assertEqual(0, code)
        self.assertEqual("READY_FOR_REVIEW", result["decision"])
        self.assertEqual({"image": 1, "model_calls": 1}, result["attempts"])
        self.assertEqual(5, result["public_submissions"])
        self.assertEqual(1, driver.unloads)
        self.assertTrue(driver.ollama_stopped)
        self.assertTrue(result["cleanup"]["proven"])
        self.assertEqual("EXPIRED_TERMINAL", result["authorization_status"])
        self.assertEqual(probe.PRODUCT_CASES, result["product_acceptance"])

    def test_image_failure_still_unloads_and_terminalizes(self):
        FakeDriver.fail_image = True
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sample = root / "sample.png"
            sample.write_bytes(b"synthetic")
            with mock.patch.object(probe, "candidate_identity", return_value={"identity_match": True}), \
                    mock.patch.object(probe, "sha256_file", return_value=probe.AUTHORIZED_SAMPLE_SHA256), \
                    mock.patch.object(probe, "validate_live_boundaries", return_value={}):
                code, result = probe.execute(live_args(PACK_ROOT, sample, root), driver_factory=FakeDriver)
        self.assertEqual(2, code)
        self.assertEqual("PUBLIC_COMFY_ROUTE_FAILED", result["exact_stop_reason"])
        self.assertEqual(1, FakeDriver.instances[0].unloads)
        self.assertEqual("EXPIRED_TERMINAL", result["authorization_status"])

    def test_cleanup_gap_downgrades_success(self):
        FakeDriver.cleanup_proven = False
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sample = root / "sample.png"
            sample.write_bytes(b"synthetic")
            with mock.patch.object(probe, "candidate_identity", return_value={"identity_match": True}), \
                    mock.patch.object(probe, "sha256_file", return_value=probe.AUTHORIZED_SAMPLE_SHA256), \
                    mock.patch.object(probe, "validate_live_boundaries", return_value={}):
                code, result = probe.execute(live_args(PACK_ROOT, sample, root), driver_factory=FakeDriver)
        self.assertEqual(2, code)
        self.assertEqual("NO_GO", result["decision"])
        self.assertEqual("CLEANUP_OR_TARGET_INTEGRITY_NOT_PROVEN", result["exact_stop_reason"])

    def test_redaction_removes_private_paths_and_secrets(self):
        value = probe.redact("/mnt/c/private/sample.png token=secret", {"/mnt/c/private/sample.png": "TEST_SOURCE/image-sample"})
        self.assertNotIn("/mnt/c/private", value)
        self.assertNotIn("secret", value)
        self.assertIn("TEST_SOURCE/image-sample", value)


def subprocess_result(code, stdout=b""):
    value = mock.Mock()
    value.returncode = code
    value.stdout = stdout.decode() if isinstance(stdout, bytes) else stdout
    return value


if __name__ == "__main__":
    unittest.main()
