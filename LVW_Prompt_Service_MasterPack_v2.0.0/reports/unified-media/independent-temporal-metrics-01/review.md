# Independent temporal metrics review

Decision: CODE_REVIEW_PASS_WITH_REAL_SEMANTICS_UNVERIFIED. Fatal 0 / Major 0 / Minor 0.

Candidate `8d43c1dcb79cedd16ce5143c8f68887de38e6572`, baseline `0cc125f9ba8a66972cf19176a61d52a4b2742bb7`. Final commit blobs for provider.py, test_provider.py, build_handoff.py and live_browser.cjs equal the reviewed working bytes; hashes are in bindings.json. Reviewed under AGENTS11 separate read-only role. Only this evidence directory was written in the shared repository.

## Evidence and conclusions

1. Production `OllamaProvider.analyze_video` calls `temporal_pixel_measurements(decoded.frames)` and forwards its result to the same `_analyze_images` user message and provider ledger. The helper reads actual RGB pixels in adjacent input order and computes changed-pixel fraction and mean absolute RGB channel difference. No sample identifier, expected camera answer, source-specific lookup or direction estimator is present.
2. Existing `build_temporal_sheet` still traverses every actual frame, validates 1–4 matching manifests, and preserves the previous complete-frame display. Source frame hashes remain calculated from unchanged `decoded.frames`. No source replacement, duplication, frame dropping or new media decoding path was introduced. PIL opens already-decoded RGB frame payloads; this review generated only synthetic image fixtures and did not probe or decode any video.
3. The prompt explicitly says pixel changes are not proof of camera motion, lists compression/lighting/subject movement alternatives, requires unknown direction/cause when ambiguous, and forbids inferring an entirely static sequence just from stable subject placement. This is generic measurement guidance, not a hardcoded tracking answer.
4. The raw HTTP response capture and PromptSpec parsing are unchanged. The helper does not rewrite model output, translation, camera_motion or subject_action. Public contracts/schema, actual timestamps, fixed denominator and all existing quality/resource limits are untouched by the reviewed implementation diff. VIDEO_TEMPLATE_SHA256 includes VIDEO_TASK, so the prompt change is hash-visible.
5. The production path still sends one HTTP Provider request. Existing `LVW_REQUIRE_BUDGET`/child rejection, model_action before attempted send, `_sent` accounting, options and keep_alive remain unchanged. The isolated provider tests include missing-child/no-send, debit-before-send and exhausted-budget/no-send cases.
6. Harness correction changes only UM-04 schema/raw success from PASS to BLOCKED, with explicit independent temporal semantic review requirement. This removes premature semantic approval and preserves the UM10 denominator. The receipt’s checkpoint completion is not Stage PASS. The build_handoff changes accurately separate current output from historical failures and point to the approved program02 grant.
7. The existing shared kernel bounds actual decoded frames to four and normalized edge 768 (`video_decoder.py`/`video_input.py`). The helper costs O(frame_count × pixels) CPU/memory and opens no process/network. Independent synthetic 4×768² measurement took 0.0184 s; complete Python process peak RSS was 84,152 KiB. These are local CPU fixture measurements, not production latency or GPU acceptance.

## Independent CPU execution

Copied app/provider tests/templates and the existing pure video-kernel module tree into an isolated `/tmp` root. Disabled pytest plugin autoload and bytecode/cache writes; blocked socket connect/connect_ex and subprocess.Popen inside the test process. `test_provider.py`: 19 passed in 0.34 s. Separate independent byte-array oracle agreed exactly for all three adjacent pairs and confirmed source payload hashes unchanged. Original logs, runner, oracle script and diff are retained. Initial collection failed because the minimal copy omitted the pure kernel dependency tree; that setup failure is retained in cpu-test-initial-collection-error.txt. Copying the existing dependency tree resolved it without changing implementation.

## Limits

No service, GPU, model, browser, media probe, real-video decode or production child was run. Live05 belongs to baseline 0cc125f and remains a historical semantic failure under its separate independent review; it cannot demonstrate this candidate’s correction. This review permits the gate owner to consider the sealed candidate for a separately authorized bounded live recheck. It does not certify UM-04 content, UM10/10, Stage PASS, human experience or release.

## Required development outline (snapshot only)

|Stage|Completed/total|Existing coordinate summary|
|---|---|---|
|V0-S0|1/2|历史探索已结束且NO_GO保留；V0-Min按后续范围签署，不回填S0 PASS|
|V0-S1|5/5|已签仅V0-Min|
|R0|1/2|仅R1a前置单图子集可确认；不把完整视频/Q01算通过|
|R1a|5/5|已签仅单图切片；完整V1未完成|
|V0-S2|7/8|Full08 fresh cumulative9/9, offline541/5checks, independent Fatal0/Major0/Minor0; human signoff and immediate Git sync remain.|
|V0-S3|0/6|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R1|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R2|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R3|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R4|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R5a|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R5b|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|
|R5c|0/4|已有设计，未完成正式交付；存在代码需进入时复用审计|

当前坐标：R1/WP-R1-U3；本批完成：独立只读代码审查、19项CPU及独立像素字节复算；最后通过门禁：本次代码/CPU审查；当前阻塞门禁：新候选真实时序语义尚未验证；全局路线位置：统一切片不替代完整R1/R2；剩余工作：受控真实复验、独审及人工签署；下一责任人：Codex门禁负责人；所需授权：program02范围内新有限子授权，非新的逐候选人批；证据目录：本目录；精确停止原因：CODE_REVIEW_COMPLETE_REAL_SEMANTICS_UNVERIFIED。
