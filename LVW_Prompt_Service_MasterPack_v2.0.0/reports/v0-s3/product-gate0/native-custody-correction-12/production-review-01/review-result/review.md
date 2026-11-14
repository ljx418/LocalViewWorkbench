# 025146b production source review — correction12

**CHANGES_REQUIRED — Fatal 0 / Major 2 / Minor 0.** The two findings remain M07 and M08; their residual paths are not counted as new Majors. M07-A is partially repaired but OPEN. M08-A, M08-B and M08-D are CLOSED_STATIC; M08-C and M08-E are partially repaired but OPEN. Previously closed M05, M09, m03, M06 and M03 exit-before-close safety remain CLOSED_STATIC within the conditions below. The 72 original obligations are individually dispositioned below and in receipt.json: 53 CLOSED_STATIC, 10 OPEN, 9 UNCERTAIN.

Candidate: `025146bc41c914b870ffe991c2e0b6dd3a49c160`. Production only; the separate test-only preflight revision, test sources/results and live implementation edits were not inspected. No Stage PASS, final independent acceptance, N2 admission or native proof follows from this review. Dynamic: NOT_RUN. Native: NOT_PROVEN.

B/C mean physical one-based lines of the two immutable bound blobs. Independently recomputed B SHA256 `5527734702c83858eb147d3752cbc00224d62848ca80932082e22fe1345674f6`, 361424 bytes, 7692 lines; C SHA256 `9b7e68969f2cbf8763664ba57fa3e5ee4133a0beed076a64f037e6344f336d8d`, 112727 bytes, 2426 lines. Both match source-binding.json. That file declares hashes, not expected line counts; the counts here were measured from the raw blobs and checked against the numbered snapshots. Git SHA-to-blob provenance remains the supplied binding, rather than an independently reconstructed checkout.

Read inputs: root AGENTS.md, README.md, .agent-governance/README.md, plans/execution-control.json and docs24; correction12 contract/scope/decision; correction11 independent review.md and receipt.json; correction12 source binding and both exact blobs. The prior review supplied atom identities and original triggers, not accepted conclusions. Current control was used for coordinates/outline only; embedded historical implementation references were not followed. Static text comparison, tokenization, line numbering, JSON processing and hashing only. No candidate import, compile, exec, collection or pytest; no native API or candidate OS process, GPU/model/service/network/DB/media/ledger/counter activity; no other agents. Shell/Python invocations processed source as text and did not load candidate code. One read command had an invalid working-directory typo and failed before running; it was corrected. No approval refusal or 429 occurred.

## Atom dispositions

| Atom | Disposition and exact evidence |
|---|---|
| M07-A ordinary no-channel failed raw stream | CLOSED_STATIC for original single-failure trigger: B6944-6949 puts the original reference in raw_streams and custody; B6888 snapshots it on the next release, B6972/B7025-7044 actually retry and forget after success. Once process/HANDLE succeeded, B6957-6962 clears process, so that ordinary next retry does not repeat process work. |
| M07-A retry when process remains / interruption / current deadline | OPEN: the residual triggers below repeat confirmed operations and/or use stale/absent raw-close admission. |
| M08-A current context at actual dispatch | CLOSED_STATIC: B4043-4109 checks current original context.cancel and effective minimum under the same generation condition before IN_IO/action, preserving source identity for refusal B4062-4064. B4732-4741 notices context cancellation while awaiting; existing initial B4616-4626 and post-readiness B4725-4730 guards remain. Cancellation after admission is bounded coordination, not promised atomic undo. |
| M08-B every normal process wait | CLOSED_STATIC: Session C2089-2096 reaches BrokerProcess; B6507-6508 and B6523-6524 reread _cleanup_deadline immediately before both waits. B6642-6657 includes original current absolute/cleanup and finite facade fallback. Previous successful process/handle facts are retained B6461-6469/B6501/B6529. |
| M08-C startup, endpoint and drain waits | CLOSED_STATIC for these specific repaired calls: B5736-5759/B5812-5822 use original current minimum; endpoint B4732/B4769 with B4636-4651 crops completion wait; channel B5370-5371/B5466-5478 crops put. No positive floor in these repaired formulas. |
| M08-C all next waits/current deadlines | OPEN: BrokerLoop read still ignores current context minimum; millisecond wait converters still force a positive 1ms floor. See residual triggers and inventory. |
| M08-D start-success-then-interrupt join | CLOSED_STATIC: B5705-5710 preserves original raised object, B5714-5734 consults actual original thread facts; B5850-5861 attempts bounded real join even when start did not return, retains UNKNOWN on unproved start/RuntimeError/alive. B6061-6100 owns before start and settles in finally with B6118-6125 current remaining; failed settle retains exact owner in context. Later same-owner settle reevaluates facts and can return true after exit. Actual scheduling/join execution remains NOT_RUN. |
| M08-E public stop before Popen | CLOSED_STATIC for original pre-Popen schedule: C1874-1877 publishes stop/cleanup; B7491-7500 rejects stop/cancel/unknown/current effective expiry; B7552/B7555/B7563 call it before directory, plan and Popen. |
| M08-E next hash/channel effects | OPEN: there is no subsequent check after admitted Popen returns or after hash preparation; see residual trigger. |

