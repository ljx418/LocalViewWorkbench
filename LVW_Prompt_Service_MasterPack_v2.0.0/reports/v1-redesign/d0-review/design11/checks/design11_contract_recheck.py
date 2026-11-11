#!/usr/bin/env python3
"""D0-B-REVIEW design1.1 independent recheck - contract/design level probes.

Read-only against the repository (this script writes only its own result file
next to itself). Stdlib + jsonschema only. No product/runtime execution, no
model, no media, no network.

Every check states what it compares and where the raw evidence lives.
Exit code 0 = script ran to completion (individual check failures are recorded
in the result JSON, they do not change the exit code).
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent

LAUNCH_D0_PAYLOAD_MANIFEST_SHA256 = "56e6f07b72023928b32ed7350b78f9d1d148daf79108daffecb7d9a175e39c4a"
AUTHORITY_SHA = "932dcbc48bca99c463ffea8bf11d121c36aefe0c"

checks: list[dict] = []


def ck(check_id: str, group: str, passed: bool, detail, severity_if_fail: str = "major") -> None:
    checks.append(
        {
            "id": check_id,
            "group": group,
            "passed": bool(passed),
            "severity_if_fail": severity_if_fail,
            "detail": detail,
        }
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def canonical_json_sha256(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


# ---------------------------------------------------------------- group: fence
G = "A_hash_fence"
spec_manifest = load_json(".agent-governance/stages/V1-D0/spec-manifest.json")
manifest_files = spec_manifest["files"]
mismatches = {}
for rel, expected in manifest_files.items():
    actual = sha256_file(ROOT / rel)
    if actual != expected:
        mismatches[rel] = {"expected": expected, "actual": actual}
ck(
    "A01",
    G,
    not mismatches,
    {
        "source": ".agent-governance/stages/V1-D0/spec-manifest.json",
        "declared_files": len(manifest_files),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "note": "17 pre-existing review files + 6 design1.1 additions (migration.sql, openapi overlay, sample-design, docs/17, docs/20, design11-adjudication.json)",
    },
)

payload_manifest = ROOT / ".agent-governance/stages/V1-D0/PAYLOAD_MANIFEST.sha256"
payload_actual_sha = sha256_file(payload_manifest)
ck(
    "A02",
    G,
    payload_actual_sha == LAUNCH_D0_PAYLOAD_MANIFEST_SHA256,
    {
        "file": ".agent-governance/stages/V1-D0/PAYLOAD_MANIFEST.sha256",
        "launch_value": LAUNCH_D0_PAYLOAD_MANIFEST_SHA256,
        "actual": payload_actual_sha,
    },
)

stage_dir = payload_manifest.parent
payload_rows = []
payload_bad = []
for line in payload_manifest.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    digest, name = line.split(None, 1)
    name = name.strip()
    actual = sha256_file(stage_dir / name)
    payload_rows.append({"file": name, "expected": digest, "actual": actual})
    if actual != digest:
        payload_bad.append(name)
ck(
    "A03",
    G,
    not payload_bad,
    {"entries": len(payload_rows), "mismatch": payload_bad, "rows": payload_rows},
    severity_if_fail="fatal",
)

legacy = load_json("reports/v1-redesign/legacy-gates-before-change.json")
canonical_now = {rel: sha256_file(ROOT / rel) for rel in legacy["canonical_contract_hashes"]}
canonical_bad = [r for r, h in canonical_now.items() if legacy["canonical_contract_hashes"][r] != h]
ck(
    "A04",
    G,
    not canonical_bad,
    {
        "recorded": legacy["canonical_contract_hashes"],
        "actual": canonical_now,
        "note": "canonical OpenAPI/core schema/baseline DDL byte-identical to pre-change record",
    },
    severity_if_fail="fatal",
)
r1_manifest_now = sha256_file(ROOT / ".agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256")
ck(
    "A05",
    G,
    r1_manifest_now == legacy["old_R1_packet_manifest_sha256"],
    {"expected": legacy["old_R1_packet_manifest_sha256"], "actual": r1_manifest_now},
    severity_if_fail="fatal",
)

# ------------------------------------------------------- group: candidate schema
G = "B_candidate_schema"
candidate = load_json("contracts/v1-multishot.schema.json")
core = load_json("contracts/lvw.schema.json")["$defs"]
api = load_json("contracts/openapi.json")
api_schemas = api["components"]["schemas"]

try:
    Draft202012Validator.check_schema(candidate)
    metaschema_ok, metaschema_err = True, None
except Exception as exc:  # pragma: no cover - defensive
    metaschema_ok, metaschema_err = False, str(exc)
ck("B01", G, metaschema_ok, {"result": "ok" if metaschema_ok else metaschema_err})

ck(
    "B02",
    G,
    candidate["$defs"]["CoreScene"] == api_schemas["Scene"] == core["Scene"],
    {
        "candidate_CoreScene_equals_openapi_Scene": candidate["$defs"]["CoreScene"] == api_schemas["Scene"],
        "candidate_CoreScene_equals_lvw_schema_Scene": candidate["$defs"]["CoreScene"] == core["Scene"],
        "canonical_Scene_required": api_schemas["Scene"]["required"],
        "canonical_Scene_additionalProperties": api_schemas["Scene"].get("additionalProperties"),
    },
    severity_if_fail="major",
)

# ShotFrameRef must be a *valid instance shape* of the canonical FrameRef.
canon_fr = core["FrameRef"]
cand_fr = candidate["$defs"]["ShotFrameRef"]
prop_report = {}
compatible = True
for name, spec in cand_fr["properties"].items():
    if name not in canon_fr["properties"]:
        prop_report[name] = "NOT_IN_CANONICAL"
        compatible = False
        continue
    cs = canon_fr["properties"][name]
    if spec == cs:
        prop_report[name] = "IDENTICAL"
    elif name == "time_basis" and spec.get("const") in cs.get("enum", []):
        prop_report[name] = f"NARROWED_CONST_in_canonical_enum({cs['enum']})"
    elif cs.get("type") == "integer" and spec.get("type") == "integer":
        prop_report[name] = "SAME_TYPE_INT"
    elif "anyOf" in cs and "anyOf" in spec and spec.get("type") in [
        b.get("type") for b in cs["anyOf"] if isinstance(b, dict)
    ]:
        prop_report[name] = "NARROWED_TO_NON_NULL_BRANCH_OF_CANONICAL_anyOf"
    else:
        prop_report[name] = {"candidate": spec, "canonical": cs}
        compatible = False
extra_required = sorted(set(cand_fr["required"]) - set(canon_fr["required"]))
if extra_required:
    compatible = False
ck(
    "B03",
    G,
    compatible and not extra_required,
    {
        "claim": "ShotFrameRef is a shape-compatible / valid instance of canonical FrameRef",
        "per_property": prop_report,
        "candidate_required_not_in_canonical": extra_required,
        "candidate_additionalProperties": cand_fr.get("additionalProperties"),
        "canonical_required": canon_fr["required"],
    },
    severity_if_fail="major",
)

# Generated instances must validate against the canonical FrameRef.
fr_validator = Draft202012Validator(canon_fr)
sample_frame = {
    "index": 0,
    "target_seconds": 1.5,
    "source_pts": 900,
    "time_base_num": 1,
    "time_base_den": 25,
    "sha256": "a" * 64,
    "time_basis": "decoded_pts",
}
instance_errors = [e.message for e in fr_validator.iter_errors(sample_frame)]
ck(
    "B04",
    G,
    not instance_errors,
    {"generated_instance": sample_frame, "canonical_FrameRef_errors": instance_errors},
    severity_if_fail="major",
)

# The reverse direction (canonical instance -> candidate) was the 1.0 probe; keep it.
live15 = load_json("reports/unified-media/live-15/video-model-run.json")
cand_fr_validator = Draft202012Validator({**candidate, "$ref": "#/$defs/ShotFrameRef"})
live_errors = {}
for frame in live15.get("frames", []):
    errs = [e.message for e in cand_fr_validator.iter_errors(frame)]
    if errs:
        live_errors[str(frame.get("index"))] = errs
ck(
    "B05",
    G,
    not live_errors,
    {
        "source": "reports/unified-media/live-15/video-model-run.json",
        "frames_checked": len(live15.get("frames", [])),
        "errors": live_errors,
    },
)

# Internal/public separation of the lease token (M6).
pub = candidate["$defs"]["PublicAnalysisBinding"]
internal = candidate["$defs"]["AnalysisBinding"]
pub_with_token = dict(pub["properties"])
pub_with_token["lease_token"] = {"type": "string"}
leak = [e.message for e in Draft202012Validator(pub).iter_errors({"shot_id": "s", "scene_revision_id": "r",
                                                                "scene_revision_hash": "a" * 64,
                                                                "media_ref_id": "m", "media_sha256": "b" * 64,
                                                                "config_hash": "c" * 64, "attempt_id": "a1",
                                                                "cancel_epoch": 0, "lease_token": "secret"})]
ck(
    "B06",
    G,
    "lease_token" not in pub["properties"] and "lease_token" in internal["required"] and bool(leak),
    {
        "public_has_lease_token": "lease_token" in pub["properties"],
        "internal_requires_lease_token": "lease_token" in internal["required"],
        "public_instance_with_token_rejected": bool(leak),
        "public_errors": leak,
    },
    severity_if_fail="major",
)

# No 'detected' vocabulary introduced in the public Scene body (m6).
blob = json.dumps(candidate, ensure_ascii=False)
ck(
    "B07",
    G,
    '"detected"' not in blob and set(candidate["$defs"]["CoreScene"]["properties"]["editor"]["enum"]) == {"algorithm", "human"},
    {
        "candidate_contains_detected_vocabulary": '"detected"' in blob,
        "candidate_editor_enum": candidate["$defs"]["CoreScene"]["properties"]["editor"]["enum"],
        "canonical_editor_enum": api_schemas["Scene"]["properties"]["editor"]["enum"],
    },
)

# --------------------------------------------------------------- group: overlay
G = "C_overlay"
overlay = load_json("contracts/v1-multishot.openapi-overlay.json")
contract = load_json("plans/v1-multishot-contract.json")

ck(
    "C01",
    G,
    "/api/v1/jobs/batch" not in overlay["add_paths"],
    {
        "canonical_batch_requestBody": api["paths"]["/api/v1/jobs/batch"]["post"]["requestBody"],
        "canonical_batch_x_product_version": api["paths"]["/api/v1/jobs/batch"]["post"].get("x-product-version"),
        "overlay_touches_batch": "/api/v1/jobs/batch" in overlay["add_paths"],
        "reserved_v2_paths": contract["explicit_reserved_v2_paths"],
    },
    severity_if_fail="fatal",
)

ck(
    "C02",
    G,
    "/api/v1/jobs/shot-batches" in overlay["add_paths"]
    and overlay["add_paths"]["/api/v1/jobs/shot-batches"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    == "#/components/schemas/MultiShot_BatchAnalyzeRequest",
    {
        "new_route_request_ref": overlay["add_paths"]["/api/v1/jobs/shot-batches"]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"],
        "note": "bounded new route, distinct component, canonical batch body untouched",
    },
    severity_if_fail="fatal",
)

# Build the effective document the way docs/31 describes and check that no
# canonical path/method/component is replaced.
effective = json.loads(json.dumps(api))
for path, ops in overlay["add_paths"].items():
    target = effective["paths"].setdefault(path, {})
    for method, op in ops.items():
        if method in target:
            raise AssertionError(f"overlay would replace existing method {method} {path}")
        target[method] = op
for name, defn in candidate["$defs"].items():
    comp = json.loads(json.dumps(defn))
    text = json.dumps(comp, ensure_ascii=False)
    text = text.replace("#/$defs/", "#/components/schemas/MultiShot_")
    comp = json.loads(text)
    effective["components"]["schemas"]["MultiShot_" + name] = comp

canonical_paths_intact = True
replaced = []
for path, ops in api["paths"].items():
    for method, op in ops.items():
        eff = effective["paths"].get(path, {}).get(method)
        if eff != op:
            canonical_paths_intact = False
            replaced.append(f"{method.upper()} {path}")
for name, comp in api["components"]["schemas"].items():
    if effective["components"]["schemas"].get(name) != comp:
        canonical_paths_intact = False
        replaced.append(f"component {name}")
ck(
    "C03",
    G,
    canonical_paths_intact,
    {"replaced_canonical_items": replaced, "checked_paths": len(api["paths"]), "checked_components": len(api["components"]["schemas"])},
    severity_if_fail="fatal",
)

name_collisions = sorted(set(candidate["$defs"]) & set(api["components"]["schemas"]))
ck(
    "C04",
    G,
    not name_collisions,
    {
        "collisions": name_collisions,
        "note": "1.0 finding C18 was a bare FrameRef name collision; 1.1 prefixes every candidate component MultiShot_",
        "prefix": overlay["component_prefix"],
    },
    severity_if_fail="major",
)

# every $ref in the effective document resolves
unresolved = []


def walk_refs(node, path):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "$ref" and isinstance(v, str):
                if not v.startswith("#/"):
                    unresolved.append((path, v))
                else:
                    cur = effective
                    for part in v[2:].split("/"):
                        if not isinstance(cur, dict) or part not in cur:
                            unresolved.append((path, v))
                            break
                        cur = cur[part]
            else:
                walk_refs(v, path)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            walk_refs(v, f"{path}[{i}]")


walk_refs(effective, "#")
ck(
    "C05",
    G,
    not unresolved,
    {"unresolved_refs": unresolved[:20], "unresolved_count": len(unresolved)},
    severity_if_fail="major",
)

# overlay/contract/doc path-set consistency
overlay_paths = set(overlay["add_paths"])
contract_paths = set(contract["additive_paths"])
ck(
    "C06",
    G,
    overlay_paths == contract_paths,
    {
        "overlay_add_paths": sorted(overlay_paths),
        "contract_additive_paths": sorted(contract_paths),
        "in_overlay_not_in_contract": sorted(overlay_paths - contract_paths),
        "in_contract_not_in_overlay": sorted(contract_paths - overlay_paths),
        "note": "the machine contract file is the enumeration an implementer/verifier would diff against the overlay",
    },
    severity_if_fail="minor",
)

reuse_paths = set(contract["reuse_paths"])
annotated = set(overlay.get("metadata_only", {}))
ck(
    "C07",
    G,
    reuse_paths == annotated,
    {
        "contract_reuse_paths": sorted(reuse_paths),
        "overlay_metadata_only_keys": sorted(annotated),
        "reuse_paths_without_overlay_annotation": sorted(reuse_paths - annotated),
        "note": "docs/31 states the overlay marks the V1-usable subset of scenes/detect and scenes; the overlay only annotates 2 of the 7 declared reuse paths",
    },
    severity_if_fail="minor",
)

# ETag header: is it a machine-declared OpenAPI header anywhere?
etag_header_declared = any(
    "headers" in json.dumps(op)
    for ops in overlay["add_paths"].values()
    for op in ops.values()
)
ck(
    "C08",
    G,
    etag_header_declared,
    {
        "overlay_metadata_only": overlay.get("metadata_only"),
        "any_openapi_headers_key_in_overlay": etag_header_declared,
        "docs31_etag_rule": 'quoted strong tag scene:<scene_revision_id>:<hash>',
        "note": "ETag is described in docs/31 and the overlay metadata_only free-text map, but not as an OpenAPI responses.*.headers entry",
    },
    severity_if_fail="minor",
)


# --- merged effective document sanity: unique operationIds, every op has responses
op_ids = []
missing_responses = []
for path, ops in effective["paths"].items():
    for method, op in ops.items():
        if method in ("parameters",):
            continue
        op_ids.append(op.get("operationId"))
        if not op.get("responses"):
            missing_responses.append(f"{method.upper()} {path}")
duplicates = sorted({o for o in op_ids if op_ids.count(o) > 1})
ck(
    "C09",
    G,
    not duplicates and not missing_responses,
    {
        "case": "the merged effective-openapi must have unique operationIds and every operation a response map",
        "duplicate_operation_ids": duplicates,
        "operations_without_responses": missing_responses,
        "operation_count": len(op_ids),
    },
    severity_if_fail="major",
)

# --------------------------------------------------------------- group: contract
G = "D_contract_entities"
for ent in ["ParentJob", "SceneRevisionInfo", "AnalysisBinding", "ShotEvidence"]:
    declared = contract["entities"][ent]["required"]
    schema_def = candidate["$defs"][ent]
    ck(
        f"D_{ent}",
        G,
        sorted(declared) == sorted(schema_def["required"]),
        {"contract_required": sorted(declared), "schema_required": sorted(schema_def["required"])},
        severity_if_fail="major",
    )

job_status = set(api_schemas["Job"]["properties"]["status"]["enum"])
child_status = set(candidate["$defs"]["ChildSummary"]["properties"]["status"]["enum"])
parent_status = set(candidate["$defs"]["ParentJob"]["properties"]["status"]["enum"])
ck(
    "D01",
    G,
    child_status <= job_status and parent_status <= job_status and "not_run" not in child_status,
    {
        "canonical_job_status": sorted(job_status),
        "child_status": sorted(child_status),
        "parent_status": sorted(parent_status),
        "invented_not_run": "not_run" in child_status,
        "note": "M7 required no invented Job enum; deadline/cancel reuse canonical values plus an explicit error_code",
    },
    severity_if_fail="major",
)

terminal = contract["terminal_errors"]
term_status_ok = all(
    v.get("child_status", "failed") in job_status for v in terminal.values()
) and all(v.get("parent_status", "failed") in job_status for v in terminal.values())
ck(
    "D02",
    G,
    term_status_ok
    and terminal["BATCH_DEADLINE_EXCEEDED"]["child_status"] == "failed"
    and terminal["JOB_CANCELLED"]["child_status"] == "cancelled"
    and terminal["CHILD_ANALYSIS_INCOMPLETE"]["parent_status"] == "partial",
    {"terminal_errors": terminal, "canonical_job_status": sorted(job_status)},
    severity_if_fail="major",
)

# request error -> HTTP status must be declared on the new route
shot_batch_responses = set(overlay["add_paths"]["/api/v1/jobs/shot-batches"]["post"]["responses"])
missing_status = {
    code: status
    for code, status in contract["request_errors"].items()
    if str(status) not in shot_batch_responses
}
ck(
    "D03",
    G,
    not missing_status,
    {
        "request_errors": contract["request_errors"],
        "shot_batches_declared_responses": sorted(shot_batch_responses),
        "request_errors_without_matching_response_code": missing_status,
        "note": "m9 asked for request-level vs terminal-level error tables; this checks the request table is routable on the new bounded route",
    },
    severity_if_fail="minor",
)

# scene hash field order == SQL argument order
sql = (ROOT / "contracts/v1-multishot-migration.sql").read_text(encoding="utf-8")
calls = [m for m in re.findall(r"lvw_scene_hash\(([^)]*)\)", sql) if "11args" not in m]
sql_args = [a.strip() for a in calls[0].split(",")] if calls else []
expected_args = [
    "s.media_ref_id",
    "m.sha256",
    "s.version",
    "s.start_pts",
    "s.end_pts",
    "s.origin_pts",
    "s.tb_num",
    "s.tb_den",
    "s.editor",
    "'unverified'",
    "0",
]
ck(
    "D04",
    G,
    sql_args == expected_args,
    {
        "contract_scene_hash_fields": contract["scene_hash"]["fields"],
        "sql_call_args": sql_args,
        "expected_sql_call_args": expected_args,
        "note": "SQL column names tb_num/tb_den vs contract time_base_num/time_base_den; the mapping is implied by the SQL text only",
    },
    severity_if_fail="minor",
)

ck(
    "D05",
    G,
    contract["scene_hash"]["algorithm"].startswith("sha256 UTF8 canonical JSON")
    and ("sort_keys" in contract["scene_hash"]["algorithm"] or "sorted keys" in contract["scene_hash"]["algorithm"])
    and contract["scene_hash"]["fields"]
    == ["media_ref_id", "media_sha256", "revision", "start_pts", "end_pts", "origin_pts", "time_base_num", "time_base_den", "editor", "time_basis", "verified"],
    {"scene_hash": contract["scene_hash"]},
    severity_if_fail="major",
)

# six product modes == canonical PromptSpec.mode enum
prompt_modes = set(core["PromptSpec"]["properties"]["mode"]["enum"])
cand_modes = set(candidate["$defs"]["BatchAnalyzeRequest"]["properties"]["mode"]["enum"])
ck(
    "D06",
    G,
    cand_modes == prompt_modes == {"documentary", "realistic", "scifi", "science", "cinematic", "stylized"},
    {
        "candidate_batch_mode_enum": sorted(cand_modes),
        "canonical_PromptSpec_mode_enum": sorted(prompt_modes),
        "canonical_AnalyzeRequest_mode": api_schemas["AnalyzeRequest"]["properties"]["mode"],
    },
    severity_if_fail="major",
)

# ---------------------------------------------------------- group: sample design
G = "E_sample_design"
samples = load_json("plans/v1-multishot-sample-design.json")
clips = samples["clips"]
shot_sum = sum(c["shots"] for c in clips)
cut_sum = sum(c["hard_cut_annotations"] for c in clips)
ck(
    "E01",
    G,
    len(clips) == 12 and shot_sum == 47 and cut_sum == 21
    and samples["total_clips"] == 12 and samples["total_shots"] == 47 and samples["hard_cut_annotation_count"] == 21,
    {
        "clips": len(clips),
        "sum_shots": shot_sum,
        "sum_hard_cut_annotations": cut_sum,
        "declared": {k: samples[k] for k in ("total_clips", "total_shots", "hard_cut_annotation_count")},
    },
    severity_if_fail="major",
)

qs = samples["quality_subset"]
counts = {}
for q in qs:
    counts[q["category"]] = counts.get(q["category"], 0) + 1
ck(
    "E02",
    G,
    len(qs) == 18 and counts == {"simple_action": 12, "ambiguous": 3, "static": 3} and counts == samples["quality_counts"],
    {"subset_size": len(qs), "counts": counts, "declared_quality_counts": samples["quality_counts"]},
    severity_if_fail="major",
)

# every quality shot id must exist inside its clip's shot count
bad_refs = []
for q in qs:
    clip = next((c for c in clips if c["id"] == q["clip_id"]), None)
    if clip is None:
        bad_refs.append({"q": q, "why": "clip missing"})
        continue
    idx = int(q["shot_id"][1:])
    if not (1 <= idx <= clip["shots"]):
        bad_refs.append({"q": q, "clip_shots": clip["shots"]})
ck(
    "E03",
    G,
    not bad_refs,
    {"quality_refs_outside_clip_shot_count": bad_refs, "note": "segment ids S01.. are 1-based per clip"},
    severity_if_fail="major",
)

# per-clip quality attribution in the machine table must agree with quality_subset
attrib_mismatch = []
for c in clips:
    derived = {q["shot_id"]: q["category"] for q in qs if q["clip_id"] == c["id"]}
    if derived != c["quality"]:
        attrib_mismatch.append({"clip": c["id"], "clip_quality": c["quality"], "derived": derived})
ck(
    "E04",
    G,
    not attrib_mismatch,
    {"per_clip_quality_attribution_mismatch": attrib_mismatch},
    severity_if_fail="major",
)

# nothing is materialised: no hashes, no frozen labels
materialised = [
    c["id"]
    for c in clips
    if c["source_sha256"] or c["annotation_hash"] or c["status"] != "NOT_MATERIALIZED_NOT_FROZEN"
]
ck(
    "E05",
    G,
    not materialised,
    {
        "clips_claiming_materialisation": materialised,
        "status": samples["status"],
        "note": "actual media hashes/annotations are NOT obtained; declared as a future Gate0 prerequisite, not a fake Gate0",
    },
    severity_if_fail="fatal",
)

# docs/32 12-row table must equal the machine sample design
doc32 = (ROOT / "docs/32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md").read_text(encoding="utf-8")
TYPE_MAP = [
    ("\u786c\u5207", "hard_cut"),
    ("\u65e0\u5207", "no_cut"),
    ("\u6e10\u53d8", "dissolve"),
    ("\u53e0\u5316", "crossfade"),
    ("VFR", "vfr"),
    ("\u5feb\u5207", "short_fastcuts"),
]
QUALITY_MAP = [
    ("\u7b80\u5355\u52a8\u4f5c", "simple_action"),
    ("\u542b\u7cca", "ambiguous"),
    ("\u9759\u6001", "static"),
]


def map_type(text: str):
    for zh, en in TYPE_MAP:
        if zh in text:
            return en
    return None


def map_quality(text: str):
    out = {}
    for zh, en in QUALITY_MAP:
        if zh in text:
            out[en] = True
    return out


doc_rows = {}
for line in doc32.splitlines():
    m = re.match(r"^\|\s*(H0\d|N0\d|D0\d|V01|F01)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|\s*$", line)
    if m:
        doc_rows[m.group(1)] = {
            "type_zh": m.group(2).strip(),
            "type": map_type(m.group(2).strip()),
            "shots": int(m.group(3).strip()),
            "cuts": int(m.group(4).strip()),
            "quality_zh": m.group(5).strip(),
            "quality_categories": map_quality(m.group(5).strip()),
        }
doc_mismatch = []
for c in clips:
    row = doc_rows.get(c["id"])
    if row is None:
        doc_mismatch.append({"clip": c["id"], "why": "missing from docs/32 table"})
        continue
    expected_categories = set(c["quality"].values())
    if (
        row["shots"] != c["shots"]
        or row["cuts"] != c["hard_cut_annotations"]
        or not str(c["category"]).startswith(str(row["type"]))
        or set(row["quality_categories"]) != expected_categories
        or len(row["quality_categories"]) != len(expected_categories)
    ):
        doc_mismatch.append({"clip": c["id"], "docs32": row, "machine": c})
ck(
    "E06",
    G,
    not doc_mismatch and len(doc_rows) == 12,
    {"docs32_rows": len(doc_rows), "mismatch": doc_mismatch},
    severity_if_fail="major",
)

# --------------------------------------------------------------- group: budgets
G = "F_budgets"
plan = load_json("plans/v1-revised-plan.json")
budget = plan["checkpoint_budget"]
resource = plan["limits"]
ck(
    "F01",
    G,
    all(450 * n + 90 <= 5490 for n in range(1, 13)) and 450 * 12 + 90 == 5490
    and resource["single_analysis_seconds"] + resource["release_seconds"] == resource["batch_per_child_budget_seconds"],
    {
        "parent_budget_formula": "450*n+90",
        "n1": 450 * 1 + 90,
        "n12": 450 * 12 + 90,
        "declared_max": resource["batch_deadline_seconds_max"],
        "child_420_plus_release_30": resource["single_analysis_seconds"] + resource["release_seconds"],
        "declared_per_child": resource["batch_per_child_budget_seconds"],
        "old_1800_removed": "batch_deadline_seconds" not in resource,
    },
    severity_if_fail="major",
)

estimate = (
    budget["video_calls"] * budget["video_threshold_seconds"]
    + budget["image_calls"] * budget["image_threshold_seconds"]
    + budget["success_calls"] * budget["release_per_success_seconds"]
    + budget["cpu_browser_overhead_seconds"]
    + budget["controlled_actions_cap"] * budget["controlled_action_seconds_cap"]
    + budget["cleanup_reserve_seconds"]
)
ck(
    "F02",
    G,
    estimate == budget["estimated_total_seconds"] == 20735
    and budget["execution_deadline_seconds"] + budget["cleanup_reserve_seconds"] == budget["wall_seconds"] == 21600
    and budget["success_calls"] + budget["controlled_actions_cap"] == budget["model_actions_cap"] == 72
    and budget["video_calls"] + budget["image_calls"] == budget["success_calls"]
    and estimate <= budget["execution_deadline_seconds"],
    {
        "recomputed_estimate": estimate,
        "declared_estimate": budget["estimated_total_seconds"],
        "execution_deadline": budget["execution_deadline_seconds"],
        "wall": budget["wall_seconds"],
        "cleanup_reserve": budget["cleanup_reserve_seconds"],
        "actions": budget["success_calls"] + budget["controlled_actions_cap"],
        "declared_estimate_basis": budget["estimate_basis"],
    },
    severity_if_fail="major",
)

snap = load_json("reports/unified-media/complete03-budget-after-live15.json")
residual_actions = snap["global_limits"]["model_actions"] - snap["model_actions"]
residual_rounds = snap["global_limits"]["effective_full_checkpoints"] - snap["effective_full_checkpoints"]
residual_seconds = snap["global_limits"]["production_seconds"] - snap["production_seconds"]
rounds_claim = min(residual_actions // 72, residual_rounds, residual_seconds // 21600)
ck(
    "F03",
    G,
    residual_actions == 995 and residual_rounds == 16 and residual_seconds == 171294 and rounds_claim == 7
    and snap["historical_consumption_reset"] is False,
    {
        "source": "reports/unified-media/complete03-budget-after-live15.json",
        "observed": {k: snap[k] for k in ("model_actions", "effective_full_checkpoints", "production_seconds")},
        "limits": snap["global_limits"],
        "residual": {"actions": residual_actions, "rounds": residual_rounds, "seconds": residual_seconds},
        "docs32_claim_min(13,16,7)": rounds_claim,
        "historical_consumption_reset": snap["historical_consumption_reset"],
    },
    severity_if_fail="major",
)


ck(
    "F04",
    G,
    "47\u9010\u955c\u5934+\u539fQ01\u5341\u4e8c\u56fe\u516d\u7247=65\u6210\u529f\u8c03\u7528" in doc32
    and 47 + 12 + 6 == budget["success_calls"]
    and budget["video_calls"] == 47 + 6
    and budget["image_calls"] == 12,
    {
        "case": "the checkpoint call derivation must be stated and arithmetically reproducible (47 per-shot + Q01 12 images + 6 clips = 65 success calls)",
        "docs32_sentence_present": "47\u9010\u955c\u5934+\u539fQ01\u5341\u4e8c\u56fe\u516d\u7247=65\u6210\u529f\u8c03\u7528" in doc32,
        "declared_video_calls": budget["video_calls"],
        "expected_video_calls": 47 + 6,
        "declared_image_calls": budget["image_calls"],
        "declared_success_calls": budget["success_calls"],
    },
    severity_if_fail="major",
)

# --------------------------------------------------------- group: behaviour probes
G = "G_behaviour"
def validator_for(name):
    return Draft202012Validator({**candidate, "$ref": f"#/$defs/{name}"})


def valid(inst, name):
    return not list(validator_for(name).iter_errors(inst))


good_req = {
    "shot_ids": ["s1", "s2"],
    "scene_revision_ids": ["r1", "r2"],
    "mode": "realistic",
    "config_profile": "p",
}
cases = [
    ("G01", "BatchAnalyzeRequest 12 shot_ids accepted", valid({**good_req, "shot_ids": [f"s{i}" for i in range(12)]}, "BatchAnalyzeRequest"), True, {}),
    ("G02", "BatchAnalyzeRequest 13 shot_ids rejected", not valid({**good_req, "shot_ids": [f"s{i}" for i in range(13)]}, "BatchAnalyzeRequest"), True, {}),
    ("G03", "BatchAnalyzeRequest unknown mode rejected", not valid({**good_req, "mode": "anime"}, "BatchAnalyzeRequest"), True, {}),
    (
        "G04",
        "BatchAnalyzeRequest unequal list lengths are NOT schema-caught (semantic only)",
        valid({**good_req, "shot_ids": ["s1"], "scene_revision_ids": ["r1", "r2"]}, "BatchAnalyzeRequest"),
        True,
        {"note": "documented in x-semantic-invariants, owner-side check"},
    ),
    (
        "G05",
        "PublicAnalysisBinding rejects lease_token",
        not valid({**{k: good_req["shot_ids"][0] for k in []}}, "PublicAnalysisBinding")
        and not valid(
            {
                "shot_id": "s",
                "scene_revision_id": "r",
                "scene_revision_hash": "a" * 64,
                "media_ref_id": "m",
                "media_sha256": "b" * 64,
                "config_hash": "c" * 64,
                "attempt_id": "a1",
                "cancel_epoch": 0,
                "lease_token": "x",
            },
            "PublicAnalysisBinding",
        ),
        {},
    ),
    (
        "G06",
        "ChildSummary rejects invented not_run status",
        not valid(
            {
                "ordinal": 0,
                "job_id": "j",
                "shot_id": "s",
                "scene_revision_id": "r",
                "scene_revision_hash": "a" * 64,
                "status": "not_run",
                "result_ref": None,
                "error_code": "BATCH_DEADLINE_EXCEEDED",
                "model_started": False,
                "retry_of_child_id": None,
            },
            "ChildSummary",
        ),
        True,
        {},
    ),
    (
        "G07",
        "ParentJob execution_budget_seconds 5491 rejected",
        not valid(
            {
                "id": "p",
                "plan_hash": "a" * 64,
                "planned_child_ids": ["c"],
                "selected_scene_revision_ids": ["r"],
                "total": 1,
                "terminal_count": 0,
                "deadline_at": "2026-11-11T00:00:00Z",
                "execution_budget_seconds": 5491,
                "status": "queued",
                "not_executed_count": 0,
                "retry_of_parent_id": None,
            },
            "ParentJob",
        ),
        True,
        {},
    ),
    (
        "G08",
        "ParentJob execution_budget_seconds 539 rejected (450*1+90=540)",
        not valid(
            {
                "id": "p",
                "plan_hash": "a" * 64,
                "planned_child_ids": ["c"],
                "selected_scene_revision_ids": ["r"],
                "total": 1,
                "terminal_count": 0,
                "deadline_at": "2026-11-11T00:00:00Z",
                "execution_budget_seconds": 539,
                "status": "queued",
                "not_executed_count": 0,
                "retry_of_parent_id": None,
            },
            "ParentJob",
        ),
        True,
        {},
    ),
    (
        "G09",
        "Character without domain rejected (M8 domain carrier)",
        not valid(
            {"local_actor_id": "a1", "visible_appearance": {"zh": "人", "en": "person"}, "evidence_frame_indices": [0]},
            "Character",
        ),
        True,
        {},
    ),
    (
        "G10",
        "Action domain user_evidence rejected (human-owned domains)",
        not valid(
            {
                "actor_ref": None,
                "description": {"zh": "走", "en": "walk"},
                "domain": "user_evidence",
                "evidence_frame_indices": [0, 1],
            },
            "Action",
        ),
        True,
        {},
    ),
    (
        "G11",
        "ShotFrameRef missing target_seconds rejected",
        not valid({k: v for k, v in sample_frame.items() if k != "target_seconds"}, "ShotFrameRef"),
        True,
        {},
    ),
    (
        "G12",
        "ShotFrameRef time_basis sample_target rejected (per-shot real PTS only)",
        not valid({**sample_frame, "time_basis": "sample_target"}, "ShotFrameRef"),
        True,
        {},
    ),
    (
        "G13",
        "SceneRevisionInfo missing time_basis rejected (M2 carrier)",
        not valid(
            {
                "scene_revision_id": "r",
                "scene_id": "s",
                "scene": {
                    "id": "s",
                    "media_ref_id": "m",
                    "revision": 1,
                    "start_pts": 0,
                    "end_pts": 10,
                    "origin_pts": 0,
                    "time_base_num": 1,
                    "time_base_den": 25,
                    "verified": True,
                    "editor": "algorithm",
                },
                "source_sha256": "a" * 64,
                "scene_revision_hash": "b" * 64,
                "etag": '"scene:r:hash"',
            },
            "SceneRevisionInfo",
        ),
        True,
        {},
    ),
    (
        "G14",
        "ShotEvidence missing frame_refs rejected",
        not valid(
            {
                "characters": [],
                "scene": {"description": {"zh": "室", "en": "room"}, "domain": "observation", "evidence_frame_indices": [0]},
                "actions": [],
                "summary": {"zh": "描", "en": "desc"},
                "negative": "",
                "tags": [],
                "unknowns": [],
            },
            "ShotEvidence",
        ),
        True,
        {},
    ),
    (
        "G15",
        "ShotFrameRef with null source_pts is rejected by the candidate schema (anyOf null branch is dead)",
        not valid({**sample_frame, "source_pts": None}, "ShotFrameRef"),
        {
            "note": "candidate adds a sibling type:integer next to anyOf[int,null]; the null branch can never validate. Intent (per-shot real PTS only) matches docs/31, but the schema text is self-contradictory",
        },
    ),
]
for entry in cases:
    cid, name, passed = entry[0], entry[1], entry[2]
    if len(entry) == 5:
        expected, detail = entry[3], entry[4]
        detail = {**detail, "expected_outcome": bool(expected), "observed_outcome": bool(passed)}
        passed = bool(passed) == bool(expected)
    else:
        detail = entry[3]
    ck(cid, G, passed, {"case": name, **detail})

# ------------------------------------------------- group: governance / product
G = "H_governance"
control = load_json("plans/execution-control.json")
ck(
    "H01",
    G,
    control["human_signoff"] is None
    and control["product_acceptance"] is None
    and control["active_slice"]["human_signoff"] is None
    and "V1_ACCEPTED" in control["forbidden_claims"],
    {
        "human_signoff": control["human_signoff"],
        "product_acceptance": control["product_acceptance"],
        "active_slice": control["active_slice"]["id"],
        "active_slice_human_signoff": control["active_slice"]["human_signoff"],
        "forbidden_claims": control["forbidden_claims"],
    },
    severity_if_fail="fatal",
)

m1 = next((s for s in control["development_outline"] if s.get("stage_id") == "V1-M1"), None)
ck(
    "H02",
    G,
    m1 is not None and m1.get("machine_acceptance") == "NOT_RUN" and m1.get("human_signoff") == "NOT_SIGNED",
    {"v1_m1_outline": m1},
    severity_if_fail="fatal",
)

approval = load_json("reports/authorization-program-v1-complete-03.request.json")
ck(
    "H03",
    G,
    "R2" in approval["stages"] and not any(s.startswith("V2") for s in approval["stages"]),
    {"authorized_stages": approval["stages"], "note": "M1 design_stage maps onto authority_stage R2; no V2 alias"},
    severity_if_fail="fatal",
)

# acceptance denominators: V1 = original 21 + MS01..08
legacy_v1 = set(legacy["required_cases"]["V1"])
plan_cases = set(plan["v1_required_cases"])
ms_cases = {c for c in plan_cases if c.startswith("MS")}
ck(
    "H04",
    G,
    len(plan_cases) == 29 and ms_cases == {f"MS0{i}" for i in range(1, 9)}
    and (legacy_v1 - ms_cases) <= plan_cases,
    {
        "v1_required_cases": len(plan_cases),
        "ms_cases": sorted(ms_cases),
        "original_cases_kept": sorted((legacy_v1 - ms_cases) & plan_cases),
        "missing_original": sorted(legacy_v1 - plan_cases),
    },
    severity_if_fail="major",
)

q01 = next(c for c in load_json("plans/acceptance_cases.json")["cases"] if c["case_id"] == "Q01")
ck(
    "H05",
    G,
    q01["preconditions"] == ["12图+6片、独立预标注"]
    and "图>=10/12、片>=5/6、无关键幻觉；不是模型自评" in q01["assertions"],
    {"q01_preconditions": q01["preconditions"], "q01_assertions": q01["assertions"]},
    severity_if_fail="major",
)

# the authority commit must not touch product/runtime source
authority_files = [
    line.split("\t", 1)[1] if "\t" in line else line
    for line in __import__("subprocess").run(
        ["git", "-C", str(ROOT), "diff", "--relative", "--name-only", "0459f85", AUTHORITY_SHA],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
]
forbidden_prefixes = ("lvw/", "tools/", "frontend/")
touched_product = [f for f in authority_files if f.startswith(forbidden_prefixes)]
ck(
    "H06",
    G,
    not touched_product,
    {
        "authority_changed_file_count": len(authority_files),
        "product_source_files_touched": touched_product,
        "note": "the 1.1 authority changes only docs/plans/contracts/reports/.agent-governance/MANIFEST",
    },
    severity_if_fail="fatal",
)


# ------------------------------------------- group: I docs <-> machine coverage
G = "I_docs_machine_coverage"
doc31 = (ROOT / "docs/31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md").read_text(encoding="utf-8")
doc17 = (ROOT / "docs/17_DATA_AND_VERSIONING.md").read_text(encoding="utf-8")
doc20 = (ROOT / "docs/20_RELIABILITY_AND_OPERATIONS.md").read_text(encoding="utf-8")
doc29 = (ROOT / "docs/29_V1_MULTI_SHOT_SUPPLEMENT_PROPOSAL.md").read_text(encoding="utf-8")

ck(
    "I01",
    G,
    "2026-11-11" in doc17 and "2026-11-11" in doc20 and "V1-M1" in doc17 and "V1-M1" in doc20,
    {
        "m1_documents_that_must_carry_the_2026-11-11_override": ["docs/17_DATA_AND_VERSIONING.md", "docs/20_RELIABILITY_AND_OPERATIONS.md"],
        "docs17_mentions_V1-M1": "V1-M1" in doc17,
        "docs20_mentions_V1-M1": "V1-M1" in doc20,
        "docs17_override_present": "2026-11-11" in doc17,
        "docs20_override_present": "2026-11-11" in doc20,
    },
    severity_if_fail="major",
)

ck(
    "I02",
    G,
    ("\u7981\u6b62\u7528\u4e8e\u672c\u529f\u80fd\u5f00\u53d1" in doc29)
    and ("\u7edd\u4e0d\u7528\u4e8e\u672c\u6b21MS\u5f00\u53d1" in doc32)
    and ("\u5373\u4f7f\u6ce8\u660e\u7528\u9014\u4e5f\u4e0d\u5141\u8bb8" in doc32),
    {
        "m2_rule": "the eleven human holdout clips must be absolutely excluded from MS development, tuning and automatic acceptance",
        "docs29_absolute_wording": "\u7981\u6b62\u7528\u4e8e\u672c\u529f\u80fd\u5f00\u53d1" in doc29,
        "docs32_absolute_wording": "\u7edd\u4e0d\u7528\u4e8e\u672c\u6b21MS\u5f00\u53d1" in doc32,
        "docs32_even_with_a_note": "\u5373\u4f7f\u6ce8\u660e\u7528\u9014\u4e5f\u4e0d\u5141\u8bb8" in doc32,
    },
    severity_if_fail="major",
)

ck(
    "I03",
    G,
    ("sha" in samples["mutual_exclusion"].lower() or "hash" in samples["mutual_exclusion"].lower())
    and ("origin" in samples["mutual_exclusion"].lower() or "source id" in samples["mutual_exclusion"].lower())
    and ("SHA" in doc32 and "origin" in doc32),
    {
        "m3_rule": "development set / new MS set / Q01 set / eleven holdouts must be mutually exclusive at media SHA and origin source id level",
        "machine_mutual_exclusion": samples["mutual_exclusion"],
        "docs32_states_sha_and_origin": ("SHA" in doc32 and "origin" in doc32),
    },
    severity_if_fail="major",
)

ck(
    "I04",
    G,
    control["updated_at"] == "2026-11-11",
    {"m5_rule": "execution-control.updated_at must be refreshed together with the coordinate write", "updated_at": control["updated_at"]},
    severity_if_fail="minor",
)

decode_phrases = [
    "\u5355\u6b21\u6709\u754c",          # single bounded pass
    "PTS\u7d22\u5f15",                     # PTS index
    "keyframe seek",                          # per-shot seek
    "\u4e0d\u7f13\u5b58\u5168\u7247tensor",  # no full-video tensor
]
missing_phrases = [p for p in decode_phrases if p not in doc31]
ck(
    "I05",
    G,
    not missing_phrases,
    {
        "m8_rule": "the decode strategy must be stated (bounded scoring + PTS metadata index + per-shot keyframe seek, no N full passes, no full-video tensor)",
        "missing_phrases_in_docs31": missing_phrases,
        "docs31_decode_section_present": "\u89e3\u7801" in doc31,
    },
    severity_if_fail="minor",
)

# docs/31 route table must mention every overlay path (with the api/v1 prefix optional)
route_mentions = {}
for path in overlay["add_paths"]:
    tail = path.replace("/api/v1", "")
    route_mentions[path] = tail in doc31
ck(
    "I06",
    G,
    all(route_mentions.values()),
    {
        "case": "every path the overlay adds must appear in the docs/31 public-route table",
        "mentioned": route_mentions,
    },
    severity_if_fail="minor",
)

# parent/child job kinds must exist in the canonical Job.kind enum
ck(
    "I07",
    G,
    {"batch", "analyze"} <= set(api_schemas["Job"]["properties"]["kind"]["enum"]),
    {
        "canonical_job_kind_enum": api_schemas["Job"]["properties"]["kind"]["enum"],
        "needed": ["batch (parent shot-batch)", "analyze (child)"],
        "note": "the parent job must not require a canonical Job enum extension",
    },
    severity_if_fail="major",
)

# every human-language evidence carrier must carry a domain and be bilingual
evidence_carriers = ["Character", "SceneEvidence", "Action"]
carrier_detail = {}
carrier_ok = True
for name in evidence_carriers:
    props = candidate["$defs"][name]["properties"]
    has_domain = "domain" in props and props["domain"]["enum"] == ["observation", "inference"]
    bilingual = any(
        isinstance(v, dict) and v.get("$ref") == "#/$defs/BilingualPhrase" for v in props.values()
    )
    carrier_detail[name] = {"domain": has_domain, "bilingual": bilingual}
    carrier_ok = carrier_ok and has_domain and bilingual
ck(
    "I08",
    G,
    carrier_ok,
    {"m8_rule": "character / scene / action must each carry domain=observation|inference and a bilingual source", "per_type": carrier_detail},
    severity_if_fail="major",
)

# BatchChildrenResponse must expose the parent view, ordered children and the deadline carrier
bcr = candidate["$defs"]["BatchChildrenResponse"]
parent_props = candidate["$defs"]["ParentJob"]["properties"]
ck(
    "I09",
    G,
    bcr["required"] == ["parent", "children"]
    and bcr["properties"]["parent"]["$ref"] == "#/$defs/ParentJob"
    and bcr["properties"]["children"]["items"]["$ref"] == "#/$defs/ChildSummary"
    and "deadline_at" in parent_props
    and "terminal_count" in parent_props
    and "ordinal" in candidate["$defs"]["ChildSummary"]["properties"],
    {
        "m4_rule": "the parent view must carry deadline/terminal_count and the children must be ordered",
        "batch_children_response_required": bcr["required"],
        "parent_has_deadline_at": "deadline_at" in parent_props,
        "parent_has_terminal_count": "terminal_count" in parent_props,
        "child_has_ordinal": "ordinal" in candidate["$defs"]["ChildSummary"]["properties"],
    },
    severity_if_fail="major",
)

# canonical AnalyzeRequest must remain a free-string mode (m7)
ck(
    "I10",
    G,
    api_schemas["AnalyzeRequest"]["properties"]["mode"] == {"type": "string"},
    {
        "m7_rule": "the legacy free-string mode must stay untouched; only the new bounded route restricts the six modes",
        "canonical_AnalyzeRequest_mode": api_schemas["AnalyzeRequest"]["properties"]["mode"],
    },
    severity_if_fail="major",
)


# ------------------------------------------- group: J preserved 1.0 obligations
G = "J_preserved_obligations"
gates = load_json("plans/release_gates.json")["gates"]
v1_gate = gates["V1"]["required_cases"]
v2_gate = gates["V2"]["required_cases"]
v3_gate = gates["V3"]["required_cases"]
ck(
    "J01",
    G,
    len(v1_gate) == 29 and len(v2_gate) == 38 and len(v3_gate) == 47
    and v1_gate[: len(v1_gate) - 8] == [c for c in legacy["required_cases"]["V1"] if not c.startswith("MS")]
    and [c for c in v1_gate if c.startswith("MS")] == [f"MS0{i}" for i in range(1, 9)],
    {
        "case": "the 1.0 denominators must stay additive (29/38/47) with the original 21 as an unchanged prefix",
        "V1": len(v1_gate),
        "V2": len(v2_gate),
        "V3": len(v3_gate),
        "V1_original_prefix": v1_gate[: len(v1_gate) - 8],
        "V1_ms_cases": [c for c in v1_gate if c.startswith("MS")],
    },
    severity_if_fail="major",
)

reqs = load_json("plans/requirements.json")
req_list = reqs["requirements"] if isinstance(reqs, dict) and "requirements" in reqs else reqs
req_by_id = {r.get("requirement_id") or r.get("id"): r for r in req_list}
ck(
    "J02",
    G,
    req_by_id.get("R13", {}).get("introduced_in") == "V2"
    and req_by_id.get("R22", {}).get("introduced_in") == "V1"
    and req_by_id.get("R06", {}).get("introduced_in") == "V1",
    {
        "case": "R13 stays V2, R22 and R06 stay V1 - the 1.1 revision must not widen or narrow the approved scope",
        "R13": req_by_id.get("R13", {}).get("introduced_in"),
        "R22": req_by_id.get("R22", {}).get("introduced_in"),
        "R06": req_by_id.get("R06", {}).get("introduced_in"),
    },
    severity_if_fail="major",
)

tasks = load_json("plans/tasks.json")
task_list = tasks["stages"] if isinstance(tasks, dict) and "stages" in tasks else tasks
deps = {}
for t in task_list:
    tid = t.get("id") or t.get("task_id") or t.get("stage_id")
    deps[tid] = list(t.get("depends_on") or t.get("dependencies") or [])
visiting, visited, cycle = set(), set(), []


def visit(node, stack):
    if node in visiting:
        cycle.append(stack + [node])
        return
    if node in visited:
        return
    visiting.add(node)
    for dep in deps.get(node, []):
        if dep in deps:
            visit(dep, stack + [node])
    visiting.discard(node)
    visited.add(node)


for node in deps:
    visit(node, [])
ck(
    "J03",
    G,
    not cycle,
    {"case": "the task dependency graph must stay acyclic", "cycles": cycle, "task_count": len(deps)},
    severity_if_fail="major",
)

ck(
    "J04",
    G,
    "\u539f21+MS01\u201308=29" in doc32 and "38/47" in doc32,
    {
        "case": "docs/32 must still state the additive denominators",
        "v1_statement_present": "\u539f21+MS01\u201308=29" in doc32,
        "v2_v3_statement_present": "38/47" in doc32,
    },
    severity_if_fail="minor",
)

# ------------------------------------------------------------------- write out
result = {
    "kind": "D0_B_REVIEW_DESIGN11_INDEPENDENT_RECHECK_CONTRACT_PROBES",
    "authority_sha": AUTHORITY_SHA,
    "launch_d0_payload_manifest_sha256": LAUNCH_D0_PAYLOAD_MANIFEST_SHA256,
    "checks": checks,
    "total": len(checks),
    "failed": sum(1 for c in checks if not c["passed"]),
    "product_actions": 0,
    "limits": "design/contract-level static probes only; no product runtime, no model, no media, no network, no sample materialisation",
}
(OUT / "contract-recheck-results.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({"checks": len(checks), "failed": result["failed"], "failed_ids": [c["id"] for c in checks if not c["passed"]]}))
sys.exit(0)
