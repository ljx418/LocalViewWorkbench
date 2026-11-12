-- DESIGN CANDIDATE ONLY. Apply to an isolated fixture after contracts/storage.sql.
-- Production migration version: NEXT_VERIFIED_SCHEMA after final V1 audit; never auto-run.
CREATE TABLE source_root(
 id TEXT PRIMARY KEY, canonical_path TEXT NOT NULL UNIQUE, display_name TEXT NOT NULL,
 volume_serial TEXT NOT NULL, root_file_id TEXT NOT NULL, scope_json TEXT NOT NULL,
 permission_epoch INTEGER NOT NULL CHECK(permission_epoch>0),
 state TEXT NOT NULL CHECK(state IN('active','missing','revoked','needs_attention')),
 etag TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE source_file(
 id TEXT PRIMARY KEY, root_id TEXT NOT NULL REFERENCES source_root(id), relative_path TEXT NOT NULL,
 path_key TEXT NOT NULL, volume_serial TEXT NOT NULL, physical_file_id TEXT NOT NULL,
 content_sha256 TEXT, byte_count INTEGER NOT NULL CHECK(byte_count>=0),
 creation_ticks TEXT NOT NULL, write_ticks TEXT NOT NULL, change_ticks TEXT NOT NULL,
 identity_version INTEGER NOT NULL CHECK(identity_version>0),
 availability TEXT NOT NULL CHECK(availability IN('discovered','available','hash_pending','missing','permission_revoked','unsupported','aliased','needs_attention')),
 etag TEXT NOT NULL, UNIQUE(root_id,path_key));
-- Same content on separate paths is NOT unique/merged. Aliased physical IDs are read-only by service policy.
CREATE INDEX ix_source_content ON source_file(content_sha256);
CREATE INDEX ix_source_physical ON source_file(volume_serial,physical_file_id);
CREATE TABLE asset_source_binding(
 id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES asset(id), media_ref_id TEXT REFERENCES media_ref(id),
 source_file_id TEXT NOT NULL REFERENCES source_file(id), binding_version INTEGER NOT NULL CHECK(binding_version>0),
 content_sha256 TEXT NOT NULL, relation TEXT NOT NULL CHECK(relation IN('registered_original','derived_copy')),
 created_at TEXT NOT NULL, UNIQUE(asset_id,source_file_id,binding_version));
CREATE TABLE asset_description_head(asset_id TEXT PRIMARY KEY REFERENCES asset(id), head_revision_id TEXT, etag TEXT NOT NULL);
CREATE TABLE asset_description_revision(
 id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES asset(id), parent_id TEXT REFERENCES asset_description_revision(id),
 model_run_id TEXT REFERENCES model_run(id), facts_json TEXT NOT NULL, unknowns_json TEXT NOT NULL,
 locked_fields_json TEXT NOT NULL, analysis_key TEXT, content_sha256 TEXT NOT NULL, author TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE naming_template_head(id TEXT PRIMARY KEY, head_revision_id TEXT, etag TEXT NOT NULL);
CREATE TABLE naming_template_revision(
 id TEXT PRIMARY KEY, template_id TEXT NOT NULL REFERENCES naming_template_head(id),
 parent_id TEXT REFERENCES naming_template_revision(id), body_json TEXT NOT NULL,
 content_sha256 TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE rename_plan_head(id TEXT PRIMARY KEY, head_revision_id TEXT, etag TEXT NOT NULL);
CREATE TABLE rename_plan_revision(
 id TEXT PRIMARY KEY, plan_id TEXT NOT NULL REFERENCES rename_plan_head(id), revision INTEGER NOT NULL CHECK(revision>0),
 parent_id TEXT REFERENCES rename_plan_revision(id), direction TEXT NOT NULL CHECK(direction IN('forward','undo')),
 undo_of_operation_id TEXT, template_revision_id TEXT NOT NULL REFERENCES naming_template_revision(id),
 plan_hash TEXT NOT NULL, body_json TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(plan_id,revision));
CREATE TABLE rename_plan_item(
 plan_revision_id TEXT NOT NULL REFERENCES rename_plan_revision(id), id TEXT NOT NULL,
 source_file_id TEXT NOT NULL REFERENCES source_file(id), description_revision_id TEXT NOT NULL REFERENCES asset_description_revision(id),
 target_root_id TEXT NOT NULL REFERENCES source_root(id), target_path_key TEXT NOT NULL,
 ordinal INTEGER NOT NULL CHECK(ordinal>0 AND ordinal<=1000), item_json TEXT NOT NULL,
 PRIMARY KEY(plan_revision_id,id), UNIQUE(plan_revision_id,source_file_id),
 UNIQUE(plan_revision_id,ordinal), UNIQUE(plan_revision_id,target_root_id,target_path_key));
CREATE TABLE rename_confirmation(
 token_sha256 TEXT PRIMARY KEY, session_id TEXT NOT NULL, plan_revision_id TEXT NOT NULL REFERENCES rename_plan_revision(id),
 plan_hash TEXT NOT NULL, selection_hash TEXT NOT NULL, root_epochs_json TEXT NOT NULL,
 expires_at TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN('issued','consumed','revoked')));
CREATE TABLE file_operation(
 id TEXT PRIMARY KEY, job_id TEXT NOT NULL REFERENCES job(id), plan_revision_id TEXT NOT NULL REFERENCES rename_plan_revision(id),
 plan_hash TEXT NOT NULL, selection_hash TEXT NOT NULL, session_id TEXT NOT NULL, route TEXT NOT NULL,
 idempotency_key TEXT NOT NULL, payload_sha256 TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN('queued','running','reconciling','succeeded','partial','failed','cancelled','needs_attention')),
 lease_token TEXT, owner_identity_json TEXT, lease_expires_at TEXT, external_journal_tip_sha256 TEXT,
 undo_of_operation_id TEXT REFERENCES file_operation(id), created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 UNIQUE(session_id,route,idempotency_key));
CREATE TABLE file_operation_event(
 operation_id TEXT NOT NULL REFERENCES file_operation(id), seq INTEGER NOT NULL CHECK(seq>0), event_id TEXT NOT NULL UNIQUE,
 item_id TEXT NOT NULL, step_id TEXT NOT NULL, attempt_id TEXT REFERENCES attempt(id), fencing_token TEXT NOT NULL,
 state TEXT NOT NULL CHECK(state IN('intent_durable','staged','moved','committed','conflict','needs_attention','cancelled')),
 evidence_json TEXT NOT NULL, previous_event_sha256 TEXT, event_sha256 TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(operation_id,seq));
CREATE TABLE source_name_history(
 id TEXT PRIMARY KEY, source_file_id TEXT NOT NULL REFERENCES source_file(id), operation_id TEXT NOT NULL REFERENCES file_operation(id),
 old_root_id TEXT NOT NULL REFERENCES source_root(id), old_relative_path TEXT NOT NULL,
 new_root_id TEXT NOT NULL REFERENCES source_root(id), new_relative_path TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX ix_history_source ON source_name_history(source_file_id);
-- Application atomically indexes current location + old names; original FTS table/schema remains unchanged.
CREATE VIRTUAL TABLE library_name_fts USING fts5(source_file_id UNINDEXED, current_name, old_names, description, tags, tokenize='unicode61');
CREATE TRIGGER description_no_update BEFORE UPDATE ON asset_description_revision BEGIN SELECT RAISE(ABORT,'IMMUTABLE_DESCRIPTION'); END;
CREATE TRIGGER description_no_delete BEFORE DELETE ON asset_description_revision BEGIN SELECT RAISE(ABORT,'IMMUTABLE_DESCRIPTION'); END;
CREATE TRIGGER naming_template_no_update BEFORE UPDATE ON naming_template_revision BEGIN SELECT RAISE(ABORT,'IMMUTABLE_NAMING_TEMPLATE'); END;
CREATE TRIGGER naming_template_no_delete BEFORE DELETE ON naming_template_revision BEGIN SELECT RAISE(ABORT,'IMMUTABLE_NAMING_TEMPLATE'); END;
CREATE TRIGGER rename_plan_no_update BEFORE UPDATE ON rename_plan_revision BEGIN SELECT RAISE(ABORT,'IMMUTABLE_RENAME_PLAN'); END;
CREATE TRIGGER rename_plan_no_delete BEFORE DELETE ON rename_plan_revision BEGIN SELECT RAISE(ABORT,'IMMUTABLE_RENAME_PLAN'); END;
CREATE TRIGGER rename_item_no_update BEFORE UPDATE ON rename_plan_item BEGIN SELECT RAISE(ABORT,'IMMUTABLE_PLAN_ITEM'); END;
CREATE TRIGGER rename_item_no_delete BEFORE DELETE ON rename_plan_item BEGIN SELECT RAISE(ABORT,'IMMUTABLE_PLAN_ITEM'); END;
CREATE TRIGGER file_event_no_update BEFORE UPDATE ON file_operation_event BEGIN SELECT RAISE(ABORT,'IMMUTABLE_FILE_EVENT'); END;
CREATE TRIGGER file_event_no_delete BEFORE DELETE ON file_operation_event BEGIN SELECT RAISE(ABORT,'IMMUTABLE_FILE_EVENT'); END;
CREATE TRIGGER source_history_no_update BEFORE UPDATE ON source_name_history BEGIN SELECT RAISE(ABORT,'IMMUTABLE_NAME_HISTORY'); END;
CREATE TRIGGER source_history_no_delete BEFORE DELETE ON source_name_history BEGIN SELECT RAISE(ABORT,'IMMUTABLE_NAME_HISTORY'); END;
-- Parent/asset/template head consistency, semantic states, root/file custody and hashes enforced by shared service.
-- Do not infer Windows I/O, transactional external rename, recovery or production migration from this DDL.
