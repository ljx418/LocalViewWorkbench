#!/usr/bin/env python3
"""D0-B-REVIEW metaschema + behavioural probe of the candidate multi-shot DTO schema.

Read-only. Uses the installed jsonschema library (allowed: JSON Schema metaschema checks).
Does not modify any contract file.
"""
import json
import os

from jsonschema import Draft202012Validator
from jsonschema.validators import validator_for

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))

with open(os.path.join(ROOT, "contracts/v1-multishot.schema.json"), encoding="utf-8") as fh:
    schema = json.load(fh)
with open(os.path.join(ROOT, "contracts/lvw.schema.json"), encoding="utf-8") as fh:
    core = json.load(fh)

validator_for(schema).check_schema(schema)
print("METASCHEMA_OK candidate contracts/v1-multishot.schema.json")
Draft202012Validator.check_schema(core)
print("METASCHEMA_OK canonical contracts/lvw.schema.json")

defs = schema["$defs"]


def validator_for_def(name):
    sub = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$defs": defs, "$ref": "#/$defs/%s" % name}
    return Draft202012Validator(sub)


def run(name, instance, label):
    errs = sorted(validator_for_def(name).iter_errors(instance), key=lambda e: list(e.path))
    print("%-42s errors=%d %s" % (label, len(errs), (errs[0].message[:110] if errs else "")))
    return len(errs)


frame = {"index": 0, "source_pts": 1, "time_base_num": 1, "time_base_den": 1, "sha256": "a" * 64}
base = {"frame_refs": [frame], "characters": [],
        "scene": {"description": "x", "evidence_frame_indices": [0]}, "actions": [], "unknowns": []}

run("ShotEvidence", base, "ShotEvidence_valid")
run("ShotEvidence", dict(base, extra=1), "ShotEvidence_extra_property")
run("ShotEvidence", dict(base, frame_refs=[frame, frame]), "ShotEvidence_duplicate_frame")
run("ShotEvidence", dict(base, frame_refs=[dict(frame, index=4)]), "ShotEvidence_frame_index_gt3")
run("ShotEvidence", dict(base, characters=[{"local_actor_id": "a1", "visible_appearance": "x",
                                            "evidence_frame_indices": [7]}]),
    "ShotEvidence_char_frame_index_oob")
run("ShotEvidence", dict(base, actions=[{"actor_ref": "a1", "description": "walks",
                                          "domain": "observation", "evidence_frame_indices": [0, 0]}]),
    "ShotEvidence_action_dup_frame_indices")
run("ShotEvidence", dict(base, actions=[{"actor_ref": "a1", "description": "walks",
                                          "domain": "guess", "evidence_frame_indices": [0]}]),
    "ShotEvidence_action_bad_domain")
run("ShotEvidence", dict(base, scene={"description": "x"}), "ShotEvidence_scene_missing_evidence")
run("Character", {"local_actor_id": "a1", "visible_appearance": "x", "evidence_frame_indices": [0]},
    "Character_valid")
run("Character", {"local_actor_id": "a1", "visible_appearance": "x"}, "Character_missing_evidence")
run("BatchAnalyzeRequest", {"shot_ids": ["s1"], "scene_revision_ids": ["r1"], "mode": "realistic",
                            "config_profile": "p"}, "BatchAnalyzeRequest_valid")
run("BatchAnalyzeRequest", {"shot_ids": ["s1", "s2"], "scene_revision_ids": ["r1"], "mode": "realistic",
                            "config_profile": "p"}, "BatchAnalyzeRequest_length_mismatch(semantic)")
run("BatchAnalyzeRequest", {"shot_ids": [str(i) for i in range(13)], "scene_revision_ids": ["r1"],
                            "mode": "realistic", "config_profile": "p"}, "BatchAnalyzeRequest_13_shots")
run("BatchAnalyzeRequest", {"shot_ids": ["s1"], "scene_revision_ids": ["r1"], "mode": "unknown_mode",
                            "config_profile": "p"}, "BatchAnalyzeRequest_bad_mode")
run("BatchChildrenResponse", {"parent_job_id": "p", "total": 2, "children": []},
    "BatchChildrenResponse_total2_children0")
run("BatchChildrenResponse", {"parent_job_id": "p", "total": 13, "children": []},
    "BatchChildrenResponse_total13")
run("SceneRevision", {"id": "i", "media_ref_id": "m", "source_sha256": "a" * 64, "version": 1,
                      "origin_pts": 0, "time_base_num": 1, "time_base_den": 1000, "start_pts": 0,
                      "end_pts": 10, "origin": "detected", "etag": "e"}, "SceneRevision_valid")
run("SceneRevision", {"id": "i", "media_ref_id": "m", "source_sha256": "a" * 64, "version": 1,
                      "origin_pts": 0, "time_base_num": 1, "time_base_den": 1000, "start_pts": 10,
                      "end_pts": 10, "origin": "detected", "etag": "e"}, "SceneRevision_zero_length(semantic)")
run("AnalysisBinding", {"shot_id": "s", "scene_revision_id": "r", "scene_revision_hash": "b" * 64,
                        "media_ref_id": "m", "media_sha256": "a" * 64, "config_hash": "c" * 64,
                        "attempt_id": "t", "cancel_epoch": 0}, "AnalysisBinding_valid")
run("AnalysisBinding", {"shot_id": "s", "scene_revision_id": "r", "scene_revision_hash": "B" * 64,
                        "media_ref_id": "m", "media_sha256": "a" * 64, "config_hash": "c" * 64,
                        "attempt_id": "t", "cancel_epoch": 0}, "AnalysisBinding_uppercase_hash")
print("NOTE schema_cannot_check: end_pts>start_pts, equal-length id arrays, cross-shot actor refs, "
      "frame-in-scene, duplicate-frame hashes, parent total==len(children), deadline -> x-semantic-invariants "
      "or owner code only")
