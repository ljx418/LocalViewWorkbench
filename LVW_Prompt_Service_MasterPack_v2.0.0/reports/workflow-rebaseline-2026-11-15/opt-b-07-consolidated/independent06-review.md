# Feedback06 independent source and actual-result review

CHANGES_REQUIRED — Fatal0 / Major5 / Minor0. No checkpoint endorsement, runtime ACK, N2 clearance or Stage PASS. This is the finite review deliverable; no candidate, guard or test was executed/imported/compiled/collected by this reviewer. Source is exact Git candidate `9b6d9d4b827587d132eaf20e2b838d449ed89bd3`; evidence commit is `bb071c1f33ddb80f9e56f4fb385f9e6fbcc85acd`. Old94cdd82 and incident/guard/readiness reports remain immutable historical records.

## Binding and actual facts

Plan SHA256 `1e370a2fdb74a3bda372100ac5323eb47d9b9ef22ce865dc85dd2738b1208271` matches. Independently rehashed61 source,4 tool,223 named dependency,3 stdlib/interpreter and10 protected history pins: zero mismatches. All182 tracked combined02 raw files equal evidence-commit blobs. Three changed test modules equal candidate bytes; production broker/custody unchanged from d645. The exact two original-module diffs change only output routing/cleanup internals, leaving original test identities, order, signatures and decorators unchanged; frozen189 is also confirmed against actual call order. Named pins establish bounded byte identity, not full transitive environment integrity. Detailed actual hashes and checks are in source-binding.json; no history was copied or rewritten.

Selected, collected and actual194 call-node identities match frozen order exactly, all unique: original189 PASS189; supplemental5 PASS4/FAIL1; skips0/missing0. The runner records only call reports, so no claim of independently logged successful setup/teardown phases; no extra reported failures were hidden. Two original integrity-only nodes remain integrity checks, not functional/native cases. Runner duration53.768878698349s, exit1. SUP03 fails at line431 with injectioncount0. The other four outer negative PASS outcomes are evidence of their executed assertions, not proof all frozen obligations are complete.

Guard ledger contains106 os.symlink denials. Outer actual accepted_cpu_feedback=false, error GUARD_RUNTIME_DENIALS_NONEMPTY. The hard veto worked and this run remains rejected. Singleton preload records only ctypes.dlopen(None), window CLOSED before candidate. FD before/after rows are identical; available inventories have no unknowns or new/reused FD, and threads after are MainThread only. cleanup_proven_for_batch=true is consistent with these CPU facts. Process exit was not substituted for observed thread cleanup.

Narrow original execution transcript commands independently bind before/guard/after argv and seven-key env -i dictionaries to plan06, with matching stdout/stderr paths; quoting differs from literal command rendering for guard/after but parsed tokens match. Outer decision bytes bind the actual rejected result; no separate in-child environment dump is claimed. Counter contents were not read. Present ten-history rehash establishes current baseline equality; producer pre/post assertions are not silently promoted to independent pre-run ownership proof. Combined05 is exhausted history and was not reused.

Key actual hashes: runner `09bb14012c19490fb4ed60614afedcdf9e4ac0e824e14bbcfad69a452cf2df25`; guard `1bfad3f917fb3f61c1ad6c4c61b758cfccec31d255629ddc343cf43769c95f00`; outer `d3b395ef74039df6982c6951ff06561263dd7a5de8a9ed931ae1c9252639b242`; producer `295bbac758eed84c7006b719179260240fea3b42f20731d2de2ad4a6ecae80f8`.

## Consolidated effective findings

### F06-M1 — Major (test qualification)

Location: tools/test_v0_s3_native_custody_cleanup_faults.py:419-451; tools/test_v0_s3_native_custody_correction10.py:3899-4280; production broker:5470-5529 / custody:835-867. Trigger: SUP03 runs the real R07 zero round before controlled CHILD_TRANSPORT writer injection.