## M07 — original raw recovery is reachable, but successful work can repeat and raw-close admission is incomplete (Major)

These are residuals in the existing M07-A owner, not new feature requirements.

**M07-A.1 — process-retained retry has two routes to the same original stream.** Locations B6888, B6918-6973, B7016-7044 and B7328-7364. Trigger: pre-channel launch failure leaves the original Popen aggregate retained; first release confirms process exit but its original HANDLE close fails, stdout.close also fails, while stdin.close succeeds. The aggregate remembers exit, retains process for HANDLE retry, and adds stdout to raw_streams. On the second release, pending_raw contains stdout; process is still present, so close_pipes is true B6922. `_release_launch_process` skips terminate/wait using exit memory but enumerates *all* original process streams again B7351-7357. It calls stdin.close again despite its earlier success, and can now successfully close stdout. The aggregate then invokes `_release_raw_streams(pending_raw,...)`, which closes that same stdout again B7026, without checking whether the process helper just confirmed it. If this latter close fails, the aggregate retains a stream whose successful close just occurred. Expected: only unresolved original identities have one executable retry owner, and each confirmed close is recorded before the next release step; successful stream work never repeats. Actual: the helper and the new raw retry list both act on the same original reference, and the helper has no per-stream successful-close memory. This does not allege a second native HANDLE close in this ordinary HANDLE-failure trigger; the first HANDLE close failed. The already-fixed process exit memory and channel-first ordering remain valid.

**M07-A.2 — raw close interruption discards already-confirmed process facts.** Locations B6923-6957 and B7328-7364. Trigger: no-channel release confirms exit, successfully closes the original HANDLE, then original stdout.close raises KeyboardInterrupt/SystemExit. The helper catches only Exception, so it never returns its exited/handle/stream result. Aggregate B6935-6936 saves the original interruption but retains the default outcome with exited=False and no retained_streams. Process remains retained and process_exit_confirmed remains false; later same-owner recovery calls terminate/wait and HANDLE.Close again and re-closes earlier successful raw streams. Expected: original interruption propagates after independently recorded successful releases, and subsequent recovery performs only unresolved work. Actual: original interruption object is preserved, but confirmed work is forgotten and later operations repeat. No claim is made about the behavior of an idempotent OS/Popen Close implementation; the duplicate method invocations and lost owner facts are the source defect. The original process object remains reachable, so this is not the old orphan-reference allegation.

**M07-A.3 — expiry/current-bound checks do not cover each actual raw close.** Locations B6930-6934/B7351-7357 and B7016-7026. Trigger A: first no-channel release begins with original cleanup already expired, or process coordination consumes the remaining budget. `_release_budget` can yield zero for process.wait, but the subsequent original raw closes are unconditional. Trigger B: there are two pending original raw streams, the retry computes value once at B7016, first close runs, and original context absolute/cleanup is tightened before the second close decision. B7019 compares against the old value and admits the second close after the current original bound. Expected: before each next raw close, reread the effective original minimum and retain/refuse at expiry; no new cleanup lease. Actual: initial helper has no raw-close bound check and new retry loop snapshots the minimum outside the loop. These are argument/admission defects; synchronous close preemption or scheduler precision is not demanded. Failure/KI in the *new* raw retry loop itself does retain the original raw entry and propagates the original interruption at B6976-6980; that repaired subpath stays closed.

The table's stale-snapshot repair remains CLOSED_STATIC: B7180-7186 checks current membership and B7218-7222 rebuilds only from current entries. The ordinary repaired raw success B7041-7043 removes owner and child entries before the stale snapshot is processed. No stale-table resurrection is found there. Partial/live channel protection also remains closed: channel registers before endpoints B5250-5262; aggregate coordinates it first B6890-6917; close_pipes uses the channel present on entry B6922; B7008 protects pending raws if a channel remains. The open issue is the no-channel cross-product above.

