# b05020a production source review — N1 correction11

CHANGES_REQUIRED. Actual open findings: **Fatal 0 / Major 2 / Minor 0**, counted as M07 and M08; their subpaths are not separate findings. Original M05, M09 and m03 are CLOSED_STATIC within the stated conditions; previously closed M06 and original M03 no-premature-process-close guards stay CLOSED_STATIC. All 72 obligations have individual dispositions: 47 CLOSED_STATIC, 16 OPEN, 9 UNCERTAIN. CLOSED_STATIC never means dynamic acceptance.

Candidate supplied by source-binding.json: `b05020a67f0e54d8584505e6ecac52be214ad7fd`. Coordinate V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION, RUNNING. This is an isolated static production review, not Stage signoff, final independent acceptance, N2 admission, native proof or permission to run anything. Batch189 is separate; its results were not read and no result is claimed.

B denotes the exact bound v0_s3_native_broker.py.txt, C the bound v0_s3_native_custody.py.txt. Positions are original physical one-based lines, retained in 01-v0_s3_native_broker-numbered.txt and 02-v0_s3_native_custody-numbered.txt. Both raw hashes were independently recalculated and matched: B SHA256 `4e1b63a982d820056093c1ac53bef4dba30668d35549b159d25627b7dffd7433`, 345225 bytes / 7369 lines; C SHA256 `9b7e68969f2cbf8763664ba57fa3e5ee4133a0beed076a64f037e6344f336d8d`, 112727 bytes / 2426 lines. Git provenance is the supplied source binding, not independently proven by these hashes; no checkout or candidate edits were made.

Authority consulted: root AGENTS.md, governance README, root execution-control and docs24; correction11 contract.md, scope.json and decision.json; exact correction10 production-prereview-02/review-result/review.md and final-receipt.json. Original receipt/report supplies the issue vocabulary and 72-atom denominator only: every disposition below is supported by this candidate's source. No implementer report, test source, PASS narrative, local test claims, runtime batch output, original ledger or counter was read. JSON/hashing and stdlib AST inspection treated source as data. Candidate import/compile/exec/collection/pytest, native API/child processes, GPU/models/services/network/DB/media and helper agents: zero.

## Original finding and subpath dispositions

