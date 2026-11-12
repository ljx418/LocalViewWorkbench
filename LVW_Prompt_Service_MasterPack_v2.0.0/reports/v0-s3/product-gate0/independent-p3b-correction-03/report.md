# Independent P3B correction03 aggregate review

**CHANGES_REQUIRED — component recommendation only; Fatal0 / Major5 / Minor1.** Four Major findings are reproducible current code defects; E01 is a separate historical process/evidence finding. No Stage PASS or product acceptance.

Candidate `630853c63a919433ccf31958d36179e4e0b3bdee`; merged evidence `0e045c71f05ed316a519c6363649b7852739d101` with `git merge --no-edit` (fast-forward from correction02 review1290616). Worktree was clean; no unrelated state was removed. Root metadata4bcb640c was read only with git show; it was not merged. Only this new review subtree is authored.

## Evidence and counts

The combined suite ran **once:145 passed, exit0**, under the inspected independent pre-pytest/product-import audit guard. The guard selftest ran once:4 blocked attempts, exit0. The immutable correction02-observation replay ran once:22 unique observations, exit0. New bounded focused observations total **183=170+8+5**, each batch exit0; these include counterexamples and are not 183 additional passing tests. No separate112/33, P3A121, P2B237 or full-project run occurred. Raw stdout/stderr, actual subprocess exits, exact commands/cwd and before/after module/test/runner/probe hashes are retained in command/launch receipts; SHA256SUMS inventories all review artifacts.

The original91 test functions still account for112 collected instances; current functions account for145. `test-obligation-audit.json` maps every original function/assertion to current collected nodeids, so this is not an arithmetic assumption. Exactly3 old test functions changed: phase-deadline setup extends parent expiry to20000 without changing assertions; persisted totals now count both retained hardlink entries/bytes; cap tests prefill publication fields and count2 entries, preserving their exact/one-over assertions. The shared synthetic release fixture adds typed baseline/full proof but retains old unproven/resident/nan/inf/bool branches. No original obligation was dropped.

Module SHA256 `ca599e9da68c9a6f9405b9f89ae8bd999a43a1ecc237e469207ffede7ae98c42`; tests `cd1eec5f8265e0e5e9e3ce49f35012f18236f8d3fe86719cfe851c3b333698d5`; replay `1babdad243f9194bcf4129d9d763c8020a365846de2a430108075bcfb8873d8b`; immutable probe guard `c1f375c8030cae6daf75a23667b13debd0f3372ecdd4a6d31ab46b8c4cbfb81b`. All match committed candidate. Contract `d06a6688fa618cd9fef1cd7f362b8d165addc0030dde0b5aee77465c2a2c20a3` and projection `47e9f14efa66bc4df851bf1a738763b48c1728eed84b76c56a7848d1b01f00c3` and frozen spec manifest remain unchanged. No full quality-set/prelabels/testSource/holdouts were read.

## Aggregate findings

### M01 — Major — reproducible current code defect

Location: `tools/v0_s3_quality_phase.py:2226-2250 load_canonical_receipt; 2405-2430 recompute_scores`.

Trigger: After actual QualityPhase.run, keep the original successful execution dictionary and real raw artifacts but remove canonical qd-receipt.json (leaving staging), corrupt its bytes, or replace it with a foreign-run canonical document; call public recompute_scores.

Expected: Consumer must establish actual canonical publication and identity/content binding for this execution/artifact root; staged-only, absent, corrupt or foreign terminal evidence cannot become aggregate PASS from favorable dictionary flags.

Actual: All three public scorer calls return aggregate_pass=true, usable=true, resolved=true. The canonical loader rejects absent/corrupt bytes when called separately, but is never called by recompute_scores; foreign canonical loader returns foreign-run. Public QS only checks published_as/receipt_persisted/terminal_status fields supplied in memory.

Evidence: `focused-observations.json:missing_canonical_retained_stage`, `focused-observations.json:corrupt_canonical`, `focused-observations.json:foreign_canonical`.

Required disposition: Wire canonical loading and exact bound-execution validation into public QS (including run/candidate/projection/root/actual canonical evidence), retaining staged bytes as nonauthority. Do not infer authority from publication booleans alone.