## M08 — remaining current-deadline waits and later launch effects (Major)

**M08-C.1 — BrokerLoop transport read still uses cached lease, and StreamChannel.read passes it through.** Locations B5914, B5954, B6197-6215 and B5480-5485. Trigger: while ordinary loop is active, shorten the original core.context.absolute_deadline or publish earlier cleanup; current original remaining is 1ms or already zero, but `_deadline_mono` still has a long lease. At the next loop/read decision, B6201 and B6210 only inspect that cached lease; B6213 supplies min(POLL_SECONDS,cached remaining) and B5485 directly requests queue.get with it. Expected: next transport/queue read argument is capped by the current original absolute/published cleanup minimum, with immediate/nonblocking refusal at expiry. Actual: the former 10ms positive floor is removed, but the next read still requests the old poll/lease bound. The Windows primitive endpoint's current context guard does not repair this distinct supervisor queue wait. This is a reachable original-context tightening schedule using the existing context API, not a demand to shorten an already admitted blocking call.

The same supervisor-read omission is reachable in the default parent chain: C815 -> B6395-6396 -> B5485 supplies the fixed CHANNEL_POLL_SECONDS without consulting the current original bound. Pause the pump before its next read, shorten original context while its own stop flag is still unset (public stop publishes context before background coordination), then resume with less than one poll remaining: the requested queue wait is still the full poll. Expected is the current effective minimum; actual is unchanged pass-through. The raw Windows endpoint guard does not crop this queue argument. Parent reply waiting also has a stale bound: C1236-1238 captures a numeric deadline, C1249 passes it to take, and C873-874 directly waits on it. Publish earlier cleanup before that next event.wait (after deadline construction); it still requests the old remainder. Expected is to reread original effective minimum before the next wait. This is not a claim that an already admitted event wait must be atomically shortened. These are additional locations of M08-C.1, not new findings.

**M08-C.2 — sub-millisecond Windows wait arguments still round up.** Locations B843-856, B1134-1152, B1164-1187 and B3394-3399/B3361-3367. Trigger: a bound API/Core process wait is about to be requested with 0.2ms of original budget remaining. The converters return max(1,int(remaining*1000)), hence request 1ms. Expected under correction12's all-next-wait/no-positive-floor rule: a requested millisecond wait may not exceed remaining; a remainder below the representable positive unit can be refused/nonblocking. Actual: the existing positive 1ms floor exceeds remaining. Exit-before-HANDLE-close remains protected; this finding is solely the requested wait bound, not false exit or native timing. No numeric threshold relaxation is proposed.

**M08-E — public stop/expiry after admitted Popen does not gate the next hash/channel effects.** Locations C1874-1877, B7563-7575, B7585-7604. Trigger: actual Popen was admitted under a valid original context and is in flight; public Session.stop publishes stop/cleanup while no broker has been returned, and the launch resumes after that bound expires while absolute lease remains future. The admitted Popen itself cannot be undone atomically; expected behavior is refusal before the *next* distinct launch effect. Actual: launcher binds/retains Popen and immediately performs executable.read_bytes/hash B7575 without `_check_launch_budget`; after hash, channel_factory constructs StreamChannel B7594-7595 (allocates endpoints/starts its reader B5253-5262) and adopts it without any further launch-budget check. Similarly, stop/expiry published during hash is not checked before channel creation. The repaired pre-Popen check cannot cover either later admission. Retained original Popen ownership B7571-7572 is good and must be preserved while refusing later work. This residual does not require undo of an admitted OS call or forbid safe custody registration/cleanup.

## Wait inventory and clock scope

This inventory covers the changed waits and their directly reached owner/primitive wrappers, plus remaining wait sites encountered in the two-source production chain. Formulas are source facts, not dynamic requested-value measurements. All clocks on the default Windows path use time.monotonic; BrokerLoop binds core clock before run B6136-6142, main prebinds original deadline before channel creation B7670-7678, and context propagates from Session C1810-1811/C2425-2426. Facade clock injections must share that domain; `_release_budget` B7295 explicitly uses time.monotonic, so synthetic-clock compatibility is not claimed as native proof.