| Original finding/subpath | Current source disposition |
|---|---|
| M05 pipe handover versus recovery | CLOSED_STATIC: B974-1007 and B1020-1029 share table state/lock; claimed pipe is not registered or delivered. |
| M05 successful CreateProcess transfer | CLOSED_STATIC for original birth-query/recovery schedule: B1510-1511 retains originals, B1571-1576 reserves both under B1053-1069 lock before commit/return; any claimed/GONE entry causes refusal and restoration B1581-1585. Recovery B1024 skips TRANSFER_PENDING. No unconditional claimed-handle forget/return remains on this path. |
| M05 failed-create direct cleanup | CLOSED_STATIC: B1676-1716 claims eligible originals, touches only claimed identities, requires exit confirmation for process close, independently handles thread and restores incomplete claims. Blocking primitives run after table decision, outside the global lock. |
| M07 exited process plus failed original HANDLE close | CLOSED_STATIC for callable original Popen HANDLE: B7033-7039 records failure, B6723-6734 retains original Popen; B6717-6718 remembers exit so same-owner retry skips terminate/wait and retries the HANDLE. |
| M07 stale snapshot resurrection | CLOSED_STATIC: B6907-6911 filters the current table, rather than assigning the stale keep list. An entry removed by aggregate.forget cannot be reinserted by a later stale snapshot item. |
| M07 partial channel ownership and order | CLOSED_STATIC: B5190-5191 registers channel before endpoint construction/start; B6662 precedes process helper; B6691 prevents raw file close whenever a channel was present on entry. B6669-6686 retains incomplete facts. |
| M07 StreamChannel interrupted/unproved start | CLOSED_STATIC for original join-RuntimeError path: B5485-5498 marks alive/unconfirmed and B5525-5542 returns without closing read endpoint. No inference of reader exit from RuntimeError remains there. Native scheduling itself remains NOT_PROVEN. |
| M07 no-channel failed raw streams | OPEN, M07-A below: references are now observable, but launch-tagged streams are never retried after the process is forgotten. |
| M08 initially expired/cancelled endpoint call | CLOSED_STATIC: B4580-4590 rejects before worker construction. |
| M08 readiness-to-submit admission | CLOSED_STATIC for cancellation/expiry already visible at final endpoint admission: B4672-4677 rechecks after readiness B4637 and before submit. Names/comments are not relied on as proof of later dispatch behavior. |
| M08 current request/round admission at worker dispatch | OPEN M08-A: generation carries call cancel and numeric deadline B4223, but run B4038-4065 does not reread worker._context cancel or dynamic deadline before primitive. |
| M08 default launch initial absolute expiry/cancel and preparation-to-Popen | CLOSED_STATIC for absolute deadline/cancel: B7229/7232/7240 check before directory, plan open and Popen. Published cleanup/stop remains OPEN M08-E. |
| M08 child formal main prebinding | CLOSED_STATIC: B7347-7348 fixes/binds actual deadline before B7353 constructs StreamChannel; channel/endpoints/workers receive original core.context. No early unbound reader window remains. |
| M08 parent endpoint API context edge | CLOSED_STATIC: B5026-5033 binds the endpoint-created API to the same original context. C1810-1811/C2425-2426 default launcher forwards it. Legacy injected 3-argument launcher remains explicit, not confused with default path. |
| M08 aggregate/table process wait dynamic context | CLOSED_STATIC for post-channel process helper: B6699-6703 reads launch original context after channel close and passes it to B7023/B6975-6984 before wait. B6858-6859 rereads table bound per aggregate. Normal BrokerProcess wait remains OPEN M08-B. |
| M08 startup start ownership/finally | Start now inside try/finally B5889-5917; normal success/ordinary/KI/SystemExit await exits call settle. Actual interrupted-start join remains OPEN M08-D. |
| M08 startup stale/floored settle budget | CLOSED_STATIC for normal started-owner settle: B5914 computes after await; B5945-5952 reads current original absolute/published cleanup, no positive floor. Startup await itself remains OPEN M08-C. |
| M08 NOT_FOUND retry and partial-write guards | CLOSED_STATIC: B4310-4324 current shared deadline and cropped pause; B4889-4925 current effective deadline before every partial write. Preserve these repairs. |
| M09 published generation error versus timeout | CLOSED_STATIC for original ordinary read-fault schedule: B4687-4689 checks immutable same-generation outcome before new timeout, B4698-4707 checks again after cancellation/join; B4749-4751 returns original object and B4726-4737 attaches parallel timeout metadata. Dynamic confirmation still required. |
| M09 error versus local close cancellation | CLOSED_STATIC: B4774-4784 inspects outcome before/after coordination, B4799-4818 keeps original primary with parallel cancellation metadata. _outcomes stores original B4110-4119; cancellation does not overwrite it. |
| M09 overflow/exact and one-over/history/two-stop guards | CLOSED_STATIC: B5297-5307/B5322-5326 use > thresholds, B5353-5356 sets sticky overflow/error, B5511-5512 and B6431-6433 propagate, B6370-6384 preserves first error. C1861-1873/C1993-2139 retains broker and UNKNOWN when reader error remains; actual two-stop schedule NOT_RUN. |
| m03 pending live eligibility | CLOSED_STATIC: B2895-2897 returns callable over original record; B2727-2730 stores same callable for pending and record; B2919-2922/B2302-2311 query it at close time. Original transient record-close failure can now be followed by eligible pending close. |
| M03 original exit-before-close safety | CLOSED_STATIC: B3428-3439 refuses unconfirmed record process close; pending uses same exit predicate. B1250-1264 and B1691-1702 retain API process HANDLE unless wait confirms exit. Terminate failure no longer skips independent wait for ordinary failure B3108-3138. Expired cleanup keeps control, with no new recovery budget B1121-1147. |
| M06 common close notification | CLOSED_STATIC: pending B2278-2281 and direct B2960-2964 reach B3281-3303, clearing original record/reader/retained resource; B3015-3018 prevents later reader double-close. Reader liveness checks and independent process finalizers remain. |

## M07-A — retained raw stream has no executable same-owner recovery (Major)

Locations B7248-7260, B6637-6742, B7015-7053, B6850-6911. This is a residual in the existing launch owner, not a request for new functionality.

