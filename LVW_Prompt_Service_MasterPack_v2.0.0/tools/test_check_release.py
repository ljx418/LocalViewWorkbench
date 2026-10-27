import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "check_release.py"
REQUIRED = json.loads((ROOT / "plans" / "release_gates.json").read_text())["gates"]["V0"]["required_cases"]


class ReleaseGateTests(unittest.TestCase):
    def fixture(self, root):
        evidence = root / "evidence.json"
        review = root / "review.md"
        evidence.write_text("{}\n", encoding="utf-8")
        review.write_text("independent PASS\n", encoding="utf-8")
        commit = "a" * 40
        run_id = "v0-release-fixture"
        ref = {"path": evidence.name, "sha256": hashlib.sha256(evidence.read_bytes()).hexdigest()}
        report = {
            "run_id": run_id,
            "application_commit": commit,
            "implementation_owner": "isolated-implementer",
            "target_environment": "fixture",
            "acceptance_hash": hashlib.sha256(("\n".join(sorted(REQUIRED)) + "\n").encode()).hexdigest(),
            "cases": [{"case_id": cid, "status": "PASS", "candidate_sha": commit, "run_id": run_id,
                       "observed": {"fixture": True}, "evidence": [ref]} for cid in REQUIRED],
            "independent_review": {"decision": "PASS", "reviewer": "isolated-reviewer",
                                   "candidate_sha": commit, "path": review.name,
                                   "sha256": hashlib.sha256(review.read_bytes()).hexdigest()},
            "human_signoff": {"decision": "APPROVED", "signer": "project-owner", "signed_at": "2026-10-27T00:00:00+08:00",
                              "scope": "V0_RELEASE", "candidate_sha": commit},
            "metrics": {"gpu_peak_gib": 22, "system_available_ram_gib_min": 3,
                        "release_after_stop_seconds": 20, "critical_hallucinations": 0,
                        "image_warm_seconds": [100] * 10, "video4_warm_seconds": [200] * 10,
                        "image_cold_seconds": 200, "video4_cold_seconds": 300,
                        "image_samples": 10, "image_usable": 8, "video_samples": 6, "video_usable": 5,
                        "outbound_attempts": 0, "oom_count": 0}
        }
        return report

    def run_gate(self, report, root):
        path = root / "report.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return subprocess.run([sys.executable, str(CHECKER), str(path), "--target", "V0", "--evidence-root", str(root)],
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)

    def test_complete_bound_report_passes_structure_gate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); result = self.run_gate(self.fixture(root), root)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_missing_human_signoff_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); report = self.fixture(root); report.pop("human_signoff")
            result = self.run_gate(report, root)
            self.assertNotEqual(result.returncode, 0); self.assertIn("human signoff", result.stdout)

    def test_old_candidate_case_and_review_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); report = self.fixture(root)
            report["cases"][0]["candidate_sha"] = "b" * 40
            report["independent_review"]["candidate_sha"] = "b" * 40
            result = self.run_gate(report, root)
            self.assertNotEqual(result.returncode, 0); self.assertIn("candidate mismatch", result.stdout)

    def test_tampered_independent_review_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td); report = self.fixture(root); (root / "review.md").write_text("changed\n")
            result = self.run_gate(report, root)
            self.assertNotEqual(result.returncode, 0); self.assertIn("hash mismatch", result.stdout)


if __name__ == "__main__":
    unittest.main()