| Wait/site | Current requested argument / disposition |
|---|---|
| StartupOwner result queue B5822 | min(0.05,current absolute, published cleanup, owner/call bound minus clock), clamped zero; original context cancel checked. Repaired. |
| StartupOwner real join B5856 / caller B6087-6090 | current settle min(original absolute/cleanup remaining, STARTUP_SETTLE_SECONDS), no positive floor; caller always finally; actual started facts checked. Repaired. Direct later callers of settle must supply current remaining; no automatic recovery run is claimed. |
| Windows endpoint wait_ready B4690 / worker B4215 | endpoint current _remaining(deadline), event wrapper max(0,seconds); final admission after readiness preserved. |
| Windows endpoint wait_done B4769 / B4276-4277 | _wait_slice over current per-iteration effective minimum; condition wrapper preserves cropped nonnegative value. Repaired former fixed 50ms. |
| Windows worker request queue get B4021 | fixed idle 0.1s service poll; dispatch subsequently enforces live context. Not used as proof of current request completion or native deadline convergence. |
| Windows worker submit queue put B4261 | fixed 0.05s bounded submission, not newly cropped. Under intended one in-flight request/one slot path it is immediate; if queue is full it can request beyond remaining. Full-queue/adversarial concurrency reachability is UNCERTAIN in this static review; no separate new Major is counted. |
| Windows worker NOT_FOUND retry pause B4346-4360 | rereads original context each retry and min(0.05,current remaining,fixed initial cap), refuses zero. Preserved. |
| Windows worker joins B4428; endpoint B4886/B5020 | endpoint computes current _remaining for each bounded join, no positive floor; RuntimeError retains UNKNOWN. |
| Channel drain queue put B5371 / B5475-5478 | min(0.5,current remaining) or finite 0.5 without context; preceding _check_wait; repaired. |
| Channel supervisor queue read B5485 / loop transport B6215 | requested timeout passes through; loop uses cached _deadline_mono only. OPEN M08-C.1. |
| Channel reader join B5557-5561 | recomputes _remaining after writer close; original live context; finite fallback only when no bound. Preserved. |
| Normal BrokerProcess waits B6508/B6524 | fresh _cleanup_deadline before EACH actual wait; max(0,current-clock). Repaired M08-B. |
| Aggregate/table process wait B7334-7336 | _release_budget includes original current context immediately before wait; aggregate after channel and table per-launch minimum preserved. Raw close admissions are separately OPEN M07-A.3. |
| Core reader finished wait/join B3048-3056 | rereads remaining_cleanup before each wait/join, min(READER_JOIN_SECONDS,remaining). Preserved. |
| API primitive waits B843-856/B1152/B1180; Core waits B3361-3367/B3394-3399 | dynamic bounds and zero-expired refusal preserved, but positive 1ms floor remains OPEN M08-C.2. |
| Parent pump supervisor read C815 -> B6396/B5485 | fixed CHANNEL_POLL_SECONDS passes through; current bound not cropped. OPEN M08-C.1. |
| Parent reply event C1236-1249/C873-874 | numeric call deadline remainder, no original context reread at actual next wait. OPEN M08-C.1 under tightening-before-wait schedule. |
| Parent heartbeat idle event C1337 | fixed HEARTBEAT_SLICE_SECONDS service poll, explicit stop event wakes it; not credited as original-deadline convergence. |
| Parent background barrier/join C1572-1617 | remaining shared cleanup argument for barrier/heartbeat/pump; no new cleanup lease. Native interrupted-start uncertainty retained. |
| Parent close-event/closer C2190-2198/C2260-2269 | original published cleanup remaining, min(current remainder,0.05), expiry UNKNOWN and current generation follow; preserved. |
| POSIX poll B3803-3804/B3825-3826 | fixed 0.05 after deadline check; alternate transport outside default Windows native-launch path. Not credited as current-context native proof; no new POSIX feature demand. |

All other primitive calls (ReadFile/WriteFile/CancelSynchronousIo/close) remain synchronous operations owned by the real worker/resource. This report bounds the next admitted call/wait arguments; it does not assert preemption or actual scheduler durations. Dynamic wait-event recordings and interrupted-start tails are NOT_RUN.

## Preserved original safety findings

M05 CLOSED_STATIC: B979-1012 handover and B1025-1034 recovery share table/claim state; B1058-1074/B1576-1590 successful process transfer refuses claimed/GONE originals and restores incomplete reservations; B1681-1721 direct failed-create cleanup only touches claimed identities outside the table lock and releases incomplete claims. Independent pipe cleanup/creation HANDLE retention remain B1822-1869/B1515-1516. No new issue in those exact transfer/direct-cleanup schedules.

M03 exit safety CLOSED_STATIC: B1164-1187/B1255-1269/B1696-1707 require confirmed exit before API process close; B3433-3445 protects Core original process control HANDLE. Ordinary terminate failure still reaches independent wait B3112-3143. Expiry retains control, not invented success. The wait-argument floor above does not reopen the exit predicate.

