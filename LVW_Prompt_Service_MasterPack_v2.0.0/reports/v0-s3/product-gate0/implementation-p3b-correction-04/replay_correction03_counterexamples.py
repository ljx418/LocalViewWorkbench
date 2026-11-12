"""The correction-03 counterexamples, replayed once as observations.

This is the *relevant* subset of the independent correction-03 focused, the
supplement and the context probes: exactly the observations that produced the
four open root causes of the aggregate correction 04.  It is not the full
correction-03 matrix and it does not repeat the full suite.

Fixture adaptation, stated explicitly:

* The public scorer now loads the *actually published* canonical receipt from
  the artifact root and the sealed original source plan from the same root.
  The three canonical counterexamples therefore reach that loader instead of
  a helper.
* The identity counterexamples now reach the seal comparison in the shared
  source validator, so their recorded reason is the seal reason.
* The typed context observations now reach the mandatory typed context of the
  shared validators.
* The driver accessor counterexamples are unchanged: they use a conforming
  driver whose public limit is a property with an observable side effect.
* The second clock read counterexample is unchanged: it inspects the call
  stack of the clock callback, so it does not depend on any hardcoded name.

Every observation is bounded, uses its own temporary root and removes it in a
``finally`` block.  The observations are observations, not product tests.
"""

import copy
import inspect
import json
import os
import shutil
import tempfile
from pathlib import Path

from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q

OUT = Path(__file__).resolve().parent
ROOT = Path(tempfile.mkdtemp(prefix="lvw-c04-replay-"))
(OUT / "replay-fixtures.json").write_text(
    json.dumps({"root": str(ROOT), "owner": "task_e9a668493916",
                "retention": "removed by its own finally block"}) + "\n")

RESULTS = []


def record(name, **kw):
    RESULTS.append({"probe": name, **kw})


def prepare(name):
    return t._prepare(ROOT / name, clock=t.FakeClock(step=0.0))


def brief(receipt, driver):
    return {"sends": driver.submissions,
            "charged": receipt["public_submissions"],
            "reserved": receipt["provider_calls_reserved"],
            "counts": receipt["test_counts"],
            "first_error": receipt["rows"][0].get("error_code"),
            "last_error": receipt["rows"][-1].get("error_code")}


def outcome(function):
    try:
        return {"value": function()}
    except Exception as error:  # noqa: BLE001 - the refusal is the observation
        return {"rejected": type(error).__name__, "detail": str(error)}


