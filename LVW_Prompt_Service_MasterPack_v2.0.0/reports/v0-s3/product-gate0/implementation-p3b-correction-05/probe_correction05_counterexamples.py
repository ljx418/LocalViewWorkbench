"""The bounded public-owner counterexamples of the correction-04 review.

The four independent findings of the correction-04 review are replayed here
against the corrected implementation, in private owned roots, through the
public production-owner path.  Every probe states the prerequisite that it
needs and the observable outcome that it produced.

The probes are *observations*, not product tests: the product obligations
themselves are the test suite of ``tools/test_v0_s3_quality_phase.py``.  This
file exists so that an independent reviewer can see the very same
counterexamples that produced the four findings, with their new outcomes.

It never opens a socket, never starts a host process, never calls a model and
never touches the frozen quality set.  It is executed only through the
inspected guarded runner of this batch.
"""

import copy
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q

OUT = Path(__file__).resolve().parent
ROOT = Path(tempfile.mkdtemp(prefix="lvw-c05-counterexamples-"))
RESULTS = []


def record(name, **kw):
    RESULTS.append({"probe": name, **kw})


def prep(name):
    return t._prepare(ROOT / name, clock=t.FakeClock(step=0.0))


def brief(p, d, r):
    return {
        "sends": d.submissions,
        "charges": r["public_submissions"],
        "reserved": r["provider_calls_reserved"],
        "observed": r["provider_calls_observed"],
        "counts": r["test_counts"],
        "rows": len(r["rows"]),
        "first_error": r["rows"][0].get("error_code"),
        "last_error": r["rows"][-1].get("error_code"),
        "storage_unproven": r["storage_unproven"],
        "cleanup_unproven": r["cleanup_unproven"],
        "closed": all(getattr(p, n) is None for n in ("_owned_root", "_owned_temp", "_owned_phase")),
        "retries": sum(x.get("automatic_retries", 0) for x in r["rows"]),
    }


def scores_for(r):
    """The independent scores of the rows that really preserved a raw.

    A row that never preserved a raw cannot be scored at all; the score
    receipt of such a row is not invented here.
    """
    out = []
    for row in r["rows"]:
        if not isinstance(row.get("raw_sha256"), str) or not isinstance(row.get("raw_artifact"), str):
            continue
        out.append(t._score_for(row, projection_sha=r["projection_sha256"]))
    return out


def score(r, p, s=None):
    try:
        o = q.recompute_scores(r, p, s if s is not None else scores_for(r),
                               independence=t._independence())
        return {
            "aggregate": o["aggregate_pass"],
            "resolved": o["all_rows_resolved"],
            "decision": o["decision"],
            "thresholds": o["thresholds"],
            "first": o["rows"][0],
        }
    except Exception as error:  # noqa: BLE001 - the refusal is the observation
        return {"rejected": type(error).__name__, "detail": str(error)}


def canon(p, r):
    (p.directory / q.CANONICAL_RECEIPT_NAME).write_text(q.canonical_json(r))