m03 CLOSED_STATIC: B2900-2902 callable reads the original record's current exited fact; B2732-2735 shares it with pending and B2924-2927 reads the same predicate for record release. B2307-2316 refuses frozen/noncallable/unknown eligibility. M06 CLOSED_STATIC: pending success B2283-2286 and direct B2965-2969 notify B3286-3308, clearing original record/reader/retained resource; B3020-3023 prevents repeat. Live-reader protection B3235-3246 remains.

M09 CLOSED_STATIC for original outcome-selection paths: B4142-4160 publishes immutable generation/original error; B4747-4767 checks original before timeout and again after successful/failed coordination, B4809-4812 returns original error object, B4833-4845/B4860-4881 keeps cancellation order/parallel facts. Channel overflow exact/one-over B5357-5367/B5382-5386 is sticky B5413-5416; BrokerProcess B6496/B6560-6577 preserves first reader error across closes; Session C2112-2139 retains broker/UNKNOWN for unresolved facts or reader error. Actual fault-publication -> effective timeout before consumption, both coordination outcomes, close-token cancellation, exact/one-over and two real public stop histories remain required dynamic evidence; none was executed or inferred from AST/text ordering.

## Complete 72-obligation disposition

Every row is independently a static condition/limit for these exact blobs. CLOSED_STATIC applies only to the source subcondition stated; dynamic NOT_RUN/native NOT_PROVEN applies to every row. OPEN means the residual Major named, not additional findings; UNCERTAIN preserves excluded test/native/external subpaths.

