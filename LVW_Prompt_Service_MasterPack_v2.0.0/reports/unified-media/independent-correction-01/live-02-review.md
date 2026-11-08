# Independent live-02 blocking review

Product candidate: `87c64a311e1608dc6abfc9a35fb6651eedb92307`.
Bound executing harness SHA256: `9a36943bd053c3893c85cb313847453b9a7dd22a83ef2a00fc0636792caacc3a` (recomputed from the candidate Git blob, not the later edited working file).
Review result: **NO_GO / real acceptance incomplete**. Fatal 0 / Major 1 / Minor 0 for the reviewed evidence/harness. This does not reopen the corrected product code findings; it identifies an evidence-retention defect in the checkpoint. No Stage PASS, UM10/10 or human signature.

No new service, model, GPU, browser, network or holdout execution by this reviewer. Read original raw files and candidate source; computed hashes locally. Independent earlier worktree remains `/tmp/lvw-independent-87c64a3`.

## Supported facts

- Authorization and receipt bind the above candidate. Candidate build_id independently recomputes to `9390c759a1b64c7bd2cee25037672c3907c24dc4ef932b072051694cf92e75ce`, exactly the recorded /health result. Program, packet-manifest, all four sample hashes, bindings SHA and native icon blob match. Launcher content matches the candidate after Git LF/working-file CRLF normalization; raw binding hash matches the actual CRLF file. Current harness changed subsequently, but the authorized historical harness is recoverable and matches its SHA.
- launcher.log records actual START_LVW -> WSL/default FastAPI API PID 1339082, public media endpoints, production React JS/CSS and browser requests. It records model runtime start 200, image upload 201, analyze 202, job query 200. Runtime-start records managed Windows PID 29484, installed model ready, model_loaded=false. This proves a live startup chain, not successful inference.
- Native stderr directly reports OLLAMA_HOST=http://127.0.0.1:11434, OLLAMA_NO_CLOUD:true, NO_PROXY:127.0.0.1,localhost, cloud disabled true and Listening on 127.0.0.1:11434. Thus the prior environment transport correction now has native server evidence. No inference performance/quality conclusion follows from startup.
- The public over-duration and corrupt files return 422 with VIDEO_DURATION_LIMIT and VIDEO_PROCESS_FAILED. These two real negatives are supported. Receipt's UM-02 PASS must be read as these partial checks plus separate offline coverage, not proof that every media-limit obligation was exercised live.
- Browser-result is NO_GO with empty completed-checks array. The browser assertion fails on missing machine suggestion (0 instead of 1). Its captured DOM shows failed image task, progress 0/1, RESOURCE_BUSY, resource released, and the manual sentinel LIVE_MANUAL_KEEP intact. No adopted image/video output, video PTS result, real cancellation, post-adoption export or offline-export sequence completed.
- No provider.jsonl is archived. START_LVW explicitly configures its run-local path and provider emits its first events after admission; absence is consistent with failure before lease acquisition/provider start. This is consistent with zero model requests, but it is not a complete request trace or resource measurement. Do not claim a successful GPU lease/release from absence of a ledger.
- Separate later diagnostic receipts show free 14023/14054 MiB, below the unchanged production admission requirement 19047 MiB by 5024/4993 MiB. Used GPU is 10116/10085 MiB and available RAM 10527/10544 MiB. These snapshots support a later capacity blocker. They are not the original acquisition snapshot: the exact failed branch (loaded inventory versus free capacity or another rejected admission condition) was not recorded. Native startup also reports a different available-GPU value (22.5 GiB); these tools/times cannot be substituted for one another. No threshold reduction is justified by this evidence.

## Major L1 — native terminal proof was archived before shutdown and then deleted

Location: bound `reports/unified-media/live_checkpoint.py:70-94`, particularly runtime-evidence copy before API SIGTERM; `START_LVW.cmd` removes RUN_ROOT when WSL exits.

Trigger: browser/checkpoint fails while the owned native Ollama is still listening, as happened here.

Expected: preserve the native nonce/PID/birth bound terminal owner proof after shutdown before deleting the temporary root, together with before/after evidence. Do not treat wrapper/API termination or listener disappearance as equivalent to native terminal proof.

Actual: archived owner `runtime-evidence/7ea5fb1c70574abf845b58f7ac28d98d.owner.json` has state=listening, listener_owned=true, PID=29484 and birth_ticks=639297419639508247. The finally block copies this before signalling API shutdown; afterwards the production launcher deletes the run root. No archived state=exited owner exists. Therefore the parent's statement that original native owner exited cannot be directly recomputed from the supplied raw owner artifact.

Reproducible evidence: inspect the above JSON and compare bound candidate harness line ordering. `live-02-recomputed.json` independently records owner_states=[listening]. The source's runtime.close requires exited proof, and launcher.log records graceful application shutdown without exception; this is indirect support that cleanup occurred. It does not recover the deleted raw native terminal record. Receipt additionally asserts both listeners absent and run_root_removed=true, but it contains only booleans, not raw native exit output. This finding is an evidence-capture defect; no claim that an orphan was actually left behind is made.

Required correction before the remaining checkpoint: retain terminal owner/log evidence after product runtime shutdown and before run-root deletion, without modifying historical live-02 files or killing foreign processes. Preserve the original listening artifact and failure. Do not rerun solely to retrofit proof into live-02.

## Cleanup and slot conclusions

Browser-result records browser_closed=true, no page errors or external requests; launcher.log records API shutdown complete and finished PID. Receipt reports API/Ollama listeners absent and run root removed. These support cleanup at the recorded levels; native original-process terminal evidence remains incomplete under L1. No GPU three-sample baseline release proof was produced, and none is required to be fabricated for this admission-rejected attempt.

live-01 receipt has stage_checkpoint_consumed=false and no API/model sequence; live-02 has true and reached the real sequence. Under the updated authority's explicit rule, independently counted full slots consumed=1, launcher attempts=2. Its maxima (<2 consumed, <3 attempts before create) leave only the named live-03 correction slot. This is a budget accounting observation, not execution authorization or a reason to lower admission. Missing receipts/default missing consumed flag count as consumed. The updated authority is a later harness revision and is not retroactively the code that issued live-02.

UM-01/03/04/05/06/07/08/09/10 cannot be signed complete from this failed sequence. UM-02 has two real public negatives plus offline evidence, with the exact boundary above. Static corrected-candidate review remains separate from real acceptance.

## Required project status

V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1/R2/R3/R4/R5a/R5b/R5c each 0/4; current R1. No count increment from live-02.

1. Coordinate: R1 / unified early slice, real checkpoint NO_GO.
2. Completed: candidate/harness/sample/build bindings and startup/no-cloud/failure evidence independently recomputed.
3. Last passed gate: R1_UNIFIED_GATE0 scope approval only.
4. Blocking gate: resource admission / incomplete real sequence, plus L1 raw terminal-proof capture.
5. Route: V0-Min and single-image R1a historical acceptance retained; full R1/V1 incomplete.
6. Remaining: evidence-capture correction, truthful capacity readiness, bounded remaining fresh checkpoint if admitted, independent recomputation and unified human signature.
7. Next owner: gate owner/trusted executor; no real execution initiated by reviewer.
8. Authorization: reviewer used read-only CPU hashing only; slot counts are not authorization.
9. Evidence: independent-correction-01/live-02-review.md, live-02-recomputed.json and live-02-evidence-hashes.json.
10. Stop: NO_GO_RESOURCE_ADMISSION_AND_NATIVE_TERMINAL_PROOF_NOT_ARCHIVED; no machine all-green or human-signature request.
