# P3B implementation receipt — READY_FOR_REVIEW

Candidate: `cea5bf328ea35a5aa1d1feb51ac3ef8946a964fa` (final, binds every check below).
Base / frozen authority: `35f1ee4df74e3a6054e021ee9cbbd066eaba5490` (root freeze commit, already the
HEAD of this worktree before the batch; nothing to merge, no reset, no rebase).
Frozen contract: `reports/v0-s3/product-gate0/p3b-quality-contract.md`
(sha256 `d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3`).
Frozen input projection: `reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json`
(sha256 `47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3`, 16 ordered rows, 10 images /
6 videos).
`contract_changes=none` — no public API, schema, threshold, denominator, prompt, workflow, owner,
authority, ledger, quality-set, prelabel, sample, template, coordinate, MANIFEST or frozen-packet file
was modified.

## Source of this candidate

| File | sha256 | lines | role |
|---|---|---:|---|
| `tools/v0_s3_quality_phase.py` | `7211f23d4fe2dc7f840c13ba0a9db1535c78f480b4f39bf0cbeadd50f23b2c26` | 1534 | QD execution phase + QS independent score recomputation |
| `tools/test_v0_s3_quality_phase.py` | `372555acfcef7b55bbd00dbb6edb6ad16e796a7e25c3a0dfb408a1fbeea28c48` | 1114 | 67 offline acceptance checks |
| `reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py` | `d1261c15c58d6b5e5bd16b7e5a683112d2746a09f432ade836022078dda183f6` | 254 | guarded runner (audit hook before pytest import) |

Commit history of this worktree for the task:

- `8f76dd8` — preserved the interrupted work-in-progress source as an explicitly **partial, untested,
  not accepted** snapshot (58886 bytes, sha256 `62a6b51594ec838d309bd14a4a2584a6a66c06cdb0db18cf7ac2df9b8be8d186`),
  so the interruption state is not lost and is not mistaken for a delivery.
- `747bef6` — the completed QD + QS implementation, the offline test module and the guarded runner.
- `667da62` — the runner gained an executed guard self-test.
- `cea5bf3` — an unused import was removed from the test module; no behaviour change. This is the
  final candidate that every check below binds.

## Complete V0–V3 outline (unchanged coordinate)

| Delivery | Stage | Completed / declared | Boundary |
|---|---|---:|---|
| V0 | V0-S0 | 1/2 | 历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS |
| V0-Min | V0-S1 | 5/5 | 已签仅V0-Min |
| V1前置 | R0 | 1/2 | 仅R1a前置单图子集可确认；不把完整视频/Q01算通过 |
| V1早期切片 | R1a | 5/5 | 已签仅单图切片；完整V1未完成 |
| V0.1 | V0-S2 | 7/8 | Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain. |
| V0.2 | V0-S3 | 0/6 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V1 | R1 | 0/4 | 最小统一图视频切片3/3、UM10机器与独审通过，用户已确认当前前端与基本视频反推；完整R1四子项仍0/4，不补签历史S2/完整V1或发布。 |
| V1 | V1-M1 | 0/3 | 用户批准纳入V1；设计/合同审查中，未实现、未测试、未签署 |
| V1 | R2 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V2 | R3 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V2 | R4 | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5a | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5b | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |
| V3 | R5c | 0/4 | 已有设计，未完成正式交付；存在代码需进入时复用审计 |

The counts are copied unchanged from `plans/execution-control.json` `development_outline`. **No
completion count was advanced by this batch.** V0-S3 stays 0/6: this is offline wiring only.

## Ten required fields

1. 当前坐标: R1 / WP-R1-U3 / `S3_P3B_QUALITY_INTEGRATION_IMPLEMENTATION`; this batch implements S3-P3B
   (QD execution then QS scoring) under the frozen internal contract.
2. 本批完成: QD public sixteen-row execution phase (offline, synthetic boundary) and QS independent
   score recomputation, plus 67 offline acceptance checks (39 QD-directed, 28 QS-directed, one
   combined run of all 67). Implementation self-check only; independent review pending; no machine
   product acceptance and no human signature is claimed.
