# Combined02 control/provenance review

Fatal0 / Major1 / Minor0. Actual fresh194 functional/count/CPUcleanup evidence is independently supported. **A hard-controlled checkpoint is not established**: exact timeout values were accepted, but a background-yield timeout was misread as termination proof, an unfrozen probe was added, and exact-command provenance is overstated. These are consolidated as CP10-M1. Root has not waived hard-stop semantics. Originalcombined01 stays NOT_QUALIFIED.

Candidate b9a81aed8e8f8fe6763a4dfd3d051cacf10e0820; correction768659217aa17f7baf30224c5c9b502bac8ce1ba; evidence3160d9380b3810e6d9d3f8f57ed8773839954521; planSHAfe0f03d14b5a57b7463f342507294e409a9ac7dc38f3ec0f233533f2510cf34f; literal inputsSHAe3dc059b1cc394553ebe10add80a74c7f161721ffc71ac795ad314e277525db8. No candidate/guard/runner/emitter/probe was replayed, imported, compiled or collected. Only existing raw/Git/Orca transcript and bounded stdlib recomputation.

## CP10-M1 — Major: timeout semantics, scope and provenance

Expected: the frozen finite envelope must have an actual stop/termination owner, the exact inputs and truthful cleanup/provenance. Actual: five original Bash timeout parameters match5000/290000/5000/5000/5000. This closes the **parameter mismatch in the new calls**, not the missing enclosing termination guarantee. Shorter actual runtime and caller return cannot establish that guarantee.

Exact immutable Orca archive (dispatchctx_f18d235adb9a, sourceIdentityuDd-pDDTLHahNJxdmsAP8En4ArLqnJZg, sourceExact/archive true) records extra probe call_01a1e025d24c76ec95929612 at16:58:57.832UTC:

`date -u +%H:%M:%S.%N; sleep 6; date -u +%H:%M:%S.%N`, Bash timeout5000.

At16:59:02.896 the tool result explicitly says the command did not complete within5s and was **moved to the background**, taskbqf273a7s. It does not say killed. Its existing owned task-output file records16:58:57.873092377 and16:59:03.876534983, followed by exited code0. The6.003442606s duration and second date support natural completion of this simple sequential probe after the5s return threshold. This is evidence of continuation beyond5s, not enforcement of5s termination. No lingering probe-process claim is made; elapsed time alone was not used as cleanup proof. Worker lifecycle is separately released/exited and does not itself prove command-tree cleanup.

The probe was absent from the frozen five commands. Checking compatibility did not authorize a new runtime probe; the executor had a STOP path for incompatibility. The command also produced tool-managed stdout in /tmp/claude-1000/.../tasks/bqf273a7s.output. Its receipt's “plain sleep/touched nothing” description omits date operations and managed output. No private/product-data write or harmful network/service side effect is inferred.

Combined02 navigation /the_control_envelope_of_this_batch/the_capability_probe_that_was_run_before_the_batch calls backgrounding proof that the cap is “accepted and enforced.” That inference is false as termination evidence. The experiment establishes one observed5s background transition; it does not prove all timeouts always background or establish what290s would do. Existing guard/runner and records show no independent enclosing290s termination/reap mechanism. Actual guard55.397374868s/runner55.284785271s and clean termination are real facts, but cannot fill that control gap.

Additionally, original five command strings omit the frozen leading `cd <pack> &&` while preserving the remaining env/argv/redirections. They are not verbatim literal commands. Inherited shell cwd may have been correct (no source misbinding alleged); navigation /the_execution_binding/the_five_renderings nonetheless overclaims exact literal input execution. Description-field formatting is not elevated into a separate issue; the actual command omission and control interpretation are part of one executor/provenance root finding.

Oracle: separately verify parameter equality, timeout action, owned termination/reap and exact command input. A stuck run must not continue indefinitely simply because a tool yielded/backgrounded. All evidence and call IDs are in recomputation.json; full original provider inputs are linked by the same call IDs as the archived Orca transcript, whose large-input view is clipped. No invented complete archive fields are supplied.

Minimum remedy: preserve all bytes; producer append an attributed correction distinguishing parameter conformance from unproved hard-stop, unfrozen actual probe, its natural exit and tool-owned output, and omittedcdprefix. Root should first establish any actually enforceable existing stop primitive from source/contract/recorded termination evidence. If none exists, freeze the smallest trusted enclosing owner for this CPUchild: explicit monotonic deadline, independently held child/process-group identity, bounded stop escalation/reap, and failure receipt when termination/cleanup is unknown. This belongs outside candidate-controlled work and must not mistake a wait timeout for termination. Any necessary control check gets its own finite freeze; this review authorizes no probe or automatic new194 and requests no product/native sandbox framework.

No actual batch overrun, candidate semantic failure or current resource leak is inferred. Major remains appropriate: required finite control and honest scope are core, and an actualPASS194 cannot use ADR16's realFAIL-only auxiliary-Minor exception.

## Prior correction and current raw binding

Correction9246305899c159e853b7182938291dca7bf6741b13fcae6ecc37a355da1823a3 matches correctioncommit7686592 and binds unchanged original navigation833fb339089c9c510c87bce5a3bbce8594d268ef7c5ad0619f4b105426ba911a. Its five /the_commands/0..4/timeout_ms pointers correctly distinguish oldactual30000/300000/30000/30000/30000 from frozen5000/290000/5000/5000/5000. Attribution is not a cryptographic signature. Thus append-only numerical provenance is verified; its use of “kill cap” does not newly prove termination semantics. Root's prior NOT_QUALIFIED disposition and oldraw remain intact, with no retrospective conformance or automatic Major closure.

