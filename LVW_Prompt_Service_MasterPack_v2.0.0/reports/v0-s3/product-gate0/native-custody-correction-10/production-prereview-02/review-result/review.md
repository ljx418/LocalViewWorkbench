# 05c58c1 production static prereview

Recommendation: CHANGES_REQUIRED. STATIC findings: Fatal 0 / Major 4 / Minor 1. The four Major finding records are M05, M07, M08 and M09; m03 is the one Minor record associated with the remaining M03 recovery sub-obligation. Subpaths below are not separately counted. This is a production-source prereview, not final independent acceptance, a Stage decision, runtime authorization, or Stage PASS.

Candidate: 05c58c1ead644ab475a566af80ad1e1f4b96e023. B means the exact input `v0_s3_native_broker.py.txt`; C means `v0_s3_native_custody.py.txt`. Every line position below is against those input files, with full numbered copies in broker-numbered.txt and custody-numbered.txt. Neither source was imported, compiled, executed, or collected. Stdlib AST parsing, JSON and hashing were used solely as data inspection.

B is 312358 bytes, SHA256 b8f84f0e56f75ac9f6907362fd7850c33e746ac8ff7ccfbd35d62276aa4164cf. C is 112727 bytes, SHA256 9b7e68969f2cbf8763664ba57fa3e5ee4133a0beed076a64f037e6344f336d8d. Both independently recomputed hashes match source-binding.json. Commit provenance is the supplied binding; no claim is made that source hashes by themselves prove a Git commit's provenance.

Authority read: root product-pack AGENTS.md (including capacity rule 26), governance README, current root execution-control, docs24, frozen correction10 contract and regression obligations, original received production-review.md, and inherited correction03/05/07 obligations. Input hashes are in input-hashes.json. The isolated workspace's control is older (READY); the root control says RUNNING and is used here. Formal coordinate stays V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION. No implementer report, test source, PASS narrative, old counter/ledger or original runtime evidence was consulted.

## Six original finding dispositions

| Original | Disposition | Independently supported scope |
|---|---|---|
| M03 | OPEN (Minor m03) | Original close-before-exit defect CLOSED_STATIC: B3188-3200 gates records on live record.exited; B2547-2548 installs false eligibility and B2130-2144 fails closed. API B1170-1194/B1577-1595 also requires exit confirmation. Remaining pending recovery predicate is a bool, not callable; details below. |
| M05 | OPEN (Major) | Original pipe recovery-versus-handover race CLOSED_STATIC: B968-1003 and B1015-1038 use the same table lock and exclusive state; recovery owns claim across close. Process creation's successful return and direct cleanup still bypass that claim protocol. |
| M06 | CLOSED_STATIC | B2728-2748 routes successful direct close through B3020-3059 common identity notification; pending B2113-2117 calls that same notification, including reader.handle=None and reader.closed=True. B2799-2802 then refuses a second reader close. Reader liveness checks and independent process cancellation handling remain B2751-2867/B3078-3149. No actual native close or cancellation result is proven. |
| M07 | OPEN (Major) | Original partial channel lookup, incomplete normal return, and channel-before-process order improved at B4774-4787/B6094-6108/B6150-6187; original process HANDLE can still be forgotten when explicit close fails. Startup ambiguity also remains in channel close. |
| M08 | OPEN (Major) | Real context edges and cleanup reads improved; admission does not enclose submit/primitive, launch has no admission check, child starts transport before binding deadline, and startup join still uses a pre-await budget. |
| M09 | OPEN (Major) | Exact ordinary-error-before-close-flag case CLOSED_STATIC at B4378-4384, and newline/count overflow CLOSED_STATIC at B4877-4887/B4933-4936/B5078-5083/B5947-5953. Timeout path still replaces an already published generation's real error. |

CLOSED_STATIC only describes inspected source behavior within the named condition; all dynamic verification is NOT_RUN and native behavior NOT_PROVEN.

## m03 — pending process eligibility is a frozen bool instead of the live predicate (Minor)

Locations: B2547-2548, B2693-2706, B2086-2096, B2130-2144; record recovery B3188-3219.