Verified progress: Actual exclusive staging write/flush/fsync/close failures preserve partial/non-authoritative evidence, canonical absent, returned blocked/storage unknown, loader rejects and replay preserves bytes. No-overwrite pinned-dirfd link and real exact/one-over caps are verified; parent-directory crash durability remains explicitly unproven.

### M08 — Major — reproducible current code defect

Location: `tools/v0_s3_quality_phase.py:483-516 validate_source_evidence; 519-563 validate_release_evidence;1087-1138 _validate_source;2331-2367 _row_evidence_complete`.

Trigger: Mutate each original descriptor identity component (device/inode/size/mtime/ctime), substitute [0,0,0,0,0], or remove/null run_root or parent_budget_baseline_gpu_mib, through public QS on PASS and complete known FAIL rows; also pass float baseline context100.0. Trace actual validator invocations through QD and QS.

Expected: Complete typed mandatory context, exact source path and original descriptor identity/size/time/inode binding, and strict bound baseline are required. Missing/null/wrong-type evidence stays unknown on PASS/FAIL; shared QD/QS source and release validators must actually run.

Actual: All five integer identity substitutions and all-zero tuple are accepted. Missing/null run_root bypasses path binding; missing/null parent baseline bypasses release-baseline equality; float100.0 is accepted as bound100. For PASS each yields usable/resolved/aggregate true; for known FAIL it stays unusable but falsely resolved and aggregate true. QD source-validator calls=0 and release=16; QS source=16/release=16. Source helper verifies only tuple shape/nonnegative integers, not identity[2]==bytes or equality with original sealed identity.

Evidence: `focused-observations.json:qs.PASS.source.identity.changed_size`, `focused-observations.json:qs.FAIL.source.identity.allzero`, `focused-observations.json:qs.PASS.receipt.run_root.missing`, `focused-observations.json:qs.FAIL.receipt.baseline.null`, `focused-observations.json:shared_validator_calls`, `context.stdout.log:context_parent_budget_baseline_gpu_mib_float`.

Required disposition: Require typed nonempty bound run_root and strict integer bound baseline before per-row validation, bind full evidence tuple to original QD evidence and enforce size consistency, and actually share source validation between QD and QS. Preserve verified known failures as resolved/not usable and independently verified critical evidence. This does not require permanent retention/live restat of deleted source media or broader hostile-filesystem guarantees.

Verified progress: All literal False uncertainty fields, malformed/missing source evidence, foreign source path and raw hash/length rejection improve correctly. Release proof loaded_models strict int0,3..32 actual samples, finite nonbool elapsed0..30, cadence<=1.5 and last3<=baseline+1024 are checked when typed context is present. Thresholds8/10,5/6,score>=8,global critical0 remain unchanged.

### NM01 — Major — reproducible current code defect

Location: `tools/v0_s3_quality_phase.py:883-909 _send_admission_guard;1394-1415 driver counter/limit reads and reservation/submit`.

Trigger: Use a conforming driver with dynamic max_public_submissions property; on its read after the final guard set phase.parent_budget.action_capacity=0. Execute actual QualityPhase.run with original production fixture semantics.

Expected: Finish all driver/accessor callbacks before the final typed proof validation; reserve/charge/send only with current sufficient proof capacity, no unchecked callback between validation and send. Diminution before first send must give0 sends and16 refused.

Actual: Property runs after guard at capacity34, changes capacity0, and one public submission is sent/charged/reserved1; first row passes and next15 block. Current capacity is0, violating cumulative reservation<=current admitted capacity at the first send.

Evidence: `focused-observations.json:driver_accessor_capacity_zero`, `focused.py:ObservedDriver.max_public_submissions`.

Required disposition: Resolve driver counters/limits and callable submit handoff before the final guard, then recheck exact typed proof and reserve/charge immediately before the saved submit, with no unchecked controlled accessor afterward. No retries/refunds or new ledger API.

