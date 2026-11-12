# Independent V2-D0 design0.2 focused re-review

Recommendation: **READY_FOR_ROOT_D0_DOCUMENT_ADJUDICATION**. Prior findings **M01/M02/m01/m02/m03/m04 are closed at the design-contract level**; remaining finding counts are **F0 / M0 / m0**. This is a focused document-readiness recommendation, not product Gate0, V2 activation, Stage PASS, native feasibility proof or HTTP runtime PASS. The root retains formal adjudication authority.

Candidate: `b7d12d76ea2bef3161c810871d9480f07e683f07`. Initial independent review: `7249ec113407e725734ce1ccc6390c9e6199d0b6`. Root baseline: `56832a43a2beb05f03ea7a00a66e198acfdd19f7`. The worktree started clean at the initial review commit; `git merge --no-edit b7d12d76ea2bef3161c810871d9480f07e683f07` completed as a fast-forward. Only this new `independent-correction01/` subtree is authored by the reviewer; no candidate, checker, product, canonical contract, old report or packet was edited. Earlier full tracked-file snapshots and the old exit-1 semantic observations are retained, not rerun or rewritten.

## Actual checks and scope

| Command / scope | Runs | Actual result |
|---|---:|---|
| `python3 tools/verify_v2_library_design.py --self-test` | 1 | exit0; 1,162 checks passed, zero failed |
| `python3 tools/build_full_spec.py --check` | 1 | exit0; raw stdout `FULL_SPEC_CURRENT` |
| New review-local `focused_probe.py` | 1 | exit0; 78 checks passed, zero failed |

All raw stdout/stderr bytes, true exit files and argv/cwd receipts are included. The stderr streams are empty. The updated checker and full-spec generator were inspected before execution; the focused probe imports only standard support and the already available jsonschema validator. It evaluates static candidate contracts, complete JSON fixtures and candidate DDL on SQLite `:memory:`. SQL INSERTs name columns explicitly to accommodate head sequence, retry metadata and default tags_json. No packages were installed.

No app imports, whole-product suite, retired V1-D0 matrix, old semantic-probe replay, actual media/DB read, media scan, original-file action, native executable, FFmpeg, MCP client, GPU/model/Provider, service, browser, network or download was used. Git merge/inspection/commit and Orca completion messaging are separate trusted metadata operations. A hand-authored SQL transaction example is evidence of the design's expressibility; it does not prove an unimplemented application handler uses that transaction.

## Closure assessment

### M01 — CLOSED_AT_DESIGN_LEVEL

Locations: `docs/34_V2_LIBRARY_ARCHITECTURE.md /设计0.2/描述与模板头的强ETag`; `contracts/candidates/v2-library/semantic-rules.json /head_cas`; `contracts/candidates/v2-library/openapi-overlay.json /description and naming-template 200 responses/headers/ETag`; `contracts/candidates/v2-library/storage-additions.sql /library_store_epoch and head_sequence`.

Required strong quoted lh headers on all five read/create/revision responses; exact head/body binding, store_epoch/revision/hash/sequence material and two recomputed vectors; missing428/stale412/weak-wildcard-list400 rules; independent memory SQL positive and stale full-transaction rollback for both description and template heads.

Limit: The local probe demonstrates candidate schema/SQL and normative transaction examples, not production CAS/HTTP handler execution.

### M02 — CLOSED_AT_DESIGN_LEVEL

Locations: `contracts/candidates/v2-library/storage-additions.sql /rename_plan_item,ix_preview_target_conflicts,file_target_reservation`; `docs/34_V2_LIBRARY_ARCHITECTURE.md /冲突预览与可执行目标保留分离`; `contracts/candidates/v2-library/semantic-rules.json /conflict_preview`.

Two duplicate-target preview rows persist; unique volume/parent/target reservations are separate. The local memory probe rejects duplicate selected reservations, rolls back operation and all new reservations, retains both preview rows, accepts one selected reservation, and rejects a competing operation without clearing the first reservation. Normative contract requires zero file actions before successful reservation.

