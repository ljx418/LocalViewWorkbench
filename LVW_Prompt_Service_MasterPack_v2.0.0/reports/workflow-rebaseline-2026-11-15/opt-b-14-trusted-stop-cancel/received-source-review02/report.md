# Deferred-cancellation controller — focused source readiness

**READY for conditional root activation of the frozen five-case feedback only — Fatal0 / Major0 / Minor0.** CTRL01-M1 is CLOSED_STATIC for this revision; runtime cancellation/termination/reap evidence is still pending. This review launches nothing and issues no runtimeACK or rootactivation. CP10-M1 staysOPEN; old194 functional/CPUcleanup facts survive and old hard-control attempts stay unqualified.

New controller SHA256e3b18a954084c5c89ff1cf7f35e719d4669c8e6df21e652b4d6d54014ff48ba1 and planSHA5e1ee44d5f6a8bdc48061e2153f61e83d20fc45270a8258b1e1894e0e7d6cd59 match. Controller/adapter/original leaf-canary pins, interpreter and all5requests rehash correctly. Old opt-b-13 source4323d266… and plan4bdd3685… are preserved byte-for-byte; old/new runroots are absent at this read. Conditional rootACK explicitly has actual_permission_to_launch_now=false. No controller/driver/canary/candidate import, compile, collection, runtime, process scan,194 rerun or probe occurred. AST/JSON/hash/static reading only.

## Prior ownership finding and corrected flow

Prior cc403e6 CTRL01-M1 concerned a throwing parent signal handler interrupting Popen after child creation but before local proc publication. At bounded_exec.py:74-82, TERM/INT now only append to pending cancel_signals. They cannot raise InterruptedError across real Popen construction, assignment, PID/recovery journal or cleanup entry. No signal mask is applied or inherited by the child.

At84-86, cancellation already known at the early check avoids launch and returns failure while finally still publishes facts. At92-105, the exact factory return becomes proc and its PID/birth/session/group journal is written before the pending cancellation check. At106-123, pending cancellation immediately selects CANCELLED; otherwise waits are cropped to remaining monotonic deadline and50ms, and a cancel recorded during wait is consumed before success is selected. At127-160 the same nonthrowing handler remains active through bounded TERM/KILL/wait and receipt publication. Repeated ordinary signals cannot throw past cleanup entry as before. Return0 requires EXITED_ZERO, actual reaped state and no recorded cancellation.

These changes address the specified asynchronous ownership gap without changing the owner lifecycle or hiding errors. Once a child is retained, ordinary exceptions still select CONTROLLER_ERROR and finally targets only that owned Popen; unknown reap becomes STOP_UNPROVEN. Cancellation or deadline cleanup success does not become workload success. Normal0/nonzero13 distinction remains, and actual deadline/negative child returns remain failure outcomes.

Same declared safe scope is retained: Linux cooperative one child, SIGCHLD default, no externalPID/group kill, owned unreaped-child targeting, journaled actual identity and exclusive new files. Installed Popen poll/send_signal/wait behavior was read without execution. No arbitrary partial-factory failure, external reaper, hostile child, descendants, parentSIGKILL/crash or hard real-time Popen/scheduling guarantee is added. Output/setup/receipt failures remain missing or failed evidence, never automaticPASS.

## Fifth canary drives the actual boundary

cancel_publication_canary.py imports only the hash-frozen trusted rootcontroller; it imports no product. observe_real_creation24-31 calls real subprocess.Popen with the controller's original args/kwargs, independently retains that exact object, sends actual SIGTERM and SIGINT to its own controller process **before returning**, then returns the same object. Controller proc assignment has not executed while these signals are delivered. This is the intended created/pre-local-publication seam, not a fake lifecycle, mock child or independently launched replacement. The CLI default factory remains realPopen.

The fifth request's actual child is the pinned leaf-canary in term mode. User-code ready output is not required for this boundary case because the real kernel child can be cancelled before its Python ready line; actual Popen/PID and reap still are required. Adapter expects one held actual child, controllerexit1/CANCELLED, exact retainedPID, signals[TERM,INT], reapedtrue, matching negative actual returncode(-15 or-9), no errors and no live-child rescue. It calls the existing controller cleanup, not a parallel successful lifecycle.

Adapter rescue39-51 is bounded toTERM/KILL with0.3s waits and sets fallback_used before signalling a still-running child; passed requires notfallback_used. A rescued live child cannot turn the regression intoPASS. The initial poll is capable of waitpid(WNOHANG) reap: fallback_used therefore measures live-child signal/wait rescue, not every waitpid observation. It must not be used alone as an independent certificate that the controller performed a reap. Current frozen success additionally requires the controller's CANCELLED/reaped/returncode receipt, same actual Popen result and the inspected real wait path. Future actual review must consume those facts, journal and exact owned identity, rather than a lone passed flag. No source execution or hypothetical altered-controller result is treated as evidence here.