Trigger and production path: BrokerCore._launch_role calls `_process_closeable(record)` while the new record has exited=False and passes its **return value** as `closeable`. `_PendingResources.add` saves that False. After stop confirms exit, suppose direct record CloseHandle fails transiently while the subsequent pending close could succeed. `close_all` calls `_is_closeable`; it executes `predicate()` on False, catches TypeError, and returns False forever for that pending entry.

Expected: record and pending ask the same current record's exit fact, allowing a safe pending recovery after confirmation. Actual: pending never attempts that process close even after exit. This does **not** demonstrate premature control-HANDLE closure: both record and pending are safe while exit is unknown. It is rated Minor because a later public Core.stop can still retry the record and remove the pending entry through a successful record close. Repair the entry to retain a callable over the original record; do not remove the exit guard.

## M05 — process creation and direct cleanup bypass recovery claims (Major)

Locations: B1431-1432 (API ownership), B1475-1490 (birth query and unconditional forget/return), B1015-1038/B1143-1211 (recovery claims), B1568-1595 (unclaimed direct cleanup), B2518-2558 (Core adoption).

Trigger: pause create_process_suspended after it retains the process/thread, for example in `_process_creation_time`; concurrently invoke the real WindowsApi.release_retained entry. Recovery claims the process and/or thread as RECOVERY_CLAIMED. Let creation's birth query return successfully while the recovery is preparing to close the claimed original handle.

Production path: Core._launch_role -> WindowsApi.create_process_suspended -> `_retain`; API recovery -> `_claim_entry` -> wait/close. Creation's success path does **not** call handover or inspect RECOVERY_CLAIMED. It unconditionally `_forget(process)` and `_forget(thread)` and returns CreatedProcess, which Core registers. If recovery has already passed `_owns_claim` at B1198-1205, it can close the now returned original handle; alternatively it can already have closed the handle before creation returns it. The check is protected only against callers that participate in the state protocol. Creation's failure `_release_created` similarly invokes direct close without obtaining a recovery claim.

Expected: one exclusive transfer/cleanup decision for these original entries, including CreateProcess success/failure and API recovery. Actual: pipe handover uses it, but process return/direct release do not; a successful-looking Core adoption can receive a handle concurrently closed by API recovery. The recovery entry is real production source; this report does not assert that main currently schedules concurrent recovery automatically. The frozen contract expressly requires these API recovery/transfer operations to exclude one another. The trigger uses that existing API and existing creation path, without an invented feature.

Keep the corrected pipe transfer. Make the actual process return and failed-creation cleanup participate in the same ownership protocol, with claimed entries refused/retained and without holding the whole table lock during blocking primitives. Callback partial-registration rollback remains UNCERTAIN under asynchronous interruption; no additional finding is counted for that assumption.

## M07 — launch aggregate drops a process on exit despite failed original HANDLE close (Major)

Locations: B6491-6546, B6150-6203, B6424-6463, B6317-6361. Secondary startup ambiguity: B4782/B5065-5074/B5115.

Trigger: production channel construction/start or BrokerProcess construction fails; `_adopt_broker_process` invokes the retained launch aggregate's release. The channel coordinates first. `_release_launch_process` confirms process exit at B6439-6440, but original Windows Popen `_handle.Close()` throws an ordinary exception at B6451-6453.

Expected: both exit and confirmed original HANDLE release are required to forget the original Popen owner; a later same-owner recovery must retry just the failed handle without repeating successful closes. Actual: helper returns `{'exited': True, 'failures': {'handle': ...}}`; aggregate B6193 checks only exited, sets self.process=None and custody.forget(process). Original HANDLE is still open but the aggregate loses its original process reference. This is the actual constructor-failure -> aggregate -> process helper path, not an inference from names or a fake complete-facts constant.

An additional real table problem makes recovery bookkeeping unreliable: `_LauncherCustody.release` snapshots `_items` at B6317-6318; aggregate.release calls custody.forget while the loop runs, but a later snapshot item with `launch is not None` is unconditionally added to `keep` at B6336-6340, and B6361 overwrites the table. A successfully forgotten process can therefore be resurrected as a detached launch-tagged entry, no longer accompanied by a retained aggregate entry. That does not repair the aggregate's lost handle-close recovery; it can instead leave an entry that every later release skips. Neither GC nor that skipped stale entry is a working recovery owner.