Verified progress: Ordinary authorize expiry2/capacity0 already gives0 sends/all16 BLOCKED. Wrong run/candidate/auth and bool interval/capacity refuse sends. Later valid interval expiry and diminution preserve first charged/reserved attempt and block remaining15. Authentic parent ledger reservation/debit remains NOT_PROVEN.

### NM02 — Major — reproducible current code defect

Location: `tools/v0_s3_quality_phase.py:898-924 _send_admission_guard/_parent_proof_is_fresh;1397-1415 driver accessors before submit`.

Trigger: Use finite nondecreasing clock values where the first final-guard read is within phase limit and the second read inside _parent_proof_is_fresh returns10801, with proofexpiry20000; separately move clock10801 through the post-guard driver limit accessor.

Expected: The latest cooperative clock observed immediately before reservation/send must meet phase10800 and parent validity together. A later clock read or callback cannot invalidate a previously checked deadline without another check.

Actual: Both cases submit and charge1 at clock10801, then report HISTORY_TIMEOUT/FAIL with15 BLOCKED. The second _now() is used only for parent interval, leaving the earlier phase check stale; dynamic driver limit is another unchecked callback after validation.

Evidence: `focused-observations.json:final_guard_second_clock_crosses_phase_deadline`, `focused-observations.json:driver_accessor_phase_expired`.

Required disposition: Use one final latest clock sample to validate both phase deadline and current proof after all controlled callbacks/accessors. Keep exact deadline10800 accepted and one-over refused. This remains cooperative validation, not the missing parent supervisor.

Verified progress: Requested prep10799/authorize+2=>10801/proofexpiry20000 counterexample now refuses0/all16. Existing exact10800/oneover tests pass. Nonfinite/bool/decreasing clocks refuse. Mandatory parent hard-process supervision remains UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER, with no process/platform tests performed.

### E01 — Major — historical execution/evidence uncertainty; not a proven current product defect or proven external action

Location: `implementation-p3b-correction-03/report.md:143-170; receipt.json:316-322; tools/test_v0_s3_quality_phase.py:24-60; root warnings msg_9967e153e87a and msg_91d0a21059c2`.

Trigger: Compare admitted ten direct piped pytest rounds plus two ad-hoc debug imports before second warning with the assertion that the test module guard before its local import pytest proves no prior socket/process/external actions. Inspect installed pytest CLI startup and retained diagnostics.

Expected: Preserve twelve underlying exits UNKNOWN and distinguish known execution-order violation, missing event/command/raw-stream evidence and unsupported zero-event claims. Test-module monkeypatches cannot retrocertify CLI startup.

Actual: python -m pytest executes import pytest in __main__ before console_main; pytest configuration/plugin loading occurs before collection imports the test module. Thus test module monkeypatches are too late to guard CLI/plugin startup, although they precede its own local import statement. Historical12 exact raw streams/true exits/pre-import audit are absent; the14 retained guarded edit diagnostics are separate runs with true exits0,1,1,1,0,1,1,0,1,1,1,1,0,0. No actual forbidden external action evidence was identified; no blanket zero-event certification is supported.

Evidence: `pytest-import-order.json`, `historical-evidence-audit.json`, `root-warning01.json`, `root-warning02.json`, `source-bindings.json:suite_runner`.

Required disposition: Append a factual erratum to the implementation narrative/receipt: test-module guard does not establish pre-pytest guarding, exits remain UNKNOWN and early zero external actions are NOT_PROVEN. Keep original wording and failed/unknown records. Do not run a cosmetic new full suite to repair historical prose; no rerun can retrocertify those attempts.

Verified progress: Final retained145 receipt has actual exit0, raw stream hashes/bytes match, and the immutable final runner installs audit hook before pytest. Current independent145 executes pinned candidate bytes with before/after hashes under a pre-import guard; early diagnostics receive no acceptance credit. Historical final receipt lacks per-run before/after imported-source hashes, so its candidate argument alone is not a full execution attestation.

### E02 — Minor — count/label erratum

Location: `implementation-p3b-correction-03/report.md:135 versus receipt.json:179-180; replay_correction02_probes.py:229-268`.

