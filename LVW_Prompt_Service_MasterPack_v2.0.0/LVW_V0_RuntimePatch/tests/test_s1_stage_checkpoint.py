import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


PACK_ROOT = Path(__file__).resolve().parents[2]
HARNESS = PACK_ROOT / "reports/v0-s1/stage-checkpoint-phase-a/checkpoint.py"
SPEC = importlib.util.spec_from_file_location("s1_stage_checkpoint", HARNESS)
checkpoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checkpoint)


class StageCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifacts = checkpoint.bind_candidate(PACK_ROOT)

    def test_fixed_denominator_hash_and_product_statuses(self):
        result = checkpoint.run_offline_prechecks(PACK_ROOT)
        self.assertEqual(checkpoint.ACCEPTANCE_HASH, result["acceptance_hash"])
        self.assertEqual(list(checkpoint.CASE_IDS), [item["case_id"] for item in result["case_prechecks"]])
        self.assertEqual({"denominator": 5, "pass": 0, "fail": 0, "blocked": 0,
                          "skipped": 0, "not_run": 5}, result["product_test_counts"])
        self.assertTrue(all(item["product_status"] == "NOT_RUN" for item in result["case_prechecks"]))
        self.assertFalse(result["stage_pass_claim"])

    def test_self_check_uses_public_owners_and_zero_external_actions(self):
        result = checkpoint.run_offline_prechecks(PACK_ROOT)
        self.assertEqual({"service_starts": 0, "gpu_probes": 0, "port_probes": 0,
                          "network_calls": 0, "real_media_reads": 0, "browser_runs": 0},
                         result["external_actions"])
        by_id = {item["case_id"]: item for item in result["case_prechecks"]}
        self.assertEqual(["LVWControlledImageInput", "LVWImagePromptBridge"], by_id["V0-A01"]["public_graph"])
        self.assertEqual(0, by_id["V0-A03"]["view_switch_extra_model_calls"])
        self.assertEqual(20_000, by_id["V0-A04"]["draft_characters"])
        self.assertTrue(by_id["V0-A04"]["write_failure_preserved"])
        self.assertEqual(1, by_id["V0-A05"]["draft_epoch"])
        self.assertEqual([], by_id["V0-A08"]["permission_fields"])

    def test_default_cli_has_no_live_branch(self):
        with self.assertRaises(SystemExit):
            checkpoint.parse_args([])
        with self.assertRaises(SystemExit):
            checkpoint.parse_args(["--execute-live"])

    def test_exact_future_budgets_are_bounded_and_cloud_browser_download_zero(self):
        self.assertEqual(set(checkpoint.CASE_IDS), set(checkpoint.CASE_BUDGETS))
        self.assertEqual(1, checkpoint.CASE_BUDGETS["V0-A01"]["model_calls"])
        for budget in checkpoint.CASE_BUDGETS.values():
            self.assertEqual(0, budget["cloud_calls"])
            self.assertEqual(0, budget["downloads"])
            self.assertEqual(0, budget["browser_runs"])

    def test_candidate_binding_rejects_drift_and_extra_python(self):
        artifact = PACK_ROOT / checkpoint.PRODUCTION_ARTIFACTS[0]
        original = artifact.read_bytes()
        with mock.patch.object(Path, "read_bytes", autospec=True,
                               side_effect=lambda path: b"drift" if path == artifact else original):
            with self.assertRaises(checkpoint.CheckpointError):
                checkpoint.bind_candidate(PACK_ROOT)
        bridge = PACK_ROOT / "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge"
        extra = bridge / "checkpoint_extra.py"
        extra.write_text("raise RuntimeError\n", encoding="utf-8")
        try:
            with self.assertRaises(checkpoint.CheckpointError) as raised:
                checkpoint.bind_candidate(PACK_ROOT)
            self.assertEqual("CANDIDATE_PYTHON_INVENTORY_MISMATCH", raised.exception.code)
        finally:
            extra.unlink()

    def case_document(self, case_id, slot=None):
        return {"case_id": case_id, "product_candidate": checkpoint.PRODUCT_CANDIDATE,
                "acceptance_hash": checkpoint.ACCEPTANCE_HASH,
                "budget": checkpoint.CASE_BUDGETS[case_id], "status": "PASS",
                "evidence_slot": slot or f"fresh/{case_id}",
                "identity": {"artifacts": self.artifacts},
                "proof": dict(checkpoint.LIVE_REQUIREMENTS),
                "oracle": {key: True for key in checkpoint.CASE_PROOF_REQUIREMENTS[case_id]}}

    def test_combiner_requires_all_five_same_candidate_fresh_slots_and_proofs(self):
        documents = [self.case_document(case_id) for case_id in checkpoint.CASE_IDS]
        combined = checkpoint.combine_case_evidence(documents, PACK_ROOT)
        self.assertEqual(5, combined["test_counts"]["pass"])
        self.assertFalse(combined["stage_pass_claim"])
        for mutation in ("candidate", "proof", "slot"):
            broken = [self.case_document(case_id) for case_id in checkpoint.CASE_IDS]
            if mutation == "candidate":
                broken[0]["product_candidate"] = "0" * 40
            elif mutation == "proof":
                broken[0]["proof"]["loopback_only"] = False
            else:
                broken[1]["evidence_slot"] = broken[0]["evidence_slot"]
            with self.subTest(mutation=mutation), self.assertRaises(checkpoint.CheckpointError):
                checkpoint.combine_case_evidence(broken, PACK_ROOT)

        broken = [self.case_document(case_id) for case_id in checkpoint.CASE_IDS]
        broken[0]["oracle"][next(iter(broken[0]["oracle"]))] = False
        with self.assertRaises(checkpoint.CheckpointError) as raised:
            checkpoint.combine_case_evidence(broken, PACK_ROOT)
        self.assertEqual("CASE_ORACLE_MISSING", raised.exception.code)

    def test_partial_or_not_run_evidence_cannot_promote_fixed_denominator(self):
        documents = [self.case_document(case_id) for case_id in checkpoint.CASE_IDS[:-1]]
        with self.assertRaises(checkpoint.CheckpointError) as raised:
            checkpoint.combine_case_evidence(documents, PACK_ROOT)
        self.assertEqual("FIXED_DENOMINATOR_INCOMPLETE", raised.exception.code)
        documents.append(self.case_document("V0-A08"))
        documents[-1]["status"] = "NOT_RUN"
        with self.assertRaises(checkpoint.CheckpointError) as raised:
            checkpoint.combine_case_evidence(documents, PACK_ROOT)
        self.assertEqual("CASE_NOT_PASS", raised.exception.code)

    def test_combiner_rejects_private_path_or_input_dump(self):
        for unsafe in ("/mnt/c/private/image.jpg", r"C:\\Users\\name\\image.jpg",
                       "Traceback (most recent call last):", "current_inputs=tensor(...)"):
            documents = [self.case_document(case_id) for case_id in checkpoint.CASE_IDS]
            documents[0]["unsafe"] = unsafe
            with self.subTest(unsafe=unsafe), self.assertRaises(checkpoint.CheckpointError) as raised:
                checkpoint.combine_case_evidence(documents, PACK_ROOT)
            self.assertEqual("CASE_PRIVACY_VIOLATION", raised.exception.code)

    def test_a05_negatives_cover_required_failures_and_retry_boundary(self):
        result = checkpoint.precheck_a05(PACK_ROOT)
        self.assertEqual({"invalid_json", "explicit_refusal", "timeout", "oom", "stale_token"},
                         {item["name"] for item in result["negatives"]})
        self.assertTrue(all(item["draft_preserved"] for item in result["negatives"]))
        self.assertEqual(2, result["retry_exact"])
        self.assertEqual(3, result["retry_one_over_rejected"])

    def test_a08_empty_manual_contract_has_no_permission_gate(self):
        result = checkpoint.precheck_a08(PACK_ROOT)
        self.assertEqual(["manual", None, "not_requested", None], result["contract_tuple"])
        self.assertEqual(0, result["model_calls"])


if __name__ == "__main__":
    unittest.main()