Limit: No actual file actions/native race tested; SQL uniqueness is a coordination mechanism, not a replacement for native no-replace.

### m01 — CLOSED_AT_DESIGN_LEVEL

Locations: `contracts/candidates/v2-library/openapi-overlay.json /semantic_rules and GET rename-plans/{id},items,exports`; `contracts/candidates/v2-library/library.schema.json /$defs/PlanSummary,PlanItemPage`.

GET is explicitly summary-only; separate keyset /items is bounded 200; exact-plan CSV/JSON streaming export retains all frozen rows including conflicts. The old promise of inline first-200 rows is removed.

Limit: Streaming/pagination behavior still needs actual public-entry tests at the appropriate packet.

### m02 — CLOSED_AT_DESIGN_LEVEL

Locations: `contracts/candidates/v2-library/job-compatibility.json`; `contracts/candidates/v2-library/library.schema.json /$defs/LibraryIntent,LibraryTask`; `contracts/candidates/v2-library/storage-additions.sql /library_job_intent`.

Typed internal intent is keyed to the same persistent job ID. All three parent kinds project to batch; reconciling/preparing and needs_attention/interrupted+RECOVERY_AMBIGUOUS are explicit. Fixed terminal/total progress, scan unsealed0/0, resource state, null parent result_ref and typed result traversal are specified. Legacy list/get remain strict; cancel dispatch checks operation-control authority, legacy retry rejects409 without replay, batch body is unchanged. Independent schema projection checks cover all30 kind/status combinations.

Limit: Actual final V1 Job/Attempt/storage reuse and dispatch authorization remain implementation/pilot packet obligations, not existing runtime claims.

### m03 — CLOSED_AT_DESIGN_LEVEL

Locations: `docs/34_V2_LIBRARY_ARCHITECTURE.md /显式重试关系`; `contracts/candidates/v2-library/library.schema.json /$defs/RetryPlanRequest,RenamePlanRevision,PlanSummary,PlanItem`; `contracts/candidates/v2-library/openapi-overlay.json /file-operations/{id}/retry-plans`.

Dedicated reviewed retry-plans route binds current operation If-Match and last_event_seq; plan and item lineage fields enter plan_hash. Terminal operation/proved writer exit/uniquely reconciled locations are required; successful or ambiguous items are excluded. A staged item uses its real current temporary locator. Failed undo retry preserves direction=undo and distinct undo_of original-forward versus retry_of failed-undo. Fresh selection/closure/reservation/confirmation is mandatory. Complete positive forward/undo DTOs and negative missing-lineage/duplicate-selection fixtures pass.

Limit: No native recovery, staged-file movement or replay executed; runtime must enforce eligibility and custody beyond JSON shape.

### m04 — CLOSED_AT_DESIGN_LEVEL

Locations: `docs/34_V2_LIBRARY_ARCHITECTURE.md /真实调用与耗时的公开投影`; `contracts/candidates/v2-library/library.schema.json /$defs/LibraryTask,LibraryAccounting,LibraryAccountingItem,LibraryAccountingItemPage`; `contracts/candidates/v2-library/openapi-overlay.json /library/tasks/{id}/accounting and accounting/items`.

Task accounting_ref traverses bounded actual accounting. Per-asset rows bind child/attempt/model_run/analysis_key/action IDs; attempts and observed calls differ, phase times are explicit, unknown observed calls/unmeasured times are null with incomplete accounting. Independent complete fixtures validate unknown and measured values, reject negative values, allow200/reject201 item pages. CPU zero calls still requires actual Provider ledger evidence.

Limit: Counter consistency, truthful observed ledger collection and timing must later be tested through actual owner/read routes.

## Goal2 tags and source/language consistency

The correction makes existing description/tag semantics explicit, without adding product scope or any case ID. FieldFact now requires `language=zh|en|und`; description revisions and edit requests require typed `tags`. TagFact carries label/language/source_kind/source_ref/source_revision/confirmation/coverage. Confirmed tags require provenance, observed tags require nonempty coverage, creative_intent is excluded, and labels are bounded. Candidate description storage adds `tags_json NOT NULL DEFAULT '[]'`.

