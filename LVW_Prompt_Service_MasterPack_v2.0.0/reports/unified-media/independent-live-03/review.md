# Independent live-03 review — NO_GO

Candidate: `a8a431d986b236cc842f4fc24e12c3a3e13ea0c1`.
Bound Harness: `ed216c12de560255e106b137e46cccc1e54f620778356e410c2ab15cf82cd205` (same reviewed 0f6b772 checkpoint).
Decision: **NO_GO / CHANGES_REQUIRED**, Fatal 0 / Major 1 / Minor 0. Coverage is 8 PASS, 1 FAIL (UM-04), 1 BLOCKED (UM-05) with source-specific limitations in coverage.json. This does not change the executor's original receipt; its “complete, review pending” result is not semantic acceptance. No Stage PASS or human signature.

## Major V1 — real video semantics contradict the sampled temporal evidence

Locations: `live-03/video-model-run.json` JSON pointers `/parsed_spec/domains/observation/0`, `/parsed_spec/domains/observation/4`, `/parsed_spec/domains/inference/0`, `/parsed_spec/technical/camera_motion`, `/parsed_spec/technical/subject_action`; `video-adopted.json:/outputs/video_prompt`; `live_browser.cjs` UM-04 oracle only checks nonempty fields/raw.

Trigger: the actual tracking.mov development sample, source SHA b08ea8b0b9fa3bcd4e62b2b0ad1c05b2bff09359539933f4581a5c2f2c69ff6d. Actual Provider attempt has frame_count=4 and source frame coordinates 1/3/5/7 seconds. The frozen fixture recipe is a navy grid with horizontal crop x=20+2*n and a red box painted afterwards at a fixed image location. The grid changes position while the red box remains fixed.

Expected: frozen R1 acceptance UM-04 requires real Provider semantics over all sampled frames; implementation prompt requires observed differences, not only an end-frame/static summary. Supported temporal differences must inform the video suggestion, or uncertainty must be acknowledged. This is already required by packet 04/06 and approved docs/27; it does not import S3 or a new quality threshold.

Actual: original model response states “three identical images”, “no moving subjects or changes”, infers a static loop, and returns camera_motion=none/subject_action=none. Chinese and English video prompts are explicitly static, and the adopted video export appends none/none with motion in negative prompts. The general sampled-only disclaimer is preserved but does not correct these positive false assertions. Different SHA alone would not establish visible motion; here the hash-bound fixture generation recipe explicitly changes the grid, and the four source images corroborate it.

Reproducible evidence: original raw content and parsed fields agree exactly; no parser transformed a correct temporal description into the error. Fixture-generation receipt records the recipe. Supplementary isolated CPU replay produced precisely the same four source PTS and all four frame hashes. Consecutive mean absolute RGB differences are approximately (22.95,22.96,13.94), (22.53,22.58,14.02), (22.44,22.46,13.63); montage four-frames.png visibly shows grid shifts. Red-box immobility is not whole-scene immobility. The replay's authorization-process deviation is disclosed below; the frozen fixture recipe plus original model/run evidence independently support the failure without treating this supplementary replay as a compliant acceptance run.

Conclusion: this is a blocking failure of the explicitly frozen sampled-sequence obligation, not merely an optional broad quality limitation. Real input transport and raw preservation pass; temporal semantic usefulness does not. Do not change the raw result, remove this sample, copy in historical S2 output, or pass the case merely because JSON parsed and four images were sent. Any changed model-input/prompt approach needs its own candidate-bound evidence and budget decision; this review authorizes no extra execution.

## Independent identity, schema and export recomputation

The exact candidate Git blobs recompute build ID `433065db0ac26afcbbc5a51ff62baeb70ee0fe1facc2586647f766000e42672d`, matching both recorded API and Windows /health. Product files are identical to c131789; checkpoint/browser/authority match the reviewed 0f6b772 versions. Harness, packet-manifest, parent authorization and four sample SHA bindings match. The current shared provider is under later development and was excluded from candidate identity calculation.

Audit correction: the first temporary script used a pathspec relative to the wrong Git cwd and omitted the backend/dist list, yielding an invalid intermediate false identity result. It was corrected to git ls-tree --full-tree and recomputed solely from committed blobs. Final audit.py/recomputed.json records the matching result; no genuine source mismatch was hidden by newline normalization. A separate isolated exact source extraction is used for checkout-level confirmation. Full worktree checkout was stopped after slow unrelated report copying; product was not modified.

Both ModelRun objects and all six initial/terminal Job objects validate against the candidate frozen OpenAPI component schemas. Raw-to-parsed observations/inferences/prompts/tags/negative and video motion fields match. This confirms structural correctness, not truth of video observations.

Every export provenance comparison passes: image adoption points to the image run; before video adoption source remains image; video adoption switches to the correct video run/source SHA/four frames; cancellation retains that adopted source and AFTER_ADOPT_MANUAL_KEEP; offline export retains source with OFFLINE_EDIT_AND_EXPORT. TXT contains the offline edit. These are real production browser downloads, not reconstructed examples.