Trigger: Count actual unique result.probe entries rather than copy21 from prose or reinterpret the replay cap labels as actual frozen-cap tests.

Expected: Accurate separated observation counts and honest cap evidence labels.

Actual: Committed implementation correction03 replay and this once-only replay each have22 unique observations; report row says21 while receipt22 is correct. Previous independent correction02 replay really has21; its focused18 plus final-gap4 are22 separate observations. Current replay actual_* cap probes mutate cap constants and do not establish real8MiB/128MiB/256 limits.

Evidence: `replay-count-erratum.json`, `replay.stdout.log`, `focused-observations.json:realcap_artifact_exact`, `focused-observations.json:realcap_total_exact`, `focused-observations.json:realcap_files_exact`.

Required disposition: Preserve old text; this append records current replay22, earlier replay21 and earlier focused18+4 separately. Actual frozen-cap evidence is the new six focused realcap observations; no replay repeated just to fix prose.

## Persistence, proof, production path and retained closures

Actual public run staging faults target the exclusive pinned-dirfd staging FD, not an unrelated artifact. Write fault retains17 partial bytes; flush/fsync/close faults retain the staged payload. All return blocked/storage unknown, canonical absent, canonical loader rejects and replay refuses overwrite with unchanged bytes. File-close occurs before publication; owned-directory close suppresses ordinary OSError after publication. Source audit found no ordinary post-publication validation/callback that changes returned success to failure; no hostile-kernel or arbitrary memory-failure guarantee is inferred. Both hardlink entries are included in actual count/bytes. New frozen-cap observations accept8,388,608 bytes per entry,134,217,728 total bytes and256 entries exactly, refuse one-over, with constants unchanged. Parent-directory crash durability remains explicitly unproven.

Public QS is actually invoked for all evidence mutations, not just helper tests.140 PASS/known-FAIL mutation observations cover receipt+row storage/cleanup flags missing/null/wrong-type, source path/bytes/hash/identity, all5 identity components, mandatory run-root/baseline context, complete release fields and sample/cadence/stability details. The root-requested context follow-up adds5 public cases; float100.0 baseline wrongly passes, while wrong string/bool/negative baseline and integer run-root reject against the original100 context. Release boundaries allow3/32 samples, elapsed0/30 and cadence1.5, reject elapsed30.000001/cadence1.500001/loaded_models=False. These are synthetic proof validation, not real GPU observations.

Complete known failure remains resolved/not usable; independent critical3 stays visible and makes globalcritical3/aggregatefalse.8images/5videos with3 resolved failures aggregates true, confirming no all-technical-success addition. Original score>=8,8/10images,5/6videos and globalcritical0 are unchanged. Raw evidence hash/strict length negatives reject.

First authorize expiry2 and capacity0 now refuse0/all16. Later true valid-interval expiry atclock2 keeps1 send/charge/reservation and15BLOCKED (supplement); later capacity diminution likewise retains1. First wrongrun/candidate/auth/bool interval/capacity refuses sends. Phase prep10799 plus authorize2 to10801 with proofexpiry20000 gives0/all16; exact10800 versus oneover and nonfinite/bool/decreasing clocks remain covered. NM01/NM02 concern the last unchecked operations only; they do not claim a parent supervisor exists.

Production `SyntheticDriver.submit` still routes real registered image/manual/video nodes, real ControlledImageOwner and BridgeOwner, original PromptSpec and public_video_oracle; only synthetic HTTP/provider/tiny fake video decoding/resource boundaries are substituted. New review probes reuse this path. No private inference helper replaces a production node. Provider rawfailure/partialframe evidence,16 denominator,1/4/34 reservation and charge/no-refund/no-retry, PID/birth and cleanup ownership remain.