3. 最后通过门禁: unchanged `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`, candidate
   `621b1bf386db71bfe08ca2f533fa8ec396b0504b`, scoped existing human acceptance.
4. 当前阻塞门禁: `S3_PRODUCT_GATE0_PENDING` — the real product Gate0, the actual run, the independent
   review of this candidate and the required human signature are all still open.
5. 全局路线位置: offline quality integration (QD+QS) → independent review of this candidate → root
   architecture/gate decision → frozen complete product Gate0 (real profiles, A06, rollback, the fixed
   twelve items) → finite same-source real run → independent acceptance → required human signature.
6. 剩余工作: independent isolated review of candidate `667da62`; the real runtime staging (actual
   profile, model digest, media preparation, child authorization, single GPU), the real finite
   sixteen-row run, the independent scoring pass on the real raw artifacts and the required human
   experience signature.
7. 下一责任人: separate independent reviewer instance, then root (Codex) as architecture and gate owner.
8. 所需授权: none additional for the completed offline scope. This batch performed no real service,
   model, media, GPU, network, download, ledger, Windows/WSL/PowerShell, parser or host-exe hashing
   action, and it does not authorize any of them.
9. 证据目录: `reports/v0-s3/product-gate0/implementation-p3b/` (receipt.json, report.md, SHA256SUMS,
   the four guarded check receipts, their raw stdout/stderr logs and the guard self-test).
10. 精确停止原因: the frozen QD + QS contract is implemented and the directed plus combined offline
    checks are green and captured with their real exit codes; the implementer stops at
    **READY_FOR_REVIEW**. No Stage PASS, no product Gate0, no machine product acceptance and no human
    signature is declared or implied.

## Production path actually exercised

The offline suite drives the **real** production code and replaces only the native boundary:

- The public node classes `LVWControlledImageInput`, `LVWImagePromptBridge`, `LVWManualPromptOwner`
  and `LVWVideoPromptOwner` are instantiated and executed; the manual metadata observation graph is
  built with the existing public helper
  `reports/v0-s1/stage-checkpoint-phase-a/checkpoint.py::manual_public_graph`, exactly the way the
  accepted cumulative phase observes it.
- The real `BridgeOwner` parses, compiles and publishes the machine suggestion; only the HTTP
  transport and the frame encoder are synthetic, so the raw Ollama envelope, the `frame_raw_responses`
  array and the `lvw.prompt/1` suggestion are production-shaped bytes.
- The real controlled image owner (`ControlledImageOwner`) preprocesses a generated 4×4 PNG and
  produces the real `source_sha256` / `source_bytes` / `output_dimensions` / `output_rgb_sha256`
  metadata that the phase binds.
- The real original oracles are reused unchanged: `tools/v0_s2_checkpoint_oracles.py::public_video_oracle`
  (four frame raws, frame timeline, four provider calls, source/run identity, suggestion schema
  version) and the frozen PromptSpec validator from `tools/v0_s2_measurements.py::spec_validator`.
- The real provider chat counter `tools/v0_s2_cancel_evidence.py::count` recomputes the chat count
  from the raw log bytes and cross-checks the log length and hash; the phase never trusts the
  driver's own count.
- The real driver surface is the `NativeRuntime` surface (`submit`, `chat_log_snapshot`,
  `resource_observer`, `_json_request`, `owned_listener_birth`, `release_preload`,
  `video_snapshot_residue`, `submissions`, `max_public_submissions`). `release_preload` is the
  accepted default image release path and is reused unchanged, so no release marker is ever
  fabricated by the phase. `video_snapshot_residue` is the one accessor that does not exist yet in
  the production runtime; the parent supplies it as a read-only adapter that enumerates the owned
  `lvw-video-*` snapshot directories under the Comfy temporary parent. **No owner, source or product
  file was modified to provide it.**