## Frozen five-case plan and budget

All5 requests and controller/driver argv/cwd/env/output routing were checked independently. The firstfour requests retain the old child semantics, limits and expected outcomes, changing only fresh output paths and controller source location. Modes: normal0/controller0; nonzero13/controller1; TERM-responsive deadline(-15/controller1); TERM-ignoring deadline(-9/controller1). IgnoreTERM handler is installed before ready output. The fifth uses the real parent-cancel adapter and expects a negative CANCELLED controller outcome while the adapter's regression result is successful only when the required failure/cleanup behavior occurs.

Each case uses wall0.5+TERM0.2+KILL0.5=1.2s; five total6.0s. Including the fifth's failed rescue path0.6s gives6.6s, within the frozen20s plan,5once/0retry. Startup/OS scheduling latency is not a hard-real-time promise; failure to establish required ready/identity in an actual case must fail honestly and never trigger an undeclared timeout increase or retry. Every output directory is a direct distinct child of NEW runroot; oracle file is fresh exclusive output there. Caller wait/background behavior is not the stop owner.

Actual root verification must match controller/child ready identity for firstfour, kernel-created identity for fifth, exact expected signal/status/returncode, bounded actual wait/reap, no adapter rescue, required receipts and exact ownedPID/birth absent after reap. Unknown cleanup, unstarted/foreign/replacement child, missing journal or failed raw blocks. Source readiness supplies none of these runtime facts. Rehash pins and obtain separate rootactivation before any case; this review does not activate the conditionalACK.

Successful actual short selftest could qualify this narrow trusted mechanism for a **future newly sealed** cooperative no-spawn child profile, with cleanup graces inside the admission budget. It could not retroactively qualify oldcombined01/combined02, decide oldtargeted07 cause, prove native9/product29, or clear Stage/N2. No automatic full194 run is requested.

## Optional finalized producer correction

Readonly exact Git blob f820fd74a0e1ec364d18ea329c61470e0bdbf00a was checked, not a partial implementation workfile. CorrectionSHA51d3264c94eb24daa9a9d14dd2782658cb09aa5d33cf5bcf62f21d3d6157443f matches, binds original combined02 navigation084bb63e4928258315b170cfe051130f5d2d6bdda013cf64fa7b740a044d7f9a from evidence3160d938, and all9 recorded JSON-pointer values match that immutable original. It distinguishes timeoutparameter/background/termination/reap, unfrozenprobe naturalexit and omittedcdprefix truth. This is verified append provenance only; no194raw was redone, no oldbytes rewritten and CP10-M1 staysOPEN pending actual trusted-control proof/adjudication.

## Exit and limits

No effective Fatal/Major in this corrected source+five-case freeze was found. CTRL01-M1 is CLOSED_STATIC, not dynamically closed. No Minor downgrade was used. Root owns activation and subsequent actual evidence review; current source readiness cannot authorize newruntime itself. Existing functional/CPUcleanup facts remain supported, old hard-control qualification unchanged, product/native/parentcrash/descendant/adversarial limitations retained.

## Full V0–V3 outline

Authoritative counts: V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1 0/4; V1-M1 0/3; R2 0/4; R3 0/4; R4 0/4; R5a 0/4; R5b 0/4; R5c 0/4. V0-S0 remains historicalNO_GO; currentR1 remains0/4. Prior unified-media early3/3/UM10 alone has actual human signoff; no product count, machine acceptance or signature advances here.

## Ten fields

1. Coordinate: V1/R1/WP-R1-U3/S3_P4, corrected trusted-control source readiness.
2. Last passed product scope: unified-media UM10 early slice only.
3. Current batch: source-only review complete; actual5caseNOT_RUN.
4. Blockers: none effective for conditional short feedback source readiness; actual control proof and CP10-M1 remainOPEN.
5. Route: root pin recheck/activation, frozen5once0retry feedback, independent actual review.
6. Remaining: real signal/identity/reap/noresidue evidence and formal control adjudication; no automatic194.
7. Next owner: root trusted-harness owner and exact selftest executor after activation.
8. Authority: no runtimeACK/rootactivation/Stage/N2/human signature issued.
9. Evidence: report.md,receipt.json,findings.json,sourcecheck.json in this new directory and exact root pins above.
10. Stop: READY_FOR_CONDITIONAL_FIVE_CASE_SOURCE_FEEDBACK,F0/M0/m0; CTRL01-M1CLOSED_STATIC and runtimepending.