| Prior finding | Disposition | Evidence / retained boundary |
|---|---|---|
|M01|PARTIALLY_FIXED_REMAINS_OPEN|M01; focused actual_run_staging_{write,flush,fsync,close}, realcap_* and canonical consumer observations|
|M02|CLOSED_SCOPED_OFFLINE|Original112 ancestor/temp/root/phase replacement and replay tests pass within145; _OwnedDirectory pinning/O_NOFOLLOW/dir_fd, exclusive writes, close paths audited. Accepted in-process inode-moving/hostile-kernel limit retained; no reopening.|
|M03|CLOSED_SCOPED_OFFLINE|Original112 source replacement/growth/hash/path tests and final post-authorization source read remain; descriptor before/after/path hash identity checked. M08 scorer evidence binding is distinct from accepted execution source ownership.|
|M04|CLOSED_SCOPED_OFFLINE|Original cleanup-exception tests, _execute_row finally and diagnostic/release ownership remain; every row unknown cleanup halts. Parent OwnedArchive cleanup still required.|
|M05|CLOSED_SCOPED_OFFLINE|Failed/unknown submit stays charged before call,1/4 local reservation max34, no refund/retry; original failed-submit/reservation tests pass. NM01 final timing gap does not erase retained accounting closure.|
|M06|CLOSED_SCOPED_OFFLINE|verify_independence exact (reviewer,session) pairs retained; original cross-pair/reused/implementer negatives pass.|
|M07|CLOSED_SCOPED_OFFLINE|Public scorer actual raw artifact hash/strict byte length checks preserved; original raw length tests and3 new focused raw mutations reject.|
|M08|PARTIALLY_FIXED_REMAINS_OPEN|M08;140 PASS/FAIL evidence-field observations plus context/boundary checks; known-failure critical3 retained; exact8images5videos with3 resolved failures aggregates true as intended.|
|M09|CLOSED_SCOPED_OFFLINE|Original BridgeError raw, video prior frame raw, provider-after persistence-failure tests pass; actual production node/BridgeOwner path retained.|
|m01|CLOSED_SCOPED_OFFLINE|Strict nonfinite/bool release evidence validation persists; original release-nan/inf/bool tests pass; new typed/public release negatives reject with bound context.|
|NM01|PARTIALLY_FIXED_REMAINS_OPEN|NM01; ordinary first/later authorize proof checks improved but unchecked driver accessor remains.|
|NM02|PARTIALLY_FIXED_REMAINS_OPEN|NM02; ordinary authorize-phase deadline improved; latest clock/accessor gap remains. Parent hard supervision explicitly not implemented.|

## Historical execution evidence: known facts, missing evidence, unsupported claims

Known facts: root warnings record direct piped CLI pytest and ad-hoc debug import after warning; implementer formally admits TEN piped pytest rounds plus TWO debug imports before the second warning. Their true underlying exits remain UNKNOWN and they receive zero acceptance credit. Fourteen later guarded diagnostics are distinct, with raw stream hashes/bytes matching retained receipts and real exits0,1,1,1,0,1,1,0,1,1,1,1,0,0. They are not substitutes for the earlier twelve records.

Missing evidence: exact complete commands/raw stdout/stderr/event audit and independently retained pre-import guards for those twelve attempts are not present in this evidence commit. The reported synthetic-only scope is an implementer assertion. No retained evidence establishes an actual forbidden external action; this review also cannot certify zero such actions. Source-level monkeypatches cannot establish historical event absence. There is no reason to rerun145 to cosmetically repair historical evidence.

Final retained145: the actual exit0 and raw stream digests/lengths match; inspected immutable `implementation-p3b/run_offline_checks.py` installs audit hook before importing pytest, disables plugin autoload/cache/bytecode, and final source/test hashes equal candidate. Its historical receipt binds candidate by argument and omits per-run imported-source hashes. This review independently runs those pinned bytes with before/after hashes, supporting current code verification but not retrocertification of earlier imports/actions. The new suite/replay/focused/context guards report no blocked external events outside the four deliberate selftest attempts. The guard covers named Python audit events; it makes no universal native-extension/direct-syscall claim.

E02 appended erratum: correction03 replay actual22; old correction02 independent replay actual21; old focused18+finalgap4 are22 separate observations. Do not merge these denominators or repeat a replay for prose. Original report/receipt/logs remain unchanged.

## Limits and ownership

