"""The canonical manual shot and revision lifecycle.

This module owns the compare-and-set semantics of the working draft and
of the head of a shot and it owns the reusable, API facing service
logic of the manual path.  The rows belong to the repositories, the
connection belongs to the storage module and the content hash belongs to
the revisions module.

The rules that this module keeps:

* the compare and the update of a compare-and-set are ONE write
  transaction: there is no precheck followed by an unconditional update;
* an append of a revision is ONE transaction: it inserts the immutable
  snapshot, moves the head, adopts the snapshot as the draft, changes
  the edit token and records the idempotency;
* an idempotent replay of the same operation, key and payload returns
  the ORIGINAL resource without a duplicate revision and without a
  movement of the edit token, even when the precondition of the first
  call is old by now;
* an analysis never writes a shot and never writes a revision: only
  the explicit manual path writes them;
* the model adopted author is refused: the adoption owner of the bound
  run does not exist in this slice and no provenance is ever forged.
"""
from __future__ import annotations

import base64
import binascii
import json
import uuid
from datetime import datetime, timezone

from .errors import AppError
from .models import Revision, RevisionCreate, Shot, ShotCreate
from .revisions import canonical_json, canonical_sha256, shot_etag, shot_state_sha256, \
    spec_content_sha256

SHOT_SCOPE = "shot.create"
REVISION_SCOPE = "revision.create"
DEFAULT_LIMIT = 30
MAX_LIMIT = 100
MANUAL_AUTHORS = ("human", "imported")

# The required canonical keys of a specification and of the nested
# evidence of a specification.  A field that an old model fills with a
# default is NOT a field that the request carried.
REQUIRED_SPEC_KEYS = ("schema_version", "mode", "domains", "technical", "locked_fields",
                      "text_zh", "text_en", "tags", "negative", "template_id",
                      "template_version")
REQUIRED_EVIDENCE_KEYS = ("id", "source_type", "source_ref", "excerpt", "verification",
                          "permission_scope")
EVIDENCE_SOURCE_TYPES = ("user", "navia", "media", "reference")
EVIDENCE_VERIFICATIONS = ("unverified", "user_supplied")