The independent probe uses complete valid description/edit/tag fixtures, including a locked `tags` path and a complete user-confirmed DJ fact. Its negative fixtures isolate creative provenance, null source/ref revision, empty observed coverage, invalid language, empty/overlong labels, extra path properties and omitted tags; a complete confirmed-inference DJ fixture is rejected while the matching user-confirmed fixture passes. This avoids false-negative conclusions from testing an otherwise incomplete DTO. Explicit-column SQL confirms the default tags_json value.

Docs34 defines fact uniqueness by (field,language), evidence-preserving normalized tag display, full tags locking, same-language fact selection or language-independent technical metadata, and missing bilingual fields following the missing-value policy without implicit translation. These are shared-service semantic obligations, not fully enforced by array JSON Schema or claimed implemented by this review. Future public-entry tests must check duplicates, lock preservation, evidence retention and indexing alongside the shape constraints. None constitutes a new D0 finding.

## Preservation and immutable binding

The bounded hash audit includes exactly **110 baseline protected files plus 23 candidate manifest entries**, with selected execution-control comparisons. `source-before.json` contains declared and actual SHA-256 values; `source-after-checks.json` and `source-final.json` contain recomputed values. All protected hashes match the root's recorded baseline and all23 candidate entries match their pinned manifest; the before/after/final source hashes are equal. No new 10k-file snapshot was generated.

`preservation-proof.json` also records the initial-review Git tree object and the identical tree object at the corrected candidate. This preserves the old review, old failed semantic evidence and original full snapshots without replaying or changing them. Execution target/next delivery, current coordinate including WAIT_BUDGET, complete outline, last-passed/current-blocking gates, implementation/429 routing, candidate, human signoff, product acceptance and stop-report policy all equal the root baseline. Candidate execution-control changes only add future V2 review/correction metadata; byte identity of the entire execution file is not asserted. Protected canonical contracts and frozen packets remain unchanged.

The V2/V3 candidate denominators remain **56/65 = active38/47 + RN18**, with V1 active29 and original R3/R4 PTS/recipe/FTS/MCP/batch/recovery/backup and V1 regression obligations retained. Typed tags add no case denominator. MasterPack v2.0.0 remains a document-package name, not an accepted product V2. The earlier external report remains input only; it was not reread, used as runtime authority or allowed to resume V1 in this focused review.

## Explicit later-packet conditions

- Native Windows no-replace/file ID/ancestor/reparse/locking/TOCTOU/case/cycle/ACL/custody/flush behavior remains unverified and requires the bounded authorized target-Windows pilot. Reservation uniqueness does not establish filesystem safety.
- Final V1 actual persistent Job/Attempt/schema/owner reuse and migration binding remain prerequisites; NEXT_VERIFIED_SCHEMA is not treated as an already deployed schema. Preserve strict old Job and generic batch through the specified facade.
- Public HTTP entry tests must verify exact returned-head/body ETags, positive/stale CAS rollback, conflict preview completeness, atomic reservation failure before enqueue/file effects, reviewed retry eligibility and fresh confirmation, actual accounting and tags locks/provenance. This review does not substitute memory SQL for those tests.
- Root paths, private samples, original-write scopes, actual30 licensed sample hashes/sealed labels, runtime budgets and model/action bindings remain unmaterialized/unapproved; runtime authorization/write/sample/threshold fields remain null and activation status remains DESIGN_CANDIDATE_NOT_ACTIVE. No user media was inspected.
- Proposed quality/performance/profile metrics remain PROPOSED_PENDING_PILOT, with no metric or threshold approval inferred. Safety no-overwrite/no-loss/no-content-modification obligations cannot be relaxed. Deferred pilot evidence is not counted as a D0 runtime failure.
- The external journal/DB restore distinction and prior-writer exit proof remain mandatory; unknown observed calls/times stay null/incomplete, never manufactured zero. Actual zero-model paths require Provider-ledger evidence later.

