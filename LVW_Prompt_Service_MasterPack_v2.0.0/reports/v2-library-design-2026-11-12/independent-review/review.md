# Independent V2-D0 design review — 2026-11-12

Recommendation: **CHANGES_REQUIRED for D0 document readiness**, with **F0 / M2 / m4**. The product intent and architecture are coherent enough to retain as a design candidate; resolve M01 and M02 in a new candidate and obtain independent focused re-review before declaring D0 ready. This report is an independent recommendation, not root adjudication, product Gate0, Stage PASS, or permission to start V2. Minor items may be accepted with explicit later-packet conditions.

Reviewed candidate `93d72f9de7c8bc9b88760ed9daef9fb7fd6f8c1f`; root baseline `56832a43a2beb05f03ea7a00a66e198acfdd19f7`. This worker started clean at `0d5c023712651b20f3554ed4f0feb2b56b974bd6` and performed the requested `git merge --no-edit` as a fast-forward. Pre-existing history was preserved, including the root baseline evidence absent from the earlier review branch; no reset, cleanup, product edit, package installation, service launch or Claude invocation occurred. The only new work is this independent-review directory.

## Actual validation and bindings

- `python3 tools/verify_v2_library_design.py --self-test`: exactly once, exit **0**, **1048 passed / 0 failed**. These are structural/JSON/schema/plan/link/hash/in-memory DDL consistency checks, including the checker's negative self-tests; they are not RN product passes.
- `python3 tools/build_full_spec.py --check`: exactly once, exit **0**, raw stdout `FULL_SPEC_CURRENT`.
- Review-local `semantic_probes.py`: once, exit **1**, **24 observations**, two unsatisfied design obligations (M01/M02). This exit is the deliberate aggregate semantic-review result, not an exception or a production failure. The memory-only SQL reproducer records the exact UNIQUE violation, database integrity `ok` and zero FK errors. Its static/schema observations also support four minor comments and positive provenance/MCP boundaries.
- The checkers were read before running. No application imports, application tests, retired V1-D0 checker, real database, media decoding, native executable, FFmpeg, Provider/model/GPU, service, browser, download or network was used. The only database connections were SQLite `:memory:`. Git inspection/merge/commit and orchestration are separate trusted metadata operations.
- Raw byte stdout/stderr, real exit files and argv/cwd receipts are alongside this report for all three runs. The empty stderr files are actual captured empty streams, not omitted failures. The initial manual tool inspections are not counted as application validation.
- `tracked-before.json` and `tracked-after-checks.json` bind every tracked repository artifact before/after the two prescribed checks (10,217 entries). `preservation-proof.json` compares protected source bytes directly to Git root-baseline blobs, independently of the author's summary. It also validates the candidate manifest and selected execution fields. Final unchanged hashes are recorded in the receipt. Hashing tracked repository fixtures is metadata verification; no actual user-media file was opened or scanned.

The external architecture report was read as text, SHA-256 `47a08763acc7942719295ef6a417d1729d4a9605dcc8da923300061d5f7d84bc`, matching change-record.proposal. It is **input only**. Its stale `b1a9386` HEAD/previous execution coordinate neither supersedes the root baseline nor resumes V1. No media referenced by that report was read. Source facts were independently read in media.py, service.py, video_kernel.py and models.py without importing them: image PNG derivatives and uploaded video copies have null source binding, refs/paths/jobs/runs/idempotency are in memory, jobs cap at 128, the worker uses asyncio.Lock, and current video input remains MP4/MOV bounded at 256 MiB with the old controlled short-video route. Final V1 persistent owners/schema are prerequisites, not existing runtime claims.

## Eight goals and retained obligations

