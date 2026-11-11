#!/usr/bin/env python3
"""Independent D0-B-REVIEW probe harness for the V1 design 1.1.1 checker.

Method (reviewer owned, does NOT mirror the implementation's test file):

  * Every probe runs the *real* checker CLI (``python3 -B tools/verify_v1_plan.py
    --root <synthetic copy>``) on a fresh TemporaryDirectory copy of the
    candidate tree.  The owner tree is never written.
  * Every probe is run in one of two modes:

      fence=on   the spec manifest / D0 payload manifest are re-frozen for the
                 mutated file, so the *semantic* guard is the only thing that
                 can still reject the package.  A rejection here is a real
                 semantic guard.
      fence=off  the fences are left untouched, so a rejection is only proof
                 that the frozen hash noticed the edit (and nothing more).

    The two modes are what lets the review tell "rejected by the frozen hash"
    apart from "rejected by an actual rule".
  * Nothing in the owner tree is modified; only the synthetic copy is.

The harness prints one JSON object per probe and writes a machine readable
summary next to itself.
"""
from __future__ import annotations

import copy
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

# Files that the authority spec manifest fences, plus the two manifests.
OWNER_FILES = [
    "contracts/lvw.schema.json",
    "contracts/openapi.json",
    "contracts/storage.sql",
    "contracts/v1-multishot-migration.sql",
    "contracts/v1-multishot.openapi-overlay.json",
    "contracts/v1-multishot.schema.json",
    "docs/17_DATA_AND_VERSIONING.md",
    "docs/20_RELIABILITY_AND_OPERATIONS.md",
    "docs/30_V1_REVISED_EXECUTION_PLAN.md",
    "docs/31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md",
    "docs/32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md",
    "plans/acceptance_cases.json",
    "plans/execution-control.json",
    "plans/release_gates.json",
    "plans/requirements.json",
    "plans/tasks.json",
    "plans/v1-multishot-contract.json",
    "plans/v1-multishot-sample-design.json",
    "plans/v1-revised-plan.json",
    "reports/v1-redesign/design11-adjudication.json",
    "reports/v1-redesign/design111-adjudication.json",
    "reports/v1-redesign/legacy-gates-before-change.json",
    "reports/v1-redesign/product-change-approval.json",
    ".agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256",
    ".agent-governance/stages/V1-D0/00-coordinate.md",
    ".agent-governance/stages/V1-D0/01-scope-and-non-goals.md",
    ".agent-governance/stages/V1-D0/02-architecture-and-ownership.md",
    ".agent-governance/stages/V1-D0/03-workpack-plan.md",
    ".agent-governance/stages/V1-D0/04-acceptance-matrix.md",
    ".agent-governance/stages/V1-D0/05-risk-and-authorization-register.md",
    ".agent-governance/stages/V1-D0/06-implementation-prompt.md",
    ".agent-governance/stages/V1-D0/07-checkpoint-plan.md",
    SPEC_MANIFEST,
    D0_MANIFEST,
    ".agent-governance/stages/V1-D0/stage-control.json",
]

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


def refreeze(root: Path, changed: list[str], rebaseline: bool = False) -> None:
    """Re-freeze the authority spec manifest and the D0 payload manifest.

    ``rebaseline=True`` additionally re-writes the frozen *canonical contract*
    hashes inside legacy-gates-before-change.json, so that a probe on a
    canonical artefact is rejected (or accepted) by a semantic rule and not by
    the canonical hash fence.
    """
    if rebaseline:
        base_rel = "reports/v1-redesign/legacy-gates-before-change.json"
        base = load(root, base_rel)
        pinned = base.get("canonical_contract_hashes") or {}
        for rel in changed:
            if rel in pinned:
                pinned[rel] = sha256(root / rel)
        base["canonical_contract_hashes"] = pinned
        save(root, base_rel, base)
        changed = changed + [base_rel]
    spec = load(root, SPEC_MANIFEST)
    for rel in changed:
        if rel in spec["files"] and (root / rel).is_file():
            spec["files"][rel] = sha256(root / rel)
    save(root, SPEC_MANIFEST, spec)
    regen_d0_manifest(root)


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
    entry = {
        "probe": name,
        "purpose": purpose,
        "mode": mode,
        "command": " ".join(cmd),
        "exit_code": proc.returncode,
        "stdout_sha256": hashlib.sha256(proc.stdout.encode("utf-8")).hexdigest(),
        "stderr_sha256": hashlib.sha256(proc.stderr.encode("utf-8")).hexdigest(),
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "note": note,
    }
    RESULTS.append(entry)
    print("=" * 78)
    print("PROBE %s  [%s]" % (name, mode))
    print("purpose : %s" % purpose)
    print("exit    : %s" % proc.returncode)
    print("stdout  : %s" % (proc.stdout.strip().replace("\n", " | ")[:600] or "<empty>"))
    if proc.stderr.strip():
        print("stderr  : %s" % proc.stderr.strip().replace("\n", " | ")[:600])
    if note:
        print("note    : %s" % note)
    return entry