Closed subitems: Popen is registered before hash (B6615-6619); channel registers with aggregate before its start (B4774-4782); incomplete returned strict facts retain channel (B6161-6178); an existing partial channel makes close_pipes=False (B6183-6187); aggregate collects cancellation and attempts process cleanup before raising the same object (B6155-6156/B6188-6189/B6206-6210). These are material repairs.

Startup ambiguity remains: StreamChannel.close treats join RuntimeError as finished=True, then closes the read endpoint, rather than retaining an unresolved start. A start interrupted before the Thread started-event is published can still have a late target. The line path is explicit, but actual native/CPython timing is NOT_PROVEN; the confirmed HANDLE-loss path above independently supports this Major. No claim is made that normal aggregate release directly closes files beneath an established active endpoint: its close_pipes=False branch prevents that old path.

## M08 — context is carried, but admission and all wait bounds are not enforced (Major)

Locations: B4239-4266/B4299-4313/B4332-4346/B4434-4468; B6588-6639; B6706-6716/B5483-5495; B5417-5472; B6150-6187/B6316-6324/B6430-6439.

1. Endpoint admission returns before start/submit. `_admission` releases its private lock at B4266; read calls `_start`, possibly waits for readiness until the deadline, then `_await` unconditionally submits at B4332. Neither worker.submit nor worker.run checks the call cancel/deadline/context (B3928-3951/B3784-3796 checks only worker._cancelled). Pause after admission or during wait_ready, publish cancellation/expire the context, resume: a read request can enter `read_stream` at B4468 before the caller notices cancel/timeout. A completed admission check is not an atomic admission of this request. The endpoint's lock is also not taken by cancel.set or context publication. Already expired/already-cancelled calls **at initial entry** now correctly reject before starting a worker; that narrower original subcase is CLOSED_STATIC. Writes independently check each segment (B4508-4515), so the unguarded read primitive is the decisive example.

2. Default launch holds context but never asks it for admission. C1694/C1808-1811 -> C2410-2426 -> B6557 forwards the original parent object. B6595-6597 copies absolute_deadline, then mkdir/open/write/Popen/hash/channel proceed at B6602-6639 with no cancel/expiry/cleanup check before or after. Trigger a validated session whose deadline has elapsed before launcher side effects (including an already VALIDATED delayed start), or let plan-file work consume the remaining lease: Popen still runs. Merely retaining the object does not bound those actions.

3. Real child main creates StreamChannel and starts its reader at B6711-6712 before loop.run fixes and binds the child deadline at B5483-5495. Core's context is constructed unbound at B2174-2175. The drain can therefore start worker/submit ReadFile with no absolute deadline before the formal binding. Once bound, ongoing endpoint waits do observe it; the original pre-binding window still exists in this formal entry.

4. StartupOwner ordinary/KI/SystemExit result exits now settle in finally (B5427-5457), but `owner.start` is outside that try (B5421), and `settle_budget` is computed before await (B5426) and reused after it (B5447). Example: less than one second remains when startup begins; action consumes that remainder, publishes an ordinary error just before deadline, and its actual thread tail remains live. finally can add the old remaining budget to a join after the deadline. `_startup_settle_seconds` also floors at POLL_SLICE_SECONDS even if remaining is smaller/zero (B5472). A newly published shorter cleanup is not reread there; StartupOwner stores only the numeric original startup deadline. The original ordinary-result missing-join bug is repaired, but the same-deadline bound and all-exit promise are incomplete.

5. Aggregate.release does not read self.context or bind its deadline into channel before close (B6150-6154), and the process helper uses the incoming numeric deadline and time.monotonic at B6430-6439. Table.release computes context minimum once at B6316. A shorter cleanup published while channel.close consumes time does not shorten the later process wait unless the caller itself supplied it. Direct `_adopt_broker_process` failure passes the launch-time absolute value. This is the actual production failure path; context merely sitting on aggregate is not a dynamic read.

Correctly connected child STOP path: B6706 -> core.context -> StreamChannel/endpoints/workers (B4778-4781/B4617-4618/B4289-4292); Core binds WindowsApi context at B2180-2183. `_stop` B5605 publishes Core cleanup through B2282, then STOPPED `_reply` B5606/B5360 -> Channel.write B5007 -> endpoint effective deadline B4230-4236/partial-write B4487-4494; main finally B6721 uses channel._remaining and endpoint close. These paths **now read published cleanup**. Do not repeat the old claim that STOPPED necessarily uses the long lease. NOT_FOUND rechecks shared absolute/cleanup each retry and crops pause (B4026-4040), also CLOSED_STATIC. Endpoint join recomputes remaining B4420/B4554.