Expected: Reach the designated inner writer exactly once, preserve its error and sentinel, reject the callee, publish real cleanup. Actual: Actual SUP03 failed at line431: injection count0; no child_transport raw. Earlier real pump ended with BROKER_CHANNEL_TIMEOUT, frames0; zero round failed and stopped the later subcase.

Oracle/negative: Require injection count1 at exact phase/index, callee failure with injected error, durable failure and real cleanup; zero real owner/context identity and exact0 wait facts remain required. A zero pump error must remain a failure; no suppressing timeout, extending product deadlines, or treating thread death as successful service.

Minimum closure: Resolve frozen zero prerequisite/scheduling with the existing real public path, and capture actual queue/error publication relative to tightening; then demonstrate the missing writer negative under a new finite frozen plan. Uncertainty: The trace establishes pump failure and missing injection, not the precise channel-error publication interleaving or a production ownership flaw. Holding pump read alone does not synchronize channel producer/error publication.

### F06-M2 — Major (trusted harness compatibility)

Location: guard-boundary-02/guard.py:40,85; pinned _pytest/pathlib.py:205-239; _pytest/tmpdir.py:109-153. Trigger: Pytest make_numbered_dir attempts a best-effort current alias inside explicit combined02/pytest-temp.

Expected: Owned fixture temp operations must coexist with protection against historical/outside writes; all remaining denials veto acceptance. Actual: All106 ledger rows are os.symlink and truncated at200 chars; pinned pytest _force_symlink swallows Exception. There are106 direct temp directories and no aliases. Outer correctly REJECTED.

Oracle/negative: Review complete source/destination/dir_fd and pinned callpath; only actual approved same-root alias operations can be admitted in a future guard. Outside target/destination, traversal, symlink ancestor/alias escape, unsupported dirfd, generic link/delete/rename remain rejected; any nonempty/missing ledger remains a hard veto.

Minimum closure: Root may freeze a minimal rule limited to canonical NEW R/pytest-temp: existing numbered directory source and direct sibling current destination with matching prefix, verified parents/root identity and no symlink ancestry; default dirfd only or explicitly resolved identity-bound anchor. Recheck destinations on subsequent mutations. Preserve hard veto, test both owned aliases and outside/escape negatives before candidate feedback. Uncertainty: Source plus count strongly supports pytest current aliases; clipped logs do not establish full arguments/caller for each106 event. Do not retroactively whitelist this run. Cooperative path checks do not solve adversarial rename races, inherited descriptors or native writes.

### F06-M3 — Major (test qualification)

Location: tools/test_v0_s3_native_custody_cleanup_faults.py:310-337,363-365; tools/test_v0_s3_native_custody_correction10.py:1447-1485. Trigger: The real drain repeats its release tuple in another iteration.

Expected: Forward the actual third callback on every invocation, but inject K1 exactly once across repeated callbacks; distinct precreated K2 must not replace first exact K1. Actual: Original third callback is now called correctly and exact K1/K2 objects are precreated. However k1_release raises on every invocation; drain_state[k1] counts wrapper installation, not raises. Actual raw shows one RELEASE K1 for this schedule only.

Oracle/negative: Count actual K1 injections and original third callback forwarding/results across repeated invocations, assert first propagated object is K1, K2 distinct, durable failure and physical cleanup. A repeat must forward the real callback without a second injected cancellation; do not replace it with a gate or simplified lifecycle.

Minimum closure: Make injected K1 one-shot independently of callback forwarding; retain and verify original callback results and injection count on a bounded repeated-callback path. Uncertainty: No repeated K1 happened in current raw; the reproducible source branch exists when the bounded drain repeats. This is a required negative qualification gap, not an observed production cleanup leak.

### F06-M4 — Major (test qualification)

Location: tools/test_v0_s3_native_custody_cleanup_faults.py:149-155,268-278,306-404,569-641. Trigger: Final query faults or interrupted-start lookup faults require exact independently held resource identity.

Expected: Compare faulted worker/settled owner/joined thread against the independently observed actual fixture-held objects. Actual: SUP01 stores self but compares only faulted_name with shutdown names. SUP02 checks hit count without binding target object. SUP05 links joined thread to settled thread, but checks settled_owner only nonnull; it does not compare to independently captured expected owner. Exact O and first K exception identity assertions are fixed.

