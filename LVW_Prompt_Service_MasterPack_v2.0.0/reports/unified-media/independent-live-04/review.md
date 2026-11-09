# Independent live-04 terminal review — NO_GO

Candidate: `9f4a659ee3f5b09b6c0abc060957b2f276916b37`.
Supplement: AUTH-REQUEST-V1-R1-U3-SEMANTIC-01, approved request SHA ddb4fa7205723c76cfe3ecbf5ca9eb6182c24a18ee74ea32341d15504394f9a0.
Result: **NO_GO / CHANGES_REQUIRED**, current-run Fatal 0 / Major 1 / Minor 1. The corrected video presentation was never exercised by a real model in this attempt; old UM-04 semantic failure is not closed. No Stage PASS, ten-case acceptance or human experience signature.

Review read terminal artifacts only after the executor's terminal notification. It ran source/artifact hashing and JSON/source inspection only: zero reviewer model/GPU/service/media probes, zero extra decode, zero holdout inputs. Original live-04 receipt/files were not modified. Source is read from exact candidate Git blobs, not the shared working tree under subsequent correction.

## Major R1 — analysis can submit during a pending runtime transition

Locations: candidate `lvw/frontend/src/App.tsx:89,96-108,126-127,252`; `lvw/frontend/src/domain.ts:56-57`; backend protection `lvw/backend/app/service.py:31-34,216-226`.

Trigger: click the production page's runtime-start control. The installed model becomes visible through readiness/status before the original runtime-start HTTP transaction has completed. Select/upload an image and activate analysis during this window.

Expected: the analysis button and handler both prevent submission throughout start/reset/stop transitions. Installed-model readiness alone must not advertise the analysis operation while the product's runtime-control transaction is still active. Keep the backend RESOURCE_BUSY protection; do not remove it to force a green test.

Actual: runtimeAction disables runtime controls but is absent from the analysis button's canAnalyze call. The analyze handler checks only file and analysis-phase busy. The status poll can set model-ready true while runtime.start is still pending, so the UI allows analyze. AnalysisService correctly rejects submit while _controller_busy is true, before any Job is created.

Reproducible original evidence: launcher.log line 19 GET/readiness 200; line 20 media upload 201; line 21 POST jobs/analyze 409; line 22 original POST runtime/ollama/start 200. The browser fixture proceeds on model_ready+managed, without waiting for the original UI runtime transaction. cleanup-job-terminals is {}, no public-jobs202 file, no ModelRun and no Provider ledger. This exact frozen production UI path failed the first requested image analysis. The original 409 JSON body was not separately retained; the RESOURCE_BUSY/controller explanation comes from the actual source's first submit guard plus the fresh-session request/order evidence, not a claimed archived error body.

## Minor R2 — failed submission is hidden behind a 420-second waiter

Location: candidate `reports/unified-media/live_browser.cjs:5,7-8`.

Trigger: submit fails before returning a Job, here HTTP409.

Expected: the browser oracle distinguishes a terminal submission error from an accepted-job lifecycle, captures the HTTP/error evidence and fails promptly with the real reason.

Actual: waitDone requires an existing .job-status in addition to a nonprocessing button. No Job means that element never exists. The page can already be in failed phase, but the oracle waits 420000ms and reports only a timeout. Browser-result has checks=[] and this timeout; no incorrect PASS was issued, but the Harness hides the immediate failure and wastes its bounded attempt.

Correction should be offline and candidate-bound: gate button+handler during every runtime transition and add controlled start/reset/stop barrier regressions; distinguish no-job failure in the waiter. No new real run or automatic retry is authorized by this review.

## Identity and authorization recomputation

Exact candidate build inputs independently recompute `f950ae3ac386375a70ee3f5a48e63dca45e0b852f97af21b567c892e5aa04932`, equal to both receipt and native Windows /health response. Candidate descends from approved998daf7 with zero frozen product/Harness differences. Checkpoint SHA a7ee727b1c63cd4e418b4b26f31c74b5a8d508841df7547b2c97a9c7efc841fd matches. Request/approval/sample/bindings SHA all match the child records. Active packet 1.0.3 equals the exact approved proposal, including manifest c20246bd153136c91ce27f7e125716c8c0b3848ffa58e7fe9857ce5f2e343502 and every referenced leaf.

The initial authorization file is historical ACTIVE_ONE_SHOT issuance; authorization.terminal.json is EXPIRED_NO_GO. The terminal and issuance retain the same supplemental request/approval hashes and authid. stage_checkpoint_consumed=true. This explicitly approved extra attempt expires at its first terminal result, irrespective of zero model calls; it cannot be refunded, reissued or retried from the old approval. The old full slots and pre-API exception do not create another slot. A historical approval file still saying APPROVED is not a current reusable authorization.

