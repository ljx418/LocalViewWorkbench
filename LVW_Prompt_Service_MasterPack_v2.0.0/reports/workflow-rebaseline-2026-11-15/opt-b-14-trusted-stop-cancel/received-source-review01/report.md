# Trusted single-child stop — source readiness

**NOTREADY — Fatal0 / Major1 / Minor0.** One resource-ownership cancellation gap must be corrected before the conditional four-canary activation. No controller/canary/candidate import, compilation, process launch, probe, test, owned-process scan or other runtime occurred. Hash/JSON/AST reading only. This is root-owned harness source review, not product implementation or a new194 run.

Plan SHA256`4bdd36852b95caeef6bb89c398dd4715d80d293adae19ec41e3a08bfdc936606` matches frozen4bdd3685…. Both controller/canary pins, interpreter pin and all4request hashes match. New runroot is absent at review. Conditional rootACK explicitly has actual_permission_to_launch_now=false and requires independentF0/M0; that condition is not met. Exact hashes/requests/AST checks are in sourcecheck.json.

## CTRL01-M1 — Major: cancellation can lose the just-created child

Location: bounded_exec.py:70,74-88,106-114; CPython3.12 subprocess.py:1026-1067,1120-1133,1885-1895. Trigger: an ordinary parent TERM/INT arrives after Popen created the child but before its constructor returns into `proc = subprocess.Popen(...)`.

Expected: retain the exact child despite cancellation, then perform bounded stop/reap with truthful ownership and failure facts. Actual: handler74-75 raises InterruptedError immediately. While the RHS constructor is still running, local proc remainsNone. The outer except records CONTROLLER_ERROR, but finally114 requires proc is notNone and therefore skips TERM/KILL/wait for the already-created child. It also lacks that child's PID/birth journal for recovery.

This is supported by the installed interpreter's source, not a guessed Popen guarantee: child creation occurs within _execute_child before constructor return. Constructor exception cleanup closes descriptors and re-raises; destructor polls and can retain a still-running process in _active instead of terminating it. No later Popen is required to occur in this controller. Because start_new_session=true, parent cancellation is not an implicit signal to that child. In-scope term/ignore-term child code can continue indefinitely after this failure path. The controller returning1 is honest failure, but does not satisfy cleanup/retention. No actual leak or reproduced timing is alleged.

Oracle/negative: cancellation at the created-before-published boundary must keep the original actual child and execute its bounded stop/reap, or retain exact recovery identity with STOP_UNPROVEN. A repeated ordinary cancellation must also not interrupt transition into mandatory cleanup. No foreignPID scan, replacement lifecycle or unsupported parentSIGKILL/descendant/native guarantee is requested.

Smallest fix: defer throwing TERM/INT exceptions during construction/publication, retain pending cancellation until the exact Popen/PID/recovery facts are safely held, then consume it immediately using existing cleanup. Make entry into mandatory cleanup nonthrowing for repeated cancellation. Keep the child's original signal semantics; blindly masking across fork/exec can leave child signals blocked, so any chosen approach must handle that explicitly. No new platform framework is needed. Root should rehash/re-freeze changed controller and request source readiness again before any activation; this report does not add or run a new signal probe. A later specifically frozen negative can check this boundary if needed.

The same asynchronous exception root affects the narrow transition before finally installs ignored handlers; it is grouped here, not a second per-line finding. Ordinary TERM/INT and exception cleanup are explicitly claimed in the current scope, unlike parentSIGKILL/crash. This is therefore a required resource-control issue, not an auxiliary Minor.

## Positive static assessment within declared scope

Once proc is successfully retained, the design is appropriately small: argv list/absolute executable, exact cwd/env and no shell; wall deadline taken with monotonic clock before Popen; one new-session child with close_fds and DEVNULL stdin; exclusive fresh output directory/intent/stdout/stderr/child/receipt files. It never sends to a supplied externalPID or process group. PID/birth/session/group are journaled; birth parsing correctly takes field22 after final')'. Kernel ownership of an unreaped single child supplies targeting, while birth remains a diagnostic used by the independent selftest oracle.

SIGCHLD default prevents inherited SIG_IGN auto-reaping in this fresh single-threaded owner. poll/send_signal/wait operate on the same retained Popen; local CPython send_signal polls before kill. With no other reaper/child in declared scope, an unreaped child's PID is not recycled to a foreign process before signalling. Exited children are polled/waited rather than blindly signalled. There is no group-wide kill or descendant-tree claim.