Mandatory actual external parent process supervision/watchdog, pending-I/O handling and owned cleanup remain **UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER**. A dictionary, constant, cooperative clock or this review cannot close it. No worker-platform/process tests were run.600/10800 limits and parent ownership remain. Authentic ledger admission/debit, native residue adapter, enforceable A06, real16quality, full12, productGate0, human/release acceptance are NOT_PROVEN. No stage counts advance.

Zero actual Windows/WSL/PowerShell/parser/hostexe hashing/realmedia/FFmpeg/models/GPU/services/network/download/real-ledger/fullcheckpoint. All fixtures are new registered own /tmp roots (replay nested beneath registered launch root), explicitly removed; receipt records exact roots/removal. Earlier roots were never scanned/deleted. Binary cap fillers/media were removed with exact owned roots and never committed. Only new text evidence/scripts are committed; no DB/ZIP/copied product source, old-history rewrite, push or permanent config. Pytest fixture cleanup is not product OwnedArchive cleanup proof.

## Ten-field handoff

1. 当前坐标: R1 / WP-R1-U3 / S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW / PREPARING_NEXT_STAGE; read-only root4bcb640c, unchanged.
2. 本批完成: Independent correction03 review complete:145/145 once (112 original obligations+33 added), guard4/4 once, replay22 once, 183 new independent observations (170+8+5); Fatal0/Major5/Minor1. Observations are not additional passing product tests.
3. 最后通过门禁: UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW on621b1bf386db71bfe08ca2f533fa8ec396b0504b; existing scoped human acceptance unchanged.
4. 当前阻塞门禁: S3_P3B_INDEPENDENT_REVIEW_AND_COMPLETE_PRODUCT_GATE0_PENDING; local CHANGES_REQUIRED, mandatory parent hard supervision remains open.
5. 全局路线位置: Root aggregate disposition → bounded correction → separate independent review → thin coordinator/native residue/admission/A06/Gate0 → finite real16 → independent semantic scores → required human/release gates.
6. 剩余工作: Four precise local code root causes plus historical evidence correction, and all listed global/native acceptance obligations; no Stage advancement.
7. 下一责任人: Root architecture/gate owner for aggregate disposition; authorized visible implementer for corrections; separate reviewer after corrected candidate.
8. 所需授权: None additional for completed authorized offline review. No real runtime permission inferred and no repeated user authorization requested.
9. 证据目录: reports/v0-s3/product-gate0/independent-p3b-correction-03/; aggregate report/receipt/findings/source pins/AST audit/commands/raw streams/cleanup/count erratum.
10. 精确停止原因: Assigned independent review delivered with reproduced current code defects and separated historical uncertainty; return once with full commit SHA and keep terminal visible.

## Full unchanged V0–V3 outline

Read-only source: root `4bcb640c1b9d2dd70779c3cf3e25a44586eac486` execution-control. Current Stage **R1**. Full substeps/status/evidence are preserved in `root-coordinate.json` and `receipt.json`; no completion or signoff was changed.

| Delivery | Stage | Done/total | Implementation | Machine | Independent | Human |
|---|---|---:|---|---|---|---|
|V0|V0-S0|1/2|ARCHIVED|NO_GO_HISTORICAL|COMPLETED_WITH_BLOCKERS|NOT_SIGNED|
|V0-Min|V0-S1|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|
|V1前置|R0|1/2|PARTIAL_REUSED|SINGLE_IMAGE_SUBSET_ONLY|NO_SEPARATE_R0_VERDICT|NO_SEPARATE_R0_SIGNOFF|
|V1早期切片|R1a|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|
|V0.1|V0-S2|7/8|IMPLEMENTED|COMPLETE_FIXED9_PASSED|COMPLETE_FATAL0_MAJOR0_MINOR0|PENDING|
|V0.2|V0-S3|0/6|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V1|R1|0/4|EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING|EARLY_SLICE_UM10_ONLY|EARLY_SLICE_FATAL0_MAJOR0|EARLY_SLICE_APPROVED_FULL_R1_PENDING|
|V1|V1-M1|0/3|DESIGN_ONLY|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V1|R2|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V2|R3|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V2|R4|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5a|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5b|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5c|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