| Requested goal | Design binding and assessment |
|---|---|
| 1. Local registration/reference/scan | R23; RN01/05/16; trusted local CLI/native IPC registration, read/list default, separately granted analyze and rename_archive, permission epoch/revocation, keyset pages and cancellation checkpoints. Distinct business source ID, volume+file ID, content hash; derived uploads confer no original write authority. |
| 2. Truthful understanding/description/tags | R24; RN02/18; independent append-only description head/revisions, source/version/coverage/unknowns, explicit adoption and locks. No creative-intent facts or guessed identity/date/song/BPM/key. M01 affects the usable CAS wire contract. Existing asset/tag responsibilities remain. |
| 3. Chinese/English/bilingual rules | R25; RN03/04; field whitelist, missing-value policy, vocabulary/template versions, frozen Seq, no CPU pseudo-translation, deterministic hash suffix and naming limits. Analysis template changes and naming template changes are expressly distinct. |
| 4. Preview/edit/select/export | R26; RN04/16; immutable full plan, old/new mapping, conflicts, selection closure/hash, expiring single-use confirmation, If-Match and exact idempotency. M02 blocks faithful persistence of duplicate-target previews; m01 clarifies the bounded GET contract. |
| 5. Safe selected batch rename | R27; RN05/06/07/10; unique writer, native no-replace candidate, explicit scope, old/temp/target checks, partial success and no hidden re-numbering. Native feasibility remains unverified, as declared. |
| 6. Same-volume archive/undo/recovery | R28; RN06/08/09/17; existing registered target directories only, no cross-volume copy fallback, durable step intents, reverse reviewed plan, no delete/overwrite, custody before new writer. m03 requests explicit forward-retry lineage. |
| 7. Search/stable references | R29; RN11/13/14; business asset/media/Prompt/Scene identity survives movement, current location and old names/FTS update together, explicit rebind and missing states. Third-party editor projects are warned about and receive mapping, never promised automatic repair. |
| 8. Offline/accounted reuse/manual path | R30; RN03/12/15/18; exact analysis reuse key includes source, actual frames/PTS, profile/model/schema/analysis-template/config; manual path and CPU rendering/apply/undo require zero Provider calls. Ledger/elapsed evidence is required, but public task accounting needs elaboration (m04). |

Old R13/R14/R15/R16/R21 and R3/R4 obligations remain: actual PTS/time-base and VFR handling, asset/recipe append-only versions, FTS, comparison/QC/JSONL, real MCP clients, generic parent/child jobs with attempt/lease/cancellation/recovery, backup and cumulative V1 regressions. L1–L4 add work inside R3/R4 and do not replace their original four substeps. V3 peer authority is untouched. The additive API check preserves old strict Job schemas and old `/jobs/batch` body exactly; m02 asks for the new facade projection, not edits to those legacy contracts.

The fixed candidate RN01–RN18 are unique and currently NOT_RUN. V2 candidate is **38+18=56**, V3 candidate is **47+18=65**; canonical active gates remain **29/38/47** for V1/V2/V3. Old gate receipts cannot certify this new scope. The package name **MasterPack v2.0.0 is not product V2**. R23–R30 and requirement coverage, cases, tasks, gate overlay, sample design and prompts were inspected as a consistent candidate set; the checker also verifies the additive gate prefixes and DAG. No RN runtime denominator was executed here.

## Safety and compatibility assessment

| Review concern | Design assessment / remaining boundary |
|---|---|
| Source identity and authorization | source_file business ID, physical volume/file ID and SHA are separate; same-hash copies remain separate, hardlink aliases are read-only, rebind never guesses basename. Root path stays server-side; API/MCP accept controlled IDs/relative locations. |
| Fact provenance | observed frames, trusted metadata and user-confirmed information carry source/version; filename/OCR/tags are candidates; mtime is not event date. Confirmed DJ/Event/Date requires user_confirmed in the schema. Creative-intent field is rejected by the local schema probe. Service-level provenance/lock policies remain implementation obligations. |
| Analysis reuse versus naming | Exact analysis-key matching and insufficient-old-analysis behavior are explicit. Naming-template change only affects plan hash and does not trigger inference. No permanently-one-model-call promise. |
| Long video | Separate <=2h/20GiB profile, 4 MiB streaming hashes, finite probe/hash/seek/window/frame/index/pixel/action limits, actual PTS and observed/unobserved coverage, no duplicate fill, no whole-film copies or per-shot rescans. Sparse frames do not establish whole-event facts. Existing 60s/256MiB/4-frame path is not relaxed. Numeric profile budgets are proposed, not proven. |
| Native Windows | Candidate NTFS-only volume/file identity and fixed parent/source handles, no replace, ancestor reparse rejection, identity/hash rechecks and no silent lock downgrade; reject unverified case-sensitive directories, UNC/network mappings, ADS, aliasing/cross-volume cases. This D0 review does not prove API feasibility, TOCTOU resistance or flush behavior. |
| Cases/cycles/permissions | Case-only and SCC cycle moves use frozen same-directory temps and per-step intent; chains run from free target backwards; exact dependency closure required. Per-step root epochs/scope/identity/hash checks and atomic no-replace target race handling are specified. ACL/lock/full-disk/root/source/parent replacement fault tests remain later native evidence. |
| Confirmation and idempotency | Server token binds session/revision/hash/selected order/epochs/expiry; stale edits, revoked scopes, changed selection or source invalidate it; same-key/same-payload returns old operation without re-consuming confirmation, mismatched payload is 409. M01 is the missing ETag transport for two mutable heads. |
| Crash and custody | DB intent precedes disk action; final event/location/index commit follows it; old/temp/target identity-based coordination never blindly renames again. Unknown child/pending I/O blocks a new writer despite expired lease. No DB/filesystem single transaction or whole-batch atomicity claim. |
| Cancel/partial/retry/undo | Cancellation preserves completed side effects and records temp positions; success is separate from terminal counts; new plans/confirmation for retry/undo, no replay of successful items. Undo rechecks physical object/content/free old location and may itself be partial/recoverable. m03 is a missing explicit forward lineage contract, not proof of data loss. |
| DB backup and external journal | SQLite backup snapshot and integrity/FK/manifest checks are separate from a non-rollback external journal mirror; restore first proves writer exit, preserves newer mirror and reconciles affected IDs. Flush/retention/capacity are explicitly unresolved and auto-restored writing is prohibited before evidence. No demand for native durability proof in D0. |
| HTTP/native registration/MCP | Additive disjoint paths and Library_ components preserve old API/Job/batch. Browser cannot register arbitrary roots. Trusted CLI/native IPC registration and session bootstrap precede read/analyze/write scopes. Old MCP analyze does not inherit apply/undo, new tools have no file writes and no arbitrary Shell/SQL/path/network fetch. |

