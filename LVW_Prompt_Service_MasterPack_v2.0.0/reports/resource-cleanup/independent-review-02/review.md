# Independent re-review of WP-R1-RESOURCE-CLEANUP-01 correction 01

**Code safety requires changes. Full machine acceptance remains BLOCKED.** The cleanup POST now directs a nonce to the original native owner and performs no HTTP unload. Its final verification can nevertheless clear a retained lease when a replacement listener responds with an HTTP error. A retained lease also lacks the identity needed to prove that it belongs to the current daemon generation.

All 13 prior findings were reviewed. Findings 1–8 remain partially open. Findings 9–13 are resolved within their stated scope, including the new source seal and the timeout across lock acquisition. [findings.json](findings.json) gives each finding's original severity, candidate file and line, trigger, expected and actual behavior, evidence and proposed correction. Open failure paths were identified by source inspection. No foreign unload, process termination or out-of-root write was observed in either archived run.

## Candidate and reproduction

The source object is 94f92bedb391f2cdcca869df10360e9b116a7c1a. The review worktree at f33517eb80feb412cf19c19e2bab101e4fead397 supplied no candidate code. I read the candidate governance and packet, prior review, correction decision and ACK, then checked the later implementation receipt and independent plan against evidence commit a2782315860c54284b7fa3d5cfca36fac470f67d. All 60 current correction evidence files match that object. The subsequent root dispatch commit c6946ae0 changes only execution-control. The frozen semantic change requires the user to start the model service again after verified release. This review treats that decision as local to this workpack.

For reproduction, use a fresh review directory. From the source repository use git archive of the full source SHA, preserving the pack prefix, for lvw (including tests, frontend dist and pyproject.toml), templates, tools, LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge, correction-01/live_harness_v2.py and the bounded controller path in the plan. Compare [source-hashes.json](source-hashes.json) before starting. All extracted bytes match their Git blobs except the unexecuted tools/open_lvw_browser.cmd, which git archive renders with CRLF per .gitattributes. Its LF-normalized SHA-256 on both sides is 0474862a9ef12d318d4f3bcad8b06d182a95c16b66dfbc37aa202579e260aa68.

Copy [request.json](request.json) to the fresh directory and replace its review-directory prefix throughout, retaining all other argv, environment, timing and controller parameters. Create empty private data and tmp directories, leave the CPU output path absent and invoke the extracted controller using [command.txt](command.txt) with the same prefix substitution. The saved command, intent, output and receipt apply to this single execution. No live harness CLI, retired harness, browser, listener, GPU probe, inference, download or private media input was used. The two frozen test modules import v2 to exercise its pre-start logic with fakes. The controller owns and reaps one cooperative child and provides no OS sandbox or descendant guarantee.

The independent run had **43 successful test markers**, exit 0 for controller and child, no stderr, signal, timeout, cancellation or controller errors. PID/session/process group 73411, birth tick 607044 and elapsed 5.413 seconds are recorded against the 90-second limit. The extracted pytest configuration is present; the double quiet setting emits progress markers without a textual pass total. No tests were edited, skipped or re-collected. [Raw stdout](cpu/stdout.log) · [stderr](cpu/stderr.log) · [receipt](cpu/receipt.json) · [intent](cpu/intent.json)

## Safety and evidence boundaries

- **Process ownership.** The public endpoint passes release_remaining=False. The native owner retains the original Process object, checks the nonce and exits that object. Neither the listener address nor a historical positive listener flag authorizes a cleanup POST to Ollama. An ordinary external loaded target and foreign models are refused. But a currently owned handle is insufficient to identify a retained lease from an earlier generation, and an empty external listener is classified as verified noop before ownership is checked.
- **Verification and recovery.** Pending cleanup records original identity, lease reference and a GPU ceiling. The owner compares nonce-validated PID/birth/exited/listener state, requires wrapper exit, takes three bounded samples and awaits runtime status before its synchronous commit. The ceiling is the lower of pre-stop used memory minus rounded model VRAM (floored at zero) plus 1024 MiB, and lease baseline plus 1024 MiB when present. Those checks explain the passing fixture recovery tests. Production readiness, however, maps HTTP errors and timeouts to unreachable. A healthy replacement in the test exercises a different branch. A missing inventory model field is silently supplied, and generic pending errors can hide which observation failed.
- **Lifecycle.** A pending record blocks start, stop and reset inside their lock. The lock wait is inside the 43-second operation deadline. The analysis route and its provider acquisition lack the pending guard. A sent lease without a pending record can also reach the legacy release tail on a different lifecycle route. These observations matter when deciding whether a follow-up user action can safely resume work.
- **Harness.** v2 checks active authority, grant hash, exact child path in the read-only ledger, row and child expiry, DB binding hashes, frozen sources/tools, private root device/inode/UID, mode and marker. Exclusive claim precedes product import. Normal finalization attempts context, browser, driver, API, runtime and socket cleanup separately, retains private diagnostics and consults SQLite for the actual action count. No recursive private-root removal is present. Descendant path and actual executable binding, capture of native identity on startup failure, isolation of proof archival and handling of unexpected/unknown ledger counts remain incomplete. The old harness CLI is explicitly retired.
- **Frontend.** The fixture exercised a 409 cleanup failure, a failed status refresh and then successful refresh. The original RESOURCE_BUSY survives both, and the status error clears. Desktop and mobile captures show the fixture error panel and the real run's observational result. The scoped human draft remains present. No personal experience or release signature follows from a screenshot.