def probe(name, purpose, mutate, *, fence, expect_code=None, expect_exit=None, extra=None, env=None, note="",
         rebaseline=False):
    """Run one probe on a fresh temporary copy."""
    with tempfile.TemporaryDirectory(prefix="d0review-%s-" % name) as tmp:
        root = build_copy(Path(tmp))
        changed = mutate(root) or []
        pin = None
        if fence and changed:
            refreeze(root, changed, rebaseline)
        if fence:
            pin = sha256(root / D0_MANIFEST)
        cmd, proc = run_checker(root, pin, extra, env)
        entry = record(name, purpose, "fence=ON (semantic)" if fence else "fence=OFF (hash only)",
                       cmd, proc, note)
        codes = sorted({line.split(":", 1)[0] for line in proc.stdout.splitlines() if ":" in line})
        entry["finding_codes"] = codes
        if expect_code is not None:
            entry["expected_code_present"] = expect_code in proc.stdout
        if expect_exit is not None:
            entry["expected_exit_matched"] = (proc.returncode == expect_exit)
        return entry


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------

def m_n6_alias_drift(root: Path):
    rel = "plans/v1-multishot-contract.json"
    doc = load(root, rel)
    doc["scene_hash"]["column_mapping"]["media_sha256"] = "scene_revision.media_ref_id"
    save(root, rel, doc)
    return [rel]


def m_n6_sql_argument_permutation(root: Path):
    rel = "contracts/v1-multishot-migration.sql"
    text = (root / rel).read_text(encoding="utf-8")
    old = "s.start_pts,s.end_pts,s.origin_pts"
    new = "s.end_pts,s.start_pts,s.origin_pts"
    assert old in text
    (root / rel).write_text(text.replace(old, new), encoding="utf-8")
    return [rel]


def m_n5_example_rule_text_key_order(root: Path):
    """Rewrite the domain example with the key order the *rule text* names."""
    rel = "plans/v1-multishot-contract.json"
    doc = load(root, rel)
    doc["canonical_domain_mapping"]["example"]["observation"] = [
        '{"kind":"character","ref":"actor1","lang":"zh","text":"红衣人物"}',
        '{"kind":"character","ref":"actor1","lang":"en","text":"person in red"}',
    ]
    save(root, rel, doc)
    return [rel]


def m_n5_example_text_drift(root: Path):
    rel = "plans/v1-multishot-contract.json"
    doc = load(root, rel)
    doc["canonical_domain_mapping"]["example"]["observation"][0] = (
        '{"kind":"character","lang":"zh","ref":"actor1","text":"蓝衣人物"}'
    )
    save(root, rel, doc)
    return [rel]


