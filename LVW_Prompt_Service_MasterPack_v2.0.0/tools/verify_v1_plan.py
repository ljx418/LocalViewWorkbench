#!/usr/bin/env python3
"""Deterministic, read-only validator for the approved V1 multi-shot plan package.

Scope (D0-B-IMPL, design 1.1): this tool checks the *plan package* only. It
never runs product code, never opens a product database, never touches
GPU/media/services/network, never writes files and never declares a Stage PASS
or a human signature.

Exit codes:
  0  every check passed (valid root plan)
  1  at least one deterministic check failed (invalid root plan)
  2  an input could not be read/parsed, so no verdict could be produced

The tool is stdlib-only. ``jsonschema`` is used for metaschema validation and
for the candidate-instance probe when it happens to be importable, but the tool
never requires that extra install: a structural fallback check always runs.

Design 1.1 re-freeze (root adjudication ``design11-adjudication.json``):
  * the D0 packet manifest pin below is re-frozen to the owner manifest that
    the root authority supplied for the 1.1 packet;
  * the parent deadline is the frozen ``450 * n + 90`` formula (max 5490) and
    not the earlier 1800 s guess;
  * the new 1.1 guards cover the parent/checkpoint budget arithmetic, the
    machine sample allocation, the additive OpenAPI overlay, the canonical
    Scene/FrameRef compatibility, the public/internal analysis binding split
    and the design-review NOT_RUN status of the new MS cases.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# --------------------------------------------------------------------------
# Frozen expectations.
#
# Every constant below is a *review-visible* value with its authority noted.
# The validator compares candidate plan packages against these values; it
# never derives them from the candidate itself, so a candidate can not lower a
# threshold and pass by lowering the expectation too.
#
# Sources:
#   docs/01_PRD.md, docs/30_V1_REVISED_EXECUTION_PLAN.md, docs/31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md,
#   docs/32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md, plans/acceptance_cases.json,
#   plans/release_gates.json, reports/v1-redesign/legacy-gates-before-change.json,
#   reports/v1-redesign/design11-adjudication.json
# --------------------------------------------------------------------------

# Fixed acceptance denominators after CHANGE-V1-MULTISHOT-01 (docs/30, docs/32).
FROZEN_DENOMINATORS = {"V1": 29, "V2": 38, "V3": 47}
# Pre-amendment denominators that must survive as an ordered prefix.
FROZEN_LEGACY_DENOMINATORS = {"V1": 21, "V2": 30, "V3": 39}
# Additive supplement cases, each of which must appear exactly once.
MS_CASE_IDS = ["MS%02d" % i for i in range(1, 9)]

# Fixed resource limits. "max" = upper bound (a larger value is a relaxed limit),
# "min" = floor (a smaller value is a relaxed limit).
FROZEN_LIMITS = {
    "video_seconds": (60, "max"),
    "video_bytes": (268435456, "max"),
    "source_pixels": (8294400, "max"),
    "shots": (12, "max"),
    "frames_per_shot": (4, "max"),
    "gpu_used_mib_exclusive": (23552, "max"),
    "ram_available_mib_min": (2048, "min"),
    "single_analysis_seconds": (420, "max"),
    "release_seconds": (30, "max"),
    "gpu_concurrency": (1, "max"),
    "automatic_model_retries": (0, "max"),
    # design 1.1: admission floor, bounded detection and the bounded PTS index.
    "gpu_free_mib_min": (19047, "min"),
    "detection_seconds": (120, "max"),
    "pts_index_bytes": (16777216, "max"),
    # design 1.1: the parent deadline is 450 * n + 90 seconds (n = 1..12).
    "batch_per_child_budget_seconds": (450, "max"),
    "batch_fixed_budget_seconds": (90, "max"),
    "batch_deadline_seconds_max": (5490, "max"),
    # design 1.1: one full V1 checkpoint (65 + 7 <= 128 actions, 21600 s wall).
    "checkpoint_model_actions_cap": (72, "max"),
    "checkpoint_seconds_cap": (21600, "max"),
    "checkpoint_cleanup_reserve_seconds": (180, "max"),
}

# The frozen parent-budget formula (docs/31, docs/32, adjudication M10).
BATCH_PER_CHILD_SECONDS = 450
BATCH_FIXED_SECONDS = 90
BATCH_MIN_SHOTS = 1
BATCH_MAX_SHOTS = 12
BATCH_MIN_DEADLINE = BATCH_PER_CHILD_SECONDS * BATCH_MIN_SHOTS + BATCH_FIXED_SECONDS  # 540
BATCH_MAX_DEADLINE = BATCH_PER_CHILD_SECONDS * BATCH_MAX_SHOTS + BATCH_FIXED_SECONDS  # 5490

# Frozen checkpoint arithmetic (docs/32). The 300/180 s values are the existing
# performance *thresholds*, not a measured M1 P95 and not a worst-case promise.
FROZEN_CHECKPOINT_INPUTS = {
    "success_calls": 65,
    "controlled_actions_cap": 7,
    "model_actions_cap": 72,
    "wall_seconds": 21600,
    "execution_deadline_seconds": 21420,
    "cleanup_reserve_seconds": 180,
    "estimated_total_seconds": 20735,
    "video_calls": 53,
    "image_calls": 12,
    "video_threshold_seconds": 300,
    "image_threshold_seconds": 180,
    "release_per_success_seconds": 30,
    "cpu_browser_overhead_seconds": 300,
    "controlled_action_seconds_cap": 35,
}
# COMPLETE03 per-child action cap; the checkpoint must stay inside it.
PARENT_CHILD_ACTION_CAP = 128
# The original Q01 acceptance set still runs inside the same checkpoint
# (12 images + 6 clips, docs/32), next to the 47 planned multi-shot calls.
Q01_IMAGE_CALLS = 12
Q01_VIDEO_CALLS = 6

# Frozen sample allocation (docs/32, plans/v1-multishot-sample-design.json).
FROZEN_SAMPLE_TOTAL_CLIPS = 12
FROZEN_SAMPLE_TOTAL_SHOTS = 47
FROZEN_SAMPLE_HARD_CUTS = 21
FROZEN_SAMPLE_QUALITY_ROWS = 18
FROZEN_SAMPLE_QUALITY_COUNTS = {"simple_action": 12, "ambiguous": 3, "static": 3}
FROZEN_SAMPLE_CLIP_STATUS = "NOT_MATERIALIZED_NOT_FROZEN"
FROZEN_SAMPLE_DESIGN_STATUS = "DESIGN_ALLOCATION_ONLY_NOT_REAL_FIXTURES"

# Fixed quality thresholds, anchored on the acceptance-case assertion text that
# carries them. A case that loses one of these tokens has had its threshold
# drifted, which is a fail-closed condition (docs/32 "分母/阈值经Gate0冻结后
# 不能由实现者更改").
FROZEN_QUALITY_TOKENS = {
    "Q01": ("图>=10/12", "片>=5/6"),
    "MS01": ("P/R均>=0.90", "各2个实际源帧"),
    "MS04": ("至少10段动作可用", "总可用>=15/18", "总>=8可用"),
    "MS05": ("反馈<=1s", "释放<=30s"),
    "MS07": ("镜头数12/13", "峰<23552MiB", "RAM>=2048MiB", "OOM0"),
}

# D0 workpack ownership, from .agent-governance/stages/V1-D0/stage-control.json.
FROZEN_D0_ALLOWED_FILES = (
    "tools/verify_v1_plan.py",
    "tools/test_verify_v1_plan.py",
    "reports/v1-redesign/d0-worker/",
)
FROZEN_D0_REVIEW_ALLOWED_FILES = (
    "reports/v1-redesign/d0-review/",
)
FROZEN_D0_FORBIDDEN_PATHS = (
    "contracts/",
    "plans/",
    "docs/",
    "lvw/",
    "LVW_V0_RuntimePatch/",
    ".agent-governance/",
    "AGENTS.md",
)
FROZEN_D0_COMMANDS = (
    "python3 -B tools/verify_v1_plan.py",
    "python3 -B -m pytest tools/test_verify_v1_plan.py -q",
)

# The D0 stage packet is *not* listed in the authority spec manifest, so it is
# fenced by its own payload manifest instead. These are the controlled packet
# files that manifest must list, exactly.
D0_PACKET_DIR = ".agent-governance/stages/V1-D0"
D0_PACKET_MANIFEST_NAME = "PAYLOAD_MANIFEST.sha256"
FROZEN_D0_PACKET_FILES = (
    "00-coordinate.md",
    "01-scope-and-non-goals.md",
    "02-architecture-and-ownership.md",
    "03-workpack-plan.md",
    "04-acceptance-matrix.md",
    "05-risk-and-authorization-register.md",
    "06-implementation-prompt.md",
    "07-checkpoint-plan.md",
    "spec-manifest.json",
    "stage-control.json",
)
# Source-control binding for the D0 packet manifest itself: the digest of the
# committed .agent-governance/stages/V1-D0/PAYLOAD_MANIFEST.sha256. The packet
# manifest binds stage-control.json and spec-manifest.json; this digest binds
# the manifest, so the whole D0 control plane is frozen even though the
# authority spec manifest does not list it. Re-freezing the D0 packet therefore
# requires re-freezing this constant in the same commit.
#
# design 1.1 re-freeze: the root authority legitimately updated the D0 packet
# to version 1.1 and supplied the owner manifest digest. This constant is
# re-frozen to that supplied digest *in the same commit as the 1.1 code
# changes*; the owner hashes themselves are not regenerated to make a check
# pass.
FROZEN_D0_PACKET_MANIFEST_SHA256 = "56e6f07b72023928b32ed7350b78f9d1d148daf79108daffecb7d9a175e39c4a"
# Only this stage display name may be accounted against the R2 authority stage.
ALLOWED_AUTHORIZATION_MAP = {"V1-M1": "R2"}
FROZEN_GLOBAL_AUTHORITY = "AUTH-PROGRAM-V1-COMPLETE-03"

# Status/claim tokens that would mean the design package invented a result.
CLAIM_TOKENS = ("PASS", "APPROVED", "SIGNED", "RELEASED", "ACCEPTED", "COMPLETE")
# Statuses a case/stage may legitimately carry (plans/release_gates.json states).
ALLOWED_CASE_STATES = ("NOT_RUN", "PASS", "FAIL", "BLOCKED")
# The design-review state of the *new* MS cases and of the new V1-M1 stage.
# "PASS" is a legal state in the general enum, but it is not legal at the
# design-review phase: nothing has been executed yet.
FROZEN_DESIGN_REVIEW_STATE = "NOT_RUN"
# Plan statuses that are acceptable for a design-review package.
ALLOWED_PLAN_STATUSES = ("DESIGN_REVIEW_REQUIRED", "DESIGN_REVIEW_NOT_ACTIVE_OPENAPI")

# Plan keys that would claim a human experience/release signature.
HUMAN_SIGNATURE_KEYS = (
    "human_signoff",
    "human_signature",
    "human_approval",
    "experience_signature",
    "release_signature",
    "signed_by",
    "signer",
)

# Authority inputs that the owner spec manifest must fence (design 1.1).
FROZEN_SPEC_FENCE_FILES = (
    "docs/30_V1_REVISED_EXECUTION_PLAN.md",
    "docs/31_V1_DETAILED_ARCHITECTURE_AND_CONTRACTS.md",
    "docs/32_V1_ACCEPTANCE_AND_AGENT_WORKFLOW.md",
    "plans/v1-revised-plan.json",
    "plans/v1-multishot-contract.json",
    "plans/v1-multishot-sample-design.json",
    "contracts/openapi.json",
    "contracts/lvw.schema.json",
    "contracts/storage.sql",
    "contracts/v1-multishot.schema.json",
    "contracts/v1-multishot-migration.sql",
    "contracts/v1-multishot.openapi-overlay.json",
    "reports/v1-redesign/design11-adjudication.json",
    ".agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256",
)

# Declared candidate artefacts (path -> frozen relative location).
FROZEN_ARTIFACT_PATHS = {
    "contract_candidate": ("plans/v1-multishot-contract.json", "plan.contract_candidate"),
    "dto_schema": ("contracts/v1-multishot.schema.json", "contract.dto_schema"),
    "openapi_overlay": ("contracts/v1-multishot.openapi-overlay.json", "contract.openapi_overlay"),
    "storage_migration": ("contracts/v1-multishot-migration.sql", "contract.storage_migration"),
    "sample_design": ("plans/v1-multishot-sample-design.json", "plan.sample_design"),
}

# The candidate migration must declare these storage objects (docs/31 table).
FROZEN_MIGRATION_OBJECTS = (
    "scene_revision",
    "scene_head",
    "scene_revision_meta",
    "shot_scene_binding",
    "model_run_artifacts",
    "shot_analysis_binding",
    "shot_analysis_evidence",
    "revision_source_binding",
    "shot_batch_parent",
    "shot_batch_item",
    "shot_batch_seal",
    "attempt_execution",
)

# The candidate DTO shape (docs/31 route table, adjudication M1/M4/M6/M8).
FROZEN_PARENT_JOB_FIELDS = (
    "id",
    "plan_hash",
    "planned_child_ids",
    "selected_scene_revision_ids",
    "total",
    "terminal_count",
    "deadline_at",
    "execution_budget_seconds",
    "status",
    "not_executed_count",
    "retry_of_parent_id",
)
FROZEN_CHILD_SUMMARY_FIELDS = (
    "ordinal",
    "job_id",
    "shot_id",
    "scene_revision_id",
    "scene_revision_hash",
    "status",
    "result_ref",
    "error_code",
    "model_started",
    "retry_of_child_id",
)
FROZEN_SHOT_EVIDENCE_FIELDS = (
    "frame_refs",
    "characters",
    "scene",
    "actions",
    "summary",
    "negative",
    "tags",
    "unknowns",
)
FROZEN_DOMAIN_DTOS = ("Character", "SceneEvidence", "Action")
FROZEN_DOMAIN_VALUES = ("observation", "inference")
# The model response must not carry server-owned or human-owned material.
FROZEN_MODEL_RESPONSE_FORBIDDEN = ("frame_refs", "user_evidence", "creative_intent")

# The six canonical product modes accepted by the new bounded route (m7).
FROZEN_BATCH_MODES = (
    "documentary",
    "realistic",
    "scifi",
    "science",
    "cinematic",
    "stylized",
)

# The candidate SQL must not be able to reach outside its own database.
FROZEN_SQL_FORBIDDEN_TOKENS = ("ATTACH", "DROP TABLE", "DROP COLUMN")


class InputError(Exception):
    """A required input could not be read or parsed."""


class Report:
    """Collects deterministic findings."""

    def __init__(self) -> None:
        self.errors: list[tuple[str, str]] = []
        self.notes: list[tuple[str, str]] = []

    def add(self, code: str, detail: str) -> None:
        self.errors.append((code, detail))

    def note(self, code: str, detail: str) -> None:
        self.notes.append((code, detail))

    @property
    def failed(self) -> bool:
        return bool(self.errors)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path, label: str) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError("%s: cannot read %s (%s)" % (label, path, exc.__class__.__name__))
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise InputError("%s: invalid JSON in %s (%s)" % (label, path, exc))
    if not isinstance(data, dict):
        raise InputError("%s: %s is not a JSON object" % (label, path))
    return data


def load_text(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError("%s: cannot read %s (%s)" % (label, path, exc.__class__.__name__))


def as_list(value, label, report: Report, code: str = "E_INPUT_SHAPE"):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        report.add(code, "%s: expected a list of strings" % label)
        return []
    return list(value)


def require_exact_list(value, expected, label, report: Report, code: str) -> bool:
    """Compare a control list with its frozen value. Empty or partial lists fail.

    The comparison is unconditional: an empty list, a missing key, a wrong
    length and a wrong order are all findings. An empty list must never be
    treated as "nothing to check" (review finding Major D0-CODE-M01).
    """
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        report.add(code, "%s: expected a list of strings, found %r" % (label, value))
        return False
    if not value:
        report.add(code, "%s: must not be empty; expected exactly %s" % (label, list(expected)))
        return False
    if value != list(expected):
        report.add(code, "%s: expected exactly %s, found %s" % (label, list(expected), value))
        return False
    return True


def is_number(value) -> bool:
    """True for a real number. ``bool`` is not a number here."""
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def is_finite(value) -> bool:
    return is_number(value) and math.isfinite(value)


def is_integer(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# --------------------------------------------------------------------------
# Individual checks
# --------------------------------------------------------------------------


def check_denominators(ctx) -> None:
    """V1/V2/V3 exactly 29/38/47, legacy 21/30/39 preserved as an ordered prefix."""
    report, gates, baseline = ctx.report, ctx.gates, ctx.baseline
    gate_cases = gates.get("gates")
    if not isinstance(gate_cases, dict):
        report.add("E_INPUT_SHAPE", "release_gates.json: missing 'gates' object")
        return
    legacy_cases = baseline.get("required_cases")
    if not isinstance(legacy_cases, dict):
        report.add("E_INPUT_SHAPE", "legacy-gates-before-change.json: missing 'required_cases' object")
        return

    for version in ("V1", "V2", "V3"):
        current = as_list((gate_cases.get(version) or {}).get("required_cases"), "release_gates.%s.required_cases" % version, report)
        legacy = as_list(legacy_cases.get(version), "legacy.required_cases.%s" % version, report)
        want = FROZEN_DENOMINATORS[version]
        want_legacy = FROZEN_LEGACY_DENOMINATORS[version]
        if len(current) != want:
            report.add("E_DENOM_%s_COUNT" % version, "release_gates.%s.required_cases has %d entries, frozen denominator is %d" % (version, len(current), want))
        if len(legacy) != want_legacy:
            report.add("E_LEGACY_COUNT_%s" % version, "legacy baseline %s has %d entries, frozen legacy denominator is %d" % (version, len(legacy), want_legacy))
        if legacy and current[:len(legacy)] != legacy:
            report.add("E_LEGACY_PREFIX_%s" % version, "release_gates.%s.required_cases no longer starts with the legacy %d cases in original order" % (version, want_legacy))
        for case_id in MS_CASE_IDS:
            hits = current.count(case_id)
            if hits == 0:
                report.add("E_MS_MISSING", "release_gates.%s.required_cases is missing %s" % (version, case_id))
            elif hits > 1:
                report.add("E_MS_DUPLICATE", "release_gates.%s.required_cases contains %s %d times" % (version, case_id, hits))
        for case_id in legacy:
            if current.count(case_id) > 1:
                report.add("E_CASE_DUPLICATE", "release_gates.%s.required_cases contains %s %d times" % (version, current.count(case_id)))


def check_plan_case_sets(ctx) -> None:
    """The candidate plan must carry the same V1 denominator as the release gates."""
    report, plan = ctx.report, ctx.plan
    gate_v1 = as_list(((ctx.gates.get("gates") or {}).get("V1") or {}).get("required_cases"), "release_gates.V1.required_cases", report)
    plan_v1 = as_list(plan.get("v1_required_cases"), "plan.v1_required_cases", report)
    if gate_v1 and plan_v1 != gate_v1:
        missing = [c for c in gate_v1 if c not in plan_v1]
        extra = [c for c in plan_v1 if c not in gate_v1]
        report.add("E_PLAN_V1_CASE_SET", "plan.v1_required_cases differs from release_gates.V1 (missing=%s unexpected=%s)" % (missing or "none", extra or "none"))
    supplement = as_list(plan.get("supplement_case_ids"), "plan.supplement_case_ids", report)
    if supplement != MS_CASE_IDS:
        report.add("E_SUPPLEMENT_SET", "plan.supplement_case_ids must be exactly %s, found %s" % (MS_CASE_IDS, supplement))
    for case_id in MS_CASE_IDS:
        hits = plan_v1.count(case_id)
        if hits == 0:
            report.add("E_MS_MISSING", "plan.v1_required_cases is missing %s" % case_id)
        elif hits > 1:
            report.add("E_MS_DUPLICATE", "plan.v1_required_cases contains %s %d times" % (case_id, hits))


def check_case_definitions(ctx) -> None:
    """Each MS case exists exactly once and stays NOT_RUN at design review."""
    report, cases_doc = ctx.report, ctx.cases
    cases = cases_doc.get("cases")
    if not isinstance(cases, list):
        report.add("E_INPUT_SHAPE", "acceptance_cases.json: missing 'cases' list")
        return
    seen = {}
    for case in cases:
        if not isinstance(case, dict):
            continue
        case_id = case.get("case_id")
        if not isinstance(case_id, str):
            continue
        seen.setdefault(case_id, []).append(case)
    for case_id in MS_CASE_IDS:
        entries = seen.get(case_id, [])
        if not entries:
            report.add("E_MS_MISSING", "acceptance_cases.json has no case definition for %s" % case_id)
        elif len(entries) > 1:
            report.add("E_MS_DUPLICATE", "acceptance_cases.json defines %s %d times" % (case_id, len(entries)))
    for case_id, entries in sorted(seen.items()):
        for case in entries:
            status = case.get("status")
            if status not in ALLOWED_CASE_STATES:
                report.add("E_CASE_STATUS_INVALID", "acceptance case %s has status %r, allowed states are %s" % (case_id, status, list(ALLOWED_CASE_STATES)))
            if case_id in MS_CASE_IDS and status != FROZEN_DESIGN_REVIEW_STATE:
                # "PASS" is legal in the general enum but is an invented result
                # at the design-review phase: nothing has been executed.
                report.add("E_MS_STATUS_CLAIM", "acceptance case %s has status %r; the new MS cases must stay %s until a real checkpoint runs" % (case_id, status, FROZEN_DESIGN_REVIEW_STATE))


def check_quality_thresholds(ctx) -> None:
    """Fixed quality thresholds must still be present in the case assertions."""
    report, cases_doc = ctx.report, ctx.cases
    cases = cases_doc.get("cases")
    if not isinstance(cases, list):
        return
    by_id = {}
    for case in cases:
        if isinstance(case, dict) and isinstance(case.get("case_id"), str):
            by_id.setdefault(case["case_id"], []).append(case)
    for case_id, tokens in sorted(FROZEN_QUALITY_TOKENS.items()):
        entries = by_id.get(case_id)
        if not entries:
            report.add("E_QUALITY_DRIFT", "case %s is missing, its frozen thresholds cannot be confirmed" % case_id)
            continue
        text = "\n".join(
            "\n".join(str(a) for a in (case.get("assertions") or []))
            for case in entries
        )
        for token in tokens:
            if token not in text:
                report.add("E_QUALITY_DRIFT", "case %s no longer states the frozen threshold %r" % (case_id, token))


def check_limits(ctx) -> None:
    """No fixed resource limit may be relaxed, and every value must be finite.

    ``json.loads`` accepts ``NaN``/``Infinity``, and every comparison against
    ``NaN`` is false, so a non-finite value would silently pass a plain
    ``value > frozen`` test. The finiteness and the integer typing are checked
    explicitly before any bound is compared.
    """
    report, plan = ctx.report, ctx.plan
    limits = plan.get("limits")
    if not isinstance(limits, dict):
        report.add("E_INPUT_SHAPE", "plan.limits is missing or not an object")
        return
    for key, (frozen, kind) in sorted(FROZEN_LIMITS.items()):
        if key not in limits:
            report.add("E_LIMIT_MISSING", "plan.limits is missing the fixed limit %s" % key)
            continue
        value = limits[key]
        if not is_number(value):
            report.add("E_LIMIT_INVALID", "plan.limits.%s is not numeric: %r" % (key, value))
            continue
        if not math.isfinite(value):
            report.add("E_LIMIT_NOT_FINITE", "plan.limits.%s is not a finite number: %r" % (key, value))
            continue
        if not is_integer(value):
            report.add("E_LIMIT_NOT_INTEGER", "plan.limits.%s must be an integer number of seconds/bytes, found %r" % (key, value))
            continue
        if kind == "max" and value > frozen:
            report.add("E_LIMIT_LOOSED", "plan.limits.%s=%s relaxes the frozen maximum %s" % (key, value, frozen))
        if kind == "min" and value < frozen:
            report.add("E_LIMIT_LOOSED", "plan.limits.%s=%s relaxes the frozen minimum %s" % (key, value, frozen))
    if "batch_deadline_seconds" in limits:
        report.add(
            "E_BUDGET_PARENT_FORMULA",
            "plan.limits carries a fixed batch_deadline_seconds=%r; the parent deadline must be the "
            "frozen %d * n + %d formula (max %d), not a guessed constant"
            % (limits.get("batch_deadline_seconds"), BATCH_PER_CHILD_SECONDS, BATCH_FIXED_SECONDS, BATCH_MAX_DEADLINE),
        )


def check_parent_budget(ctx) -> None:
    """The parent deadline is 450 * n + 90 (max 5490) everywhere it is stated."""
    report = ctx.report
    limits = ctx.plan.get("limits") or {}
    per_child = limits.get("batch_per_child_budget_seconds")
    fixed = limits.get("batch_fixed_budget_seconds")
    if not (is_integer(per_child) and is_integer(fixed)):
        report.add("E_BUDGET_PARENT_FORMULA", "plan.limits must declare integer batch_per_child_budget_seconds and batch_fixed_budget_seconds")
        return
    if per_child > BATCH_PER_CHILD_SECONDS:
        report.add("E_BUDGET_PARENT_FORMULA", "plan.limits.batch_per_child_budget_seconds=%s exceeds the frozen %d" % (per_child, BATCH_PER_CHILD_SECONDS))
    if fixed > BATCH_FIXED_SECONDS:
        report.add("E_BUDGET_PARENT_FORMULA", "plan.limits.batch_fixed_budget_seconds=%s exceeds the frozen %d" % (fixed, BATCH_FIXED_SECONDS))
    declared_max = limits.get("batch_deadline_seconds_max")
    expected_max = per_child * BATCH_MAX_SHOTS + fixed
    if declared_max != expected_max:
        report.add("E_BUDGET_PARENT_FORMULA", "plan.limits.batch_deadline_seconds_max=%r does not equal %d * %d + %d = %d" % (declared_max, per_child, BATCH_MAX_SHOTS, fixed, expected_max))
    if expected_max != BATCH_MAX_DEADLINE:
        report.add("E_BUDGET_PARENT_FORMULA", "the parent deadline formula yields %d, the frozen maximum is %d" % (expected_max, BATCH_MAX_DEADLINE))

    # The DTO must expose the same formula range.
    definition = (ctx.schema.get("$defs") or {}).get("ParentJob") or {}
    budget_field = ((definition.get("properties") or {}).get("execution_budget_seconds") or {})
    minimum = budget_field.get("minimum")
    maximum = budget_field.get("maximum")
    if minimum != BATCH_MIN_DEADLINE:
        report.add("E_BUDGET_PARENT_FORMULA", "candidate ParentJob.execution_budget_seconds.minimum=%r must be %d (= %d * %d + %d)" % (minimum, BATCH_MIN_DEADLINE, BATCH_PER_CHILD_SECONDS, BATCH_MIN_SHOTS, BATCH_FIXED_SECONDS))
    if maximum != BATCH_MAX_DEADLINE:
        report.add("E_BUDGET_PARENT_FORMULA", "candidate ParentJob.execution_budget_seconds.maximum=%r must be %d (= %d * %d + %d)" % (maximum, BATCH_MAX_DEADLINE, BATCH_PER_CHILD_SECONDS, BATCH_MAX_SHOTS, BATCH_FIXED_SECONDS))

    # The contract invariant must state the same formula.
    invariant_text = " ".join(
        str(item) for entity in (ctx.contract.get("entities") or {}).values()
        if isinstance(entity, dict)
        for item in (entity.get("invariants") or [])
    )
    if "450*total+90" not in invariant_text.replace(" ", ""):
        report.add("E_BUDGET_PARENT_FORMULA", "the candidate contract no longer states the parent budget invariant execution_budget_seconds=450*total+90")


def check_checkpoint_budget(ctx) -> None:
    """One full V1 checkpoint: 65 + 7 = 72 actions, 21600 s wall, 20735 s estimate."""
    report = ctx.report
    budget = ctx.plan.get("checkpoint_budget")
    if not isinstance(budget, dict):
        report.add("E_INPUT_SHAPE", "plan.checkpoint_budget is missing or not an object")
        return
    values = {}
    for key, expected in sorted(FROZEN_CHECKPOINT_INPUTS.items()):
        if key not in budget:
            report.add("E_CHECKPOINT_INPUT_MISSING", "plan.checkpoint_budget is missing %s" % key)
            continue
        value = budget[key]
        if not is_number(value):
            report.add("E_CHECKPOINT_INPUT_INVALID", "plan.checkpoint_budget.%s is not numeric: %r" % (key, value))
            continue
        if not math.isfinite(value):
            report.add("E_CHECKPOINT_INPUT_NOT_FINITE", "plan.checkpoint_budget.%s is not a finite number: %r" % (key, value))
            continue
        if value != expected:
            report.add("E_CHECKPOINT_INPUT_DRIFT", "plan.checkpoint_budget.%s=%s differs from the frozen design value %s" % (key, value, expected))
        values[key] = value

    required = set(FROZEN_CHECKPOINT_INPUTS)
    if not required.issubset(values):
        return

    if values["success_calls"] + values["controlled_actions_cap"] != values["model_actions_cap"]:
        report.add("E_CHECKPOINT_ACTIONS", "plan.checkpoint_budget declares %d success calls + %d controlled actions != %d model actions" % (values["success_calls"], values["controlled_actions_cap"], values["model_actions_cap"]))
    if values["model_actions_cap"] > PARENT_CHILD_ACTION_CAP:
        report.add("E_CHECKPOINT_ACTIONS", "plan.checkpoint_budget.model_actions_cap=%d exceeds the authorized per-child cap %d" % (values["model_actions_cap"], PARENT_CHILD_ACTION_CAP))
    if values["wall_seconds"] > FROZEN_CHECKPOINT_INPUTS["wall_seconds"]:
        report.add("E_CHECKPOINT_WALL", "plan.checkpoint_budget.wall_seconds=%s exceeds the authorized %d" % (values["wall_seconds"], FROZEN_CHECKPOINT_INPUTS["wall_seconds"]))
    if values["execution_deadline_seconds"] + values["cleanup_reserve_seconds"] != values["wall_seconds"]:
        report.add("E_CHECKPOINT_WALL", "plan.checkpoint_budget execution deadline %s + cleanup reserve %s != wall %s" % (values["execution_deadline_seconds"], values["cleanup_reserve_seconds"], values["wall_seconds"]))
    if values["video_calls"] + values["image_calls"] != values["success_calls"]:
        report.add("E_CHECKPOINT_CALLS", "plan.checkpoint_budget video_calls(%s) + image_calls(%s) != success_calls(%s)" % (values["video_calls"], values["image_calls"], values["success_calls"]))

    # The estimate must be reproducible from the declared threshold inputs.
    estimate = (
        values["video_calls"] * values["video_threshold_seconds"]
        + values["image_calls"] * values["image_threshold_seconds"]
        + values["success_calls"] * values["release_per_success_seconds"]
        + values["cpu_browser_overhead_seconds"]
        + values["controlled_actions_cap"] * values["controlled_action_seconds_cap"]
        + values["cleanup_reserve_seconds"]
    )
    if estimate != values["estimated_total_seconds"]:
        report.add("E_CHECKPOINT_ESTIMATE_ARITHMETIC", "the declared thresholds sum to %d, plan.checkpoint_budget.estimated_total_seconds=%s" % (estimate, values["estimated_total_seconds"]))
    if estimate > values["wall_seconds"]:
        report.add("E_CHECKPOINT_ESTIMATE_ARITHMETIC", "the threshold based estimate %d exceeds the wall budget %s" % (estimate, values["wall_seconds"]))

    # The estimate is threshold based; it must not be sold as a measured P95 or
    # as a guaranteed worst case (docs/32).
    basis = budget.get("estimate_basis")
    if not isinstance(basis, str) or not basis.strip():
        report.add("E_CHECKPOINT_ESTIMATE_BASIS", "plan.checkpoint_budget.estimate_basis must state that the estimate is threshold based")
        return
    lowered = basis.lower()
    if "threshold" not in lowered:
        report.add("E_CHECKPOINT_ESTIMATE_BASIS", "plan.checkpoint_budget.estimate_basis must name the performance thresholds it uses: %r" % basis)
    if not re.search(r"not\s+(a\s+)?measured|not\s+current|non-measured|not\s+this", lowered):
        report.add("E_CHECKPOINT_ESTIMATE_BASIS", "plan.checkpoint_budget.estimate_basis must disclaim a measured per-shot P95: %r" % basis)
    if not re.search(r"not\s+(hard\s+|a\s+|an\s+)?worst[- ]?case|non-guarantee|not\s+guarantee", lowered):
        report.add("E_CHECKPOINT_ESTIMATE_BASIS", "plan.checkpoint_budget.estimate_basis must disclaim a guaranteed worst case: %r" % basis)


def check_stages_and_dag(ctx) -> None:
    """Stage dependencies: M1 after R1, R2 after M1, and no cycles anywhere."""
    report, plan = ctx.report, ctx.plan
    stages = plan.get("stages")
    if not isinstance(stages, list) or not stages:
        report.add("E_INPUT_SHAPE", "plan.stages is missing or empty")
        return
    plan_deps = {}
    for stage in stages:
        if not isinstance(stage, dict):
            report.add("E_INPUT_SHAPE", "plan.stages contains a non-object entry")
            continue
        stage_id = stage.get("id")
        if not isinstance(stage_id, str) or not stage_id:
            report.add("E_INPUT_SHAPE", "plan.stages entry without a string id")
            continue
        if stage_id in plan_deps:
            report.add("E_DAG_DUPLICATE_STAGE", "plan.stages defines %s more than once" % stage_id)
        deps = as_list(stage.get("depends_on"), "plan.stages[%s].depends_on" % stage_id, report)
        plan_deps[stage_id] = deps
        if stage_id in deps:
            report.add("E_DAG_SELF_DEP", "plan stage %s depends on itself" % stage_id)
        completed = stage.get("completed")
        total = stage.get("total")
        if isinstance(completed, bool) or not isinstance(completed, int):
            report.add("E_INPUT_SHAPE", "plan.stages[%s].completed is not an integer" % stage_id)
        elif isinstance(total, int) and completed > total:
            report.add("E_COMPLETED_CLAIM", "plan.stages[%s].completed=%d exceeds total=%d" % (stage_id, completed, total))
        elif plan.get("status") in ALLOWED_PLAN_STATUSES and completed != 0:
            report.add("E_COMPLETED_CLAIM", "plan.stages[%s].completed=%d while the package is still in %s" % (stage_id, completed, plan.get("status")))
        if isinstance(total, int) and total <= 0:
            report.add("E_INPUT_SHAPE", "plan.stages[%s].total must be positive" % stage_id)
        if not stage.get("workpacks"):
            report.add("E_INPUT_SHAPE", "plan.stages[%s] lists no workpacks" % stage_id)

    m1_deps = plan_deps.get("V1-M1")
    if m1_deps is not None and "R1" not in m1_deps:
        report.add("E_DEP_M1_R1", "plan stage V1-M1 must depend on R1, found %s" % (m1_deps,))
    r2_deps = plan_deps.get("R2")
    if r2_deps is not None and "V1-M1" not in r2_deps:
        report.add("E_DEP_R2_M1", "plan stage R2 must depend on V1-M1, found %s" % (r2_deps,))
    for stage_id in ("R1", "V1-M1", "R2"):
        if stage_id not in plan_deps:
            report.add("E_INPUT_SHAPE", "plan.stages is missing the %s stage" % stage_id)

    for cycle in find_cycles(plan_deps):
        report.add("E_DAG_CYCLE", "plan stage dependency cycle: %s" % " -> ".join(cycle))
    known = set(plan_deps) | set(ctx.task_stage_ids)
    for stage_id, deps in sorted(plan_deps.items()):
        for dep in deps:
            if dep not in known:
                report.add("E_DEP_UNKNOWN", "plan stage %s depends on unknown stage %s" % (stage_id, dep))


def find_cycles(deps: dict[str, list[str]]) -> list[list[str]]:
    """Return every simple cycle in a dependency graph (deterministic order)."""
    cycles = []
    state = {}
    stack = []

    def visit(node):
        state[node] = "open"
        stack.append(node)
        for dep in deps.get(node, []):
            if dep not in deps:
                continue
            if state.get(dep) == "open":
                cycle = stack[stack.index(dep):] + [dep]
                if cycle not in cycles:
                    cycles.append(cycle)
            elif state.get(dep) is None:
                visit(dep)
        stack.pop()
        state[node] = "closed"

    for node in sorted(deps):
        if state.get(node) is None:
            visit(node)
    return cycles


def check_task_dag(ctx) -> None:
    """The task graph must agree with the plan graph and stay acyclic."""
    report = ctx.report
    task_deps = ctx.task_deps
    for cycle in find_cycles(task_deps):
        report.add("E_DAG_CYCLE", "tasks.json stage dependency cycle: %s" % " -> ".join(cycle))
    for stage_id, deps in sorted(ctx.plan_deps.items()):
        if stage_id in task_deps and sorted(task_deps[stage_id]) != sorted(deps):
            report.add("E_TASK_DEP_MISMATCH", "plan stage %s depends on %s but tasks.json says %s" % (stage_id, deps, task_deps[stage_id]))
    m1 = ctx.task_stages.get("V1-M1")
    if m1 is None:
        report.add("E_INPUT_SHAPE", "tasks.json has no V1-M1 stage")
    else:
        if "R1" not in (m1.get("depends_on") or []):
            report.add("E_DEP_M1_R1", "tasks.json V1-M1 must depend on R1")
        if "R22" not in (m1.get("requirements") or []):
            report.add("E_M1_TASK_COVERAGE", "tasks.json V1-M1 does not cover requirement R22")
        if sorted(m1.get("work_on_cases") or []) != sorted(MS_CASE_IDS):
            report.add("E_M1_TASK_COVERAGE", "tasks.json V1-M1 must work on exactly %s" % MS_CASE_IDS)
        if m1.get("status") != FROZEN_DESIGN_REVIEW_STATE:
            report.add("E_STAGE_STATUS_CLAIM", "tasks.json V1-M1 has status %r; the new stage must stay %s until a real checkpoint runs" % (m1.get("status"), FROZEN_DESIGN_REVIEW_STATE))
    r2 = ctx.task_stages.get("R2")
    if r2 is None:
        report.add("E_INPUT_SHAPE", "tasks.json has no R2 stage")
    else:
        gate_v1 = ((ctx.gates.get("gates") or {}).get("V1") or {}).get("required_cases") or []
        if sorted(r2.get("work_on_cases") or []) != sorted(gate_v1):
            report.add("E_R2_CASE_SET", "tasks.json R2 work_on_cases differs from the frozen V1 denominator")


def check_requirement_coverage(ctx) -> None:
    """R22 must exist, stay open and be covered by V1-M1 and R2."""
    report = ctx.report
    requirements = ctx.requirements.get("requirements")
    if not isinstance(requirements, list):
        report.add("E_INPUT_SHAPE", "requirements.json: missing 'requirements' list")
        return
    matches = [r for r in requirements if isinstance(r, dict) and r.get("requirement_id") == "R22"]
    if not matches:
        report.add("E_R22_MISSING", "requirements.json has no R22 requirement")
        return
    if len(matches) > 1:
        report.add("E_R22_DUPLICATE", "requirements.json defines R22 %d times" % len(matches))
        return
    r22 = matches[0]
    stages = r22.get("stages")
    if not isinstance(stages, list) or "V1-M1" not in stages or "R2" not in stages:
        report.add("E_R22_STAGES", "R22.stages must contain V1-M1 and R2, found %s" % (stages,))
    if sorted(r22.get("acceptance_ids") or []) != sorted(MS_CASE_IDS):
        report.add("E_R22_ACCEPTANCE", "R22.acceptance_ids must be exactly %s" % MS_CASE_IDS)
    if r22.get("status") not in ALLOWED_CASE_STATES:
        report.add("E_R22_STATUS", "R22.status %r is not an allowed state %s" % (r22.get("status"), list(ALLOWED_CASE_STATES)))
    if r22.get("status") != FROZEN_DESIGN_REVIEW_STATE:
        report.add("E_R22_STATUS", "R22.status %r cannot be anything but %s while the V1 package is only in design review" % (r22.get("status"), FROZEN_DESIGN_REVIEW_STATE))


def check_status_and_human_claims(ctx) -> None:
    """No invented completion and no invented human signature."""
    report, plan = ctx.report, ctx.plan
    status = plan.get("status")
    if status not in ALLOWED_PLAN_STATUSES:
        report.add("E_PLAN_STATUS_INVALID", "plan.status %r is not an allowed design-review status %s" % (status, list(ALLOWED_PLAN_STATUSES)))
    for token in CLAIM_TOKENS:
        if isinstance(status, str) and token in status:
            report.add("E_FORBIDDEN_CLAIM", "plan.status %r contains the result claim %r" % (status, token))
    forbidden = ctx.execution_control.get("forbidden_claims")
    if isinstance(forbidden, list):
        if status in forbidden:
            report.add("E_FORBIDDEN_CLAIM", "plan.status %r is a forbidden claim in plans/execution-control.json" % status)
        for stage in plan.get("stages") or []:
            if isinstance(stage, dict) and stage.get("status") in forbidden:
                report.add("E_FORBIDDEN_CLAIM", "plan stage %s claims forbidden status %r" % (stage.get("id"), stage.get("status")))
    if plan.get("legacy_v0_obligations_retained") is not True:
        report.add("E_LEGACY_OBLIGATION_DROPPED", "plan.legacy_v0_obligations_retained must stay true")
    if plan.get("old_slice_human_signoff_waived") is not False:
        report.add("E_HUMAN_APPROVAL_CLAIM", "plan.old_slice_human_signoff_waived must stay false")
    for key in HUMAN_SIGNATURE_KEYS:
        if key in plan and plan[key]:
            report.add("E_HUMAN_APPROVAL_CLAIM", "plan carries a human signature field %r" % key)
    approval = ctx.approval
    if approval.get("human_acceptance_of_621b1bf") is not False:
        report.add("E_HUMAN_APPROVAL_CLAIM", "product-change-approval.json does not state human_acceptance_of_621b1bf=false")
    if approval.get("release_approved") is not False:
        report.add("E_HUMAN_APPROVAL_CLAIM", "product-change-approval.json does not state release_approved=false")
    coordinate = (ctx.execution_control.get("coordinate") or {})
    if plan.get("product_current_coordinate_source") != "plans/execution-control.json":
        report.add("E_COORDINATE_SOURCE", "plan.product_current_coordinate_source must stay plans/execution-control.json, found %r" % plan.get("product_current_coordinate_source"))
    if isinstance(coordinate, dict):
        state = coordinate.get("state")
        if isinstance(forbidden, list) and state in forbidden:
            report.add("E_FORBIDDEN_CLAIM", "execution-control coordinate state %r is a forbidden claim" % state)
        elif state != "WAIT_HUMAN":
            report.note("E_COORDINATE_NOTE", "execution-control coordinate state is %r (the plan still claims no human signature)" % (state,))
    if ctx.execution_control.get("human_signoff") is not None:
        report.add("E_HUMAN_APPROVAL_CLAIM", "plans/execution-control.json carries a human signoff value while the plan claims none")
    if ctx.execution_control.get("product_acceptance") is not None:
        report.add("E_FORBIDDEN_CLAIM", "plans/execution-control.json carries a product acceptance value while the package is only in design review")


def check_ownership(ctx) -> None:
    """D0 role separation and write-path ownership."""
    report, plan = ctx.report, ctx.plan
    stage_control = ctx.stage_control
    expected_control_rel = str(Path(ctx.d0_packet_dir) / "stage-control.json")
    if ctx.stage_control_rel != expected_control_rel:
        report.add("E_OWNERSHIP_CONTROL_PATH", "the validated stage control must be the packet-bound %s, found %s" % (expected_control_rel, ctx.stage_control_rel))
    if stage_control.get("stage_pass_forbidden") is not True:
        report.add("E_OWNERSHIP_ROLE", "stage-control.json must keep stage_pass_forbidden=true")
    if stage_control.get("product_execution_authorized") is not False:
        report.add("E_OWNERSHIP_ROLE", "stage-control.json must keep product_execution_authorized=false")
    roles = stage_control.get("roles")
    if not isinstance(roles, dict):
        report.add("E_INPUT_SHAPE", "stage-control.json: missing 'roles' object")
        roles = {}
    role_values = [roles.get(name) for name in ("gate_owner", "implementation_owner", "independent_reviewer")]
    if not all(isinstance(v, str) and v for v in role_values):
        report.add("E_OWNERSHIP_ROLE", "stage-control.json roles are incomplete: %s" % (roles,))
    elif len(set(role_values)) != len(role_values):
        report.add("E_OWNERSHIP_ROLE", "stage-control.json roles are not separated: %s" % (roles,))

    workpacks = stage_control.get("workpacks")
    impl = None
    review = None
    if not isinstance(workpacks, list):
        report.add("E_INPUT_SHAPE", "stage-control.json: missing 'workpacks' list")
    else:
        for workpack in workpacks:
            if not isinstance(workpack, dict):
                continue
            if workpack.get("id") == "D0-B-IMPL":
                impl = workpack
            elif workpack.get("id") == "D0-B-REVIEW":
                review = workpack
        if impl is None:
            report.add("E_OWNERSHIP_WORKPACK", "stage-control.json has no D0-B-IMPL workpack")
        else:
            require_exact_list(impl.get("allowed_files"), FROZEN_D0_ALLOWED_FILES,
                               "stage-control.D0-B-IMPL.allowed_files", report, "E_OWNERSHIP_ALLOWED_FILES")
            require_exact_list(impl.get("commands"), FROZEN_D0_COMMANDS,
                               "stage-control.D0-B-IMPL.commands", report, "E_OWNERSHIP_COMMANDS")
            outputs = impl.get("outputs")
            if not isinstance(outputs, list) or not outputs:
                report.add("E_OWNERSHIP_OUTPUTS", "stage-control.D0-B-IMPL.outputs must be a non-empty list, found %r" % (outputs,))
        if review is None:
            report.add("E_OWNERSHIP_WORKPACK", "stage-control.json has no D0-B-REVIEW workpack")
        else:
            require_exact_list(review.get("allowed_files"), FROZEN_D0_REVIEW_ALLOWED_FILES,
                               "stage-control.D0-B-REVIEW.allowed_files", report, "E_OWNERSHIP_REVIEW_FILES")
            if impl is not None:
                overlap = sorted(set(impl.get("allowed_files") or []) & set(review.get("allowed_files") or []))
                if overlap:
                    report.add("E_OWNERSHIP_OVERLAP", "D0-B-IMPL and D0-B-REVIEW both claim %s" % overlap)
    require_exact_list(stage_control.get("forbidden_write_paths"), FROZEN_D0_FORBIDDEN_PATHS,
                       "stage-control.forbidden_write_paths", report, "E_OWNERSHIP_FORBIDDEN_PATHS")
    for key in ("model_gpu_runtime_budget", "product_full_checkpoints"):
        value = stage_control.get(key)
        if value != 0:
            report.add("E_OWNERSHIP_BUDGET", "stage-control.%s must stay 0 for the offline D0 packet, found %r" % (key, value))

    plan_roles = plan.get("roles")
    if not isinstance(plan_roles, dict):
        report.add("E_INPUT_SHAPE", "plan.roles is missing or not an object")
    else:
        separated = [plan_roles.get(name) for name in ("architect_gate_owner", "implementer", "independent_reviewer", "human")]
        if not all(isinstance(v, str) and v for v in separated):
            report.add("E_OWNERSHIP_ROLE", "plan.roles does not name all four parties: %s" % (plan_roles,))
        elif len(set(separated)) != len(separated):
            report.add("E_OWNERSHIP_ROLE", "plan.roles are not separated: %s" % (plan_roles,))
    preparation = plan.get("parallel_preparation")
    if not isinstance(preparation, dict):
        report.add("E_INPUT_SHAPE", "plan.parallel_preparation is missing or not an object")
    else:
        if preparation.get("product_edits_allowed") is not False:
            report.add("E_OWNERSHIP_WORKPACK", "plan.parallel_preparation.product_edits_allowed must be false")
        names = as_list(preparation.get("workpacks"), "plan.parallel_preparation.workpacks", report)
        for prefix in ("D0-A", "D0-B"):
            if not any(item.startswith(prefix) for item in names):
                report.add("E_OWNERSHIP_WORKPACK", "plan.parallel_preparation.workpacks is missing a %s entry" % prefix)


def check_authorization_accounting(ctx) -> None:
    """Budget is not reset and the V1-M1 -> R2 accounting stays explicit."""
    report, plan = ctx.report, ctx.plan
    if plan.get("budget_reset") is not False:
        report.add("E_BUDGET_RESET", "plan.budget_reset must be false, found %r" % plan.get("budget_reset"))
    if plan.get("global_authority") != FROZEN_GLOBAL_AUTHORITY:
        report.add("E_GLOBAL_AUTHORITY_DRIFT", "plan.global_authority must stay %s, found %r" % (FROZEN_GLOBAL_AUTHORITY, plan.get("global_authority")))
    accounting = plan.get("authorization_accounting")
    if not isinstance(accounting, dict):
        report.add("E_INPUT_SHAPE", "plan.authorization_accounting is missing or not an object")
        return
    design_stage = accounting.get("design_stage")
    authority_stage = accounting.get("authority_stage")
    if design_stage not in ALLOWED_AUTHORIZATION_MAP:
        report.add("E_STAGE_ALIAS", "authorization_accounting.design_stage %r is not an authorized design stage %s" % (design_stage, sorted(ALLOWED_AUTHORIZATION_MAP)))
    if authority_stage != "R2":
        report.add("E_STAGE_ALIAS", "authorization_accounting.authority_stage %r is not the approved authority stage R2" % (authority_stage,))
    elif ALLOWED_AUTHORIZATION_MAP.get(design_stage) != authority_stage:
        report.add("E_STAGE_ALIAS", "stage %r may not be accounted against %r" % (design_stage, authority_stage))
    scope_record = accounting.get("scope_record")
    if not isinstance(scope_record, str) or not scope_record:
        report.add("E_SCOPE_RECORD_UNKNOWN", "authorization_accounting.scope_record is missing")
        return
    expected_scope = ctx.approval_rel
    if scope_record != expected_scope:
        report.add("E_SCOPE_RECORD_UNKNOWN", "authorization_accounting.scope_record %r is not the approved scope record %r" % (scope_record, expected_scope))
    scope_hash = ctx.spec_files.get(scope_record)
    actual = ctx.hashes.get(scope_record)
    if scope_hash is None:
        report.add("E_SCOPE_RECORD_UNKNOWN", "scope record %r is not covered by the spec manifest" % scope_record)
    elif actual is None:
        report.add("E_SCOPE_HASH_DRIFT", "scope record %r cannot be read" % scope_record)
    elif actual != scope_hash:
        report.add("E_SCOPE_HASH_DRIFT", "scope record %r hash %s does not match the frozen spec manifest hash %s" % (scope_record, actual, scope_hash))


def check_contract_and_schema(ctx) -> None:
    """Candidate contract and candidate DTO schema must agree and stay review-only."""
    report = ctx.report
    contract = ctx.contract
    if contract.get("status") != "DESIGN_REVIEW_NOT_ACTIVE_OPENAPI":
        report.add("E_CONTRACT_STATUS", "v1-multishot-contract.json status %r is not a design-review candidate" % contract.get("status"))
    schema = ctx.schema
    schema_uri = schema.get("$schema")
    if not isinstance(schema_uri, str) or "json-schema.org" not in schema_uri:
        report.add("E_SCHEMA_META", "candidate schema does not declare a JSON Schema metaschema")
    defs = schema.get("$defs")
    if not isinstance(defs, dict) or not defs:
        report.add("E_SCHEMA_DTO", "candidate schema has no $defs")
        defs = {}
    for name, definition in sorted(defs.items()):
        if not isinstance(definition, dict):
            report.add("E_SCHEMA_DTO", "candidate schema $defs.%s is not an object" % name)
            continue
        if definition.get("type") != "object":
            report.add("E_SCHEMA_DTO", "candidate schema $defs.%s is not an object type" % name)
        properties = definition.get("properties")
        required = definition.get("required")
        if not isinstance(properties, dict) or not isinstance(required, list):
            report.add("E_SCHEMA_DTO", "candidate schema $defs.%s lacks properties/required" % name)
            continue
        if definition.get("additionalProperties") is not False:
            report.add("E_SCHEMA_DTO", "candidate schema $defs.%s must set additionalProperties=false" % name)
        unknown = [field for field in required if field not in properties]
        if unknown:
            report.add("E_SCHEMA_DTO", "candidate schema $defs.%s requires undeclared fields %s" % (name, unknown))
    try:
        import jsonschema  # type: ignore
    except Exception:
        jsonschema = None
    if jsonschema is not None:
        try:
            jsonschema.validators.validator_for(schema).check_schema(schema)
        except Exception as exc:
            report.add("E_SCHEMA_META", "candidate schema is not a valid JSON Schema: %s" % exc)
    else:
        report.note("E_SCHEMA_META_SKIPPED", "jsonschema is not importable; only the structural candidate-schema check ran")
    ctx.schema_metaschema_checked = jsonschema is not None

    entities = contract.get("entities")
    if not isinstance(entities, dict):
        report.add("E_INPUT_SHAPE", "v1-multishot-contract.json: missing 'entities' object")
        return
    for name, entity in sorted(entities.items()):
        required = entity.get("required") if isinstance(entity, dict) else None
        if not isinstance(required, list):
            report.add("E_CONTRACT_SCHEMA_MISMATCH", "contract entity %s has no required field list" % name)
            continue
        definition = defs.get(name)
        if definition is None:
            # A declared entity without a DTO is a hole in the design, not a
            # detail to skip silently (adjudication M1/M4/M6).
            report.add("E_CONTRACT_ENTITY_UNRESOLVED", "contract entity %s has no matching DTO in the candidate schema $defs" % name)
            continue
        schema_required = definition.get("required")
        if sorted(schema_required or []) != sorted(required):
            report.add("E_CONTRACT_SCHEMA_MISMATCH", "contract entity %s requires %s but the candidate schema requires %s" % (name, sorted(required), sorted(schema_required or [])))
    shot = entities.get("ShotEvidence") or {}
    if isinstance(shot, dict):
        for key, def_name in (("character_fields", "Character"), ("action_fields", "Action")):
            fields = shot.get(key)
            definition = defs.get(def_name)
            if definition is None:
                report.add("E_CONTRACT_ENTITY_UNRESOLVED", "contract ShotEvidence.%s refers to %s, which has no DTO in the candidate schema" % (key, def_name))
                continue
            if isinstance(fields, list) and sorted(fields) != sorted(definition.get("required") or []):
                report.add("E_CONTRACT_SCHEMA_MISMATCH", "contract ShotEvidence.%s %s differs from candidate schema %s.required %s" % (key, sorted(fields), def_name, sorted(definition.get("required") or [])))


def check_dto_contract_shape(ctx) -> None:
    """The 1.1 DTOs must carry the parent deadline, the full child rows and the
    domain split, and the public binding must not leak the internal lease token.
    """
    report = ctx.report
    defs = ctx.schema.get("$defs") or {}

    def required_of(name):
        definition = defs.get(name)
        if not isinstance(definition, dict):
            report.add("E_DTO_MISSING", "the candidate schema has no %s DTO" % name)
            return None
        return list(definition.get("required") or [])

    parent = required_of("ParentJob")
    if parent is not None:
        missing = [field for field in FROZEN_PARENT_JOB_FIELDS if field not in parent]
        if missing:
            report.add("E_PARENT_DTO_FIELD", "the candidate ParentJob DTO does not carry %s" % missing)
    children = required_of("BatchChildrenResponse")
    if children is not None and sorted(children) != ["children", "parent"]:
        report.add("E_CHILDREN_ENVELOPE", "the candidate BatchChildrenResponse must carry exactly the parent view and the ordered children, found %s" % sorted(children))
    child = required_of("ChildSummary")
    if child is not None:
        missing = [field for field in FROZEN_CHILD_SUMMARY_FIELDS if field not in child]
        if missing:
            report.add("E_CHILD_ROW_FIELDS", "the candidate ChildSummary DTO does not carry %s" % missing)
    evidence = required_of("ShotEvidence")
    if evidence is not None:
        missing = [field for field in FROZEN_SHOT_EVIDENCE_FIELDS if field not in evidence]
        if missing:
            report.add("E_EVIDENCE_DTO_FIELDS", "the candidate ShotEvidence DTO does not carry %s" % missing)
    for name in FROZEN_DOMAIN_DTOS:
        required = required_of(name)
        if required is None:
            continue
        if "domain" not in required or "evidence_frame_indices" not in required:
            report.add("E_DOMAIN_DTO_FIELDS", "the candidate %s DTO must carry domain and evidence_frame_indices, found %s" % (name, required))
        definition = defs.get(name) or {}
        domain = ((definition.get("properties") or {}).get("domain") or {}).get("enum")
        if domain is not None and sorted(domain) != sorted(FROZEN_DOMAIN_VALUES):
            report.add("E_DOMAIN_DTO_FIELDS", "the candidate %s DTO domain enum must be exactly %s, found %s" % (name, list(FROZEN_DOMAIN_VALUES), domain))

    model = defs.get("MachineShotResponse")
    if isinstance(model, dict):
        properties = model.get("properties") or {}
        leaked = [field for field in FROZEN_MODEL_RESPONSE_FORBIDDEN if field in properties]
        if leaked:
            report.add("E_MODEL_RESPONSE_SCOPE", "the candidate MachineShotResponse must not carry %s" % leaked)

    public = defs.get("PublicAnalysisBinding")
    internal = defs.get("AnalysisBinding")
    if not isinstance(public, dict):
        report.add("E_DTO_MISSING", "the candidate schema has no PublicAnalysisBinding DTO")
    else:
        properties = public.get("properties") or {}
        if "lease_token" in properties:
            report.add("E_PUBLIC_BINDING_LEASE_TOKEN", "the public analysis binding must not expose the internal lease_token")
        if "lease_token" in (public.get("required") or []):
            report.add("E_PUBLIC_BINDING_LEASE_TOKEN", "the public analysis binding must not require the internal lease_token")
    if not isinstance(internal, dict):
        report.add("E_DTO_MISSING", "the candidate schema has no internal AnalysisBinding DTO")
    elif "lease_token" not in (internal.get("properties") or {}):
        report.add("E_INTERNAL_BINDING_TOKEN", "the internal analysis binding must carry the lease_token")
    evidence_dto = defs.get("ShotAnalysisEvidence")
    if isinstance(evidence_dto, dict):
        binding_ref = ((evidence_dto.get("properties") or {}).get("binding") or {}).get("$ref")
        if binding_ref != "#/$defs/PublicAnalysisBinding":
            report.add("E_PUBLIC_BINDING_REF", "the candidate ShotAnalysisEvidence must bind the public analysis binding, found %r" % binding_ref)


def type_set(schema: dict) -> set | None:
    """The set of JSON types a property schema accepts."""
    if not isinstance(schema, dict):
        return None
    declared = schema.get("type")
    if declared is None:
        return None
    if isinstance(declared, str):
        return {declared}
    if isinstance(declared, list) and all(isinstance(item, str) for item in declared):
        return set(declared)
    return None


def effective_type_set(schema: dict) -> set | None:
    """Type set after intersecting ``type`` with the ``anyOf`` branches."""
    declared = type_set(schema)
    branches = schema.get("anyOf")
    if not isinstance(branches, list) or not branches:
        return declared
    branch_types = []
    for branch in branches:
        subset = effective_type_set(branch)
        if subset is None:
            continue
        branch_types.append(subset)
    if not branch_types:
        return declared
    union = set()
    for subset in branch_types:
        union |= subset
    if declared is None:
        return union
    return declared & union


def inferred_type_set(schema: dict) -> set | None:
    """The type set of a schema that pins its values with ``const``/``enum``."""
    values = enum_values(schema)
    if not values:
        return None
    types = set()
    for value in values:
        if isinstance(value, bool):
            types.add("boolean")
        elif isinstance(value, int):
            types.add("integer")
        elif isinstance(value, float):
            types.add("number")
        elif isinstance(value, str):
            types.add("string")
        elif value is None:
            types.add("null")
        else:
            return None
    return types


def enum_values(schema: dict) -> set | None:
    if not isinstance(schema, dict):
        return None
    if "const" in schema:
        return {schema["const"]}
    values = schema.get("enum")
    if isinstance(values, list):
        return set(values)
    return None


def allows_null(schema: dict) -> bool:
    """True when a property schema accepts a null value.

    A sibling ``type`` constraint narrows the whole schema, so a ``type`` that
    excludes null wins over an ``anyOf`` branch that allows it.
    """
    if not isinstance(schema, dict):
        return False
    declared = type_set(schema)
    if declared is not None:
        return "null" in declared
    branches = schema.get("anyOf")
    if isinstance(branches, list):
        return any(allows_null(branch) for branch in branches)
    return False


HEX_PATTERN = re.compile(r"^\^\[([^\]]+)\]\{(\d+)\}\$$")


def pattern_key(pattern):
    """Normalise a simple character-class pattern so equivalent regexes compare equal."""
    if not isinstance(pattern, str):
        return None
    match = HEX_PATTERN.match(pattern)
    if not match:
        return pattern
    return ("charset", frozenset(match.group(1)), int(match.group(2)))


def is_refinement(child: dict, parent: dict) -> list:
    """Return the reasons why *child* is not a narrowing of *parent*.

    Every value that is valid under *child* must also be valid under *parent*:
    a candidate DTO may tighten the canonical contract, never widen it.
    """
    reasons = []
    child_types = effective_type_set(child)
    if child_types is None:
        child_types = inferred_type_set(child)
    parent_types = effective_type_set(parent)
    if parent_types is not None:
        if child_types is None:
            reasons.append("drops the canonical type constraint %s" % sorted(parent_types))
        elif not child_types.issubset(parent_types):
            reasons.append("accepts %s, which the canonical type %s rejects" % (sorted(child_types - parent_types), sorted(parent_types)))
    parent_enum = enum_values(parent)
    if parent_enum is not None:
        child_enum = enum_values(child)
        if child_enum is None:
            reasons.append("drops the canonical enumeration %s" % sorted(parent_enum))
        elif not child_enum.issubset(parent_enum):
            reasons.append("accepts %s, which the canonical enumeration rejects" % sorted(child_enum - parent_enum))
    for key, comparison in (("minimum", lambda c, p: c >= p), ("maximum", lambda c, p: c <= p)):
        if key in parent:
            if key not in child:
                reasons.append("drops the canonical %s bound %s" % (key, parent[key]))
            elif not comparison(child[key], parent[key]):
                reasons.append("weakens the canonical %s bound %s" % (key, parent[key]))
    parent_pattern = parent.get("pattern")
    if parent_pattern is not None:
        child_pattern = child.get("pattern")
        if child_pattern is None:
            reasons.append("drops the canonical pattern %s" % parent_pattern)
        elif pattern_key(child_pattern) != pattern_key(parent_pattern):
            reasons.append("changes the canonical pattern %s into %s" % (parent_pattern, child_pattern))
    return reasons


def check_canonical_compatibility(ctx) -> None:
    """The candidate must alias the canonical Scene and narrow the canonical FrameRef."""
    report = ctx.report
    defs = ctx.schema.get("$defs") or {}
    canonical_defs = ctx.canonical_schema.get("$defs") or {}

    candidate_scene = defs.get("CoreScene")
    canonical_scene = canonical_defs.get("Scene")
    if not isinstance(candidate_scene, dict) or not isinstance(canonical_scene, dict):
        report.add("E_CANONICAL_ALIAS", "the candidate schema must carry a CoreScene alias of the canonical Scene")
    elif candidate_scene != canonical_scene:
        report.add("E_CANONICAL_ALIAS", "the candidate CoreScene is not an exact alias of the canonical Scene DTO")

    candidate_ref = defs.get("ShotFrameRef")
    canonical_ref = canonical_defs.get("FrameRef")
    if not isinstance(candidate_ref, dict) or not isinstance(canonical_ref, dict):
        report.add("E_FRAME_REF_INCOMPATIBLE", "the candidate schema must carry a ShotFrameRef next to the canonical FrameRef")
        return
    canonical_props = canonical_ref.get("properties") or {}
    candidate_props = candidate_ref.get("properties") or {}
    if set(candidate_props) != set(canonical_props):
        missing = sorted(set(canonical_props) - set(candidate_props))
        extra = sorted(set(candidate_props) - set(canonical_props))
        report.add("E_FRAME_REF_INCOMPATIBLE", "ShotFrameRef must carry exactly the canonical FrameRef fields (missing=%s extra=%s)" % (missing, extra))
    if sorted(candidate_ref.get("required") or []) != sorted(canonical_ref.get("required") or []):
        report.add("E_FRAME_REF_INCOMPATIBLE", "ShotFrameRef.required %s differs from the canonical FrameRef.required %s" % (sorted(candidate_ref.get("required") or []), sorted(canonical_ref.get("required") or [])))
    for name in sorted(set(canonical_props) & set(candidate_props)):
        reasons = is_refinement(candidate_props[name] or {}, canonical_props[name] or {})
        for reason in reasons:
            report.add("E_FRAME_REF_INCOMPATIBLE", "ShotFrameRef.%s is not a valid canonical FrameRef: %s" % (name, reason))

    # The 1.1 design pins the per-shot frame reference: only real decoded PTS
    # and the decoded_pts basis (docs/31, adjudication M3). A candidate that
    # accepts a null PTS or a sample_target basis would let a per-shot frame
    # reference that the canonical contract never meant to carry.
    frozen_basis = candidate_props.get("time_basis")
    if not isinstance(frozen_basis, dict) or enum_values(frozen_basis) != {"decoded_pts"}:
        report.add("E_FRAME_REF_CONSTRAINT", "the candidate ShotFrameRef must pin time_basis to decoded_pts")
    for name in ("source_pts", "time_base_num", "time_base_den"):
        prop = candidate_props.get(name)
        if not isinstance(prop, dict):
            report.add("E_FRAME_REF_CONSTRAINT", "the candidate ShotFrameRef must declare %s" % name)
            continue
        if allows_null(prop):
            report.add("E_FRAME_REF_CONSTRAINT", "the candidate ShotFrameRef.%s must not accept null; a per-shot frame reference carries real source PTS" % name)

    # The real frame references that are already retained must stay valid
    # instances of the candidate DTO (adjudication M3).
    sample = ctx.frame_sample
    if not isinstance(sample, dict):
        report.note("E_FRAME_REF_SAMPLE_SKIPPED", "no retained frame reference sample was available for the instance probe")
        return
    frames = sample.get("frames")
    if not isinstance(frames, list):
        report.note("E_FRAME_REF_SAMPLE_SKIPPED", "the retained frame reference sample carries no frames list")
        return
    try:
        import jsonschema  # type: ignore
    except Exception:
        jsonschema = None
    if jsonschema is not None:
        validator = jsonschema.Draft202012Validator({"$ref": "#/$defs/ShotFrameRef", "$defs": defs})
        for index, frame in enumerate(frames):
            errors = sorted(validator.iter_errors(frame), key=lambda e: e.message)
            for error in errors:
                report.add("E_FRAME_REF_INSTANCE", "retained frame %d is not a valid ShotFrameRef: %s" % (index, error.message))
        ctx.frame_instance_probe = "jsonschema"
    else:
        required = set(candidate_ref.get("required") or [])
        for index, frame in enumerate(frames):
            if not isinstance(frame, dict):
                report.add("E_FRAME_REF_INSTANCE", "retained frame %d is not an object" % index)
                continue
            missing = sorted(required - set(frame))
            if missing:
                report.add("E_FRAME_REF_INSTANCE", "retained frame %d lacks %s" % (index, missing))
        ctx.frame_instance_probe = "structural"


def check_overlay_additive(ctx) -> None:
    """The overlay may only add; it must never replace an existing method."""
    report = ctx.report
    overlay = ctx.overlay
    base_paths = (ctx.base_openapi.get("paths") or {})
    if overlay.get("base_file") != "contracts/openapi.json":
        report.add("E_OVERLAY_BASE", "the overlay must name contracts/openapi.json as its base, found %r" % overlay.get("base_file"))
    if overlay.get("component_source") != "contracts/v1-multishot.schema.json":
        report.add("E_OVERLAY_BASE", "the overlay must build its components from contracts/v1-multishot.schema.json, found %r" % overlay.get("component_source"))
    if overlay.get("status") != "DESIGN_REVIEW_NOT_ACTIVE":
        report.add("E_OVERLAY_STATUS", "the overlay status %r is not a design-review candidate" % overlay.get("status"))
    if "components" in overlay:
        report.add("E_OVERLAY_COMPONENTS_REPLACE", "the overlay must not ship its own components block; a component could shadow a canonical schema")

    add_paths = overlay.get("add_paths")
    if not isinstance(add_paths, dict) or not add_paths:
        report.add("E_INPUT_SHAPE", "the overlay has no add_paths object")
        return
    for path, operations in sorted(add_paths.items()):
        if not isinstance(operations, dict):
            report.add("E_OVERLAY_SHAPE", "the overlay path %s has no operations" % path)
            continue
        for method in sorted(operations):
            existing = (base_paths.get(path) or {}).get(method)
            if existing is not None:
                report.add("E_OVERLAY_REPLACES_METHOD", "the overlay defines %s %s, which the canonical OpenAPI already defines" % (method.upper(), path))
    reserved = ctx.contract.get("explicit_reserved_v2_paths")
    if isinstance(reserved, list):
        for path in reserved:
            if path in add_paths:
                report.add("E_OVERLAY_RESERVED_PATH", "the overlay touches the reserved V2 path %s" % path)
    if "/api/v1/jobs/batch" in add_paths:
        report.add("E_OVERLAY_RESERVED_PATH", "the canonical /api/v1/jobs/batch route must stay untouched by the overlay")

    # The canonical V2 batch body must still be the {items:[AnalyzeRequest]} shape.
    batch = ((base_paths.get("/api/v1/jobs/batch") or {}).get("post") or {})
    schema = (((batch.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
    properties = schema.get("properties") or {}
    items = properties.get("items") or {}
    if "items" not in properties:
        report.add("E_V2_BATCH_BODY_DRIFT", "the canonical /api/v1/jobs/batch request body no longer carries the items array")
    elif (items.get("items") or {}).get("$ref") != "#/components/schemas/AnalyzeRequest":
        report.add("E_V2_BATCH_BODY_DRIFT", "the canonical /api/v1/jobs/batch items array no longer holds AnalyzeRequest entries")
    if sorted(schema.get("required") or []) != ["items"]:
        report.add("E_V2_BATCH_BODY_DRIFT", "the canonical /api/v1/jobs/batch request body must require exactly items")

    # The new bounded route must exist and reuse the canonical Job response.
    shot_batches = (add_paths.get("/api/v1/jobs/shot-batches") or {}).get("post")
    if not isinstance(shot_batches, dict):
        report.add("E_OVERLAY_ROUTE_MISSING", "the overlay does not add POST /api/v1/jobs/shot-batches")
    else:
        request_ref = (((shot_batches.get("requestBody") or {}).get("content") or {}).get("application/json") or {}).get("schema") or {}
        if request_ref.get("$ref") != "#/components/schemas/MultiShot_BatchAnalyzeRequest":
            report.add("E_OVERLAY_ROUTE_MISSING", "the shot-batches request body must use the candidate BatchAnalyzeRequest DTO")
        accepted = (((shot_batches.get("responses") or {}).get("202") or {}).get("content") or {}).get("application/json") or {}
        data_ref = (((accepted.get("schema") or {}).get("properties") or {}).get("data") or {}).get("$ref")
        if data_ref != "#/components/schemas/Job":
            report.add("E_OVERLAY_ROUTE_MISSING", "the shot-batches 202 response must return the canonical Job DTO, found %r" % data_ref)

    # Every candidate component the overlay references must exist in the schema.
    defs = ctx.schema.get("$defs") or {}
    prefix = overlay.get("component_prefix") or "MultiShot_"
    for ref in collect_refs(overlay):
        if ref.startswith("#/components/schemas/"):
            name = ref.split("/")[-1]
            if name.startswith(prefix):
                if name[len(prefix):] not in defs:
                    report.add("E_OVERLAY_COMPONENT_UNKNOWN", "the overlay references %s but the candidate schema has no %s DTO" % (ref, name[len(prefix):]))
            elif name not in (ctx.base_openapi.get("components") or {}).get("schemas", {}):
                report.add("E_OVERLAY_COMPONENT_UNKNOWN", "the overlay references %s, which is neither a candidate nor a canonical schema" % ref)

    # Metadata annotations may only describe existing routes.
    metadata = overlay.get("metadata_only")
    if isinstance(metadata, dict):
        for path, notes in sorted(metadata.items()):
            if path not in base_paths:
                report.add("E_OVERLAY_METADATA_PATH", "the overlay annotates %s, which the canonical OpenAPI does not define" % path)
                continue
            if not isinstance(notes, dict):
                report.add("E_OVERLAY_METADATA_PATH", "the overlay metadata for %s is not an object" % path)
                continue
            if notes.get("put_body_response_unchanged") is False:
                report.add("E_OVERLAY_METADATA_REPLACES", "the overlay metadata for %s claims the existing body/response changed" % path)
            if notes.get("v2_profiles_unchanged") is False:
                report.add("E_OVERLAY_METADATA_REPLACES", "the overlay metadata for %s claims the V2 profiles changed" % path)


def collect_refs(node):
    """Yield every ``$ref`` string in a nested structure."""
    refs = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                refs.append(value)
            else:
                refs.extend(collect_refs(value))
    elif isinstance(node, list):
        for item in node:
            refs.extend(collect_refs(item))
    return refs


def check_sample_design(ctx) -> None:
    """The machine sample table is a design allocation, not a frozen fixture set."""
    report = ctx.report
    design = ctx.sample_design
    if design.get("status") != FROZEN_SAMPLE_DESIGN_STATUS:
        report.add("E_SAMPLE_STATUS", "the sample design status %r must stay %s" % (design.get("status"), FROZEN_SAMPLE_DESIGN_STATUS))
    clips = design.get("clips")
    if not isinstance(clips, list):
        report.add("E_INPUT_SHAPE", "the sample design has no clips list")
        return
    if len(clips) != FROZEN_SAMPLE_TOTAL_CLIPS:
        report.add("E_SAMPLE_CLIP_COUNT", "the sample design allocates %d clips, the frozen design is %d" % (len(clips), FROZEN_SAMPLE_TOTAL_CLIPS))
    total_shots = 0
    total_cuts = 0
    seen_ids = set()
    for clip in clips:
        if not isinstance(clip, dict):
            report.add("E_SAMPLE_SHAPE", "the sample design has a non-object clip entry")
            continue
        clip_id = clip.get("id")
        if not isinstance(clip_id, str) or not clip_id:
            report.add("E_SAMPLE_SHAPE", "the sample design has a clip without a string id")
            continue
        if clip_id in seen_ids:
            report.add("E_SAMPLE_DUPLICATE_CLIP", "the sample design defines clip %s twice" % clip_id)
        seen_ids.add(clip_id)
        shots = clip.get("shots")
        cuts = clip.get("hard_cut_annotations")
        if not is_integer(shots) or shots <= 0:
            report.add("E_SAMPLE_SHAPE", "clip %s has a non positive shot count %r" % (clip_id, shots))
            continue
        if not is_integer(cuts) or cuts < 0:
            report.add("E_SAMPLE_SHAPE", "clip %s has an invalid hard cut annotation count %r" % (clip_id, cuts))
            continue
        total_shots += shots
        total_cuts += cuts
        category = clip.get("category")
        if category == "hard_cut":
            if cuts != shots - 1:
                report.add("E_SAMPLE_CUT_COUNT", "hard cut clip %s declares %d cuts for %d shots; each cut separates two shots" % (clip_id, cuts, shots))
        elif cuts != 0:
            report.add("E_SAMPLE_CUT_COUNT", "clip %s is not a hard cut clip but declares %d hard cut annotations" % (clip_id, cuts))
        if clip.get("status") != FROZEN_SAMPLE_CLIP_STATUS:
            report.add("E_SAMPLE_MATERIALIZED", "clip %s has status %r; the design allocation must stay %s until the media, rights and labels are frozen" % (clip_id, clip.get("status"), FROZEN_SAMPLE_CLIP_STATUS))
        for placeholder in ("source_sha256", "annotation_hash", "origin_source_id", "rights_record"):
            if clip.get(placeholder) is not None:
                report.add("E_SAMPLE_MATERIALIZED", "clip %s already carries a %s; the design allocation must not pretend the sample is materialized" % (clip_id, placeholder))
    if total_shots != FROZEN_SAMPLE_TOTAL_SHOTS:
        report.add("E_SAMPLE_SHOT_COUNT", "the sample design allocates %d shots, the frozen design is %d" % (total_shots, FROZEN_SAMPLE_TOTAL_SHOTS))
    if total_cuts != FROZEN_SAMPLE_HARD_CUTS:
        report.add("E_SAMPLE_CUT_COUNT", "the sample design allocates %d hard cut annotations, the frozen design is %d" % (total_cuts, FROZEN_SAMPLE_HARD_CUTS))
    for key, expected in (("total_clips", FROZEN_SAMPLE_TOTAL_CLIPS), ("total_shots", FROZEN_SAMPLE_TOTAL_SHOTS), ("hard_cut_annotation_count", FROZEN_SAMPLE_HARD_CUTS)):
        if design.get(key) != expected:
            report.add("E_SAMPLE_TOTALS", "the sample design declares %s=%r, the frozen design is %d" % (key, design.get(key), expected))

    quality = design.get("quality_subset")
    if not isinstance(quality, list):
        report.add("E_INPUT_SHAPE", "the sample design has no quality_subset list")
        return
    if len(quality) != FROZEN_SAMPLE_QUALITY_ROWS:
        report.add("E_SAMPLE_QUALITY_COUNT", "the quality subset holds %d rows, the frozen design is %d" % (len(quality), FROZEN_SAMPLE_QUALITY_ROWS))
    counts = {name: 0 for name in FROZEN_SAMPLE_QUALITY_COUNTS}
    shots_by_clip = {clip.get("id"): clip.get("shots") for clip in clips if isinstance(clip, dict)}
    for row in quality:
        if not isinstance(row, dict):
            report.add("E_SAMPLE_SHAPE", "the quality subset has a non-object row")
            continue
        clip_id = row.get("clip_id")
        shot_id = row.get("shot_id")
        category = row.get("category")
        if clip_id not in shots_by_clip:
            report.add("E_SAMPLE_QUALITY_ID", "the quality subset refers to unknown clip %r" % (clip_id,))
            continue
        if not isinstance(shot_id, str) or not re.match(r"^S\d+$", shot_id or ""):
            report.add("E_SAMPLE_QUALITY_ID", "the quality subset row for %s has an invalid shot id %r" % (clip_id, shot_id))
            continue
        index = int(shot_id[1:])
        if index < 1 or index > (shots_by_clip.get(clip_id) or 0):
            report.add("E_SAMPLE_QUALITY_ID", "the quality subset row %s/%s does not resolve inside the clip" % (clip_id, shot_id))
        if category not in FROZEN_SAMPLE_QUALITY_COUNTS:
            report.add("E_SAMPLE_QUALITY_CATEGORY", "the quality subset row %s/%s has an unknown category %r" % (clip_id, shot_id, category))
            continue
        counts[category] += 1
    if counts != FROZEN_SAMPLE_QUALITY_COUNTS:
        report.add("E_SAMPLE_QUALITY_CATEGORY", "the quality subset categories are %s, the frozen design is %s" % (counts, FROZEN_SAMPLE_QUALITY_COUNTS))
    declared_counts = design.get("quality_counts")
    if isinstance(declared_counts, dict) and declared_counts != FROZEN_SAMPLE_QUALITY_COUNTS:
        report.add("E_SAMPLE_QUALITY_CATEGORY", "the sample design declares quality_counts %s, the frozen design is %s" % (declared_counts, FROZEN_SAMPLE_QUALITY_COUNTS))


def check_candidate_artifacts(ctx) -> None:
    """The candidate artefacts must be declared and hash bound; the SQL is not run."""
    report = ctx.report
    for label, (expected_path, pointer) in sorted(FROZEN_ARTIFACT_PATHS.items()):
        holder, _, key = pointer.partition(".")
        document = ctx.plan if holder == "plan" else ctx.contract
        declared = document.get(key)
        if declared != expected_path:
            report.add("E_ARTIFACT_DECLARATION", "%s declares %s=%r, the frozen candidate artefact is %s" % (pointer, key, declared, expected_path))
            continue
        if expected_path not in ctx.spec_files:
            report.add("E_ARTIFACT_NOT_HASH_BOUND", "the candidate artefact %s is not fenced by the authority spec manifest" % expected_path)
        elif ctx.hashes.get(expected_path) != ctx.spec_files.get(expected_path):
            report.add("E_ARTIFACT_HASH_DRIFT", "the candidate artefact %s does not match its spec manifest hash" % expected_path)

    sql = ctx.migration_text
    upper = sql.upper()
    for name in FROZEN_MIGRATION_OBJECTS:
        pattern = r"CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?" + re.escape(name.upper()) + r"\s*\("
        if not re.search(pattern, upper):
            report.add("E_SQL_DECLARATION", "the candidate migration does not declare the %s table" % name)
    if "450*PLANNED_COUNT+90" not in upper.replace(" ", ""):
        report.add("E_SQL_DECLARATION", "the candidate migration does not freeze the parent budget constraint execution_budget_seconds=450*planned_count+90")
    if "LEASE_TOKEN" not in upper:
        report.add("E_SQL_DECLARATION", "the candidate migration does not keep the internal lease_token in the shot_analysis_binding table")
    for token in FROZEN_SQL_FORBIDDEN_TOKENS:
        if token in upper:
            report.add("E_SQL_FORBIDDEN", "the candidate migration contains the forbidden token %s" % token)


def check_adjudication(ctx) -> None:
    """The architecture adjudication must not fake a product gate or a human signature."""
    report = ctx.report
    adjudication = ctx.adjudication
    if adjudication.get("product_pass") is not False:
        report.add("E_ADJUDICATION_CLAIM", "the architecture adjudication must keep product_pass=false while the design is only in review")
    if adjudication.get("human_signoff") is not None:
        report.add("E_HUMAN_APPROVAL_CLAIM", "the architecture adjudication carries a human signoff value")
    decision = adjudication.get("decision")
    if isinstance(decision, str) and re.search(r"product[_ ]?pass|released|accepted", decision, re.IGNORECASE):
        report.add("E_ADJUDICATION_CLAIM", "the architecture adjudication decision %r claims a product result" % decision)


def check_immutability(ctx) -> None:
    """The old R1 packet and the canonical contracts must stay byte-identical."""
    report, baseline = ctx.report, ctx.baseline
    manifest_rel = ctx.r1_manifest_rel
    expected_manifest = baseline.get("old_R1_packet_manifest_sha256")
    actual_manifest = ctx.hashes.get(manifest_rel)
    if actual_manifest is None:
        report.add("E_R1_MANIFEST_DRIFT", "old R1 packet manifest %s cannot be read" % manifest_rel)
    elif expected_manifest != actual_manifest:
        report.add("E_R1_MANIFEST_DRIFT", "old R1 packet manifest %s hash %s differs from the frozen %s" % (manifest_rel, actual_manifest, expected_manifest))
    for rel, expected in sorted(ctx.r1_manifest_entries.items()):
        actual = ctx.hashes.get(rel)
        if actual is None:
            report.add("E_R1_FILE_DRIFT", "old R1 packet file %s is missing" % rel)
        elif actual != expected:
            report.add("E_R1_FILE_DRIFT", "old R1 packet file %s hash %s differs from the frozen %s" % (rel, actual, expected))
    contract_hashes = baseline.get("canonical_contract_hashes")
    if not isinstance(contract_hashes, dict) or not contract_hashes:
        report.add("E_INPUT_SHAPE", "legacy-gates-before-change.json: missing canonical_contract_hashes")
        contract_hashes = {}
    for rel, expected in sorted(contract_hashes.items()):
        actual = ctx.hashes.get(rel)
        if actual is None:
            report.add("E_CONTRACT_DRIFT", "canonical contract %s is missing" % rel)
        elif actual != expected:
            report.add("E_CONTRACT_DRIFT", "canonical contract %s hash %s differs from the frozen %s" % (rel, actual, expected))


def check_d0_packet_integrity(ctx) -> None:
    """The D0 stage packet must be complete, unmodified and bound to source control.

    The authority spec manifest does not list the D0 stage-control, so the D0
    packet manifest is the fence for that control plane. It is verified here
    for integrity (every listed file still hashes the same), inventory (exactly
    the frozen packet files, nothing missing and nothing extra) and
    source-control binding (the manifest digest itself is pinned).
    """
    report, root = ctx.report, ctx.root
    packet_dir = root / ctx.d0_packet_dir
    manifest_rel = str(Path(ctx.d0_packet_dir) / D0_PACKET_MANIFEST_NAME)
    manifest_path = root / manifest_rel
    if not packet_dir.is_dir():
        report.add("E_D0_PACKET_MISSING", "D0 packet directory %s is missing" % ctx.d0_packet_dir)
        return
    if not manifest_path.is_file():
        report.add("E_D0_PACKET_MANIFEST_MISSING", "D0 packet manifest %s is missing" % manifest_rel)
        return
    actual_manifest = sha256_file(manifest_path)
    if actual_manifest != ctx.d0_manifest_expected:
        report.add("E_D0_PACKET_MANIFEST_PINNED", "D0 packet manifest %s hash %s differs from the source-control pinned %s" % (manifest_rel, actual_manifest, ctx.d0_manifest_expected))
    entries = {}
    try:
        lines = manifest_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        report.add("E_D0_PACKET_MANIFEST_MISSING", "D0 packet manifest %s cannot be read (%s)" % (manifest_rel, exc.__class__.__name__))
        return
    for lineno, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            report.add("E_D0_PACKET_MANIFEST_FORMAT", "%s line %d is not '<sha256>  <file>'" % (manifest_rel, lineno))
            continue
        digest, name = parts[0], parts[1].strip()
        if name in entries:
            report.add("E_D0_PACKET_MANIFEST_DUPLICATE", "%s lists %s twice" % (manifest_rel, name))
            continue
        entries[name] = digest
    for name in FROZEN_D0_PACKET_FILES:
        if name not in entries:
            report.add("E_D0_PACKET_MANIFEST_MISSING_ENTRY", "%s does not list the controlled packet file %s" % (manifest_rel, name))
    for name in sorted(entries):
        digest = entries[name]
        if name not in FROZEN_D0_PACKET_FILES:
            report.add("E_D0_PACKET_MANIFEST_EXTRA_ENTRY", "%s lists %s, which is not a frozen D0 packet file" % (manifest_rel, name))
        if "/" in name or name.startswith("."):
            report.add("E_D0_PACKET_MANIFEST_FORMAT", "%s lists an invalid packet file name %r" % (manifest_rel, name))
            continue
        path = packet_dir / name
        if not path.is_file():
            report.add("E_D0_PACKET_FILE_MISSING", "D0 packet file %s listed in %s is missing" % (name, manifest_rel))
            continue
        actual = sha256_file(path)
        if actual != digest:
            report.add("E_D0_PACKET_DRIFT", "D0 packet file %s hash %s differs from the manifest entry %s" % (name, actual, digest))
    on_disk = set()
    try:
        on_disk = {item.name for item in packet_dir.iterdir() if item.name != D0_PACKET_MANIFEST_NAME}
    except OSError:
        pass
    for name in sorted(on_disk - set(entries)):
        report.add("E_D0_PACKET_UNLISTED_FILE", "D0 packet directory holds %s, which is not listed in %s" % (name, manifest_rel))
    if "stage-control.json" not in entries:
        report.add("E_D0_CONTROL_UNBOUND", "the D0 stage control is not bound by %s" % manifest_rel)
    if "spec-manifest.json" not in entries:
        report.add("E_D0_CONTROL_UNBOUND", "the authority spec manifest is not bound by %s" % manifest_rel)


def check_spec_fence(ctx) -> None:
    """Every file frozen in the authority spec manifest must still hash the same."""
    report = ctx.report
    files = ctx.spec_manifest.get("files")
    if not isinstance(files, dict) or not files:
        report.add("E_INPUT_SHAPE", "spec-manifest.json: missing 'files' object")
        return
    for rel in FROZEN_SPEC_FENCE_FILES:
        if rel not in files:
            report.add("E_SPEC_FENCE_INCOMPLETE", "the authority spec manifest does not fence %s" % rel)
    for rel, expected in sorted(files.items()):
        actual = ctx.hashes.get(rel)
        if actual is None:
            report.add("E_SPEC_FENCE_MISSING", "spec manifest file %s is missing" % rel)
        elif actual != expected:
            report.add("E_SPEC_FENCE_DRIFT", "spec manifest file %s hash %s differs from the frozen %s" % (rel, actual, expected))


class Context:
    def __init__(self) -> None:
        self.report = Report()
        self.hashes = {}
        self.spec_files = {}
        self.plan_deps = {}
        self.task_deps = {}
        self.task_stage_ids = set()
        self.task_stages = {}
        self.schema_metaschema_checked = False
        self.frame_instance_probe = "none"
        self.root = ROOT
        self.d0_packet_dir = D0_PACKET_DIR
        self.d0_manifest_expected = FROZEN_D0_PACKET_MANIFEST_SHA256
        self.stage_control_rel = D0_PACKET_DIR + "/stage-control.json"


def collect_hashes(ctx: Context, root: Path, relatives) -> None:
    for rel in relatives:
        path = root / rel
        try:
            ctx.hashes[rel] = sha256_file(path)
        except OSError:
            ctx.hashes[rel] = None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only deterministic validator for the approved V1 multi-shot plan package."
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="LVW package root (default: the directory holding tools/)")
    parser.add_argument("--plan", default="plans/v1-revised-plan.json", help="root plan under validation")
    parser.add_argument("--baseline", default="reports/v1-redesign/legacy-gates-before-change.json")
    parser.add_argument("--gates", default="plans/release_gates.json")
    parser.add_argument("--cases", default="plans/acceptance_cases.json")
    parser.add_argument("--requirements", default="plans/requirements.json")
    parser.add_argument("--tasks", default="plans/tasks.json")
    parser.add_argument("--contract", default="plans/v1-multishot-contract.json")
    parser.add_argument("--contract-schema", default="contracts/v1-multishot.schema.json")
    parser.add_argument("--canonical-schema", default="contracts/lvw.schema.json")
    parser.add_argument("--base-openapi", default="contracts/openapi.json")
    parser.add_argument("--overlay", default="contracts/v1-multishot.openapi-overlay.json")
    parser.add_argument("--migration", default="contracts/v1-multishot-migration.sql")
    parser.add_argument("--sample-design", default="plans/v1-multishot-sample-design.json")
    parser.add_argument("--adjudication", default="reports/v1-redesign/design11-adjudication.json")
    parser.add_argument("--frame-sample", default="reports/unified-media/live-15/video-model-run.json")
    parser.add_argument("--stage-control", default=".agent-governance/stages/V1-D0/stage-control.json")
    parser.add_argument("--spec-manifest", default=".agent-governance/stages/V1-D0/spec-manifest.json")
    parser.add_argument("--approval", default="reports/v1-redesign/product-change-approval.json")
    parser.add_argument("--execution-control", default="plans/execution-control.json")
    parser.add_argument("--r1-packet-dir", default=".agent-governance/stages/R1")
    parser.add_argument("--d0-packet-dir", default=D0_PACKET_DIR, help="D0 stage packet directory (fenced by its own payload manifest)")
    parser.add_argument("--d0-packet-manifest-sha256", default=FROZEN_D0_PACKET_MANIFEST_SHA256,
                        help="source-control pinned digest of the D0 packet payload manifest")
    return parser


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else (root / path)


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    ctx = Context()

    inputs = {
        "plan": args.plan,
        "baseline": args.baseline,
        "gates": args.gates,
        "cases": args.cases,
        "requirements": args.requirements,
        "tasks": args.tasks,
        "contract": args.contract,
        "contract-schema": args.contract_schema,
        "canonical-schema": args.canonical_schema,
        "base-openapi": args.base_openapi,
        "overlay": args.overlay,
        "sample-design": args.sample_design,
        "adjudication": args.adjudication,
        "stage-control": args.stage_control,
        "spec-manifest": args.spec_manifest,
        "approval": args.approval,
        "execution-control": args.execution_control,
    }
    documents = {}
    for name, value in inputs.items():
        path = resolve(root, value)
        try:
            documents[name] = load_json(path, name)
        except InputError as exc:
            sys.stderr.write("INPUT_ERROR: %s\n" % exc)
            return 2
    try:
        migration_text = load_text(resolve(root, args.migration), "migration")
    except InputError as exc:
        sys.stderr.write("INPUT_ERROR: %s\n" % exc)
        return 2

    frame_sample = None
    frame_path = resolve(root, args.frame_sample)
    if frame_path.is_file():
        try:
            frame_sample = load_json(frame_path, "frame-sample")
        except InputError:
            frame_sample = None

    ctx.plan = documents["plan"]
    ctx.baseline = documents["baseline"]
    ctx.gates = documents["gates"]
    ctx.cases = documents["cases"]
    ctx.requirements = documents["requirements"]
    ctx.tasks = documents["tasks"]
    ctx.contract = documents["contract"]
    ctx.schema = documents["contract-schema"]
    ctx.canonical_schema = documents["canonical-schema"]
    ctx.base_openapi = documents["base-openapi"]
    ctx.overlay = documents["overlay"]
    ctx.migration_text = migration_text
    ctx.sample_design = documents["sample-design"]
    ctx.adjudication = documents["adjudication"]
    ctx.frame_sample = frame_sample
    ctx.stage_control = documents["stage-control"]
    ctx.spec_manifest = documents["spec-manifest"]
    ctx.approval = documents["approval"]
    ctx.execution_control = documents["execution-control"]
    ctx.approval_rel = args.approval
    if Path(args.approval).is_absolute():
        try:
            ctx.approval_rel = str(Path(args.approval).resolve().relative_to(root))
        except ValueError:
            ctx.approval_rel = args.approval
    ctx.root = root
    ctx.d0_packet_dir = args.d0_packet_dir
    ctx.d0_manifest_expected = args.d0_packet_manifest_sha256
    ctx.stage_control_rel = args.stage_control

    # Hashes of every file the frozen fences talk about.
    spec_files = ctx.spec_manifest.get("files")
    ctx.spec_files = spec_files if isinstance(spec_files, dict) else {}
    relatives = set(ctx.spec_files)
    contract_hashes = ctx.baseline.get("canonical_contract_hashes")
    if isinstance(contract_hashes, dict):
        relatives.update(contract_hashes)
    r1_dir = resolve(root, args.r1_packet_dir)
    manifest_rel = str(Path(args.r1_packet_dir) / "PAYLOAD_MANIFEST.sha256")
    relatives.add(manifest_rel)
    ctx.r1_manifest_rel = manifest_rel
    r1_entries = {}
    try:
        for line in manifest_rel_text(r1_dir).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            digest, name = parts[0], parts[1].strip()
            r1_entries[str(Path(args.r1_packet_dir) / name)] = digest
    except OSError:
        r1_entries = {}
    ctx.r1_manifest_entries = r1_entries
    relatives.update(r1_entries)
    collect_hashes(ctx, root, sorted(relatives))

    # Task graph.
    for stage in ctx.tasks.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        stage_id = stage.get("stage_id")
        if not isinstance(stage_id, str):
            continue
        ctx.task_stage_ids.add(stage_id)
        ctx.task_stages[stage_id] = stage
        deps = stage.get("depends_on")
        ctx.task_deps[stage_id] = list(deps) if isinstance(deps, list) and all(isinstance(d, str) for d in deps) else []
        status = stage.get("status")
        if status not in ALLOWED_CASE_STATES:
            ctx.report.add("E_STAGE_STATUS_INVALID", "tasks.json stage %s has status %r, allowed states are %s" % (stage_id, status, list(ALLOWED_CASE_STATES)))

    # Plan dependency map for the cross-check.
    for stage in ctx.plan.get("stages") or []:
        if isinstance(stage, dict) and isinstance(stage.get("id"), str):
            deps = stage.get("depends_on")
            ctx.plan_deps[stage["id"]] = list(deps) if isinstance(deps, list) and all(isinstance(d, str) for d in deps) else []

    check_denominators(ctx)
    check_plan_case_sets(ctx)
    check_case_definitions(ctx)
    check_quality_thresholds(ctx)
    check_limits(ctx)
    check_parent_budget(ctx)
    check_checkpoint_budget(ctx)
    check_stages_and_dag(ctx)
    check_task_dag(ctx)
    check_requirement_coverage(ctx)
    check_status_and_human_claims(ctx)
    check_ownership(ctx)
    check_authorization_accounting(ctx)
    check_contract_and_schema(ctx)
    check_dto_contract_shape(ctx)
    check_canonical_compatibility(ctx)
    check_overlay_additive(ctx)
    check_sample_design(ctx)
    check_candidate_artifacts(ctx)
    check_adjudication(ctx)
    check_immutability(ctx)
    check_d0_packet_integrity(ctx)
    check_spec_fence(ctx)

    errors = sorted(ctx.report.errors)
    for code, detail in errors:
        sys.stdout.write("%s: %s\n" % (code, detail))
    if errors:
        sys.stdout.write("RESULT: FAIL (%d finding(s))\n" % len(errors))
        return 1
    gate_v1 = len(((ctx.gates.get("gates") or {}).get("V1") or {}).get("required_cases") or [])
    sys.stdout.write(
        "RESULT: PASS (V1=%d V2=%d V3=%d; MS01-MS08 once and NOT_RUN; legacy prefix intact; DAG acyclic; "
        "parent deadline %d*n+%d<=%d; checkpoint %d+ %d=%d actions / %d s; no human signature claimed)\n"
        % (
            gate_v1,
            len(((ctx.gates.get("gates") or {}).get("V2") or {}).get("required_cases") or []),
            len(((ctx.gates.get("gates") or {}).get("V3") or {}).get("required_cases") or []),
            BATCH_PER_CHILD_SECONDS,
            BATCH_FIXED_SECONDS,
            BATCH_MAX_DEADLINE,
            FROZEN_CHECKPOINT_INPUTS["success_calls"],
            FROZEN_CHECKPOINT_INPUTS["controlled_actions_cap"],
            FROZEN_CHECKPOINT_INPUTS["model_actions_cap"],
            FROZEN_CHECKPOINT_INPUTS["wall_seconds"],
        )
    )
    sys.stdout.write(
        "NOTE: this is a deterministic plan-structure check only; it is not product acceptance and not a Stage PASS.\n"
    )
    return 0


def manifest_rel_text(r1_dir: Path) -> str:
    return (r1_dir / "PAYLOAD_MANIFEST.sha256").read_text(encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
