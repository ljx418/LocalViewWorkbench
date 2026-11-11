#!/usr/bin/env python3
"""Negative tests for tools/verify_v1_plan.py (design 1.1).

Every test builds a *synthetic* package tree under pytest's tmp_path and mutates
only that copy. The canonical plans, packets and manifests in this repository
are never written to.

The synthetic tree mirrors the *actual* parent spec layout: the authority spec
manifest does not list the D0 stage control, and the D0 stage packet is fenced
by its own payload manifest instead.

Run: python3 -B -m pytest tools/test_verify_v1_plan.py -q
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "tools" / "verify_v1_plan.py"
sys.path.insert(0, str(ROOT / "tools"))

import verify_v1_plan as checker  # noqa: E402

LEGACY_V1 = (
    ["A%02d" % i for i in range(1, 13)]
    + ["F%02d" % i for i in range(1, 6)]
    + ["Q01"]
    + ["X%02d" % i for i in range(1, 4)]
)
LEGACY_V2_EXTRA = ["A%02d" % i for i in range(13, 18)] + ["F06"] + ["X%02d" % i for i in range(4, 7)]
LEGACY_V3_EXTRA = ["A%02d" % i for i in range(18, 23)] + ["F07"] + ["X%02d" % i for i in range(7, 10)]
MS = checker.MS_CASE_IDS

GATES_V1 = LEGACY_V1 + MS
GATES_V2 = LEGACY_V1 + LEGACY_V2_EXTRA + MS
GATES_V3 = LEGACY_V1 + LEGACY_V2_EXTRA + LEGACY_V3_EXTRA + MS

APPROVAL_REL = "reports/v1-redesign/product-change-approval.json"
BASELINE_REL = "reports/v1-redesign/legacy-gates-before-change.json"
ADJUDICATION_REL = "reports/v1-redesign/design11-adjudication.json"
ADJUDICATION_111_REL = "reports/v1-redesign/design111-adjudication.json"
ADJUDICATION_112_REL = "reports/v1-redesign/design112-adjudication.json"
SAMPLE_REL = "plans/v1-multishot-sample-design.json"
MIGRATION_REL = "contracts/v1-multishot-migration.sql"
OVERLAY_REL = "contracts/v1-multishot.openapi-overlay.json"
FRAME_SAMPLE_REL = "reports/unified-media/live-15/video-model-run.json"
D0_DIR = ".agent-governance/stages/V1-D0"
R1_DIR = ".agent-governance/stages/R1"
D0_MANIFEST_REL = D0_DIR + "/PAYLOAD_MANIFEST.sha256"

# The 1.0 D0 packet manifest digest. The 1.1 owner manifest was re-frozen, so
# the old pin must no longer validate the packet (CLI decision, not a constant).
OLD_D0_MANIFEST_SHA256 = "9bffdf2dc968f54fae0404d162c394e265cfb9900f68d9c303683bef756ede7b"
# The 1.1 owner packet digest. The 1.1.1 and the 1.1.2 packets replaced it, so
# it must no longer validate the packet either (CLI decision, not a constant).
OLD_D0_MANIFEST_1_1_SHA256 = "56e6f07b72023928b32ed7350b78f9d1d148daf79108daffecb7d9a175e39c4a"
# The 1.1.1 owner packet digest. The 1.1.2 packet replaced it, so it must no
# longer validate the packet either (CLI decision, not a constant).
OLD_D0_MANIFEST_1_1_1_SHA256 = "04d3bfb4af3c2d7be68e494a6d59624a96051a0ebf28e81d6a0367aa32aa6710"

ESTIMATE_BASIS = (
    "design performance thresholds, not measured current per-shot P95 "
    "and not hard worst-case guarantee"
)


# ---------------------------------------------------------------------------
# Synthetic 1.1 design documents
# ---------------------------------------------------------------------------

CANONICAL_SCENE = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "minLength": 1, "maxLength": 128},
        "media_ref_id": {"type": "string", "minLength": 1, "maxLength": 128},
        "revision": {"type": "integer", "minimum": 1},
        "start_pts": {"type": "integer"},
        "end_pts": {"type": "integer"},
        "origin_pts": {"type": "integer"},
        "time_base_num": {"type": "integer", "minimum": 1},
        "time_base_den": {"type": "integer", "minimum": 1},
        "verified": {"type": "boolean"},
        "editor": {"type": "string", "enum": ["algorithm", "human"]},
    },
    "required": [
        "id", "media_ref_id", "revision", "start_pts", "end_pts", "origin_pts",
        "time_base_num", "time_base_den", "verified", "editor",
    ],
    "additionalProperties": False,
}

CANONICAL_FRAME_REF = {
    "type": "object",
    "properties": {
        "index": {"type": "integer", "minimum": 0},
        "target_seconds": {"type": "number", "minimum": 0},
        "source_pts": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "time_base_num": {"anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]},
        "time_base_den": {"anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]},
        "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
        "time_basis": {"type": "string", "enum": ["sample_target", "decoded_pts"]},
    },
    "required": [
        "index", "target_seconds", "source_pts", "time_base_num",
        "time_base_den", "sha256", "time_basis",
    ],
    "additionalProperties": False,
}


def shot_frame_ref() -> dict:
    """The candidate ShotFrameRef: the canonical FrameRef shape, narrowed.

    design 1.1.1 (N4): the per shot reference carries a real decoded PTS and
    positive timebases, so the null branch is gone instead of sitting next to
    a sibling ``type``.
    """
    return {
        "type": "object",
        "properties": {
            "index": {"type": "integer", "minimum": 0},
            "target_seconds": {"type": "number", "minimum": 0},
            "source_pts": {"type": "integer"},
            "time_base_num": {"type": "integer", "minimum": 1},
            "time_base_den": {"type": "integer", "minimum": 1},
            "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "time_basis": {"const": "decoded_pts"},
        },
        "required": [
            "index", "target_seconds", "source_pts", "time_base_num",
            "time_base_den", "sha256", "time_basis",
        ],
        "additionalProperties": False,
    }


def closed_dto(properties: dict, required: list[str]) -> dict:
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


def candidate_defs() -> dict:
    """The 1.1 candidate DTO set."""
    scene_revision_info = closed_dto(
        {
            "scene_revision_id": {"type": "string", "minLength": 1},
            "scene_id": {"type": "string", "minLength": 1},
            "scene": {"$ref": "#/$defs/CoreScene"},
            "source_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "scene_revision_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "etag": {"type": "string", "minLength": 1},
            "time_basis": {"type": "string", "enum": ["decoded_pts", "estimated", "unverified"]},
        },
        ["scene_revision_id", "scene_id", "scene", "source_sha256", "scene_revision_hash", "etag", "time_basis"],
    )
    binding_fields = {
        "shot_id": {"type": "string", "minLength": 1},
        "scene_revision_id": {"type": "string", "minLength": 1},
        "scene_revision_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "media_ref_id": {"type": "string", "minLength": 1},
        "media_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "config_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
        "attempt_id": {"type": "string", "minLength": 1},
        "cancel_epoch": {"type": "integer", "minimum": 0},
    }
    public_binding = closed_dto(binding_fields, sorted(binding_fields))
    internal_binding = closed_dto(
        dict(binding_fields, lease_token={"type": "string", "minLength": 1}),
        sorted(binding_fields) + ["lease_token"],
    )
    bilingual_phrase = closed_dto(
        {"zh": {"type": "string"}, "en": {"type": "string"}}, ["zh", "en"]
    )
    bilingual_summary = closed_dto(
        {"zh": {"type": "string"}, "en": {"type": "string"}}, ["zh", "en"]
    )
    frame_indices = {
        "type": "array",
        "items": {"type": "integer", "minimum": 0, "maximum": 3},
        "minItems": 1,
        "maxItems": 4,
        "uniqueItems": True,
    }
    character = closed_dto(
        {
            "local_actor_id": {"type": "string", "minLength": 1},
            "visible_appearance": {"$ref": "#/$defs/BilingualPhrase"},
            "domain": {"enum": ["observation", "inference"]},
            "evidence_frame_indices": frame_indices,
        },
        ["local_actor_id", "visible_appearance", "domain", "evidence_frame_indices"],
    )
    scene_evidence = closed_dto(
        {
            "description": {"$ref": "#/$defs/BilingualPhrase"},
            "domain": {"enum": ["observation", "inference"]},
            "evidence_frame_indices": frame_indices,
        },
        ["description", "domain", "evidence_frame_indices"],
    )
    action = closed_dto(
        {
            "actor_ref": {"type": ["string", "null"]},
            "description": {"$ref": "#/$defs/BilingualPhrase"},
            "domain": {"enum": ["observation", "inference"]},
            "evidence_frame_indices": frame_indices,
        },
        ["actor_ref", "description", "domain", "evidence_frame_indices"],
    )
    machine_response = closed_dto(
        {
            "characters": {"type": "array", "items": {"$ref": "#/$defs/Character"}, "maxItems": 4},
            "scene": {"$ref": "#/$defs/SceneEvidence"},
            "actions": {"type": "array", "items": {"$ref": "#/$defs/Action"}, "maxItems": 4},
            "summary": {"$ref": "#/$defs/BilingualSummary"},
            "negative": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "unknowns": {"type": "array", "items": {"$ref": "#/$defs/BilingualPhrase"}, "maxItems": 8},
        },
        ["characters", "scene", "actions", "summary", "negative", "tags", "unknowns"],
    )
    shot_evidence = closed_dto(
        {
            "frame_refs": {"type": "array", "items": {"$ref": "#/$defs/ShotFrameRef"}, "minItems": 1, "maxItems": 4},
            "characters": {"type": "array", "items": {"$ref": "#/$defs/Character"}, "maxItems": 4},
            "scene": {"$ref": "#/$defs/SceneEvidence"},
            "actions": {"type": "array", "items": {"$ref": "#/$defs/Action"}, "maxItems": 4},
            "summary": {"$ref": "#/$defs/BilingualSummary"},
            "negative": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
            "unknowns": {"type": "array", "items": {"$ref": "#/$defs/BilingualPhrase"}, "maxItems": 8},
        },
        ["frame_refs", "characters", "scene", "actions", "summary", "negative", "tags", "unknowns"],
    )
    batch_request = closed_dto(
        {
            "shot_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 12, "uniqueItems": True},
            "scene_revision_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 12, "uniqueItems": True},
            "mode": {"enum": list(checker.FROZEN_BATCH_MODES)},
            "config_profile": {"type": "string", "minLength": 1},
            "retry_of_parent_id": {"type": ["string", "null"]},
        },
        ["shot_ids", "scene_revision_ids", "mode", "config_profile"],
    )
    parent_job = closed_dto(
        {
            "id": {"type": "string", "minLength": 1},
            "plan_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "planned_child_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 12},
            "selected_scene_revision_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 12},
            "total": {"type": "integer", "minimum": 1, "maximum": 12},
            "terminal_count": {"type": "integer", "minimum": 0, "maximum": 12},
            "deadline_at": {"type": "string", "format": "date-time"},
            "execution_budget_seconds": {"type": "integer", "minimum": 540, "maximum": 5490},
            "status": {"enum": ["queued", "preparing", "running", "partial", "succeeded", "failed", "cancelled", "interrupted"]},
            "not_executed_count": {"type": "integer", "minimum": 0, "maximum": 12},
            "retry_of_parent_id": {"type": ["string", "null"]},
        },
        list(checker.FROZEN_PARENT_JOB_FIELDS),
    )
    child_summary = closed_dto(
        {
            "ordinal": {"type": "integer", "minimum": 0, "maximum": 11},
            "job_id": {"type": "string", "minLength": 1},
            "shot_id": {"type": "string", "minLength": 1},
            "scene_revision_id": {"type": "string", "minLength": 1},
            "scene_revision_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "status": {"enum": ["queued", "preparing", "running", "partial", "succeeded", "failed", "cancelled", "interrupted"]},
            "result_ref": {"type": ["string", "null"]},
            "error_code": {"type": ["string", "null"]},
            "model_started": {"type": "boolean"},
            "retry_of_child_id": {"type": ["string", "null"]},
        },
        list(checker.FROZEN_CHILD_SUMMARY_FIELDS),
    )
    children_response = closed_dto(
        {
            "parent": {"$ref": "#/$defs/ParentJob"},
            "children": {"type": "array", "items": {"$ref": "#/$defs/ChildSummary"}, "minItems": 1, "maxItems": 12},
        },
        ["parent", "children"],
    )
    analysis_evidence = closed_dto(
        {
            "model_run_id": {"type": "string", "minLength": 1},
            "binding": {"$ref": "#/$defs/PublicAnalysisBinding"},
            "state": {"enum": ["current", "stale", "partial"]},
            "raw_schema_version": {"type": "string", "minLength": 1},
            "evidence": {"$ref": "#/$defs/ShotEvidence"},
        },
        ["model_run_id", "binding", "state", "raw_schema_version", "evidence"],
    )
    shot_scene_binding = closed_dto(
        {
            "shot_id": {"type": "string", "minLength": 1},
            "scene_revision_id": {"type": ["string", "null"]},
            "scene_revision_hash": {"type": ["string", "null"]},
            "etag": {"type": "string", "minLength": 1},
        },
        ["shot_id", "scene_revision_id", "scene_revision_hash", "etag"],
    )
    return {
        "CoreScene": json.loads(json.dumps(CANONICAL_SCENE)),
        "ShotFrameRef": shot_frame_ref(),
        "SceneRevisionInfo": scene_revision_info,
        "AnalysisBinding": internal_binding,
        "PublicAnalysisBinding": public_binding,
        "BilingualPhrase": bilingual_phrase,
        "BilingualSummary": bilingual_summary,
        "Character": character,
        "SceneEvidence": scene_evidence,
        "Action": action,
        "MachineShotResponse": machine_response,
        "ShotEvidence": shot_evidence,
        "BatchAnalyzeRequest": batch_request,
        "ParentJob": parent_job,
        "ChildSummary": child_summary,
        "BatchChildrenResponse": children_response,
        "ShotAnalysisEvidence": analysis_evidence,
        "ShotSceneBinding": shot_scene_binding,
    }


CLIP_ROWS = (
    ("H01", "hard_cut", 5, 4),
    ("H02", "hard_cut", 5, 4),
    ("H03", "hard_cut", 5, 4),
    ("H04", "hard_cut", 4, 3),
    ("H05", "hard_cut", 4, 3),
    ("H06", "hard_cut", 4, 3),
    ("N01", "no_cut_flash_static", 1, 0),
    ("N02", "no_cut_pan_static_subjects", 1, 0),
    ("D01", "dissolve_manual_corrected", 3, 0),
    ("D02", "crossfade_manual_corrected", 3, 0),
    ("V01", "vfr", 4, 0),
    ("F01", "short_fastcuts", 8, 0),
)


def sample_design() -> dict:
    clips = []
    quality = []
    for clip_id, category, shots, cuts in CLIP_ROWS:
        clip = {
            "id": clip_id,
            "category": category,
            "shots": shots,
            "hard_cut_annotations": cuts,
            "quality": {},
            "source_sha256": None,
            "annotation_hash": None,
            "status": checker.FROZEN_SAMPLE_CLIP_STATUS,
            "origin_source_id": None,
            "rights_record": None,
        }
        if category == "hard_cut":
            clip["quality"] = {"S02": "simple_action", "S03": "simple_action"}
            quality.append({"clip_id": clip_id, "shot_id": "S02", "category": "simple_action"})
            quality.append({"clip_id": clip_id, "shot_id": "S03", "category": "simple_action"})
        elif category == "no_cut_flash_static" or category == "no_cut_pan_static_subjects":
            clip["quality"] = {"S01": "static"}
            quality.append({"clip_id": clip_id, "shot_id": "S01", "category": "static"})
        elif category == "short_fastcuts":
            clip["quality"] = {"S04": "static"}
            quality.append({"clip_id": clip_id, "shot_id": "S04", "category": "static"})
        elif category == "vfr":
            clip["quality"] = {"S03": "ambiguous"}
            quality.append({"clip_id": clip_id, "shot_id": "S03", "category": "ambiguous"})
        else:
            clip["quality"] = {"S02": "ambiguous"}
            quality.append({"clip_id": clip_id, "shot_id": "S02", "category": "ambiguous"})
        clips.append(clip)
    return {
        "schema_version": "lvw.multishot-sample-design/1.1",
        "status": checker.FROZEN_SAMPLE_DESIGN_STATUS,
        "clips": clips,
        "total_clips": 12,
        "total_shots": 47,
        "hard_cut_annotation_count": 21,
        "quality_subset": quality,
        "quality_counts": {"simple_action": 12, "ambiguous": 3, "static": 3},
        "automatic_detection_scored_on": "H01..H06 hardcut group",
    }


def base_openapi() -> dict:
    error_response = {
        "description": "Error",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
    }
    return {
        "openapi": "3.1.0",
        "paths": {
            "/api/v1/jobs/batch": {
                "post": {
                    "operationId": "post_api_v1_jobs_batch",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "items": {
                                            "type": "array",
                                            "items": {"$ref": "#/components/schemas/AnalyzeRequest"},
                                        }
                                    },
                                    "required": ["items"],
                                    "additionalProperties": False,
                                }
                            }
                        },
                    },
                    "responses": {"202": {"description": "Accepted"}, "409": error_response},
                }
            },
            "/api/v1/scenes/detect": {
                "post": {
                    "operationId": "post_api_v1_scenes_detect",
                    "x-product-version": "V2",
                    "responses": {"202": {"description": "Accepted"}},
                }
            },
            "/api/v1/scenes": {
                "get": {
                    "operationId": "get_api_v1_scenes",
                    "x-product-version": "V2",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/api/v1/scenes/{id}": {
                "put": {
                    "operationId": "put_api_v1_scene",
                    "x-product-version": "V2",
                    "parameters": [{"name": "id", "in": "path", "required": True,
                                    "schema": {"type": "string"}}],
                    "responses": {"200": {
                        "description": "OK",
                        "content": {"application/json": {"schema": canonical_success_envelope()}},
                    }},
                }
            },
            "/api/v1/shots": {
                "post": {
                    "operationId": "post_api_v1_shots",
                    "x-product-version": "V1",
                    "responses": {"202": {"description": "Accepted"}},
                }
            },
            "/api/v1/shots/{id}": {
                "get": {
                    "operationId": "get_api_v1_shot",
                    "x-product-version": "V1",
                    "responses": {"200": {"description": "OK"}},
                },
                "put": {
                    "operationId": "put_api_v1_shot",
                    "x-product-version": "V1",
                    "responses": {"200": {"description": "OK"}},
                },
            },
            "/api/v1/jobs/{id}": {
                "get": {
                    "operationId": "get_api_v1_job",
                    "x-product-version": "V1",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/api/v1/jobs/{id}/cancel": {
                "post": {
                    "operationId": "post_api_v1_job_cancel",
                    "x-product-version": "V1",
                    "responses": {"202": {"description": "Accepted"}},
                }
            },
        },
        "components": {
            "schemas": {
                "Job": {"type": "object"},
                "Error": {"type": "object"},
                "Scene": {"type": "object"},
                "AnalyzeRequest": {"type": "object"},
            }
        },
    }


ETAG_PATTERN = '^\"scene:[^\":]+:[0-9a-f]{64}\"$'


def canonical_success_envelope() -> dict:
    """The canonical success envelope: data / request_id / schema_version.

    The new Scene GET must return the canonical Scene inside exactly this
    envelope, so the canonical operation on the same path carries it too.
    """
    return {
        "type": "object",
        "properties": {
            "data": {"$ref": "#/components/schemas/Scene"},
            "request_id": {"type": "string", "minLength": 1, "maxLength": 128},
            "schema_version": {"type": "string"},
        },
        "required": ["data", "request_id", "schema_version"],
        "additionalProperties": False,
    }


def etag_header() -> dict:
    """The machine declared strong ETag header object (owner artifact 743e028)."""
    return {
        "description": "Strong tag for the exact Scene revision in this response; never a weak tag.",
        "required": True,
        "schema": {"type": "string", "pattern": ETAG_PATTERN},
        "example": '\"scene:revision-1:%s\"' % ("a" * 64),
    }


def v1_annotation() -> dict:
    """The only two metadata keys the overlay may add to a canonical method."""
    return {"x-v1-profile": "local-shot-v1", "x-v2-semantics-unchanged": True}


def overlay_document() -> dict:
    error_responses = {
        code: {"description": "Error", "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}}}
        for code in ("400", "401", "403", "404", "409", "412", "422", "428", "503")
    }
    return {
        "kind": "LVW_ADDITIVE_OPENAPI_OVERLAY_DESIGN_1_1_1",
        "status": "DESIGN_REVIEW_NOT_ACTIVE",
        "base_file": "contracts/openapi.json",
        "component_source": "contracts/v1-multishot.schema.json",
        "component_prefix": "MultiShot_",
        "ref_rewrite": "#/$defs/X -> #/components/schemas/MultiShot_X",
        "merge_policy": "Copy base; add disjoint paths/methods and prefixed components; apply only declared additive response headers and x-v1-profile annotations. Never replace existing body schemas, parameters, response codes, x-product-version or V2 semantics. Abort on missing target, key collision or any other mutation.",
        "add_paths": {
            "/api/v1/jobs/shot-batches": {
                "post": {
                    "operationId": "post_api_v1_jobs_shot_batches",
                    "parameters": [{"name": "Idempotency-Key", "in": "header", "required": True,
                                   "schema": {"type": "string", "minLength": 1}}],
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/MultiShot_BatchAnalyzeRequest"}}},
                    },
                    "responses": dict(
                        {
                            "202": {
                                "description": "Accepted",
                                "content": {
                                    "application/json": {
                                        "schema": {
                                            "type": "object",
                                            "properties": {
                                                "data": {"$ref": "#/components/schemas/Job"},
                                                "request_id": {"type": "string"},
                                            },
                                            "required": ["data", "request_id"],
                                        }
                                    }
                                },
                            }
                        },
                        **error_responses,
                    ),
                }
            },
            "/api/v1/scenes/{id}": {
                "get": {
                    "operationId": "get_api_v1_scene_current",
                    "responses": {"200": {
                        "description": "OK",
                        "headers": {"ETag": etag_header()},
                        "content": {"application/json": {"schema": canonical_success_envelope()}},
                    }},
                }
            },
            "/api/v1/scenes/{id}/revision-info": {
                "get": {
                    "operationId": "get_api_v1_scene_revision_info",
                    "responses": {"200": {"description": "OK", "headers": {"ETag": etag_header()}}},
                }
            },
            "/api/v1/jobs/{id}/children": {
                "get": {
                    "operationId": "get_api_v1_job_children",
                    "responses": {"200": {"description": "OK"}},
                }
            },
            "/api/v1/shots/{id}/scene-binding": {
                "get": {"operationId": "get_api_v1_shot_scene_binding", "responses": {"200": {"description": "OK"}}},
                "put": {"operationId": "put_api_v1_shot_scene_binding", "responses": {"200": {"description": "OK"}}},
            },
            "/api/v1/shots/{id}/analyses/{run_id}/evidence": {
                "get": {"operationId": "get_api_v1_shot_analysis_evidence", "responses": {"200": {"description": "OK"}}},
            },
            "/api/v1/shots/{id}/analyses/{run_id}/adopt": {
                "post": {"operationId": "post_api_v1_shot_analysis_adopt", "responses": {"201": {"description": "Created"}}},
            },
        },
        "metadata_only": {
            "/api/v1/scenes/detect": {"post": v1_annotation()},
            "/api/v1/scenes": {"get": v1_annotation()},
            "/api/v1/scenes/{id}": {"put": v1_annotation()},
            "/api/v1/shots": {"post": v1_annotation()},
            "/api/v1/shots/{id}": {"get": v1_annotation(), "put": v1_annotation()},
            "/api/v1/jobs/{id}": {"get": v1_annotation()},
            "/api/v1/jobs/{id}/cancel": {"post": v1_annotation()},
        },
        "add_response_headers": {
            "/api/v1/scenes/{id}": {"put": {"200": {"ETag": etag_header()}}},
        },
        "metadata_merge_rule": "For each metadata_only[path][method], the target MUST exist in base; add only those absent x-* keys. Keep original x-product-version; x-v1-profile declares the bounded V1 use alongside the unchanged broader V2 contract. For add_response_headers, target path/method/status MUST exist; add headers only with no collision, leave body/content unchanged. Apply new methods first, then these two allowlisted additions; any missing target/collision/other change aborts.",
    }


def migration_sql() -> str:
    lines = [
        "-- DESIGN CANDIDATE 1.1.2 ONLY. No production DB was opened during D0.",
        "-- register deterministic lvw_scene_hash(11args) before this transaction.",
        "PRAGMA foreign_keys=ON;",
        "BEGIN IMMEDIATE;",
    ]
    for name in checker.FROZEN_MIGRATION_OBJECTS:
        if name == "scene_revision":
            # The scene hash binds the hashed field names to these DDL columns.
            lines.append(
                "CREATE TABLE IF NOT EXISTS scene_revision(id TEXT PRIMARY KEY, media_ref_id TEXT NOT NULL, "
                "version INTEGER NOT NULL, start_pts INTEGER NOT NULL, end_pts INTEGER NOT NULL, "
                "origin_pts INTEGER NOT NULL, tb_num INTEGER NOT NULL CHECK(tb_num>0), "
                "tb_den INTEGER NOT NULL CHECK(tb_den>0), editor TEXT NOT NULL);"
            )
            continue
        if name == "scene_head":
            lines.append(
                "CREATE TABLE scene_head(scene_id TEXT PRIMARY KEY, head_revision_id TEXT NOT NULL, "
                "etag TEXT NOT NULL);"
            )
            continue
        if name == "scene_revision_meta":
            lines.append(
                "CREATE TABLE scene_revision_meta(scene_revision_id TEXT PRIMARY KEY, scene_id TEXT NOT NULL, "
                "revision INTEGER NOT NULL, source_sha256 TEXT NOT NULL, time_basis TEXT NOT NULL, "
                "verified INTEGER NOT NULL CHECK(verified IN(0,1)), content_sha256 TEXT NOT NULL, "
                "etag TEXT NOT NULL, CHECK((verified=1 AND time_basis='decoded_pts') OR "
                "(verified=0 AND time_basis!='decoded_pts')));"
            )
            continue
        lines.append("CREATE TABLE IF NOT EXISTS %s(id TEXT PRIMARY KEY, payload TEXT NOT NULL);" % name)
    lines.append(
        "CREATE TABLE shot_batch_parent_check(id TEXT PRIMARY KEY, planned_count INTEGER NOT NULL, "
        "execution_budget_seconds INTEGER NOT NULL, CHECK(execution_budget_seconds=450*planned_count+90));"
    )
    lines.append(
        "CREATE TABLE shot_analysis_binding_token(model_run_id TEXT PRIMARY KEY, lease_token TEXT NOT NULL);"
    )
    # The two backfill call sites. The 11 arguments are the 11 hashed fields
    # in the declared order.
    lines.append(
        "INSERT INTO scene_head SELECT s.id,s.id,'\"scene:'||s.id||':'||"
        "lvw_scene_hash(s.media_ref_id,m.sha256,s.version,s.start_pts,s.end_pts,s.origin_pts,"
        "s.tb_num,s.tb_den,s.editor,'unverified',0)||'\"' FROM scene_revision s "
        "JOIN media_ref m ON s.media_ref_id=m.id;"
    )
    lines.append(
        "INSERT INTO scene_revision_meta SELECT s.id,s.id,s.version,m.sha256,'unverified',0,"
        "lvw_scene_hash(s.media_ref_id,m.sha256,s.version,s.start_pts,s.end_pts,s.origin_pts,"
        "s.tb_num,s.tb_den,s.editor,'unverified',0),h.etag FROM scene_revision s "
        "JOIN media_ref m ON m.id=s.media_ref_id JOIN scene_head h ON h.scene_id=s.id;"
    )
    lines.append("COMMIT;")
    return "\n".join(lines) + "\n"


def frame_sample() -> dict:
    frames = []
    for index in range(4):
        frames.append({
            "index": index,
            "target_seconds": index * 2 + 1,
            "source_pts": 12288 * (index * 2 + 1),
            "time_base_num": 1,
            "time_base_den": 12288,
            "sha256": hashlib.sha256(("frame-%d" % index).encode("utf-8")).hexdigest(),
            "time_basis": "decoded_pts",
        })
    return {"id": "synthetic-run", "frames": frames}


def candidate_contract() -> dict:
    defs = candidate_defs()
    return {
        "schema_version": "lvw.multishot-contract-candidate/1.1.1",
        "status": "DESIGN_REVIEW_NOT_ACTIVE_OPENAPI",
        "authority": "docs/31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md",
        "entities": {
            "SceneRevisionInfo": {"required": list(defs["SceneRevisionInfo"]["required"]), "invariants": ["scene.id==scene_id"]},
            "AnalysisBinding": {"required": list(defs["AnalysisBinding"]["required"]), "invariants": []},
            "ShotEvidence": {
                "required": list(defs["ShotEvidence"]["required"]),
                "invariants": ["FrameRefs are server-owned additions"],
                "character_fields": list(defs["Character"]["required"]),
                "action_fields": list(defs["Action"]["required"]),
            },
            "ParentJob": {
                "required": list(defs["ParentJob"]["required"]),
                "invariants": [
                    "id=canonical Job.id; progress_done=terminal_count; progress_total=total",
                    "execution_budget_seconds=450*total+90; deadline_at=created_at+budget; no extension on restart",
                ],
            },
        },
        "reuse_paths": [
            "/api/v1/scenes/detect",
            "/api/v1/scenes",
            "/api/v1/scenes/{id}",
            "/api/v1/shots",
            "/api/v1/shots/{id}",
            "/api/v1/jobs/{id}",
            "/api/v1/jobs/{id}/cancel",
        ],
        "dto_schema": "contracts/v1-multishot.schema.json",
        "openapi_overlay": "contracts/v1-multishot.openapi-overlay.json",
        "storage_migration": "contracts/v1-multishot-migration.sql",
        "additive_paths": [
            "/api/v1/jobs/shot-batches",
            "/api/v1/scenes/{id}",
            "/api/v1/scenes/{id}/revision-info",
            "/api/v1/jobs/{id}/children",
            "/api/v1/shots/{id}/scene-binding",
            "/api/v1/shots/{id}/analyses/{run_id}/evidence",
            "/api/v1/shots/{id}/analyses/{run_id}/adopt",
        ],
        "additive_operations": [
            {"path": "/api/v1/jobs/shot-batches", "method": "POST"},
            {"path": "/api/v1/scenes/{id}", "method": "GET"},
            {"path": "/api/v1/scenes/{id}/revision-info", "method": "GET"},
            {"path": "/api/v1/jobs/{id}/children", "method": "GET"},
            {"path": "/api/v1/shots/{id}/scene-binding", "method": "GET"},
            {"path": "/api/v1/shots/{id}/scene-binding", "method": "PUT"},
            {"path": "/api/v1/shots/{id}/analyses/{run_id}/evidence", "method": "GET"},
            {"path": "/api/v1/shots/{id}/analyses/{run_id}/adopt", "method": "POST"},
        ],
        "explicit_reserved_v2_paths": ["/api/v1/jobs/batch", "/api/v1/jobs/{id}/retry"],
        "http_rules": [
            "canonical POST /jobs/batch {items:[AnalyzeRequest]} remains V2 unchanged",
            "public analysis provenance excludes lease_token",
        ],
        "scene_hash": {
            "algorithm": "sha256 UTF8 canonical JSON sorted keys, compact separators, ensure_ascii=False, allow_nan=False",
            "fields": [
                "media_ref_id",
                "media_sha256",
                "revision",
                "start_pts",
                "end_pts",
                "origin_pts",
                "time_base_num",
                "time_base_den",
                "editor",
                "time_basis",
                "verified",
            ],
            "etag": "quoted strong tag scene:<scene_revision_id>:<scene_revision_hash>",
            "excluded": ["random row id", "created_at", "server clock"],
            "storage": "scene_revision_meta.content_sha256/etag; AnalysisBinding.scene_revision_hash immutable copy",
            "column_mapping": {
                "media_ref_id": "scene_revision.media_ref_id",
                "media_sha256": "scene_revision_meta.source_sha256 (legacy backfill: media_ref.sha256)",
                "revision": "scene_revision.version (equals scene_revision_meta.revision)",
                "start_pts": "scene_revision.start_pts",
                "end_pts": "scene_revision.end_pts",
                "origin_pts": "scene_revision.origin_pts",
                "time_base_num": "scene_revision.tb_num",
                "time_base_den": "scene_revision.tb_den",
                "editor": "scene_revision.editor",
                "time_basis": "scene_revision_meta.time_basis",
                "verified": "scene_revision_meta.verified (SQLite 0/1 converted to JSON false/true)",
            },
            "serialization_rule": "Use the declared hash field names as JSON keys; column aliases are value sources only. All PTS/timebase/revision values are JSON integers (never bool/float/string); verified is JSON boolean; no extra keys.",
        },
        "canonical_domain_mapping": {
            "version": "shot-domains/1",
            "language_order": ["zh", "en"],
            "item_order": "characters sorted by local_actor_id Unicode codepoint, then scene, then actions in original zero-based array order; route each item only to its declared observation or inference domain",
            "entry_serialization": "Each nonempty language value produces one string: compact UTF-8 JSON object, sorted keys, ensure_ascii=False, allow_nan=False. The JSON key set is {kind, lang, ref, text}; serialized key order MUST be kind, lang, ref, text (sort_keys=True), never insertion order. No translation, normalization, trim or deduplication; skip only exactly empty strings. Preserve raw model response byte-for-byte.",
            "refs": {
                "character": "local_actor_id",
                "scene": "scene",
                "action": "decimal original zero-based action array index",
                "unknown": "decimal original zero-based unknowns array index",
            },
            "source_fields": {
                "character": "visible_appearance",
                "scene": "description",
                "action": "description",
                "unknown": "unknowns item",
            },
            "unknowns": "Original unknowns array order, each zh then en; same JSON entry with kind=unknown into Domains.unknowns only.",
            "human_domains": "Do not generate or overwrite user_evidence/creative_intent; merge only through explicit adoption with human locks taking precedence.",
            "prompt_text": "summary.zh -> text_zh; summary.en -> text_en, exact copies. Missing language stays empty, no translation.",
            "example": {
                "source": {
                    "local_actor_id": "actor1",
                    "visible_appearance": {"zh": "红衣人物", "en": "person in red"},
                    "domain": "observation",
                },
                "observation": [
                    "{\"kind\":\"character\",\"lang\":\"zh\",\"ref\":\"actor1\",\"text\":\"红衣人物\"}",
                    "{\"kind\":\"character\",\"lang\":\"en\",\"ref\":\"actor1\",\"text\":\"person in red\"}",
                ],
            },
        },
    }


def root_plan() -> dict:
    return {
        "schema_version": "lvw.v1-plan/1.1",
        "approval": APPROVAL_REL,
        "status": "DESIGN_REVIEW_REQUIRED",
        "roles": {
            "architect_gate_owner": "Codex",
            "implementer": "Orca visible ClaudeCode worker",
            "local_validation": "same implementer plus deterministic executor, not independent",
            "independent_reviewer": "separate context/workspace, read-only candidate",
            "human": "actual experience and release signatures",
        },
        "product_current_coordinate_source": "plans/execution-control.json",
        "parallel_preparation": {
            "id": "V1-D0",
            "workpacks": [
                "D0-A architecture/contracts/acceptance design",
                "D0-B deterministic plan checker and independent design review",
            ],
            "product_edits_allowed": False,
        },
        "stages": [
            {"id": "R1", "depends_on": ["R1a", "V0-S3"], "workpacks": ["R1-A"], "completed": 0, "total": 4},
            {"id": "V1-M1", "depends_on": ["R1"], "workpacks": ["M1-A", "M1-B", "M1-C"], "completed": 0, "total": 3},
            {"id": "R2", "depends_on": ["R1", "V1-M1"], "workpacks": ["R2-A", "R2-D"], "completed": 0, "total": 4},
        ],
        "legacy_v0_obligations_retained": True,
        "old_slice_human_signoff_waived": False,
        "limits": {key: value for key, (value, _kind) in checker.FROZEN_LIMITS.items()},
        "v1_required_cases": list(GATES_V1),
        "supplement_case_ids": list(MS),
        "contract_candidate": "plans/v1-multishot-contract.json",
        "sample_design": SAMPLE_REL,
        "acceptance_design": "docs/32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md",
        "global_authority": checker.FROZEN_GLOBAL_AUTHORITY,
        "budget_reset": False,
        "authorization_accounting": {
            "design_stage": "V1-M1",
            "authority_stage": "R2",
            "scope_record": APPROVAL_REL,
            "policy": "M1 is approved V1/R2 early substage; finite receipt binds both identities and scope hash.",
        },
        "checkpoint_budget": dict(checker.FROZEN_CHECKPOINT_INPUTS, estimate_basis=ESTIMATE_BASIS),
    }


def d0_stage_control() -> dict:
    return {
        "schema_version": "lvw.stage-control/1",
        "stage_id": "V1-D0",
        "status": "FROZEN_OFFLINE_TOOL_SCOPE_ONLY_PRODUCT_GATE0_NOT_READY",
        "version": "1.1",
        "product_execution_authorized": False,
        "roles": {
            "gate_owner": "Codex",
            "implementation_owner": "ClaudeCode-D0-Implement",
            "independent_reviewer": "ClaudeCode-D0-Review",
        },
        "workpacks": [
            {
                "id": "D0-B-IMPL",
                "allowed_files": list(checker.FROZEN_D0_ALLOWED_FILES),
                "commands": list(checker.FROZEN_D0_COMMANDS),
                "outputs": ["implementation receipt", "raw commands", "test exit codes", "risks"],
            },
            {
                "id": "D0-B-REVIEW",
                "allowed_files": list(checker.FROZEN_D0_REVIEW_ALLOWED_FILES),
                "depends_on": ["D0-A-DESIGN-DRAFT"],
                "outputs": ["read-only design review", "Fatal/Major/Minor list"],
            },
        ],
        "forbidden_write_paths": list(checker.FROZEN_D0_FORBIDDEN_PATHS),
        "model_gpu_runtime_budget": 0,
        "product_full_checkpoints": 0,
        "stage_pass_forbidden": True,
    }


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def regenerate_d0_manifest(root: Path) -> str:
    """Rewrite the D0 payload manifest over the frozen packet inventory."""
    packet = root / D0_DIR
    lines = []
    for name in checker.FROZEN_D0_PACKET_FILES:
        lines.append("%s  %s\n" % (sha256(packet / name), name))
    manifest = packet / "PAYLOAD_MANIFEST.sha256"
    manifest.write_text("".join(lines), encoding="utf-8")
    return sha256(manifest)


def build_fixture(root: Path) -> dict:
    """Write a minimal but complete synthetic package tree."""
    # --- release gates and the pre-amendment baseline ------------------------
    write_json(root / "plans/release_gates.json", {
        "schema_version": "lvw.release-gates/1",
        "gates": {
            "V1": {"required_cases": list(GATES_V1)},
            "V2": {"required_cases": list(GATES_V2)},
            "V3": {"required_cases": list(GATES_V3)},
        },
        "states": ["NOT_RUN", "PASS", "FAIL", "BLOCKED"],
    })
    write_json(root / BASELINE_REL, {
        "kind": "PRE_AMENDMENT_CASE_SETS",
        "required_cases": {
            "V1": list(LEGACY_V1),
            "V2": LEGACY_V1 + LEGACY_V2_EXTRA,
            "V3": LEGACY_V1 + LEGACY_V2_EXTRA + LEGACY_V3_EXTRA,
        },
        "canonical_contract_hashes": {},
        "old_R1_packet_manifest_sha256": "",
    })

    # --- candidate contract and candidate DTO schema -------------------------
    write_json(root / "plans/v1-multishot-contract.json", candidate_contract())
    write_json(root / "contracts/v1-multishot.schema.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:lvw:v1-multishot:design-candidate:1.1",
        "title": "V1 multi-shot candidate DTOs",
        "$defs": candidate_defs(),
    })

    # --- the machine sample allocation ---------------------------------------
    write_json(root / SAMPLE_REL, sample_design())

    # --- the additive OpenAPI overlay and the candidate migration ------------
    write_json(root / OVERLAY_REL, overlay_document())
    (root / MIGRATION_REL).parent.mkdir(parents=True, exist_ok=True)
    (root / MIGRATION_REL).write_text(migration_sql(), encoding="utf-8")

    # --- the retained frame reference sample ---------------------------------
    write_json(root / FRAME_SAMPLE_REL, frame_sample())

    # --- the root adjudication -----------------------------------------------
    write_json(root / ADJUDICATION_REL, {
        "kind": "CODEX_ARCHITECTURE_ADJUDICATION_NOT_INDEPENDENT_CLOSURE",
        "version": "1.1",
        "decision": "CORRECTIONS_PROPOSED_AWAIT_ISOLATED_RECHECK",
        "responses": [{"id": "F1", "status": "PENDING_RECHECK"}],
        "product_pass": False,
        "human_signoff": None,
    })
    write_json(root / ADJUDICATION_111_REL, {
        "kind": "CODEX_OWNER_MINOR_CORRECTION_NOT_INDEPENDENT_ACCEPTANCE",
        "version": "1.1.1",
        "original22": "Resolved at design level by design11 independent review; not product acceptance",
        "findings": [
            {"id": finding_id, "state": "CORRECTED_PENDING_INDEPENDENT_RECHECK"}
            for finding_id in ("N1", "N2", "N3", "N4", "N5", "N6")
        ],
        "code_candidate": "172d176",
        "product_gate0": False,
        "sample_materialization": "NOT_RUN",
    })
    # The design 1.1.2 consolidated correction authority. It is a correction
    # package: CHANGES_REQUIRED, no product gate and no closed finding.
    write_json(root / ADJUDICATION_112_REL, {
        "kind": "CODEX_D0_CONSOLIDATED_CORRECTION_NOT_PRODUCT_GATE",
        "version": "1.1.2",
        "decision": "CHANGES_REQUIRED",
        "findings": [
            {"id": "NM-1", "severity": "Major", "state": "IMPLEMENTATION_CORRECTION_REQUIRED"},
            {"id": "NM-2", "severity": "Major", "state": "IMPLEMENTATION_CORRECTION_REQUIRED"},
            {"id": "NM-3", "severity": "Major", "state": "IMPLEMENTATION_CORRECTION_REQUIRED"},
            {"id": "NM-4", "severity": "Minor", "state": "IMPLEMENTATION_CORRECTION_REQUIRED"},
            {"id": "NM-5", "severity": "Minor", "state": "OWNER_CLARIFICATION_PENDING_RECHECK"},
            {"id": "NM-6", "severity": "Minor", "state": "IMPLEMENTATION_CORRECTION_REQUIRED"},
            {"id": "NM-7", "severity": "Minor", "state": "IMPLEMENTATION_CORRECTION_REQUIRED"},
            {"id": "NM-8", "severity": "Minor", "state": "IMPLEMENTATION_CORRECTION_REQUIRED"},
        ],
        "derived_counts": {"Fatal": 0, "Major": 3, "Minor": 5},
        "review_summary_minor_count": 6,
        "count_discrepancy": "Retain original report; eight concrete findings; next reviewer to reconcile count in appended receipt.",
        "product_gate0": False,
        "product_actions": 0,
        "historical_source": {"authority": "743e028474909be02326facd6f14ca0ac26aa56f"},
    })

    # --- acceptance cases ----------------------------------------------------
    cases = []
    for case_id in ["Q01"] + MS:
        tokens = checker.FROZEN_QUALITY_TOKENS.get(case_id, ())
        assertions = ["阈值断言 %s" % token for token in tokens] or ["无固定阈值"]
        cases.append({"case_id": case_id, "version": "V1", "status": "NOT_RUN", "assertions": assertions})
    write_json(root / "plans/acceptance_cases.json", {
        "schema_version": "lvw.acceptance-cases/2.0",
        "cases": cases,
    })

    # --- requirements and task graph -----------------------------------------
    write_json(root / "plans/requirements.json", {
        "requirements": [{
            "requirement_id": "R22",
            "title": "V1短视频多镜头",
            "stages": ["V1-M1", "R2"],
            "acceptance_ids": list(MS),
            "status": "NOT_RUN",
        }],
    })
    write_json(root / "plans/tasks.json", {
        "stages": [
            {"stage_id": "R1a", "version": "V1", "depends_on": [], "status": "NOT_RUN",
             "requirements": [], "work_on_cases": []},
            {"stage_id": "V0-S3", "version": "V0.2", "depends_on": [], "status": "NOT_RUN",
             "requirements": [], "work_on_cases": []},
            {"stage_id": "R1", "version": "V1", "depends_on": ["R1a", "V0-S3"], "status": "NOT_RUN",
             "requirements": [], "work_on_cases": GATES_V1[:16]},
            {"stage_id": "V1-M1", "version": "V1", "depends_on": ["R1"], "status": "NOT_RUN",
             "requirements": ["R22"], "work_on_cases": list(MS)},
            {"stage_id": "R2", "version": "V1", "depends_on": ["R1", "V1-M1"], "status": "NOT_RUN",
             "requirements": ["R22"], "work_on_cases": list(GATES_V1)},
        ],
    })

    # --- root plan -----------------------------------------------------------
    write_json(root / "plans/v1-revised-plan.json", root_plan())

    # --- approval, execution control, D0 stage packet ------------------------
    write_json(root / APPROVAL_REL, {
        "kind": "APPROVED_PRODUCT_SCOPE_AND_DEVELOPMENT_ROLE_CHANGE",
        "id": "CHANGE-V1-MULTISHOT-01",
        "decision": "APPROVED_BY_PROJECT_OWNER",
        "human_acceptance_of_621b1bf": False,
        "release_approved": False,
    })
    write_json(root / "plans/execution-control.json", {
        "schema_version": "lvw.execution-control/1",
        "coordinate": {"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "UNIFIED_MEDIA", "state": "WAIT_HUMAN"},
        "forbidden_claims": ["V1_ACCEPTED", "PRODUCTION_RELEASED"],
        "human_signoff": None,
        "product_acceptance": None,
    })
    packet = root / D0_DIR
    packet.mkdir(parents=True, exist_ok=True)
    for name in checker.FROZEN_D0_PACKET_FILES:
        if name.endswith(".md"):
            (packet / name).write_text("# %s\n\nsynthetic packet file for the D0 checker tests\n" % name, encoding="utf-8")
    write_json(packet / "stage-control.json", d0_stage_control())

    # --- canonical contracts and the protected old R1 packet -----------------
    write_json(root / "contracts/openapi.json", base_openapi())
    write_json(root / "contracts/lvw.schema.json", {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "urn:lvw:core:1",
        "$defs": {"Scene": json.loads(json.dumps(CANONICAL_SCENE)),
                  "FrameRef": json.loads(json.dumps(CANONICAL_FRAME_REF))},
    })
    (root / "contracts/storage.sql").write_text("-- baseline DDL\n", encoding="utf-8")
    for name in ("17_DATA_AND_VERSIONING.md", "20_RELIABILITY_AND_OPERATIONS.md",
                 "30_V1_REVISED_EXECUTION_PLAN.md", "31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md",
                 "32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md"):
        doc = root / "docs" / name
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# %s\n\nsynthetic authority document\n" % name, encoding="utf-8")

    r1_file = root / R1_DIR / "stage-control.json"
    r1_file.parent.mkdir(parents=True, exist_ok=True)
    r1_file.write_text(json.dumps({"stage_id": "R1", "frozen": True}) + "\n", encoding="utf-8")
    (root / R1_DIR / "PAYLOAD_MANIFEST.sha256").write_text(
        "%s  stage-control.json\n" % sha256(r1_file), encoding="utf-8")

    baseline = json.loads((root / BASELINE_REL).read_text(encoding="utf-8"))
    baseline["canonical_contract_hashes"] = {
        "contracts/openapi.json": sha256(root / "contracts/openapi.json"),
        "contracts/lvw.schema.json": sha256(root / "contracts/lvw.schema.json"),
        "contracts/storage.sql": sha256(root / "contracts/storage.sql"),
    }
    baseline["old_R1_packet_manifest_sha256"] = sha256(root / R1_DIR / "PAYLOAD_MANIFEST.sha256")
    write_json(root / BASELINE_REL, baseline)

    # Actual parent layout: the authority spec manifest does *not* list the D0
    # stage control or the D0 payload manifest; the D0 packet manifest fences
    # that control plane instead. design 1.1.2: the authority spec manifest is
    # a closed inventory of exactly 25 files; the design 1.1.1 adjudication is
    # retained as the historical frozen record and the design 1.1.2
    # adjudication is added.
    fenced = [
        "docs/17_DATA_AND_VERSIONING.md",
        "docs/20_RELIABILITY_AND_OPERATIONS.md",
        "docs/30_V1_REVISED_EXECUTION_PLAN.md",
        "docs/31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md",
        "docs/32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md",
        "plans/v1-revised-plan.json",
        "plans/v1-multishot-contract.json",
        "plans/v1-multishot-sample-design.json",
        "plans/requirements.json",
        "plans/tasks.json",
        "plans/acceptance_cases.json",
        "plans/release_gates.json",
        "plans/execution-control.json",
        "contracts/openapi.json",
        "contracts/lvw.schema.json",
        "contracts/storage.sql",
        "contracts/v1-multishot.schema.json",
        "contracts/v1-multishot-migration.sql",
        "contracts/v1-multishot.openapi-overlay.json",
        APPROVAL_REL,
        BASELINE_REL,
        ADJUDICATION_REL,
        ADJUDICATION_111_REL,
        ADJUDICATION_112_REL,
        R1_DIR + "/PAYLOAD_MANIFEST.sha256",
    ]
    assert len(fenced) == 25, "the synthetic authority fence must hold exactly 25 files"
    write_json(root / D0_DIR / "spec-manifest.json", {
        "kind": "D0_AUTHORITY_DESIGN112_CANDIDATE_HASH_FENCE_NOT_PRODUCT_GATE0",
        "files": {rel: sha256(root / rel) for rel in fenced},
    })
    return {"d0_manifest_sha256": regenerate_d0_manifest(root)}


def run_checker(root: Path, pin: str | None = None, extra: list[str] | None = None, env: dict | None = None):
    command = [sys.executable, "-B", str(CHECKER), "--root", str(root)]
    if pin is not None:
        command += ["--d0-packet-manifest-sha256", pin]
    command += list(extra or [])
    run_env = dict(os.environ)
    if env:
        run_env.update(env)
    return subprocess.run(command, capture_output=True, text=True, env=run_env)


def load(root: Path, rel: str):
    return json.loads((root / rel).read_text(encoding="utf-8"))


def save(root: Path, rel: str, payload) -> None:
    write_json(root / rel, payload)


def refresh_fences(package: dict, rels=()) -> None:
    """Re-freeze the authority spec manifest and the D0 payload manifest.

    Used only after mutations that are *not* the subject of the test, so the
    tree stays consistent and the asserted finding stays specific.
    """
    root = package["root"]
    spec_path = root / D0_DIR / "spec-manifest.json"
    spec = load(root, D0_DIR + "/spec-manifest.json")
    touched = set(rels)
    baseline = load(root, BASELINE_REL)
    pinned = baseline.get("canonical_contract_hashes") or {}
    for rel in rels:
        if rel in pinned:
            pinned[rel] = sha256(root / rel)
            touched.add(BASELINE_REL)
    if BASELINE_REL in touched:
        baseline["canonical_contract_hashes"] = pinned
        write_json(root / BASELINE_REL, baseline)
    for rel in sorted(touched):
        spec["files"][rel] = sha256(root / rel)
    write_json(spec_path, spec)
    package["d0_manifest_sha256"] = regenerate_d0_manifest(root)


@pytest.fixture()
def package(tmp_path):
    root = tmp_path / "pkg"
    root.mkdir()
    state = build_fixture(root)
    state["root"] = root
    return state


def expect_failure(result, code: str):
    assert result.returncode != 0, "checker exited 0 for a faulty package:\n%s" % result.stdout
    assert code in result.stdout, "expected %s in output:\n%s" % (code, result.stdout)


def run_package(package: dict, extra=None, env=None):
    return run_checker(package["root"], package["d0_manifest_sha256"], extra, env)


# ---------------------------------------------------------------------------
# Positive controls
# ---------------------------------------------------------------------------


def test_valid_package_exits_zero(package):
    result = run_package(package)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout


def test_checker_is_read_only(package):
    root = package["root"]
    before = {p: sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}
    assert run_package(package).returncode == 0
    after = {p: sha256(p) for p in sorted(root.rglob("*")) if p.is_file()}
    assert before == after


def test_canonical_package_validates_read_only():
    """The canonical package must satisfy the checker; the run must not write anything."""
    watched = [
        "plans/v1-revised-plan.json",
        "plans/release_gates.json",
        "plans/acceptance_cases.json",
        "plans/requirements.json",
        "plans/tasks.json",
        "plans/v1-multishot-contract.json",
        "plans/v1-multishot-sample-design.json",
        "plans/execution-control.json",
        "contracts/v1-multishot.schema.json",
        "contracts/v1-multishot.openapi-overlay.json",
        "contracts/v1-multishot-migration.sql",
        "contracts/openapi.json",
        "contracts/lvw.schema.json",
        "contracts/storage.sql",
        D0_DIR + "/stage-control.json",
        D0_DIR + "/spec-manifest.json",
        D0_DIR + "/PAYLOAD_MANIFEST.sha256",
        APPROVAL_REL,
        ADJUDICATION_REL,
        R1_DIR + "/PAYLOAD_MANIFEST.sha256",
    ]
    before = {rel: sha256(ROOT / rel) for rel in watched}
    result = subprocess.run(
        [sys.executable, "-B", str(CHECKER)], capture_output=True, text=True, cwd=str(ROOT)
    )
    after = {rel: sha256(ROOT / rel) for rel in watched}
    assert before == after, "the checker modified a canonical file"
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout


def test_stale_1_0_packet_pin_no_longer_validates_the_owner_packet():
    """The 1.1 owner manifest was re-frozen; the superseded 1.0 pin must fail."""
    result = subprocess.run(
        [sys.executable, "-B", str(CHECKER), "--d0-packet-manifest-sha256", OLD_D0_MANIFEST_SHA256],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    expect_failure(result, "E_D0_PACKET_MANIFEST_PINNED")


# ---------------------------------------------------------------------------
# Major D0-CODE-M01: empty control lists must never bypass a check
# ---------------------------------------------------------------------------


def test_empty_allowed_files_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-IMPL":
            workpack["allowed_files"] = []
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_ALLOWED_FILES")


def test_empty_commands_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-IMPL":
            workpack["commands"] = []
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_COMMANDS")


def test_empty_forbidden_write_paths_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    control["forbidden_write_paths"] = []
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_FORBIDDEN_PATHS")


def test_empty_review_allowed_files_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-REVIEW":
            workpack["allowed_files"] = []
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_REVIEW_FILES")


def test_missing_workpack_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    control["workpacks"] = [w for w in control["workpacks"] if w["id"] != "D0-B-IMPL"]
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_WORKPACK")


def test_nonzero_d0_budget_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    control["model_gpu_runtime_budget"] = 8
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_BUDGET")


# ---------------------------------------------------------------------------
# Major D0-CODE-M01: the D0 control plane must be fenced even though the
# authority spec manifest does not list it
# ---------------------------------------------------------------------------


def test_actual_style_layout_without_stage_control_fence_detects_drift(package):
    """The spec manifest does not list the D0 stage control; the packet manifest must catch drift."""
    control = load(package["root"], D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-IMPL":
            workpack["allowed_files"] = []
    save(package["root"], D0_DIR + "/stage-control.json", control)
    result = run_package(package)
    expect_failure(result, "E_D0_PACKET_DRIFT")
    expect_failure(result, "E_OWNERSHIP_ALLOWED_FILES")


def test_d0_packet_control_drift_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    control["stage_pass_forbidden"] = False
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_D0_PACKET_DRIFT")


def test_d0_packet_manifest_missing_entry_is_rejected(package):
    manifest = package["root"] / D0_MANIFEST_REL
    kept = [line for line in manifest.read_text(encoding="utf-8").splitlines() if not line.endswith("  stage-control.json")]
    manifest.write_text("\n".join(kept) + "\n", encoding="utf-8")
    result = run_package(package)
    expect_failure(result, "E_D0_PACKET_MANIFEST_MISSING_ENTRY")
    expect_failure(result, "E_D0_CONTROL_UNBOUND")


def test_d0_packet_manifest_extra_entry_is_rejected(package):
    manifest = package["root"] / D0_MANIFEST_REL
    manifest.write_text(
        manifest.read_text(encoding="utf-8") + "%s  extra-notebook.md\n" % ("0" * 64), encoding="utf-8"
    )
    expect_failure(run_package(package), "E_D0_PACKET_MANIFEST_EXTRA_ENTRY")


def test_d0_packet_manifest_missing_file_is_rejected(package):
    (package["root"] / D0_DIR / "07-checkpoint-plan.md").unlink()
    expect_failure(run_package(package), "E_D0_PACKET_FILE_MISSING")


def test_d0_packet_manifest_missing_is_rejected(package):
    (package["root"] / D0_MANIFEST_REL).unlink()
    expect_failure(run_package(package), "E_D0_PACKET_MANIFEST_MISSING")


def test_d0_packet_manifest_regenerated_to_hide_drift_is_rejected(package):
    """Editing the control and re-signing the manifest must still fail the source-control pin."""
    root = package["root"]
    control = load(root, D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-IMPL":
            workpack["allowed_files"] = []
    save(root, D0_DIR + "/stage-control.json", control)
    regenerate_d0_manifest(root)  # attacker re-signs the packet manifest
    expect_failure(run_package(package), "E_D0_PACKET_MANIFEST_PINNED")


def test_d0_packet_unlisted_file_is_rejected(package):
    (package["root"] / D0_DIR / "08-extra-note.md").write_text("uncontrolled\n", encoding="utf-8")
    expect_failure(run_package(package), "E_D0_PACKET_UNLISTED_FILE")


def test_d0_packet_manifest_not_bound_to_spec_manifest_is_rejected(package):
    manifest = package["root"] / D0_MANIFEST_REL
    kept = [line for line in manifest.read_text(encoding="utf-8").splitlines() if not line.endswith("  spec-manifest.json")]
    manifest.write_text("\n".join(kept) + "\n", encoding="utf-8")
    expect_failure(run_package(package), "E_D0_CONTROL_UNBOUND")


def test_stage_control_must_be_the_packet_bound_file(package):
    root = package["root"]
    stray = root / "reports" / "v1-redesign" / "stage-control-copy.json"
    write_json(stray, load(root, D0_DIR + "/stage-control.json"))
    result = run_package(package, ["--stage-control", "reports/v1-redesign/stage-control-copy.json"])
    expect_failure(result, "E_OWNERSHIP_CONTROL_PATH")


# ---------------------------------------------------------------------------
# Denominators and case identity
# ---------------------------------------------------------------------------


def test_shrunk_v1_denominator_is_rejected(package):
    gates = load(package["root"], "plans/release_gates.json")
    gates["gates"]["V1"]["required_cases"] = gates["gates"]["V1"]["required_cases"][:-1]
    save(package["root"], "plans/release_gates.json", gates)
    refresh_fences(package, ["plans/release_gates.json"])
    expect_failure(run_package(package), "E_DENOM_V1_COUNT")


def test_dropped_legacy_case_breaks_the_prefix(package):
    gates = load(package["root"], "plans/release_gates.json")
    gates["gates"]["V1"]["required_cases"].remove("A05")
    save(package["root"], "plans/release_gates.json", gates)
    refresh_fences(package, ["plans/release_gates.json"])
    expect_failure(run_package(package), "E_LEGACY_PREFIX_V1")


def test_duplicate_ms_case_is_rejected(package):
    gates = load(package["root"], "plans/release_gates.json")
    gates["gates"]["V1"]["required_cases"].append("MS02")
    save(package["root"], "plans/release_gates.json", gates)
    refresh_fences(package, ["plans/release_gates.json"])
    expect_failure(run_package(package), "E_MS_DUPLICATE")


def test_duplicate_ms_case_definition_is_rejected(package):
    cases = load(package["root"], "plans/acceptance_cases.json")
    cases["cases"].append(dict(cases["cases"][1], case_id="MS03"))
    save(package["root"], "plans/acceptance_cases.json", cases)
    refresh_fences(package, ["plans/acceptance_cases.json"])
    expect_failure(run_package(package), "E_MS_DUPLICATE")


def test_plan_must_match_the_release_gate_denominator(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["v1_required_cases"] = plan["v1_required_cases"][:-1]
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_PLAN_V1_CASE_SET")


def test_r22_coverage_gap_is_rejected(package):
    requirements = load(package["root"], "plans/requirements.json")
    requirements["requirements"][0]["acceptance_ids"] = [c for c in MS if c != "MS08"]
    save(package["root"], "plans/requirements.json", requirements)
    refresh_fences(package, ["plans/requirements.json"])
    expect_failure(run_package(package), "E_R22_ACCEPTANCE")


def test_missing_ms_case_is_rejected(package):
    gates = load(package["root"], "plans/release_gates.json")
    gates["gates"]["V1"]["required_cases"].remove("MS08")
    save(package["root"], "plans/release_gates.json", gates)
    refresh_fences(package, ["plans/release_gates.json"])
    expect_failure(run_package(package), "E_MS_MISSING")


def test_plan_duplicate_ms_case_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["v1_required_cases"].append("MS04")
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_MS_DUPLICATE")


# ---------------------------------------------------------------------------
# DAG
# ---------------------------------------------------------------------------


def test_dag_cycle_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["stages"][0]["depends_on"] = ["R1a", "V0-S3", "V1-M1"]
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_DAG_CYCLE")


def test_missing_m1_dependency_on_r1_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["stages"][1]["depends_on"] = []
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_DEP_M1_R1")


def test_missing_r2_dependency_on_m1_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["stages"][2]["depends_on"] = ["R1"]
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_DEP_R2_M1")


# ---------------------------------------------------------------------------
# Thresholds and numeric domain
# ---------------------------------------------------------------------------


def test_relaxed_resource_limit_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["limits"]["gpu_used_mib_exclusive"] = 40960
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_LIMIT_LOOSED")


def test_lowered_ram_floor_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["limits"]["ram_available_mib_min"] = 512
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_LIMIT_LOOSED")


def test_lowered_gpu_free_floor_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["limits"]["gpu_free_mib_min"] = 1024
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_LIMIT_LOOSED")


def test_dropped_fixed_limit_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    del plan["limits"]["shots"]
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_LIMIT_MISSING")


def test_non_finite_limit_is_rejected(package):
    """NaN compares false against every bound; the checker must reject it anyway."""
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["limits"]["single_analysis_seconds"] = float("nan")
    (package["root"] / "plans/v1-revised-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_LIMIT_NOT_FINITE")


def test_infinite_limit_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["limits"]["release_seconds"] = float("inf")
    (package["root"] / "plans/v1-revised-plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_LIMIT_NOT_FINITE")


def test_non_integer_limit_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["limits"]["frames_per_shot"] = 4.5
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_LIMIT_NOT_INTEGER")


def test_quality_threshold_drift_is_rejected(package):
    cases = load(package["root"], "plans/acceptance_cases.json")
    for case in cases["cases"]:
        if case["case_id"] == "MS04":
            case["assertions"] = ["阈值断言 总可用>=9/18", "阈值断言 总>=4可用"]
    save(package["root"], "plans/acceptance_cases.json", cases)
    refresh_fences(package, ["plans/acceptance_cases.json"])
    expect_failure(run_package(package), "E_QUALITY_DRIFT")


# ---------------------------------------------------------------------------
# Design 1.1 budget guards
# ---------------------------------------------------------------------------


def test_guessed_fixed_parent_deadline_is_rejected(package):
    """The 1.0 guess of a flat 1800 s parent budget must not come back."""
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["limits"]["batch_deadline_seconds"] = 1800
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_BUDGET_PARENT_FORMULA")


def test_parent_deadline_max_must_follow_the_formula(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["limits"]["batch_per_child_budget_seconds"] = 900
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_BUDGET_PARENT_FORMULA")


def test_parent_job_budget_range_must_follow_the_formula(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ParentJob"]["properties"]["execution_budget_seconds"]["maximum"] = 1800
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_BUDGET_PARENT_FORMULA")


def test_contract_must_state_the_parent_budget_invariant(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["entities"]["ParentJob"]["invariants"] = ["id=canonical Job.id"]
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_BUDGET_PARENT_FORMULA")


def test_checkpoint_actions_must_add_up(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["checkpoint_budget"]["model_actions_cap"] = 70
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_CHECKPOINT_ACTIONS")


def test_checkpoint_actions_cap_cannot_exceed_the_parent_cap(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["checkpoint_budget"]["model_actions_cap"] = 200
    plan["checkpoint_budget"]["success_calls"] = 193
    plan["checkpoint_budget"]["controlled_actions_cap"] = 7
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_CHECKPOINT_ACTIONS")


def test_checkpoint_must_keep_the_cleanup_reserve(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["checkpoint_budget"]["execution_deadline_seconds"] = 21600
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_CHECKPOINT_WALL")


def test_checkpoint_estimate_must_be_reproducible(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["checkpoint_budget"]["estimated_total_seconds"] = 20000
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_CHECKPOINT_ESTIMATE_ARITHMETIC")


def test_checkpoint_estimate_basis_must_not_claim_a_measured_p95(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["checkpoint_budget"]["estimate_basis"] = "measured per-shot P95 average with a guaranteed worst case"
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_CHECKPOINT_ESTIMATE_BASIS")


def test_checkpoint_calls_must_match_the_success_call_total(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["checkpoint_budget"]["video_calls"] = 40
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_CHECKPOINT_CALLS")


# ---------------------------------------------------------------------------
# Design 1.1 sample allocation
# ---------------------------------------------------------------------------


def test_sample_clip_count_drift_is_rejected(package):
    design = load(package["root"], SAMPLE_REL)
    design["clips"] = design["clips"][:-1]
    save(package["root"], SAMPLE_REL, design)
    refresh_fences(package, [SAMPLE_REL])
    expect_failure(run_package(package), "E_SAMPLE_CLIP_COUNT")


def test_sample_shot_total_drift_is_rejected(package):
    design = load(package["root"], SAMPLE_REL)
    design["clips"][0]["shots"] = 6
    save(package["root"], SAMPLE_REL, design)
    refresh_fences(package, [SAMPLE_REL])
    expect_failure(run_package(package), "E_SAMPLE_SHOT_COUNT")


def test_sample_hard_cut_total_drift_is_rejected(package):
    design = load(package["root"], SAMPLE_REL)
    design["clips"][0]["hard_cut_annotations"] = 3
    save(package["root"], SAMPLE_REL, design)
    refresh_fences(package, [SAMPLE_REL])
    expect_failure(run_package(package), "E_SAMPLE_CUT_COUNT")


def test_sample_quality_subset_must_hold_18_rows(package):
    design = load(package["root"], SAMPLE_REL)
    design["quality_subset"] = design["quality_subset"][:-1]
    save(package["root"], SAMPLE_REL, design)
    refresh_fences(package, [SAMPLE_REL])
    expect_failure(run_package(package), "E_SAMPLE_QUALITY_COUNT")


def test_sample_quality_categories_are_frozen(package):
    design = load(package["root"], SAMPLE_REL)
    design["quality_subset"][0]["category"] = "static"
    save(package["root"], SAMPLE_REL, design)
    refresh_fences(package, [SAMPLE_REL])
    expect_failure(run_package(package), "E_SAMPLE_QUALITY_CATEGORY")


def test_sample_quality_shot_id_must_resolve(package):
    design = load(package["root"], SAMPLE_REL)
    design["quality_subset"][0]["shot_id"] = "S09"
    save(package["root"], SAMPLE_REL, design)
    refresh_fences(package, [SAMPLE_REL])
    expect_failure(run_package(package), "E_SAMPLE_QUALITY_ID")


def test_sample_must_not_pretend_to_be_materialized(package):
    design = load(package["root"], SAMPLE_REL)
    design["clips"][0]["source_sha256"] = "a" * 64
    save(package["root"], SAMPLE_REL, design)
    refresh_fences(package, [SAMPLE_REL])
    expect_failure(run_package(package), "E_SAMPLE_MATERIALIZED")


def test_sample_clip_status_must_stay_pending(package):
    design = load(package["root"], SAMPLE_REL)
    design["clips"][0]["status"] = "FROZEN"
    save(package["root"], SAMPLE_REL, design)
    refresh_fences(package, [SAMPLE_REL])
    expect_failure(run_package(package), "E_SAMPLE_MATERIALIZED")


def test_sample_design_status_must_stay_design_only(package):
    design = load(package["root"], SAMPLE_REL)
    design["status"] = "REAL_FIXTURES_FROZEN"
    save(package["root"], SAMPLE_REL, design)
    refresh_fences(package, [SAMPLE_REL])
    expect_failure(run_package(package), "E_SAMPLE_STATUS")


# ---------------------------------------------------------------------------
# Design 1.1 additive overlay
# ---------------------------------------------------------------------------


def test_overlay_cannot_replace_an_existing_method(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["add_paths"]["/api/v1/scenes/{id}"]["put"] = {"operationId": "put_api_v1_scene"}
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_REPLACES_METHOD")


def test_overlay_cannot_touch_the_reserved_v2_batch_route(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["add_paths"]["/api/v1/jobs/batch"] = {"post": {"operationId": "post_api_v1_jobs_batch"}}
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_RESERVED_PATH")


def test_overlay_components_block_is_rejected(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["components"] = {"schemas": {"Job": {"type": "object", "required": ["invented"]}}}
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_COMPONENTS_REPLACE")


def test_overlay_cannot_reference_an_unknown_candidate_component(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["add_paths"]["/api/v1/jobs/{id}/children"]["get"]["responses"]["200"] = {
        "description": "OK",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/MultiShot_NotADto"}}},
    }
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_COMPONENT_UNKNOWN")


def test_overlay_must_keep_the_bounded_shot_batch_route(package):
    overlay = load(package["root"], OVERLAY_REL)
    del overlay["add_paths"]["/api/v1/jobs/shot-batches"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_ROUTE_MISSING")


def test_overlay_metadata_may_not_replace_the_existing_body(package):
    # design 1.1.1: the flat prose metadata map became a per method map that may
    # only carry the two allowlisted x- keys. The old "the body changed" claim
    # is now an unauthorized metadata key, so the same intent - the overlay may
    # not replace the existing body - is enforced by a stricter rule.
    overlay = load(package["root"], OVERLAY_REL)
    overlay["metadata_only"]["/api/v1/scenes/{id}"]["put"]["put_body_response_unchanged"] = False
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_METADATA_KEY")


def test_canonical_v2_batch_body_must_stay_untouched(package):
    api = load(package["root"], "contracts/openapi.json")
    api["paths"]["/api/v1/jobs/batch"]["post"]["requestBody"]["content"]["application/json"]["schema"] = {
        "type": "object",
        "properties": {"shot_ids": {"type": "array", "items": {"type": "string"}}},
        "required": ["shot_ids"],
    }
    save(package["root"], "contracts/openapi.json", api)
    refresh_fences(package, ["contracts/openapi.json"])
    expect_failure(run_package(package), "E_V2_BATCH_BODY_DRIFT")


# ---------------------------------------------------------------------------
# Design 1.1 canonical compatibility and DTO shape
# ---------------------------------------------------------------------------


def test_canonical_scene_alias_must_be_exact(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["CoreScene"]["properties"]["verified"] = {"type": "boolean", "default": True}
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_CANONICAL_ALIAS")


def test_shot_frame_ref_may_not_widen_the_canonical_frame_ref(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ShotFrameRef"]["properties"]["source_pts"] = {
        "anyOf": [{"type": "integer"}, {"type": "null"}]
    }
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_FRAME_REF_CONSTRAINT")


def test_shot_frame_ref_may_not_invent_a_time_basis(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ShotFrameRef"]["properties"]["time_basis"] = {"const": "sample_target"}
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_FRAME_REF_CONSTRAINT")


def test_shot_frame_ref_may_not_drop_a_canonical_field(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    del schema["$defs"]["ShotFrameRef"]["properties"]["time_base_den"]
    schema["$defs"]["ShotFrameRef"]["required"] = [
        field for field in schema["$defs"]["ShotFrameRef"]["required"] if field != "time_base_den"
    ]
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_FRAME_REF_INCOMPATIBLE")


def test_retained_frame_reference_must_stay_a_valid_candidate_instance(package):
    sample = load(package["root"], FRAME_SAMPLE_REL)
    sample["frames"][1]["time_basis"] = "sample_target"
    save(package["root"], FRAME_SAMPLE_REL, sample)
    refresh_fences(package, [FRAME_SAMPLE_REL])
    expect_failure(run_package(package), "E_FRAME_REF_INSTANCE")


def test_public_binding_must_not_leak_the_lease_token(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["PublicAnalysisBinding"]["properties"]["lease_token"] = {"type": "string"}
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_PUBLIC_BINDING_LEASE_TOKEN")


def test_evidence_must_bind_the_public_analysis_binding(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ShotAnalysisEvidence"]["properties"]["binding"] = {"$ref": "#/$defs/AnalysisBinding"}
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_PUBLIC_BINDING_REF")


def test_contract_entity_without_a_dto_is_rejected(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["entities"]["SceneRevision"] = {"required": ["id", "media_ref_id"]}
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_CONTRACT_ENTITY_UNRESOLVED")


def test_parent_dto_must_carry_the_deadline_and_the_counts(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ParentJob"]["required"] = [
        field for field in schema["$defs"]["ParentJob"]["required"] if field != "deadline_at"
    ]
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_PARENT_DTO_FIELD")


def test_children_envelope_must_carry_the_parent_and_the_children(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["BatchChildrenResponse"]["required"] = ["children"]
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_CHILDREN_ENVELOPE")


def test_child_rows_must_carry_model_started_and_the_error_code(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ChildSummary"]["required"] = [
        field for field in schema["$defs"]["ChildSummary"]["required"] if field != "model_started"
    ]
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_CHILD_ROW_FIELDS")


def test_domain_dtos_must_declare_observation_and_inference(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["Action"]["properties"]["domain"] = {"enum": ["observation"]}
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_DOMAIN_DTO_FIELDS")


def test_model_response_must_not_carry_frame_refs(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["MachineShotResponse"]["properties"]["frame_refs"] = {"type": "array"}
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_MODEL_RESPONSE_SCOPE")


# ---------------------------------------------------------------------------
# Ownership, human signature, authorization
# ---------------------------------------------------------------------------


def test_write_path_ownership_violation_is_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    for workpack in control["workpacks"]:
        if workpack["id"] == "D0-B-IMPL":
            workpack["allowed_files"] = list(checker.FROZEN_D0_ALLOWED_FILES) + ["lvw/"]
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_ALLOWED_FILES")


def test_unseparated_roles_are_rejected(package):
    control = load(package["root"], D0_DIR + "/stage-control.json")
    control["roles"]["independent_reviewer"] = control["roles"]["implementation_owner"]
    save(package["root"], D0_DIR + "/stage-control.json", control)
    expect_failure(run_package(package), "E_OWNERSHIP_ROLE")


def test_false_human_signature_in_plan_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["human_signoff"] = {"decision": "APPROVED", "signer": "project-owner"}
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_HUMAN_APPROVAL_CLAIM")


def test_false_human_acceptance_in_approval_is_rejected(package):
    approval = load(package["root"], APPROVAL_REL)
    approval["human_acceptance_of_621b1bf"] = True
    save(package["root"], APPROVAL_REL, approval)
    refresh_fences(package, [APPROVAL_REL])
    expect_failure(run_package(package), "E_HUMAN_APPROVAL_CLAIM")


def test_execution_control_must_not_carry_a_human_signoff(package):
    control = load(package["root"], "plans/execution-control.json")
    control["human_signoff"] = {"decision": "APPROVED", "signer": "project-owner"}
    save(package["root"], "plans/execution-control.json", control)
    refresh_fences(package, ["plans/execution-control.json"])
    expect_failure(run_package(package), "E_HUMAN_APPROVAL_CLAIM")


def test_execution_control_must_not_carry_a_product_acceptance(package):
    control = load(package["root"], "plans/execution-control.json")
    control["product_acceptance"] = {"decision": "ACCEPTED"}
    save(package["root"], "plans/execution-control.json", control)
    refresh_fences(package, ["plans/execution-control.json"])
    expect_failure(run_package(package), "E_FORBIDDEN_CLAIM")


def test_adjudication_must_not_claim_a_product_pass(package):
    adjudication = load(package["root"], ADJUDICATION_REL)
    adjudication["product_pass"] = True
    save(package["root"], ADJUDICATION_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_REL])
    expect_failure(run_package(package), "E_ADJUDICATION_CLAIM")


def test_invented_completion_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["stages"][1]["completed"] = 3
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_COMPLETED_CLAIM")


def test_forbidden_release_claim_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["status"] = "V1_ACCEPTED"
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_PLAN_STATUS_INVALID")


def test_budget_reset_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["budget_reset"] = True
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_BUDGET_RESET")


def test_unauthorized_stage_alias_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["authorization_accounting"]["design_stage"] = "V2"
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_STAGE_ALIAS")


def test_authority_stage_alias_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["authorization_accounting"]["authority_stage"] = "V3"
    save(package["root"], "plans/v1-revised-plan.json", plan)
    refresh_fences(package, ["plans/v1-revised-plan.json"])
    expect_failure(run_package(package), "E_STAGE_ALIAS")


def test_scope_hash_drift_is_rejected(package):
    approval = load(package["root"], APPROVAL_REL)
    approval["note"] = "scope file changed after the fence was frozen"
    save(package["root"], APPROVAL_REL, approval)
    result = run_package(package)
    expect_failure(result, "E_SPEC_FENCE_DRIFT")
    expect_failure(result, "E_SCOPE_HASH_DRIFT")


# ---------------------------------------------------------------------------
# Design-review status honesty
# ---------------------------------------------------------------------------


def test_new_ms_case_may_not_claim_pass(package):
    """PASS is legal in the general enum, but not at the design-review phase."""
    cases = load(package["root"], "plans/acceptance_cases.json")
    for case in cases["cases"]:
        if case["case_id"] == "MS04":
            case["status"] = "PASS"
    save(package["root"], "plans/acceptance_cases.json", cases)
    refresh_fences(package, ["plans/acceptance_cases.json"])
    result = run_package(package)
    expect_failure(result, "E_MS_STATUS_CLAIM")


def test_new_m1_stage_may_not_claim_pass(package):
    tasks = load(package["root"], "plans/tasks.json")
    for stage in tasks["stages"]:
        if stage["stage_id"] == "V1-M1":
            stage["status"] = "PASS"
    save(package["root"], "plans/tasks.json", tasks)
    refresh_fences(package, ["plans/tasks.json"])
    expect_failure(run_package(package), "E_STAGE_STATUS_CLAIM")


def test_r22_may_not_claim_pass(package):
    requirements = load(package["root"], "plans/requirements.json")
    requirements["requirements"][0]["status"] = "PASS"
    save(package["root"], "plans/requirements.json", requirements)
    refresh_fences(package, ["plans/requirements.json"])
    expect_failure(run_package(package), "E_R22_STATUS")


# ---------------------------------------------------------------------------
# Candidate artefacts: declared and hash bound, never executed
# ---------------------------------------------------------------------------


def test_candidate_migration_must_stay_declared(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["storage_migration"] = "contracts/some-other-migration.sql"
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_ARTIFACT_DECLARATION")


def test_candidate_migration_must_stay_hash_bound(package):
    spec = load(package["root"], D0_DIR + "/spec-manifest.json")
    del spec["files"][MIGRATION_REL]
    save(package["root"], D0_DIR + "/spec-manifest.json", spec)
    package["d0_manifest_sha256"] = regenerate_d0_manifest(package["root"])
    expect_failure(run_package(package), "E_ARTIFACT_NOT_HASH_BOUND")


def test_candidate_migration_must_keep_the_parent_budget_constraint(package):
    sql = (package["root"] / MIGRATION_REL).read_text(encoding="utf-8")
    sql = sql.replace("CHECK(execution_budget_seconds=450*planned_count+90)", "CHECK(execution_budget_seconds>0)")
    (package["root"] / MIGRATION_REL).write_text(sql, encoding="utf-8")
    refresh_fences(package, [MIGRATION_REL])
    expect_failure(run_package(package), "E_SQL_DECLARATION")


def test_candidate_migration_must_declare_the_batch_tables(package):
    sql = (package["root"] / MIGRATION_REL).read_text(encoding="utf-8")
    sql = "\n".join(line for line in sql.splitlines() if "shot_batch_seal" not in line)
    (package["root"] / MIGRATION_REL).write_text(sql + "\n", encoding="utf-8")
    refresh_fences(package, [MIGRATION_REL])
    expect_failure(run_package(package), "E_SQL_DECLARATION")


def test_candidate_migration_may_not_reach_outside_its_database(package):
    sql = (package["root"] / MIGRATION_REL).read_text(encoding="utf-8")
    (package["root"] / MIGRATION_REL).write_text(
        sql + "ATTACH DATABASE 'file:other.db' AS other;\n", encoding="utf-8"
    )
    refresh_fences(package, [MIGRATION_REL])
    expect_failure(run_package(package), "E_SQL_FORBIDDEN")


def test_candidate_migration_may_not_drop_product_tables(package):
    sql = (package["root"] / MIGRATION_REL).read_text(encoding="utf-8")
    (package["root"] / MIGRATION_REL).write_text(
        sql + "DROP TABLE shot_scene_binding;\n", encoding="utf-8"
    )
    refresh_fences(package, [MIGRATION_REL])
    expect_failure(run_package(package), "E_SQL_FORBIDDEN")


# ---------------------------------------------------------------------------
# Protected artefacts
# ---------------------------------------------------------------------------


def test_canonical_contract_drift_is_rejected(package):
    path = package["root"] / "contracts/openapi.json"
    path.write_text(json.dumps({"openapi": "3.1.0", "changed": True}) + "\n", encoding="utf-8")
    expect_failure(run_package(package), "E_CONTRACT_DRIFT")


def test_old_r1_packet_drift_is_rejected(package):
    path = package["root"] / R1_DIR / "stage-control.json"
    path.write_text(json.dumps({"stage_id": "R1", "frozen": False}) + "\n", encoding="utf-8")
    expect_failure(run_package(package), "E_R1_FILE_DRIFT")


def test_spec_fence_drift_is_rejected(package):
    plan = load(package["root"], "plans/v1-revised-plan.json")
    plan["next_action"] = "changed without re-freezing the authority manifest"
    save(package["root"], "plans/v1-revised-plan.json", plan)
    expect_failure(run_package(package), "E_SPEC_FENCE_DRIFT")


def test_spec_fence_must_cover_the_authority_inputs(package):
    spec = load(package["root"], D0_DIR + "/spec-manifest.json")
    del spec["files"]["docs/32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md"]
    save(package["root"], D0_DIR + "/spec-manifest.json", spec)
    package["d0_manifest_sha256"] = regenerate_d0_manifest(package["root"])
    expect_failure(run_package(package), "E_SPEC_FENCE_INCOMPLETE")


# ---------------------------------------------------------------------------
# Candidate contract and schema
# ---------------------------------------------------------------------------


def test_contract_schema_mismatch_is_rejected(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["entities"]["SceneRevisionInfo"]["required"] = ["scene_revision_id", "scene_id"]
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_CONTRACT_SCHEMA_MISMATCH")


def test_schema_without_closed_dtos_is_rejected(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["SceneRevisionInfo"]["additionalProperties"] = True
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_SCHEMA_DTO")


def test_missing_input_exits_nonzero_without_verdict(package):
    result = subprocess.run(
        [sys.executable, "-B", str(CHECKER), "--root", str(package["root"]), "--plan", "plans/missing.json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "INPUT_ERROR" in result.stderr
    assert "RESULT: PASS" not in result.stdout


# ---------------------------------------------------------------------------
# Design 1.1.1: the six owner corrections N1-N6
#
# The owner corrections are checked here, but they are not accepted here: the
# adjudication states that they await an independent recheck. Every negative
# test mutates a *copy* and asserts the decision the real checker makes.
# ---------------------------------------------------------------------------


def test_d0_packet_pin_is_the_owner_supplied_112_digest():
    # The pin is a hard coded source control digest, not a value that is
    # derived from the packet at run time.
    assert checker.FROZEN_D0_PACKET_MANIFEST_SHA256 == "181c08ee7290f5bef02e22b6f7fd3c874c2d404cc8b4ffff84d2148a71f47eb8"


def test_stale_1_1_packet_pin_no_longer_validates_the_owner_packet():
    # The 1.1 owner digest is no longer the pin; the 1.1.2 digest is.
    result = run_checker(ROOT, OLD_D0_MANIFEST_1_1_SHA256)
    assert result.returncode != 0
    assert "E_D0_PACKET_MANIFEST_PINNED" in result.stdout


def test_stale_1_1_1_packet_pin_no_longer_validates_the_owner_packet():
    # The 1.1.1 owner digest is no longer the pin either: the 1.1.2 packet
    # replaced it, so the old pin must reject the new packet.
    result = run_checker(ROOT, OLD_D0_MANIFEST_1_1_1_SHA256)
    assert result.returncode != 0
    assert "E_D0_PACKET_MANIFEST_PINNED" in result.stdout


def test_stale_1_0_packet_pin_no_longer_validates_the_owner_packet():
    # The 1.0 owner digest is no longer the pin either.
    result = run_checker(ROOT, OLD_D0_MANIFEST_SHA256)
    assert result.returncode != 0
    assert "E_D0_PACKET_MANIFEST_PINNED" in result.stdout


def test_authority_spec_fence_holds_exactly_the_frozen_inventory(package):
    spec = load(package["root"], D0_DIR + "/spec-manifest.json")
    assert len(spec["files"]) == 25
    assert sorted(spec["files"]) == sorted(checker.FROZEN_SPEC_FENCE_FILES)
    assert len(checker.FROZEN_D0_PACKET_FILES) == 10


def test_spec_fence_may_not_grow(package):
    spec = load(package["root"], D0_DIR + "/spec-manifest.json")
    spec["files"]["reports/v1-redesign/legacy-gates-before-change.json.bak"] = "0" * 64
    save(package["root"], D0_DIR + "/spec-manifest.json", spec)
    package["d0_manifest_sha256"] = regenerate_d0_manifest(package["root"])
    expect_failure(run_package(package), "E_SPEC_FENCE_EXTRA_ENTRY")


def test_spec_fence_may_not_shrink(package):
    spec = load(package["root"], D0_DIR + "/spec-manifest.json")
    del spec["files"]["docs/17_DATA_AND_VERSIONING.md"]
    save(package["root"], D0_DIR + "/spec-manifest.json", spec)
    package["d0_manifest_sha256"] = regenerate_d0_manifest(package["root"])
    expect_failure(run_package(package), "E_SPEC_FENCE_INCOMPLETE")


# --- N1: the strong ETag and the strict merge rule -------------------------


def test_new_scene_get_must_declare_the_strong_etag(package):
    overlay = load(package["root"], OVERLAY_REL)
    del overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["headers"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_ETAG_MISSING")


def test_revision_info_get_must_declare_the_strong_etag(package):
    overlay = load(package["root"], OVERLAY_REL)
    del overlay["add_paths"]["/api/v1/scenes/{id}/revision-info"]["get"]["responses"]["200"]["headers"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_ETAG_MISSING")


def test_existing_scene_put_must_receive_the_etag_through_add_response_headers(package):
    overlay = load(package["root"], OVERLAY_REL)
    del overlay["add_response_headers"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_ETAG_MISSING")


def test_etag_pattern_may_not_drift_from_the_frozen_strong_format(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["headers"]["ETag"]["schema"]["pattern"] = ".*"
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_ETAG_FORMAT")


def test_etag_pattern_may_not_accept_a_weak_tag(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["headers"]["ETag"]["schema"]["pattern"] = '^(W/)?"scene:[^":]+:[0-9a-f]{64}"$'
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_ETAG_WEAK")


def test_response_header_may_not_collide_with_the_canonical_one(package):
    api = load(package["root"], "contracts/openapi.json")
    api["paths"]["/api/v1/scenes/{id}"]["put"]["responses"]["200"]["headers"] = {"ETag": {"schema": {"type": "string"}}}
    save(package["root"], "contracts/openapi.json", api)
    refresh_fences(package, ["contracts/openapi.json"])
    expect_failure(run_package(package), "E_OVERLAY_HEADER_COLLISION")


def test_response_header_may_not_be_unauthorized(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["add_response_headers"]["/api/v1/scenes/{id}"]["put"]["200"]["X-Internal-Token"] = {"schema": {"type": "string"}}
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_HEADER_NOT_ALLOWED")


def test_response_header_target_must_exist(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["add_response_headers"]["/api/v1/scenes/{id}"]["delete"] = {"200": {"ETag": etag_header()}}
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_HEADER_TARGET_MISSING")


def test_metadata_target_must_exist(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["metadata_only"]["/api/v1/scenes/{id}"]["delete"] = v1_annotation()
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_METADATA_TARGET_MISSING")


def test_metadata_may_not_replace_the_canonical_x_product_version(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["metadata_only"]["/api/v1/scenes/{id}"]["put"]["x-product-version"] = "V1"
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_METADATA_KEY")


def test_merge_may_not_change_the_canonical_operation_body(package):
    # The overlay may not smuggle a body change into a canonical operation.
    overlay = load(package["root"], OVERLAY_REL)
    overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["content"] = {"application/json": {"schema": {"$ref": "#/components/schemas/Scene"}}}
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    result = run_package(package)
    # design 1.1.2 (NM-2): the new GET is an addition, not a replacement, but
    # it must keep the canonical success envelope around the canonical Scene.
    # The envelope the mutation installs is a bare component reference, so the
    # package is now rejected.
    assert result.returncode != 0, result.stdout
    assert "E_SCENE_GET_ENVELOPE" in result.stdout
    # The canonical PUT itself was not touched by the overlay: the merge
    # guard did not fire.
    assert "E_OVERLAY_BASE_MUTATED" not in result.stdout


def test_canonical_operation_is_byte_identical_after_the_merge(package):
    api = load(package["root"], "contracts/openapi.json")
    overlay = load(package["root"], OVERLAY_REL)
    result = run_package(package)
    assert result.returncode == 0, result.stdout
    # The canonical PUT keeps its own body, parameters, status code and
    # x-product-version: the overlay only adds an ETag header and two x- keys.
    canonical = api["paths"]["/api/v1/scenes/{id}"]["put"]
    assert canonical["x-product-version"] == "V2"
    assert "headers" not in canonical["responses"]["200"]
    assert overlay["add_response_headers"]["/api/v1/scenes/{id}"]["put"]["200"]["ETag"]["schema"]["pattern"] == ETAG_PATTERN


# --- N2: the additive surface ----------------------------------------------


def test_contract_additive_paths_must_match_the_overlay(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["additive_paths"].remove("/api/v1/scenes/{id}")
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_ADDITIVE_PATHS")


def test_contract_additive_operations_must_match_the_overlay(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["additive_operations"] = [
        entry for entry in contract["additive_operations"]
        if not (entry["path"] == "/api/v1/scenes/{id}" and entry["method"] == "GET")
    ]
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_ADDITIVE_OPERATIONS")


def test_overlay_additive_surface_is_frozen(package):
    overlay = load(package["root"], OVERLAY_REL)
    del overlay["add_paths"]["/api/v1/scenes/{id}/revision-info"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_ADDITIVE_SURFACE")


def test_additive_surface_may_not_shrink_to_the_path_names_only(package):
    # The new GET on the *existing* Scene path must stay part of the surface.
    overlay = load(package["root"], OVERLAY_REL)
    del overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_ADDITIVE_SURFACE")


# --- N3: the reuse annotations ---------------------------------------------


def test_every_reuse_path_must_be_annotated(package):
    overlay = load(package["root"], OVERLAY_REL)
    del overlay["metadata_only"]["/api/v1/shots"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_REUSE_METADATA")


def test_every_reuse_method_must_be_annotated(package):
    overlay = load(package["root"], OVERLAY_REL)
    del overlay["metadata_only"]["/api/v1/shots/{id}"]["put"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_REUSE_METADATA")


def test_reuse_annotation_keys_are_allowlisted(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["metadata_only"]["/api/v1/jobs/{id}"]["get"]["x-legacy-note"] = "anything"
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_METADATA_KEY")


def test_reuse_annotation_may_not_collide_with_an_existing_key(package):
    api = load(package["root"], "contracts/openapi.json")
    api["paths"]["/api/v1/jobs/{id}"]["get"]["x-v1-profile"] = "local-shot-v1"
    save(package["root"], "contracts/openapi.json", api)
    refresh_fences(package, ["contracts/openapi.json"])
    expect_failure(run_package(package), "E_OVERLAY_METADATA_COLLISION")


def test_reuse_annotation_profile_value_is_frozen(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["metadata_only"]["/api/v1/jobs/{id}"]["get"]["x-v1-profile"] = "local-shot-v2"
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_METADATA_VALUE")


def test_reuse_annotation_may_not_deny_the_v2_semantics(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["metadata_only"]["/api/v1/jobs/{id}"]["get"]["x-v2-semantics-unchanged"] = False
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    expect_failure(run_package(package), "E_OVERLAY_METADATA_VALUE")


def test_contract_reuse_paths_must_match_the_overlay(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["reuse_paths"].remove("/api/v1/shots/{id}")
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_REUSE_PATHS")


# --- N4: the per shot frame reference -------------------------------------


def test_shot_frame_ref_may_not_reintroduce_the_null_branch(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ShotFrameRef"]["properties"]["source_pts"] = {
        "anyOf": [{"type": "integer"}, {"type": "null"}],
        "type": "integer",
    }
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_FRAME_REF_CONSTRAINT")


def test_shot_frame_ref_timebase_must_stay_positive(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ShotFrameRef"]["properties"]["time_base_den"] = {"type": "integer", "minimum": 0}
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_FRAME_REF_CONSTRAINT")


def test_shot_frame_ref_pts_must_stay_an_integer(package):
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ShotFrameRef"]["properties"]["source_pts"] = {"type": "number"}
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_package(package), "E_FRAME_REF_CONSTRAINT")


# --- N5: the canonical domain mapping --------------------------------------


def test_domain_language_order_is_frozen(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["language_order"] = ["en", "zh"]
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_DOMAIN_MAPPING")


def test_domain_serialization_rule_may_not_drop_the_raw_promise(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["entry_serialization"] = (
        "Each nonempty language value produces one string: compact UTF-8 JSON object, "
        "sorted keys, ensure_ascii=False, allow_nan=False. Keys kind, ref, lang, text."
    )
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_DOMAIN_MAPPING")


def test_domain_serialization_rule_may_not_translate(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["entry_serialization"] = (
        "Each nonempty language value produces one string: compact UTF-8 JSON object, sorted keys, "
        "ensure_ascii=False, allow_nan=False. Keys kind, ref, lang, text. Translate to English, "
        "trim and deduplicate. Preserve the raw model response byte-for-byte."
    )
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_DOMAIN_MAPPING")


def test_domain_example_must_match_the_deterministic_serialization(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["example"]["observation"][0] = (
        '{"kind":"character","lang":"zh","ref":"actor1","text":"红衣"}'
    )
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_DOMAIN_MAPPING")


def test_domain_example_may_not_omit_a_language_entry(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    del contract["canonical_domain_mapping"]["example"]["observation"][1]
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_DOMAIN_MAPPING")


def test_human_domains_must_stay_untouched(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["human_domains"] = "Overwrite user_evidence with the model output."
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_DOMAIN_MAPPING")


def test_item_order_rule_may_not_drop_the_unicode_sort(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["item_order"] = (
        "characters sorted by local_actor_id, then scene, then actions in original zero-based "
        "array order; route each item only to its declared observation or inference domain"
    )
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_DOMAIN_MAPPING")


# --- N6: the scene hash column mapping ------------------------------------


def test_scene_hash_column_mapping_must_cover_every_field(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    del contract["scene_hash"]["column_mapping"]["time_basis"]
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_scene_hash_timebase_aliases_are_frozen(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["scene_hash"]["column_mapping"]["time_base_num"] = "scene_revision.time_base_num"
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_scene_hash_revision_alias_is_frozen(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["scene_hash"]["column_mapping"]["revision"] = "scene_revision_meta.revision"
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_scene_hash_verified_conversion_must_survive(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["scene_hash"]["column_mapping"]["verified"] = "scene_revision_meta.verified"
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_scene_hash_may_not_use_the_sql_alias_as_a_json_key(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["scene_hash"]["column_mapping"]["tb_num"] = "scene_revision.tb_num"
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_scene_hash_field_set_is_frozen(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["scene_hash"]["fields"].remove("editor")
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    expect_failure(run_package(package), "E_SCENE_HASH_MAPPING")


# --- the owner adjudication and the product coordinate ---------------------


def test_owner_corrections_may_not_be_recorded_as_accepted(package):
    adjudication = load(package["root"], ADJUDICATION_111_REL)
    adjudication["findings"][0]["state"] = "ACCEPTED"
    save(package["root"], ADJUDICATION_111_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_111_REL])
    expect_failure(run_package(package), "E_111_ADJUDICATION")


def test_owner_adjudication_may_not_claim_the_product_gate(package):
    adjudication = load(package["root"], ADJUDICATION_111_REL)
    adjudication["product_gate0"] = True
    save(package["root"], ADJUDICATION_111_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_111_REL])
    expect_failure(run_package(package), "E_111_ADJUDICATION")


def test_owner_adjudication_may_not_claim_a_materialized_sample(package):
    adjudication = load(package["root"], ADJUDICATION_111_REL)
    adjudication["sample_materialization"] = "DONE"
    save(package["root"], ADJUDICATION_111_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_111_REL])
    expect_failure(run_package(package), "E_111_ADJUDICATION")


def test_product_coordinate_must_stay_in_the_r1_human_gate(package):
    control = load(package["root"], "plans/execution-control.json")
    control["coordinate"]["state"] = "GATE0_PASS"
    save(package["root"], "plans/execution-control.json", control)
    refresh_fences(package, ["plans/execution-control.json"])
    expect_failure(run_package(package), "E_PRODUCT_COORDINATE")


# ---------------------------------------------------------------------------
# The real owner package, copied and mutated
#
# The synthetic fixture above proves the rules on a hand written tree. These
# tests take the *actual* owner artefacts (authority 743e028), copy them into
# a temporary directory, mutate one artefact and assert the decision the real
# checker makes on that copy.
# ---------------------------------------------------------------------------


def owner_copy_files() -> list[str]:
    relatives = set(json.loads((ROOT / D0_DIR / "spec-manifest.json").read_text(encoding="utf-8"))["files"])
    relatives.add(D0_DIR + "/PAYLOAD_MANIFEST.sha256")
    for name in checker.FROZEN_D0_PACKET_FILES:
        relatives.add(D0_DIR + "/" + name)
    for line in (ROOT / R1_DIR / "PAYLOAD_MANIFEST.sha256").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            relatives.add(R1_DIR + "/" + line.split(None, 1)[1].strip())
    relatives.add(FRAME_SAMPLE_REL)
    return sorted(relatives)


@pytest.fixture()
def owner_copy(tmp_path):
    root = tmp_path / "owner"
    root.mkdir()
    for rel in owner_copy_files():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / rel).read_bytes())
    state = {"root": root}
    state["d0_manifest_sha256"] = sha256(root / D0_DIR / "PAYLOAD_MANIFEST.sha256")
    return state


def refresh_owner_fences(state: dict, rels=()) -> None:
    root = state["root"]
    spec_path = root / D0_DIR / "spec-manifest.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    for rel in rels:
        spec["files"][rel] = sha256(root / rel)
    write_json(spec_path, spec)
    state["d0_manifest_sha256"] = regenerate_d0_manifest(root)


def run_owner_copy(state: dict, extra=None):
    return run_checker(state["root"], state["d0_manifest_sha256"], extra)


def test_real_owner_package_validates_read_only(owner_copy):
    result = run_owner_copy(owner_copy)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: PASS" in result.stdout


def test_real_owner_overlay_without_the_etag_is_rejected(owner_copy):
    overlay = load(owner_copy["root"], OVERLAY_REL)
    del overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["headers"]
    save(owner_copy["root"], OVERLAY_REL, overlay)
    refresh_owner_fences(owner_copy, [OVERLAY_REL])
    expect_failure(run_owner_copy(owner_copy), "E_ETAG_MISSING")


def test_real_owner_overlay_with_a_weak_etag_pattern_is_rejected(owner_copy):
    overlay = load(owner_copy["root"], OVERLAY_REL)
    overlay["add_response_headers"]["/api/v1/scenes/{id}"]["put"]["200"]["ETag"]["schema"]["pattern"] = ".*"
    save(owner_copy["root"], OVERLAY_REL, overlay)
    refresh_owner_fences(owner_copy, [OVERLAY_REL])
    expect_failure(run_owner_copy(owner_copy), "E_ETAG_FORMAT")


def test_real_owner_contract_without_the_new_scene_get_is_rejected(owner_copy):
    contract = load(owner_copy["root"], "plans/v1-multishot-contract.json")
    contract["additive_operations"] = [
        entry for entry in contract["additive_operations"]
        if not (entry["path"] == "/api/v1/scenes/{id}" and entry["method"] == "GET")
    ]
    save(owner_copy["root"], "plans/v1-multishot-contract.json", contract)
    refresh_owner_fences(owner_copy, ["plans/v1-multishot-contract.json"])
    expect_failure(run_owner_copy(owner_copy), "E_ADDITIVE_OPERATIONS")


def test_real_owner_overlay_without_a_reuse_annotation_is_rejected(owner_copy):
    overlay = load(owner_copy["root"], OVERLAY_REL)
    del overlay["metadata_only"]["/api/v1/jobs/{id}/cancel"]
    save(owner_copy["root"], OVERLAY_REL, overlay)
    refresh_owner_fences(owner_copy, [OVERLAY_REL])
    expect_failure(run_owner_copy(owner_copy), "E_REUSE_METADATA")


def test_real_owner_schema_with_the_null_branch_is_rejected(owner_copy):
    schema = load(owner_copy["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ShotFrameRef"]["properties"]["time_base_num"] = {
        "anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}],
        "type": "integer",
    }
    save(owner_copy["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_owner_fences(owner_copy, ["contracts/v1-multishot.schema.json"])
    expect_failure(run_owner_copy(owner_copy), "E_FRAME_REF_CONSTRAINT")


def test_real_owner_domain_example_must_match_its_own_rule(owner_copy):
    contract = load(owner_copy["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["example"]["observation"][0] = (
        '{"kind":"character","lang":"zh","ref":"actor1","text":"blue"}'
    )
    save(owner_copy["root"], "plans/v1-multishot-contract.json", contract)
    refresh_owner_fences(owner_copy, ["plans/v1-multishot-contract.json"])
    expect_failure(run_owner_copy(owner_copy), "E_DOMAIN_MAPPING")


def test_real_owner_scene_hash_alias_drift_is_rejected(owner_copy):
    contract = load(owner_copy["root"], "plans/v1-multishot-contract.json")
    contract["scene_hash"]["column_mapping"]["time_base_den"] = "scene_revision.time_base_den"
    save(owner_copy["root"], "plans/v1-multishot-contract.json", contract)
    refresh_owner_fences(owner_copy, ["plans/v1-multishot-contract.json"])
    expect_failure(run_owner_copy(owner_copy), "E_SCENE_HASH_MAPPING")


def test_real_owner_merge_keeps_the_canonical_scene_put(owner_copy):
    api = load(owner_copy["root"], "contracts/openapi.json")
    before = json.dumps(api["paths"]["/api/v1/scenes/{id}"]["put"], sort_keys=True)
    result = run_owner_copy(owner_copy)
    assert result.returncode == 0, result.stdout + result.stderr
    after = json.dumps(load(owner_copy["root"], "contracts/openapi.json")["paths"]["/api/v1/scenes/{id}"]["put"], sort_keys=True)
    assert before == after


# ---------------------------------------------------------------------------
# Design 1.1.2: the consolidated correction of NM-1 - NM-8
#
# Every test drives the real CLI on a copy and asserts the decision the real
# checker makes. The reviewer owned probes P01, P02, P05, P22, P23 and P24
# are turned into regression tests here, together with the obligations the
# design 1.1.1 suite already carried. No prior hard negative was removed.
# ---------------------------------------------------------------------------


def assert_clean_failure(result, code: str):
    """The run failed with a deterministic finding, not with a traceback."""
    assert result.returncode != 0, "checker exited 0 for a faulty package:\n%s" % result.stdout
    assert code in result.stdout, "expected %s in output:\n%s" % (code, result.stdout)
    assert result.stdout.strip(), "a failed run must not leave stdout empty"
    assert "Traceback" not in result.stderr, "the run leaked a traceback:\n%s" % result.stderr
    assert "RESULT: PASS" not in result.stdout


def mutate_migration(package: dict, old: str, new: str) -> None:
    """Rewrite one fragment of the candidate migration and re-freeze it."""
    path = package["root"] / MIGRATION_REL
    text = path.read_text(encoding="utf-8")
    assert old in text, "the migration does not carry %r" % old
    path.write_text(text.replace(old, new), encoding="utf-8")
    refresh_fences(package, [MIGRATION_REL])


# --- NM-1: the 11 scene hash aliases ---------------------------------------


@pytest.mark.parametrize("field", sorted(checker.FROZEN_SCENE_HASH_COLUMN_ALIASES))
def test_every_scene_hash_alias_is_pinned_to_its_frozen_mapping(package, field):
    # NM-1: all 11 aliases are bound to their exact frozen mapping value. The
    # design 1.1.1 checker pinned only three of them.
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["scene_hash"]["column_mapping"][field] = "scene_revision.some_other_column"
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    assert_clean_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_the_scene_hash_mapping_covers_all_eleven_fields(package):
    # The frozen inventory really holds 11 fields and 11 aliases.
    assert len(checker.FROZEN_SCENE_HASH_FIELDS) == 11
    assert len(checker.FROZEN_SCENE_HASH_COLUMN_ALIASES) == 11
    assert sorted(checker.FROZEN_SCENE_HASH_COLUMN_ALIASES) == sorted(checker.FROZEN_SCENE_HASH_FIELDS)


def test_the_scene_hash_sql_call_site_may_not_permute_the_pts(package):
    # NM-1 / reviewer probe P02: the permuted PTS arguments of the backfill
    # call site must be rejected, not silently hashed into another value.
    mutate_migration(package, "s.start_pts,s.end_pts", "s.end_pts,s.start_pts")
    assert_clean_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_the_scene_hash_sql_call_site_may_not_swap_two_arguments(package):
    mutate_migration(package, "m.sha256,s.version", "s.version,m.sha256")
    assert_clean_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_the_scene_hash_sql_call_site_may_not_drop_an_argument(package):
    mutate_migration(package, "s.editor,'unverified',0)", "s.editor,'unverified')")
    assert_clean_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_the_scene_hash_sql_call_site_may_not_add_an_argument(package):
    mutate_migration(package, "s.editor,'unverified',0)", "s.editor,'unverified',0,0)")
    assert_clean_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_the_scene_hash_sql_call_site_may_not_bind_another_column(package):
    mutate_migration(package, "s.tb_num,s.tb_den", "s.tb_den,s.tb_num")
    assert_clean_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_the_scene_hash_time_basis_must_stay_a_literal(package):
    # The backfill has no decoded PTS yet, so the time basis is a literal and
    # not a column reference.
    mutate_migration(package, "s.editor,'unverified',0)", "s.editor,s.time_basis,0)")
    assert_clean_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_the_scene_hash_verified_must_stay_an_integer_literal(package):
    mutate_migration(package, "s.editor,'unverified',0)", "s.editor,'unverified','0')")
    assert_clean_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_an_unexpected_scene_hash_call_site_is_rejected(package):
    # A third call site is an unexpected one.
    path = package["root"] / MIGRATION_REL
    text = path.read_text(encoding="utf-8")
    extra = (
        "INSERT INTO scene_head SELECT s.id,s.id,lvw_scene_hash(s.media_ref_id,m.sha256,s.version,"
        "s.start_pts,s.end_pts,s.origin_pts,s.tb_num,s.tb_den,s.editor,'unverified',0) "
        "FROM scene_revision s JOIN media_ref m ON s.media_ref_id=m.id;"
    )
    path.write_text(text.replace("COMMIT;", extra + "\nCOMMIT;"), encoding="utf-8")
    refresh_fences(package, [MIGRATION_REL])
    assert_clean_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_the_owner_migration_declares_exactly_two_backfill_call_sites(owner_copy):
    # The positive control: the real candidate migration carries exactly the
    # two frozen backfill call sites with exactly 11 arguments each.
    text = (owner_copy["root"] / MIGRATION_REL).read_text(encoding="utf-8")
    sites = checker.find_sql_call_sites(text, "lvw_scene_hash")
    assert len(sites) == 2
    for site in sites:
        assert len(site["arguments"]) == 11
        assert site["table"] in ("SCENE_HEAD", "SCENE_REVISION_META")
    result = run_owner_copy(owner_copy)
    assert result.returncode == 0, result.stdout + result.stderr


# --- NM-2: the new Scene GET envelope --------------------------------------


def test_the_new_scene_get_may_not_return_another_candidate_component(package):
    # NM-2 / reviewer probe P05: the new Scene GET must return the canonical
    # Scene, not a candidate component that also resolves.
    overlay = load(package["root"], OVERLAY_REL)
    body = overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    body["properties"]["data"] = {"$ref": "#/components/schemas/MultiShot_SceneRevisionInfo"}
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    assert_clean_failure(run_package(package), "E_SCENE_GET_ENVELOPE")


def test_the_new_scene_get_may_not_drop_the_canonical_envelope(package):
    overlay = load(package["root"], OVERLAY_REL)
    del overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["content"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    assert_clean_failure(run_package(package), "E_SCENE_GET_ENVELOPE")


def test_the_new_scene_get_envelope_required_set_is_frozen(package):
    overlay = load(package["root"], OVERLAY_REL)
    body = overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    body["required"] = ["data"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    assert_clean_failure(run_package(package), "E_SCENE_GET_ENVELOPE")


def test_the_new_scene_get_envelope_may_not_accept_extra_properties(package):
    overlay = load(package["root"], OVERLAY_REL)
    body = overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    body["additionalProperties"] = True
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    assert_clean_failure(run_package(package), "E_SCENE_GET_ENVELOPE")


def test_the_new_scene_get_returns_the_canonical_scene_in_the_canonical_envelope(owner_copy):
    # The positive control: the real overlay carries the canonical Scene
    # inside the canonical success envelope, byte for byte.
    api = load(owner_copy["root"], "contracts/openapi.json")
    overlay = load(owner_copy["root"], OVERLAY_REL)
    canonical = api["paths"]["/api/v1/scenes/{id}"]["put"]["responses"]["200"]["content"]["application/json"]["schema"]
    added = overlay["add_paths"]["/api/v1/scenes/{id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert added == canonical
    assert added["properties"]["data"] == {"$ref": "#/components/schemas/Scene"}
    assert "Scene" in api["components"]["schemas"]
    result = run_owner_copy(owner_copy)
    assert result.returncode == 0, result.stdout + result.stderr


# --- NM-3: malformed input ---------------------------------------------------


def test_a_malformed_overlay_metadata_container_is_rejected(package):
    # NM-3 / reviewer probe P22: metadata_only as a JSON list.
    overlay = load(package["root"], OVERLAY_REL)
    overlay["metadata_only"] = ["/api/v1/scenes"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    assert_clean_failure(run_package(package), "E_OVERLAY_METADATA_SHAPE")


def test_a_malformed_overlay_header_container_is_rejected(package):
    # NM-3 / reviewer probe P23: add_response_headers as a JSON list.
    overlay = load(package["root"], OVERLAY_REL)
    overlay["add_response_headers"] = ["/api/v1/scenes/{id}"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    assert_clean_failure(run_package(package), "E_OVERLAY_HEADER_SHAPE")


def test_a_malformed_overlay_metadata_entry_is_rejected(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["metadata_only"]["/api/v1/scenes"] = ["get"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    assert_clean_failure(run_package(package), "E_OVERLAY_METADATA_SHAPE")


def test_a_malformed_overlay_header_entry_is_rejected(package):
    overlay = load(package["root"], OVERLAY_REL)
    overlay["add_response_headers"]["/api/v1/scenes/{id}"] = ["put"]
    save(package["root"], OVERLAY_REL, overlay)
    refresh_fences(package, [OVERLAY_REL])
    assert_clean_failure(run_package(package), "E_OVERLAY_HEADER_SHAPE")


def test_an_invalid_candidate_schema_regex_is_rejected(package):
    # NM-3 / reviewer probe P24: a syntactically invalid regular expression.
    schema = load(package["root"], "contracts/v1-multishot.schema.json")
    schema["$defs"]["ShotFrameRef"]["properties"]["sha256"]["pattern"] = "([unclosed"
    save(package["root"], "contracts/v1-multishot.schema.json", schema)
    refresh_fences(package, ["contracts/v1-multishot.schema.json"])
    assert_clean_failure(run_package(package), "E_SCHEMA_PATTERN")


def test_a_missing_input_reports_a_clean_input_error_on_stdout(package):
    # NM-3: an unreadable input is a clean INPUT_ERROR with exit 2, never a
    # traceback and never an empty stdout.
    result = subprocess.run(
        [sys.executable, "-B", str(CHECKER), "--root", str(package["root"]), "--plan", "plans/missing.json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "INPUT_ERROR" in result.stdout
    assert "INPUT_ERROR" in result.stderr
    assert "Traceback" not in result.stderr
    assert "RESULT: PASS" not in result.stdout


def test_a_malformed_domain_mapping_container_is_rejected(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"] = []
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    assert_clean_failure(run_package(package), "E_DOMAIN_MAPPING")


def test_a_malformed_scene_hash_container_is_rejected(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["scene_hash"]["column_mapping"] = []
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    assert_clean_failure(run_package(package), "E_SCENE_HASH_MAPPING")


def test_a_malformed_sample_design_container_is_rejected(package):
    design = load(package["root"], SAMPLE_REL)
    design["clips"] = {}
    save(package["root"], SAMPLE_REL, design)
    refresh_fences(package, [SAMPLE_REL])
    assert_clean_failure(run_package(package), "E_INPUT_SHAPE")


def test_a_malformed_spec_manifest_container_is_rejected(package):
    spec = load(package["root"], D0_DIR + "/spec-manifest.json")
    spec["files"] = []
    save(package["root"], D0_DIR + "/spec-manifest.json", spec)
    package["d0_manifest_sha256"] = regenerate_d0_manifest(package["root"])
    assert_clean_failure(run_package(package), "E_INPUT_SHAPE")


# --- NM-4: the run discloses what it validated ------------------------------


def test_the_run_declares_its_validation_capability(package):
    result = run_package(package)
    assert result.returncode == 0, result.stdout
    assert "VALIDATION: metaschema_check=" in result.stdout
    assert "frame_instance_probe=" in result.stdout
    assert "frame_sample=present" in result.stdout


def test_the_mandatory_owner_run_used_the_optional_dependency_and_the_real_frames(owner_copy):
    # The mandatory candidate verification really ran the full metaschema
    # check and the real retained frame instance probe.
    result = run_owner_copy(owner_copy)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "metaschema_check=jsonschema" in result.stdout
    assert "frame_instance_probe=jsonschema" in result.stdout
    assert "frame_sample=present" in result.stdout


def test_a_degraded_run_without_the_frame_sample_is_not_byte_identical(package):
    # NM-4: a run without the retained frame sample must not look like a full
    # run.
    full = run_package(package)
    assert full.returncode == 0, full.stdout
    degraded = run_package(package, extra=["--frame-sample", "reports/unified-media/live-15/absent.json"])
    assert degraded.returncode == 0, degraded.stdout
    assert degraded.stdout != full.stdout
    assert "E_FRAME_REF_SAMPLE_SKIPPED" in degraded.stdout
    assert "frame_instance_probe=skipped-no-sample" in degraded.stdout
    assert "frame_sample=absent" in degraded.stdout


def test_a_degraded_run_without_jsonschema_is_not_byte_identical(package, tmp_path):
    # NM-4: a host without the optional jsonschema dependency must not
    # produce evidence that is indistinguishable from a full run.
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "jsonschema.py").write_text(
        'raise ImportError("shadow jsonschema for the degraded-run regression test")\n',
        encoding="utf-8",
    )
    full = run_package(package)
    assert full.returncode == 0, full.stdout
    degraded = run_package(package, env={"PYTHONPATH": str(shadow)})
    assert degraded.returncode == 0, degraded.stdout
    assert degraded.stdout != full.stdout
    assert "E_SCHEMA_META_SKIPPED" in degraded.stdout
    assert "metaschema_check=structural-fallback" in degraded.stdout
    assert "frame_instance_probe=structural" in degraded.stdout


def test_the_structural_fallback_is_not_claimed_as_a_full_validation(package, tmp_path):
    # NM-4: the degraded run must not claim that it ran the full validation.
    shadow = tmp_path / "shadow"
    shadow.mkdir()
    (shadow / "jsonschema.py").write_text(
        'raise ImportError("shadow jsonschema for the degraded-run regression test")\n',
        encoding="utf-8",
    )
    degraded = run_package(package, env={"PYTHONPATH": str(shadow)})
    assert degraded.returncode == 0, degraded.stdout
    assert "metaschema_check=jsonschema" not in degraded.stdout


# --- NM-5: the one key set and the one sorted order -------------------------


def test_the_frozen_domain_entry_key_order_is_the_sorted_order():
    # NM-5: the frozen key constant is used and it is the sorted order.
    assert checker.FROZEN_DOMAIN_ENTRY_KEYS == ("kind", "lang", "ref", "text")
    assert list(checker.FROZEN_DOMAIN_ENTRY_KEYS) == sorted(checker.FROZEN_DOMAIN_ENTRY_KEYS)


def test_the_frozen_example_uses_the_sorted_key_order(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    entry = contract["canonical_domain_mapping"]["example"]["observation"][0]
    assert entry.startswith('{"kind":"character","lang":"zh","ref":"')
    assert list(json.loads(entry).keys()) == sorted(json.loads(entry).keys())


def test_the_domain_rule_may_not_name_another_key_order(package):
    # NM-5: the rule text may not go back to the ambiguous enumeration.
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["entry_serialization"] = (
        "Each nonempty language value produces one string: compact UTF-8 JSON object, sorted keys, "
        "ensure_ascii=False, allow_nan=False. The JSON key set is {kind, ref, lang, text}; serialized "
        "key order MUST be kind, ref, lang, text, never insertion order. No translation, normalization, "
        "trim or deduplication; skip only exactly empty strings. Preserve raw model response byte-for-byte."
    )
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    assert_clean_failure(run_package(package), "E_DOMAIN_MAPPING")


def test_the_domain_rule_may_not_drop_the_sorted_order_clause(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["entry_serialization"] = (
        "Each nonempty language value produces one string: compact UTF-8 JSON object, sorted keys, "
        "ensure_ascii=False, allow_nan=False. Keys kind, ref, lang, text. No translation, normalization, "
        "trim or deduplication; skip only exactly empty strings. Preserve raw model response byte-for-byte."
    )
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    assert_clean_failure(run_package(package), "E_DOMAIN_MAPPING")


# --- NM-6: the declaration driven domain engine -----------------------------


DOMAIN_EVIDENCE = {
    "characters": [
        {"local_actor_id": "actor-b", "visible_appearance": {"zh": "蓝衣", "en": "blue"}, "domain": "inference"},
        {"local_actor_id": "actor-a", "visible_appearance": {"zh": "红衣", "en": "red"}, "domain": "observation"},
    ],
    "scene": {"description": {"zh": "室内", "en": "indoor"}, "domain": "observation"},
    "actions": [
        {"description": {"zh": "起身", "en": "rise"}, "domain": "observation"},
        {"description": {"zh": "转身", "en": "turn"}, "domain": "inference"},
    ],
    "unknowns": [{"zh": "未知一", "en": "unknown one"}],
}

EXPECTED_OBSERVATION = [
    '{"kind":"character","lang":"zh","ref":"actor-a","text":"红衣"}',
    '{"kind":"character","lang":"en","ref":"actor-a","text":"red"}',
    '{"kind":"scene","lang":"zh","ref":"scene","text":"室内"}',
    '{"kind":"scene","lang":"en","ref":"scene","text":"indoor"}',
    '{"kind":"action","lang":"zh","ref":"0","text":"起身"}',
    '{"kind":"action","lang":"en","ref":"0","text":"rise"}',
]
EXPECTED_INFERENCE = [
    '{"kind":"character","lang":"zh","ref":"actor-b","text":"蓝衣"}',
    '{"kind":"character","lang":"en","ref":"actor-b","text":"blue"}',
    '{"kind":"action","lang":"zh","ref":"1","text":"转身"}',
    '{"kind":"action","lang":"en","ref":"1","text":"turn"}',
]
EXPECTED_UNKNOWNS = [
    '{"kind":"unknown","lang":"zh","ref":"0","text":"未知一"}',
    '{"kind":"unknown","lang":"en","ref":"0","text":"unknown one"}',
]


def declared_mapping(package: dict) -> dict:
    return load(package["root"], "plans/v1-multishot-contract.json")["canonical_domain_mapping"]


def test_the_domain_engine_routes_every_kind_and_both_domains(package):
    # NM-6: the rule, not one worked example: all four kinds, both domains
    # and the language order.
    result = checker.build_domain_entries(declared_mapping(package), DOMAIN_EVIDENCE)
    assert result["errors"] == []
    assert result["observation"] == EXPECTED_OBSERVATION
    assert result["inference"] == EXPECTED_INFERENCE
    assert result["unknowns"] == EXPECTED_UNKNOWNS


def test_the_domain_engine_sorts_the_characters_by_actor_id(package):
    result = checker.build_domain_entries(declared_mapping(package), DOMAIN_EVIDENCE)
    assert result["observation"][0].endswith('"ref":"actor-a","text":"红衣"}')
    assert result["inference"][0].endswith('"ref":"actor-b","text":"蓝衣"}')


def test_the_domain_engine_keeps_the_original_action_and_unknown_index(package):
    result = checker.build_domain_entries(declared_mapping(package), DOMAIN_EVIDENCE)
    assert '"ref":"0","text":"起身"}' in result["observation"][4]
    assert '"ref":"1","text":"转身"}' in result["inference"][2]
    assert all('"ref":"0"' in entry for entry in result["unknowns"])


def test_the_domain_engine_skips_only_an_exactly_empty_language(package):
    evidence = {
        "characters": [
            {"local_actor_id": "actor-a", "visible_appearance": {"zh": "", "en": "red"}, "domain": "observation"},
        ],
        "scene": {"description": {"zh": " ", "en": ""}, "domain": "observation"},
        "actions": [],
        "unknowns": [],
    }
    result = checker.build_domain_entries(declared_mapping(package), evidence)
    assert result["observation"] == [
        '{"kind":"character","lang":"en","ref":"actor-a","text":"red"}',
        '{"kind":"scene","lang":"zh","ref":"scene","text":" "}',
    ]


def test_the_domain_engine_keeps_the_raw_text_unchanged(package):
    raw = "  红衣 人物\n"
    evidence = {
        "characters": [
            {"local_actor_id": "actor-a", "visible_appearance": {"zh": raw, "en": raw}, "domain": "observation"},
        ],
        "scene": None,
        "actions": [],
        "unknowns": [],
    }
    result = checker.build_domain_entries(declared_mapping(package), evidence)
    assert json.loads(result["observation"][0])["text"] == raw
    assert json.loads(result["observation"][1])["text"] == raw


def test_the_domain_engine_never_touches_the_human_domains(package):
    result = checker.build_domain_entries(declared_mapping(package), DOMAIN_EVIDENCE)
    assert set(result) == {"observation", "inference", "unknowns", "errors"}
    for key in result:
        assert "user_evidence" not in key
        assert "creative_intent" not in key


def test_the_domain_engine_follows_the_declared_language_order(package):
    mapping = dict(declared_mapping(package))
    mapping["language_order"] = ["en", "zh"]
    result = checker.build_domain_entries(mapping, DOMAIN_EVIDENCE)
    assert result["observation"][0] == '{"kind":"character","lang":"en","ref":"actor-a","text":"red"}'
    assert result["observation"][1] == '{"kind":"character","lang":"zh","ref":"actor-a","text":"红衣"}'


def test_the_domain_engine_reports_an_undeclared_domain(package):
    evidence = {
        "characters": [
            {"local_actor_id": "actor-a", "visible_appearance": {"zh": "红衣", "en": "red"}, "domain": "hallucination"},
        ],
        "scene": None,
        "actions": [],
        "unknowns": [],
    }
    result = checker.build_domain_entries(declared_mapping(package), evidence)
    assert result["errors"]
    assert result["observation"] == []
    assert result["inference"] == []


def test_the_frozen_example_source_domain_must_match_its_destination(package):
    # NM-6: the example declares the domain its entries are routed to; the
    # checker reads it instead of ignoring it.
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["example"]["source"]["domain"] = "inference"
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    assert_clean_failure(run_package(package), "E_DOMAIN_MAPPING")


def test_the_frozen_example_may_not_also_carry_the_other_domain(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["example"]["inference"] = [
        '{"kind":"character","lang":"zh","ref":"actor1","text":"红衣人物"}',
    ]
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    assert_clean_failure(run_package(package), "E_DOMAIN_MAPPING")


def test_the_domain_rule_must_name_a_source_field_the_dto_declares(package):
    contract = load(package["root"], "plans/v1-multishot-contract.json")
    contract["canonical_domain_mapping"]["source_fields"]["character"] = "not_a_declared_field"
    save(package["root"], "plans/v1-multishot-contract.json", contract)
    refresh_fences(package, ["plans/v1-multishot-contract.json"])
    assert_clean_failure(run_package(package), "E_DOMAIN_MAPPING")


# --- NM-7 and the 1.1.2 adjudication ----------------------------------------


def test_the_112_adjudication_may_not_claim_the_product_gate(package):
    adjudication = load(package["root"], ADJUDICATION_112_REL)
    adjudication["product_gate0"] = True
    save(package["root"], ADJUDICATION_112_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_112_REL])
    assert_clean_failure(run_package(package), "E_112_ADJUDICATION")


def test_the_112_adjudication_may_not_close_a_finding(package):
    adjudication = load(package["root"], ADJUDICATION_112_REL)
    adjudication["findings"][0]["state"] = "ACCEPTED"
    save(package["root"], ADJUDICATION_112_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_112_REL])
    assert_clean_failure(run_package(package), "E_112_ADJUDICATION")


def test_the_112_adjudication_may_not_invent_a_ninth_finding(package):
    adjudication = load(package["root"], ADJUDICATION_112_REL)
    adjudication["findings"].append({"id": "NM-9", "severity": "Minor", "state": "IMPLEMENTATION_CORRECTION_REQUIRED"})
    save(package["root"], ADJUDICATION_112_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_112_REL])
    assert_clean_failure(run_package(package), "E_112_ADJUDICATION")


def test_the_112_adjudication_counts_are_the_derived_ones(package):
    adjudication = load(package["root"], ADJUDICATION_112_REL)
    adjudication["derived_counts"] = {"Fatal": 0, "Major": 3, "Minor": 6}
    save(package["root"], ADJUDICATION_112_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_112_REL])
    assert_clean_failure(run_package(package), "E_112_ADJUDICATION")


def test_the_112_adjudication_keeps_the_review_summary_minor_count(package):
    # The review report summary wrote 6 Minor; the actual finding array holds
    # five. The original report is retained and the discrepancy is reconciled
    # in the appended receipt, so the count itself may not be rewritten.
    adjudication = load(package["root"], ADJUDICATION_112_REL)
    adjudication["review_summary_minor_count"] = 5
    save(package["root"], ADJUDICATION_112_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_112_REL])
    assert_clean_failure(run_package(package), "E_112_ADJUDICATION")


def test_the_112_adjudication_decision_is_changes_required(package):
    adjudication = load(package["root"], ADJUDICATION_112_REL)
    adjudication["decision"] = "ACCEPTED"
    save(package["root"], ADJUDICATION_112_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_112_REL])
    assert_clean_failure(run_package(package), "E_112_ADJUDICATION")


def test_the_111_adjudication_stays_the_historical_pending_record(package):
    # The design 1.1.1 adjudication is the historical frozen record of that
    # revision: it stays pending, it is not rewritten into a closure.
    adjudication = load(package["root"], ADJUDICATION_111_REL)
    for finding in adjudication["findings"]:
        assert finding["state"] == "CORRECTED_PENDING_INDEPENDENT_RECHECK"
    adjudication["findings"][0]["state"] = "ACCEPTED"
    save(package["root"], ADJUDICATION_111_REL, adjudication)
    refresh_fences(package, [ADJUDICATION_111_REL])
    assert_clean_failure(run_package(package), "E_111_ADJUDICATION")


# --- NM-8: the pin the run verified against ---------------------------------


def test_the_run_records_the_default_d0_pin(owner_copy):
    result = run_owner_copy(owner_copy)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PIN: mode=default" in result.stdout
    assert checker.FROZEN_D0_PACKET_MANIFEST_SHA256 in result.stdout


def test_the_mandatory_owner_run_used_the_frozen_default_pin(owner_copy):
    result = run_owner_copy(owner_copy)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "mode=default (frozen stage command pin)" in result.stdout
    assert "NON-AUTHORITY" not in result.stdout


def test_an_overridden_pin_run_is_marked_as_non_authority(package):
    result = run_package(package)
    assert result.returncode == 0, result.stdout
    assert "PIN: mode=explicit-override" in result.stdout
    assert "NON-AUTHORITY" in result.stdout
    assert checker.FROZEN_D0_PACKET_MANIFEST_SHA256 in result.stdout


def test_an_overridden_pin_run_still_reports_the_computed_actual_pin(package):
    result = run_package(package)
    assert result.returncode == 0, result.stdout
    assert package["d0_manifest_sha256"] in result.stdout


def test_a_stale_pin_is_still_rejected_when_it_is_overridden(package):
    result = run_checker(package["root"], OLD_D0_MANIFEST_1_1_1_SHA256)
    assert result.returncode != 0
    assert "E_D0_PACKET_MANIFEST_PINNED" in result.stdout
    assert "mode=explicit-override" in result.stdout