Parent endpoint-created WindowsApi instances at B4615-4616 are not bind_context'd by _make_endpoint, although their worker and endpoint get parent context. This is a missing propagation edge, not independently counted as a blocking native failure: those stream primitive methods do not currently wait through the API recovery facade. The old injected three-argument launcher boundary is explicit at C1786-1792/C1812-1813; default production launcher does accept and forwards context. No claim of a default three-argument bypass is made.

## M09 — timeout still hides an immutable completed generation error (Major)

Locations: B3795-3805/B3829-3847 (original outcome), B4333-4346 (selection), B4417-4432 (cancel/join), B4909-4910/B4938-4972 (channel history), B5835/B5890-5904 and C2126-2138 (parent retry).

Trigger: a genuine read_stream fault completes and publishes the original BrokerError/OSError outcome for the submitted generation while endpoint._await is between slices. Before it resumes, the bound deadline expires, with channel cancel still unset. Endpoint resumes B4334 and takes B4337 before consulting worker.wait_done/outcome. `_cancel` succeeds, then B4339 raises a newly created BROKER_PIPE_TIMEOUT; if cancel/join itself fails, that new failure leaves even earlier. The already published original ordinary error object remains only inside worker._outcomes, never selected for channel error history.

Expected under frozen C: the immutable real generation failure remains the primary error, with timeout/cancellation beside it; parent close/retry must not lose that error. Actual production chain is WindowsPipeWorker -> endpoint._await -> StreamChannel._drain -> _record_reader_error -> BrokerProcess.close -> Session.stop. Channel records PIPE_TIMEOUT (or CANCEL_NOT_CONFIRMED), and both stops preserve that replacement code rather than the original real fault. Resource facts remain strict/UNKNOWN; this report does **not** claim the replacement error is benign or that this trigger releases the broker without error. The defect is lost primary evidence, not false resource release.

The originally reported close-token interleaving is fixed: when cancel is already set, `_raise_cancellation` reads the generation outcome before cancellation and again afterwards, and `_outcome_error` returns the original object. No generation error is overwritten in _outcomes by request_cancel. Overflow is recorded at its origin, propagated as reader_error plus overflow facts, then sticky across BrokerProcess retries. These closed subitems must remain closed during the next repair.

## Complete original atom audit

All 72 inherited/local obligation records (16 + 24 + 18 + 14) are listed individually. CLOSED_STATIC is restricted to the explicit source subcondition; UNCERTAIN identifies information requiring excluded tests, external pins, or runtime. Related residuals are cross-referenced instead of being counted as additional findings.