## Findings

### M01 — Description/template CAS has no specified ETag read transport

Severity: **M**. Location: `docs/34_V2_LIBRARY_ARCHITECTURE.md:41,96`; `contracts/candidates/v2-library/library.schema.json:415 ($defs.AssetDescriptionRevision),570 ($defs.NamingTemplateRevision)`; `contracts/candidates/v2-library/openapi-overlay.json:1315,1639 (GET success responses)`.

Trigger: A client reads an existing asset description or naming template, then creates the next revision using the required If-Match header.

Expected: A documented strong ETag for the mutable head is returned, with a defined relationship to the revision/head and exact If-Match semantics.

Actual: Both GET responses return only their immutable revision DTO, whose additionalProperties=false and properties omit etag; neither response declares ETag headers. The POST revision responses have the same gap, so the next legitimate CAS value is unspecified.

Evidence: semantic-probes.stdout.log observations 1–6; header/body inspection, no HTTP server run.

Impact: A conforming client cannot derive the specified head CAS value; implementers must invent an undocumented response/header or weaken the required concurrency contract.

Design resolution: Specify ETag response headers on description/template reads and revision/create responses, or an explicit head DTO/read route; bind head/revision and stale/write behavior. Add bounded positive and stale CAS wire-contract probes. No product implementation requested.

### M02 — Duplicate-target conflict previews cannot persist all planned rows

Severity: **M**. Location: `docs/34_V2_LIBRARY_ARCHITECTURE.md:49,51,53`; `plans/candidates/v2-library/acceptance_cases.json /cases/RN04`; `contracts/candidates/v2-library/storage-additions.sql:41–47`.

Trigger: Two distinct files render to the same target under collision_policy=block; the required preview must show both frozen rows and allow editing or deterministic suffix revision.

Expected: Both conflicting rows remain representable in one immutable reviewable plan, with conflict reasons and application blocked until resolved; the CSV/JSON and item list retain the same complete plan.

Actual: UNIQUE(plan_revision_id,target_root_id,target_path_key) rejects the second preview row. The in-memory DDL probe retains 1 row and raises sqlite3.IntegrityError; no alternate persisted conflict-draft representation or alternate failure/preview contract is specified.

Evidence: semantic-probes.stdout.log duplicate-target-preview-second-row and retained-row-count; exact failing constraint recorded, integrity_check=ok and foreign_key_check empty.

Impact: The common duplicate-name review/edit workflow conflicts with the executable storage contract. Dropping the offending row would also violate the full frozen-plan obligation. This is not a claim that native rename overwrites anything.

Design resolution: Separate preview conflict representation from executable target reservations, or explicitly define a complete conflict-draft carrier and its revision/export path; keep duplicate-target apply forbidden. Add a static/in-memory test that preserves two conflicting rows and blocks their application.

