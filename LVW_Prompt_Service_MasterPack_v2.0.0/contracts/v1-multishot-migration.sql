-- DESIGN CANDIDATE 1.1 ONLY. R1 migrator must validate schema_version=1,
-- backup first and register deterministic lvw_scene_hash(11args) before this transaction.
-- No production DB was opened/applied during D0. On any failure ROLLBACK.
PRAGMA foreign_keys=ON;
BEGIN IMMEDIATE;
CREATE TABLE IF NOT EXISTS scene_revision(id TEXT PRIMARY KEY, media_ref_id TEXT NOT NULL REFERENCES media_ref(id), version INTEGER NOT NULL, start_pts INTEGER NOT NULL, end_pts INTEGER NOT NULL, origin_pts INTEGER NOT NULL, tb_num INTEGER NOT NULL CHECK(tb_num>0), tb_den INTEGER NOT NULL CHECK(tb_den>0), editor TEXT NOT NULL, CHECK(end_pts>start_pts));
CREATE TABLE scene_head(scene_id TEXT PRIMARY KEY, head_revision_id TEXT NOT NULL REFERENCES scene_revision(id) DEFERRABLE INITIALLY DEFERRED, etag TEXT NOT NULL);
CREATE TABLE scene_revision_meta(scene_revision_id TEXT PRIMARY KEY REFERENCES scene_revision(id), scene_id TEXT NOT NULL REFERENCES scene_head(scene_id) DEFERRABLE INITIALLY DEFERRED, revision INTEGER NOT NULL CHECK(revision>=1), source_sha256 TEXT NOT NULL CHECK(length(source_sha256)=64 AND source_sha256 NOT GLOB '*[^0-9a-f]*'), time_basis TEXT NOT NULL CHECK(time_basis IN('decoded_pts','estimated','unverified')), verified INTEGER NOT NULL CHECK(verified IN(0,1)), content_sha256 TEXT NOT NULL CHECK(length(content_sha256)=64), etag TEXT NOT NULL, UNIQUE(scene_id,revision), CHECK((verified=1 AND time_basis='decoded_pts') OR (verified=0 AND time_basis!='decoded_pts')));
-- Old rows become separate logical scene IDs, preserving original IDs/values.
-- No grouping/verified timestamp is invented from adjacent positions or versions.
INSERT INTO scene_head SELECT s.id,s.id,'"scene:'||s.id||':'||lvw_scene_hash(s.media_ref_id,m.sha256,s.version,s.start_pts,s.end_pts,s.origin_pts,s.tb_num,s.tb_den,s.editor,'unverified',0)||'"' FROM scene_revision s JOIN media_ref m ON s.media_ref_id=m.id;
INSERT INTO scene_revision_meta SELECT s.id,s.id,s.version,m.sha256,'unverified',0,lvw_scene_hash(s.media_ref_id,m.sha256,s.version,s.start_pts,s.end_pts,s.origin_pts,s.tb_num,s.tb_den,s.editor,'unverified',0),h.etag FROM scene_revision s JOIN media_ref m ON m.id=s.media_ref_id JOIN scene_head h ON h.scene_id=s.id;
CREATE TRIGGER scene_revision_no_update BEFORE UPDATE ON scene_revision BEGIN SELECT RAISE(ABORT,'IMMUTABLE_SCENE_REVISION'); END;
CREATE TRIGGER scene_revision_no_delete BEFORE DELETE ON scene_revision BEGIN SELECT RAISE(ABORT,'IMMUTABLE_SCENE_REVISION'); END;
CREATE TRIGGER scene_meta_no_update BEFORE UPDATE ON scene_revision_meta BEGIN SELECT RAISE(ABORT,'IMMUTABLE_SCENE_META'); END;
CREATE TRIGGER scene_meta_no_delete BEFORE DELETE ON scene_revision_meta BEGIN SELECT RAISE(ABORT,'IMMUTABLE_SCENE_META'); END;
CREATE TRIGGER scene_meta_matches_base BEFORE INSERT ON scene_revision_meta BEGIN SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM scene_revision s JOIN media_ref m ON m.id=s.media_ref_id WHERE s.id=NEW.scene_revision_id AND s.version=NEW.revision AND m.sha256=NEW.source_sha256) THEN RAISE(ABORT,'SCENE_BINDING_MISMATCH') END; END;
CREATE TABLE shot_scene_binding(shot_id TEXT PRIMARY KEY REFERENCES shot(id), scene_revision_id TEXT NOT NULL REFERENCES scene_revision(id), scene_revision_hash TEXT NOT NULL CHECK(length(scene_revision_hash)=64));
CREATE TABLE IF NOT EXISTS model_run_artifacts(model_run_id TEXT PRIMARY KEY REFERENCES model_run(id), frames_json TEXT NOT NULL CHECK(json_valid(frames_json)));
CREATE TABLE shot_analysis_binding(model_run_id TEXT PRIMARY KEY REFERENCES model_run(id), shot_id TEXT NOT NULL REFERENCES shot(id), scene_revision_id TEXT NOT NULL REFERENCES scene_revision(id), scene_revision_hash TEXT NOT NULL CHECK(length(scene_revision_hash)=64), media_sha256 TEXT NOT NULL CHECK(length(media_sha256)=64), config_hash TEXT NOT NULL CHECK(length(config_hash)=64), attempt_id TEXT NOT NULL REFERENCES attempt(id), lease_token TEXT NOT NULL, cancel_epoch INTEGER NOT NULL CHECK(cancel_epoch>=0));
CREATE TABLE shot_analysis_evidence(model_run_id TEXT PRIMARY KEY REFERENCES model_run(id), raw_schema_version TEXT NOT NULL, evidence_json TEXT NOT NULL CHECK(json_valid(evidence_json)), evidence_sha256 TEXT NOT NULL CHECK(length(evidence_sha256)=64));
CREATE TABLE revision_source_binding(revision_id TEXT PRIMARY KEY REFERENCES prompt_revision(id), model_run_id TEXT NOT NULL REFERENCES model_run(id), scene_revision_id TEXT NOT NULL REFERENCES scene_revision(id), scene_revision_hash TEXT NOT NULL CHECK(length(scene_revision_hash)=64));
CREATE TABLE shot_batch_parent(parent_job_id TEXT PRIMARY KEY REFERENCES job(id), plan_hash TEXT NOT NULL CHECK(length(plan_hash)=64), planned_count INTEGER NOT NULL CHECK(planned_count BETWEEN 1 AND 12), created_at TEXT NOT NULL, deadline_at TEXT NOT NULL, execution_budget_seconds INTEGER NOT NULL, retry_of_parent_id TEXT REFERENCES shot_batch_parent(parent_job_id), CHECK(execution_budget_seconds=450*planned_count+90));
CREATE TABLE shot_batch_item(parent_job_id TEXT NOT NULL REFERENCES shot_batch_parent(parent_job_id), ordinal INTEGER NOT NULL CHECK(ordinal BETWEEN 0 AND 11), child_job_id TEXT NOT NULL UNIQUE REFERENCES job(id), shot_id TEXT NOT NULL REFERENCES shot(id), scene_revision_id TEXT NOT NULL REFERENCES scene_revision(id), scene_revision_hash TEXT NOT NULL CHECK(length(scene_revision_hash)=64), media_sha256 TEXT NOT NULL CHECK(length(media_sha256)=64), config_hash TEXT NOT NULL CHECK(length(config_hash)=64), retry_of_child_id TEXT REFERENCES job(id), PRIMARY KEY(parent_job_id,ordinal), UNIQUE(parent_job_id,shot_id));
CREATE TABLE shot_batch_seal(parent_job_id TEXT PRIMARY KEY REFERENCES shot_batch_parent(parent_job_id), plan_hash TEXT NOT NULL, sealed_at TEXT NOT NULL);
CREATE TRIGGER shot_batch_seal_complete BEFORE INSERT ON shot_batch_seal BEGIN SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM shot_batch_parent p WHERE p.parent_job_id=NEW.parent_job_id AND p.plan_hash=NEW.plan_hash AND (SELECT count(*) FROM shot_batch_item i WHERE i.parent_job_id=p.parent_job_id)=p.planned_count AND (SELECT min(ordinal) FROM shot_batch_item i WHERE i.parent_job_id=p.parent_job_id)=0 AND (SELECT max(ordinal) FROM shot_batch_item i WHERE i.parent_job_id=p.parent_job_id)=p.planned_count-1) THEN RAISE(ABORT,'INCOMPLETE_BATCH_PLAN') END; END;
CREATE TRIGGER shot_batch_item_no_append_after_seal BEFORE INSERT ON shot_batch_item WHEN EXISTS(SELECT 1 FROM shot_batch_seal WHERE parent_job_id=NEW.parent_job_id) BEGIN SELECT RAISE(ABORT,'IMMUTABLE_BATCH_PLAN'); END;
CREATE TABLE attempt_execution(attempt_id TEXT PRIMARY KEY REFERENCES attempt(id), model_action_at TEXT, provider_call_id TEXT);
-- Immutable artifact tables; only job/attempt status, scene_head and current
-- shot_scene_binding remain mutable under their owning CAS transactions.
CREATE TRIGGER shot_analysis_binding_no_update BEFORE UPDATE ON shot_analysis_binding BEGIN SELECT RAISE(ABORT,'IMMUTABLE_ANALYSIS_BINDING'); END;
CREATE TRIGGER shot_analysis_binding_no_delete BEFORE DELETE ON shot_analysis_binding BEGIN SELECT RAISE(ABORT,'IMMUTABLE_ANALYSIS_BINDING'); END;
CREATE TRIGGER shot_analysis_evidence_no_update BEFORE UPDATE ON shot_analysis_evidence BEGIN SELECT RAISE(ABORT,'IMMUTABLE_ANALYSIS_EVIDENCE'); END;
CREATE TRIGGER shot_analysis_evidence_no_delete BEFORE DELETE ON shot_analysis_evidence BEGIN SELECT RAISE(ABORT,'IMMUTABLE_ANALYSIS_EVIDENCE'); END;
CREATE TRIGGER IF NOT EXISTS model_run_artifacts_no_update BEFORE UPDATE ON model_run_artifacts BEGIN SELECT RAISE(ABORT,'IMMUTABLE_FRAME_ARTIFACT'); END;
CREATE TRIGGER IF NOT EXISTS model_run_artifacts_no_delete BEFORE DELETE ON model_run_artifacts BEGIN SELECT RAISE(ABORT,'IMMUTABLE_FRAME_ARTIFACT'); END;
CREATE TRIGGER revision_source_binding_no_update BEFORE UPDATE ON revision_source_binding BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION_SOURCE'); END;
CREATE TRIGGER revision_source_binding_no_delete BEFORE DELETE ON revision_source_binding BEGIN SELECT RAISE(ABORT,'IMMUTABLE_REVISION_SOURCE'); END;
CREATE TRIGGER shot_batch_parent_no_update BEFORE UPDATE ON shot_batch_parent BEGIN SELECT RAISE(ABORT,'IMMUTABLE_BATCH_PLAN'); END;
CREATE TRIGGER shot_batch_parent_no_delete BEFORE DELETE ON shot_batch_parent BEGIN SELECT RAISE(ABORT,'IMMUTABLE_BATCH_PLAN'); END;
CREATE TRIGGER shot_batch_item_no_update BEFORE UPDATE ON shot_batch_item BEGIN SELECT RAISE(ABORT,'IMMUTABLE_BATCH_PLAN'); END;
CREATE TRIGGER shot_batch_item_no_delete BEFORE DELETE ON shot_batch_item BEGIN SELECT RAISE(ABORT,'IMMUTABLE_BATCH_PLAN'); END;
CREATE TRIGGER shot_batch_seal_no_update BEFORE UPDATE ON shot_batch_seal BEGIN SELECT RAISE(ABORT,'IMMUTABLE_BATCH_PLAN'); END;
CREATE TRIGGER shot_batch_seal_no_delete BEFORE DELETE ON shot_batch_seal BEGIN SELECT RAISE(ABORT,'IMMUTABLE_BATCH_PLAN'); END;
INSERT INTO schema_version(version,applied_at) VALUES(2,strftime('%Y-%m-%dT%H:%M:%fZ','now'));
COMMIT;
