# Independent offline semantic-correction review

Final candidate: `998daf73a4ad06b7549fa19ab047b41250329de3`.
Result: **offline correction review complete; WAIT_AUTH**. New inspected code findings: Fatal 0 / Major 0 / Minor 0. Historical live-03 UM-04 remains FAIL: no real semantic result has been produced for the corrected presentation. This report is not a Stage PASS, machine all-green, new-run authorization or human signature.

Product Provider bytes are identical to tested ad4265c/a2beea1; AnalysisService bytes are identical to live-03. Final authority source equals the bytes used for corrected guard probes (SHA256 b1c6447d070b11bec00f43e2e2b77b74c90b303568c204fcb008a24b9c422c6d). Source verification used exact Git blobs and an isolated /tmp/lvw-semantic-ad426 copy. No candidate product file was changed by reviewer.

## Presentation and provenance

build_temporal_sheet processes all 1–4 actual decoded frame bytes in their existing chronological order. It creates 384px cells, at most two columns/two rows (max 768x768), converts each frame to RGB, applies aspect-preserving thumbnail, centers/pastes it with space for a metadata label, and outlines cells. There is no crop, copied replacement frame or synthesized missing panel. Three source frames leave a blank fourth cell and the prompt explicitly states populated count 3. Invalid count 0/5 and frame/manifest count mismatch reject.

Labels F1..F4 and seconds derive from the corresponding actual manifest; model instruction identifies them as metadata. Ordering is left-to-right/top-to-bottom. The prompt replaces the old single-image task sentence, directs comparison of background/framing/subject across all populated panels, preserves sampled-only/uncertain-motion limitations, and uses neutral uncertainty rather than providing an expected grid-motion answer. No sample-specific camera direction, tracked-object answer or fixture oracle is inserted.

The Provider ledger distinguishes source frame_count from payload_image_count (4 versus 1 in the synthetic test), records actual source PPM byte hashes and the SHA of the actual PNG sent, and includes temporal-sheet/1. VIDEO_TEMPLATE_SHA256 includes this presentation version/task. Public ModelRun FrameRefs/PTS/source SHA remain unchanged. The image route still sends its original one image with image schema / 2048 context/512 prediction; video keeps 4096/768. No extra Provider request or hand-coded semantic answer was added.

Independent synthetic capture used four differently sized artificial images, explicit timestamps, mocked HTTP only, actual Provider serialization and actual ledger writes. Result: PNG 768x768, one wire image/four recorded source frames, four expected panel center colors match, source hashes/payload hash/times/count match, no single-image task conflict, no response-oracle sentinel in input, num_ctx 4096 / num_predict 768. These checks establish transport/presentation and provenance, not improved real model semantics. Original source shrinking within cells may affect perception; its actual effect remains for the separately authorized semantic recheck.

## CPU cancellation evidence

The isolated 17 Provider tests plus new preparing-cancel barrier test passed: **18 passed in 1.06s**. No GPU/model/service or media probe was executed. To respect the explicit no-media-probe restriction, the preparing test's upload probe was stubbed and tracking.mov contained dummy inert bytes; the actual AnalysisService/public cancel/thread barrier/cleanup owner remained unchanged.

The test enters preparing with a blocked decoder thread, sends public cancel, requires the shared cancellation event to reach that thread, removes the owned marker in its finally, and allows release only after cleaned=true. It then checks cancelled/released, result_ref=null, no ModelRun, Provider calls 0 and no marker. This is valid controlled-error evidence for the actual service owner. It closes the earlier specific UM-05 preparing-owner coverage gap when combined with existing shared-process cancellation/reaping evidence; it does not claim an additional real loaded-GPU cancellation. A separate live-03 coverage supplement records9PASS/1FAIL, with UM-04 unchanged.

## Supplemental authority and proposed packet