| Atom | Status | Source support / retained limitation |
|---|---|---|
| N03-R01 | CLOSED_STATIC | B1375,1431-1432,1465-1535,1577-1595: original refs/primary survive failed release; recovery claims caveat M05. |
| N03-R02 | CLOSED_STATIC | B1435-1467,1475-1535: independent attribute/NUL/birth/process cleanup and primary association. |
| N03-R03 | CLOSED_STATIC | B1245-1321: full header/returned/allocated/count equality/cap/inline PID array guards. |
| N03-R04 | CLOSED_STATIC | B2409-2423,2728-2748: failed job close retains original Core.job/pending. |
| N03-R05 | CLOSED_STATIC | B2930-3002: step catches primary independently, continues all finalizers, no release latch on failures. |
| N03-R06 | OPEN | C1696-1774 preserves parent startup guard; B6491-6546 launch cleanup still loses failed Popen HANDLE (M07). |
| N03-R07 | OPEN | B2293-2313,2465-2619 checks late Core actions; B5417-5472 startup bound not fully enforced (M08). |
| N03-R08 | OPEN | B5774-5860 uses recomputed parent deadline; B5426/5447 and B6186/6439 retain old bounds (M08). |
| N03-R09 | CLOSED_STATIC | B4497-4520 completes partial writes; B4549-4593 retains file on failed real join and retries thread HANDLE. |
| N03-R10 | OPEN | B3928-3951 bounded queue/current generation; B3991-4040 retry fixed; endpoint-to-worker admission still OPEN M08. |
| N03-R11 | CLOSED_STATIC | C1111-1152 write lock and stop barrier; C1274-1312 callback failure; C1416-1462 atomic UNKNOWN. |
| N03-R12 | CLOSED_STATIC | C1154-1196 and C1253-1271 share budget lock; B5337-5360/B5584-5591 use combined terminal budget. |
| N03-R13 | CLOSED_STATIC | B4863-4917 bounds no-newline buffer (+1 detection), names partial EOF; queue loop calls _check_wait. |
| N03-R14 | CLOSED_STATIC | C2112-2138 rejects missing/false/reader error; B4549-4593/B5817-5835 retries incomplete resources. |
| N03-R15 | CLOSED_STATIC | C1808-1827 structured launcher error mapping; B6580-6585 rejects unsupported platform before files. |
| N03-R16 | UNCERTAIN | Source-level compatible items below inspected, but full lifecycle/native/old tests and other source pins outside two-blob scope NOT_RUN/NOT_PROVEN. |
| N05-R01 | CLOSED_STATIC | B1375/B1448-1464 retains NUL on close failure; original API table recovery persists. |
| N05-R02 | CLOSED_STATIC | B1435-1535/B1568-1599 independent cleanup and primary/original cancellation association; shared-bound residual M08. |
| N05-R03 | CLOSED_STATIC | B1668-1746 pipe pair retained at creation, both closes independent, partial failure retains originals. |
| N05-R04 | CLOSED_STATIC | B2086-2128/B3181-3221 independently process handles and rethrow original cancellation after group. |
| N05-R05 | CLOSED_STATIC | B3078-3149 wait/exit errors do not skip later processes; KI/SystemExit rethrow through group. |
| N05-R06 | UNCERTAIN | B2684-2690 reader preregistration/B2799-2867 alive guard preserved; actual interrupted Thread.start inflight timing not proved. |
| N05-R07 | UNCERTAIN | C1350-1414 preregistered background records/starting counts and C1542-1621 stopping barrier; late native start timing unverified. |
| N05-R08 | UNCERTAIN | C1386-1409 keeps registered original record and tests actual alive/ident; interrupted start before ident remains timing assumption. |
| N05-R09 | CLOSED_STATIC | C1464-1511 names closer failure, resets latch and retains original thread list; C2257-2278 RuntimeError is UNKNOWN. |
| N05-R10 | OPEN | B4774-4787/B6150-6203 partial owner fixed; confirmed process exit with HANDLE close failure still drops recovery (M07). |
| N05-R11 | OPEN | B2293-2313/B2496-2614 Core checks closed subset; B6602-6639 launcher and B4434-4468 read admission still M08. |
| N05-R12 | CLOSED_STATIC | B201-215 and C1636-1663 lock/publish one cleanup deadline; no extension from repeated entry. |
| N05-R13 | OPEN | B2834-2835/B3130-3134 remaining per Core operation; startup/aggregate old bound paths M08. |
| N05-R14 | CLOSED_STATIC | B4334/B4210-4237 dynamic endpoint binding; B4026-4040 dynamic NOT_FOUND context reads/cropped pause. |
| N05-R15 | OPEN | B3784-3796 worker intent and B3928-3951 current generation closed; endpoint call cancellation does not atomically admit read (M08). |
| N05-R16 | CLOSED_STATIC | C1416-1429/C1444-1462 same state lock protects UNKNOWN and late apply. |
| N05-R17 | CLOSED_STATIC | C1154-1177/C1253-1271 one budget lock check+commit; C1111-1152 serialized sequence/write. |
| N05-R18 | CLOSED_STATIC | C1154-1177/C1253-1271 and B5343/B5584-5586 consume terminal reservation with reserved=0. |
| N05-R19 | CLOSED_STATIC | C1837-1922/1993-2064 public repeated stop invokes same-owner recovery with original cleanup; B5817-5835 lower retry. |
| N05-R20 | CLOSED_STATIC | B4549-4593 recomputes retained/alive and retries HANDLE even with _closed file; B3480-3630 POSIX close idempotent. |
| N05-R21 | CLOSED_STATIC | B5769-5772/B5836-5839 BrokerProcess uses endpoint file facts, no direct raw stdin/stdout close. |
| N05-R22 | CLOSED_STATIC | C2112-2138 strict required True/zero/reader facts; replacement-error history residual M09 does not weaken these guards. |
| N05-R23 | CLOSED_STATIC | C2157-2278 captures current event, follows generation and actually joins closers; expiry/RuntimeError latch UNKNOWN. |
| N05-R24 | UNCERTAIN | Two-source compatibility inspected below; original test node identities/order and external production pins deliberately not read. |
| N07-R01 | CLOSED_STATIC | B1577-1595/B1170-1194 API process Close only after exit; Core B3188-3200 same safety guard. |
| N07-R02 | CLOSED_STATIC | B1143-1211 retains unconfirmed process, releases claim for retry, rethrows original cancellation after safe steps; per-call bounds caveat M08. |
| N07-R03 | CLOSED_STATIC | B968-1003/B1015-1038/B1143-1211 pipe handover and recovery share exclusive claim; process-return bypass separately M05. |
| N07-R04 | CLOSED_STATIC | B1668-1746 inherits/close failure treats ends independently, retains unresolved refs and associates original cancellation. |
| N07-R05 | CLOSED_STATIC | B2825-2867 rechecks alive after wait/join errors; B3004-3020 pending protection asks actual owner. |
| N07-R06 | CLOSED_STATIC | B3078-3149 KI/SystemExit on wait/exit propagated after later records. |
| N07-R07 | CLOSED_STATIC | B2728-2748/B3020-3059 common close identity notifies reader/pending/record/retained; no second read close once handle None. |
| N07-R08 | UNCERTAIN | B4289-4308 worker preregistered and RuntimeError join false B4107-4113; wait_ready timing/late startup combinations dynamic NOT_RUN. |
| N07-R09 | OPEN | B6615-6619 and B4774-4787 preserve hash/partial owner; aggregate HANDLE failure M07 still OPEN. |
| N07-R10 | CLOSED_STATIC | C1490-1493 stores original closer before start; C2269-2276 does not equate RuntimeError with exit. |
| N07-R11 | CLOSED_STATIC | B3784-3796 same worker condition for intent; B3991-4040 retries NOT_FOUND with current generation and own pause. |
| N07-R12 | CLOSED_STATIC | B4483-4495/B4508-4515 recomputes absolute/bound/published-cleanup minimum each partial segment. |
| N07-R13 | OPEN | B2401/B2496-2614 Core pre/post improvements; formal launch/endpoint and child early reader window M08. |
| N07-R14 | OPEN | B5233-5241 real Thread.join; result exits finally B5444-5457 fixed, precomputed budget and owner.start outside try remain M08. |
| N07-R15 | CLOSED_STATIC | B5817-5835 `_channel_complete` controls retry; C1993-2139 public stop recovery keeps errors/facts. Dynamic failure combinations not run. |
| N07-R16 | CLOSED_STATIC | B4549-4575 recomputes live/retained/HANDLE release each close, before _closed early return. |
| N07-R17 | CLOSED_STATIC | C2053-2064 allocates current event/generation; C2186-2207 follows a new running generation after prior event. |
| N07-R18 | CLOSED_STATIC | C1859-1872/C1906-1921 public stop paths await actual closer; C2218-2278 current-thread avoidance/real join/UNKNOWN. |
| N10-R01 | OPEN | Original close-before-exit CLOSED_STATIC B3188-3200; pending live-predicate/recovery defect Minor m03 B2548/B2139. |
| N10-R02 | CLOSED_STATIC | Exact pipe claim/handover competition fixed B968-1003/B1015-1038; process success/direct cleanup bypass remains related Major M05. |
| N10-R03 | CLOSED_STATIC | B2113-2117/B3020-3059 notification clears reader.handle and retained; B2799 skips subsequent close. |
| N10-R04 | OPEN | Partial aggregate registration and no raw close beneath established endpoint fixed B4774/B6183; HANDLE-loss/start ambiguity M07. |
| N10-R05 | OPEN | Incomplete facts retained B6161-6178 and aggregate cancellation rethrown B6206-6210; failed HANDLE ownership M07. |
| N10-R06 | CLOSED_STATIC | Calls already expired/cancelled at initial entry reject B4249-4265 before B4443-4445; later admission-to-submit race M08 remains OPEN. |
| N10-R07 | OPEN | Default/child shared context edges present; launcher admission/child initial unbound window/aggregate reads M08. |
| N10-R08 | OPEN | NOT_FOUND dynamic tighten CLOSED_STATIC B4026-4040; launcher/aggregate subsequent wait does not reread per-launch cleanup M08. |
| N10-R09 | OPEN | All awaited result exceptions enter real-join finally B5444; start exception and stale/floored settle bounds M08. |
| N10-R10 | CLOSED_STATIC | Exact local-close-flag after published read error returns same original object B4378-4384/B4358-4360; timeout path M09 separately OPEN. |
| N10-R11 | CLOSED_STATIC | B4877-4887/B4933-4936 sticky overflow to close B5078-5083/B5947-5953; B5890-5904 keeps first code; C2126 retains broker. |
| N10-R12 | UNCERTAIN | Fixture/test causality outside this source-only task; no test code read or executed. |
| N10-R13 | UNCERTAIN | Fixture-controlled negative combinations and JSON phase artifacts outside source-only scope; real source ordinary-fault timeout residual M09. |
| N10-R14 | UNCERTAIN | Production compatibility subset inspected; actual old175/new14 node identity/order, test salvage, and dynamic outcomes NOT_RUN. |

