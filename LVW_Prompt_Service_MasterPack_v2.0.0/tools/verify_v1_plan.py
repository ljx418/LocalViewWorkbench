#!/usr/bin/env python3
"""Deterministic, read-only validator for the approved V1 multi-shot plan package.

Scope (D0-B-IMPL): this tool checks the *plan package* only. It never runs
product code, never touches GPU/media/services/network, never writes files and
never declares a Stage PASS or a human signature.

Exit codes:
  0  every check passed (valid root plan)
  1  at least one deterministic check failed (invalid root plan)
  2  an input could not be read/parsed, so no verdict could be produced

The tool is stdlib-only. ``jsonschema`` is used for metaschema validation when
it happens to be importable, but the tool never requires that extra install:
a structural fallback check always runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
#   plans/release_gates.json, reports/v1-redesign/legacy-gates-before-change.json
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
    "batch_deadline_seconds": (1800, "max"),
    "automatic_model_retries": (0, "max"),
}

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
# Only this stage display name may be accounted against the R2 authority stage.
ALLOWED_AUTHORIZATION_MAP = {"V1-M1": "R2"}
FROZEN_GLOBAL_AUTHORITY = "AUTH-PROGRAM-V1-COMPLETE-03"

# Status/claim tokens that would mean the design package invented a result.
CLAIM_TOKENS = ("PASS", "APPROVED", "SIGNED", "RELEASED", "ACCEPTED", "COMPLETE")
# Statuses a case/stage may legitimately carry (plans/release_gates.json states).
ALLOWED_CASE_STATES = ("NOT_RUN", "PASS", "FAIL", "BLOCKED")
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


def as_list(value, label, report: Report, code: str = "E_INPUT_SHAPE"):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        report.add(code, "%s: expected a list of strings" % label)
        return []
    return list(value)


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
                report.add("E_CASE_DUPLICATE", "release_gates.%s.required_cases contains %s %d times" % (version, case_id, current.count(case_id)))


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
    """Each MS case exists exactly once as a case definition and stays NOT_RUN."""
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
    """No fixed resource limit may be relaxed."""
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
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            report.add("E_LIMIT_INVALID", "plan.limits.%s is not numeric: %r" % (key, value))
            continue
        if kind == "max" and value > frozen:
            report.add("E_LIMIT_LOOSED", "plan.limits.%s=%s relaxes the frozen maximum %s" % (key, value, frozen))
        if kind == "min" and value < frozen:
            report.add("E_LIMIT_LOOSED", "plan.limits.%s=%s relaxes the frozen minimum %s" % (key, value, frozen))


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
    if r22.get("status") == "PASS":
        report.add("E_R22_STATUS", "R22 cannot be PASS while the V1 package is only in design review")


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


def check_ownership(ctx) -> None:
    """D0 role separation and write-path ownership."""
    report, plan = ctx.report, ctx.plan
    stage_control = ctx.stage_control
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
    if not isinstance(workpacks, list):
        report.add("E_INPUT_SHAPE", "stage-control.json: missing 'workpacks' list")
    else:
        for workpack in workpacks:
            if isinstance(workpack, dict) and workpack.get("id") == "D0-B-IMPL":
                impl = workpack
        if impl is None:
            report.add("E_OWNERSHIP_WORKPACK", "stage-control.json has no D0-B-IMPL workpack")
        else:
            allowed = as_list(impl.get("allowed_files"), "stage-control.D0-B-IMPL.allowed_files", report)
            if allowed and allowed != list(FROZEN_D0_ALLOWED_FILES):
                report.add("E_OWNERSHIP_ALLOWED_FILES", "D0-B-IMPL allowed_files %s differ from the frozen allow-list %s" % (allowed, list(FROZEN_D0_ALLOWED_FILES)))
            commands = as_list(impl.get("commands"), "stage-control.D0-B-IMPL.commands", report)
            if commands and commands != list(FROZEN_D0_COMMANDS):
                report.add("E_OWNERSHIP_COMMANDS", "D0-B-IMPL commands %s differ from the frozen commands %s" % (commands, list(FROZEN_D0_COMMANDS)))
    forbidden = as_list(stage_control.get("forbidden_write_paths"), "stage-control.forbidden_write_paths", report)
    for path in FROZEN_D0_FORBIDDEN_PATHS:
        if path not in forbidden:
            report.add("E_OWNERSHIP_FORBIDDEN_PATHS", "stage-control.forbidden_write_paths does not contain %s" % path)

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
            continue
        schema_required = definition.get("required")
        if sorted(schema_required or []) != sorted(required):
            report.add("E_CONTRACT_SCHEMA_MISMATCH", "contract entity %s requires %s but the candidate schema requires %s" % (name, sorted(required), sorted(schema_required or [])))
    shot = entities.get("ShotEvidence") or {}
    if isinstance(shot, dict):
        for key, def_name in (("character_fields", "Character"), ("action_fields", "Action")):
            fields = shot.get(key)
            definition = defs.get(def_name) or {}
            if isinstance(fields, list) and sorted(fields) != sorted(definition.get("required") or []):
                report.add("E_CONTRACT_SCHEMA_MISMATCH", "contract ShotEvidence.%s %s differs from candidate schema %s.required %s" % (key, sorted(fields), def_name, sorted(definition.get("required") or [])))
    children = defs.get("BatchChildrenResponse") or {}
    if "total" not in (children.get("required") or []):
        report.add("E_CONTRACT_SCHEMA_MISMATCH", "candidate schema BatchChildrenResponse must keep the fixed denominator field 'total'")


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


def check_spec_fence(ctx) -> None:
    """Every file frozen in the authority spec manifest must still hash the same."""
    report = ctx.report
    files = ctx.spec_manifest.get("files")
    if not isinstance(files, dict) or not files:
        report.add("E_INPUT_SHAPE", "spec-manifest.json: missing 'files' object")
        return
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
    parser.add_argument("--stage-control", default=".agent-governance/stages/V1-D0/stage-control.json")
    parser.add_argument("--spec-manifest", default=".agent-governance/stages/V1-D0/spec-manifest.json")
    parser.add_argument("--approval", default="reports/v1-redesign/product-change-approval.json")
    parser.add_argument("--execution-control", default="plans/execution-control.json")
    parser.add_argument("--r1-packet-dir", default=".agent-governance/stages/R1")
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

    ctx.plan = documents["plan"]
    ctx.baseline = documents["baseline"]
    ctx.gates = documents["gates"]
    ctx.cases = documents["cases"]
    ctx.requirements = documents["requirements"]
    ctx.tasks = documents["tasks"]
    ctx.contract = documents["contract"]
    ctx.schema = documents["contract-schema"]
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
    check_stages_and_dag(ctx)
    check_task_dag(ctx)
    check_requirement_coverage(ctx)
    check_status_and_human_claims(ctx)
    check_ownership(ctx)
    check_authorization_accounting(ctx)
    check_contract_and_schema(ctx)
    check_immutability(ctx)
    check_spec_fence(ctx)

    errors = sorted(ctx.report.errors)
    for code, detail in errors:
        sys.stdout.write("%s: %s\n" % (code, detail))
    if errors:
        sys.stdout.write("RESULT: FAIL (%d finding(s))\n" % len(errors))
        return 1
    gate_v1 = len(((ctx.gates.get("gates") or {}).get("V1") or {}).get("required_cases") or [])
    sys.stdout.write(
        "RESULT: PASS (V1=%d V2=%d V3=%d; MS01-MS08 once; legacy prefix intact; DAG acyclic; no human signature claimed)\n"
        % (
            gate_v1,
            len(((ctx.gates.get("gates") or {}).get("V2") or {}).get("required_cases") or []),
            len(((ctx.gates.get("gates") or {}).get("V3") or {}).get("required_cases") or []),
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