- The phase reads the two production workflow JSON files and re-verifies their bytes against the
  candidate-bound `source_identity`; the graph is the frozen graph with only `1.inputs.image_reference`
  or `1.inputs.video_reference` replaced, plus the public manual metadata observer node for images.
  No label, caption, expected answer or score ever enters the graph.

## What the phase enforces (and what it refuses)

QD, per row, before and after the send:

- the frozen projection is strict: unique asset id, unique source hash, unique simple reference,
  10/6/16 denominator, an exact field set per row and at the top level, so no label, prelabel or
  score field can travel with the execution input;
- every prepared source is validated up front; a single mismatch means **zero submissions** and all
  sixteen rows retained (the failing row FAIL, the others BLOCKED);
- the critical source is re-verified immediately before its own send with a bounded read (never past
  the frozen byte count) and a stable dev/ino/size/mtime/ctime identity, so growth or replacement
  between the preflight and the send is detected instead of silently followed;
- the provider budget (1 chat for an image, 4 for a video, 34 in total) is **reserved before** the
  attempt, so a failed or unknown submission can never be under-counted and re-sent;
- the actual raw bytes are written as UTF-8 **before** any structural judgement, with the machine
  suggestion and the controlled metadata kept in separate artifacts; a rejected row keeps its raw
  and its history;
- the before provider log must remain the exact original prefix of the after log, the observed chat
  count must be exactly 1 or 4, and the prompt id must be unique across the sixteen rows;
- the owned Comfy and Ollama listener PID/birth must not drift, the reused public release evidence
  must be proven with an empty model inventory and baseline-stable GPU samples, and the owned video
  snapshot residue must be empty;
- an uncertain public state, a storage failure, an unproven release, a residue, an identity drift or
  a budget ceiling stops every later submission. The sixteen rows always stay in the denominator,
  nothing is ever retried automatically, and no row is ever silently replaced or reordered.

QS, independently:

- it is a pure validation and aggregation entry point; the QD path never calls it, and the QD class
  source contains no reference to it, to the rubric, or to any score field (asserted by a test);
- every scoring receipt must bind run, candidate, projection hash, asset id, source hash, the raw
  artifact path and its hash, and the reviewer and session identity;
- the reviewer identity string alone proves nothing: an isolation receipt with an explicit
  separation block and a run binding is required, and the reviewer may not be the implementer;
- the actual raw artifact is re-read and re-hashed from disk; a suggestion or manual substitute is
  rejected by the artifact path binding and by the hash;
- the five frozen dimensions are integers in 0..2 (a bool is not an integer) and the critical
  hallucination count is a non-negative integer; a missing score, a failed execution or an
  unpreserved raw keeps the row FAIL inside the unchanged sixteen row denominator;
- the aggregate needs 8 of 10 images, 5 of 6 videos and zero critical hallucinations, and it needs
  every row resolved: an unscored raw run can never aggregate PASS;
- the output is scoped to the bound sixteen rows, states that four frames cannot prove motion
  continuity or physical camera movement, and never claims a Stage or product pass.

## Actual checks, real exit codes

Every check was executed through `run_offline_checks.py`, whose `sys.addaudithook` guard is installed
**before pytest is imported**. Plugin autoload is disabled (`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`), the
cache provider is disabled and bytecode writing is off. The raw stdout and stderr streams and the
actual pytest exit code are written next to each other; the shell captured the process exit code
directly (no pipeline masking it).

| Run | Label | Exit | Result | Denominator | Evidence |
|---|---|---:|---|---|---|
| guard-selftest | guard-selftest | 0 | all four blocked attempts blocked | 4 attempts | `guard-selftest.guard-selftest.json` |
| QD directed | qd-directed | 0 | 39 passed, 28 deselected | 39 | `qd-directed.stdout.log`, `qd-directed.receipt.json` |
| QS directed | qs-directed | 0 | 28 passed, 39 deselected | 28 | `qs-directed.stdout.log`, `qs-directed.receipt.json` |
| combined final | combined-final | 0 | 67 passed | 67 | `combined-final.stdout.log`, `combined-final.receipt.json` |

