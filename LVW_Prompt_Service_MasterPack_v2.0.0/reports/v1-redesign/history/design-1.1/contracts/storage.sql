-- LVW V1–V3 schema baseline. Execute in clean test DB; production via versioned migrations.
PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;
CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
CREATE TABLE media_ref(id TEXT PRIMARY KEY, sha256 TEXT NOT NULL, kind TEXT NOT NULL CHECK(kind IN('image','video')), metadata_json TEXT NOT NULL, source_root_id TEXT, relative_path TEXT, created_at TEXT NOT NULL);
CREATE INDEX ix_media_hash ON media_ref(sha256);
CREATE TABLE shot(id TEXT PRIMARY KEY, title TEXT NOT NULL, media_ref_id TEXT REFERENCES media_ref(id), spec_json TEXT NOT NULL, etag TEXT NOT NULL, head_revision_id TEXT, updated_at TEXT NOT NULL);
CREATE TABLE prompt_revision(id TEXT PRIMARY KEY, shot_id TEXT NOT NULL REFERENCES shot(id), parent_id TEXT REFERENCES prompt_revision(id), author TEXT NOT NULL, spec_json TEXT NOT NULL, content_sha256 TEXT NOT NULL, created_at TEXT NOT NULL, idempotency_key TEXT UNIQUE NOT NULL);
CREATE TRIGGER revision_no_update BEFORE UPDATE ON prompt_revision BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION'); END;
CREATE TABLE job(id TEXT PRIMARY KEY, kind TEXT NOT NULL, state TEXT NOT NULL, idempotency_key TEXT UNIQUE NOT NULL, payload_hash TEXT NOT NULL, active_attempt_id TEXT, cancel_epoch INTEGER NOT NULL DEFAULT 0, payload_json TEXT NOT NULL, result_ref TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE attempt(id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES job(id), attempt_no INTEGER NOT NULL, token TEXT NOT NULL UNIQUE, cancel_epoch INTEGER NOT NULL, state TEXT NOT NULL, lease_expires_at TEXT, error_code TEXT, started_at TEXT, ended_at TEXT, UNIQUE(job_id,attempt_no));
CREATE TABLE model_run(id TEXT PRIMARY KEY, attempt_id TEXT NOT NULL REFERENCES attempt(id), model_tag TEXT NOT NULL, model_digest TEXT, raw_text TEXT NOT NULL, parsed_json TEXT, config_hash TEXT NOT NULL, input_hash TEXT NOT NULL, created_at TEXT NOT NULL);
-- V2
CREATE TABLE scene_revision(id TEXT PRIMARY KEY, media_ref_id TEXT NOT NULL REFERENCES media_ref(id), version INTEGER NOT NULL, start_pts INTEGER NOT NULL, end_pts INTEGER NOT NULL, origin_pts INTEGER NOT NULL, tb_num INTEGER NOT NULL CHECK(tb_num>0), tb_den INTEGER NOT NULL CHECK(tb_den>0), editor TEXT NOT NULL, CHECK(end_pts>start_pts));
CREATE TABLE asset(id TEXT PRIMARY KEY, kind TEXT NOT NULL, target_id TEXT NOT NULL, title TEXT NOT NULL, tags_json TEXT NOT NULL, provenance_json TEXT NOT NULL, archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN(0,1)));
CREATE TABLE asset_link(id TEXT PRIMARY KEY, from_id TEXT NOT NULL REFERENCES asset(id), to_id TEXT NOT NULL REFERENCES asset(id), relation TEXT NOT NULL, UNIQUE(from_id,to_id,relation));
CREATE TABLE recipe_revision(id TEXT PRIMARY KEY, name TEXT NOT NULL, version TEXT NOT NULL, recipe_json TEXT NOT NULL, content_hash TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(name,version));
CREATE TRIGGER recipe_no_update BEFORE UPDATE ON recipe_revision BEGIN SELECT RAISE(ABORT,'IMMUTABLE_RECIPE'); END;
CREATE VIRTUAL TABLE asset_fts USING fts5(asset_id UNINDEXED, title, description, tags, tokenize='unicode61');
-- Application rebuilds Chinese search tokens deterministically; trigram option requires tested SQLite.
CREATE TABLE batch_child(parent_job_id TEXT REFERENCES job(id), child_job_id TEXT REFERENCES job(id), PRIMARY KEY(parent_job_id,child_job_id));
-- V3
CREATE TABLE evidence_ref(id TEXT PRIMARY KEY, source_system TEXT NOT NULL, external_ref TEXT NOT NULL, source_version TEXT NOT NULL, scope_json TEXT NOT NULL, evidence_json TEXT NOT NULL);
CREATE TABLE external_link(id TEXT PRIMARY KEY, peer TEXT NOT NULL, external_project_id TEXT NOT NULL, external_shot_id TEXT NOT NULL, source_revision TEXT NOT NULL, local_shot_id TEXT NOT NULL REFERENCES shot(id), UNIQUE(peer,external_project_id,external_shot_id,source_revision));
CREATE TABLE outbox(id TEXT PRIMARY KEY, peer TEXT NOT NULL, idempotency_key TEXT NOT NULL UNIQUE, payload_hash TEXT NOT NULL, payload_json TEXT NOT NULL, state TEXT NOT NULL, external_id TEXT, updated_at TEXT NOT NULL);
CREATE TABLE receipt(id TEXT PRIMARY KEY, outbox_id TEXT NOT NULL REFERENCES outbox(id), peer_state TEXT NOT NULL, body_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE workflow_allowlist(id TEXT PRIMARY KEY, workflow_hash TEXT NOT NULL, parameter_schema_json TEXT NOT NULL, node_versions_json TEXT NOT NULL);
