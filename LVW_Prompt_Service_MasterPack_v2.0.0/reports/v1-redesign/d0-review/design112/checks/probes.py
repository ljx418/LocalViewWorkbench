#!/usr/bin/env python3
"""Independent D0-B-REVIEW probe harness for the V1 design 1.1.2 checker.

This is a *bounded independent regression recheck* of the consolidated NM-1..
NM-8 correction package (candidate eea5663). It is not a restart of the
original 22 finding architecture audit.

Method (reviewer owned, does not mirror the candidate test file):

  * Every probe runs the *real* checker CLI (``python3 -B
    tools/verify_v1_plan.py --root <synthetic copy>``) on a fresh
    ``tempfile.TemporaryDirectory`` copy of the candidate tree. The owner
    tree is never written and no owner hash is ever regenerated in the
    checkout.
  * Semantic probes run in ``fence=on`` mode: the *synthetic copy* is
    re-frozen (the spec manifest hash of the mutated file is recomputed and
    the D0 payload manifest is rebuilt over the packet), so the only thing
    that can still reject the package is an actual rule. A rejection in this
    mode is a semantic guard, not a hash notice.
  * ``fence=off`` mode is only used where the point of the probe is the
    frozen hash itself.

Adapation note (the candidate changed version, inventory and pin):
the design 1.1.2 authority adds one fenced owner source
(``reports/v1-redesign/design112-adjudication.json``), so the owner file
inventory is 25 files, and the D0 payload pin moved from
04d3bfb4... (1.1.1) to 181c08ee... (1.1.2). The harness therefore reads the
inventories from the tree it copies instead of carrying a hard coded list,
and it computes the pin of the synthetic copy instead of assuming one. The
oracle expectations are the reviewer's own; they are not copied from the
candidate.

The harness prints one JSON object per probe and writes a machine readable
summary next to itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OWNER = Path(__file__).resolve().parents[5]          # .../LVW_Prompt_Service_MasterPack_v2.0.0
CHECKER_REL = "tools/verify_v1_plan.py"
D0_DIR = ".agent-governance/stages/V1-D0"
D0_MANIFEST = D0_DIR + "/PAYLOAD_MANIFEST.sha256"
SPEC_MANIFEST = D0_DIR + "/spec-manifest.json"

RESULTS = []


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(root: Path, rel: str):
    return json.loads((root / rel).read_text(encoding="utf-8"))


def save(root: Path, rel: str, payload) -> None:
    (root / rel).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def regen_d0_manifest(root: Path) -> str:
    """Rebuild the D0 payload manifest over the packet directory."""
    packet = root / D0_DIR
    names = sorted(p.name for p in packet.iterdir() if p.name != "PAYLOAD_MANIFEST.sha256")
    lines = ["%s  %s" % (sha256(packet / name), name) for name in names]
    (root / D0_MANIFEST).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return sha256(root / D0_MANIFEST)


def refreeze(root: Path, changed: list[str]) -> str:
    """Re-freeze the authority spec manifest and the D0 payload manifest.

    Only the *synthetic copy* is touched. The owner checkout keeps its
    hashes.
    """
    spec = load(root, SPEC_MANIFEST)
    for rel in changed:
        if rel in spec["files"] and (root / rel).is_file():
            spec["files"][rel] = sha256(root / rel)
    save(root, SPEC_MANIFEST, spec)
    return regen_d0_manifest(root)


def build_copy(tmp: Path) -> Path:
    root = tmp / "pkg"
    shutil.copytree(OWNER, root, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    return root


def run_checker(root: Path, pin: str | None = None, extra: list[str] | None = None, env: dict | None = None):
    cmd = [sys.executable, "-B", str(root / CHECKER_REL), "--root", str(root)]
    if pin is not None:
        cmd += ["--d0-packet-manifest-sha256", pin]
    cmd += list(extra or [])
    run_env = dict(os.environ)
    if env:
        run_env.update(env)
    proc = subprocess.run(cmd, capture_output=True, text=True, env=run_env)
    return cmd, proc


def record(name, purpose, mode, cmd, proc, note=""):
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    entry = {
        "probe": name,
        "purpose": purpose,
        "mode": mode,
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "stdout_sha256": hashlib.sha256(stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr.encode("utf-8")).hexdigest(),
        "stdout_bytes": len(stdout.encode("utf-8")),
        "stderr_bytes": len(stderr.encode("utf-8")),
        "stdout": stdout,
        "stderr": stderr,
        "traceback_in_stderr": "Traceback (most recent call last)" in stderr,
        "note": note,
    }
    RESULTS.append(entry)
    print("=" * 78)
    print("PROBE %s  [%s]" % (name, mode))
    print("purpose : %s" % purpose)
    print("exit    : %s" % proc.returncode)
    print("stdout  : %s" % (stdout.strip().replace("\n", " | ")[:700] or "<empty>"))
    if stderr.strip():
        print("stderr  : %s" % stderr.strip().replace("\n", " | ")[:400])
    if note:
        print("note    : %s" % note)
    return entry


def probe(name, purpose, mutate=None, *, fence=True, expect_code=None, expect_exit=None,
          extra=None, env=None, note="", use_default_pin=False):
    """Run one probe on a fresh temporary copy."""
    with tempfile.TemporaryDirectory(prefix="d0review112-%s-" % name) as tmp:
        root = build_copy(Path(tmp))
        changed = []
        if mutate is not None:
            changed = mutate(root) or []
        pin = None
        if fence and changed:
            pin = refreeze(root, changed)
        if use_default_pin:
            pin = None
        cmd, proc = run_checker(root, pin, extra, env)
        mode = "fence=ON (semantic)" if (fence and changed) else (
            "fence=OFF (hash only)" if not fence else "fence=n/a (unmutated)"
        )
        entry = record(name, purpose, mode, cmd, proc, note)
        codes = sorted({line.split(":", 1)[0] for line in proc.stdout.splitlines()
                        if line and ":" in line})
        entry["finding_codes"] = codes
        entry["result_line"] = next((line for line in proc.stdout.splitlines()
                                     if line.startswith("RESULT:")), "")
        entry["validation_line"] = next((line for line in proc.stdout.splitlines()
                                         if line.startswith("VALIDATION:")), "")
        entry["pin_line"] = next((line for line in proc.stdout.splitlines()
                                  if line.startswith("PIN:")), "")
        if expect_code is not None:
            entry["expected_code_present"] = expect_code in proc.stdout
        if expect_exit is not None:
            entry["expected_exit_matched"] = (proc.returncode == expect_exit)
        entry["stdout_has_traceback"] = "Traceback (most recent call last)" in proc.stdout
        return entry


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def m_benign_package_note(root: Path):
    """A benign edit that changes the payload pin of the synthetic copy.

    It is used by the pin probes: the synthetic copy gets a new D0 payload
    manifest digest, which is then passed explicitly on the command line.
    """
    rel = ".agent-governance/stages/V1-D0/00-coordinate.md"
    text = (root / rel).read_text(encoding="utf-8")
    (root / rel).write_text(text + "\nindependent probe: benign package note\n", encoding="utf-8")
    return [rel]


def m_alias_media_sha256(root: Path):
    """NM-1 replay: a formerly unpinned column alias is rebound."""
    rel = "plans/v1-multishot-contract.json"
    doc = load(root, rel)
    doc["scene_hash"]["column_mapping"]["media_sha256"] = "scene_revision.media_ref_id"
    save(root, rel, doc)
    return [rel]


def m_alias_editor(root: Path):
    """NM-1 new: another formerly unpinned alias (editor) is rebound."""
    rel = "plans/v1-multishot-contract.json"
    doc = load(root, rel)
    doc["scene_hash"]["column_mapping"]["editor"] = "scene_revision.tb_num"
    save(root, rel, doc)
    return [rel]


def m_sql_permutation_pts(root: Path):
    """NM-1 replay: the PTS arguments of the call site are permuted."""
    rel = "contracts/v1-multishot-migration.sql"
    text = (root / rel).read_text(encoding="utf-8")
    old = "s.start_pts,s.end_pts,s.origin_pts"
    new = "s.end_pts,s.start_pts,s.origin_pts"
    assert old in text, "the frozen call site text moved"
    (root / rel).write_text(text.replace(old, new), encoding="utf-8")
    return [rel]


def m_sql_permutation_first_two(root: Path):
    """NM-1 new: a second, different call-site permutation."""
    rel = "contracts/v1-multishot-migration.sql"
    text = (root / rel).read_text(encoding="utf-8")
    old = "s.media_ref_id,m.sha256"
    new = "m.sha256,s.media_ref_id"
    assert old in text, "the frozen call site text moved"
    (root / rel).write_text(text.replace(old, new), encoding="utf-8")
    return [rel]


def m_scene_get_body_swapped(root: Path):
    """NM-2 replay: the new Scene GET returns another candidate component."""
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    body = doc["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    body["properties"]["data"] = {"$ref": "#/components/schemas/MultiShot_SceneRevisionInfo"}
    save(root, rel, doc)
    return [rel]


def m_scene_get_envelope_extra_property(root: Path):
    """NM-2 new: the success envelope gains a property."""
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    body = doc["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    body["properties"]["extra"] = {"type": "string"}
    save(root, rel, doc)
    return [rel]


def m_scene_get_envelope_required_dropped(root: Path):
    """NM-2 new: the success envelope drops a required member."""
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    body = doc["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    body["required"] = [name for name in body.get("required", []) if name != "request_id"]
    save(root, rel, doc)
    return [rel]


def m_metadata_only_list(root: Path):
    """NM-3 replay: overlay.metadata_only is a list."""
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["metadata_only"] = ["/api/v1/scenes"]
    save(root, rel, doc)
    return [rel]


def m_metadata_only_nested_list(root: Path):
    """NM-3 new: a nested metadata value is a list instead of an object."""
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["metadata_only"]["/api/v1/scenes/{id}"] = ["get"]
    save(root, rel, doc)
    return [rel]


def m_add_headers_list(root: Path):
    """NM-3 replay: overlay.add_response_headers is a list."""
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["add_response_headers"] = ["/api/v1/scenes/{id}"]
    save(root, rel, doc)
    return [rel]


def m_add_headers_nested_list(root: Path):
    """NM-3 new: a nested response header status map is a list."""
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["add_response_headers"]["/api/v1/scenes/{id}"]["put"] = ["200"]
    save(root, rel, doc)
    return [rel]


def m_schema_bad_pattern(root: Path):
    """NM-3 replay: an invalid regular expression in the candidate schema."""
    rel = "contracts/v1-multishot.schema.json"
    doc = load(root, rel)
    doc["$defs"]["ShotFrameRef"]["properties"]["sha256"]["pattern"] = "([unclosed"
    save(root, rel, doc)
    return [rel]


def m_schema_defs_list(root: Path):
    """NM-3 new: a nested container of the candidate schema is not an object."""
    rel = "contracts/v1-multishot.schema.json"
    doc = load(root, rel)
    doc["$defs"] = ["Scene"]
    save(root, rel, doc)
    return [rel]


def m_domain_scene_ref(root: Path):
    """NM-6: the declared ref of the scene domain is rebound."""
    rel = "plans/v1-multishot-contract.json"
    doc = load(root, rel)
    doc["canonical_domain_mapping"]["refs"]["scene"] = "scene_id"
    save(root, rel, doc)
    return [rel]


def m_domain_example_other_domain(root: Path):
    """NM-6: the example also carries entries of the other declared domain."""
    rel = "plans/v1-multishot-contract.json"
    doc = load(root, rel)
    doc["canonical_domain_mapping"]["example"]["inference"] = [
        '{"kind":"character","lang":"zh","ref":"actor1","text":"红衣人物"}'
    ]
    save(root, rel, doc)
    return [rel]


def shadow_jsonschema(tmp: Path) -> str:
    """A directory whose jsonschema module refuses to import."""
    shadow = tmp / "shadow"
    shadow.mkdir()
    (shadow / "jsonschema.py").write_text(
        "raise ImportError('shadowed by the independent probe harness')\n",
        encoding="utf-8",
    )
    return str(shadow)


# ---------------------------------------------------------------------------
# The probes
# ---------------------------------------------------------------------------

def main() -> int:
    # -- positive control -------------------------------------------------
    probe("P00", "positive control: the unmodified candidate copy passes with the default pin",
          fence=False, use_default_pin=True, expect_exit=0,
          note="the oracle is the reviewer's own: exit 0 and a RESULT: PASS line")

    # -- NM-1 -------------------------------------------------------------
    probe("P01", "NM-1 replay: a formerly unpinned column alias is rebound (media_sha256)",
          m_alias_media_sha256, expect_code="E_SCENE_HASH_MAPPING", expect_exit=1)
    probe("P02", "NM-1 replay: the call-site PTS arguments are permuted",
          m_sql_permutation_pts, expect_code="E_SCENE_HASH_MAPPING", expect_exit=1)
    probe("P30", "NM-1 new: a second, different call-site permutation (first two arguments)",
          m_sql_permutation_first_two, expect_code="E_SCENE_HASH_MAPPING", expect_exit=1)
    probe("P31", "NM-1 new: another formerly unpinned alias is rebound (editor)",
          m_alias_editor, expect_code="E_SCENE_HASH_MAPPING", expect_exit=1)

    # -- NM-2 -------------------------------------------------------------
    probe("P05", "NM-2 replay: the new Scene GET returns another candidate component",
          m_scene_get_body_swapped, expect_code="E_SCENE_GET_ENVELOPE", expect_exit=1)
    probe("P32", "NM-2 new: the success envelope gains a property",
          m_scene_get_envelope_extra_property, expect_code="E_SCENE_GET_ENVELOPE", expect_exit=1)
    probe("P37", "NM-2 new: the success envelope drops a required member",
          m_scene_get_envelope_required_dropped, expect_code="E_SCENE_GET_ENVELOPE", expect_exit=1)

    # -- NM-3 -------------------------------------------------------------
    probe("P22", "NM-3 replay: overlay.metadata_only is a list",
          m_metadata_only_list, expect_exit=1,
          note="the oracle is a deterministic E_* on stdout, a non-zero exit and no traceback")
    probe("P23", "NM-3 replay: overlay.add_response_headers is a list",
          m_add_headers_list, expect_exit=1)
    probe("P24", "NM-3 replay: the candidate schema carries an invalid regular expression",
          m_schema_bad_pattern, expect_code="E_SCHEMA_PATTERN", expect_exit=1)
    probe("P33", "NM-3 new: a nested metadata value is a list instead of an object",
          m_metadata_only_nested_list, expect_exit=1)
    probe("P34", "NM-3 new: a nested response header status map is a list",
          m_add_headers_nested_list, expect_exit=1)
    probe("P35", "NM-3 new: a nested container of the candidate schema is not an object",
          m_schema_defs_list, expect_exit=1)

    # -- NM-4 / NM-8 ------------------------------------------------------
    with tempfile.TemporaryDirectory(prefix="d0review112-shadow-") as tmp:
        shadow = shadow_jsonschema(Path(tmp))
        probe("P25", "NM-4 replay: the optional jsonschema dependency is not importable",
              fence=False, use_default_pin=True, expect_exit=0, env={"PYTHONPATH": shadow},
              note="a degraded run must be distinguishable from a full run")
    probe("P26", "NM-4 replay: the retained frame sample is absent",
          fence=False, use_default_pin=True, expect_exit=0,
          extra=["--frame-sample", "reports/unified-media/live-15/does-not-exist.json"],
          note="a degraded run must be distinguishable from a full run")
    probe("P27", "NM-8: an explicit pin override is marked as a non authority run",
          m_benign_package_note, fence=True, expect_exit=0,
          note="the oracle is the reviewer's own: exit 0 and a PIN line that names the override")
    probe("P28", "NM-8: the same copy under the default pin is rejected and reported as the default mode",
          m_benign_package_note, fence=True, use_default_pin=True,
          expect_code="E_D0_PACKET_MANIFEST_PINNED", expect_exit=1,
          note="the default pin and the explicit override must be distinguishable")
    probe("P29", "NM-8: a stale 1.1.1 pin passed explicitly is still rejected",
          fence=False, use_default_pin=True,
          extra=["--d0-packet-manifest-sha256",
                 "04d3bfb4af3c2d7be68e494a6d59624a96051a0ebf28e81d6a0367aa32aa6710"],
          expect_code="E_D0_PACKET_MANIFEST_PINNED", expect_exit=1)

    probe("P40", "NM-8: the design 1.1 pin passed explicitly is still rejected",
          fence=False, use_default_pin=True,
          extra=["--d0-packet-manifest-sha256",
                 "56e6f07b72023928b32ed7350b78f9d1d148daf79108daffecb7d9a175e39c4a"],
          expect_code="E_D0_PACKET_MANIFEST_PINNED", expect_exit=1)
    probe("P41", "NM-8: the design 1.0 pin passed explicitly is still rejected",
          fence=False, use_default_pin=True,
          extra=["--d0-packet-manifest-sha256",
                 "9bffdf2dc968f54fae0404d162c394e265cfb9900f68d9c303683bef756ede7b"],
          expect_code="E_D0_PACKET_MANIFEST_PINNED", expect_exit=1)

    # -- NM-6 -------------------------------------------------------------
    probe("P38", "NM-6: the declared ref of the scene domain is rebound",
          m_domain_scene_ref, expect_code="E_DOMAIN_MAPPING", expect_exit=1)
    probe("P39", "NM-6: the example also carries entries of the other declared domain",
          m_domain_example_other_domain, expect_code="E_DOMAIN_MAPPING", expect_exit=1)

    summary = {
        "probes_total": len(RESULTS),
        "probes": RESULTS,
    }
    out = HERE / "probe-results.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("=" * 78)
    print("probes written to %s" % out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