Reachable trigger: launch_broker creates and registers the Popen at B7248-7249, then executable hashing raises KeyboardInterrupt/SystemExit at B7255-7260 before channel construction. Existing release_retained_launches B6923-6942 finds the real retained aggregate. In its first release, let terminate/wait confirm exit and the original HANDLE close succeed, while stdout.close raises an ordinary transient error. No channel exists, so close_pipes=True (B6691). B7047-7051 returns the failed original stream; B6712-6716 registers it in custody with launch=self, while B6724-6729 clears self.process and forgets Popen because exit and HANDLE are complete.

Expected: same-owner recovery retries that original failed stdout stream, does not repeat successful process/HANDLE work, and does not drop its aggregate while it owns an unresolved raw resource. Actual: _LaunchAggregate.retain only recognizes channel/endpoint/worker (B6586-6593); raw stdout is not added to an aggregate retry collection. The next aggregate.release sees process=None and channel=None and reports retained=[] (B6658/B6687/B6735). Table.release then removes aggregate from the current table, but encounters stdout with a non-None launch and unconditionally skips it at B6871-6876. Later releases keep skipping that original stream forever; the retained original reference is observable but has no working cleanup route. This is distinct from stale snapshot resurrection, which is repaired. The raw error summary is not the problem: the missing retry/owner relationship is.

Preserve the repaired original HANDLE retention, exit-memory retry, no-channel versus partial-channel separation, snapshot filtering and RuntimeError UNKNOWN. Repair only the remaining raw-stream ownership/retry path and retain its original references until a confirmed close.

## M08 — current context admission and original-deadline waits remain incomplete (Major)

The following are subpaths of one original Major, not five new findings. All triggers use existing entry points and state transitions. They describe conditional production behavior, not executed native experiments.

**M08-A: worker dispatch reads a captured request deadline and omits current round cancellation.** B4675-4677 supplies effective numeric deadline; B4223 stores (call cancel, deadline). Worker owns self._context (B3980), but B4038-4065 checks only self._cancelled, call cancel and that captured numeric deadline, then B4073 executes endpoint._read_block -> B4874 read_stream. Pause after submit and before worker dispatch, with both caller and worker paused; publish context.request_cancel(), or shorten original context absolute deadline / publish cleanup so it has expired; resume worker first. Call/channel cancel remains unset and the old numeric deadline is future, so the original read primitive runs. Expected: worker admission uses the same generation's current original context before IN_IO, zero primitive calls when it is already cancelled/expired at that decision. For a round cancellation after endpoint admission, the promised bounded cancellation is also absent from _await: B4679-4681 checks the call flag, not context.cancel. This is not a demand to undo an OS call that already began. Endpoint post-readiness rejection is genuinely repaired and stays closed.

**M08-B: normal BrokerProcess.close uses an earlier copied bound for later process waits.** C2089-2096 -> B6254 copies _cleanup_deadline once; channel close at B6298/B6306 can consume time and publish/tighten the original context. Immediately before _process.wait, B6322 and retry B6334 use value minus now without rereading _cleanup_deadline/current context. Trigger: original absolute bound remains long, channel close is in progress, original context publishes a shorter cleanup before channel returns, process remains alive. Expected: next process wait uses the remaining new original cleanup. Actual: it receives the remaining old lease. This is the normal Session -> BrokerProcess path, independently of the aggregate helper's now-repaired B7023 dynamic read. The initial _cleanup_deadline helper B6455-6462 does inspect context, but it is called too early for the later wait.

**M08-C: startup await keeps its original numeric deadline and fixed poll waits exceed remaining time.** _StartupOwner B5595 stores a number; await_result B5649 only compares against that copy and B5653 always queue.get(timeout=POLL_SLICE_SECONDS). While real startup action is blocked, shorten core.context absolute deadline or publish earlier cleanup. The await still uses the old number until an outcome/old deadline, although normal finally's settle budget correctly uses the new context. Even without dynamic tightening, with 1ms remaining and an empty result queue, B5653 can request 50ms (constant B89); Windows endpoint B4709 similarly calls wait_done with 50ms after checking a smaller remaining value. Channel _drain B5309-5311 checks its deadline then may queue.put for 0.5s, and BrokerLoop B6032 floors the transport read to 0.01s when less remains. Expected: each next wait is cropped to current remaining original deadline, with no positive floor beyond it; actual wait arguments exceed it. This is a source argument-bound defect; scheduler overshoot and physical timing are not asserted. Fixed idle service polling is not independently counted.

