# Actual five-case trusted-control review

**Qualified for the narrow future cooperative single-child mechanism — Fatal0 / Major0 / Minor0.** All5 actual cases independently match their frozen control oracles. CTRL01-M1 is closed for the tested created-before-local-publication ownership/cancellation boundary. This is not supervisor+guard integration, a supervised194 checkpoint, product29/native9, Stage/N2 or human clearance. No new execution, probe, import, compilation, collection or present PID scan occurred.

Evidence `444410f496eacbbb17b17c5ff5c2916e16dbd55c` (rootcommit444410f); unchanged controller SHA256e3b18a954084c5c89ff1cf7f35e719d4669c8e6df21e652b4d6d54014ff48ba1; planSHA5e1ee44d5f6a8bdc48061e2153f61e83d20fc45270a8258b1e1894e0e7d6cd59. Existing39a5ce57 source qualifications are reused only after exact pin checks, not inherited from a PASS label. No194/source-history redo was performed.

## Binding, activation and independent recomputation

All3 source pins, interpreter and5request hashes match.45 scoped committed files (source/plan/activation/commands/raw/review scope, excluding copied prior reports) match immutable444410f blobs; no mismatch. Current intent documents equal exact request JSON, and each receipt carries identical child argv/cwd/replacement environment. Five original tool commands match frozen renderings/argv/cwd in order, unique case and unique PID, no retry. Expected tool exits are0/1/1/1/driver0, not five successful workload exits.

Activation97c0f274… binds plan and source-review39a5ce57 receiptSHA c55fc131…, issued17:41:29.763607UTC; prior source commit is17:40:06UTC. Recorded activation-file ordering precedes first intent. These original activation/execution records support pre-launch admission; no independent trusted-clock reconstruction or undocumented per-callUTC timestamps are claimed. The original tool results are consumed separately from the root summary.

Recorded orchestration elapsed2.001s is within20s. Independently summed controller elapsed is1.3001455279954826s; each case lies within its0.5wall+0.2TERM+0.5KILL envelope. Tool result wall fields are return/collection metadata and are not substituted for child elapsed. No shorter elapsed time is treated as termination proof; signal outcomes and owned wait/reap facts supply the mechanism proof.

## Actual outcomes

| Case | PID / birth | Controller status | Child RC | Tool RC | Child signals | Controller seconds |
|---|---|---|---:|---:|---|---:|
| normal | 1486494 / 5635381 | EXITED_ZERO | 0 | 0 | none | 0.040245 |
| nonzero | 1486521 / 5635402 | EXITED_NONZERO | 13 | 1 | none | 0.042504 |
| term | 1486548 / 5635420 | DEADLINE_EXPIRED | -15 | 1 | SIGTERM | 0.503369 |
| ignore-term | 1486575 / 5635482 | DEADLINE_EXPIRED | -9 | 1 | SIGTERM, SIGKILL | 0.703481 |
| cancel-publication | 1486602 / 5635564 | CANCELLED | -15 | 0 | SIGTERM | 0.010547 |

For normal/nonzero, flushed actual child ready JSON has matching PID/birth/session/group/mode, with parentPID positive and distinct. Child session/group equals its newly owned PID. Journal identity matches receipt exactly. Normal remains EXITED_ZERO0; error13 remains EXITED_NONZERO/controller1. Nonzero workload was not reclassified as successful work to make a control test pass.

TERM case is timed_out=true, actual SIGTERM with childRC-15, reapedtrue and no controller errors. IgnoreTERM child printed ready only after installing its SIG_IGN handler; actual TERM thenKILL occurs in order, with KILL at least0.2s afterTERM, childRC-9 and reapedtrue. The unchanged pinned controller's successful Popen.wait path backs those terminal states; source-bound waitpid/reap evidence and recorded returncodes are used without inventing a syscall trace. Timeout remains DEADLINE_EXPIRED/controller1 even after successful cleanup.

The fifth case records an actual kernel child1486602/birth5635564. Its factory calls realPopen, holds and returns that same object, and sends real parentTERM+INT before the controller local assignment. Current oracle's actual_created_pids is exactly that journalPID; receipt is identical to the separately read controller receipt. Pending cancel_signals=[15,2], statusCANCELLED, controllerexit1, childRC-15, reapedtrue, noerrors/fallbackfalse. User-code stdout is empty because cancellation can precede Python ready; that is valid for this kernel-created/prepublication oracle and is not fabricated ready evidence. No replacement or mock owner is used.

The source-qualified nonthrowing handler now actually preserves ownership through this tested boundary and allows bounded real TERM/reap. Adapter initial poll can reap a terminated child, so fallbackfalse alone is not treated as a standalone certificate; the current exact controller wait path, receipt state/returncode, same actual object/PID, terminal child outcome and separate postidentity record are consumed together. No arbitrary mutation/fake-receipt fault proof or all possible constructor interruption times is claimed.

## Cleanup and identity snapshots