## Calls, resources and cleanup

- Exactly three client Provider attempts (frame counts 1/4/4), two completed responses and one cancelled attempt. Do not describe these as three completed model inferences. Native stdout has two successful /api/chat completions plus three unload /api/generate requests; the cancelled attempt has no completed model output.
- Exactly three distinct leases. Admission free GPU: 20571/20551/20517 MiB, all >=19047. Each lease has three consecutive empty-inventory release samples within its own GPU baseline+1024 MiB. Acquire-to-release elapsed: 18.411s, 18.817s, 2.733s. Completion/start-to-release: 2.377s, 2.375s, 2.412s. All threshold calculations independently recomputed.
- Peak running GPU 22109 MiB <23552; minimum running RAM 10365 MiB >=2048. This is observed sampled telemetry, not a claim of continuous sub-second peak measurement.
- Cancelled job has cancel_epoch1, cancelled/released, result_ref=null. It cancelled soon after request start; GPU samples remained near baseline. This demonstrates live service/request-state running cancellation and no late publication, not independently a cancellation after full GPU model loading/token generation. Controlled late-success fault tests exercise real AnalysisService publication, and are valid error-branch evidence.
- Native stderr explicitly witnesses loopback OLLAMA_HOST, NO_PROXY and OLLAMA_NO_CLOUD:true/cloud disabled true. Native model server logs show context 2048 for image and 4096 for video. Owner PID24304 matches runtime-start and terminal owner with nonce e74b8ae87cf54dc880cf3b59c50126be, birth_ticks639297435140954437, state=exited/listener_owned=false. Stop marker matches that nonce.
- Cleanup-job-terminals preserves both successful results and cancelled result. Public cleanup-stop-response is stopped/unreachable/unmanaged, with no last_error. Owner exited was archived after stop; launcher records API PID1390948 shutdown complete; receipt records root removed and both listener absences, without cleanup_error. Unlike live-02, raw native terminal proof is present.

## What the CPU/fault evidence proves

A FakeProvider used solely to assert zero calls does not invalidate a real MediaStore/public upload rejection. Real shared validator boundary calls test the actual production limit owner. The actual ASGI AnalysisService with a controlled late-returning Provider is the correct production publication owner for late-success suppression; requiring a real model to intentionally violate cancellation would add risk without improving that oracle. These offline proofs are accepted in coverage.json and are not relabelled real GPU calls.

UM-05 remains specifically incomplete for current AnalysisService preparing cancellation with an in-progress decoder thread and terminal cleanup. Shared decoder/process cancellation tests and static event plumbing are useful but do not directly execute that combined owner scenario. The owner may supply a new CPU-only, candidate-source-equivalent barrier test; its validity must be assessed separately. No additional real model run is requested here. The UM-04 semantic FAIL alone suffices for NO_GO regardless of this coverage gap.

## Reviewer execution-process deviation

One supplementary tracking.mov CPU decode was started under the parent's explicit permission to decode this development sample, but before a finite child record was issued; the reminder to create review-pts-01 arrived after launch. This missed the pre-issued-child governance requirement. No retrospective ACTIVE authorization was fabricated. Actual scope: decoder=1, model calls=0, GPU probes=0, services=0, downloads=0, holdout inputs=0. Isolated temporary media/decode directory was removed and decoder temp root was empty. Source SHA, outputs, script and log are preserved. The replay is supplementary disclosed evidence, not represented as an authorized acceptance slot. Gate owner must assess this deviation; the reviewer does not self-sign it away.

## Gates and budget

The two complete checkpoint slots are now consumed (live-02 and live-03); live-01 was pre-API and stage_checkpoint_consumed=false. Three launcher attempts exist. No remaining full checkpoint/recheck is inferred. Parent authorization and product thresholds are unchanged; retries require the responsible gate owner's explicit budget/authority handling. All original failures/receipts remain unmodified. Eleven human holdouts remain untouched by reviewer/model execution.

Development outline unchanged: V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1/R2/R3/R4/R5a/R5b/R5c each 0/4; current R1.

1. Coordinate: R1 / unified early media slice / independent live review.
2. Completed: original live artifacts, schemas, source/build/sample bindings, raw semantics, provenance, resources and native cleanup independently recomputed.
3. Last passed gate: R1_UNIFIED_GATE0 scope approval only.
4. Blocking gate: Major V1 UM-04 semantic FAIL; UM-05 preparing cancellation coverage unresolved.
5. Route: historical V0-Min/R1a acceptance retained; full R1/V1 incomplete.
6. Remaining: owner-scoped corrective work, explicit evidence/budget decision, independent review; human signature only after machine obligations close.
7. Next owner: gate owner/implementer; reviewer reports findings without replacing adjudication.
8. Authorization: no new GPU/model/service/holdout work; CPU replay process deviation disclosed.
9. Evidence: reports/unified-media/independent-live-03/; raw originals remain live-03/.
10. Exact stop: NO_GO_UM04_TEMPORAL_SEMANTICS_FAIL_NOT_HUMAN_SIGNOFF; no Stage PASS.