**M08-D: interrupted start enters finally, but settle does not attempt a real join.** B5618 invokes underlying Thread.start; B5619 sets _started only afterwards. KeyboardInterrupt/SystemExit between these lines can occur after the real thread has started and even after ident is known. _run_startup finally B5917 invokes settle, but B5679-5682 returns False solely because _started remains False, without calling B5684 join. Expected: attempt a bounded real join for an established started thread; preserve UNKNOWN for genuinely unproved start/RuntimeError, retain owner if incomplete, and preserve original interruption. Actual: no join even when current original thread facts can establish startup; the boolean remains False for later settle calls. Ownership and primary exception are retained, so this is not a false release allegation. The original all-exit real-join obligation is still incomplete. Normal await-result error finally and zero/fresh settle-budget repairs remain closed.

**M08-E: parent launch ignores already-published cleanup/stop.** C1874-1877 sets stopping and publishes the original cleanup while start may still be in the launcher. _check_launch_budget B7173-7177 checks cancel/unknown and absolute_deadline only. Pause preparation before B7240, let public Session.stop publish cleanup while broker has not been returned, let that cleanup expire while absolute lease remains future and context.cancel remains unset, then resume. B7240 admits Popen at B7241 even after the original published cleanup expired. Expected: next launch effect consults the current original context minimum; actual: original absolute/cancel-only checks omit cleanup. The repaired initial-expired/cancelled call and preparation-expired absolute lease subpaths stay closed. No stronger atomic OS-undo guarantee is requested.

## Complete 72-obligation disposition

Each row is a static subcondition, with no inherited dynamic PASS. Every row's dynamic status is NOT_RUN and native status NOT_PROVEN. OPEN rows cross-reference the two counted Majors, and UNCERTAIN rows preserve excluded external/test/native obligations rather than inventing evidence.

