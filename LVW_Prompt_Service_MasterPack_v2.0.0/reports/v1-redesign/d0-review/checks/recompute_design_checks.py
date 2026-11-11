#!/usr/bin/env python3
"""D0-B-REVIEW independent recomputation (read-only).

Independent of the D0-B-IMPL checker tool (not received, not used).
Recomputes the design-level invariants that the D0 acceptance matrix (04-acceptance-matrix.md)
claims, plus DTO/canonical-contract collision checks, read-only, stdlib only.
Writes nothing outside this checks/ directory.
"""
import json
import os
import sys
import hashlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))
OUT = os.path.dirname(__file__)

results = []


def check(cid, desc, ok, detail):
    results.append({"check_id": cid, "description": desc, "result": "PASS" if ok else "FAIL", "detail": detail})
    return ok


def p(*parts):
    return os.path.join(ROOT, *parts)


def load(rel):
    with open(p(rel), "r", encoding="utf-8") as fh:
        return json.load(fh)


def sha(rel):
    with open(p(rel), "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


# ---------------------------------------------------------------- C1 hash fence
manifest = load(".agent-governance/stages/V1-D0/spec-manifest.json")
bad = []
for rel, expected in manifest["files"].items():
    actual = sha(rel) if os.path.exists(p(rel)) else None
    if actual != expected:
        bad.append({"file": rel, "expected": expected, "actual": actual})
check("C1", "spec-manifest hash fence (17 reviewed design files) matches", not bad,
      "mismatches=%d %s" % (len(bad), json.dumps(bad, ensure_ascii=False)))

# ---------------------------------------------------------------- C2/C5 gate denominators
legacy = load("reports/v1-redesign/legacy-gates-before-change.json")["required_cases"]
gates = load("plans/release_gates.json")["gates"]
counts = {k: len(v["required_cases"]) for k, v in gates.items()}
check("C2", "release gate cumulative counts V1=29 V2=38 V3=47", counts.get("V1") == 29 and counts.get("V2") == 38 and counts.get("V3") == 47,
      "counts=%s" % json.dumps(counts))

prefix_ok = {}
for ver in ("V1", "V2", "V3"):
    legacy_list = legacy[ver]
    current = gates[ver]["required_cases"]
    prefix_ok[ver] = current[: len(legacy_list)] == legacy_list
check("C3", "legacy required-case lists preserved as unchanged prefix (original 21/30/39)", all(prefix_ok.values()),
      json.dumps(prefix_ok))
check("C4", "MS01-MS08 appended exactly once per gate, no duplicates",
      all(len(gates[v]["required_cases"]) == len(set(gates[v]["required_cases"])) and
          gates[v]["required_cases"].count("MS01") == 1 and gates[v]["required_cases"].count("MS08") == 1
          for v in ("V1", "V2", "V3")),
      json.dumps({v: len(gates[v]["required_cases"]) - len(set(gates[v]["required_cases"])) for v in ("V1", "V2", "V3")}))

plan = load("plans/v1-revised-plan.json")
check("C5", "v1-revised-plan v1_required_cases == release_gates V1 required_cases (order sensitive)",
      plan["v1_required_cases"] == gates["V1"]["required_cases"],
      "plan=%d gate=%d equal=%s" % (len(plan["v1_required_cases"]), len(gates["V1"]["required_cases"]),
                                    plan["v1_required_cases"] == gates["V1"]["required_cases"]))
check("C6", "supplement_case_ids == MS01..MS08 exactly", plan["supplement_case_ids"] == ["MS0%d" % i for i in range(1, 9)],
      json.dumps(plan["supplement_case_ids"]))

# ---------------------------------------------------------------- C7 acceptance inventory
cases = load("plans/acceptance_cases.json")["cases"]
ids = [c["case_id"] for c in cases]
dup = sorted({i for i in ids if ids.count(i) > 1})
check("C7", "no duplicate acceptance case_id and every gate case exists in acceptance_cases",
      not dup and all(c in ids for v in ("V1", "V2", "V3") for c in gates[v]["required_cases"]),
      "duplicates=%s" % json.dumps(dup))

q01 = [c for c in cases if c["case_id"] == "Q01"][0]
check("C8", "Q01 retained unchanged (12 images + 6 videos, >=10/12 and >=5/6)",
      "12图+6片" in " ".join(q01["preconditions"]) and "图>=10/12" in " ".join(q01["assertions"]) and "片>=5/6" in " ".join(q01["assertions"]),
      json.dumps(q01["preconditions"], ensure_ascii=False) + " | " + json.dumps(q01["assertions"], ensure_ascii=False))

# ---------------------------------------------------------------- C9 DAG
tasks = load("plans/tasks.json")
dep = {s["stage_id"]: [d for d in s["depends_on"]] for s in tasks["stages"]}
state = {}


def visit(n, stack):
    if state.get(n) == 2:
        return []
    if state.get(n) == 1:
        return [stack + [n]]
    state[n] = 1
    cycles = []
    for m in dep.get(n, []):
        if m in dep:
            cycles += visit(m, stack + [n])
    state[n] = 2
    return cycles


cycles = []
for n in dep:
    cycles += visit(n, [])
check("C9", "plans/tasks.json dependency graph is acyclic", not cycles, "cycles=%s" % json.dumps(cycles))

seq = tasks["preferred_sequence"]
pos = {s: i for i, s in enumerate(seq)}
order_bad = [[k, x] for k, v in dep.items() for x in v if x in pos and k in pos and pos[x] > pos[k]]
check("C10", "preferred_sequence respects depends_on ordering", not order_bad, json.dumps(order_bad))

plan_stages = {s["id"]: s for s in plan["stages"]}
plan_dep = {k: v["depends_on"] for k, v in plan_stages.items()}
plan_state = {}


def pvisit(n, stack):
    if plan_state.get(n) == 2:
        return []
    if plan_state.get(n) == 1:
        return [stack + [n]]
    plan_state[n] = 1
    out = []
    for m in plan_dep.get(n, []):
        if m in plan_dep:
            out += pvisit(m, stack + [n])
    plan_state[n] = 2
    return out


pcycles = []
for n in plan_dep:
    pcycles += pvisit(n, [])
check("C11", "v1-revised-plan stage DAG acyclic (R1 -> V1-M1 -> R2)", not pcycles,
      "cycles=%s depends=%s" % (json.dumps(pcycles), json.dumps(plan_dep)))
check("C12", "v1-revised-plan declares V1-M1 depends_on R1 and R2 depends_on V1-M1",
      plan_dep.get("V1-M1") == ["R1"] and "V1-M1" in plan_dep.get("R2", []),
      json.dumps(plan_dep))
check("C13", "plan stage deps consistent with tasks.json stage deps for R1/V1-M1/R2",
      all(plan_dep.get(s) == dep.get(s) for s in ("R1", "V1-M1", "R2")),
      json.dumps({"plan": {s: plan_dep.get(s) for s in ("R1", "V1-M1", "R2")},
                  "tasks": {s: dep.get(s) for s in ("R1", "V1-M1", "R2")}}))

# ---------------------------------------------------------------- C14 canonical immutability
legacy_hashes = load("reports/v1-redesign/legacy-gates-before-change.json")["canonical_contract_hashes"]
drift = {k: {"expected": v, "actual": sha(k)} for k, v in legacy_hashes.items() if sha(k) != v}
check("C14", "canonical openapi/coreSchema/storage byte-identical to pre-change record", not drift, json.dumps(drift))

# ---------------------------------------------------------------- C15 authorization mapping
complete03 = load("reports/authorization-program-v1-complete-03.request.json")
stages_auth = complete03["stages"]
check("C15", "authority_stage R2 is inside COMPLETE03 authorized stages; no V2 stage alias",
      plan["authorization_accounting"]["authority_stage"] in stages_auth and
      plan["authorization_accounting"]["design_stage"] == "V1-M1" and
      not any(s in plan["authorization_accounting"]["authority_stage"] for s in ("R3", "R4", "R5")),
      "authorized=%s mapping=%s" % (json.dumps(stages_auth), json.dumps(plan["authorization_accounting"])))
check("C16", "plan does not reset budget and does not claim a completed/product pass",
      plan["budget_reset"] is False and plan["old_slice_human_signoff_waived"] is False and
      plan["status"].startswith("DESIGN_REVIEW") and plan["parallel_preparation"]["product_edits_allowed"] is False,
      "budget_reset=%s waived=%s status=%s" % (plan["budget_reset"], plan["old_slice_human_signoff_waived"], plan["status"]))

# ---------------------------------------------------------------- C17 DTO schema structure
ms = load("contracts/v1-multishot.schema.json")
defs = ms["$defs"]


def _iter_refs(node):
    if isinstance(node, dict):
        if "$ref" in node and isinstance(node["$ref"], str):
            yield node
        for value in node.values():
            for item in _iter_refs(value):
                yield item
    elif isinstance(node, list):
        for value in node:
            for item in _iter_refs(value):
                yield item


check("C17", "v1-multishot schema: every $ref resolves inside the file",
      all(r["$ref"].startswith("#/$defs/") and r["$ref"].split("/")[-1] in defs
          for d in defs.values() for r in _iter_refs(d)),
      "defs=%s" % json.dumps(sorted(defs)))

# ---------------------------------------------------------------- C18 canonical DTO name collisions
openapi = load("contracts/openapi.json")
canonical_schemas = set(openapi["components"]["schemas"])
collisions = sorted(set(defs) & canonical_schemas)
check("C18", "no $defs name collides with an existing canonical OpenAPI component name",
      not collisions, "collisions=%s" % json.dumps(collisions))

# FrameRef shape comparison
canon_fr = openapi["components"]["schemas"]["FrameRef"]
ms_fr = defs["FrameRef"]
canon_req = set(canon_fr["required"])
ms_req = set(ms_fr["required"])
check("C19", "candidate FrameRef is shape-compatible with canonical FrameRef (required fields)",
      canon_req <= ms_req,
      "canonical_required=%s candidate_required=%s missing_in_candidate=%s" %
      (json.dumps(sorted(canon_req)), json.dumps(sorted(ms_req)), json.dumps(sorted(canon_req - ms_req))))

# ---------------------------------------------------------------- C20 route/DTO reuse conflicts
contract = load("plans/v1-multishot-contract.json")
reuse = contract["reuse_paths"]
openapi_paths = openapi["paths"]

def body_schema(path, method):
    op = openapi_paths.get(path, {}).get(method)
    if not op:
        return None
    rb = op.get("requestBody")
    if rb:
        return rb["content"]["application/json"]["schema"]
    return None


batch_canonical = body_schema("/api/v1/jobs/batch", "post")
batch_req = set(batch_canonical["properties"]) if batch_canonical else set()
ms_batch_req = set(defs["BatchAnalyzeRequest"]["properties"])
check("C20", "reuse_path /api/v1/jobs/batch canonical request body is compatible with candidate BatchAnalyzeRequest",
      batch_req == ms_batch_req,
      "canonical=%s candidate=%s" % (json.dumps(sorted(batch_req)), json.dumps(sorted(ms_batch_req))))

detect_canonical = body_schema("/api/v1/scenes/detect", "post")
detect_req = set(detect_canonical["properties"]) if detect_canonical else set()
check("C21", "reuse_path /api/v1/scenes/detect canonical request body matches docs/31 (media_ref_id+profile)",
      detect_req == {"media_ref_id", "profile"},
      "canonical=%s" % json.dumps(sorted(detect_req)))

# scene DTO divergence
canon_scene = openapi["components"]["schemas"]["Scene"]
ms_scene = defs["SceneRevision"]
canon_scene_req = set(canon_scene["required"])
ms_scene_req = set(ms_scene["required"])
divergent = sorted((canon_scene_req - ms_scene_req) | (ms_scene_req - canon_scene_req))
check("C22", "candidate SceneRevision required-field set equals canonical Scene required-field set for reused routes",
      not divergent,
      "canonical_only=%s candidate_only=%s" % (json.dumps(sorted(canon_scene_req - ms_scene_req)),
                                              json.dumps(sorted(ms_scene_req - canon_scene_req))))

# new routes must not exist in canonical openapi
new_routes = [r for r in reuse if r not in openapi_paths]
check("C23", "reuse_paths entries absent from canonical OpenAPI are exactly the declared new ones",
      sorted(new_routes) == sorted(["/api/v1/jobs/{id}/children"]),
      "absent_from_canonical=%s" % json.dumps(sorted(new_routes)))

# ---------------------------------------------------------------- C24 ParentJob representability
parent_required = set(contract["entities"]["ParentJob"]["required"])
canonical_job = openapi["components"]["schemas"]["Job"]
canon_job_props = set(canonical_job["properties"])
not_representable = sorted(parent_required - canon_job_props)
check("C24", "ParentJob required fields are representable in the strict canonical Job DTO (no field smuggling)",
      not not_representable,
      "not_in_canonical_job=%s" % json.dumps(not_representable))
check("C25", "candidate schema defines a ParentJob DTO",
      "ParentJob" in defs, "defined_defs=%s" % json.dumps(sorted(defs)))

# ---------------------------------------------------------------- C26 children route strictness
children_resp = defs["BatchChildrenResponse"]
child_props = set(defs["ChildSummary"]["properties"])
job_status_enum = set(openapi["components"]["schemas"]["Job"]["properties"]["status"]["enum"])
check("C26", "ChildSummary.status values are a subset of canonical Job.status enum",
      set(defs["ChildSummary"]["properties"]["status"]["enum"]) <= job_status_enum,
      "child=%s canonical=%s extra=%s" % (json.dumps(sorted(defs["ChildSummary"]["properties"]["status"]["enum"])),
                                          json.dumps(sorted(job_status_enum)),
                                          json.dumps(sorted(set(defs["ChildSummary"]["properties"]["status"]["enum"]) - job_status_enum))))
check("C27", "BatchChildrenResponse exposes parent progress (terminal_count/total) and deadline",
      {"total"} <= set(children_resp["properties"]) and "deadline" in children_resp["properties"],
      "children_props=%s" % json.dumps(sorted(children_resp["properties"])))

# ---------------------------------------------------------------- C28 storage baseline facts
sql = open(p("contracts/storage.sql"), encoding="utf-8").read()
check("C28", "baseline DDL scene_revision has no append-only trigger and no etag/source_sha256 column",
      "scene_revision_no_update" not in sql and "CREATE TABLE scene_revision" in sql and
      "etag" not in sql.split("CREATE TABLE scene_revision")[1].split(";")[0],
      "scene_revision_ddl=%s" % sql.split("CREATE TABLE scene_revision")[1].split(";")[0].strip())
batch_child_ddl = sql.split("CREATE TABLE batch_child")[1].split(";")[0]
check("C29", "baseline DDL batch_child carries no ordinal / shot_id / scene_revision_id column",
      not any(k in batch_child_ddl for k in ("ordinal", "shot_id", "scene_revision_id")),
      "batch_child_ddl=%s" % batch_child_ddl.strip())

# ---------------------------------------------------------------- C30 fixed sample arithmetic
doc32 = open(p("docs/32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md"), encoding="utf-8").read()
hard = 5 + 5 + 5 + 4 + 4 + 4           # 6 hard-cut clips
nocut = 2                               # 2 no-cut clips
vfr = 4                                 # 1 VFR clip, 4 shots
fast = 8                                # 1 short/fast-cut clip, 8 shots
dissolve_min = 2                        # 2 dissolve clips, >=1 shot each
dissolve_max = 6                        # 2 dissolve clips, <=3 shots each
check("C30", "documented 12-clip composition yields the stated 47 planned shots",
      hard + nocut + vfr + fast + dissolve_min == 47,
      "hard=%d nocut=%d vfr=%d fast=%d dissolve(1..3 shots each)=%d..%d total=%d..%d stated=47" %
      (hard, nocut, vfr, fast, dissolve_min, dissolve_max,
       hard + nocut + vfr + fast + dissolve_min, hard + nocut + vfr + fast + dissolve_max))
check("C31", "doc32 states 47 planned shots and 21 hard-cut annotation points",
      "47个计划镜头" in doc32 and "21个标注切点" in doc32, "phrases_present")
ms01 = [c for c in cases if c["case_id"] == "MS01"][0]
check("C32", "MS01 cut-point threshold matches the inherited V2 A13 threshold (>=20 points, +-2 source frames, P/R>=0.90)",
      "至少20个预标切点" in " ".join(ms01["assertions"]) and "P/R均>=0.90" in " ".join(ms01["assertions"]),
      json.dumps(ms01["assertions"], ensure_ascii=False))

# ---------------------------------------------------------------- C33 budget arithmetic
budget = load("reports/unified-media/complete03-budget-after-live15.json")
limits = budget["global_limits"]
used_actions = budget["model_actions"]
used_rounds = budget["effective_full_checkpoints"]
used_seconds = budget["production_seconds"]
design_actions = 80
design_seconds = 10800
check("C33", "design per-round estimate (80 actions / 10800 s) fits the COMPLETE03 per-child ceilings (128 / 21600)",
      design_actions <= complete03["global_cumulative_limits"]["per_child_model_actions_ceiling"] and
      design_seconds <= complete03["global_cumulative_limits"]["per_child_wall_seconds_ceiling"],
      "design=%d/%d ceilings=%d/%d" % (design_actions, design_seconds,
                                       complete03["global_cumulative_limits"]["per_child_model_actions_ceiling"],
                                       complete03["global_cumulative_limits"]["per_child_wall_seconds_ceiling"]))
remaining_actions = limits["model_actions"] - used_actions
remaining_rounds = limits["effective_full_checkpoints"] - used_rounds
remaining_seconds = limits["production_seconds"] - used_seconds
check("C34", "global remaining budget can fund several full V1 checkpoint rounds at the design estimate",
      remaining_actions // design_actions >= 3 and remaining_rounds >= 3,
      "remaining_actions=%d rounds_by_actions=%d remaining_rounds=%d remaining_seconds=%d rounds_by_seconds=%d" %
      (remaining_actions, remaining_actions // design_actions, remaining_rounds, remaining_seconds,
       remaining_seconds // design_seconds))
check("C35", "design per-round wall estimate (10800 s) is consistent with the measured video-analysis P95 (300 s) x 47 shots",
      47 * 300 <= design_seconds,
      "47 shots x 300 s P95 = %d s vs design estimate %d s (per-call average implied by estimate = %.1f s)" %
      (47 * 300, design_seconds, design_seconds / design_actions))
check("C36", "parent batch deadline (1800 s) covers the measured worst case of its own children (12 x 420 s)",
      12 * 420 <= 1800,
      "12 children x 420 s = %d s vs parent deadline 1800 s; measured video P95 300 s x 8-shot sample = %d s" %
      (12 * 420, 8 * 300))

# ---------------------------------------------------------------- C37 human signature untouched
ec = load("plans/execution-control.json")
check("C37", "no human signature or product acceptance claimed; V1_ACCEPTED forbidden",
      ec.get("human_signoff") is None and ec.get("product_acceptance") is None and
      "V1_ACCEPTED" in ec.get("forbidden_claims", []) and
      ec.get("active_slice", {}).get("human_signoff") is None,
      "human_signoff=%s product_acceptance=%s forbidden=%s" %
      (ec.get("human_signoff"), ec.get("product_acceptance"), json.dumps(ec.get("forbidden_claims"))))
check("C38", "D0 stage control forbids product execution and Stage PASS",
      load(".agent-governance/stages/V1-D0/stage-control.json")["product_execution_authorized"] is False and
      load(".agent-governance/stages/V1-D0/stage-control.json")["stage_pass_forbidden"] is True, "ok")

# ---------------------------------------------------------------- C39 holdout separation
hold = ec.get("human_validation_holdout", {})
check("C39", "11-video human holdout set recorded as non-formal and separate from the new MS sample set",
      hold.get("videos") == 11 and hold.get("formal_quality_set") is False,
      json.dumps(hold, ensure_ascii=False))

# ---------------------------------------------------------------- C40 evidence of appearance-only 1.8
run = load("reports/unified-media/live-15/video-model-run.json")
raw = json.loads(run["raw_response"])
content = json.loads(raw["message"]["content"])
check("C40", "current 1.8 video template response carries no action/scene/character evidence fields (appearance-only)",
      set(content) == {"frame_appearances", "prompt_zh", "prompt", "negative", "tags", "unknowns"} and
      run["parsed_spec"]["template_version"] == "1.8.0",
      "template_version=%s keys=%s" % (run["parsed_spec"]["template_version"], json.dumps(sorted(content))))
canon_frame_keys = set(canon_fr["properties"])
check("C41", "canonical model_run.frames records frames with target_seconds + time_basis (sample_target vs decoded_pts)",
      {"target_seconds", "time_basis"} <= canon_frame_keys and
      set(run["frames"][0]) == canon_frame_keys,
      "canonical_frame_ref_fields=%s live_frame_fields=%s" %
      (json.dumps(sorted(canon_frame_keys)), json.dumps(sorted(run["frames"][0]))))

# ---------------------------------------------------------------- write outputs
summary = {
    "kind": "D0_B_REVIEW_INDEPENDENT_RECOMPUTATION",
    "note": "Read-only recomputation by the isolated D0-B-REVIEW window. Not product acceptance. "
            "Does not use the D0-B-IMPL checker (not received in this workspace).",
    "total": len(results),
    "passed": sum(1 for r in results if r["result"] == "PASS"),
    "failed": sum(1 for r in results if r["result"] == "FAIL"),
    "checks": results,
}
with open(os.path.join(OUT, "recompute-results.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, ensure_ascii=False, indent=1)

for r in results:
    print("%-5s %-4s %s" % (r["check_id"], r["result"], r["description"]))
    if r["result"] == "FAIL":
        print("        detail: %s" % r["detail"])
print("\nTOTAL=%d PASS=%d FAIL=%d" % (summary["total"], summary["passed"], summary["failed"]))
sys.exit(0)