try:
    # ------------------------------------------------------------------
    # The honest baseline: one genuine public production-owner run and the
    # independent scoring of that very run.
    # ------------------------------------------------------------------
    p, d, _ = prep("baseline")
    r = p.run()
    original = copy.deepcopy(r)
    record("baseline",
           run=brief(p, d, r),
           qs=score(r, p.directory),
           actual_files=sum(x.is_file() for x in p.directory.rglob("*")),
           actual_bytes=sum(x.stat().st_size for x in p.directory.rglob("*") if x.is_file()),
           seal_initial_bytes=(p.directory / q.SOURCE_PLAN_NAME).stat().st_size)

    # ------------------------------------------------------------------
    # M01: the canonical document is the authority.
    # ------------------------------------------------------------------
    # A genuine run with one injected unknown validation failure after the
    # actual owner and the actual oracle.  The raw, the source and the
    # release evidence of that row stay intact.
    p2, d2, _ = prep("unknown-validation")
    validate = p2._validate_row

    def unknown(row, *args):
        validate(row, *args)
        if row["ordinal"] == 1:
            raise q.QualityContractError("INDEPENDENT_UNKNOWN_VALIDATION")

    p2._validate_row = unknown
    r2 = p2.run()
    record("published_unknown_failure", run=brief(p2, d2, r2), qs=score(r2, p2.directory))
    doc = copy.deepcopy(r2)
    doc["rows"][0]["error_code"] = "PUBLIC_EXECUTION_NOT_SUCCESSFUL"
    record("published_unknown_failure_supplied_known_error",
           qs=score(doc, p2.directory),
           canonical_error=r2["rows"][0]["error_code"],
           only_changed="supplied rows[0].error_code",
           expected="the published unknown failure stays unresolved")

    # One genuine known structure failure: a supplied PASS never makes it
    # usable, the row stays resolved and not usable, and the critical count
    # stays global.
    p3, d3, _ = prep("known-failure")
    validate = p3._validate_row

    def known(row, *args):
        validate(row, *args)
        if row["ordinal"] == 1:
            raise q.QualityContractError("PUBLIC_EXECUTION_NOT_SUCCESSFUL")

    p3._validate_row = known
    r3 = p3.run()
    doc = copy.deepcopy(r3)
    doc["rows"][0].update(execution_status="PASS", error_code=None)
    record("published_fail_supplied_pass", run=brief(p3, d3, r3), qs=score(doc, p3.directory))
    scores = t._scores(r3, r3["projection_sha256"])
    scores[0]["critical_hallucinations"] = 3
    record("published_fail_critical3", qs=score(r3, p3.directory, scores))

    # Caller-only rewriting of the actual execution facts.
    for name, mutate in [
            ("valid_but_fabricated_release_samples",
             lambda x: x["rows"][0]["release_evidence"].update(
                 gpu_samples=[{"monotonic_seconds": i, "gpu_used_mib": 0} for i in range(3)])),
            ("fabricated_bound_baseline_and_release",
             lambda x: (x.update(parent_budget_baseline_gpu_mib=200),
                        [a["release_evidence"].update(baseline_gpu_mib=200) for a in x["rows"]])),
            ("fabricated_terminal_counts",
             lambda x: x.update(test_counts={"fixed": 16, "PASS": 0, "FAIL": 16,
                                             "BLOCKED": 0, "NOT_RUN": 0})),
            ("fabricated_attempt_row",
             lambda x: x["rows"][0].update(public_submission_attempted=False)),
            ("fabricated_run_context",
             lambda x: x.update(run_root=str(x["run_root"]) + "-elsewhere")),
    ]:
        doc = copy.deepcopy(r)
        mutate(doc)
        record(name,
               qs=score(doc, p.directory),
               canonical_unchanged=json.loads(
                   (p.directory / q.CANONICAL_RECEIPT_NAME).read_text())["rows"][0]["release_evidence"]
               == original["rows"][0]["release_evidence"],
               expected="the fabricated fact is refused or leaves the row unresolved")

    # ------------------------------------------------------------------
    # M08: the seal must describe the very same canonical execution row.
    # ------------------------------------------------------------------
    planpath = p.directory / q.SOURCE_PLAN_NAME
    planraw = planpath.read_bytes()
    for field, value in [("asset_id", "FOREIGN-ASSET"), ("media_kind", "video"),
                         ("input_reference", "foreign.png")]:
        altered = copy.deepcopy(json.loads(planraw))
        altered["rows"][0][field] = value
        raw = q.canonical_json(altered).encode()
        planpath.write_bytes(raw)
        doc = copy.deepcopy(r)
        doc["source_plan"].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        canon(p, doc)
        record("seal_label_alignment." + field,
               qs=score(doc, p.directory),
               prerequisites=("write the seal bytes and the canonical source_plan binding; "
                              "the canonical execution rows and the raw stay untouched"),
               expected="the contradictory seal row never certifies the execution row")
    planpath.write_bytes(planraw)
    canon(p, r)

    for name, mutator in [
            ("swap_whole_rows",
             lambda x: x["rows"].__setitem__(slice(0, 2), list(reversed(x["rows"][:2])))),
            ("swap_descriptor",
             lambda x: x["rows"][0].update(identity=x["rows"][1]["identity"],
                                           path=x["rows"][1]["path"]))]:
        altered = copy.deepcopy(json.loads(planraw))
        mutator(altered)
        raw = q.canonical_json(altered).encode()
        planpath.write_bytes(raw)
        doc = copy.deepcopy(r)
        doc["source_plan"].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        canon(p, doc)
        record("seal_swap." + name,
               qs=score(doc, p.directory),
               expected="the swapped seal never certifies the execution row")
    planpath.write_bytes(planraw)
    canon(p, r)

    # The accepted trust boundary: a *coherent* rewrite of both trusted
    # originals.  The root accepted that this is not a new cryptographic
    # signature obligation; the parent has to bind the selected owned
    # archive or an independent attestation before a real run.
    altered = copy.deepcopy(json.loads(planraw))
    altered["rows"][0]["identity"][0] += 1
    raw = q.canonical_json(altered).encode()
    planpath.write_bytes(raw)
    doc = copy.deepcopy(r)
    doc["rows"][0]["source_evidence"]["identity"][0] += 1
    doc["source_plan"].update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    canon(p, doc)
    record("consistent_seal_and_canonical_identity_rewrite",
           qs=score(doc, p.directory),
           prerequisites=("write the original seal, the authoritative canonical row and the "
                         "source_plan hash, plus the supplied receipt; no independent parent "
                         "attestation is supplied"),
           accepted_trust_boundary=("a total coherent rewrite of both trusted originals is not a "
                                    "new cryptographic-signature obligation; the parent must bind "
                                    "the selected owned archive or an independent attestation "
                                    "before a real consumer run (integration NOT_PROVEN)"))
    planpath.write_bytes(planraw)
    canon(p, r)

    # ------------------------------------------------------------------
    # NM03: the strict artifact ancestry of the scoring entry point.
    # ------------------------------------------------------------------
    p5, d5, _ = prep("temp-redirect")
    r5 = p5.run()
    (p5.root / "temp").rename(p5.root / "retained-temp")
    (p5.root / "temp").symlink_to(p5.root / "retained-temp", target_is_directory=True)
    record("qs_temp_ancestor_symlink",
           qs=score(r5, p5.directory),
           symlink=str(p5.root / "temp"),
           canonical_bytes_unchanged=True,
           expected="the redirected ancestor is refused, never resolved away")
    (p5.root / "temp").unlink()
    (p5.root / "retained-temp").rename(p5.root / "temp")

    p6, d6, _ = prep("phase-redirect")
    r6 = p6.run()
    (p6.root / "temp" / "s3-quality").rename(p6.root / "temp" / "retained-phase")
    (p6.root / "temp" / "s3-quality").symlink_to(p6.root / "temp" / "retained-phase",
                                                 target_is_directory=True)
    record("qs_phase_ancestor_symlink", qs=score(r6, p6.directory),
           expected="the redirected phase directory is refused")

    p7, d7, _ = prep("leaf-redirect")
    r7 = p7.run()
    canonical = p7.directory / q.CANONICAL_RECEIPT_NAME
    staged = p7.directory / q.STAGED_RECEIPT_NAME
    before = canonical.read_bytes()
    canonical.unlink()
    canonical.symlink_to(staged)
    record("qs_canonical_leaf_symlink", qs=score(r7, p7.directory),
           bytes_unchanged=canonical.read_bytes() == before,
           expected="the redirected leaf is refused")

    # ------------------------------------------------------------------
    # NM04: the final source handoff.
    # ------------------------------------------------------------------
    p8, d8, _ = prep("limit-source-identity-changed")
    p8.parent_budget["expires_monotonic"] = 20000.0
    trigger = []
    originalclass = type(d8)

    class Driver(originalclass):
        def __getattribute__(self, key):
            value = super().__getattribute__(key)
            if key == "max_public_submissions" and not trigger:
                trigger.append(key)
                source = p8.root / "input" / json.loads(p8.projection_bytes)["samples"][0]["input_reference"]
                st = source.stat()
                os.utime(source, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000))
            return value

    d8.__class__ = Driver
    r8 = p8.run()
    source = p8.root / "input" / r8["rows"][0]["input_reference"]
    actual = p8._identity(source.stat())
    sealed = json.loads((p8.directory / q.SOURCE_PLAN_NAME).read_text())["rows"][0]["identity"]
    record("limit_source_identity_changed",
           run=brief(p8, d8, r8),
           trigger=trigger,
           actual_identity=actual,
           sealed_identity=sealed,
           changed=actual != sealed,
           qs=score(r8, p8.directory),
           expected=("zero sends, zero charges and zero reserved calls, and sixteen terminal "
                     "refusals"))

    # The later source change: the earlier attempts and charges stay real and
    # every later send stops.
    p9, d9, _ = prep("later-source-identity-changed")
    p9.parent_budget["expires_monotonic"] = 20000.0
    reads = []
    originalclass = type(d9)

    class LaterDriver(originalclass):
        def __getattribute__(self, key):
            value = super().__getattribute__(key)
            if key == "max_public_submissions":
                reads.append(key)
                if len(reads) == 6:
                    # The accessor of the sixth row changes the source of
                    # that row, after the five earlier rows really ran.
                    samples = json.loads(p9.projection_bytes)["samples"]
                    source = p9.root / "input" / samples[5]["input_reference"]
                    st = source.stat()
                    os.utime(source, ns=(st.st_atime_ns, st.st_mtime_ns + 1000000))
            return value

    d9.__class__ = LaterDriver
    r9 = p9.run()
    record("later_source_identity_changed",
           run=brief(p9, d9, r9),
           trigger=reads,
           changed_row_error=r9["rows"][5].get("error_code"),
           qs=score(r9, p9.directory),
           expected=("the earlier attempts and charges are preserved and every later send stops"))
finally:
    shutil.rmtree(ROOT, ignore_errors=True)

payload = {"results": RESULTS, "count": len(RESULTS), "owned_root": str(ROOT),
           "removed": not ROOT.exists()}
(OUT / "counterexample-observations.json").write_text(
    json.dumps(payload, indent=2, sort_keys=True) + "\n")
print(json.dumps(payload, indent=2, sort_keys=True))