| Atom | Status | Exact production evidence / limit |
|---|---|---|
| N03-R01 | CLOSED_STATIC | B1515-1516/B1569-1614/B1678-1721 retain original creation identities, reserve/refuse transfer, and preserve failed cleanup. |
| N03-R02 | CLOSED_STATIC | B1526-1568/B1593-1614 independently handle attribute/NUL/birth/process failures and original cancellation association. |
| N03-R03 | CLOSED_STATIC | B1359-1405 validates job PID header, returned byte bounds, equal assigned/listed counts and cap before PID reads. |
| N03-R04 | CLOSED_STATIC | B2589-2606/B2949-2969/B3474-3483 retain original job when close is unconfirmed. |
| N03-R05 | CLOSED_STATIC | B3185-3223 independently executes stop finalizers and rethrows first original error after bookkeeping. |
| N03-R06 | OPEN | C1696-1774 parent startup failure owner retained; B6888/B6930-6973/B7351-7364 raw retry facts/duplicate-close/expiry residual M07-A. |
| N03-R07 | CLOSED_STATIC | B2472-2489/B2674-2801 startup effect guards; B5705-5734/B5850-5861/B6061-6100 fixes established-start interrupted join and retains unknown original owner. |
| N03-R08 | OPEN | B6507-6508/B6523-6524 normal process waits and B5812-5822 startup waits repaired; all-next-wait M08-C remains B6210-6215/B3399. |
| N03-R09 | CLOSED_STATIC | B4972-4986 partial-write current minimum; B5012-5058 retries unresolved worker/thread HANDLE before closed-file early return. |
| N03-R10 | CLOSED_STATIC | B4246-4271 bounded generation queue; B4043-4109 checks current original cancel/minimum at dispatch before primitive action. |
| N03-R11 | CLOSED_STATIC | C1134-1152 serializes writes and stop barrier; C1305-1311 latches background failure; C1424-1429/C1457-1462 UNKNOWN sticky. |
| N03-R12 | CLOSED_STATIC | C1169-1176/C1265-1267 common frame budget; B5983/B6246-6251 terminal reserve zero, combined budget unchanged. |
| N03-R13 | CLOSED_STATIC | B5357-5397 exact/one-over frame/tail/partial EOF; B5370-5371/B5475-5478 newly crops drain queue put using current remaining. |
| N03-R14 | CLOSED_STATIC | C2112-2139 strict actual close facts and reader-error retention; B6478-6487/B5012-5058 retries incomplete channel/workers. |
| N03-R15 | CLOSED_STATIC | C1808-1827 structured original launcher code; B7527-7532 refuses platform/plan/nonce before files; further launch context residual separately M08-E. |
| N03-R16 | UNCERTAIN | Two production blobs do not establish external pins, complete original tests or full lifecycle/native compatibility; excluded. |
| N05-R01 | CLOSED_STATIC | B1459/B1536-1542 retains original NUL on failed close; B1192-1297 explicit retained-handle recovery remains. |
| N05-R02 | CLOSED_STATIC | B1526-1568/B1681-1723 independent cleanup and original cancellation association retained; raw Popen interruption issue is separately M07-A. |
| N05-R03 | CLOSED_STATIC | B1822-1823/B1840-1869 retains both original pipe ends and independently cleans inheritance-failure ends with cancellation association. |
| N05-R04 | CLOSED_STATIC | B2211-2290/B3426-3469 independent pending/record close; B2732-2735 shares callable live original process eligibility. |
| N05-R05 | CLOSED_STATIC | B3334-3349/B3351-3392 per-original-process waits and exit queries continue across ordinary/KI/SystemExit failures before original rethrow. |
| N05-R06 | UNCERTAIN | B2871-2877 preregisters original Core reader, but ident-less interrupted late start B3029-3044 is not native timing proof. |
| N05-R07 | UNCERTAIN | C1376-1414/C1569-1621 has startup records/barrier; true late background start timing remains excluded/unproved. |
| N05-R08 | UNCERTAIN | C1386-1408 retains background startup record; ident-less interrupted start physical lifecycle remains unproved. |
| N05-R09 | CLOSED_STATIC | C1481-1511 records original closer before start, resets failed latch; C2268-2276 keeps RuntimeError UNKNOWN. |
| N05-R10 | OPEN | B6950-6967 original HANDLE retention/exit memory remains; B6888/B6930-6973/B7351-7364 cross-product raw double routes/confirmed-fact loss M07-A. |
| N05-R11 | OPEN | B4043-4109 dispatch current-context repair closed; B7491-7500/B7563 pre-Popen stop/expiry refusal closed; B7575/B7594 next effects still M08-E. |
| N05-R12 | CLOSED_STATIC | B199-208 and C274-277 publish one cleanup under lock; C1653-1663 reuses published original cleanup rather than resetting lease. |
| N05-R13 | OPEN | B3048-3056 Core waits recompute; B6507/B6523 and B5812-5822 repaired; B6210-6215 and millisecond floors retain M08-C. |
| N05-R14 | CLOSED_STATIC | B4536-4563 live endpoint minimum; B4346-4360 NOT_FOUND rereads original context and crops each pause; no fresh retry lease. |
| N05-R15 | CLOSED_STATIC | B4043-4109 current context cancel/effective minimum in actual dispatch decision; B4735-4741 await notices original context cancel. |
| N05-R16 | CLOSED_STATIC | C1424-1429/C1457-1462 common state lock prevents late state apply from clearing UNKNOWN. |
| N05-R17 | CLOSED_STATIC | C1169-1176/C1265-1267 atomic common frame count; C1134-1151 sequence/write serialized. |
| N05-R18 | CLOSED_STATIC | C1170-1172/C1265-1267 and B5983/B6246-6251 terminal reserve zero on combined terminal budget, thresholds unchanged. |
| N05-R19 | CLOSED_STATIC | C1861-1877/C1993-2064 repeated public stop keeps original cleanup, close event generation, and same-owner incomplete recovery. |
| N05-R20 | CLOSED_STATIC | B5012-5058 incomplete Windows worker/HANDLE retry precedes closed-file early return; B3853-3875 POSIX facts idempotent within its alternate path. |
| N05-R21 | CLOSED_STATIC | B6499-6500 derives standard-pipe facts from channel; normal BrokerProcess never closes those raw files itself. |
| N05-R22 | CLOSED_STATIC | C2112-2139 requires true/zero facts, actual reader finish and no reader error; no inference from close return alone. |
| N05-R23 | CLOSED_STATIC | C2172-2216 follows current in-progress event/generation; C2246-2278 bounded real original closer join, self-join avoidance and unknown-start refusal. |
| N05-R24 | UNCERTAIN | External pins, exact original node identities/order, assertions, phase artifacts and batch189/native results excluded. |
| N07-R01 | CLOSED_STATIC | B1164-1187/B1255-1269/B1696-1707 explicit exit confirmation before original process HANDLE close; B3433-3445 same Core safety. |
| N07-R02 | CLOSED_STATIC | B1134-1152/B1255-1291 API recovery retains unconfirmed control and returns incomplete claims with original bounded deadline; millisecond floor separately M08-C. |
| N07-R03 | CLOSED_STATIC | B979-1012/B1025-1034 shared pipe transfer/recovery claim; B1576-1590 and B1681-1721 process transfer/direct cleanup participate. |
| N07-R04 | CLOSED_STATIC | B1822-1869 independent original pipe-end retention/cleanup and original cancellation association. |
| N07-R05 | CLOSED_STATIC | B3048-3088 rereads actual reader liveness after wait/join failure; B3235-3246 pending close protects original live owner. |
| N07-R06 | CLOSED_STATIC | B3334-3349/B3366-3392 per-record finalizers preserve original KI/SystemExit after later safe records. |
| N07-R07 | CLOSED_STATIC | B2949-2969/B3262-3308 common success notification clears original record/reader/retained handle; B3020-3023 prevents repeat reader close. |
| N07-R08 | UNCERTAIN | B4667-4690 preregisters actual endpoint worker; B4427-4435 RuntimeError=false; real ident-less/start scheduling remains unproved. |
| N07-R09 | OPEN | B7571-7572 original pre-hash ownership and B5250-5262 partial channel registration preserved; ordinary stranded raw recovery repaired B6944-7044, cross-product M07-A remains. |
| N07-R10 | CLOSED_STATIC | C1489-1491 original closer registered before start; C2269-2276 does not infer thread exit from RuntimeError. |
| N07-R11 | CLOSED_STATIC | B4204-4211 worker cancel decision; B4338-4360 same-generation completion/NOT_FOUND retry bounded by current original minimum. |
| N07-R12 | CLOSED_STATIC | B4949-4986 before each partial write uses current bound/absolute/cleanup minimum; preserves prior admitted-call cancellation semantics. |
| N07-R13 | OPEN | B7670-7678 child prebinding and B4043-4109 current dispatch repaired; pre-Popen public stop repaired B7491-7500; later hash/channel M08-E remains. |
| N07-R14 | CLOSED_STATIC | B6061-6100 startup registered before start and settles every exit; B5705-5734/B5850-5861 actual-start facts enable real join after interrupted start; startup await current bound B5812-5822. |
| N07-R15 | CLOSED_STATIC | B6478-6487/B6600-6635 incomplete channel retries; C1993-2139 same-original public stop recovery retains incomplete facts/error history. |
| N07-R16 | CLOSED_STATIC | B5012-5058 recomputes worker/alive/HANDLE/retained before _closed early return; incomplete original thread HANDLE retry preserved. |
| N07-R17 | CLOSED_STATIC | C2053-2064 uses fresh event/generation for retry; C2198-2211 follows current in-progress generation. |
| N07-R18 | CLOSED_STATIC | C1867-1872/C1907-1921 public stop awaits; C2246-2278 actual closer exit coordination and self-join avoidance. |
| N10-R01 | CLOSED_STATIC | B2732-2735 stores original shared callable B2900-2902; B2924-2927 and B2307-2316 ask current original exit, B3433-3445 refuses early process close. |
| N10-R02 | CLOSED_STATIC | B979-1012/B1025-1034 pipe handover/recovery guarded; B1576-1590/B1681-1721 process successful transfer/direct failed-create claims guarded. |
| N10-R03 | CLOSED_STATIC | B2283-2286/B2965-2969/B3286-3308 common close notification; original reader handle cleared and B3020 prevents repeat. |
| N10-R04 | OPEN | B5250-5262 partial channel owned first; B5560-5616 unknown join protects raw read file; no-channel raw cross-product M07-A still open. |
| N10-R05 | OPEN | B6950-6967 original HANDLE failure retention/exit memory, B7180-7186/B7218-7222 no stale resurrection and ordinary raw retry fixed; M07-A duplicate/fact-loss/current-bound residual remains. |
| N10-R06 | CLOSED_STATIC | B4616-4626 initially cancelled/expired refusal; B4725-4730 final post-readiness admission and B4043-4109 current-context worker dispatch now both enforced. |
| N10-R07 | OPEN | C1810-1811/C2425-2426/B5083-5093 original context propagated, B7670-7678 child prebinding, dispatch/process waits repaired; M08-E later launch effects remain. |
| N10-R08 | CLOSED_STATIC | B4346-4360 NOT_FOUND current pause; B6930-6934/B7334-7336 aggregate dynamic process wait; B6507-6508/B6523-6524 normal wait and retry now reread original bound. |
| N10-R09 | CLOSED_STATIC | B6061-6100/B6118-6125 all-exit startup settle current budget; B5705-5734/B5850-5861 established interrupted start gets actual bounded join; B5736-5759/B5812-5822 current startup await. |
| N10-R10 | CLOSED_STATIC | B4747-4767 same-generation original error selected before/after timeout coordination; B4809-4812 original object returned; B4833-4881 cancellation order/parallel facts preserved. |
| N10-R11 | CLOSED_STATIC | B5357-5367/B5382-5386 exact/one-over; B5413-5416 sticky overflow; B5585-5586/B6621-6623 propagates; B6496/B6560-6577 first-error history; C2126 retains broker. |
| N10-R12 | UNCERTAIN | Actual event schedule causality/primitive calls and test fixtures excluded; static source cannot establish dynamic coverage. |
| N10-R13 | UNCERTAIN | Actual per-generation publication->timeout->coordination phase JSON, negatives and two public stop histories excluded; M09 static ordering alone is insufficient. |
| N10-R14 | UNCERTAIN | Exact old175/new14 identities/order, tool/dependency pins, changed assertions, before-salvage state and batch189 outcomes excluded. |