## Reconciliation with submitted evidence

[audit.py](audit.py) compares Git bytes, immutable read-only SQLite rows, tool files, requests, intents, child identities, receipts, PNGs and raw logs. Its output is [audit.json](audit.json). Every one of 47 root ACK hashes matches both dc7e6d7114be4e9a8d179d054709df7598e454e2 and the candidate. The new distribution JS and index differ between these commits. Each live child's 22 frozen files, including dist and v2, match 94f92bed. All declared historical tool binaries currently match their digests, including the two real-only/telemetry dependencies where declared. This checks their bytes without launching them. These agreements do not resolve the validator's missing equality checks for actual execution paths.

The four root CPU requests equal their intents. Receipt argv/cwd/environment and PID/birth/session/group agree with their corresponding request and child record. All four children exited zero and were reaped with empty stderr. Check 01 has 43 success markers. Check 02 has 197 and a Pillow deprecation warning. Check 03 has TAP 12/12, zero skipped or failed. Check 04 records tsc and Vite with the sealed distribution asset names. Only check 01 was independently re-executed.

| Historical run | Raw result and bounds |
| --- | --- |
| ui-fixture-01 | Nine passing UI checks, simulated model rows/telemetry and native PID 987. Backend returned released. Desktop 1440×1321 and mobile 390×3193 PNGs were decoded and inspected. |
| real-zero-model-01 | Seven passing observational checks. Initially managed, model ready but unloaded. Public POST returned noop, empty actions, GPU used 9886 MiB before and after. Desktop 1440×1390 and mobile 390×3175 PNGs were decoded and inspected. |
| Terminal evidence | Both live requests match their intents and controller identities; both children exited 0 and were reaped. Claim contents match run IDs. Both DB rows have active=0 and calls=0, and their child/tool paths and hashes match. Both receipts record original runtime closed, diagnostics retained and no cleanup errors. The real native-final and retained owner agree on PID 4256, birth 639306960410274452, matching nonce and exited/listener_owned=false; the stop file carries that nonce. The native access log contains only GET tags/ps, including a startup HTTP 500. See [native-and-history.json](native-and-history.json). |

The previous validation-01 exit sequence remains 0, 2, 0, 0, 1, 0. Historical live-01 failed admission, reporting 17514 MiB available GPU memory against 19047 required and zero model actions. The previous noop, failed checks, raw controller logs and diagnostic roots were preserved.

## Fixed workpack obligations

| Obligation | Disposition |
| --- | --- |
| RC01 | Partial. Public owner stop works in a fixture. Production replacement verification can falsely report released. |
| RC02 | Partial. Owned empty inventory returns noop, but missing model identity is accepted. |
| RC03 | Partial. No unload POST or foreign PID kill in cleanup. Unbound generation and external-empty classification remain open. |
| RC04 | Verified for scoped busy, queued, active and concurrent controls and lock recovery. |
| RC05 | Partial. Native/telemetry/status exceptions retain tested leases. A misclassified production observation can commit early. |
| RC06 | Verified for fixed endpoint/control header, Origin, production Host/peer and unexpected parameters. |
| RC07 | Partial. Lock-inclusive deadline verified. Observation errors and replacement evidence remain incomplete. |
| RC08 | Verified for captured UI/fixture interactions, failure separation, draft preservation and bounded layout. |
| RC09 | Partial. Related backend/frontend regressions passed. Unresolved-cleanup interactions and real post-restart analysis remain unverified or open. |
| RC10 | Verified for the submitted subtree, frontend tests, typecheck and build only. |
| RC11 | BLOCKED. Real empty-inventory observation only. No loaded-model release, explicit restart followed by image inference, or full machine sequence. |
| RC12 | Independent review complete with changes required. Root disposition pending. |

**Delivery state.** Product 189/29 remains outstanding. Full machine acceptance is independently blocked even after code fixes. Human signoff remains outstanding. No Stage decision was made. Main persistence R1 / WP-R1-U3 remains paused and 23bd8da803903370be3b154a8cf21b9cc8f145a8 was untouched.

Candidate execution-control progress, completed substeps/total: V0-S0 1/2, V0-S1 5/5, R0 1/2, R1a 5/5, V0-S2 7/8, V0-S3 0/6, current R1 0/4, V1-M1 0/3, R2 0/4, R3 0/4, R4 0/4, R5a 0/4, R5b 0/4, R5c 0/4.