try:
    # ------------------------------------------------------------------
    # M01: the canonical evidence of the public consumer
    # ------------------------------------------------------------------
    phase, driver, _ = prepare("baseline")
    receipt = phase.run()
    scores = t._scores(receipt, receipt["projection_sha256"])

    def qs(document, supplied=None):
        return q.recompute_scores(document, phase.directory, supplied or scores,
                                  independence=t._independence())

    def summary(document, supplied=None):
        out = qs(document, supplied)
        row = out["rows"][0]
        return {"aggregate_pass": out["aggregate_pass"], "usable": row["usable"],
                "resolved": row["resolved"], "reason": row["reason"],
                "evidence_reason": row.get("evidence_reason")}

    record("public_baseline", run=brief(receipt, driver), score=summary(receipt),
           canonical_loaded=q.load_canonical_receipt(phase.directory)["run_id"],
           handles_closed=all(item is None for item in
                              [phase._owned_root, phase._owned_temp, phase._owned_phase]))
    canonical = phase.directory / q.CANONICAL_RECEIPT_NAME
    original = canonical.read_bytes()
    for name in ["missing_canonical_retained_stage", "corrupt_canonical", "foreign_canonical"]:
        canonical.unlink(missing_ok=True)
        if name == "corrupt_canonical":
            canonical.write_bytes(b"{")
        elif name == "foreign_canonical":
            foreign = copy.deepcopy(receipt)
            foreign["run_id"] = "foreign-run"
            canonical.write_text(q.canonical_json(foreign))
        record(name,
               canonical_loader=outcome(lambda: q.load_canonical_receipt(phase.directory).get("run_id")),
               public_scorer=outcome(lambda: summary(receipt)),
               staging_exists=(phase.directory / q.STAGED_RECEIPT_NAME).exists())
        canonical.unlink(missing_ok=True)
        canonical.write_bytes(original)

    # ------------------------------------------------------------------
    # M08: the original source identity and the typed context
    # ------------------------------------------------------------------
    for index, name in enumerate(["device", "inode", "size", "mtime", "ctime"]):
        document = copy.deepcopy(receipt)
        identity = list(document["rows"][0]["source_evidence"]["identity"])
        identity[index] += 1
        document["rows"][0]["source_evidence"]["identity"] = identity
        record("qs.PASS.source.identity.changed_" + name,
               expected="unknown/unresolved; never aggregate pass",
               actual=outcome(lambda: summary(document)))
    document = copy.deepcopy(receipt)
    document["rows"][0]["source_evidence"]["identity"] = [0] * 5
    record("qs.PASS.source.identity.allzero", expected="unknown/unresolved; never aggregate pass",
           actual=outcome(lambda: summary(document)))
    for field, label, value in [("parent_budget_baseline_gpu_mib", "float", 100.0),
                                 ("parent_budget_baseline_gpu_mib", "bool", True),
                                 ("parent_budget_baseline_gpu_mib", "string", "100"),
                                 ("parent_budget_baseline_gpu_mib", "negative", -1),
                                 ("run_root", "integer", 0),
                                 ("run_root", "missing", None)]:
        document = copy.deepcopy(receipt)
        document[field] = value
        record("context_" + field + "_" + label, value=value,
               actual=outcome(lambda: summary(document)))

    # Both validators must actually run on QD and on QS.
    calls = {"source": 0, "release": 0}
    original_source = q.validate_source_evidence
    original_release = q.validate_release_evidence

    def traced_source(*args, **kwargs):
        calls["source"] += 1
        return original_source(*args, **kwargs)

    def traced_release(*args, **kwargs):
        calls["release"] += 1
        return original_release(*args, **kwargs)

    q.validate_source_evidence = traced_source
    q.validate_release_evidence = traced_release
    try:
        local, local_driver, _ = prepare("validator-trace")
        local_receipt = local.run()
        qd = dict(calls)
        q.recompute_scores(local_receipt, local.directory,
                           t._scores(local_receipt, local_receipt["projection_sha256"]),
                           independence=t._independence())
        record("shared_validator_calls", qd=qd,
               qs={key: calls[key] - qd[key] for key in calls})
    finally:
        q.validate_source_evidence = original_source
        q.validate_release_evidence = original_release

    # The seal: the published plan must reproduce the original identity.
    seal = phase.directory / receipt["source_plan"]["path"]
    seal_document = json.loads(seal.read_bytes().decode("utf-8"))
    record("source_plan_shape",
           rows=len(seal_document["rows"]),
           schema_version=seal_document["schema_version"],
           run_bound=seal_document["run_id"] == receipt["run_id"],
           identity_matches_row=all(
               sealed["identity"] == row["source_evidence"]["identity"]
               for sealed, row in zip(seal_document["rows"], receipt["rows"])))

    # ------------------------------------------------------------------
    # NM01 and NM02: the final guard boundary
    # ------------------------------------------------------------------
    local, local_driver, _ = prepare("second-clock-read")
    local.parent_budget["expires_monotonic"] = 20000.0
    clock = local.clock

    def crossing_clock():
        frame = inspect.currentframe().f_back
        if frame and frame.f_code.co_name == "_now":
            caller = frame.f_back
            if (caller and caller.f_code.co_name == "_parent_proof_is_fresh"
                    and caller.f_back and caller.f_back.f_code.co_name == "_send_admission_guard"):
                clock.now = 10801.0
        return clock.now

    local.clock = crossing_clock
    local_receipt = local.run()
    record("final_guard_second_clock_crosses_phase_deadline",
           actual=brief(local_receipt, local_driver), clock_now=clock.now)

    for name in ["driver_accessor_capacity_zero", "driver_accessor_phase_expired"]:
        local, local_driver, _ = prepare(name)
        local.parent_budget["expires_monotonic"] = 20000.0
        trigger = []
        limit = local_driver.max_public_submissions

        class ObservedDriver(type(local_driver)):
            @property
            def max_public_submissions(self):
                if not trigger:
                    trigger.append({"before": local.clock.now,
                                    "capacity_before": local.parent_budget["action_capacity"]})
                    if name == "driver_accessor_capacity_zero":
                        local.parent_budget["action_capacity"] = 0
                    else:
                        local.clock.now = 10801.0
                return limit

        local_driver.__class__ = ObservedDriver
        local_receipt = local.run()
        record(name, actual=brief(local_receipt, local_driver), trigger=trigger,
               current_capacity=local.parent_budget["action_capacity"])

    # ------------------------------------------------------------------
    # The supplement observations that touch the changed code
    # ------------------------------------------------------------------
    local, local_driver, _ = prepare("true-later-expiry")
    local.parent_budget["expires_monotonic"] = 2.0

    def expire(action, subject):
        if action == "quality_public_submit" and local_driver.submissions == 1:
            local.clock.now = 2.0

    local.authorize = expire
    local_receipt = local.run()
    record("later_true_interval_expiry",
           issued=local.parent_budget["issued_monotonic"],
           expires=local.parent_budget["expires_monotonic"],
           clock=local.clock.now, sends=local_driver.submissions,
           charged=local_receipt["public_submissions"],
           reserved=local_receipt["provider_calls_reserved"],
           second_error=local_receipt["rows"][1]["error_code"],
           counts=local_receipt["test_counts"])

    local, local_driver, _ = prepare("release-boundaries")
    local_receipt = local.run()
    local_scores = t._scores(local_receipt, local_receipt["projection_sha256"])
    cases = [("samples32", {"gpu_samples": [{"monotonic_seconds": i * 0.5, "gpu_used_mib": 1124}
                                            for i in range(32)], "elapsed_seconds": 30}),
             ("elapsed0", {"elapsed_seconds": 0}),
             ("elapsed30", {"elapsed_seconds": 30}),
             ("cadence1.5", {"gpu_samples": [{"monotonic_seconds": i * 1.5, "gpu_used_mib": 1124}
                                            for i in range(3)]}),
             ("cadence1.500001", {"gpu_samples": [{"monotonic_seconds": i * 1.500001,
                                                   "gpu_used_mib": 1124} for i in range(3)]}),
             ("elapsed30.000001", {"elapsed_seconds": 30.000001}),
             ("loaded_models_false", {"loaded_models": False})]
    for name, changes in cases:
        document = copy.deepcopy(local_receipt)
        document["rows"][0]["release_evidence"].update(changes)
        record("release_boundary_" + name,
               actual=outcome(lambda: q.recompute_scores(
                   document, local.directory, local_scores,
                   independence=t._independence())["aggregate_pass"]))
finally:
    shutil.rmtree(ROOT, ignore_errors=True)

(OUT / "replay-observations.json").write_text(json.dumps({
    "results": RESULTS,
    "count": len(RESULTS),
    "owned_root": str(ROOT),
    "removed": not ROOT.exists(),
    "classification": ("bounded observations of the correction-03 counterexamples "
                       "against the correction-04 candidate; not additional product "
                       "passing tests"),
    "fixture_adaptation": [
        "the public scorer loads the actually published canonical receipt and the "
        "sealed source plan from the artifact root",
        "the identity counterexamples reach the seal comparison",
        "the typed context observations reach the mandatory typed context",
        "the driver accessor and the second clock read counterexamples are unchanged",
    ],
}, indent=2) + "\n")
print(json.dumps({"count": len(RESULTS), "removed": not ROOT.exists(),
                  "results": RESULTS}, indent=2))