| Atom | Status | Current bound-source evidence / limit |
|---|---|---|
| N03-R01 | CLOSED_STATIC | B1510-1511,1564-1609,1673-1716 retain original creation handles/failures and refuse claimed or gone entries. |
| N03-R02 | CLOSED_STATIC | B1521-1563,1588-1609 independent attribute/NUL/birth/process cleanup and primary association. |
| N03-R03 | CLOSED_STATIC | B1354-1400 validates header/allocated/returned/count equality/cap before inline PID reads. |
| N03-R04 | CLOSED_STATIC | B2584-2601,2944-2964,3463-3478 retains original job on failed close. |
| N03-R05 | CLOSED_STATIC | B3180-3218 independent stop steps catch failures, continue finalizers and preserve first raised object. |
| N03-R06 | OPEN | C1696-1774 retains parent startup guard; B6699-6734/B6850-6911 raw-stream recovery is stranded (M07-A). |
| N03-R07 | OPEN | B2467-2484,2669-2796 Core checks; B5618-5619/5679-5684 interrupted start bypasses real join (M08-D). |
| N03-R08 | OPEN | B6254/6322/6334 stale normal-close deadline and B5649-5653 fixed startup await remain M08-B/C. |
| N03-R09 | CLOSED_STATIC | B4903-4925 loops partial writes; B4955-4998 retains unresolved workers/file and retries HANDLE close. |
| N03-R10 | OPEN | B4181-4241 bounded generation queue; B4038-4073 ignores live context at dispatch (M08-A). |
| N03-R11 | CLOSED_STATIC | C1111-1152 serializes writes/stop barrier; C1274-1312 callback failures; C1416-1462 atomic UNKNOWN. |
| N03-R12 | CLOSED_STATIC | C1169-1176/C1253-1271 common frame budget lock; B5811-5812/B6064-6069 terminal reserved=0. |
| N03-R13 | CLOSED_STATIC | B5283-5337 exact/one-over frame, bounded no-newline tail, partial EOF; wait checks in queue loop. |
| N03-R14 | CLOSED_STATIC | C2112-2139 strict close facts/error retention; B6297-6306/B4955-4998 incomplete-resource retry. |
| N03-R15 | CLOSED_STATIC | C1808-1827 structured launcher errors; B7204-7209 platform/plan/nonce refusal before files. |
| N03-R16 | UNCERTAIN | External tool pins, complete lifecycle and original tests excluded; two-source compatibility only. |
| N05-R01 | CLOSED_STATIC | B1454/1531-1537 retains original NUL on failed close; B1187-1292 recovery table remains available. |
| N05-R02 | CLOSED_STATIC | B1521-1563/1676-1718 independent cleanup and cancellation association; M08 wait residual separate. |
| N05-R03 | CLOSED_STATIC | B1817-1818/1835-1864 records both pipe originals and independently closes ends on inheritance failure. |
| N05-R04 | CLOSED_STATIC | B2206-2285/3421-3461 independent process closes and cancellation; B2727-2730 live eligibility repair. |
| N05-R05 | CLOSED_STATIC | B3329-3344/3346-3387 independent waits/exit queries and KI/SystemExit after later records. |
| N05-R06 | UNCERTAIN | B2866-2872 preregisters readers; B3024-3039 ident-less interrupted Core reader start remains timing assumption, no native proof. |
| N05-R07 | UNCERTAIN | C1376-1414/C1569-1621 background start records/barrier inspected; late native start timing excluded. |
| N05-R08 | UNCERTAIN | C1386-1408 retains original background record but ident-less interrupted start requires dynamic proof. |
| N05-R09 | CLOSED_STATIC | C1481-1511 retains original closer and resets latch on failure; C2268-2276 RuntimeError remains UNKNOWN. |
| N05-R10 | OPEN | B6724-6729 retains failed HANDLE correctly; raw stream original at B6712-6716 has no same-owner retry (M07-A). |
| N05-R11 | OPEN | B7229-7240 absolute/cancel launch checks repaired; dispatch context and published-cleanup launch gap M08-A/E. |
| N05-R12 | CLOSED_STATIC | B194-203/C267-277 publish one cleanup under lock; C1653-1663 reuses it without lease reset. |
| N05-R13 | OPEN | B3043-3051 recomputes Core joins; B6254/6322/6334 and B5649-5653 remain M08-B/C. |
| N05-R14 | CLOSED_STATIC | B4515-4527 live endpoint minimum; B4310-4324 NOT_FOUND rereads context and crops retry pause. Worker dispatch caveat M08-A. |
| N05-R15 | OPEN | B4038-4065 generation condition/guard checks call cancel and copied deadline only; live context omitted (M08-A). |
| N05-R16 | CLOSED_STATIC | C1424-1429/C1457-1462 shared state lock keeps UNKNOWN sticky against late state apply. |
| N05-R17 | CLOSED_STATIC | C1169-1176/C1265-1267 atomic shared count; C1134-1151 sequence/write serialized. |
| N05-R18 | CLOSED_STATIC | C1170-1172/C1265-1267 terminal reserve=0; B5811/B6064-6069 same combined terminal budget. |
| N05-R19 | CLOSED_STATIC | C1861-1873/C1993-2064 actual public repeated stop uses same cleanup/event generation and incomplete recovery. |
| N05-R20 | CLOSED_STATIC | B4955-4998 retries incomplete worker/HANDLE before file-closed early return; B3848-3869 POSIX idempotent facts. |
| N05-R21 | CLOSED_STATIC | B6318-6319 derives stdin/stdout from channel facts; normal BrokerProcess does not directly close raw pipe files. |
| N05-R22 | CLOSED_STATIC | C2112-2139 requires True/zero, reader completion, no reader error; no benign fallback from close return alone. |
| N05-R23 | CLOSED_STATIC | C2172-2216 follows current event/generation; C2246-2278 actual closer join/UNKNOWN on unresolved start. |
| N05-R24 | UNCERTAIN | External pins and original node identities/order not read; separate batch189 and native outcomes not reviewed. |
| N07-R01 | CLOSED_STATIC | B1164-1184/1250-1264/1691-1702 requires actual exit confirmation before process HANDLE close; B3428-3439 same Core guard. |
| N07-R02 | CLOSED_STATIC | B1121-1147/1250-1286 API recovery retains unconfirmed control and restores claims without fresh recovery budget. |
| N07-R03 | CLOSED_STATIC | B974-1007/1020-1029 shared pipe claim; process return/direct cleanup now uses B1571-1585/B1676-1716. |
| N07-R04 | CLOSED_STATIC | B1817-1864 independent pipe-end cleanup with original retention/cancellation association. |
| N07-R05 | CLOSED_STATIC | B3043-3083 rereads reader alive after wait/join failure; B3230-3241 protects actual owner during pending close. |
| N07-R06 | CLOSED_STATIC | B3329-3344/3361-3387 propagates KI/SystemExit after independent records. |
| N07-R07 | CLOSED_STATIC | B2944-2964/B3257-3303 common notification clears reader.handle, pending/record/retained once; B3015-3018 prevents repeat. |
| N07-R08 | UNCERTAIN | B4620-4637 preregistration and B4391-4398 join RuntimeError=false preserved; actual startup scheduling excluded. |
| N07-R09 | OPEN | B7248-7249 pre-hash ownership/B5190-5202 partial channel registration repaired; raw-stream retry M07-A remains. |
| N07-R10 | CLOSED_STATIC | C1489-1491 registers original closer before start; C2269-2276 does not infer exit from RuntimeError. |
| N07-R11 | CLOSED_STATIC | B4168-4175 worker cancellation condition; B4302-4324 current completion/NOT_FOUND retry remains bounded. |
| N07-R12 | CLOSED_STATIC | B4889-4900/B4915-4925 current deadline minimum before each partial write, no fixed lease for next segment. |
| N07-R13 | OPEN | B7347-7354 child prebinding and B7229-7240 launch absolute/cancel fixed; live dispatch and cleanup-launch gaps M08-A/E remain. |
| N07-R14 | OPEN | B5889-5917 includes start/finally and recomputes join budget; B5679-5684 still skips actual join after start interruption, await M08-C/D. |
| N07-R15 | CLOSED_STATIC | B6297-6306/B6396-6405 incomplete channel retries; C1993-2139 same-owner public stop retains errors/facts. |
| N07-R16 | CLOSED_STATIC | B4955-4998 recomputes live/HANDLE/retained before _closed early return and retries incomplete HANDLE. |
| N07-R17 | CLOSED_STATIC | C2053-2064 fresh close event/generation; C2198-2211 follows current in-progress generation. |
| N07-R18 | CLOSED_STATIC | C1867-1872/C1907-1921 public stop awaits; C2246-2278 actual closer joins and self-join avoidance. |
| N10-R01 | CLOSED_STATIC | B2727-2730 stores shared callable B2895-2897; B2919-2922 record and B2302-2311 pending ask original current exit; no close before exit B3428-3439. |
| N10-R02 | CLOSED_STATIC | B974-1007/B1020-1029 pipe handover/recovery guarded; B1571-1585 process transfer and B1676-1716 failed-create claims now participate. |
| N10-R03 | CLOSED_STATIC | B2278-2281/B2944-2964/B3281-3303 common close notification; reader original cleared and B3015 prevents repeat. |
| N10-R04 | OPEN | B5190-5202 partial owner/B5485-5542 unknown join protection repaired; no-channel failed raw stream recovery M07-A remains. |
| N10-R05 | OPEN | B6724-6734 HANDLE failure retention/retry and B6907-6911 no-resurrection repaired; raw streams orphaned from executable recovery M07-A. |
| N10-R06 | CLOSED_STATIC | B4580-4590 rejects initially cancelled/expired before B4850; B4672-4677 rechecks after readiness and before submit. Dispatch live-context residual separately M08-A. |
| N10-R07 | OPEN | C1810-1811/C2425-2426/B5026-5033 context edges, B7347-7354 prebinding fixed; M08-A/B/E current context use incomplete. |
| N10-R08 | OPEN | B4310-4324 NOT_FOUND and B6699-6703/B7023 current aggregate process wait fixed; normal BrokerProcess stale value B6322/B6334 remains M08-B. |
| N10-R09 | OPEN | B5889-5917 finally includes start and live settle budget; B5618-5619/B5679-5684 real join skipped on interrupted start; B5649-5653 static await remains M08-C/D. |
| N10-R10 | CLOSED_STATIC | B4687-4707 inspects same generation error before timeout and after coordination; B4749-4751 returns same original; B4774-4784 preserves cancellation ordering. |
| N10-R11 | CLOSED_STATIC | B5297-5307/B5322-5326/B5353-5356 overflow sticky; B5511-5512/B6431-6433 propagate, B6370-6384 preserve first error; C2126 retains broker. |
| N10-R12 | UNCERTAIN | Test fixture causality and actual independent primitive-event schedules excluded from static two-blob scope. |
| N10-R13 | UNCERTAIN | JSON phase artifacts/test negatives excluded; M09 published fault then timeout before consumption still needs directed dynamic coverage. |
| N10-R14 | UNCERTAIN | Exact old175/new14 node identities/order, tooling pins, assertions/salvage and batch189 results not inspected or claimed. |

