"""The owned SQLite database of the service.

This module owns the connection, the transaction, the version 1 core
bootstrap and the translation of a SQLite failure into the stable
errors of the workpack.  The repositories are the only SQL owners of
the rows.

The rules that this module keeps:

* only a FRESH EMPTY database is bootstrapped, and the bootstrap is ONE
  transaction: a failure rolls the whole bootstrap back;
* a database that is not empty and carries no version, a database of
  another version and a database of a malformed shape are REFUSED before
  any persistent schema or data write: nothing is recreated, dropped or
  implicitly upgraded;
* one connection per operation and every connection is closed, so a
  busy, closed or read only database never leaves an owned handle
  behind;
* a write transaction is BEGIN IMMEDIATE, so a compare and the update
  of a compare-and-set are ONE write transaction and never a precheck
  followed by an unconditional update;
* the busy timeout is bounded to two seconds and the failure of a busy
  database is a stable 503, never a silent success.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .errors import AppError

SCHEMA_VERSION = 1
MAX_BUSY_TIMEOUT_SECONDS = 2.0

# The core statements are the ones of contracts/storage.sql, verbatim:
# the columns, the types and the foreign keys of the core tables are the
# canonical ones and they are not renamed here.
CORE_SCHEMA = (
    "CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);",
    "CREATE TABLE media_ref(id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, kind TEXT NOT NULL "
    "CHECK(kind IN('image','video')), metadata_json TEXT NOT NULL, source_root_id TEXT, "
    "relative_path TEXT, created_at TEXT NOT NULL);",
    "CREATE INDEX ix_media_hash ON media_ref(sha256);",
    "CREATE TABLE shot(id TEXT PRIMARY KEY, title TEXT NOT NULL, media_ref_id TEXT "
    "REFERENCES media_ref(id), spec_json TEXT NOT NULL, etag TEXT NOT NULL, "
    "head_revision_id TEXT, updated_at TEXT NOT NULL);",
    "CREATE TABLE prompt_revision(id TEXT PRIMARY KEY, shot_id TEXT NOT NULL "
    "REFERENCES shot(id), parent_id TEXT REFERENCES prompt_revision(id), author TEXT NOT NULL, "
    "spec_json TEXT NOT NULL, content_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, "
    "idempotency_key TEXT UNIQUE NOT NULL);",
)

# The private tables are not public DTO columns: they carry the owned
# copy of an upload and the durable record of an idempotent operation.
PRIVATE_SCHEMA = (
    "CREATE TABLE media_blob(media_ref_id TEXT PRIMARY KEY REFERENCES media_ref(id), "
    "stored_name TEXT NOT NULL, stored_sha256 TEXT NOT NULL, stored_bytes INTEGER NOT NULL "
    "CHECK(stored_bytes>=0))",
    "CREATE TABLE idempotency_record(scope TEXT NOT NULL, key TEXT NOT NULL, "
    "payload_sha256 TEXT NOT NULL, response_ref TEXT NOT NULL, PRIMARY KEY(scope,key))",
)

# A revision is immutable: the update and the delete are both refused.
REVISION_TRIGGERS = (
    "CREATE TRIGGER prompt_revision_no_update BEFORE UPDATE ON prompt_revision BEGIN "
    "SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END",
    "CREATE TRIGGER prompt_revision_no_delete BEFORE DELETE ON prompt_revision BEGIN "
    "SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END",
)

# The shape that a supported version 1 database must have.  A database
# that does not have it is malformed and it is refused.
REQUIRED_COLUMNS = {
    "schema_version": ("version", "applied_at"),
    "media_ref": ("id", "sha256", "kind", "metadata_json", "source_root_id",
                   "relative_path", "created_at"),
    "shot": ("id", "title", "media_ref_id", "spec_json", "etag",
             "head_revision_id", "updated_at"),
    "prompt_revision": ("id", "shot_id", "parent_id", "author", "spec_json",
                         "content_sha256", "created_at", "idempotency_key"),
    "media_blob": ("media_ref_id", "stored_name", "stored_sha256", "stored_bytes"),
    "idempotency_record": ("scope", "key", "payload_sha256", "response_ref"),
}


def translate(error: sqlite3.Error) -> AppError:
    """Translate a SQLite failure into the stable error of the workpack."""
    detail = str(error)
    lowered = detail.lower()
    if "locked" in lowered or "busy" in lowered:
        return AppError("DATABASE_BUSY", "数据库忙，请稍后重试", status_code=503,
                        retryable=True, details={"detail": detail})
    if "readonly" in lowered:
        return AppError("DATABASE_UNAVAILABLE", "数据库不可用", status_code=503,
                        retryable=True, details={"detail": detail})
    if "no such table" in lowered or "malformed" in lowered:
        return AppError("DATABASE_SCHEMA_INVALID", "数据库结构无效", status_code=503,
                        details={"detail": detail})
    if "not a database" in lowered or "encrypted" in lowered:
        return AppError("DATABASE_UNSUPPORTED_VERSION", "数据库版本不受支持", status_code=503,
                        details={"detail": detail})
    return AppError("DATABASE_UNAVAILABLE", "数据库不可用", status_code=503,
                    retryable=True, details={"detail": detail})


class Database:
    """The owned SQLite database of one service instance."""

    def __init__(self, path: Path | str, *, busy_timeout_seconds: float = MAX_BUSY_TIMEOUT_SECONDS):
        self.path = Path(path)
        self.busy_timeout_seconds = min(max(float(busy_timeout_seconds), 0.0),
                                        MAX_BUSY_TIMEOUT_SECONDS)
        self._bootstrap_lock = threading.Lock()
        self._ready = False

    # -- the connection ---------------------------------------------------
    def connect(self) -> sqlite3.Connection:
        """One owned connection with the pragmas of the workpack."""
        connection = sqlite3.connect(self.path, timeout=self.busy_timeout_seconds,
                                    isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = %d" % int(self.busy_timeout_seconds * 1000))
        return connection

    def _tables(self, connection: sqlite3.Connection) -> set[str]:
        rows = connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        return {str(row[0]) for row in rows}

    # -- the bootstrap ----------------------------------------------------
    def ensure_ready(self) -> None:
        """Make the database usable, or refuse it."""
        if self._ready:
            return
        with self._bootstrap_lock:
            if self._ready:
                return
            self._initialize()
            self._ready = True

    def _initialize(self) -> None:
        nonempty = self.path.exists() and self.path.stat().st_size > 0
        try:
            connection = self.connect()
        except sqlite3.Error as error:
            raise translate(error) from error
        try:
            tables = self._tables(connection)
            if "schema_version" not in tables:
                if tables or nonempty:
                    raise AppError("DATABASE_UNSUPPORTED_VERSION", "数据库版本不受支持",
                                   status_code=503, details={"tables": sorted(tables)})
            else:
                row = connection.execute("SELECT version FROM schema_version").fetchone()
                version = int(row[0]) if row is not None else None
                if version != SCHEMA_VERSION:
                    raise AppError("DATABASE_UNSUPPORTED_VERSION", "数据库版本不受支持",
                                   status_code=503, details={"version": version})
            # The pragmas of a supported database are applied here: an
            # unsupported database never reached this point, so it was
            # never written to.  A database that is already in the WAL
            # mode is left alone: the switch needs the write lock and it
            # must never contend with another owner.
            mode = connection.execute("PRAGMA journal_mode").fetchone()
            if mode is None or str(mode[0]).lower() != "wal":
                connection.execute("PRAGMA journal_mode = WAL")
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.Error as error:
                raise translate(error) from error
            try:
                tables = self._tables(connection)
                if "schema_version" in tables:
                    row = connection.execute("SELECT version FROM schema_version").fetchone()
                    version = int(row[0]) if row is not None else None
                    if version != SCHEMA_VERSION:
                        raise AppError("DATABASE_UNSUPPORTED_VERSION", "数据库版本不受支持",
                                       status_code=503, details={"version": version})
                    self._validate_shape(connection)
                else:
                    self._bootstrap(connection)
                connection.execute("COMMIT")
            except BaseException:
                self._rollback(connection)
                raise
        except sqlite3.Error as error:
            raise translate(error) from error
        finally:
            connection.close()

    def _bootstrap(self, connection: sqlite3.Connection) -> None:
        """Create the version 1 core and the private tables atomically."""
        for statement in CORE_SCHEMA + PRIVATE_SCHEMA + REVISION_TRIGGERS:
            connection.execute(statement)
        connection.execute("INSERT INTO schema_version(version, applied_at) VALUES(?,?)",
                           (SCHEMA_VERSION, datetime.now(timezone.utc).isoformat(timespec="seconds")))

    def _validate_shape(self, connection: sqlite3.Connection) -> None:
        """Refuse a version 1 database whose required shape is missing."""
        tables = self._tables(connection)
        missing = []
        for table, columns in REQUIRED_COLUMNS.items():
            if table not in tables:
                missing.append(table)
                continue
            present = {str(row[1]) for row in connection.execute("PRAGMA table_info(%s)" % table)}
            for column in columns:
                if column not in present:
                    missing.append("%s.%s" % (table, column))
        if missing:
            raise AppError("DATABASE_SCHEMA_INVALID", "数据库结构无效", status_code=503,
                           details={"missing": sorted(missing)})

    @staticmethod
    def _rollback(connection: sqlite3.Connection) -> None:
        try:
            connection.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    # -- the operations ---------------------------------------------------
    @contextmanager
    def read(self):
        """One owned read connection."""
        self.ensure_ready()
        try:
            connection = self.connect()
        except sqlite3.Error as error:
            raise translate(error) from error
        try:
            yield connection
        except sqlite3.Error as error:
            raise translate(error) from error
        finally:
            connection.close()

    @contextmanager
    def write(self):
        """One owned write transaction."""
        self.ensure_ready()
        try:
            connection = self.connect()
        except sqlite3.Error as error:
            raise translate(error) from error
        try:
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.Error as error:
                raise translate(error) from error
            try:
                yield connection
            except sqlite3.Error as error:
                self._rollback(connection)
                raise translate(error) from error
            except BaseException:
                self._rollback(connection)
                raise
            try:
                connection.execute("COMMIT")
            except sqlite3.Error as error:
                self._rollback(connection)
                raise translate(error) from error
        finally:
            connection.close()