def _now() -> str:
    """The current instant of the service, in the canonical form."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _validate_spec(spec) -> None:
    """Refuse a specification that does not carry the canonical keys.

    Every required canonical key of the specification and of the nested
    evidence must be present in the request.  A key that the model
    filled with an old default is not a key that the request carried and
    it is never accepted as one.
    """
    missing = [key for key in REQUIRED_SPEC_KEYS if key not in spec.model_fields_set]
    if missing:
        raise AppError("VALIDATION_FAILED", "提示词规格缺少必填字段", status_code=422,
                       details={"missing": missing})
    for item in spec.domains.user_evidence:
        if not isinstance(item, dict):
            raise AppError("VALIDATION_FAILED", "证据项必须是对象", status_code=422)
        missing = [key for key in REQUIRED_EVIDENCE_KEYS if key not in item]
        extra = [key for key in item if key not in REQUIRED_EVIDENCE_KEYS]
        if missing or extra:
            raise AppError("VALIDATION_FAILED", "证据项的字段不符合规范", status_code=422,
                           details={"missing": sorted(missing), "extra": sorted(extra)})
        if item["source_type"] not in EVIDENCE_SOURCE_TYPES:
            raise AppError("VALIDATION_FAILED", "证据来源类型无效", status_code=422,
                           details={"source_type": item["source_type"]})
        if item["verification"] not in EVIDENCE_VERIFICATIONS:
            raise AppError("VALIDATION_FAILED", "证据核验状态无效", status_code=422,
                           details={"verification": item["verification"]})
        for key in ("id", "source_ref", "excerpt", "permission_scope"):
            if not isinstance(item[key], str):
                raise AppError("VALIDATION_FAILED", "证据字段必须是字符串", status_code=422,
                               details={"field": key})


def _canonical_spec(spec) -> tuple[str, str]:
    """The canonical JSON and the content hash of a specification.

    A specification that carries a value that the canonical JSON
    refuses, a non finite number for instance, is a validation failure
    of the request and never a silent approximation of the content.
    """
    _validate_spec(spec)
    try:
        spec_json = canonical_json(spec.model_dump(mode="json"))
        content_sha256 = spec_content_sha256(spec)
    except (ValueError, TypeError) as error:
        raise AppError("VALIDATION_FAILED", "提示词规格无法被规范化", status_code=422,
                       details={"reason": "non_finite_or_unserialisable"}) from error
    return spec_json, content_sha256


class ShotService:
    """The manual shot, the working draft and the immutable revisions."""

    def __init__(self, database, repository):
        self.database = database
        self.repository = repository

    # -- the shots --------------------------------------------------------
    def create_shot(self, payload: ShotCreate, *, idempotency_key: str) -> Shot:
        """Create one manual shot; it creates no revision and no head."""
        spec_json, spec_sha256 = _canonical_spec(payload.spec)
        payload_sha256 = canonical_sha256({"title": payload.title,
                                            "media_ref_id": payload.media_ref_id,
                                            "spec": json.loads(spec_json)})
        with self.database.write() as connection:
            existing = self.repository.find_idempotency(connection, SHOT_SCOPE, idempotency_key)
            if existing is not None:
                if existing["payload_sha256"] != payload_sha256:
                    raise AppError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他请求", status_code=409)
                return self._shot(connection, existing["response_ref"])
            if payload.media_ref_id is not None and not self.repository.media_exists(
                    connection, payload.media_ref_id):
                raise AppError("MEDIA_INVALID", "引用的媒体不存在", status_code=422)
            shot_id = "shot_" + uuid.uuid4().hex
            etag = shot_etag(shot_state_sha256(
                title=payload.title, media_ref_id=payload.media_ref_id,
                spec_sha256=spec_sha256, head_revision_id=None))
            self.repository.insert_shot(connection, shot_id, payload.title, payload.media_ref_id,
                                        spec_json, etag, _now())
            self.repository.record_idempotency(connection, SHOT_SCOPE, idempotency_key,
                                               payload_sha256, shot_id)
            return self._shot(connection, shot_id)

    def get_shot(self, shot_id: str) -> Shot:
        """One shot and its current edit token."""
        with self.database.read() as connection:
            return self._shot(connection, shot_id)

    def update_shot(self, shot_id: str, payload: ShotCreate, *,
                    if_match: str | None) -> Shot:
        """Update the working draft; the head and the history are untouched."""
        if not if_match:
            raise AppError("PRECONDITION_REQUIRED", "缺少 If-Match", status_code=428)
        spec_json, spec_sha256 = _canonical_spec(payload.spec)
        with self.database.write() as connection:
            row = self.repository.get_shot(connection, shot_id)
            if row is None:
                raise AppError("SHOT_NOT_FOUND", "找不到镜头", status_code=404)
            if row["etag"] != if_match:
                raise AppError("ETAG_MISMATCH", "编辑令牌已过期", status_code=412)
            if payload.media_ref_id is not None and not self.repository.media_exists(
                    connection, payload.media_ref_id):
                raise AppError("MEDIA_INVALID", "引用的媒体不存在", status_code=422)
            etag = shot_etag(shot_state_sha256(
                title=payload.title, media_ref_id=payload.media_ref_id,
                spec_sha256=spec_sha256, head_revision_id=row["head_revision_id"]))
            self.repository.update_shot_draft(connection, shot_id, payload.title,
                                               payload.media_ref_id, spec_json, etag, _now())
            return self._shot(connection, shot_id)

    # -- the revisions ----------------------------------------------------
    def append_revision(self, payload: RevisionCreate, *, idempotency_key: str,
                        if_match: str | None) -> Revision:
        """Append one immutable revision and adopt it as the head."""
        if not if_match:
            raise AppError("PRECONDITION_REQUIRED", "缺少 If-Match", status_code=428)
        if payload.author not in MANUAL_AUTHORS:
            raise AppError("MODEL_ADOPTION_REQUIRES_BOUND_RUN",
                           "模型采纳需要绑定的运行", status_code=422)
        spec_json, content_sha256 = _canonical_spec(payload.spec_snapshot)
        payload_sha256 = canonical_sha256({"shot_id": payload.shot_id,
                                            "parent_id": payload.parent_id,
                                            "author": payload.author,
                                            "spec_snapshot": json.loads(spec_json)})
        with self.database.write() as connection:
            existing = self.repository.find_idempotency(connection, REVISION_SCOPE, idempotency_key)
            if existing is not None:
                if existing["payload_sha256"] != payload_sha256:
                    raise AppError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他请求", status_code=409)
                return self._revision(connection, existing["response_ref"])
            row = self.repository.get_shot(connection, payload.shot_id)
            if row is None:
                raise AppError("SHOT_NOT_FOUND", "找不到镜头", status_code=404)
            if row["etag"] != if_match:
                raise AppError("ETAG_MISMATCH", "编辑令牌已过期", status_code=412)
            if (row["head_revision_id"] or None) != (payload.parent_id or None):
                raise AppError("REVISION_PARENT_MISMATCH", "父修订与当前头不一致", status_code=409)
            revision_id = "rev_" + uuid.uuid4().hex
            self.repository.insert_revision(connection, revision_id, payload.shot_id,
                                           payload.parent_id, payload.author, spec_json,
                                           content_sha256, _now(), idempotency_key)
            etag = shot_etag(shot_state_sha256(
                title=row["title"], media_ref_id=row["media_ref_id"],
                spec_sha256=content_sha256, head_revision_id=revision_id))
            self.repository.set_shot_head(connection, payload.shot_id, revision_id,
                                          spec_json, etag, _now())
            self.repository.record_idempotency(connection, REVISION_SCOPE, idempotency_key,
                                               payload_sha256, revision_id)
            return self._revision(connection, revision_id)

    def get_revision(self, revision_id: str) -> Revision:
        """One immutable revision."""
        with self.database.read() as connection:
            row = self.repository.get_revision(connection, revision_id)
            if row is None:
                raise AppError("REVISION_NOT_FOUND", "找不到修订", status_code=404)
            return self._revision_value(row)

    def list_revisions(self, shot_id: str, *, limit: int | None,
                       cursor: str | None) -> dict:
        """One page of the revisions of a shot in the deterministic order."""
        if limit is None:
            limit = DEFAULT_LIMIT
        elif isinstance(limit, bool) or not isinstance(limit, int) or limit < 1 or limit > MAX_LIMIT:
            raise AppError("VALIDATION_FAILED", "limit 必须是 1 到 100 的整数", status_code=422,
                           details={"limit": limit})
        after = None if cursor is None else self._decode_cursor(cursor, shot_id)
        with self.database.read() as connection:
            rows = self.repository.list_revisions(connection, shot_id, limit + 1, after)
        page = rows[:limit]
        next_cursor = None
        if len(rows) > limit and page:
            last = page[-1]
            next_cursor = self._encode_cursor(shot_id, last["created_at"], last["id"])
        return {"items": [self._revision_value(row) for row in page],
                "next_cursor": next_cursor}

    # -- the values -------------------------------------------------------
    def _shot(self, connection, shot_id: str) -> Shot:
        row = self.repository.get_shot(connection, shot_id)
        if row is None:
            raise AppError("SHOT_NOT_FOUND", "找不到镜头", status_code=404)
        return self._shot_value(row)

    @staticmethod
    def _shot_value(row) -> Shot:
        return Shot(id=row["id"], title=row["title"], media_ref_id=row["media_ref_id"],
                    spec=json.loads(row["spec_json"]), etag=row["etag"],
                    head_revision_id=row["head_revision_id"])

    @staticmethod
    def _revision_value(row) -> Revision:
        return Revision(id=row["id"], shot_id=row["shot_id"], parent_id=row["parent_id"],
                        author=row["author"], spec_snapshot=json.loads(row["spec_json"]),
                        content_sha256=row["content_sha256"],
                        created_at=datetime.fromisoformat(row["created_at"]),
                        source_run_id=None)

    # -- the opaque cursor ------------------------------------------------
    @staticmethod
    def _encode_cursor(shot_id: str, created_at: str, revision_id: str) -> str:
        raw = canonical_json({"shot_id": shot_id, "created_at": created_at,
                               "id": revision_id}).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str, shot_id: str) -> tuple[str, str]:
        padded = cursor + "=" * (-len(cursor) % 4)
        try:
            raw = base64.urlsafe_b64decode(padded.encode("ascii"))
            value = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeError, binascii.Error) as error:
            raise AppError("VALIDATION_FAILED", "分页游标无效", status_code=422,
                           details={"reason": "malformed"}) from error
        if (not isinstance(value, dict) or value.get("shot_id") != shot_id
                or not isinstance(value.get("created_at"), str)
                or not isinstance(value.get("id"), str)):
            raise AppError("VALIDATION_FAILED", "分页游标无效", status_code=422,
                           details={"reason": "bound_to_another_shot"})
        return value["created_at"], value["id"]