## Zero model calls: joined proof, not absence alone

- The only jobs/analyze response is 409, with no 202 anywhere in the public log. Candidate submit rejects before constructing a Job on the identified controller-busy branch.
- cleanup-job-terminals is {}, public-jobs.jsonl does not exist, provider.jsonl does not exist and no image/video ModelRun export exists.
- Native Ollama stdout logs no /api/chat or /api/generate; stderr has no model-runner startup. runtime-start reports model_loaded=false.
- Native startup does enumerate the GPU; that is not a vision-model request. This review's0 model-call conclusion concerns this bounded run, not arbitrary other applications on the host.

These mutually consistent control-flow and original-log facts support zero actual inference attempts from this sequence. It is not inferred solely from a missing ledger. No source4/wire1 payload was constructed/sent, no real temporal-sheet wire hash exists and no real corrected semantic response exists. Old synthetic sheet tests remain transport tests, not substitutes for this absent result.

## Cleanup and resource boundary

Native log directly witnesses OLLAMA_NO_CLOUD:true, cloud disabled true and listening on 127.0.0.1:11434. Native original owner PID 31804 matches runtime-start; birth_ticks 639297821491757855 and nonce cb00fa69862c427689b3a062b2fefcda are retained. Stop marker exactly matches nonce, and archived owner is state=exited/listener_owned=false. The public cleanup-stop response is stopped/unreachable/unmanaged/no last_error. API PID 1817252 has application-shutdown-complete/finished records; receipt records run root removed and both listeners absent, with no cleanup_error. Browser closed and reports no page errors or external requests.

Reviewer did not independently connect to ports or requery host resources. Recorded root/listener checks are executor measurements audited against its source and shutdown evidence; native exit is additionally supported by the raw owner proof. Preflight free 20950MiB was admission preparation, not an analysis lease baseline. No inference lease, running GPU/RAM telemetry or three-sample model-release sequence occurred here; therefore no peak or physical inference-release PASS is manufactured.

## Ten-case boundary

coverage.json records 2 PASS (UM-02, UM-10), 1 FAIL (UM-01), 7 BLOCKED (UM-03 through UM-09 except UM-10). The two real public duration/corrupt negatives and valid same-owner CPU boundary evidence support UM-02. Identity, owned cleanup, spent authorization and this independent review support UM-10. The runtime/bootstrap chain itself is real, but the requested browser image/video/adoption/cancel/offline sequence did not complete.

Prior validated MediaStore negative, shared decoder/PTS, queued/preparing cancellation and controlled late-success tests retain their precise owner-level value. They are not invalid merely because a Provider is stubbed, but they cannot be presented as fresh live-04 model/video/export results. The old live-03 temporal semantic FAIL remains history, and the new presentation's real semantics are BLOCKED/NOT_RUN, not assumed fixed or marked failed by a nonexistent response.

## Required project status

Outline unchanged: V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1/R2/R3/R4/R5a/R5b/R5c each 0/4; current R1.

1. Current coordinate snapshot: R1/WP-R1-U3/RUNTIME_TRANSITION_CORRECTION_OFFLINE/RUNNING; reviewed real child live-04 is already terminal NO_GO.
2. Completed: original live-04 identity/order/zero-inference/native cleanup and terminal-authorization facts independently recomputed; findings preserved.
3. Last passed gate from execution-control: SEMANTIC_CORRECTION_CPU_REGRESSION, candidate 998daf7, offline-07/offline-reuse-01, CPU 108 only; no real-model/human acceptance.
4. Blocking gate: production runtime-transition race; corrected temporal semantics not verified; original supplemental real-run authority spent.
5. Global route: unified early slice, historical V0-Min/R1a accepted scopes retained; full R1/V1 incomplete.
6. Remaining: authorized offline correction and meaningful controlled regression, independent review; any subsequent real attempt needs a new concrete authority/budget decision. Human signature remains later.
7. Next owner: implementer/gate owner for offline correction; reviewer does not authorize a retry.
8. Authorization: original supplemental one-shot expired at NO_GO; this review consumed no real execution.
9. Evidence: reports/unified-media/independent-live-04/, raw originals remain live-04/.
10. Exact stop: NO_GO_RUNTIME_TRANSITION_RACE_ZERO_INFERENCE_SUPPLEMENT_EXPIRED_NOT_HUMAN_SIGNOFF.