## Preserved compatibility and unresolved assumptions

M01 directory fullmatch/traversal/device checks C450-481, m01 immutable role view/sealed copy C498-574, M02 fixed-width types and explicit prototypes B353-609, M04 Job header/count/length/cap guards B1245-1321, and M11 nonce generation/refusal C1056-1069/C1816-1827/B6580-6585 are CLOSED_STATIC within these two sources. M10 role_command B1851-1901 remains an explicit role command builder, but same-commit external tool pins and old node lists are UNCERTAIN: those other files are outside this exact production-source input and have not been read or run. No inherited PASS or prior AST-equivalence claim was reused.

Native thread startup interruption, actual Windows handle reuse, cancellation timing, Kernel32 behavior, Popen cleanup and end-to-end resource convergence are NOT_PROVEN. The listed reproducible schedules identify source control paths and conditional primitive outcomes; no scheduling frequency or physical native reproduction is claimed. Tests, collection, imports, compile/exec, candidate subprocesses, native API, services, models/GPU/media/network/DB, downloads and original ledger/counter reads: NOT_RUN. No new quota, ACK, schema, endpoint protocol or feature demand is proposed. No Stage or product denominator is changed. Test-causality N10-R12/R13 and old node ordering remain the separate implementer/dynamic review responsibility.

