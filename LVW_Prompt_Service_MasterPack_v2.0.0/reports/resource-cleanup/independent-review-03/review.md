# Resource cleanup correction 02 independent review

**Changes required.** Cleanup now requires a dedicated TCP refusal before it clears a lease, but its generation check can still authorize a stop for an unbound lease. Several harness fault paths also weaken the claimed execution and evidence boundaries. The two archived live receipts support their specific observations. Real **loaded-model release, explicit restart and successful image inference remain BLOCKED**. No Stage decision or human signature is issued here.

## Candidate and evidence

I reviewed Git objects from source candidate `679803cf62770e8a4268992855311cfee833c3e2`. Both live runs used `312e3a96214e1bf79cef977f195ed301ce80411f`. A path-level diff found only the two parameterized GPU boundary cases and evidence/metadata changes between the candidates. Evidence and the review plan are archived in `aec4c19d109d434046dea4f68927b325897db240`, the source candidate's direct child. I read the two previous reviews, their findings, candidate instructions, decision, ACK, implementation receipt, and plan. I used a new pack-layout extraction outside the report and left the older review worktree source and persistence candidate `23bd8da8` untouched.

The independent command ran once under the candidate's opt-b-14 bounded_exec.py. The request and intent contain its exact argv, cwd and sanitized environment. Both roots were fresh. The extraction included pyproject, frontend dist, backend, tests, templates, tools, bridge and v3. Frozen-source test enumeration gives 48 product cleanup cases and 27 harness cases. Raw pytest progress contains 75 successes. The pack's extra quiet flag suppresses the summary. Controller and direct child exited zero. PID/session/group 86930, birth tick 1041626, was reaped after 9.386 seconds with no signals, cancellation or timeout against 90 seconds. Stderr was empty. Execution used in-process ASGI and mocked transport/native/telemetry seams. No live harness CLI, browser, native runtime, GPU utility, listener or model was launched. This cooperative single-child controller provides no OS sandbox or descendant-reap guarantee. [Raw intent](cpu/intent.json) · [Output](cpu/stdout.log) · [Controller receipt](cpu/receipt.json)

## Findings requiring correction

The generation check is the highest priority. A proof read returns a new observation each time. With an unbound retained lease, one successful read followed by an unreadable record makes both sides of the second comparison null. Cleanup can then stop the original handle and clear a lease it never bound to that handle. Use one nonempty current generation and require an independently nonempty lease generation before comparison. No such failure was observed in the submitted runs.

| Finding | Severity | Remaining issue |
|---|---|---|
| 03-A | Major | Repeated generation reads can admit an unbound lease. |
| 03-B | Major | A valid sealed data directory does not constrain the ambient data root consumed when app.main is imported. |
| 03-C | Major | The direct native path-conversion helper lacks an executable binding. The project authority executes before its digest is validated. |
| 03-D | Major | Startup failure can derive both expected PID/birth and observed PID/birth from one terminal record. |
| 03-E | Major | Claim write/close failure after exclusive creation bypasses budget retention and terminal receipt. |
| 03-F | Major | Opening an existing FIFO can block before the relative output writer checks its type. |
| 03-G | Major, evidence | The real managed oracle labels any verified closure zero-model without asserting empty inventory at cleanup time. |
| 03-H | Minor | Deadline during an observation can label it unobserved or skipped despite having started it. |

All eight are source findings. Each trigger, expected and actual behavior, file/line, supporting evidence and disposition for each of the 13 prior findings is recorded in [findings.json](findings.json).

## Production and harness conclusions

The fixed cleanup endpoint sends no HTTP unload. The only requested mutation is the nonce stop for the original native process object. Normal job finalization has a separate provider release path. Start/reset/stop guard pending and retained leases, and runtime_control has no automatic release tail. Acquisition records nonce/PID/birth from runtime ownership or records no generation. Strict inventory rejects missing/conflicting model names, whitespace, duplicates, malformed digests and invalid VRAM sizes. Model readiness and available actions reflect unresolved cleanup. Admission is checked before scheduling and again on submit. Pending blocks dequeue. A retained lease blocks the production provider before a queued job can acquire or infer.

Final verification reads matching native exit, samples the resource ceiling three times, reads runtime status, demands a dedicated absence observation, then compares the retained lease and generation. A responding TCP endpoint remains present even if HTTP fails with 500, malformed JSON or a timeout. Other TCP errors remain indeterminate. Coarse HTTP unavailability alone cannot clear a lease. The exact 1024 MiB boundary passes and one MiB above retains recovery. External service cleanup blocks even for empty inventory. A second click may return noop only after matching the previous exit and observing absence.

V3 checks fresh sealed private/data directory identities and existing descendant aliases before product import. Run claims use exclusive creation. Both JSON and PNG use the shared dir-relative, no-follow final open and regular/single-link check before truncation. No recursive temp removal appears on v3's path. Python, Chromium, Ollama, PowerShell and PATH-selected nvidia-smi compare against the actual selected paths. Each live child lists the authority, bridge, telemetry, backend, templates, distribution and v3. The earlier CLIs both exit with a retirement message. These improvements have the limitations in 03-B/C/E/F.

