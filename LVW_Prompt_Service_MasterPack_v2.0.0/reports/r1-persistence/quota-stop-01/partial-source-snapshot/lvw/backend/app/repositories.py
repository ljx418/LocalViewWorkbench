"""The sole SQL owner of the rows of the persistence workpack.

Every statement of this module is parameterised and every statement of
this module names its table explicitly.  The callers own the
transaction: this module never opens, commits or rolls back a
transaction of its own, so the compare and the update of a
compare-and-set stay ONE write transaction.

The module owns no rule of the product: the content hash of a
specification belongs to the revisions module, the compare-and-set
semantics of a shot belong to the shots module and the connection
belongs to the storage module.
"""
from __future__ import annotations

import sqlite3


class Repository:
    """The rows of the media, the shots, the revisions and the idempotency."""

    def __init__(self, database):
        self.database = database

    # -- the durable idempotency ----------------------------------------
    def find_idempotency(self, connection: sqlite3.Connection, scope: str,
                         key: str) -> sqlite3.Row | None:
        """The record of one idempotent operation, or None."""
        return connection.execute(
            "SELECT payload_sha256, response_ref FROM idempotency_record "
            "WHERE scope=? AND key=?", (scope, key)).fetchone()

    def record_idempotency(self, connection: sqlite3.Connection, scope: str, key: str,
                            payload_sha256: str, response_ref: str) -> None:
        """Record one idempotent operation inside the caller's transaction."""
        connection.execute(
            "INSERT INTO idempotency_record(scope, key, payload_sha256, response_ref) "
            "VALUES(?,?,?,?)", (scope, key, payload_sha256, response_ref))

    # -- the media --------------------------------------------------------
    def insert_media(self, connection: sqlite3.Connection, media_id: str, sha256: str, kind: str,
                     metadata_json: str, created_at: str) -> None:
        connection.execute(
            "INSERT INTO media_ref(id, sha256, kind, metadata_json, source_root_id, "
            "relative_path, created_at) VALUES(?,?,?,?,?,?,?)",
            (media_id, sha256, kind, metadata_json, None, None, created_at))

    def insert_media_blob(self, connection: sqlite3.Connection, media_id: str, stored_name: str,
                          stored_sha256: str, stored_bytes: int) -> None:
        connection.execute(
            "INSERT INTO media_blob(media_ref_id, stored_name, stored_sha256, stored_bytes) "
            "VALUES(?,?,?,?)", (media_id, stored_name, stored_sha256, stored_bytes))

    def get_media(self, connection: sqlite3.Connection, media_id: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT id, sha256, kind, metadata_json, source_root_id, relative_path, created_at "
            "FROM media_ref WHERE id=?", (media_id,)).fetchone()

    def get_media_blob(self, connection: sqlite3.Connection, media_id: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT media_ref_id, stored_name, stored_sha256, stored_bytes FROM media_blob "
            "WHERE media_ref_id=?", (media_id,)).fetchone()

    # -- the shots --------------------------------------------------------
    def insert_shot(self, connection: sqlite3.Connection, shot_id: str, title: str,
                    media_ref_id: str | None, spec_json: str, etag: str,
                    updated_at: str) -> None:
        connection.execute(
            "INSERT INTO shot(id, title, media_ref_id, spec_json, etag, head_revision_id, updated_at) "
            "VALUES(?,?,?,?,?,?,?)", (shot_id, title, media_ref_id, spec_json, etag, None, updated_at))

    def get_shot(self, connection: sqlite3.Connection, shot_id: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT id, title, media_ref_id, spec_json, etag, head_revision_id, updated_at "
            "FROM shot WHERE id=?", (shot_id,)).fetchone()

    def media_exists(self, connection: sqlite3.Connection, media_id: str) -> bool:
        row = connection.execute("SELECT 1 FROM media_ref WHERE id=?", (media_id,)).fetchone()
        return row is not None

    def update_shot_draft(self, connection: sqlite3.Connection, shot_id: str, title: str,
                           media_ref_id: str | None, spec_json: str, etag: str,
                           updated_at: str) -> int:
        """Update the working draft of a shot without touching its head."""
        cursor = connection.execute(
            "UPDATE shot SET title=?, media_ref_id=?, spec_json=?, etag=?, updated_at=? "
            "WHERE id=?", (title, media_ref_id, spec_json, etag, updated_at, shot_id))
        return cursor.rowcount

    def set_shot_head(self, connection: sqlite3.Connection, shot_id: str,
                      head_revision_id: str, spec_json: str, etag: str,
                      updated_at: str) -> int:
        """Move the head of a shot to a saved revision and adopt its snapshot."""
        cursor = connection.execute(
            "UPDATE shot SET head_revision_id=?, spec_json=?, etag=?, updated_at=? WHERE id=?",
            (head_revision_id, spec_json, etag, updated_at, shot_id))
        return cursor.rowcount

    # -- the revisions ----------------------------------------------------
    def insert_revision(self, connection: sqlite3.Connection, revision_id: str, shot_id: str,
                        parent_id: str | None, author: str, spec_json: str,
                        content_sha256: str, created_at: str, idempotency_key: str) -> None:
        connection.execute(
            "INSERT INTO prompt_revision(id, shot_id, parent_id, author, spec_json, content_sha256, "
            "created_at, idempotency_key) VALUES(?,?,?,?,?,?,?,?)",
            (revision_id, shot_id, parent_id, author, spec_json, content_sha256, created_at,
             idempotency_key))

    def get_revision(self, connection: sqlite3.Connection, revision_id: str) -> sqlite3.Row | None:
        return connection.execute(
            "SELECT id, shot_id, parent_id, author, spec_json, content_sha256, created_at "
            "FROM prompt_revision WHERE id=?", (revision_id,)).fetchone()

    def list_revisions(self, connection: sqlite3.Connection, shot_id: str, limit: int,
                       after: tuple[str, str] | None) -> list[sqlite3.Row]:
        """One page of the revisions of a shot in the deterministic keyset order."""
        if after is None:
            return connection.execute(
                "SELECT id, shot_id, parent_id, author, spec_json, content_sha256, created_at "
                "FROM prompt_revision WHERE shot_id=? ORDER BY created_at, id LIMIT ?",
                (shot_id, limit)).fetchall()
        created_at, revision_id = after
        return connection.execute(
            "SELECT id, shot_id, parent_id, author, spec_json, content_sha256, created_at "
            "FROM prompt_revision WHERE shot_id=? AND (created_at > ? OR (created_at = ? AND id > ?)) "
            "ORDER BY created_at, id LIMIT ?",
            (shot_id, created_at, created_at, revision_id, limit)).fetchall()