Each controller receipt records reapedtrue and a terminal returncode; PID/birth/session/group journal and actual ready bind the firstfour, while the fifth uses actual Popen creation rather than an unowed user-ready requirement. Five exact root post-run snapshots identify the same PID/expectedbirth and stateMISSING/original_absenttrue. They are existing execution evidence, compared to the journals and hashed with the committed raw; reviewer never rescanned /proc or inferred exit solely from present absence/time. All stdout/stderr/intent/child/receipt and fifthoracle bytes match committed evidence. No unknown cleanup, fallback rescue, foreignPID targeting or resource residue appears in the scoped evidence.

This demonstrates real termination/reap for these single-child cases, including TERM refusal and deferred cancellation. It does not prove parentSIGKILL/crash recovery, process trees, hostile/native programs, WindowsAPI lifecycle, hard real-time scheduling or arbitrary OSfailure behavior. The controller explicitly makes none of those claims.

## Finalized producer correction and old attempts

Finalized Git correctionf820fd74a0e1ec364d18ea329c61470e0bdbf00a SHA51d3264c94eb24daa9a9d14dd2782658cb09aa5d33cf5bcf62f21d3d6157443f matches its already-reviewed source binding. Original combined02 navigation084bb63e… remains unchanged; all9 recorded JSON-pointer values match immutable3160d938 original. Correction distinguishes configured timeout, caller yield/background, termination and reaping; it records the unfrozenprobe's naturalexit and omittedcdprefix honestly. No partial implementation file was read and no194raw was redone here.

Numerical/provenance correction and actual control mechanism are qualified pieces of CP10-M1 remediation. Oldcombined01 remainsNOT_QUALIFIED, oldcombined02 hardcontrolNOT_ESTABLISHED; this selftest does not retrofit a supervisor into those Bash calls or overwrite historical failures. Current194 functional/CPUcleanup datasets remain supported; oldtargeted07 cause remainsUNDECIDED. Formal ledger/gate disposition belongs to root; no Major was silently downgraded toMinor.

## Precise future admission and minimal remaining proof

1. Freeze a **new integration request** with this exact controller/interpreter, intended real child Popen argv/cwd/replacement env, guard/runner/source/dependency pins, all outputs and workload denominator. The actual supervised child must be the pinned guard→runner Python chain, not a shell wrapper that leaves an unowned workload elsewhere.
2. Require the guard's closed no-spawn/native-loading profile before candidate imports. This mechanism targets one actual owned child; it supplies no descendant cleanup guarantee. Preserve ordinary-denial hard veto, mandatory singleton/CLOSED facts, result identity and existing failure/cleanup predicates.
3. Put immutable trusted control intent/child/signal/reap receipts **outside the child's permitted write root**, with fresh canonical owned paths and no journal handles inherited by the child. Payload/evidence roots are distinct; passed stdout/stderr handles are logs, not trusted control state. Cooperative guard limits remain explicit rather than an OS privilege-isolation claim.
4. Budget wall+TERM+KILL inside the frozen envelope (for290s, an existing documented example is288+0.5+1=289.5s, plus separately budgeted outer work). Caller wait/background settings do not own the deadline. Cancellation/timeout/nonzero/unknownreap remains failed workload, and incomplete journal/identity/cleanup must block.
5. If root needs an accepted **supervised full194 component checkpoint**, the missing proof is one separately sealed actual controller→guard→runner194 integration with these control receipts and current exact194/192functional/2integrity accounting. Old194 functional outcomes cannot prove a new enclosing supervisor was actually present. No automatic new194, canary or historical rerun is issued by this review; root decides and authorizes the concrete next scope.

The five-case proof is sufficient for the declared narrow mechanism, not the future integration step. Product29, native9, Gate0, Stage/N2 and human obligations remain unproved. No budget reset or full productcheckpoint credit follows.

## Full V0–V3 outline

Authoritative counts: V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1 0/4; V1-M1 0/3; R2 0/4; R3 0/4; R4 0/4; R5a 0/4; R5b 0/4; R5c 0/4. V0-S0 historicalNO_GO and S2 signoff scope remain; currentR1 remains0/4. Prior unified-media early3/3/UM10 alone has actual human signoff. This control review advances no product counts/signatures.

## Ten fields

1. Coordinate: V1/R1/WP-R1-U3/S3_P4, actual trusted-control review03.
2. Last passed product scope: unified-media UM10 early slice only.
3. Current batch: five actual short control cases independently5PASS/0FAIL/0retry; no new execution.
4. Blockers: none effective for narrow mechanism; supervisor+guard integration and formal control checkpoint still pending.
5. Route: root freeze exact next integration/admission only if needed.
6. Remaining: actual supervised workload controljournal/guard/result binding; product/native/formal obligations.
7. Next owner: root trusted-harness/gate owner; no automatic implementation or runtime handoff.
8. Authority: no runtimeACK, newrun, Stage/N2 or human/product signature issued.
9. Evidence: report.md,receipt.json,findings.json,recomputation.json and immutable444410f actualrun.
10. Stop: QUALIFIED_NARROW_ACTUAL_SINGLE_CHILD_CONTROL,F0/M0/m0; oldattempts unqualified and integrationpending.