### m01 — GET-plan semantic rule contradicts its summary-only response

Severity: **m**. Location: `contracts/candidates/v2-library/openapi-overlay.json:3858 (semantic_rules[4])`; `contracts/candidates/v2-library/library.schema.json:1750 ($defs.PlanSummary)`; `contracts/candidates/v2-library/openapi-overlay.json /add_paths/~1api~1v2~1rename-plans~1{id}/get/responses/200`.

Trigger: A client follows the semantic rule promising metadata plus the first bounded 200 items from GET plan.

Expected: The rule and response DTO agree on whether this route returns items.

Actual: The response is PlanSummary, which has no items and forbids additional properties. A separate bounded /items route exists, so the workflow remains possible.

Evidence: semantic-probes.stdout.log GET-plan-response-schema, PlanSummary-has-items, PlanSummary-additional-properties and bounded-items-route-exists.

Design resolution: Prefer documenting summary-only GET plus /items pagination, or explicitly change the candidate response schema; preserve the bounded page contract.

### m02 — Library facade to persistent strict Job needs an explicit compatibility projection

Severity: **m**. Location: `contracts/candidates/v2-library/openapi-overlay.json:3856 (semantic_rules[2])`; `contracts/candidates/v2-library/library.schema.json:1217 ($defs.LibraryTask)`; `contracts/candidates/v2-library/storage-additions.sql:53`; `contracts/job.schema.json /$defs/Job`.

Trigger: A library scan/describe/file operation uses the shared persistent job ID, then is listed, polled or cancelled through an old Job-facing consumer, including recovery/needs_attention.

Expected: A design mapping defines internal typed intent, canonical Job kind/status/progress/result/error projection, old-list visibility, and cancel/retry ownership without changing strict old schemas or /jobs/batch.

Actual: The overlay names internal typed LibraryIntent but defines no such carrier or projection table; LibraryTask introduces needs_attention and file_operation introduces reconciling outside canonical Job states. Separate DTOs are an appropriate boundary, but same-ID storage alone does not define old-consumer behavior.

Evidence: semantic-probes.stdout.log LibraryIntent-schema-defined=false and both enum sets; baseline canonical API preservation checks pass.

Design resolution: Before L1 freezing, specify an additive internal intent/projection table and old route policy. This is a nonblocking D0 elaboration item, not a demand to bind unshipped final V1 tables now and not a reproduced runtime failure.

### m03 — Forward retry lineage is required in prose but absent from the candidate wire plan

Severity: **m**. Location: `docs/34_V2_LIBRARY_ARCHITECTURE.md:53,80`; `contracts/candidates/v2-library/library.schema.json:797,899 ($defs.RenamePlanRevision/CreatePlan)`.

Trigger: A cancelled/partial operation, including an item left at a frozen temporary location, is reviewed and retried as a new plan/attempt without redoing successful items.

Expected: The new forward plan has an unambiguous original operation/item/event lineage and review semantics, distinct from undo; selection and confirmation bind the intended retry.

Actual: CreatePlan exposes no retry_of reference; RenamePlanRevision exposes only parent_id for plan revision and undo_of_operation_id. The prose requires a new operation-chain binding but supplies no forward retry carrier, event relation or service-side derivation rule.

Evidence: semantic-probes.stdout.log CreatePlan-properties and RenamePlanRevision-properties; docs34 explicitly preserves successful items and requires fresh confirmation.

Design resolution: Before L3 freezing, specify explicit forward retry lineage or a deterministic server-derived relation plus its public review display, including staged items. Do not repurpose the legacy Job retry route or replay old tokens.

### m04 — Goal 8 transparency lacks a defined public library-task accounting projection

Severity: **m**. Location: `docs/33_V2_PRODUCT_REBASELINE.md:22`; `docs/35_V2_LIBRARY_EXECUTION_AND_ACCEPTANCE.md:33–45`; `contracts/candidates/v2-library/library.schema.json:1217 ($defs.LibraryTask)`.

Trigger: The user reviews pending assets, exact cache reuse, actual Provider actions, failures and elapsed time for a description batch.

Expected: The design identifies a bounded read projection of actual per-asset/run accounting and timing, and distinguishes reused, not attempted and failed items.

Actual: The design requires Provider ledgers and separately measured timings as evidence, but LibraryTask exposes only totals/cursor/etag; no library accounting/result-ref carrier or explicit old run-detail traversal is defined. This leaves the user-facing cost transparency part of the eighth input goal less concrete than its backend evidence obligations.