Missing native evidence or multiple prepared generations fails reconciliation. Proof archival failures are recorded and reach ordinary finalization. Unknown ledger counts remain null, nonzero counts remain visible, read/settle/retain errors fail, and a retained reservation requires active=2. A receipt-write failure on the normal final path returns nonzero to the outer owner. The recorded real native proof has independent earlier and later identities. The startup-failure shortcut and early claim failure remain open. Unknown product verdicts fail both the managed and external branches of the live oracle. Its external branch requires blocked/unverified, while the managed branch requires released/verified.

## Reconciliation of prior runs

| Evidence | Independently checked |
|---|---|
| correction-02 CPU history | Check 01 retained its 71 successes/one failure on the failed-before versus skipped-after assertion. Commit 773fdf27 corrects that assertion and retains no-stop and unknown assertions. Check 02 full 226, 03 targeted 72, 04 targeted 73, 05 full 227, 06 targeted 73, 07 full 227. The intermediate PNG/nonce and live-oracle edits remain in history. |
| Final root CPU | Check 08 has 75 successes. Check 09 has 229 and one Pillow deprecation warning. Both intents match requests and both direct children exited zero and were reaped. Earlier source-side final-binding still named 312e3a96 for latest tests. Its archived correction names 679803cf for those tests, with 312e3a96 retained for the live product. |
| Reused frontend | The entire frontend Git tree is identical at 94f92bed, 312e3a96 and 679803cf. Correction-01 check 03 TAP records 12/12. Check 04 records successful TypeScript and Vite production build. Both receipts show exit zero and reap. |
| Earlier failures | Validation-01 exit codes remain 0,2,0,0,1,0. Old live-01 failed admission with 17514 MiB free against 19047 required. The early noop receipts remain historical. |
| UI fixture | Nine assertions passed, including original-handle simulation, manual draft, busy failure, failed recheck and subsequent recovery. Simulated native PID 987. |
| Real empty service | Seven assertions passed. Initially managed, ready, model_loaded=false, PID 10372. Response records original-service stop, verified released, stopped/unmanaged, TCP CONNECTION_REFUSED, and GPU usage 3455 MiB before and after. |
| Native and budget terminal | Real nonce 50b32f91f6704272b9bd9f06a831375c, PID 10372, birth 639306993378652178 agree between expected listening and final exited proof. The retained owner equals proof, stop file equals nonce and listener_owned=false. The retained native HTTP access log contains only GET tags/ps. Both runs have exclusively named claims matching their run IDs, matching owner/controller identities, zero actions, settled DB rows active=0/calls=0, and matching grant, child, tool and source hashes. |

The per-child hashes, extracted-source and Git digests, request/owner comparisons, DB rows read by run ID, retained file comparisons, individual assertions, tool identities and screenshot dimensions are in [source-hashes.json](source-hashes.json). The raw archived real evidence supports closing this specific empty daemon. It establishes neither loaded-model release nor later analysis.

## Twelve verification obligations

| Obligation | Independent disposition |
|---|---|
| RC01 | Public endpoint and native-stop fixture demonstrated. Loaded target unverified and 03-A open. |
| RC02 | Ambiguous inventory rejected. Owned-empty closure, proven repeated noop, and external refusal distinguished. |
| RC03 | Cleanup has no HTTP unload or PID-based foreign stop. Unbound retained-lease custody remains open under 03-A. |
| RC04 | Active, queued, concurrent controls and lock recovery exercised. |
| RC05 | Covered failures retain recovery. Unbound-generation race prevents full closure. |
| RC06 | Fixed endpoint, Origin, Host, peer, control header and body/query negative cases exercised. |
| RC07 | Cooperative deadline includes lock wait. Telemetry and native failures retain unknown outcomes. 03-H remains. |
| RC08 | Nine archived UI fixture checks, real maintenance click, separate status error and draft preservation verified. |
| RC09 | Related lifecycle/job/frontend regression evidence available. Real post-restart image inference outstanding. |
| RC10 | Final scoped 229 backend and reused frontend 12/typecheck/build verified. |
| RC11 | **BLOCKED**. The full loaded-model release/restart/image inference sequence has no execution receipt. |
| RC12 | Independent review complete with changes required. Root disposition remains outstanding. |

Product acceptance denominators remain 189/29. The 12 obligations, 75 targeted cases, historical regressions, fixture assertions and real empty-service observations have separate scopes. Human acceptance remains unsigned for this correction.

Candidate governance outline, completed substeps/total from execution-control. V0-S0 1/2, V0-S1 5/5, R0 1/2, R1a 5/5, V0-S2 7/8, V0-S3 0/6, R1 0/4, V1-M1 0/3, R2 0/4, R3 0/4, R4 0/4, R5a 0/4, R5b 0/4, R5c 0/4. Current R1 persistence work remains paused.