These conditions concern future activation and implementation packets; they do not reopen the six corrected document findings or request product implementation in D0. No automatic restart, quota fallback, model change or Claude launch occurred; current V1 correction04 remains WAIT_BUDGET.

## Ten-field observation-only stop record

- **当前坐标**: {"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW", "state": "WAIT_BUDGET"}; target_version=V1
- **本批完成**: Focused independent design0.2 review: both Major and all four Minor findings closed at design level; typed tags consistent; residual F0/M0/m0; 1162 design checks, FULL_SPEC_CURRENT and 78 focused checks.
- **最后通过门禁**: {"gate": "UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW", "candidate_sha": "621b1bf386db71bfe08ca2f533fa8ec396b0504b", "receipt": "reports/unified-media/independent-live-15/receipt.json", "decision": "10PASS_0FAIL_0BLOCKED_FATAL0_MAJOR0_HUMAN_ACCEPTED_SCOPE_ONLY", "cpu_checks": 212, "fixed_cases": 10, "passed_cases": 10, "human_signoff": "reports/unified-media/human-signoff-live15.json"}
- **当前阻塞门禁**: WAIT_BUDGET_CLAUDE429_CORRECTION04_STOPPED_NO_TAKEOVER_AUTHORIZATION; V1 correction04 WAIT_BUDGET unchanged; V2 runtime remains inactive.
- **全局路线位置**: Full unchanged V0–V3 development_outline below; this review adds no product completion count.
- **剩余工作**: Root D0 document adjudication; final V1 reuse/schema audit, explicitly authorized native/sample/model pilots, budget/quality approval, actual public-entry validation and formal Stage packet before V2 activation.
- **下一责任人**: Root Codex design/gate coordinator; future implementation only through the authorized route after prerequisites, never automatic Claude429 fallback.
- **所需授权**: This focused static/schema/memory review and local commit are authorized; no V2 runtime/private media/original-file write/GPU/model/download authority or metric approval inferred.
- **证据目录**: reports/v2-library-design-2026-11-12/independent-correction01/
- **精确停止原因**: Assigned focused independent re-review complete; ready for root D0 document-readiness adjudication with no residual findings, while future runtime gates and current V1 WAIT_BUDGET remain.

## Complete unchanged V0–V3 outline

Counts reflect declared completed substeps/total, not work estimates. Current Stage: R1 / WP-R1-U3 / WAIT_BUDGET.

| Stage / delivery | Completed | Implementation | Machine acceptance | Independent review | Human signoff |
|---|---:|---|---|---|---|
| V0-S0 / V0 | 1/2 | ARCHIVED | NO_GO_HISTORICAL | COMPLETED_WITH_BLOCKERS | NOT_SIGNED |
| V0-S1 / V0-Min | 5/5 | DELIVERED | ACCEPTED_SCOPE_ONLY | COMPLETED | APPROVED |
| R0 / V1前置 | 1/2 | PARTIAL_REUSED | SINGLE_IMAGE_SUBSET_ONLY | NO_SEPARATE_R0_VERDICT | NO_SEPARATE_R0_SIGNOFF |
| R1a / V1早期切片 | 5/5 | DELIVERED | ACCEPTED_SCOPE_ONLY | COMPLETED | APPROVED |
| V0-S2 / V0.1 | 7/8 | IMPLEMENTED | COMPLETE_FIXED9_PASSED | COMPLETE_FATAL0_MAJOR0_MINOR0 | PENDING |
| V0-S3 / V0.2 | 0/6 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R1 / V1 | 0/4 | EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING | EARLY_SLICE_UM10_ONLY | EARLY_SLICE_FATAL0_MAJOR0 | EARLY_SLICE_APPROVED_FULL_R1_PENDING |
| V1-M1 / V1 | 0/3 | DESIGN_ONLY | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R2 / V1 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R3 / V2 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R4 / V2 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R5a / V3 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R5b / V3 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
| R5c / V3 | 0/4 | NOT_DELIVERED | NOT_RUN | NOT_RUN | NOT_SIGNED |