## Remaining dynamic coverage and limits

No batch189 outcome is signed or inferred. The coordinator's separate bounded dynamic review must establish test identity/order (189 unchanged nodes), actual production primitive reachability, assertion reconciliations, all ten phase documents/NOT_RUN causes, absence of skips and distinction between product cleanup and test-owner salvage. Source comments, method names, constants, an empty helper report, mocked booleans or HTTP200 cannot establish any of those facts.

In particular, M09 needs the exact schedule **genuine original read fault published for the current generation, then timeout before endpoint consumption**, both successful and failed cancellation/join coordination, verifying original object identity in endpoint selection, primary code through channel/BrokerProcess history and two actual Session.stop calls preserving original first error/UNKNOWN. It is CLOSED_STATIC here because B4687-4707 now selects that original object, not because such a test was observed. Close-token-before-consumption and exact/one-over overflow are separate schedules; they cannot substitute for timeout-after-publication coverage.

Other necessary dynamic evidence remains process/thread transfer versus recovery under actual retained entries, direct failed-create exclusivity, unconfirmed-exit retention versus confirmed-exit close, transient original HANDLE retry without repeated successful release, failed raw-stream same-owner recovery, partial start unknown versus real join, cancellation/expiry between readiness/final endpoint admission/worker dispatch, live deadline tightening before every next wait, child prebinding before transport construction, startup success/error/KI/SystemExit with real thread tails and start-success-then-interruption. Runtime/native cancellation, real HANDLE reuse and OS exit/convergence remain NOT_PROVEN. These are existing frozen obligations, not added product features or test-denominator changes.