Oracle/negative: Retain expected real references before the fault; assert faulted is expected worker and settled is expected held owner, and joined is expected held thread. Use transparent original method/result recorders. A wrong same-name worker or different owner/thread pair must fail qualification even if each is nonnull and internally consistent.

Minimum closure: Add the missing exact reference comparisons at existing observation seams, with no lifecycle replacement. Requalify affected negatives; keep actual branch PASS separate. Uncertainty: No evidence that wrong objects were used in this run. Current assertions/raw cannot independently exclude that regression as required by frozen M2/M5.

### F06-M5 — Major (evidence truth)

Location: combined02-execution-receipt.json /unresolved_limits/3. Trigger: Producer emits final receipt for the194-call run.

Expected: Accurately distinguish executed original189, supplemental5 and unexecuted product29. Actual: Receipt says remaining175 of189 were NOT selected/NOT run, contradicted by exact selected/collected/call order. Root snapshot preserves it and records contradiction.

Oracle/negative: Append-only producer correction binds original receipt SHA256 and exact actual call evidence; no silent replacement. Do not infer product29/native acceptance from original189 or total194.

Minimum closure: Producer append a signed/attributed correction identifying wrong JSON pointer, original hash,189/189 actual calls and rejected overall result; preserve original bytes. Uncertainty: Root annotation already prevents blind acceptance but does not correct producer record; this is necessary coverage truth, not a purely duplicate display detail.

## Zero timeout and compatibility boundaries

SUP03 zero raw proves the real held background pump finished=true/alive=false, exact broker/context/observer identity true, replywait[0.0]/queuewait[0.0], error BrokerError(BROKER_CHANNEL_TIMEOUT), frames0, broker retained and UNKNOWN_RETAINED. Gate release succeeded. Production custody.run calls broker.read after its earlier remaining check; broker.read crops to0 and, on empty queue, propagates an already-published channel error. Channel _check_wait can publish timeout at the newly expired context. This explains a feasible scheduling mechanism, not a proved complete interleaving. The fixture holds pump read but does not establish underlying queue/error publication order. Preserve this semantic failure and actual retained broker facts; do not call timeout harmless, infer production owner loss, or extend product thresholds. Actual salvage and final batch resource inventories demonstrate cleanup separately. Minimal next evidence is the relevant queue/error publication relative to tightening, followed by the missing inner-writer fault at its exact existing phase.

The pinned pytest _force_symlink unlinks the old current alias and attempts symlink_to(new numbered directory), swallowing ordinary Exception. make_numbered_dir calls it after mkdir; explicit basetemp resolves to new R/pytest-temp. All106 clipped denials were inspected, but their full destination/dirfd/caller are unavailable. Count106 matches direct numbered directories; this supports a compatibility diagnosis without proving each argument. No retroactive waiver. A future bounded exception must validate canonical source AND destination under new owned R, same-parent numbered/current relationship, root identity and dirfd semantics. A relative target is resolved against link parent, not cwd. Unsupported dirfd remains denied unless anchored and verified. Avoid symlink ancestors and check every subsequent write/rename destination; do not open generic aliases, /tmp, HOME, /dev, deletion or rename exceptions. Existing literal /dev/null identity allowance remains the only device compatibility rule.

Adjacent pinned pytest mutation audit: explicit basetemp can rm_rf an existing directory, then mkdir700; freshness must be checked by root before execution. Numbered dirs require owned mkdir, current replacement unlink/symlink and dead-alias cleanup; those cannot authorize recursive outside removal. Logging uses already-reviewed literal /dev/null. No new broader platform framework is needed. Cooperative Python path checks retain native/adversarial/inherited-fd/TOCTOU race limits; do not claim OS isolation.

## Historical M1–M5 and four obligations