## Execution control and handoff

Complete V0–V3 outline from current execution-control (formal completed/declared substeps, not effort or this review completion):

| Stage | Completed/total | Implementation / machine / independent / human |
|---|---|---|
| V0-S0 | 1/2 | ARCHIVED / NO_GO_HISTORICAL / COMPLETED_WITH_BLOCKERS / NOT_SIGNED |
| V0-S1 | 5/5 | DELIVERED / ACCEPTED_SCOPE_ONLY / COMPLETED / APPROVED |
| R0 | 1/2 | PARTIAL_REUSED / SINGLE_IMAGE_SUBSET_ONLY / NO_SEPARATE_R0_VERDICT / NO_SEPARATE_R0_SIGNOFF |
| R1a | 5/5 | DELIVERED / ACCEPTED_SCOPE_ONLY / COMPLETED / APPROVED |
| V0-S2 | 7/8 | IMPLEMENTED / COMPLETE_FIXED9_PASSED / COMPLETE_FATAL0_MAJOR0_MINOR0 / PENDING |
| V0-S3 | 0/6 | NOT_DELIVERED / NOT_RUN / NOT_RUN / NOT_SIGNED |
| R1 | 0/4 | EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING / EARLY_SLICE_UM10_ONLY / EARLY_SLICE_FATAL0_MAJOR0 / EARLY_SLICE_APPROVED_FULL_R1_PENDING |
| V1-M1 | 0/3 | DESIGN_ONLY / NOT_RUN / NOT_RUN / NOT_SIGNED |
| R2 | 0/4 | NOT_DELIVERED / NOT_RUN / NOT_RUN / NOT_SIGNED |
| R3 | 0/4 | NOT_DELIVERED / NOT_RUN / NOT_RUN / NOT_SIGNED |
| R4 | 0/4 | NOT_DELIVERED / NOT_RUN / NOT_RUN / NOT_SIGNED |
| R5a | 0/4 | NOT_DELIVERED / NOT_RUN / NOT_RUN / NOT_SIGNED |
| R5b | 0/4 | NOT_DELIVERED / NOT_RUN / NOT_RUN / NOT_SIGNED |
| R5c | 0/4 | NOT_DELIVERED / NOT_RUN / NOT_RUN / NOT_SIGNED |

