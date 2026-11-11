"""Bounded synthetic tests for the corrected independent hash recheck helper.

Every fixture in this module is synthetic: the source files are a few dozen
bytes written by the test itself, the "repository" is a throw-away git
repository created inside the pytest basetemp, and the expected digests are
produced by an oracle that is independent of the helper implementation
(``hashlib`` over the whole file plus the external ``sha256sum`` binary).

The tests never reference the production media root except as a *string*
that the guard has to refuse; the guard's own check is lexical, so the
production tree is never stat'ed, opened or hashed by this suite.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import hash_child_recheck_correction as helper

HELPER_PATH = Path(helper.__file__).resolve()
PACKAGE = "LVW_Prompt_Service_MasterPack_v2.0.0"
CHILD_REL = "reports/v0-s3/preparation-03/fixture/fixture-child.json"
CODE_FILES = ("tools/alpha.py", "tools/beta.py")


# --------------------------------------------------------------------------
# oracle
# --------------------------------------------------------------------------


def oracle_sha256(path: Path) -> str:
    """Independent sha256 oracle: whole-file hashlib plus the sha256sum binary.

    The helper hashes in chunks through its own reader; this oracle reads the
    file in one go and cross-checks it against the external ``sha256sum``
    binary, so a bug in the helper's chunked reader cannot hide here.
    """
    with_hashlib = hashlib.sha256(path.read_bytes()).hexdigest()
    binary = shutil.which("sha256sum")
    if binary:
        out = subprocess.run([binary, str(path)], capture_output=True, text=True, check=True)
        with_binary = out.stdout.split()[0]
        assert with_binary == with_hashlib, "oracles disagree for %s" % path
    return with_hashlib


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo)] + list(args), capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


# --------------------------------------------------------------------------
# fixture construction
# --------------------------------------------------------------------------


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.repo = root / "repo"
        self.package = self.repo / PACKAGE
        self.source = root / "source"
        self.child_path = self.package / CHILD_REL
        self.source_files = []
        self.anchor_commit = ""
        self.child_sha256 = ""
        self.code_commit = ""
        self.source_commit = ""
        self.receipt_path = self.package / "reports/v0-s3/preparation-03/fixture/receipt.json"
        self.outside_file = root / "outside" / "secret.bin"

    # -- helpers ---------------------------------------------------------
    def write_child(self, **overrides) -> None:
        child = {
            "kind": "SYNTHETIC_FIXTURE_CHILD_FOR_PROCESS_CORRECTION",
            "id": "SYNTHETIC-FIXTURE-CHILD-01",
            "repo_root": str(self.repo),
            "repo_package_prefix": PACKAGE + "/",
            "child_rel_path": CHILD_REL,
            "source_candidate": self.source_commit,
            "implementation_code_candidate": self.code_commit,
            "code_files": list(CODE_FILES),
            "inventory_receipt": str(self.receipt_path),
            "inventory_receipt_sha256": oracle_sha256(self.receipt_path),
            "source_root": str(self.source),
            "selected_files": [
                {
                    "relative_path": name,
                    "sha256": oracle_sha256(self.source / name),
                    "bytes": (self.source / name).stat().st_size,
                    "file_id": hashlib.sha256(name.encode("utf-8")).hexdigest(),
                }
                for name in self.source_files
            ],
            "limits": {"files": 3, "bytes": 1 << 20, "wall_seconds": 60, "chunk_bytes": 64},
        }
        child.update(overrides)
        self.child = child
        self.child_path.parent.mkdir(parents=True, exist_ok=True)
        self.child_path.write_text(json.dumps(child, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
        self.child_sha256 = hashlib.sha256(self.child_path.read_bytes()).hexdigest()

    def commit_all(self, message: str) -> str:
        git(self.repo, "add", "-A")
        git(self.repo, "-c", "user.name=fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "commit", "-q", "-m", message)
        return git(self.repo, "rev-parse", "HEAD")

    def run_helper(self, out_path: Path, **kwargs):
        """Run the helper in-process with a spy adapter."""
        SpyAdapter.last = None
        code, payload = helper.run(
            self.child_path,
            out_path,
            kwargs.pop("expected_child_sha256", self.child_sha256),
            kwargs.pop("expected_child_commit", self.anchor_commit),
            kwargs.pop("allowed_source_roots", [self.source]),
            repo_root=self.repo,
            adapter_factory=SpyAdapter,
        )
        spy = SpyAdapter.last if SpyAdapter.last is not None else EmptySpy()
        return code, payload, spy


class SpyAdapter(helper.LocalSourceAdapter):
    """Adapter that records every source-side filesystem touch."""

    last = None

    def __init__(self, root):
        super().__init__(root)
        SpyAdapter.last = self

    def touched(self) -> list:
        return [arg for _, arg in self.calls]


class EmptySpy:
    """Stand-in for the adapter of a run that never reached the source phase."""

    calls = []

    def call_count(self, op: str) -> int:
        return 0

    def touched(self) -> list:
        return []


@pytest.fixture()
def fixture(tmp_path: Path) -> Fixture:
    fix = Fixture(tmp_path)
    fix.package.mkdir(parents=True)
    fix.source.mkdir(parents=True)
    (fix.root / "outside").mkdir(parents=True)

    git(fix.repo, "init", "-q", "-b", "main")
    (fix.package / "README.md").write_text("synthetic fixture package\n", encoding="utf-8")
    fix.source_commit = fix.commit_all("synthetic: base commit")

    (fix.package / "tools").mkdir(parents=True, exist_ok=True)
    (fix.package / "tools" / "alpha.py").write_text("ALPHA = 'candidate-alpha'\n", encoding="utf-8")
    (fix.package / "tools" / "beta.py").write_text("BETA = 'candidate-beta'\n", encoding="utf-8")
    fix.receipt_path.parent.mkdir(parents=True, exist_ok=True)
    fix.receipt_path.write_text(
        json.dumps({"kind": "SYNTHETIC_INVENTORY_RECEIPT", "items": []}) + "\n", encoding="utf-8")
    fix.code_commit = fix.commit_all("synthetic: candidate code and receipt")

    for name in ("alpha.bin", "beta.bin", "gamma.bin"):
        (fix.source / name).write_bytes(bytes(range(256)) * 2 + name.encode("utf-8"))
    fix.source_files = ["alpha.bin", "beta.bin", "gamma.bin"]
    (fix.source / helper.FIXTURE_MARKER_NAME).write_text(
        helper.FIXTURE_MARKER_CONTENT, encoding="utf-8")
    fix.outside_file.write_bytes(b"outside-the-fixture-root-bytes")

    fix.write_child()
    fix.anchor_commit = fix.commit_all("synthetic: fixture child authority")
    # the child file bytes change when it is committed only in path terms; the
    # blob of the committed file must equal the worktree file
    return fix


# --------------------------------------------------------------------------
# positives
# --------------------------------------------------------------------------


def test_positive_run_verifies_small_files_against_independent_oracle(fixture: Fixture, tmp_path):
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code == 0
    assert payload["decision"] == helper.DECISION_VERIFIED
    assert payload["preflight_validated_before_source_access"] is True
    assert payload["source_phase_entered"] is True
    assert len(payload["results"]) == 3
    for record in payload["results"]:
        assert record["result"] == "VERIFIED"
        assert record["actual_sha256"] == oracle_sha256(fixture.source / record["relative_path"])
        assert record["sha256_matches_candidate"] is True
    assert payload["counters"]["bytes_read"] == sum(
        (fixture.source / name).stat().st_size for name in fixture.source_files)
    assert spy.call_count("open_read") == 3


def test_positive_cli_exit_code_is_zero_and_matches_external_oracle(fixture: Fixture, tmp_path):
    out = tmp_path / "cli.json"
    proc = subprocess.run(
        [sys.executable, str(HELPER_PATH),
         "--child", str(fixture.child_path),
         "--out", str(out),
         "--expected-child-sha256", fixture.child_sha256,
         "--expected-child-commit", fixture.anchor_commit,
         "--allow-source-root", str(fixture.source)],
        capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["decision"] == helper.DECISION_VERIFIED
    for record in payload["results"]:
        assert record["actual_sha256"] == oracle_sha256(fixture.source / record["relative_path"])


def test_code_binding_uses_the_package_prefix_in_every_git_path(fixture: Fixture, tmp_path):
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code == 0
    for relative, identity in payload["code_identity"].items():
        assert identity["git_path"].startswith(PACKAGE + "/")
        assert identity["byte_identical_to_candidate"] is True


# --------------------------------------------------------------------------
# preflight failures must fail closed with zero source access
# --------------------------------------------------------------------------


def assert_rejected_without_source_access(code, payload, spy):
    assert code != 0
    assert payload["decision"] != helper.DECISION_VERIFIED
    assert payload["decision"] in (
        helper.DECISION_REJECTED_PREFLIGHT,
        helper.DECISION_REJECTED_GUARD,
        helper.DECISION_REJECTED_SOURCE,
        helper.DECISION_REJECTED_INTERNAL,
    )
    assert payload["source_phase_entered"] is False
    assert payload["counters"]["adapter_resolve_calls"] == 0
    assert payload["counters"]["adapter_stat_calls"] == 0
    assert payload["counters"]["adapter_open_calls"] == 0
    assert spy.call_count("resolve") == 0
    assert spy.call_count("stat") == 0
    assert spy.call_count("open_read") == 0


def test_mismatched_child_sha256_is_rejected_with_zero_source_access(fixture: Fixture, tmp_path):
    code, payload, spy = fixture.run_helper(
        tmp_path / "out.json", expected_child_sha256="0" * 64)
    assert_rejected_without_source_access(code, payload, spy)
    assert "child_sha256_matches_out_of_band_anchor" in str(payload.get("preflight_rejection"))


def test_mismatched_child_git_blob_is_rejected_with_zero_source_access(fixture: Fixture, tmp_path):
    # the worktree child file drifts away from the anchored commit blob; the
    # out-of-band digest anchor is refreshed so that the *git blob* binding is
    # the check that has to catch the drift
    fixture.child_path.write_text(
        fixture.child_path.read_text(encoding="utf-8").replace("SYNTHETIC-FIXTURE-CHILD-01",
                                                                "SYNTHETIC-FIXTURE-CHILD-02"),
        encoding="utf-8")
    fixture.child_sha256 = hashlib.sha256(fixture.child_path.read_bytes()).hexdigest()
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert_rejected_without_source_access(code, payload, spy)
    assert "child_git_blob_matches_worktree" in str(payload.get("preflight_rejection"))


def test_code_binding_mismatch_is_rejected_with_zero_source_access(fixture: Fixture, tmp_path):
    (fixture.package / "tools" / "alpha.py").write_text("ALPHA = 'drifted'\n", encoding="utf-8")
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert_rejected_without_source_access(code, payload, spy)
    assert "code_files_byte_identical_to_candidate" in str(payload.get("preflight_rejection"))


def test_inventory_receipt_sha_mismatch_is_rejected_with_zero_source_access(fixture: Fixture,
                                                                            tmp_path):
    fixture.receipt_path.write_text(
        json.dumps({"kind": "SYNTHETIC_INVENTORY_RECEIPT", "items": ["tampered"]}) + "\n",
        encoding="utf-8")
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert_rejected_without_source_access(code, payload, spy)
    assert "inventory_receipt_sha256_matches" in str(payload.get("preflight_rejection"))


def test_nonzero_git_exit_is_rejected_with_zero_source_access(fixture: Fixture, tmp_path):
    # an anchor commit that does not exist in the repository
    code, payload, spy = fixture.run_helper(
        tmp_path / "out.json", expected_child_commit="1" * 40)
    assert_rejected_without_source_access(code, payload, spy)
    assert "exited" in str(payload.get("preflight_rejection"))


def test_missing_repository_is_rejected_with_zero_source_access(fixture: Fixture, tmp_path):
    shutil.rmtree(fixture.repo)
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert_rejected_without_source_access(code, payload, spy)


def test_wrong_git_prefix_is_rejected_with_zero_source_access(fixture: Fixture, tmp_path,
                                                              monkeypatch):
    # reproduce the historical trigger: the git path loses the package prefix
    monkeypatch.setattr(helper, "REPO_PACKAGE_PREFIX", "")
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert_rejected_without_source_access(code, payload, spy)


def test_git_layer_rejects_a_prefix_less_path(fixture: Fixture):
    # the git layer itself must fail closed on the exact historical input
    with pytest.raises(helper.PreflightRejected):
        helper.git_object_id(fixture.repo, ["rev-parse", "%s:tools/alpha.py" % fixture.code_commit],
                             "prefix-less code blob")
    # and it must reject a git invocation that does not return an object id
    with pytest.raises(helper.PreflightRejected):
        helper.git_object_id(fixture.repo, ["rev-parse", "not-a-commit-id"], "bogus id")


def test_hashes_alone_never_produce_a_verified_decision(fixture: Fixture, tmp_path):
    # the source files are still perfectly hashable; only the metadata drifts
    (fixture.package / "tools" / "beta.py").write_text("BETA = 'drifted'\n", encoding="utf-8")
    for record in fixture.child["selected_files"]:
        assert oracle_sha256(fixture.source / record["relative_path"]) == record["sha256"]
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code != 0
    assert payload["decision"] != helper.DECISION_VERIFIED
    assert payload["source_phase_entered"] is False
    assert spy.call_count("open_read") == 0


# --------------------------------------------------------------------------
# guard: the production root is hard disabled
# --------------------------------------------------------------------------


def test_production_real_root_is_hard_disabled(fixture: Fixture, tmp_path):
    fixture.write_child(source_root="/mnt/c/workSpace/videoWorkLine/testSource")
    fixture.anchor_commit = fixture.commit_all("synthetic: repoint the child at production")
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code == helper.EXIT_GUARD
    assert payload["decision"] == helper.DECISION_REJECTED_GUARD
    assert payload["source_phase_entered"] is False
    assert spy.call_count("resolve") == 0
    assert spy.call_count("stat") == 0
    assert spy.call_count("open_read") == 0
    assert all("testSource" not in touched for touched in spy.touched())


def test_production_root_child_is_refused_without_any_allow_list(fixture: Fixture, tmp_path):
    fixture.write_child(source_root="/mnt/c/workSpace/videoWorkLine/testSource")
    fixture.anchor_commit = fixture.commit_all("synthetic: repoint the child at production 2")
    code, payload, spy = fixture.run_helper(tmp_path / "out.json", allowed_source_roots=[])
    assert code == helper.EXIT_GUARD
    assert payload["decision"] == helper.DECISION_REJECTED_GUARD
    assert spy.call_count("open_read") == 0


def test_source_root_without_the_fixture_marker_is_refused(fixture: Fixture, tmp_path):
    (fixture.source / helper.FIXTURE_MARKER_NAME).unlink()
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code == helper.EXIT_GUARD
    assert payload["decision"] == helper.DECISION_REJECTED_GUARD
    assert spy.call_count("open_read") == 0


def test_cli_without_an_allow_list_refuses_to_run(fixture: Fixture, tmp_path):
    proc = subprocess.run(
        [sys.executable, str(HELPER_PATH),
         "--child", str(fixture.child_path),
         "--out", str(tmp_path / "out.json"),
         "--expected-child-sha256", fixture.child_sha256,
         "--expected-child-commit", fixture.anchor_commit],
        capture_output=True, text=True, check=False)
    assert proc.returncode == helper.EXIT_GUARD
    assert "allow-source-root" in proc.stderr


# --------------------------------------------------------------------------
# source phase: budgets, identity, escape
# --------------------------------------------------------------------------


def test_symlink_escape_is_rejected_and_the_outside_file_is_not_read(fixture: Fixture, tmp_path):
    outside_hash_before = oracle_sha256(fixture.outside_file)
    link = fixture.source / "alpha.bin"
    link.unlink()
    os.symlink(str(fixture.outside_file), str(link))
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code != 0
    assert payload["decision"] != helper.DECISION_VERIFIED
    escaped = [r for r in payload["results"] if r["relative_path"] == "alpha.bin"]
    assert escaped and escaped[0]["result"] == "SYMLINK_ESCAPE_REJECTED_NOT_VERIFIED"
    assert payload["counters"]["escape_rejected"] == 1
    assert str(fixture.outside_file) not in spy.touched()
    assert oracle_sha256(fixture.outside_file) == outside_hash_before


def test_changed_identity_is_not_verified(fixture: Fixture, tmp_path):
    target = fixture.source / "beta.bin"
    data = bytearray(target.read_bytes())
    data[0] = (data[0] + 1) % 256
    target.write_bytes(bytes(data))
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code != 0
    assert payload["decision"] != helper.DECISION_VERIFIED
    changed = [r for r in payload["results"] if r["relative_path"] == "beta.bin"]
    assert changed and changed[0]["result"] == "SOURCE_CHANGED_NOT_VERIFIED"
    assert payload["counters"]["identity_mismatch"] == 1


def test_byte_budget_exhaustion_is_rejected(fixture: Fixture, tmp_path):
    fixture.write_child(limits={"files": 3, "bytes": 16, "wall_seconds": 60, "chunk_bytes": 64})
    fixture.anchor_commit = fixture.commit_all("synthetic: tighten the byte budget")
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code != 0
    assert payload["decision"] != helper.DECISION_VERIFIED
    assert payload["counters"]["budget_exceeded"] >= 1


def test_wall_budget_exhaustion_is_rejected(fixture: Fixture, tmp_path):
    fixture.write_child(limits={"files": 3, "bytes": 1 << 20, "wall_seconds": 0,
                                "chunk_bytes": 64})
    fixture.anchor_commit = fixture.commit_all("synthetic: tighten the wall budget")
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code != 0
    assert payload["decision"] != helper.DECISION_VERIFIED
    assert payload["counters"]["budget_exceeded"] >= 1


def test_file_count_limit_is_enforced(fixture: Fixture, tmp_path):
    fixture.write_child(limits={"files": 2, "bytes": 1 << 20, "wall_seconds": 60,
                                "chunk_bytes": 64})
    fixture.anchor_commit = fixture.commit_all("synthetic: tighten the file count limit")
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code == helper.EXIT_REJECTED
    assert payload["decision"] == helper.DECISION_REJECTED_SOURCE
    assert "budget_rejection" in payload


def test_missing_selected_file_is_not_verified(fixture: Fixture, tmp_path):
    (fixture.source / "gamma.bin").unlink()
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert code != 0
    assert payload["decision"] != helper.DECISION_VERIFIED
    missing = [r for r in payload["results"] if r["relative_path"] == "gamma.bin"]
    assert missing and missing[0]["result"] == "MISSING_NOT_VERIFIED"
    assert payload["counters"]["missing"] == 1


def test_every_preflight_failure_mode_keeps_the_source_phase_untouched(fixture: Fixture,
                                                                       tmp_path):
    modes = [
        ("wrong_child_anchor", dict(expected_child_commit="2" * 40), None),
        ("wrong_child_digest", dict(expected_child_sha256="3" * 64), None),
        ("code_drift", {}, "tools/alpha.py"),
    ]

    for name, kwargs, drift in modes:
        if drift:
            (fixture.package / drift).write_text("ALPHA = 'drift-2'\n", encoding="utf-8")
        out = tmp_path / ("out-%s.json" % name)
        code, payload, spy = fixture.run_helper(out, **kwargs)
        assert_rejected_without_source_access(code, payload, spy)
        assert payload["preflight_rejection"], name


def test_preflight_verdict_is_control_flow_not_only_a_report_field(fixture: Fixture, tmp_path):
    # the report field and the control flow must agree: a false preflight must
    # not have entered the source phase at all
    (fixture.package / "tools" / "alpha.py").write_text("ALPHA = 'drift-3'\n", encoding="utf-8")
    code, payload, spy = fixture.run_helper(tmp_path / "out.json")
    assert payload["preflight_validated_before_source_access"] is False
    assert payload["source_phase_entered"] is False
    assert payload["counters"]["files_attempted"] == 0
    assert payload["counters"]["bytes_read"] == 0
    assert spy.calls == []