| Obligation | Independent disposition for this candidate/run |
|---|---|
| Old M1 | Mechanism CLOSED_STATIC: actual _reader/_writer and invoked stop_accepting/request_cancel. Raw has real shutdown entry, joined_after and thread_handle_released true; batch resources clean. No formal historical rewrite. |
| Old M2 | Frame depth3 reaches designated zero_guarded_query; SUP01/02 actual hitcount1 supported by executed assertions. Exact worker target identity still F06-M4. |
| Old M3 | Correct original third callback and precreated exact K1/K2; first exact K1 escaped on this run. Repeated injection/forwarding qualification remains F06-M3. |
| Old M4 | CLOSED_STATIC plus SUP01/02 branch evidence: unknown liveness stays null, unknown_queries/handle_proof/proof_failure persist, callee fails; independent salvage joined/dead and batch resources clean. No conversion of unknown into false. |
| Old M5 | Exact O identity SUP01/05 and firstK SUP02 fixed; SUP05 real original settle and join forwarded, joinedthread is settledthread asserted. Independent expected owner/target identity still F06-M4. |
| N1-OPT-01 | OPEN: required inner-writer negative absent in current run (F06-M1). |
| N1-OPT-02 | SUP04 actual PASS qualifies recovered final-write branch: injected at third write, retry durable error plus failed proof, calleeFAIL and quiescent. No overall closure. |
| N1-OPT-03 | Final-query O > firstK > ordinary verdict preserved; necessary publication reached in SUP01/02; unknown fails. Residual M3/M4 prevent complete negative qualification. |
| N1-OPT-04 | SUP05 real public interrupted-start failure, inflight query fault and later thread lookup fault, actual settle5/join/dead retained. Expected owner identity still incomplete. |

N05 now requires explicit nonempty absolute evidence env; F5/T10/N05 plan routes are separate new directories and sup cases have independent subdirectories. Module route checks do not themselves establish freshness. Product29 and original9 native uncertainties remain unproved, using unchanged prior review scope. CPU194 never substitutes for189, product29 or native runtime evidence. All historical five Majors/incident remain open for formal exit until root adjudicates complete closure; static/branch facts above are deliberately narrower.

## Next necessary action and stop state

Root and ClaudeCode should freeze one consolidated minimal correction set for missing SUP03 prerequisite evidence, callback one-shot proof, exact resource identities and bounded pytest alias compatibility, plus an append-only producer correction. Rehash/review corrections before any separately authorized finite feedback. Keep original combined02 and the false producer sentence immutable. Required negative/guard/identity evidence remains necessary; no automatic Minor downgrade. Review is complete with blockers; no new runtime permission is issued.

## Full development outline

From authoritative execution-control: V0-S0 1/2 (historical NO_GO), V0-S1 5/5 (signed scope); R0 1/2, R1a 5/5 (signed single-image scope); V0-S2 7/8 (human signoff pending), V0-S3 0/6; current R1 0/4 (early unified-media3/3 UM10 accepted/signed only), V1-M1 0/3, R2 0/4; V2 R3 0/4, R4 0/4; V3 R5a 0/4, R5b 0/4, R5c 0/4. This review changes none of these counts or signoffs.

## Ten fields

1. Coordinate: V1 / R1 / WP-R1-U3 / S3_P4.
2. Last passed scope: unified-media UM10 early slice, not full R1.
3. Current batch: concentrated independent source+actual feedback06 review complete.
4. Blockers: F06-M1..M5; historical formal exit/incident remains open.
5. Route: approved OPT-B correction/feedback, then C only when dependencies qualify.
6. Remaining: consolidated corrections, byte freeze, required negative/guard evidence and formal adjudication.
7. Next owner: root for scope/harness/receipt; ClaudeCode for frozen test corrections.
8. Authority: read-only review; no runtime ACK, Stage or N2 clearance.
9. Evidence: source-binding.json, findings.json and immutable combined02 raw at evidence commitbb071c1.
10. Stop: CHANGES_REQUIRED; implementation delivered, actual CPU run rejected, independent review with blockers, human/product/native acceptance not supplied.
