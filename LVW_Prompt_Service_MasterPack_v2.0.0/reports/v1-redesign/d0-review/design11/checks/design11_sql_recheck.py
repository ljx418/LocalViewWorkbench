#!/usr/bin/env python3
"""D0-B-REVIEW design1.1 independent recheck - storage/migration probes.

In-memory SQLite only (":memory:"), against the canonical baseline DDL plus
the design1.1 candidate migration. No production DB, no file DB, no product
runtime, no model, no media, no network.

The deterministic scene-hash function used here is *declared by this script*
from the contract's documented algorithm (plans/v1-multishot-contract.json ->
scene_hash): sha256 over UTF-8 canonical JSON with sort_keys=True,
separators=(',',':'), ensure_ascii=False, allow_nan=False, over exactly the 11
declared fields, with `verified` as a JSON boolean.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
OUT = Path(__file__).resolve().parent

checks: list[dict] = []


def ck(check_id: str, group: str, passed: bool, detail, severity_if_fail: str = "major") -> None:
    checks.append(
        {"id": check_id, "group": group, "passed": bool(passed), "severity_if_fail": severity_if_fail, "detail": detail}
    )


BASE_DDL = (ROOT / "contracts/storage.sql").read_text(encoding="utf-8")
MIGRATION = (ROOT / "contracts/v1-multishot-migration.sql").read_text(encoding="utf-8")
CONTRACT = json.loads((ROOT / "plans/v1-multishot-contract.json").read_text(encoding="utf-8"))

HASH_FIELDS = CONTRACT["scene_hash"]["fields"]
VALID_EDITORS = {"algorithm", "human"}


def declared_scene_hash(*args) -> str:
    """The hash function declared by the design (11 positional fields)."""
    if len(args) != len(HASH_FIELDS):
        raise ValueError("scene hash expects 11 fields")
    data = dict(zip(HASH_FIELDS, args))
    data["verified"] = bool(data["verified"])
    if data["editor"] not in VALID_EDITORS:
        raise ValueError("invalid editor vocabulary")
    payload = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fixture(bad_media_sha: bool = False, bad_editor: bool = False):
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(BASE_DDL)
    conn.execute("INSERT INTO schema_version VALUES(1,'before')")
    sha = "z" * 64 if bad_media_sha else "a" * 64
    conn.execute(
        "INSERT INTO media_ref VALUES('m',?,'video','{}',NULL,NULL,'before')", (sha,)
    )
    conn.execute(
        "INSERT INTO scene_revision VALUES('s','m',1,0,10,0,1,25,?)",
        ("robot" if bad_editor else "algorithm",),
    )
    conn.execute("INSERT INTO shot VALUES('manual','title',NULL,'{}','etag',NULL,'before')")
    conn.execute("INSERT INTO shot VALUES('image-shot','title','m','{}','etag',NULL,'before')")
    conn.execute("INSERT INTO shot VALUES('extra','title','m','{}','etag',NULL,'before')")
    conn.execute(
        "INSERT INTO prompt_revision VALUES('r','manual',NULL,'human','{}','unchanged','before','key')"
    )
    conn.commit()
    conn.create_function("lvw_scene_hash", 11, declared_scene_hash, deterministic=True)
    return conn


def applied_migration_tables(conn):
    return {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('scene_head','scene_revision_meta','shot_scene_binding','model_run_artifacts',"
            "'shot_analysis_binding','shot_analysis_evidence','revision_source_binding',"
            "'shot_batch_parent','shot_batch_item','shot_batch_seal','attempt_execution')"
        )
    }


# ------------------------------------------------------------------ S01 apply
conn = fixture()
conn.executescript(MIGRATION)
ck(
    "S01",
    "A_migration_apply",
    True,
    {
        "statement": "candidate migration executes on the canonical baseline DDL in memory",
        "new_tables": sorted(applied_migration_tables(conn)),
        "schema_version": conn.execute("SELECT max(version) FROM schema_version").fetchone()[0],
    },
)

# ------------------------------------------------------- S02 legacy scene rows
head = conn.execute("SELECT scene_id, head_revision_id, etag FROM scene_head").fetchall()
meta = conn.execute(
    "SELECT scene_revision_id, scene_id, revision, source_sha256, time_basis, verified, content_sha256, etag "
    "FROM scene_revision_meta"
).fetchall()
expected_hash = declared_scene_hash("m", "a" * 64, 1, 0, 10, 0, 1, 25, "algorithm", "unverified", 0)
expected_etag = f'"scene:s:{expected_hash}"'
ck(
    "S02",
    "B_legacy_backfill",
    len(head) == 1
    and head[0][0] == "s"
    and head[0][1] == "s"
    and head[0][2] == expected_etag
    and len(meta) == 1
    and meta[0][0] == "s"
    and meta[0][1] == "s"
    and meta[0][2] == 1
    and meta[0][3] == "a" * 64
    and meta[0][4] == "unverified"
    and meta[0][5] == 0
    and meta[0][6] == expected_hash
    and meta[0][7] == expected_etag,
    {
        "scene_head": head,
        "scene_revision_meta": meta,
        "independently_recomputed_hash": expected_hash,
        "independently_recomputed_etag": expected_etag,
        "note": "legacy scene keeps its id as the logical scene_id, is not falsely verified, and the hash/etag follow the declared algorithm",
    },
)

# --------------------------------------------------- S03 no invented revisions
rev = conn.execute("SELECT content_sha256 FROM prompt_revision WHERE id='r'").fetchone()
bindings = conn.execute("SELECT count(*) FROM shot_scene_binding").fetchone()[0]
shots = conn.execute("SELECT count(*) FROM shot").fetchone()[0]
legacy_batch_child = conn.execute(
    "SELECT count(*) FROM sqlite_master WHERE type='table' AND name='batch_child'"
).fetchone()[0]
ck(
    "S03",
    "B_legacy_backfill",
    rev[0] == "unchanged" and bindings == 0 and shots >= 2 and legacy_batch_child == 1,
    {
        "legacy_prompt_revision_content_sha256": rev[0],
        "shot_scene_binding_rows": bindings,
        "shot_rows": shots,
        "generic_batch_child_table_still_present": legacy_batch_child,
        "note": "manual/image shots are not force-bound and existing revision hashes are untouched",
    },
)

# ------------------------------------------------------- S04 immutability rules
def expect_abort(conn, sql, params=()):
    """Run one statement inside a savepoint so only that statement is undone."""
    conn.execute("SAVEPOINT probe_stmt")
    try:
        conn.execute(sql, params)
    except sqlite3.Error as exc:
        conn.execute("ROLLBACK TO probe_stmt")
        conn.execute("RELEASE probe_stmt")
        return True, str(exc)
    conn.execute("RELEASE probe_stmt")
    return False, None


abort_results = {}
for cid, sql, params in [
    ("scene_revision_update", "UPDATE scene_revision SET end_pts=20 WHERE id='s'", ()),
    ("scene_revision_delete", "DELETE FROM scene_revision WHERE id='s'", ()),
    ("scene_meta_update", "UPDATE scene_revision_meta SET revision=2 WHERE scene_revision_id='s'", ()),
    ("scene_meta_delete", "DELETE FROM scene_revision_meta WHERE scene_revision_id='s'", ()),
]:
    aborted, err = expect_abort(conn, sql, params)
    abort_results[cid] = {"aborted": aborted, "error": err}
ck(
    "S04",
    "C_immutability",
    all(v["aborted"] for v in abort_results.values()),
    abort_results,
)

# ------------------------------------------------------------ S05 batch sealing
for jid, kind in [("parent", "batch"), ("child1", "analyze"), ("child2", "analyze"),
                  ("parent2", "batch"), ("child3", "analyze"), ("child4", "analyze")]:
    conn.execute(
        "INSERT INTO job VALUES(?,?,?,'key-'||?,'hash-'||?,NULL,0,'{}',NULL,'before','before')",
        (jid, kind, "queued", jid, jid),
    )
conn.execute(
    "INSERT INTO shot_batch_parent VALUES('parent',?,2,'before','deadline',990,NULL)", ("b" * 64,)
)
sealed_too_early, err = expect_abort(
    conn, "INSERT INTO shot_batch_seal VALUES('parent',?,'now')", ("b" * 64,)
)
ck(
    "S05",
    "D_batch_plan",
    sealed_too_early,
    {
        "case": "seal before all planned children exist",
        "aborted": sealed_too_early,
        "error": err,
        "planned_count": 2,
        "items_present": 0,
    },
)

# an ordinal gap must not seal either
conn.execute(
    "INSERT INTO shot_batch_item VALUES('parent',0,'child1','manual','s',?,?,?,NULL)",
    ("c" * 64, "a" * 64, "d" * 64),
)
conn.execute(
    "INSERT INTO shot_batch_item VALUES('parent',2,'child2','image-shot','s',?,?,?,NULL)",
    ("c" * 64, "a" * 64, "d" * 64),
)
gap_seal, gap_err = expect_abort(conn, "INSERT INTO shot_batch_seal VALUES('parent',?,'now')", ("b" * 64,))
ck(
    "S06",
    "D_batch_plan",
    gap_seal,
    {
        "case": "plan with an ordinal gap (items 0 and 2 for planned_count=2) must not seal",
        "aborted": gap_seal,
        "error": gap_err,
        "note": "seal trigger requires count=planned_count AND min(ordinal)=0 AND max(ordinal)=planned_count-1",
    },
)

# a second parent with a contiguous plan seals normally
conn.execute(
    "INSERT INTO shot_batch_parent VALUES('parent2',?,2,'before','deadline',990,NULL)", ("e" * 64,)
)
conn.execute(
    "INSERT INTO shot_batch_item VALUES('parent2',0,'child3','manual','s',?,?,?,NULL)",
    ("c" * 64, "a" * 64, "d" * 64),
)
conn.execute(
    "INSERT INTO shot_batch_item VALUES('parent2',1,'child4','image-shot','s',?,?,?,NULL)",
    ("c" * 64, "a" * 64, "d" * 64),
)
claimable_before_seal = conn.execute(
    "SELECT count(*) FROM shot_batch_item i JOIN shot_batch_seal s ON s.parent_job_id=i.parent_job_id "
    "WHERE i.parent_job_id='parent2'"
).fetchone()[0]
seal_ok, seal_err = expect_abort(conn, "INSERT INTO shot_batch_seal VALUES('parent2',?,'now')", ("e" * 64,))
claimable_after_seal = conn.execute(
    "SELECT count(*) FROM shot_batch_item i JOIN shot_batch_seal s ON s.parent_job_id=i.parent_job_id "
    "WHERE i.parent_job_id='parent2'"
).fetchone()[0]
ck(
    "S07",
    "D_batch_plan",
    not seal_ok and claimable_before_seal == 0 and claimable_after_seal == 2,
    {
        "case": "a complete ordered plan seals, and a worker claim that joins the seal sees nothing before it",
        "seal_succeeded": not seal_ok,
        "seal_error": seal_err,
        "claimable_children_before_seal": claimable_before_seal,
        "claimable_children_after_seal": claimable_after_seal,
        "note": "docs/31: 'worker claim必须join seal，绝不领取未提交/未封印的半套计划'",
    },
)

post_seal = {}
for cid, sql, params in [
    ("append_after_seal", "INSERT INTO shot_batch_item VALUES('parent2',2,'child4','extra','s',?,?,?,NULL)", ("c" * 64, "a" * 64, "d" * 64)),
    ("update_item_after_seal", "UPDATE shot_batch_item SET shot_id='extra' WHERE parent_job_id='parent2' AND ordinal=0", ()),
    ("delete_item_after_seal", "DELETE FROM shot_batch_item WHERE parent_job_id='parent2' AND ordinal=0", ()),
    ("update_parent_after_seal", "UPDATE shot_batch_parent SET deadline_at='later' WHERE parent_job_id='parent2'", ()),
    ("delete_parent_after_seal", "DELETE FROM shot_batch_parent WHERE parent_job_id='parent2'", ()),
    ("update_seal_after_seal", "UPDATE shot_batch_seal SET sealed_at='later' WHERE parent_job_id='parent2'", ()),
]:
    aborted, err = expect_abort(conn, sql, params)
    post_seal[cid] = {"aborted": aborted, "error": err}
ck(
    "S08",
    "C_immutability",
    all(v["aborted"] for v in post_seal.values()),
    post_seal,
)

# ------------------------------------------------------ S09 constraint coverage
constraint_cases = {}
for cid, sql, params, expect_abort_flag in [
    (
        "meta_verified_mismatch",
        "INSERT INTO scene_revision_meta VALUES('s2','s',2,?,'decoded_pts',0,?,'e')",
        ("a" * 64, "b" * 64),
        True,
    ),
    (
        "meta_bad_hash_length",
        "INSERT INTO scene_revision_meta VALUES('s3','s',3,?,'unverified',0,'short','e')",
        ("a" * 64,),
        True,
    ),
    (
        "parent_budget_wrong",
        "INSERT INTO shot_batch_parent VALUES('p2',?,1,'before','deadline',123,NULL)",
        ("b" * 64,),
        True,
    ),
]:
    aborted, err = expect_abort(conn, sql, params)
    constraint_cases[cid] = {"aborted": aborted, "expected_abort": expect_abort_flag, "error": err}
ck(
    "S09",
    "E_constraints",
    all(v["aborted"] == v["expected_abort"] for v in constraint_cases.values()),
    {
        "cases": constraint_cases,
        "note": "verified<->decoded_pts pairing, 64-hex hash length and execution_budget_seconds=450*planned_count+90 are enforced by the DDL",
    },
)

fk = conn.execute("PRAGMA foreign_key_check").fetchall()
ck("S10", "E_constraints", not fk, {"foreign_key_check": fk})

# ---------------------------------------------------- S11 attempt_execution rows
conn.execute(
    "INSERT INTO attempt VALUES('att1','child1',1,'tok1',0,'running',NULL,NULL,'before',NULL)"
)
conn.execute("INSERT INTO attempt_execution(attempt_id, model_action_at, provider_call_id) VALUES('att1',NULL,NULL)")
not_started = conn.execute(
    "SELECT count(*) FROM attempt_execution WHERE attempt_id='att1' AND model_action_at IS NOT NULL"
).fetchone()[0]
conn.execute("UPDATE attempt_execution SET model_action_at='2026-11-11T00:00:00Z', provider_call_id='p1' WHERE attempt_id='att1'")
started = conn.execute(
    "SELECT count(*) FROM attempt_execution WHERE attempt_id='att1' AND model_action_at IS NOT NULL"
).fetchone()[0]
ck(
    "S11",
    "E_constraints",
    not_started == 0 and started == 1,
    {
        "case": "model_started is derived from a persisted attempted send, not from a claimed CPU task",
        "rows_with_send_before_update": not_started,
        "rows_with_send_after_update": started,
    },
)

# ------------------------------------------------------- S12 fail-closed legacy
conn_bad = fixture(bad_media_sha=True)
try:
    conn_bad.executescript(MIGRATION)
    failed_closed = False
    err = None
except sqlite3.Error as exc:
    failed_closed = True
    err = str(exc)
    try:
        conn_bad.rollback()
    except sqlite3.Error:
        pass
tables_after_fail = applied_migration_tables(conn_bad)
version_after_fail = conn_bad.execute("SELECT max(version) FROM schema_version").fetchone()[0]
ck(
    "S12",
    "F_fail_closed",
    failed_closed and not tables_after_fail and version_after_fail == 1,
    {
        "case": "legacy media row with a non-hex sha256 must abort the whole migration",
        "raised": failed_closed,
        "error": err,
        "tables_left_behind": sorted(tables_after_fail),
        "schema_version_after": version_after_fail,
        "note": "no half-applied DDL and no silent row loss",
    },
)

conn_bad_editor = fixture(bad_editor=True)
try:
    conn_bad_editor.executescript(MIGRATION)
    editor_failed = False
    editor_err = None
except sqlite3.Error as exc:
    editor_failed = True
    editor_err = str(exc)
    try:
        conn_bad_editor.rollback()
    except sqlite3.Error:
        pass
ck(
    "S13",
    "F_fail_closed",
    editor_failed and not applied_migration_tables(conn_bad_editor),
    {
        "case": "legacy scene with an editor value outside {algorithm,human} must abort (no invented vocabulary)",
        "raised": editor_failed,
        "error": editor_err,
        "tables_left_behind": sorted(applied_migration_tables(conn_bad_editor)),
    },
)


# ------------------------------------------- S14 mutable job rows, immutable plan
job_mutable, job_err = expect_abort(conn, "UPDATE job SET state='running' WHERE id='child1'")
ck(
    "S14",
    "G_separation",
    not job_mutable,
    {
        "case": "job/attempt status stays mutable under its own CAS while plan rows stay immutable",
        "job_update_rejected": job_mutable,
        "error": job_err,
        "job_state_after": conn.execute("SELECT state FROM job WHERE id='child1'").fetchone()[0],
    },
    severity_if_fail="major",
)

# ------------------------------------------- S15 required carrier columns exist
def columns(table):
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


carrier_expectations = {
    "shot_analysis_binding": {"model_run_id", "shot_id", "scene_revision_id", "scene_revision_hash",
                              "media_sha256", "config_hash", "attempt_id", "lease_token", "cancel_epoch"},
    "model_run_artifacts": {"model_run_id", "frames_json"},
    "shot_analysis_evidence": {"model_run_id", "raw_schema_version", "evidence_json", "evidence_sha256"},
    "revision_source_binding": {"revision_id", "model_run_id", "scene_revision_id", "scene_revision_hash"},
    "scene_revision_meta": {"scene_revision_id", "scene_id", "revision", "source_sha256", "time_basis",
                            "verified", "content_sha256", "etag"},
    "shot_batch_parent": {"parent_job_id", "plan_hash", "planned_count", "created_at", "deadline_at",
                          "execution_budget_seconds", "retry_of_parent_id"},
    "shot_batch_item": {"parent_job_id", "ordinal", "child_job_id", "shot_id", "scene_revision_id",
                        "scene_revision_hash", "media_sha256", "config_hash", "retry_of_child_id"},
    "shot_batch_seal": {"parent_job_id", "plan_hash", "sealed_at"},
    "attempt_execution": {"attempt_id", "model_action_at", "provider_call_id"},
}
carrier_report = {}
carrier_ok = True
for table, needed in carrier_expectations.items():
    have = columns(table)
    missing = sorted(needed - have)
    carrier_report[table] = {"missing": missing, "columns": sorted(have)}
    carrier_ok = carrier_ok and not missing
ck(
    "S15",
    "G_separation",
    carrier_ok,
    {
        "case": "every promised carrier column exists in the candidate migration",
        "per_table": carrier_report,
    },
    severity_if_fail="major",
)

# ------------------------------------------- S16 generic V2 batch_child untouched
legacy_batch_child_cols = sorted(r[1] for r in conn.execute("PRAGMA table_info(batch_child)"))
legacy_batch_child_rows = conn.execute("SELECT count(*) FROM batch_child").fetchone()[0]
ck(
    "S16",
    "G_separation",
    legacy_batch_child_cols == ["child_job_id", "parent_job_id"] and legacy_batch_child_rows == 0,
    {
        "case": "the generic V2 batch_child table keeps its original shape and stays empty",
        "columns": legacy_batch_child_cols,
        "rows": legacy_batch_child_rows,
    },
    severity_if_fail="major",
)

conn.close()
conn_bad.close()
conn_bad_editor.close()

result = {
    "kind": "D0_B_REVIEW_DESIGN11_INDEPENDENT_RECHECK_STORAGE_PROBES",
    "declared_hash_function": {
        "algorithm": CONTRACT["scene_hash"]["algorithm"],
        "fields": HASH_FIELDS,
        "implementation": "python hashlib.sha256 over json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=False, allow_nan=False).encode('utf-8')",
    },
    "checks": checks,
    "total": len(checks),
    "failed": sum(1 for c in checks if not c["passed"]),
    "product_actions": 0,
    "limits": "in-memory sqlite only; structural DDL constraints only, not implemented application handlers",
}
(OUT / "storage-recheck-results.json").write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print(json.dumps({"checks": len(checks), "failed": result["failed"], "failed_ids": [c["id"] for c in checks if not c["passed"]]}))
sys.exit(0)