Preserved compatibility inspected independently: C469-481 fullmatch/traversal/device directory guards (M01); C498-574 frozen role view/deep sealed copy (m01); B385-519 fixed width/pointer types and B545-614 explicit primitive prototypes (M02); B1354-1400 full Job header/count/length/cap guards (M04); C1065-1069 nonce generation/refusal plus B7204-7209/B7316-7319 refusal (M11). M10 B1988-2020 role_command remains explicit; actual external tool pins and old node lists are UNCERTAIN, excluded from the two-source snapshot. This report does not assert native execution from any guard or false-valued evidence constant.

All writes are new under production-review-01/review-result; no historical report, candidate source, control, ledger, runtime output or manifest changed. No agents were started and no runtime resources were created. The read-only assigned review slot is settled by one worker_done; no keep-open or polling loop is used.

## Required handoff fields

Full V0–V3 control outline: V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1 0/4; V1-M1 0/3; R2 0/4; R3 0/4; R4 0/4; R5a 0/4; R5b 0/4; R5c 0/4. V0-S0 historical NO_GO, V0-S1 V0-Min scope, R0 only partial prerequisite, R1a single-image scope, V0-S2 old human signoff pending; current Stage R1, unified early slice independently signed separately. V1-M1 belongs to V1; R3/R4 to V2; R5a/b/c to V3. No count is increased by this source review.

Current coordinate: V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION, RUNNING. This batch: exact bound two-source static audit, original findings/guards and all72 atom dispositions, actual F0/M2/m0. Last passed gate: control navigates to 621b1bf unified-media live15 scope only; it was not revalidated here. Current blocking gate: S3_P4_N1_CORRECTION11_FROZEN189_VALIDATION_AND_SOURCE_REVIEW plus M07/M08 residuals. Global route position: outline above, full R1/V1 pending. Remaining work: coordinator repairs/dispositions, separate finite dynamic evidence review, later independent acceptance and required human/product gates. Next owner: coordinator/gate owner. Required authorization: static review already supplied; no new runtime authority granted. Evidence directory: this review-result. Exact stop reason: assigned static review completed with CHANGES_REQUIRED, then one worker_done and idle. Implementation, machine acceptance, final independent acceptance and human signoff remain separate; no Stage PASS is issued.
