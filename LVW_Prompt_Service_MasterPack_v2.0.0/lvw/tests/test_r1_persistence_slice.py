"""The component oracles of the R1 core persistence slice.

Every oracle drives the PUBLIC FastAPI routes in process against a REAL
SQLite database in a fresh owned scratch root.  The provider and the
runtime are refused by the mocks: they only prove that the manual path
invokes neither of them.  The database and the repositories are never
faked: the rollback, the concurrency, the immutability and the busy
failures are real SQLite behaviours.

The data of every oracle is synthetic and owned by the oracle: no
existing user database, no old uploaded file and no external socket is
ever touched.
"""
from __future__ import annotations

import hashlib
import io
import json
import sqlite3
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import Settings
from app.main import create_app
from app.models import Domains, PromptSpec, Technical
from app.storage import CORE_SCHEMA, Database

ROOT = Path(__file__).resolve().parents[2]
CANONICAL_STORAGE = (ROOT / "contracts" / "storage.sql").read_text(encoding="utf-8")


# -- the fakes that may only refuse ---------------------------------------
class ForbiddenProvider:
    """A provider that refuses every call: the manual path needs none."""

    model = "gemma4:26b"

    def __init__(self):
        self.calls = 0

    async def readiness(self):
        self.calls += 1
        raise AssertionError("the manual path must not call the provider")

    async def analyze(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("the manual path must not call the provider")


class ForbiddenRuntime:
    """A runtime that refuses every call: the manual path needs none."""

    def __init__(self):
        self.calls = 0

    async def status(self):
        self.calls += 1
        raise AssertionError("the manual path must not call the runtime")

    async def start(self):
        self.calls += 1
        raise AssertionError("the manual path must not call the runtime")

    async def reset(self):
        self.calls += 1
        raise AssertionError("the manual path must not call the runtime")

    async def stop(self):
        self.calls += 1
        raise AssertionError("the manual path must not call the runtime")

    async def close(self):
        return None


class CountingProvider:
    """The provider of the existing analysis path, with a call counter."""

    model = "gemma4:26b"

    def __init__(self):
        self.calls = 0

    async def readiness(self):
        self.calls += 1
        return {"ready": True, "model": self.model, "reason": None, "loaded": True}

    async def analyze(self, image_path, *, mode, content_profile="standard", custom_guidance=""):
        self.calls += 1
        spec = PromptSpec(mode=mode,
            domains=Domains(observation=["A cobalt square fills the frame."], inference=[],
                            user_evidence=[], creative_intent=[], unknowns=[]),
            technical=Technical(duration_seconds=None, aspect_ratio="", fps_intent=None,
                                camera_motion="", subject_action="", lighting="",
                                composition="centered", style_notes="", beats=[]),
            locked_fields=[], text_zh="画面中央的钴蓝色方块", text_en="Cobalt square",
            tags=["cobalt"], negative="blur", template_id="lvw-r1a-image",
            template_version="1.0.0")
        return json.dumps({"message": {"content": "fixture"}}), spec


# -- the database seam -----------------------------------------------------
class AuthorizerDatabase(Database):
    """A database whose connections carry a REAL SQLite authorizer.

    The authorizer denies one real statement of the real path, so the
    failure of the oracle is a real SQLite failure and never a faked
    one.
    """

    def __init__(self, path, *, deny: str | None = None):
        super().__init__(path)
        self.deny = deny

    def connect(self):
        connection = super().connect()
        deny = self.deny
        if deny is not None:
            def authorizer(action, arg1, arg2, db_name, trigger):
                if deny == "create" and action == sqlite3.SQLITE_CREATE_TABLE:
                    return sqlite3.SQLITE_DENY
                if deny == "update_shot" and action == sqlite3.SQLITE_UPDATE and arg1 == "shot":
                    return sqlite3.SQLITE_DENY
                if deny == "insert_media" and action == sqlite3.SQLITE_INSERT and arg1 == "media_ref":
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            connection.set_authorizer(authorizer)
        return connection


# -- the helpers -----------------------------------------------------------
def _client(data_root: Path, *, provider=None, runtime=None, database=None):
    """One app of the public routes over an owned scratch root."""
    app = create_app(Settings.local(data_root=data_root),
                     provider=provider or ForbiddenProvider(),
                     runtime=runtime or ForbiddenRuntime(),
                     database=database)
    return TestClient(app), app


def _spec(text: str = "画面中央的钴蓝色方块", *, locked=(), evidence=()):
    """A canonical specification of the public contract."""
    return {"schema_version": "lvw.prompt/1", "mode": "realistic",
            "domains": {"observation": [text], "inference": [], "user_evidence": list(evidence),
                        "creative_intent": [], "unknowns": []},
            "technical": {"duration_seconds": None, "aspect_ratio": "16:9", "fps_intent": None,
                          "camera_motion": "固定", "subject_action": "静止", "lighting": "柔光",
                          "composition": "居中", "style_notes": "", "beats": []},
            "locked_fields": list(locked), "text_zh": text, "text_en": "Cobalt square",
            "tags": ["钴蓝"], "negative": "模糊, 水印", "template_id": "lvw-r1a-image",
            "template_version": "1.0.0"}


def _shot_body(title: str = "镜头", *, media_ref_id=None, spec=None):
    return {"title": title, "media_ref_id": media_ref_id, "spec": spec or _spec()}


def _jpeg_bytes() -> bytes:
    """A synthetic JPEG: its sanitised copy is a genuinely other file."""
    output = io.BytesIO()
    Image.new("RGB", (64, 40), (42, 91, 212)).save(output, format="JPEG")
    return output.getvalue()


def _rows(data_root: Path, sql: str, params=()):
    """The rows of the owned database of the oracle."""
    connection = sqlite3.connect(data_root / "lvw.sqlite3")
    try:
        return connection.execute(sql, params).fetchall()
    finally:
        connection.close()


def _tables(data_root: Path) -> set[str]:
    return {row[0] for row in _rows(data_root, "SELECT name FROM sqlite_master WHERE type='table'")}


def _create_shot(client, *, key="shot-1", title="镜头", spec=None):
    response = client.post("/api/v1/shots", headers={"Idempotency-Key": key},
                           json=_shot_body(title, spec=spec))
    assert response.status_code == 201, response.text
    return response.json()["data"]


def _append_revision(client, shot, *, key, parent, spec=None, author="human"):
    response = client.post("/api/v1/prompts/revisions",
                           headers={"Idempotency-Key": key, "If-Match": shot["etag"]},
                           json={"shot_id": shot["id"], "parent_id": parent, "author": author,
                                 "spec_snapshot": spec or _spec()})
    return response


# -- the oracles ------------------------------------------------------------
def test_pp01_unknown_schema_fails_closed(tmp_path):
    """PP01: an unknown or malformed database is refused and never rewritten."""
    root = tmp_path / "data"
    root.mkdir()
    database = root / "lvw.sqlite3"
    database.write_bytes(b"this is not a database\n")
    before = database.read_bytes()
    client, _ = _client(root)
    response = client.post("/api/v1/shots", headers={"Idempotency-Key": "k"},
                           json=_shot_body())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNSUPPORTED_VERSION"
    assert database.read_bytes() == before

    other = tmp_path / "other"
    other.mkdir()
    path = other / "lvw.sqlite3"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE schema_version(version INTEGER PRIMARY KEY, "
                       "applied_at TEXT NOT NULL)")
    connection.execute("INSERT INTO schema_version VALUES(2, 'before')")
    connection.commit()
    connection.close()
    client, _ = _client(other)
    response = client.post("/api/v1/shots", headers={"Idempotency-Key": "k"},
                           json=_shot_body())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNSUPPORTED_VERSION"

    broken = tmp_path / "broken"
    broken.mkdir()
    connection = sqlite3.connect(broken / "lvw.sqlite3")
    connection.execute("CREATE TABLE schema_version(version INTEGER PRIMARY KEY, "
                       "applied_at TEXT NOT NULL)")
    connection.execute("INSERT INTO schema_version VALUES(1, 'before')")
    connection.commit()
    connection.close()
    client, _ = _client(broken)
    response = client.post("/api/v1/shots", headers={"Idempotency-Key": "k"},
                           json=_shot_body())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_SCHEMA_INVALID"
    assert _tables(broken) == {"schema_version"}


def test_pp02_core_bootstrap_reopen(tmp_path):
    """PP02: the fresh version 1 bootstrap is atomic, minimal and reopenable."""
    root = tmp_path / "data"
    client, _ = _client(root)
    _create_shot(client)
    tables = _tables(root)
    assert {"schema_version", "media_ref", "shot", "prompt_revision",
            "media_blob", "idempotency_record"} <= tables
    assert not (tables & {"scene_head", "scene_revision_meta", "shot_scene_binding",
                          "model_run_artifacts", "shot_analysis_binding", "asset",
                          "asset_link", "recipe_revision", "job", "attempt", "model_run",
                          "outbox", "receipt", "evidence_ref", "external_link",
                          "workflow_allowlist", "batch_child", "scene_revision"})
    assert not any("fts" in name.lower() for name in tables)
    assert _rows(root, "SELECT version FROM schema_version")[0][0] == 1
    for statement in CORE_SCHEMA:
        assert statement in CANONICAL_STORAGE

    restarted, _ = _client(root)
    assert restarted.get("/health").status_code == 200
    assert len(_rows(root, "SELECT id FROM shot")) == 1

    fault_root = tmp_path / "fault"
    faulty = AuthorizerDatabase(fault_root / "lvw.sqlite3", deny="create")
    client, _ = _client(fault_root, database=faulty)
    response = client.post("/api/v1/shots", headers={"Idempotency-Key": "k"},
                           json=_shot_body())
    assert response.status_code == 503
    assert _tables(fault_root) == set()


def test_pp03_public_manual_restart(tmp_path):
    """PP03: a manual shot survives a restart with the same draft and token."""
    root = tmp_path / "data"
    provider = ForbiddenProvider()
    client, _ = _client(root, provider=provider)
    shot = _create_shot(client, title="空镜头")
    assert shot["head_revision_id"] is None
    assert shot["media_ref_id"] is None
    fetched = client.get("/api/v1/shots/%s" % shot["id"])
    assert fetched.status_code == 200
    assert fetched.json()["data"] == shot
    assert fetched.headers["ETag"] == shot["etag"]
    assert fetched.json()["schema_version"] == "lvw.api/1"

    restarted, _ = _client(root, provider=provider)
    again = restarted.get("/api/v1/shots/%s" % shot["id"])
    assert again.status_code == 200
    assert again.json()["data"] == shot
    assert again.headers["ETag"] == shot["etag"]
    assert provider.calls == 0


def test_pp04_upload_restart_copy_identity(tmp_path):
    """PP04: the upload keeps the source identity and the copy identity apart."""
    root = tmp_path / "data"
    client, _ = _client(root)
    payload = _jpeg_bytes()
    response = client.post("/api/v1/media", headers={"Idempotency-Key": "media-1"},
                           files={"file": ("shot.jpg", payload, "image/jpeg")})
    assert response.status_code == 201, response.text
    ref = response.json()["data"]
    assert ref["sha256"] == hashlib.sha256(payload).hexdigest()
    assert ref["bytes"] == len(payload)
    assert ref["source_root_id"] is None and ref["relative_path"] is None
    stored = _rows(root, "SELECT stored_name, stored_sha256, stored_bytes FROM media_blob")[0]
    assert stored[1] != ref["sha256"]
    copy = root / "media" / stored[0]
    assert copy.is_file()
    assert hashlib.sha256(copy.read_bytes()).hexdigest() == stored[1]
    assert stored[2] == copy.stat().st_size

    restarted, _ = _client(root)
    again = restarted.get("/api/v1/media/%s" % ref["id"])
    assert again.status_code == 200
    assert again.json()["data"] == ref


def test_pp05_durable_idempotency(tmp_path):
    """PP05: the idempotency of a shot is durable and never merges a payload."""
    root = tmp_path / "data"
    client, _ = _client(root)
    first = client.post("/api/v1/shots", headers={"Idempotency-Key": "same"},
                        json=_shot_body())
    assert first.status_code == 201
    second = client.post("/api/v1/shots", headers={"Idempotency-Key": "same"},
                         json=_shot_body())
    assert second.status_code == 201
    assert second.json()["data"]["id"] == first.json()["data"]["id"]
    conflict = client.post("/api/v1/shots", headers={"Idempotency-Key": "same"},
                           json=_shot_body("另一个镜头"))
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    assert len(_rows(root, "SELECT id FROM shot")) == 1

    restarted, _ = _client(root)
    replay = restarted.post("/api/v1/shots", headers={"Idempotency-Key": "same"},
                             json=_shot_body())
    assert replay.status_code == 201
    assert replay.json()["data"]["id"] == first.json()["data"]["id"]
    assert len(_rows(root, "SELECT id FROM shot")) == 1
    assert len(_rows(root, "SELECT scope, key FROM idempotency_record")) == 1


def test_pp06_cas_preconditions(tmp_path):
    """PP06: the compare-and-set of the draft needs the current token."""
    root = tmp_path / "data"
    client, _ = _client(root)
    shot = _create_shot(client)
    missing = client.put("/api/v1/shots/%s" % shot["id"], json=_shot_body("改写"))
    assert missing.status_code == 428
    assert missing.json()["error"]["code"] == "PRECONDITION_REQUIRED"
    stale = client.put("/api/v1/shots/%s" % shot["id"],
                       headers={"If-Match": '"shot:%s"' % ("0" * 64)},
                       json=_shot_body("改写"))
    assert stale.status_code == 412
    assert stale.json()["error"]["code"] == "ETAG_MISMATCH"

    updated = client.put("/api/v1/shots/%s" % shot["id"],
                         headers={"If-Match": shot["etag"]},
                         json=_shot_body("改写", spec=_spec("改写后的文字")))
    assert updated.status_code == 200
    body = updated.json()["data"]
    assert body["title"] == "改写"
    assert body["spec"]["text_zh"] == "改写后的文字"
    assert body["etag"] != shot["etag"]
    assert updated.headers["ETag"] == body["etag"]
    assert body["head_revision_id"] is None
    assert len(_rows(root, "SELECT id FROM prompt_revision")) == 0

    restarted, _ = _client(root)
    again = restarted.get("/api/v1/shots/%s" % shot["id"])
    assert again.status_code == 200
    assert again.json()["data"] == body


def test_pp07_concurrent_cas_one_winner(tmp_path):
    """PP07: two real connections race one token and exactly one commits."""
    root = tmp_path / "data"
    client, _ = _client(root)
    shot = _create_shot(client)
    barrier = threading.Barrier(2)
    outcomes: list[int] = []

    def update(title: str) -> None:
        other, _ = _client(root)
        barrier.wait(10)
        outcomes.append(other.put("/api/v1/shots/%s" % shot["id"],
                                  headers={"If-Match": shot["etag"]},
                                  json=_shot_body(title)).status_code)

    threads = [threading.Thread(target=update, args=("甲",)),
               threading.Thread(target=update, args=("乙",))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert sorted(outcomes) == [200, 412]
    rows = _rows(root, "SELECT title FROM shot WHERE id=?", (shot["id"],))
    assert len(rows) == 1 and rows[0][0] in ("甲", "乙")


def test_pp08_revision_atomic_head(tmp_path):
    """PP08: the revision, the head, the draft and the token move together."""
    root = tmp_path / "data"
    client, _ = _client(root)
    shot = _create_shot(client)
    adopted = _append_revision(client, shot, key="rev-1", parent=None)
    assert adopted.status_code == 201, adopted.text
    revision = adopted.json()["data"]
    assert revision["parent_id"] is None
    assert revision["author"] == "human"
    assert revision["source_run_id"] is None
    assert revision["content_sha256"] == hashlib.sha256(
        json.dumps(revision["spec_snapshot"], sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False, allow_nan=False).encode("utf-8")).hexdigest()

    after = client.get("/api/v1/shots/%s" % shot["id"]).json()["data"]
    assert after["head_revision_id"] == revision["id"]
    assert after["spec"] == revision["spec_snapshot"]
    assert after["etag"] != shot["etag"]

    replay = _append_revision(client, shot, key="rev-1", parent=None)
    assert replay.status_code == 201
    assert replay.json()["data"]["id"] == revision["id"]
    assert client.get("/api/v1/shots/%s" % shot["id"]).json()["data"]["head_revision_id"] \
        == revision["id"]
    assert len(_rows(root, "SELECT id FROM prompt_revision")) == 1

    refused = _append_revision(client, after, key="rev-2", parent=revision["id"],
                               author="model_adopted")
    assert refused.status_code == 422
    assert refused.json()["error"]["code"] == "MODEL_ADOPTION_REQUIRES_BOUND_RUN"
    assert len(_rows(root, "SELECT id FROM prompt_revision")) == 1


def test_pp09_revision_immutable(tmp_path):
    """PP09: a saved revision is immutable through the real SQL."""
    root = tmp_path / "data"
    client, _ = _client(root)
    shot = _create_shot(client)
    revision = _append_revision(client, shot, key="rev-1", parent=None).json()["data"]
    stored = _rows(root, "SELECT spec_json, content_sha256 FROM prompt_revision WHERE id=?",
                   (revision["id"],))[0]

    connection = sqlite3.connect(root / "lvw.sqlite3")
    try:
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
            connection.execute("UPDATE prompt_revision SET author='human' WHERE id=?",
                               (revision["id"],))
        with pytest.raises(sqlite3.IntegrityError, match="IMMUTABLE_REVISION"):
            connection.execute("DELETE FROM prompt_revision WHERE id=?", (revision["id"],))
    finally:
        connection.rollback()
        connection.close()

    after = client.get("/api/v1/shots/%s" % shot["id"]).json()["data"]
    updated = client.put("/api/v1/shots/%s" % shot["id"],
                         headers={"If-Match": after["etag"]},
                         json=_shot_body("改写", spec=_spec("后来的文字")))
    assert updated.status_code == 200
    assert _rows(root, "SELECT spec_json, content_sha256 FROM prompt_revision WHERE id=?",
                 (revision["id"],))[0] == stored
    fetched = client.get("/api/v1/prompts/revisions/%s" % revision["id"]).json()["data"]
    assert fetched["id"] == revision["id"]
    assert fetched["content_sha256"] == revision["content_sha256"]
    assert fetched["spec_snapshot"] == revision["spec_snapshot"]


def test_pp10_revision_pagination_boundaries(tmp_path):
    """PP10: the keyset page is exact, bounded and bound to its shot."""
    root = tmp_path / "data"
    client, _ = _client(root)
    shot = _create_shot(client)
    parent = None
    for index in range(5):
        current = client.get("/api/v1/shots/%s" % shot["id"]).json()["data"]
        response = _append_revision(client, current, key="rev-%d" % index, parent=parent,
                                    spec=_spec("第%d版" % index))
        assert response.status_code == 201, response.text
        parent = response.json()["data"]["id"]

    first = client.get("/api/v1/prompts/revisions",
                        params={"shot_id": shot["id"], "limit": 1})
    assert first.status_code == 200
    page = first.json()["data"]
    assert len(page["items"]) == 1
    assert page["next_cursor"]
    seen = [item["id"] for item in page["items"]]
    cursor = page["next_cursor"]
    while cursor:
        step = client.get("/api/v1/prompts/revisions",
                          params={"shot_id": shot["id"], "limit": 1, "cursor": cursor})
        assert step.status_code == 200
        data = step.json()["data"]
        seen.extend(item["id"] for item in data["items"])
        cursor = data["next_cursor"]
    assert len(seen) == len(set(seen)) == 5
    assert seen[0] == page["items"][0]["id"]

    assert client.get("/api/v1/prompts/revisions",
                      params={"shot_id": shot["id"], "limit": 0}).status_code == 422
    assert client.get("/api/v1/prompts/revisions",
                      params={"shot_id": shot["id"], "limit": 101}).status_code == 422
    assert client.get("/api/v1/prompts/revisions",
                      params={"shot_id": shot["id"], "limit": 100}).status_code == 200
    assert client.get("/api/v1/prompts/revisions",
                      params={"shot_id": shot["id"], "cursor": "not-a-cursor"}).status_code == 422

    other = _create_shot(client, key="other-shot", title="另一个镜头")
    cross = client.get("/api/v1/prompts/revisions",
                        params={"shot_id": other["id"], "cursor": page["next_cursor"]})
    assert cross.status_code == 422

    restarted, _ = _client(root)
    again = restarted.get("/api/v1/prompts/revisions",
                          params={"shot_id": shot["id"], "limit": 100}).json()["data"]
    assert [item["id"] for item in again["items"]] == seen


def test_pp11_head_transaction_rollback(tmp_path):
    """PP11: a real fault between the revision and the head rolls everything back."""
    root = tmp_path / "data"
    faulty = AuthorizerDatabase(root / "lvw.sqlite3", deny="update_shot")
    client, _ = _client(root, database=faulty)
    shot = _create_shot(client)
    before = client.get("/api/v1/shots/%s" % shot["id"]).json()["data"]

    response = _append_revision(client, shot, key="rev-1", parent=None)
    assert response.status_code != 200
    assert response.status_code == 503
    assert len(_rows(root, "SELECT id FROM prompt_revision")) == 0
    assert len(_rows(root, "SELECT scope, key FROM idempotency_record")) == 0
    after = client.get("/api/v1/shots/%s" % shot["id"]).json()["data"]
    assert after == before
    assert after["head_revision_id"] is None


def test_pp12_unicode_locks_and_injection(tmp_path):
    """PP12: the canonical text is preserved and the SQL stays parameterised."""
    root = tmp_path / "data"
    client, _ = _client(root)
    text = "画面中央的钴蓝色方块；DROP TABLE shot;-- ' \" "
    spec = _spec(text, locked=["text_zh", "tags"],
                 evidence=[{"id": "e1", "source_type": "user", "source_ref": "u1",
                            "excerpt": "用户描述", "verification": "user_supplied",
                            "permission_scope": "local"}])
    shot = _create_shot(client, spec=spec)
    assert shot["spec"]["text_zh"] == text
    assert shot["spec"]["locked_fields"] == ["text_zh", "tags"]
    assert shot["spec"]["domains"]["user_evidence"][0]["id"] == "e1"
    stored = _rows(root, "SELECT spec_json FROM shot WHERE id=?", (shot["id"],))[0][0]
    assert "DROP TABLE shot;--" in stored
    assert json.loads(stored)["text_zh"] == text
    assert len(_rows(root, "SELECT id FROM shot")) == 1
    assert "shot" in _tables(root)

    extra = client.post("/api/v1/shots", headers={"Idempotency-Key": "extra"},
                        json=_shot_body(spec=dict(_spec(), unexpected="x")))
    assert extra.status_code == 422
    assert len(_rows(root, "SELECT id FROM shot")) == 1

    missing = _spec()
    missing.pop("schema_version")
    absent = client.post("/api/v1/shots", headers={"Idempotency-Key": "absent"},
                         json=_shot_body(spec=missing))
    assert absent.status_code == 422
    assert len(_rows(root, "SELECT id FROM shot")) == 1

    nonfinite = _spec()
    nonfinite["technical"] = dict(nonfinite["technical"], fps_intent=float("nan"))
    body = json.dumps(_shot_body(spec=nonfinite), ensure_ascii=False).encode("utf-8")
    finite = client.post("/api/v1/shots",
                         headers={"Idempotency-Key": "nan", "Content-Type": "application/json"},
                         content=body)
    assert finite.status_code == 422
    assert len(_rows(root, "SELECT id FROM shot")) == 1


def test_pp13_upload_commit_failure_cleanup(tmp_path):
    """PP13: a failed registration removes only the new uncommitted copy."""
    root = tmp_path / "data"
    database = AuthorizerDatabase(root / "lvw.sqlite3")
    client, _ = _client(root, database=database)
    payload = _jpeg_bytes()
    first = client.post("/api/v1/media", headers={"Idempotency-Key": "media-1"},
                        files={"file": ("shot.jpg", payload, "image/jpeg")})
    assert first.status_code == 201, first.text
    before = sorted(path.name for path in (root / "media").iterdir())
    assert before

    database.deny = "insert_media"
    second = client.post("/api/v1/media", headers={"Idempotency-Key": "media-2"},
                         files={"file": ("other.jpg", _jpeg_bytes(), "image/jpeg")})
    assert second.status_code == 503
    after = sorted(path.name for path in (root / "media").iterdir())
    assert after == before
    assert len(_rows(root, "SELECT id FROM media_ref")) == 1
    assert len(_rows(root, "SELECT scope, key FROM idempotency_record")) == 1

    database.deny = None
    retry = client.post("/api/v1/media", headers={"Idempotency-Key": "media-2"},
                        files={"file": ("other.jpg", _jpeg_bytes(), "image/jpeg")})
    assert retry.status_code == 201
    assert len(_rows(root, "SELECT id FROM media_ref")) == 2


def test_pp14_media_path_and_copy_failure(tmp_path):
    """PP14: a missing, a substituted or a malicious copy fails closed."""
    root = tmp_path / "data"
    client, _ = _client(root)
    payload = _jpeg_bytes()
    response = client.post("/api/v1/media", headers={"Idempotency-Key": "media-1"},
                           files={"file": ("shot.jpg", payload, "image/jpeg")})
    assert response.status_code == 201, response.text
    ref = response.json()["data"]
    stored_name = _rows(root, "SELECT stored_name FROM media_blob")[0][0]
    copy = root / "media" / stored_name
    source_hash = ref["sha256"]

    copy.unlink()
    missing = client.get("/api/v1/media/%s" % ref["id"])
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "MEDIA_INVALID"

    outside = tmp_path / "outside.txt"
    outside.write_text("not a copy", encoding="utf-8")
    copy.symlink_to(outside)
    substituted = client.get("/api/v1/media/%s" % ref["id"])
    assert substituted.status_code == 404

    copy.unlink()
    connection = sqlite3.connect(root / "lvw.sqlite3")
    connection.execute("UPDATE media_blob SET stored_name=? WHERE media_ref_id=?",
                       ("../escape.png", ref["id"]))
    connection.commit()
    connection.close()
    escaped = client.get("/api/v1/media/%s" % ref["id"])
    assert escaped.status_code == 404
    assert not (root / "escape.png").exists()
    assert not (tmp_path / "escape.png").exists()
    assert _rows(root, "SELECT sha256 FROM media_ref WHERE id=?", (ref["id"],))[0][0] \
        == source_hash


def test_pp15_database_busy_unavailable(tmp_path):
    """PP15: a busy and an unavailable database are bounded, stable 503."""
    root = tmp_path / "data"
    client, _ = _client(root)
    _create_shot(client)
    blocker = sqlite3.connect(root / "lvw.sqlite3", timeout=0.1, isolation_level=None)
    blocker.execute("BEGIN IMMEDIATE")
    blocker.execute("INSERT INTO idempotency_record(scope, key, payload_sha256, response_ref) "
                    "VALUES('hold','hold','hold','hold')")
    started = time.monotonic()
    response = client.post("/api/v1/shots", headers={"Idempotency-Key": "busy"},
                           json=_shot_body())
    elapsed = time.monotonic() - started
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_BUSY"
    assert elapsed < 30
    blocker.execute("ROLLBACK")
    blocker.close()

    recovered = client.post("/api/v1/shots", headers={"Idempotency-Key": "after"},
                            json=_shot_body())
    assert recovered.status_code == 201

    broken = tmp_path / "broken"
    (broken / "lvw.sqlite3").mkdir(parents=True)
    client, _ = _client(broken)
    response = client.post("/api/v1/shots", headers={"Idempotency-Key": "broken"},
                           json=_shot_body())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "DATABASE_UNAVAILABLE"


def test_pp16_existing_api_compatibility(tmp_path):
    """PP16: the existing surface is unchanged and the manual path is offline."""
    root = tmp_path / "data"
    provider = CountingProvider()
    runtime = ForbiddenRuntime()
    client, app = _client(root, provider=provider, runtime=runtime)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["data"]["scope"] == "R1-unified"
    capabilities = client.get("/api/v1/capabilities")
    assert capabilities.status_code == 200
    assert capabilities.json()["data"]["stage"] == "R1-unified"

    payload = _jpeg_bytes()
    uploaded = client.post("/api/v1/media", headers={"Idempotency-Key": "media-1"},
                           files={"file": ("shot.jpg", payload, "image/jpeg")})
    assert uploaded.status_code == 201
    assert set(uploaded.json()) == {"data", "request_id", "schema_version"}

    _create_shot(client, key="manual-1")
    assert provider.calls == 0
    assert runtime.calls == 0

    media_id = uploaded.json()["data"]["id"]
    submitted = client.post("/api/v1/jobs/analyze", headers={"Idempotency-Key": "analyse"},
                            json={"media_ref_id": media_id, "shot_id": None, "mode": "realistic",
                                  "config_profile": "local-default"})
    assert submitted.status_code == 202
    assert provider.calls >= 1
    job = client.get("/api/v1/jobs/%s" % submitted.json()["data"]["id"])
    assert job.status_code == 200
    assert job.json()["data"]["status"] == "succeeded"

    paths = set(app.openapi()["paths"])
    assert {"/api/v1/media", "/api/v1/shots", "/api/v1/shots/{id}",
            "/api/v1/prompts/revisions", "/api/v1/prompts/revisions/{id}"} <= paths
    assert "/api/v1/jobs/shot-batches" not in paths
    assert "/api/v1/scenes/{id}" not in paths