def m_n1_scene_get_body_swapped(root: Path):
    """The new Scene GET returns another candidate component instead of Scene."""
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    body = doc["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    body["properties"]["data"] = {"$ref": "#/components/schemas/MultiShot_SceneRevisionInfo"}
    save(root, rel, doc)
    return [rel]


def m_n1_etag_pattern_equivalent_rewrite(root: Path):
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    hdr = doc["add_response_headers"]["/api/v1/scenes/{id}"]["put"]["200"]["ETag"]
    hdr["schema"]["pattern"] = '^"scene:[0-9a-z-]+:[0-9a-f]{64}"$'
    save(root, rel, doc)
    return [rel]


def m_n3_unauthorized_metadata_key(root: Path):
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["metadata_only"]["/api/v1/jobs/{id}"]["get"]["x-body-changed"] = True
    save(root, rel, doc)
    return [rel]


def m_n3_missing_reuse_annotation(root: Path):
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    del doc["metadata_only"]["/api/v1/shots/{id}"]["put"]
    save(root, rel, doc)
    return [rel]


def m_n2_contract_drops_operation(root: Path):
    rel = "plans/v1-multishot-contract.json"
    doc = load(root, rel)
    doc["additive_operations"] = [e for e in doc["additive_operations"]
                                  if not (e["path"] == "/api/v1/scenes/{id}" and e["method"] == "GET")]
    save(root, rel, doc)
    return [rel]


def m_n2_contract_drops_path(root: Path):
    rel = "plans/v1-multishot-contract.json"
    doc = load(root, rel)
    doc["additive_paths"] = [p for p in doc["additive_paths"] if p != "/api/v1/scenes/{id}"]
    save(root, rel, doc)
    return [rel]


def m_n4_null_branch_reintroduced(root: Path):
    rel = "contracts/v1-multishot.schema.json"
    doc = load(root, rel)
    doc["$defs"]["ShotFrameRef"]["properties"]["source_pts"] = {
        "anyOf": [{"type": "integer"}, {"type": "null"}],
        "type": "integer",
    }
    save(root, rel, doc)
    return [rel]


def m_n4_timebase_minimum_dropped(root: Path):
    rel = "contracts/v1-multishot.schema.json"
    doc = load(root, rel)
    doc["$defs"]["ShotFrameRef"]["properties"]["time_base_den"]["minimum"] = 0
    save(root, rel, doc)
    return [rel]


def m_empty_limits(root: Path):
    rel = "plans/v1-revised-plan.json"
    doc = load(root, rel)
    doc["limits"] = {}
    save(root, rel, doc)
    return [rel]


def m_dropped_dependency(root: Path):
    rel = "plans/v1-revised-plan.json"
    doc = load(root, rel)
    for stage in doc["stages"]:
        if stage.get("id") == "V1-M1":
            stage["depends_on"] = [d for d in stage.get("depends_on", []) if d != "R1"]
    save(root, rel, doc)
    return [rel]


def m_missing_entity_dto(root: Path):
    rel = "contracts/v1-multishot.schema.json"
    doc = load(root, rel)
    doc["$defs"].pop("ParentJob", None)
    save(root, rel, doc)
    return [rel]


def m_nan_limit(root: Path):
    rel = "plans/v1-revised-plan.json"
    text = (root / rel).read_text(encoding="utf-8")
    doc = json.loads(text)
    doc["limits"]["video_seconds"] = float("nan")
    save(root, rel, doc)
    return [rel]


def m_canonical_v2_batch_body(root: Path):
    rel = "contracts/openapi.json"
    doc = load(root, rel)
    doc["paths"]["/api/v1/jobs/batch"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"] = {
        "items2": {"type": "array"}
    }
    save(root, rel, doc)
    return [rel]


def m_docs_edit_only(root: Path):
    rel = "docs/31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md"
    text = (root / rel).read_text(encoding="utf-8")
    (root / rel).write_text(text + "\n<!-- reviewer probe -->\n", encoding="utf-8")
    return [rel]


def m_overlay_metadata_is_list(root: Path):
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["metadata_only"] = ["/api/v1/scenes"]
    save(root, rel, doc)
    return [rel]


def m_overlay_headers_is_list(root: Path):
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["add_response_headers"] = ["/api/v1/scenes/{id}"]
    save(root, rel, doc)
    return [rel]


def m_invalid_candidate_schema(root: Path):
    rel = "contracts/v1-multishot.schema.json"
    doc = load(root, rel)
    doc["$defs"]["ShotFrameRef"]["properties"]["sha256"]["pattern"] = "([unclosed"
    save(root, rel, doc)
    return [rel]


def m_adjudication_claims_accepted(root: Path):
    rel = "reports/v1-redesign/design111-adjudication.json"
    doc = load(root, rel)
    for finding in doc["findings"]:
        finding["state"] = "ACCEPTED"
    save(root, rel, doc)
    return [rel]


def m_sample_materialized(root: Path):
    rel = "plans/v1-multishot-sample-design.json"
    doc = load(root, rel)
    doc["clips"][0]["source_sha256"] = "0" * 64
    save(root, rel, doc)
    return [rel]


def m_checkpoint_budget_inflated(root: Path):
    rel = "plans/v1-revised-plan.json"
    doc = load(root, rel)
    doc["checkpoint_budget"]["model_actions_cap"] = 128
    save(root, rel, doc)
    return [rel]


def no_mutation(root: Path):
    return []


# --- second batch -----------------------------------------------------------

def m_overlay_surface_shrinks(root: Path):
    """Remove a whole (path, method) pair from the overlay itself."""
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    del doc["add_paths"]["/api/v1/shots/{id}/scene-binding"]["put"]
    save(root, rel, doc)
    return [rel]


def m_overlay_surface_grows(root: Path):
    """Add a ninth operation to the overlay surface."""
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["add_paths"]["/api/v1/extra-route"] = {"get": {"responses": {"200": {"description": "x"}}}}
    save(root, rel, doc)
    return [rel]


def m_etag_removed_from_put(root: Path):
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    del doc["add_response_headers"]["/api/v1/scenes/{id}"]["put"]["200"]["ETag"]
    save(root, rel, doc)
    return [rel]


def m_profile_value_drift(root: Path):
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["metadata_only"]["/api/v1/shots"]["post"]["x-v1-profile"] = "local-shot-v2"
    save(root, rel, doc)
    return [rel]


def m_metadata_collides_with_canonical_key(root: Path):
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["metadata_only"]["/api/v1/scenes"]["get"]["x-v2-semantics-unchanged"] = True
    doc["metadata_only"]["/api/v1/scenes"]["get"]["x-product-version"] = "V1"
    save(root, rel, doc)
    return [rel]


def m_v2_semantics_denied(root: Path):
    rel = "contracts/v1-multishot.openapi-overlay.json"
    doc = load(root, rel)
    doc["metadata_only"]["/api/v1/jobs/{id}"]["get"]["x-v2-semantics-unchanged"] = False
    save(root, rel, doc)
    return [rel]


def m_v2_batch_body_only(root: Path):
    """Change the canonical V2 batch body *and* re-baseline the canonical hashes,
    so only the semantic rule can reject it."""
    rel = "contracts/openapi.json"
    doc = load(root, rel)
    body = doc["paths"]["/api/v1/jobs/batch"]["post"]["requestBody"]["content"]["application/json"]["schema"]
    body["properties"]["items"]["items"] = {"$ref": "#/components/schemas/PromptSpec"}
    save(root, rel, doc)
    return [rel]


def m_core_scene_alias_drift(root: Path):
    """Break the canonical Scene alias and re-baseline the canonical hashes."""
    rel = "contracts/v1-multishot.schema.json"
    doc = load(root, rel)
    doc["$defs"]["CoreScene"]["properties"]["editor"]["enum"] = ["algorithm"]
    save(root, rel, doc)
    return [rel]


def m_adjudication_drops_finding(root: Path):
    rel = "reports/v1-redesign/design111-adjudication.json"
    doc = load(root, rel)
    doc["findings"] = [f for f in doc["findings"] if f.get("id") != "N3"]
    save(root, rel, doc)
    return [rel]


def m_product_coordinate_moved(root: Path):
    rel = "plans/execution-control.json"
    doc = load(root, rel)
    doc["coordinate"]["state"] = "UNIFIED_MEDIA_MACHINE_AND_INDEPENDENT_VERIFIED"
    save(root, rel, doc)
    return [rel]


def m_spec_fence_file_deleted(root: Path):
    rel = "docs/17_DATA_AND_VERSIONING.md"
    (root / rel).unlink()
    return [rel]


def m_canonical_carries_allowlisted_key(root: Path):
    """Let the canonical operation already carry x-v1-profile, so the overlay
    annotation becomes a real collision."""
    rel = "contracts/openapi.json"
    doc = load(root, rel)
    doc["paths"]["/api/v1/scenes"]["get"]["x-v1-profile"] = "canonical-profile"
    save(root, rel, doc)
    return [rel]


def m_canonical_loses_annotated_method(root: Path):
    """Remove the canonical GET /api/v1/jobs/{id} so the overlay annotation
    target no longer exists."""
    rel = "contracts/openapi.json"
    doc = load(root, rel)
    del doc["paths"]["/api/v1/jobs/{id}"]["get"]
    save(root, rel, doc)
    return [rel]


def m_canonical_loses_put_target(root: Path):
    """Remove the canonical PUT /api/v1/scenes/{id} so the ETag header target
    no longer exists."""
    rel = "contracts/openapi.json"
    doc = load(root, rel)
    del doc["paths"]["/api/v1/scenes/{id}"]["put"]
    save(root, rel, doc)
    return [rel]


def m_denominator_shrunk(root: Path):
    rel = "plans/release_gates.json"
    doc = load(root, rel)
    doc["gates"]["V1"]["required_cases"] = doc["gates"]["V1"]["required_cases"][:-1]
    save(root, rel, doc)
    return [rel]


def m_sample_shot_total_drift(root: Path):
    rel = "plans/v1-multishot-sample-design.json"
    doc = load(root, rel)
    doc["clips"][0]["shots"] = doc["clips"][0]["shots"] + 1
    save(root, rel, doc)
    return [rel]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("owner tree : %s" % OWNER)
    print("checker    : %s" % (OWNER / CHECKER_REL))
    print("checker sha: %s" % sha256(OWNER / CHECKER_REL))

    # --- positive control -------------------------------------------------
    probe("P00-positive-control", "unmodified copy of the candidate tree must PASS",
          no_mutation, fence=True, expect_exit=0, expect_code="RESULT: PASS")

    # --- N6 (scene hash alias mapping) ------------------------------------
    probe("P01-n6-unpinned-alias-drift",
          "N6: rename a NON pinned column alias (media_sha256 -> scene_revision.media_ref_id)",
          m_n6_alias_drift, fence=True,
          note="the 11 alias mapping is only pinned for time_base_num/time_base_den/revision")

    probe("P02-n6-sql-argument-permutation",
          "N6: permute the lvw_scene_hash call site arguments in the candidate migration",
          m_n6_sql_argument_permutation, fence=True,
          note="the SQL call site argument order is never compared with scene_hash.fields")

    # --- N5 (bilingual -> canonical Domains) --------------------------------
    probe("P03-n5-example-rule-text-key-order",
          "N5: rewrite the example with the key order the rule text names (kind,ref,lang,text)",
          m_n5_example_rule_text_key_order, fence=True, expect_code="E_DOMAIN_MAPPING")

    probe("P04-n5-example-text-drift",
          "N5: change the Chinese text of the example entry (red -> blue)",
          m_n5_example_text_drift, fence=True, expect_code="E_DOMAIN_MAPPING")

    # --- N1 (strong ETag / overlay merge) -----------------------------------
    probe("P05-n1-scene-get-body-swapped",
          "N1: the new GET /api/v1/scenes/{id} returns another candidate component instead of the canonical Scene",
          m_n1_scene_get_body_swapped, fence=True,
          note="the canonical Scene DTO on the new GET is not machine guarded")

    probe("P06-n1-etag-pattern-rewrite",
          "N1: rewrite the ETag pattern to a different but still strong-only regex",
          m_n1_etag_pattern_equivalent_rewrite, fence=True, expect_code="E_ETAG_FORMAT")

    # --- N3 (reuse annotations) ---------------------------------------------
    probe("P07-n3-unauthorized-metadata-key",
          "N3: add an unauthorized x- key to a reuse annotation",
          m_n3_unauthorized_metadata_key, fence=True, expect_code="E_OVERLAY_METADATA_KEY")

    probe("P08-n3-missing-reuse-annotation",
          "N3: drop the PUT annotation of /api/v1/shots/{id}",
          m_n3_missing_reuse_annotation, fence=True, expect_code="E_REUSE_METADATA")

    # --- N2 (additive surface) ----------------------------------------------
    probe("P09-n2-contract-drops-operation",
          "N2: remove the new GET /api/v1/scenes/{id} from the contract additive_operations",
          m_n2_contract_drops_operation, fence=True, expect_code="E_ADDITIVE_OPERATIONS")

    probe("P10-n2-contract-drops-path",
          "N2: remove /api/v1/scenes/{id} from the contract additive_paths",
          m_n2_contract_drops_path, fence=True, expect_code="E_ADDITIVE_PATHS")

    # --- N4 (per shot frame reference) ---------------------------------------
    probe("P11-n4-null-branch-reintroduced",
          "N4: reintroduce the unreachable null branch next to the integer source_pts",
          m_n4_null_branch_reintroduced, fence=True, expect_code="E_FRAME_REF_CONSTRAINT")

    probe("P12-n4-timebase-minimum-dropped",
          "N4: drop the positive timebase minimum of time_base_den",
          m_n4_timebase_minimum_dropped, fence=True, expect_code="E_FRAME_REF_CONSTRAINT")

    # --- empty list / missing dependency / missing entity --------------------
    probe("P13-empty-limits",
          "D0-CODE-M01 family: empty the plan limits object",
          m_empty_limits, fence=True, expect_code="E_LIMIT_MISSING")

    probe("P14-dropped-dependency",
          "drop the R1 dependency of the V1-M1 stage in the plan",
          m_dropped_dependency, fence=True, expect_code="E_DEP_M1_R1")

    probe("P15-missing-entity-dto",
          "remove the ParentJob DTO while the contract still declares the entity",
          m_missing_entity_dto, fence=True, expect_code="E_CONTRACT_ENTITY_UNRESOLVED")

    probe("P16-nan-limit",
          "put a NaN into plan.limits.video_seconds",
          m_nan_limit, fence=True, expect_code="E_LIMIT_NOT_FINITE")

    probe("P17-checkpoint-budget-inflated",
          "inflate the checkpoint model action cap to the per child cap",
          m_checkpoint_budget_inflated, fence=True, expect_code="E_CHECKPOINT_INPUT_DRIFT")

    probe("P18-sample-pretends-materialized",
          "let the sample design carry a materialized source_sha256",
          m_sample_materialized, fence=True, expect_code="E_SAMPLE_MATERIALIZED")

    probe("P19-adjudication-claims-accepted",
          "let the owner adjudication record N1-N6 as ACCEPTED",
          m_adjudication_claims_accepted, fence=True, expect_code="E_111_ADJUDICATION")

    # --- hash fence only ------------------------------------------------------
    probe("P20-hash-fence-only",
          "edit a fenced authority document WITHOUT re-freezing the fences",
          m_docs_edit_only, fence=False, expect_code="E_SPEC_FENCE_DRIFT",
          note="this rejection is the frozen hash, not a semantic rule")

    probe("P21-canonical-contract-drift",
          "change the canonical /api/v1/jobs/batch request body",
          m_canonical_v2_batch_body, fence=True, expect_code="E_CONTRACT_DRIFT",
          note="rejected by the frozen canonical contract hash")

    # --- malformed input ------------------------------------------------------
    probe("P22-malformed-overlay-metadata",
          "malformed input: overlay metadata_only is a list instead of an object",
          m_overlay_metadata_is_list, fence=True,
          note="expected a deterministic finding, not an uncaught traceback")

    probe("P23-malformed-overlay-headers",
          "malformed input: overlay add_response_headers is a list instead of an object",
          m_overlay_headers_is_list, fence=True,
          note="expected a deterministic finding, not an uncaught traceback")

    probe("P24-invalid-candidate-schema",
          "an invalid JSON Schema (unbalanced regex) in the candidate schema",
          m_invalid_candidate_schema, fence=True, expect_code="E_SCHEMA_META")

    # --- degraded evidence ----------------------------------------------------
    probe("P25-frame-sample-missing",
          "the retained frame reference sample is not available",
          no_mutation, fence=True, extra=["--frame-sample", "reports/unified-media/live-15/does-not-exist.json"],
          note="expected: the instance probe is skipped but the run still reports PASS")

    with tempfile.TemporaryDirectory(prefix="d0review-nojsonschema-") as tmp:
        shadow = Path(tmp) / "shadow"
        shadow.mkdir()
        (shadow / "jsonschema.py").write_text(
            'raise ImportError("jsonschema blocked by the reviewer probe")\n', encoding="utf-8")
        probe("P26-jsonschema-unavailable",
              "the optional jsonschema dependency is not importable",
              no_mutation, fence=True,
              env={"PYTHONPATH": str(shadow)},
              note="expected: the same PASS text, without disclosing the degraded validation")

    probe("P41-denominator-shrunk",
          "shrink the V1 acceptance denominator in release_gates.json",
          m_denominator_shrunk, fence=True, expect_code="E_DENOM_V1_COUNT")

    probe("P42-sample-shot-total-drift",
          "drift the sample design shot total",
          m_sample_shot_total_drift, fence=True, expect_code="E_SAMPLE_SHOT_COUNT")

    summary = Path(os.environ.get("D0REVIEW_SUMMARY", str(HERE / "probe-results.json")))

    # --- second batch: isolate the semantic guard from the hash guard -------
    probe("P27-overlay-surface-shrinks",
          "N2: remove one (path, method) pair from the overlay itself",
          m_overlay_surface_shrinks, fence=True, expect_code="E_ADDITIVE_SURFACE")

    probe("P28-overlay-surface-grows",
          "N2: add a ninth operation to the overlay additive surface",
          m_overlay_surface_grows, fence=True, expect_code="E_ADDITIVE_SURFACE")

    probe("P29-etag-removed-from-put",
          "N1: remove the ETag from the existing Scene PUT 200",
          m_etag_removed_from_put, fence=True, expect_code="E_ETAG_MISSING")

    probe("P30-profile-value-drift",
          "N3: change the x-v1-profile value of a reuse annotation",
          m_profile_value_drift, fence=True, expect_code="E_OVERLAY_METADATA_VALUE")

    probe("P31-metadata-collides-with-canonical-key",
          "N3: add an annotation key that already exists on the canonical operation",
          m_metadata_collides_with_canonical_key, fence=True, expect_code="E_OVERLAY_METADATA_COLLISION")

    probe("P32-v2-semantics-denied",
          "N3: set x-v2-semantics-unchanged to false",
          m_v2_semantics_denied, fence=True, expect_code="E_OVERLAY_METADATA_VALUE")

    probe("P33-v2-batch-body-semantic-only",
          "N1/F1: change the canonical V2 batch items $ref AND re-baseline the canonical hash",
          m_v2_batch_body_only, fence=True, rebaseline=True, expect_code="E_V2_BATCH_BODY_DRIFT",
          note="the canonical hash was re-baselined, so only the semantic rule can reject it")

    probe("P34-core-scene-alias-drift",
          "M1: break the canonical Scene alias and re-baseline the canonical hash",
          m_core_scene_alias_drift, fence=True, rebaseline=True, expect_code="E_CANONICAL_ALIAS")

    probe("P35-adjudication-drops-a-finding",
          "let the owner adjudication silently drop N3",
          m_adjudication_drops_finding, fence=True, expect_code="E_111_ADJUDICATION")

    probe("P36-product-coordinate-moved",
          "move the product coordinate away from R1 / WAIT_HUMAN",
          m_product_coordinate_moved, fence=True, expect_code="E_PRODUCT_COORDINATE")

    probe("P37-spec-fence-file-deleted",
          "delete a file that the authority spec manifest fences",
          m_spec_fence_file_deleted, fence=True, expect_code="E_SPEC_FENCE_MISSING")

    probe("P38-metadata-collision-reachable",
          "N3: the canonical operation already carries x-v1-profile, so the overlay annotation collides",
          m_canonical_carries_allowlisted_key, fence=True, rebaseline=True,
          expect_code="E_OVERLAY_METADATA_COLLISION")

    probe("P39-metadata-target-missing",
          "N1/N3: the overlay annotation target no longer exists in the canonical document",
          m_canonical_loses_annotated_method, fence=True, rebaseline=True,
          expect_code="E_OVERLAY_METADATA_TARGET_MISSING")

    probe("P40-header-target-missing",
          "N1: the overlay ETag header target no longer exists in the canonical document",
          m_canonical_loses_put_target, fence=True, rebaseline=True,
          expect_code="E_OVERLAY_HEADER_TARGET_MISSING")

    summary.write_text(json.dumps({"owner": str(OWNER), "probes": RESULTS}, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
    print("=" * 78)
    print("summary written to %s" % summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