Evidence: semantic-probes.stdout.log LibraryTask-properties; external input section 4 core goal 8; all references are static.

Design resolution: Before the describe-batch packet freezes, name the read DTO/route or existing detail traversal and required accounting/timing fields. It can remain additive and bounded; no runtime implementation needed at D0.

## Accepted deferred conditions, not runtime failures

Native no-replace/ancestor handle behavior, custody and flush require the proposed isolated Windows pilot. The final V1 owner/schema/migration number must be audited after actual delivery. The 30 real licensed samples (18 development, 12 independent holdout), paths/hashes/sealed labels, fixed model/actions and original-file scopes are correctly null/unmaterialized now. Performance/quality proposals remain PROPOSED_PENDING_PILOT; safety no-overwrite/no-loss/no-content-modification duties cannot be relaxed. No sample or numeric target is marked as a runtime failure merely because it has not yet been authorized or measured.

Before V2 activation: resolve the two major document contradictions; independently review the corrected candidate; retain/accept the minor conditions with packet ownership; verify final V1 prerequisites; obtain finite actual pilot/sample/root/write/cleanup/budget authority; freeze evidence-based metrics/profile and new Stage packet; explicitly merge the effective overlay without changing old gates. Watch folders, auto apply, Office/PDF, more containers/audio, song/BPM/key/identity lookup and cross-volume moves remain separate L5 scope. None is added as a D0 implementation demand.

## Unchanged V1 proof

All **110** baseline-declared source/contract/plan/Stage-packet hashes match both the root Git baseline and candidate bytes; all **21** candidate manifest entries match. The Git diff against root baseline changes no existing old report, Stage packet or product-code path. Execution target, next delivery, coordinate (including WAIT_BUDGET), complete development_outline, last-passed/current-blocking gates, implementation route/429 policy, implementation candidate, human signoff, acceptance and stop-report policy compare equal. The execution-control file does have the author's additive V2 design reference; byte identity of that entire file is not claimed. Existing V1 spec docs30–32 have candidate cross-reference appendices, while the frozen packets and active canonical contracts remain unchanged. This reviewer changed neither.

The following ten fields are an observation-only stop report, not an update to execution-control:

- **当前坐标**: {"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW", "state": "WAIT_BUDGET"}; target_version=V1
- **本批完成**: Independent V2-D0 design review and bounded evidence captured; F0/M2/m4; CHANGES_REQUIRED recommendation only. No business implementation or runtime acceptance.
- **最后通过门禁**: {"gate": "UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW", "candidate_sha": "621b1bf386db71bfe08ca2f533fa8ec396b0504b", "receipt": "reports/unified-media/independent-live-15/receipt.json", "decision": "10PASS_0FAIL_0BLOCKED_FATAL0_MAJOR0_HUMAN_ACCEPTED_SCOPE_ONLY", "cpu_checks": 212, "fixed_cases": 10, "passed_cases": 10, "human_signoff": "reports/unified-media/human-signoff-live15.json"}
- **当前阻塞门禁**: WAIT_BUDGET_CLAUDE429_CORRECTION04_STOPPED_NO_TAKEOVER_AUTHORIZATION; current V1 correction04 remains WAIT_BUDGET. V2 D0 recommendation additionally requires M01/M02 correction.
- **全局路线位置**: Unchanged complete V0–V3 outline below; future V2-D0 review is not R3/R4 product progress.
- **剩余工作**: Root adjudication, corrected candidate and focused independent re-review of M01/M02; later-stage minor conditions, V1 prerequisites and explicitly authorized pilots/runtime gates remain.
- **下一责任人**: Root Codex design/gate coordinator; this worker does not resume the stopped Claude implementation.
- **所需授权**: Current static review/commit covered by task. No permission for V2 runtime, private sample scan, original-file writing, models/GPU or thresholds inferred. Claude429 routing unchanged.
- **证据目录**: reports/v2-library-design-2026-11-12/independent-review/
- **精确停止原因**: Assigned independent design review complete with two documented major contract gaps; recommendation awaits root adjudication. Prescribed checks each executed once; no scope escalation or implementation.

## Complete unchanged V0–V3 outline

Counts are declared completed substeps/total, not effort percentages; separate implementation/machine/review/human statuses are copied from execution-control. Current Stage is R1 / WP-R1-U3 / WAIT_BUDGET.

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
