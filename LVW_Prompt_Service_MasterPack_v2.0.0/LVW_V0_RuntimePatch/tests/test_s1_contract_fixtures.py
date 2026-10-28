import copy
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

import jsonschema


PACK_ROOT = Path(__file__).resolve().parents[2]
PATCH_ROOT = PACK_ROOT / "LVW_V0_RuntimePatch"
FIXTURE_PATH = PATCH_ROOT / "tests" / "fixtures" / "s1-contract-fixtures.json"
BINDING_PATH = PATCH_ROOT / "manifests" / "s1-baseline-bindings.json"


class S1ContractFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        cls.binding = json.loads(BINDING_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads((PACK_ROOT / "contracts" / "v0-result.schema.json").read_text(encoding="utf-8"))
        cls.validator = jsonschema.Draft202012Validator(cls.schema)

    def test_valid_manual_result_matches_frozen_schema(self):
        self.validator.validate(self.fixture["valid_manual_result"])

    def test_invalid_mutations_are_rejected(self):
        base = self.fixture["valid_manual_result"]
        for mutation in self.fixture["invalid_mutations"]:
            with self.subTest(mutation=mutation["name"]):
                candidate = copy.deepcopy(base)
                candidate[mutation["path"]] = mutation["value"]
                with self.assertRaises(jsonschema.ValidationError):
                    self.validator.validate(candidate)

    def test_20000_character_fixture_is_exact(self):
        boundary = self.fixture["draft_boundary"]
        value = boundary["character"] * boundary["repeat"]
        payload = value.encode("utf-8")
        self.assertEqual(20000, len(value))
        self.assertEqual(boundary["utf8_bytes"], len(payload))
        self.assertEqual(boundary["sha256_utf8"], hashlib.sha256(payload).hexdigest())

    def test_invalid_json_fixture_is_not_parseable(self):
        with self.assertRaises(json.JSONDecodeError):
            json.loads(self.fixture["invalid_json_text"])

    def test_image_exact_and_one_over_boundaries_bind_runtime_defaults(self):
        runtime = json.loads((PACK_ROOT / "config" / "runtime.defaults.json").read_text(encoding="utf-8"))
        boundary = self.fixture["image_boundaries"]
        self.assertEqual(runtime["media"]["max_image_bytes"], boundary["max_bytes"])
        self.assertEqual(boundary["max_bytes"] + 1, boundary["one_over_bytes"])
        self.assertEqual(runtime["media"]["max_image_pixels"], boundary["max_pixels"])
        self.assertEqual(boundary["max_pixels"] + 1, boundary["one_over_pixels"])

    def test_late_callbacks_never_update_draft(self):
        cases = self.fixture["late_callback_cases"]
        self.assertEqual({"stale_run_token", "current_result_requires_explicit_adopt"}, {item["name"] for item in cases})
        for item in cases:
            self.assertEqual(item["draft_epoch_before"], item["draft_epoch_after"])
            self.assertEqual(item["draft_sha256_before"], item["draft_sha256_after"])
            self.assertFalse(item["draft_update_allowed"])

    def test_contract_and_binding_hashes_match(self):
        for relative, expected in self.binding["contract_sha256"].items():
            if relative.endswith("lvw_v0_bridge/__init__.py"):
                repository_path = f"{PACK_ROOT.name}/{relative}"
                baseline = subprocess.run(
                    ["git", "show", f"{self.binding['product_bridge_candidate']}:{repository_path}"],
                    cwd=PACK_ROOT.parent, check=True, stdout=subprocess.PIPE,
                ).stdout
                actual = hashlib.sha256(baseline).hexdigest()
            else:
                actual = hashlib.sha256((PACK_ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(expected, actual, relative)
        init_text = (PATCH_ROOT / "custom_nodes" / "lvw_v0_bridge" / "__init__.py").read_text(encoding="utf-8")
        for node in self.binding["public_node_bindings"]:
            self.assertIn(f'"{node}"', init_text)

    def test_acceptance_denominator_is_frozen(self):
        expected = ["V0-A01", "V0-A03", "V0-A04", "V0-A05", "V0-A08"]
        payload = ("\n".join(sorted(expected)) + "\n").encode("utf-8")
        self.assertEqual(expected, self.binding["fixed_acceptance_ids"])
        self.assertEqual(self.binding["acceptance_hash"], hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    unittest.main()
