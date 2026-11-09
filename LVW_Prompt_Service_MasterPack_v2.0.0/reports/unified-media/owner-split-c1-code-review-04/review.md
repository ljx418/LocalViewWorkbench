# C1 independent code review 04

Decision: CHANGES_REQUIRED for C1; Fatal0/Major1/Minor0. This is C1 code review only, never Stage PASS. Initial candidate source hashes match owner-split-c1-offline-04/receipt.json and remain unchanged through this review. HEAD98036df8 freezes packet1.0.4; reviewed uncommitted C1 code is bound separately.

## Major C1-RAW-01 — successful raw response lost on composition failure

Location:lvw/backend/app/service.py, video compose call and following AppError handler (lines164 and173–175). Trigger:Provider returns valid appearance raw/spec, then CPU compose_video_spec rejects an internal evidence policy mismatch. Expected:failed result retains exact successful model raw response for diagnosis; parsed suggestion is unpublished. Actual:AppError handler overwrites already populated raw with getattr(error,'raw_response',''), clearing it because composition errors do not carry raw_response. A failed ModelRun with PARSE_PARTIAL is published with empty raw_response. The original wire cannot be recovered from its hash alone.

Evidence:reproduce_compose_raw.py injects only CPU temporal policy-version rejection with four synthetic PPMs and an in-memory fake Provider. compose-raw.log records failed/PARSE_PARTIAL, actual_runs_count1 and actual_raw_preserved:false for original wire SHA218505c7b0b66f4f73ef5054e098408aff477907eb3b0cc7e96bf605d124565f. No model/network/real service used. Preserve already received raw when a later CPU error lacks its own raw_response; add a meaningful composition-failure regression. Cancellation intentionally suppressing publication is a separate retained requirement.

## Other C1 findings and limits

Provider's public video default now sends all actual1–4lossless RGB sourcePNGs in one appearance-only model call, no contact sheet, no numeric temporal evidence in model prompt, thinkFalse/ctx4096/predict768/temp0.2. Original frame order/hash and actual frame denominator are retained. Appearance schema/parser enforce exact fields and frame IDs/order/count, duplicate-key rejection, per-language lengths and complete stop; model words/raw remain verbatim on the success/provider-failure paths. Image request construction is unchanged; legacy diagnostic paths remain explicit appearance_only=False.

video_temporal moves the existing bounded measurements into CPU ownership with cancellation checks per frame/pair/search row. AnalysisService computes decode+measurement in its preparation thread under the existing deadline, joins preparation before release, and composes a deep copy only after Provider returns. Public cancellation/release tests remain green. Source hashes and frame-pair identities/counts are recorded; policy mismatch and denominator drift reject composition. Program facts/inferences are separately labeled, with fit ambiguity, physical camera/subject and continuous-motion limits retained. Model appearance is not replaced by numeric output. UI changes the title to sampled change/limits and preserves the manual-suggestion boundary. Build identity includes new backend modules and appearance policy.

This review does not verify actual model appearance quality or that raw obeys the new no-temporal-claims instruction. The parser deliberately cannot certify semantic truth:erroneous raw claims such as unchanged relationships must still FAIL the real C2/C3 raw-quality gate even if CPU text is correct. Numeric/unknown-only results cannot substitute for useful appearance and supported sampled change. Parent's packet1.0.4 decision/recipe/Gate0 conditions retain those obligations, original tracking/fixedUM10, missing real negatives, allthree real cancellation phases, request/config binding and human signoff. No changed denominator/schema/threshold was found in C1.

Independent CPU rerun:81passed,oneexisting Pillow warning; pytest.log contains full raw output. Command matches implementer five directed files, with cache disabled and temp root confined here. These CPU tests exercise synthetic/mocked model/telemetry and existing CPU decoder fixtures; they are not real model or real service acceptance. No actual model/GPU/network/server/browser activity was performed. C2 reports-only changes are outside this code review; no Stage conclusion is made.

Writes stayed within this report root. Complete tracked staged+unstaged pack diff and untracked new source/test/template snapshots are retained. Source-hashes-before/after match. Initial reviewer reproduction timestamps were adjusted to valid1/3/5/7sampling metadata before the final successful raw-loss reproduction; that adjustment does not modify product code.

## Development outline (copied authority; unchanged)

| Stage | Done/total | Scope |
|---|---:|---|
| V0-S0 | 1/2 | 基线探索 |
| V0-S1 | 5/5 | 图片与独立人工 |
| R0 | 1/2 | 独立服务复核 |
| R1a | 5/5 | 单图React/FastAPI |
| V0-S2 | 7/8 | 视频与资源控制 |
| V0-S3 | 0/6 | 离线质量与增量包 |
| R1 | 0/4 | 人工业务骨架 |
| R2 | 0/4 | 任务与正式运行包 |
| R3 | 0/4 | 镜头资产与检索 |
| R4 | 0/4 | MCP与恢复 |
| R5a | 0/4 | 证据与建议合同 |
| R5b | 0/4 | 受控生成交接 |
| R5c | 0/4 | 集成与完整交付 |

Current coordinate:R1/WP-R1-U3-C1; batch:isolated C1 review and81CPU tests complete; last review gate:C1 initial review; blocker:C1-RAW-01; route:packet1.0.4 implementation before C3; remaining:fix/review C1,C2review,fulloffline/pilot/fullreal/runtimeindependent/humansignature; next owner:parent implementer; authorization:existing scope; evidence:this directory; stop reason:one reproduced Major requires correction,not Stage stop/pass.