The limited pre-review is complete; repairs and any further finite verification/independent acceptance are for the coordinator. This worker started no agents, created no runtime resources, made no candidate edits and did not touch the approved CMD exception or old output. All writes are new files under this review-result directory. No live capacity beyond the assigned single readonly slot was inferred; worker_done settles this worker.

## Required product handoff fields

Current coordinate: V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION (root control RUNNING). This batch: static review of hash-bound 05c58c1 two-source snapshot, 72-atom audit, F0/M4/m1. Last accepted gate: 621b1bf unified-media live15 scope only (control navigation, not revalidated here). Current blocking gate: S3_P4_N1_CONSOLIDATED_OWNER_CONTEXT_AND_IO_OUTCOME_CORRECTION10 plus the source defects above. Global route position: outline below. Remaining work: coordinator dispositions/repairs, separate tests, bounded independent verification and existing product gates/signatures. Next owner: coordinator gate owner. Authorization: static scope already supplied; this report grants no runtime permission. Evidence directory: production-prereview-02/review-result. Exact stop reason: assigned static prereview completed, CHANGES_REQUIRED; worker_done then idle.

Full control outline: V0-S0 1/2 (historical NO_GO); V0-S1 5/5 (V0-Min scope); R0 1/2; R1a 5/5 (single-image scope); V0-S2 7/8 (old human signoff pending); V0-S3 0/6; R1 0/4 (unified early slice separately signed); V1-M1 0/3; R2 0/4; R3/V2 0/4; R4/V2 0/4; R5a/V3 0/4; R5b/V3 0/4; R5c/V3 0/4. This prereview changes no implementation, machine-acceptance, final-independent-review or human-signoff status.