All338 new entries match evidence3160d938 blobs;104 symlink blobs were compared as literal link text. All61 source pins match (60 exact Git files+externalinterpreter), tools5/deps223/stdlib3/history10 match. Candidate/source/dependency/stdlib/history and tool hash multiset equal prior qualified scope. This supports reuse of14e65/a52 source qualification without wholesale repetition. Production broker/custody and test wiring remain unchanged.

Current combined02 selected/collected/called order exactly194 unique=189original+5SUP. All194PASS,0failed/skip/missing/duplicate/unexpected,2 integrity-only and192functional=187originalfunctional+5SUP. All reports were checked; no separately recorded successful setup/teardown phases are fabricated. All machine counting/inputhash/outer predicates independently recompute with no mismatch. Outererrors[] and accepted_cpu_feedback=true describe selected checks, not hard-stop admission. No oldcombined01/targeted raw is substituted.

Original five tool calls at16:59:17.473,17:00:08.731,17:02:56.495,17:03:44.185,17:03:56.635UTC have the correct timeout values and non-error completed results. Exact env-i seven-key dictionaries, argv and remaining redirection strings match; literalcdprefix omission remains above. Raw command records, not navigation alone, bind the parameters. No timeout termination branch was exercised by the batch.

Ordinary guard ledgerEMPTY; exact singleton ctypes.dlopen(None) once/CLOSED and8 startup refusals.106 bounded alias admissions satisfy same canonical owned parent, numbered directory/current prefix, defaultdirfd and parentidentity.104 terminal links match latest admissions;2 records were superseded, not missing terminal links. Admission records are not themselves completed-syscall receipts. FD inventories known/equal withunknown[], new_or_reused[], MainThread only, CPUcleanuptrue. Exact counter/parent absence observations equal; no content read/create/reset/refund/continuity claim. Present source/history/metadata agrees with navigation but cannot alone prove arbitrary past ownership; unrelated dirty report body was not read or staged.

## Current branch facts and preserved boundaries

Combined02 main owner raw independently shows alive/unfinished before expiry, then finished/dead/errorNone/frames2 at body, exact context/broker/background/observer STARTED identity and SAME pointer with no body join. Separate salvage real joinTrue/errorNone at54121.27995672 and pointerABSENT, quiescenttrue/originalNone/proofNone. Thus later cleanup is not body proof. BodyABSENT conditional remains static; oldtargeted07 cause staysUNDECIDED.

Current public zero_session remains distinct real production chain with producer/pump hold, exact0 waits, actual owner identity/start/context/error facts and returned UNKNOWN_RETAINED/broker retention preserved. CurrentSUP01/02 keep exactO/firstK priority, exact expectedpipeworker identity, queryUNKNOWN/failed durable proof separate from actual cleanup. SUP02 once-only K1 and real third-callback controlled repeat remain executed. SUP03 actual designated inner-writer injection and SUP04 recoveredfinalwrite retain sentinel/error/failedproof/quiescence; SUP05 exact independently expected startupowner/thread and real settle/join fallback remain executed.28 relevant current phase documents are hashed/summarized in recomputation.json. T07-M1/M2 source/branch qualifications remain valid; they do not decide control-plane CP10-M1.

Functional194 and CPUcleanup stay supported. Oldcombined01 remainsNOT_QUALIFIED and newcombined02 hard-controlled checkpoint isNOT_ESTABLISHED pending root action. Product29/native9/Windows-real production cleanup/Gate0/N2/Stage/human acceptance remain unproved. Guard remains cooperative Python checking, not native/adversarial/fd/race containment. No budget reset or extra productcheckpoint credit follows.

## Full V0–V3 outline

Authoritative counts: V0-S0 1/2(historicalNO_GO), V0-S1 5/5; R0 1/2,R1a5/5; V0-S2 7/8,V0-S3 0/6; currentR1 0/4,V1-M1 0/3,R2 0/4; V2 R3/R4 each0/4; V3 R5a/R5b/R5c each0/4. Prior unified-media early3/3/UM10 alone has actual human signoff; product counts/signatures are not advanced.

## Ten fields

1. Coordinate: V1/R1/WP-R1-U3/S3_P4, focused control review10.
2. Last passed product scope: unified-media UM10 early slice only.
3. Current batch: combined02 actual194PASS/CPUcleanup independently confirmed; control qualification held.
4. Blocker: CP10-M1 timeout/background semantics, unfrozen probe and exact-input provenance.
5. Route: root trusted-control adjudication and append-only producer truth correction.
6. Remaining: real enclosing stop/reap evidence, then separately frozen action only if needed; product/native/formal obligations remain.
7. Next owner: root trusted harness/control owner; executor append correction.
8. Authority: no own runtime/probe, runtimeACK, Stage/N2/human clearance.
9. Evidence: newreport/receipt/findings/recomputation plus immutable3160d938 and exact Orca archived tool records.
10. Stop: CHANGES_REQUIRED; functional194 preserved, hard-controlNOT_ESTABLISHED, independentF0/M1/m0; no automatic new194.