Guard self-test: `socket.connect`, `socket.bind`, `subprocess.Popen` and `os.system` were each
attempted once and each was refused by the audit hook (`guard_effective: true`). The boundary is
executed and falsifiable, not merely declared.

The P3A 121-check suite, the P2B 237-check suite and the full project suite were **not** re-run, as
the frozen packet requires; this batch repeats neither.

### Earlier diagnostic runs, retained honestly

The interactive debugging rounds before the guarded runner existed were executed as
`python3 -B -m pytest tools/test_v0_s3_quality_phase.py ... | tail/head/grep`. Their **exit codes are
UNKNOWN**: the pipeline masked the pytest exit status, and they were not executed under the
pre-pytest audit hook. Their observed outcome counts are recorded here for honesty and are not
reconstructed as raw streams:

| Round | Exit | Observed | Scope |
|---|---:|---|---|
| 1 | UNKNOWN | 34 failed, 2 passed, 31 errors | first import of the interrupted source, class body split by a misplaced helper |
| 2 | UNKNOWN | 14 failed, 63 passed | oracle called with the history record instead of the history mapping; two separate clocks; expectations corrected |
| 3 | UNKNOWN | 4 failed, 63 passed | threshold expectations corrected to the frozen 8/10 and 5/6 gates; not-attempted rows are BLOCKED, not FAIL |
| 4 | UNKNOWN | 67 passed | same source as the final candidate; still not under the audit hook |

No failed run was rewritten or deleted, and no diagnostic round is counted as a passing acceptance.
Only the four guarded runs above are acceptance evidence, and they bind the final candidate
`667da62`. Every repair round produced new evidence (a different, newly located defect), so this is
not the prohibited two-same-route-repairs-without-evidence pattern; the sequence stopped as soon as
the frozen contract was fully covered.

## Retained fixture state and cleanup

- The synthetic fixtures (ten generated 4×4 PNGs, six small synthetic video byte blobs, the
  synthetic provider log and the phase artifacts) live only in pytest's own temporary roots under
  `/tmp/pytest-of-administrator/` (three retained sessions, about 21 MiB, session `pytest-12` is the
  current one). They are outside the repository and are not committed.
- **No cleanup is claimed here.** The parent `OwnedArchive` owns the real raw archive and deletion;
  pytest's temporary directory retention is a test-harness fact and is not a product cleanup
  property.
- The repository itself contains no generated phase directory: `find` over the worktree reports no
  `s3-quality` path outside the temporary roots.
- No binary media, database, archive or copied source is committed. The only committed files are the
  two text code modules, the text runner and this text evidence.
- The pre-existing untracked `__pycache__` directories were neither deleted nor committed.

## Limits, and what this batch does NOT prove

- Offline only. No real ComfyUI, no real Ollama, no model, no GPU, no real media, no network, no
  download, no ledger mutation, no Windows/WSL/PowerShell, no host-exe hashing, no parser probe and
  no full checkpoint was executed.
- The native HTTP/provider boundary and the media bytes are synthetic. The suite therefore proves the
  wiring, the refusals and the evidence binding — it does **not** prove any product quality result.
- `public_video_oracle` still requires independent decoder recomputation of the frame bytes, and four
  sampled frames still cannot prove full motion continuity or physical camera movement; this phase
  does not score either.
- The quality set, the prelabels and the frozen projection are never read by the execution or the
  scoring module; the projection carries no label, caption or expected answer, and the five scoring
  dimensions are embedded constants taken from the frozen rubric.
- The production `video_snapshot_residue` accessor does not exist yet. Until the parent supplies it,
  no real video row can be shown clean by the phase, which is the intended fail-closed behaviour.
- No machine product acceptance, no independent review verdict, no Stage PASS and no human signature
  is produced or implied by this receipt.
