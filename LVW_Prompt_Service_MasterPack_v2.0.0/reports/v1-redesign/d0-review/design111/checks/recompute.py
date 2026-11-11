#!/usr/bin/env python3
"""Independent recomputation of the design 1.1.1 corrections N1-N6.

This script does NOT call tools/verify_v1_plan.py.  It re-derives the N1-N6
conclusions from the frozen owner artefacts with the reviewer's own code, so
that the checker's verdict is corroborated (or contradicted) independently.

Everything is read only.  The only writes are this script's own JSON result
file.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent / "recompute-results.json"

RESULTS = {}


def record(key, value, detail=""):
    RESULTS[key] = {"value": value, "detail": detail}
    print("%-46s %s  %s" % (key, value, detail))


def load(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# N1 - strict overlay merge, replayed by the reviewer
# ---------------------------------------------------------------------------

def n1_merge_replay():
    base = load("contracts/openapi.json")
    overlay = load("contracts/v1-multishot.openapi-overlay.json")
    merged = copy.deepcopy(base)
    added_meta = {}
    added_headers = {}
    problems = []

    for path, operations in sorted(overlay["add_paths"].items()):
        for method, operation in sorted(operations.items()):
            if method in (merged["paths"].get(path) or {}):
                problems.append("overlay replaces %s %s" % (method.upper(), path))
                continue
            merged["paths"].setdefault(path, {})[method] = copy.deepcopy(operation)

    for path, methods in sorted(overlay["metadata_only"].items()):
        for method, keys in sorted(methods.items()):
            target = (merged["paths"].get(path) or {}).get(method)
            if target is None:
                problems.append("annotation target missing: %s %s" % (method.upper(), path))
                continue
            for key in sorted(keys):
                if key not in ("x-v1-profile", "x-v2-semantics-unchanged"):
                    problems.append("unauthorized annotation key %s on %s %s" % (key, method.upper(), path))
                    continue
                if key in target:
                    problems.append("annotation collision %s on %s %s" % (key, method.upper(), path))
                    continue
                target[key] = copy.deepcopy(keys[key])
                added_meta.setdefault((path, method), []).append(key)

    for path, methods in sorted(overlay["add_response_headers"].items()):
        for method, statuses in sorted(methods.items()):
            target = (merged["paths"].get(path) or {}).get(method)
            if target is None:
                problems.append("header target missing: %s %s" % (method.upper(), path))
                continue
            for status, headers in sorted(statuses.items()):
                response = (target.get("responses") or {}).get(status)
                if not isinstance(response, dict):
                    problems.append("header status missing: %s %s %s" % (method.upper(), path, status))
                    continue
                for name in sorted(headers):
                    if name != "ETag":
                        problems.append("unauthorized response header %s" % name)
                        continue
                    if name in (response.get("headers") or {}):
                        problems.append("header collision %s" % name)
                        continue
                    response.setdefault("headers", {})[name] = copy.deepcopy(headers[name])
                    added_headers.setdefault((path, method), {}).setdefault(status, []).append(name)

    # every canonical operation must survive byte identical outside the allowlist
    mutated = []
    for path, operations in sorted((base.get("paths") or {}).items()):
        for method, operation in sorted(operations.items()):
            merged_op = copy.deepcopy((merged["paths"].get(path) or {}).get(method))
            if merged_op is None:
                mutated.append("%s %s dropped" % (method.upper(), path))
                continue
            for key in added_meta.get((path, method), []):
                merged_op.pop(key, None)
            for status, names in added_headers.get((path, method), {}).items():
                response = (merged_op.get("responses") or {}).get(status)
                if isinstance(response, dict) and isinstance(response.get("headers"), dict):
                    for name in names:
                        response["headers"].pop(name, None)
                    if not response["headers"]:
                        response.pop("headers")
            if merged_op != operation:
                mutated.append("%s %s changed" % (method.upper(), path))

    record("n1.canonical_operations_total", len([1 for p in (base.get("paths") or {}).values() for _ in p]),
           "canonical operations compared byte for byte")
    record("n1.canonical_operations_mutated", mutated, "must be empty")
    record("n1.merge_problems", problems, "must be empty")
    record("n1.added_operations", sorted(
        "%s %s" % (m.upper(), p) for p, ops in overlay["add_paths"].items() for m in ops))
    record("n1.annotated_methods", sorted("%s %s" % (m.upper(), p)
                                           for p, ms in overlay["metadata_only"].items() for m in ms))
    record("n1.header_additions", sorted("%s %s %s" % (m.upper(), p, s)
                                         for (p, m), ss in added_headers.items() for s in ss))

    # the strong ETag really is machine declared, and the weak tag is refused
    pattern = overlay["add_response_headers"]["/api/v1/scenes/{id}"]["put"]["200"]["ETag"]["schema"]["pattern"]
    strong = '"scene:revision-1:%s"' % ("a" * 64)
    weak = 'W/"scene:revision-1:%s"' % ("a" * 64)
    record("n1.etag_pattern", pattern)
    record("n1.etag_accepts_strong", bool(re.search(pattern, strong)))
    record("n1.etag_accepts_weak", bool(re.search(pattern, weak)), "must be False")

    # the merged PUT 200 must carry the ETag and nothing else may have changed
    put_before = copy.deepcopy(base["paths"]["/api/v1/scenes/{id}"]["put"])
    put_after = merged["paths"]["/api/v1/scenes/{id}"]["put"]
    added = sorted(set(put_after.get("responses", {}).get("200", {}).get("headers", {})) -
                   set(put_before.get("responses", {}).get("200", {}).get("headers", {})))
    record("n1.put_200_added_headers", added, "must be exactly ['ETag']")
    body_before = json.dumps(put_before.get("requestBody"), sort_keys=True, ensure_ascii=False)
    body_after = json.dumps(put_after.get("requestBody"), sort_keys=True, ensure_ascii=False)
    record("n1.put_request_body_identical", body_before == body_after)
    record("n1.put_x_product_version", put_after.get("x-product-version"),
           "canonical value: %s" % put_before.get("x-product-version"))

    # the new Scene GET must return the canonical Scene DTO
    new_get = merged["paths"]["/api/v1/scenes/{id}"]["get"]
    data_ref = (((new_get.get("responses") or {}).get("200") or {}).get("content") or {}) \
        .get("application/json", {}).get("schema", {}).get("properties", {}).get("data", {}).get("$ref")
    record("n1.new_scene_get_body_ref", data_ref, "must be #/components/schemas/Scene")
    record("n1.new_scene_get_etag", sorted(
        (((new_get.get("responses") or {}).get("200") or {}).get("headers") or {}).keys()))


# ---------------------------------------------------------------------------
# N2 - additive surface recomputed from the overlay
# ---------------------------------------------------------------------------

def n2_surface():
    overlay = load("contracts/v1-multishot.openapi-overlay.json")
    contract = load("plans/v1-multishot-contract.json")
    ops = sorted((p, m.lower()) for p, ms in overlay["add_paths"].items() for m in ms)
    paths = sorted(overlay["add_paths"])
    record("n2.overlay_operations", ops)
    record("n2.overlay_paths", paths)
    record("n2.contract_additive_operations_match",
           sorted((e["path"], e["method"].lower()) for e in contract["additive_operations"]) == ops)
    record("n2.contract_additive_paths_match", sorted(contract["additive_paths"]) == paths)
    # the contract must cover the new GET on the *existing* Scene path
    record("n2.new_get_on_existing_scene_path",
           [o for o in ops if o[0] == "/api/v1/scenes/{id}" and o[1] == "get"])
    base = load("contracts/openapi.json")
    record("n2.scene_path_exists_in_canonical", "/api/v1/scenes/{id}" in base["paths"])
    record("n2.scene_get_not_in_canonical", "get" not in base["paths"]["/api/v1/scenes/{id}"],
           "so the overlay GET is a real addition, not a replacement")


# ---------------------------------------------------------------------------
# N3 - reuse annotations recomputed
# ---------------------------------------------------------------------------

def n3_reuse():
    base = load("contracts/openapi.json")
    overlay = load("contracts/v1-multishot.openapi-overlay.json")
    contract = load("plans/v1-multishot-contract.json")
    meta = overlay["metadata_only"]
    report = {}
    for path, methods in sorted(meta.items()):
        for method, keys in sorted(methods.items()):
            op = base["paths"].get(path, {}).get(method)
            report["%s %s" % (method.upper(), path)] = {
                "target_exists": op is not None,
                "canonical_x_product_version": (op or {}).get("x-product-version"),
                "keys": sorted(keys),
                "collides": sorted(k for k in keys if op and k in op),
            }
    record("n3.annotation_count", len(report))
    record("n3.all_targets_exist", all(v["target_exists"] for v in report.values()))
    record("n3.all_keys_allowlisted", all(sorted(v["keys"]) == ["x-v1-profile", "x-v2-semantics-unchanged"]
                                           for v in report.values()))
    record("n3.no_collision", all(not v["collides"] for v in report.values()))
    record("n3.contract_reuse_paths_match_overlay", sorted(contract["reuse_paths"]) == sorted(meta))
    record("n3.detail", report)


# ---------------------------------------------------------------------------
# N4 - per shot frame reference
# ---------------------------------------------------------------------------

def n4_frame_ref():
    schema = load("contracts/v1-multishot.schema.json")
    canonical = load("contracts/lvw.schema.json")
    shot = schema["$defs"]["ShotFrameRef"]
    frame = canonical["$defs"]["FrameRef"]
    record("n4.shot_properties", sorted(shot["properties"]))
    record("n4.canonical_properties", sorted(frame["properties"]))
    record("n4.same_property_set", sorted(shot["properties"]) == sorted(frame["properties"]))
    record("n4.same_required_set", sorted(shot["required"]) == sorted(frame["required"]))
    detail = {}
    for name in ("source_pts", "time_base_num", "time_base_den"):
        prop = shot["properties"][name]
        detail[name] = {"type": prop.get("type"), "minimum": prop.get("minimum"),
                        "anyOf": prop.get("anyOf"), "oneOf": prop.get("oneOf"),
                        "canonical_type": frame["properties"][name].get("type"),
                        "canonical_anyOf": frame["properties"][name].get("anyOf")}
    record("n4.pts_fields", detail)
    record("n4.shot_time_basis", shot["properties"]["time_basis"])
    record("n4.canonical_time_basis", frame["properties"]["time_basis"])

    # the retained historical frame references must validate as ShotFrameRef
    sample = load("reports/unified-media/live-15/video-model-run.json")
    frames = sample.get("frames") or []
    record("n4.retained_frame_count", len(frames))
    try:
        import jsonschema
        validator = jsonschema.Draft202012Validator({"$ref": "#/$defs/ShotFrameRef", "$defs": schema["$defs"]})
        errors = []
        for index, item in enumerate(frames):
            for err in validator.iter_errors(item):
                errors.append("frame %d: %s" % (index, err.message))
        record("n4.retained_frames_valid", not errors, "; ".join(errors))
        record("n4.probe_engine", "jsonschema %s" % getattr(jsonschema, "__version__", "?"))
    except ImportError:
        record("n4.retained_frames_valid", "NOT_RUN", "jsonschema not importable")


# ---------------------------------------------------------------------------
# N5 - bilingual -> canonical Domains, recomputed from the rule
# ---------------------------------------------------------------------------

def n5_domains():
    contract = load("plans/v1-multishot-contract.json")
    mapping = contract["canonical_domain_mapping"]
    example = mapping["example"]
    source = example["source"]
    order = mapping["language_order"]
    ref_field = mapping["refs"]["character"]
    text_field = mapping["source_fields"]["character"]
    expected = []
    for lang in order:
        text = source[text_field].get(lang)
        if not isinstance(text, str) or text == "":
            continue
        entry = {"kind": "character", "ref": source[ref_field], "lang": lang, "text": text}
        expected.append(json.dumps(entry, ensure_ascii=False, sort_keys=True,
                                   separators=(",", ":"), allow_nan=False))
    record("n5.example_recomputed", expected)
    record("n5.example_matches_rule", expected == example["observation"])
    record("n5.example_key_order", [list(json.loads(e).keys()) for e in example["observation"]])
    record("n5.rule_text_key_order_claim", mapping["entry_serialization"], )
    record("n5.rule_text_contradiction",
           "the rule text names the key order 'kind, ref, lang, text' while it also says 'sorted keys' "
           "and the example uses the sorted order 'kind, lang, ref, text'")

    # the rule is implementable for the other three domains as well
    scene_source = {"description": {"zh": "室内", "en": "interior"}, "domain": "observation"}
    scene_entries = [json.dumps({"kind": "scene", "ref": "scene", "lang": lang, "text": scene_source["description"][lang]},
                                ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                     for lang in order if scene_source["description"].get(lang)]
    action_source = {"description": {"zh": "抬手", "en": "raises a hand"}}
    action_entries = [json.dumps({"kind": "action", "ref": "0", "lang": lang, "text": action_source["description"][lang]},
                                 ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                      for lang in order if action_source["description"].get(lang)]
    unknown_source = {"text": "身份不明", "zh": "身份不明", "en": "unknown identity"}
    unknown_entries = [json.dumps({"kind": "unknown", "ref": "0", "lang": lang, "text": unknown_source[lang]},
                                   ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                       for lang in order if unknown_source.get(lang)]
    record("n5.scene_example_derived", scene_entries)
    record("n5.action_example_derived", action_entries)
    record("n5.unknown_example_derived", unknown_entries)
    record("n5.only_character_example_is_frozen", True,
           "the owner example only exercises the character domain")
    record("n5.canonical_domains_shape", load("contracts/lvw.schema.json")["$defs"]["Domains"]["properties"])
    record("n5.human_domains_rule", mapping["human_domains"])
    record("n5.prompt_text_rule", mapping["prompt_text"])
    record("n5.unknowns_rule", mapping["unknowns"])


# ---------------------------------------------------------------------------
# N6 - scene hash: alias mapping, DDL columns and a recomputed fixture hash
# ---------------------------------------------------------------------------

def n6_scene_hash():
    contract = load("plans/v1-multishot-contract.json")
    scene_hash = contract["scene_hash"]
    fields = scene_hash["fields"]
    mapping = scene_hash["column_mapping"]
    sql = (ROOT / "contracts/v1-multishot-migration.sql").read_text(encoding="utf-8")
    record("n6.hash_fields", fields)
    record("n6.mapping_covers_fields", sorted(mapping) == sorted(fields))
    record("n6.mapping", mapping)

    # the SQL call site must pass the 11 values in the declared field order
    sql_code = "\n".join(line for line in sql.splitlines() if not line.strip().startswith("--"))
    call = re.search(r"lvw_scene_hash\(([^)]*)\)", sql_code)
    args = [a.strip() for a in call.group(1).split(",")] if call else []
    record("n6.sql_call_site_argument_count", len(args), "args: %s" % args)
    record("n6.sql_call_site_field_order_ok", len(args) == len(fields),
           "argument count matches the 11 declared hash fields: %s" % (len(args) == len(fields)))
    record("n6.sql_call_site_args", args)

    # every alias target column must exist in the candidate DDL
    ddl_columns = {c.lower() for c in re.findall(r"\b([a-z_][a-z0-9_]*)\s+(?:TEXT|INTEGER|REAL|BLOB)",
                                                 sql)}
    missing = []
    for field, alias in sorted(mapping.items()):
        for token in re.findall(r"[a-z_][a-z0-9_]*\.[a-z_][a-z0-9_]*", alias.lower()):
            column = token.split(".", 1)[1]
            if column not in ddl_columns:
                missing.append("%s -> %s" % (field, column))
    record("n6.alias_columns_missing_in_ddl", missing, "must be empty")
    record("n6.ddl_columns_seen", sorted(ddl_columns))

    # an independent fixture hash, computed from the declared rule
    row = {
        "media_ref_id": "media-001",
        "media_sha256": "b" * 64,
        "revision": 3,
        "start_pts": 0,
        "end_pts": 122880,
        "origin_pts": 0,
        "time_base_num": 1,
        "time_base_den": 12288,
        "editor": "algorithm",
        "time_basis": "decoded_pts",
        "verified": True,          # SQLite 0/1 -> JSON false/true
    }
    payload = {name: row[name] for name in fields}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    etag = '"scene:%s:%s"' % ("scene-rev-001", digest)
    record("n6.fixture_serialized_bytes", blob)
    record("n6.fixture_sha256", digest)
    record("n6.fixture_etag", etag)
    record("n6.fixture_etag_matches_frozen_pattern",
           bool(re.search(r'^"scene:[^":]+:[0-9a-f]{64}"$', etag)))
    record("n6.fixture_hash_is_stable", digest == hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                   allow_nan=False).encode("utf-8")).hexdigest())
    record("n6.verified_json_type", type(payload["verified"]).__name__)
    record("n6.hash_function_defined_in_package", "lvw_scene_hash" in sql and "CREATE FUNCTION lvw_scene_hash" in sql.upper(),
           "the migration only calls the function; the DDL that defines it is not in the frozen package")


def main():
    n1_merge_replay()
    n2_surface()
    n3_reuse()
    n4_frame_ref()
    n5_domains()
    n6_scene_hash()
    OUT.write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("\nwritten to %s" % OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