1. 当前坐标: V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION, RUNNING.
2. 本批完成: exact two-blob static review, hash/line binding, 72 dispositions and numbered snapshots; no implementation or dynamic acceptance.
3. 最后通过门禁: control last_passed_gate is {"gate": "UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW", "candidate_sha": "621b1bf386db71bfe08ca2f533fa8ec396b0504b", "receipt": "reports/unified-media/independent-live-15/receipt.json", "decision": "10PASS_0FAIL_0BLOCKED_FATAL0_MAJOR0_HUMAN_ACCEPTED_SCOPE_ONLY", "cpu_checks": 212, "fixed_cases": 10, "passed_cases": 10, "human_signoff": "reports/unified-media/human-signoff-live15.json"}. No gate advanced here.
4. 当前阻塞门禁: S3_P4_N1_CORRECTION12_FROZEN189_VALIDATION_AND_SOURCE_REVIEW; this source review remains CHANGES_REQUIRED.
5. 全局路线位置: remaining V1; historical V0-Min/R1a and unified early slice acceptances remain scoped; full R1/M1/R2 incomplete.
6. 剩余工作: resolve M07-A and M08-C/E residuals, independently review bound corrected production, then root-controlled finite dynamic validation; native NOT_PROVEN and real acceptance/signoff still required.
7. 下一责任人: coordinator/gate owner for disposition; isolated implementer for scoped correction.
8. 所需授权: no additional permission needed for this completed static review; no runtime authorization issued by it. First429 => WAIT_BUDGET, no retry/switch; first approval refusal => stop.
9. 证据目录: correction12/production-review-01/review-result only.
10. 精确停止原因: authorized isolated static review delivered; two original Majors remain open. No candidate edit, Stage/final acceptance or dynamic coverage claim.