Initial wait is cropped to remaining wall deadline. Timeout sets DEADLINE_EXPIRED/timed_outtrue, then finally attempts TERM grace and KILL grace with bounded wait/reap. Unknown reap becomes STOP_UNPROVEN and exit1. Nonzero remains EXITED_NONZERO and exit1; deadline cleanup success does not become EXITED_ZERO. Other caught errors become CONTROLLER_ERROR. Positive workload exit requires EXITED_ZERO and reaped. Required identity/ready/receipt facts still must be checked independently; exit0 alone cannot override a missing journal or raw result.

File setup failure before Popen creates no child; missing final receipt remains failed evidence. Birth/session metadata can be missing in an error case; future root oracle must reject missing required identity rather than infer successful cleanup. This source-readiness review does not demand adversarial path confinement for trusted frozen output roots or full descendant/native control.

## Four-case plan and real-call semantics

Each frozen controller argv is `/usr/bin/python3.12 -I -B bounded_exec.py <exact-request>`. Each request launches the actual control_canary.py with one of normal,nonzero,term,ignore-term, exact pack cwd and replacementPATH/HOME/PYTHONDONTWRITEBYTECODE environment. Output is a separate direct child of NEW runroot for every case. Four cases/0retry; wall0.5+TERM0.2+KILL0.5=1.2s each, total4.8s of execution+graces within20s plan. Process-start/OS-scheduling latency is explicitly not a hard-real-time guarantee; no silent deadline increase is justified if a canary is not ready in time.

Canary emits real PID,parent,session,group,birth,mode and ready=true with flush. Normal/nonzero then exit0/13. TERM-responsive mode keeps default TERM behavior and loops; ignore-term installs SIG_IGN **before** ready and loops. Expected actual return statuses are0,13,-15,-9, controller exits0,1,1,1, exact signal sequences[],[],[TERM],[TERM,KILL]. Negative workload outcomes are expected canary control observations, never successful product work.

The plan requires actual ready/identity matching childjournal, expected signal/outcome, waitpid reap, exact ownedPID/birth no longer present and no foreign targeting. Those are future runtime oracles, not source facts. Present source cannot demonstrate them without the separately activated selftest, and source-only AST validity is not runtime proof. Four normal/deadline cases do not themselves exercise ordinary parent cancellation at construction; successful cases later would not automatically close this source gap.

A corrected supervisor plus successful actual selftest could support **future newly sealed** single-child cooperative guard/no-spawn admission, with wall+bothgraces included in the envelope. It would not retroactively qualify old Bash calls, establish parentSIGKILL/adversarial/native/descendant behavior, or grant Stage/N2/product acceptance. CP10-M1 remainsOPEN; both old194 functional/CPUcleanup datasets remain supported, while old hard-control qualifications remain withheld. Claude's concurrent append correction was not read as a final product or modified.

## Required next action and limits

Root owns the focused cancellation/publication fix and new pins. No selftest launch is ready now, and no automatic194 rerun is requested. Preserve source revision/history and all prior findings. Actual unknown cleanup always blocks; no unsupportedOS guarantee, new diagnostic framework or product change is added. This report issues no runtimeACK, rootactivation, Stage/N2 or human signature.

## Full V0–V3 outline

From authoritative execution-control: V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1 0/4; V1-M1 0/3; R2 0/4; R3 0/4; R4 0/4; R5a 0/4; R5b 0/4; R5c 0/4. V0-S0 historicalNO_GO remains; S2 signoff boundary unchanged. CurrentR1 is0/4; prior unified-media early3/3/UM10 alone has actual human signoff. No counts or signatures advance here.

## Ten fields

1. Coordinate: V1/R1/WP-R1-U3/S3_P4, trusted-control source readiness.
2. Last passed product scope: unified-media UM10 early slice only.
3. Current batch: source-only controller/canary/4request review complete; runtimeNOT_RUN.
4. Blocker: CTRL01-M1 cancellation before child ownership publication.
5. Route: root minimal source correction, re-freeze, independent readiness, then separate conditional rootactivation.
6. Remaining: actual4case ready/identity/signal/reap outcomes; existing control/product/native obligations remain.
7. Next owner: root trusted-harness owner; implementation receipt correction remains separate.
8. Authority: no process launch/probe/runtimeACK/Stage/N2/human acceptance issued.
9. Evidence: report.md,receipt.json,findings.json,sourcecheck.json in this new directory; frozen4bdd3685 plan and exact root pins.
10. Stop: NOTREADY,F0/M1/m0; CP10-M1OPEN and no automatic next run.