The ad4265c guard had a Minor in a fresh/missing-history state: live-04 entered the ordinary budget branch, created its directory, then referenced undefined request_path. This failed before service launch but violated the no-directory requirement. The final guard unconditionally routes run_id=live-04 through the supplemental checks; both three-history and zero-history/no-approval probes now reject before allocation. Historical failure and corrected raw probe logs are retained.

The final guard requires exactly three previous live attempts, a separate explicit APPROVED grant bound to the entire request hash/authid, exact run ID/one recheck, matching budgets/seconds/port/sample paths and hashes, matching Harness hash, approved proposed-packet manifest hash, every leaf's actual hash, exact leaf file set, candidate ancestry and zero frozen product/Harness diff. Supplemental request/approval paths and hashes/authid are attached to the future child. It has no default approval and no inferred slot reuse.

Nine independent negative guard experiments reject missing grant, request-hash mismatch, sample-hash mismatch, Harness mismatch, packet-manifest mismatch, packet-leaf tampering, extra packet leaf, bad ancestry and frozen-path drift. Each created no live04 directory and invoked no external command/service/model. Git subprocess checks were controlled CPU oracles in private fake roots; no fake grant was written into the real repository. The actual live04 directory and actual approval file are absent.

The pending request binds final candidate 998daf7 and correct Harness/sample hashes. Current request SHA256: ddb4fa7205723c76cfe3ecbf5ca9eb6182c24a18ee74ea32341d15504394f9a0. It explicitly proposes changing four independent wire images to one<=768 temporal sheet, preserving source FrameRefs, same denominators and resource/quality thresholds, one additional full recheck and no human signature. Active packet 1.0.2 is excluded from the product/Harness zero-diff set; activation is instead constrained to the exact proposed 1.0.3 manifest, actual leaf bytes and file set. This resolves the earlier mutual conflict between packet activation and zero-diff freezing.

Proposed1.0.3 remains under its proposed directory, not activated by this reviewer. Its fixed acceptance IDs, ten slice IDs, acceptance hashes and acceptance-matrix bytes remain unchanged. Its new implementation prompt explicitly requires chronological source panels and distinct source/wire counts. A pending request is not authorization; activation and live04 must wait for the explicit human approval bound to this request. Any changed request requires a new hash binding.

## Evidence limits and next gate

No real model/GPU/service/browser/holdout/media-probe execution occurred in this correction review. Inputs for presentation checks were synthetic and transport used httpx.MockTransport. The old failed raw live-03 results were not edited or replaced. The earlier supplementary CPU-decode child omission remains disclosed in the separate live-03 review; no retrospective authorization was created.

This review did not treat offline04 timeout or offline05 dependency-collection failure as success. The executor's new full offline06 was not used as evidence before a terminal raw result was supplied. The 18 targeted tests are not relabelled the entire consolidated suite. The correction is suitable for the concrete supplemental-authorization request, with the original semantic gate still unclosed.

Development outline unchanged: V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1/R2/R3/R4/R5a/R5b/R5c each 0/4; current R1.

1. Coordinate: R1/WP-R1-U3/UNIFIED_SEMANTIC_CORRECTION_RECHECK/WAIT_AUTH.
2. Completed: corrected presentation/provenance/cancellation owner and supplemental authority independently reviewed; targeted CPU checks pass.
3. Last gate: R1_UNIFIED_GATE0 scope approval only.
4. Blocking gate: explicit supplemental approval; original real UM-04 remains FAIL until independently verified new result.
5. Route: early unified slice; historical accepted scopes retained, full R1/V1 incomplete.
6. Remaining: consolidated offline terminal evidence, approved exact packet activation if granted, one bounded fresh real recheck and independent recomputation; later human signature.
7. Next owner: gate owner/human authorizer; reviewer does not issue authorization.
8. Authorization used here: isolated CPU/synthetic/negative tests only; zero real model/service/GPU/media probe.
9. Evidence: reports/unified-media/independent-semantic-correction-01/.
10. Exact stop: WAIT_AUTH_OFFLINE_CORRECTION_REVIEWED_REAL_SEMANTICS_NOT_REVERIFIED; no Stage PASS.
