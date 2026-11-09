# Independent temporal units review

Decision: CODE_REVIEW_PASS_WITH_REAL_SEMANTICS_UNVERIFIED. Fatal 0 / Major 0 / Minor 0.

Candidate: `d9759decaa760eb81479db5434ff9206b18b3327`. Baseline: `8d43c1dcb79cedd16ce5143c8f68887de38e6572`. Both provider/test commit blobs match reviewed and tested bytes; Harness commit blobs are identical to baseline. Prior independent-temporal-metrics-01 evidence is retained unchanged.

## Scope and findings

The production diff replaces different_pixel_fraction with different_pixel_percent = round(100 * changed / total, 4), adds exact integer changed_pixel_count and frame_pixel_count, and updates generic instructions and CPU test expectations. The integer numerator counts pixels with any nonzero RGB difference, not changed channels. The denominator is the actual adjacent frame width × height. Percent has 0..100 units; the prompt explicitly forbids dividing it by 100 again. Exact counts permit cross-checking rounded percent. Mean absolute RGB delta retains its existing units and computation.

The added wording requires unknown cause/direction when visual attribution is uncertain and forbids inventing an unchanged background or unsupported compression-noise explanation. It supplies no expected sample answer, motion direction, source name or lookup. This addresses input clarity only; model adherence remains unverified.

The same production analyze_video(decoded.frames) path, actual frame list/hashes/timestamps, complete-frame temporal sheet, one HTTP Provider call, model_action-before-send guard, raw response, parsing and PromptSpec assignments remain unchanged. Public schemas/API and UM10 denominator, sample set and all quality/resource thresholds are unchanged. The existing VIDEO_TEMPLATE_SHA256 incorporates the new VIDEO_TASK. No Harness production diff is present relative to baseline; UM-04 remains BLOCKED pending independent semantic review.

## Independent CPU evidence

A temporary isolated copy contains the reviewed provider and tests, existing app/pure-kernel dependencies, and template. Test process disables bytecode/cache and automatic pytest plugins; socket connect/connect_ex and subprocess.Popen are blocked. Existing test_provider.py: 19 passed in 0.36 seconds. No service, model, GPU, browser, media probe or real video decode was run.

An independent fixture oracle uses exact Decimal division from selected integer pixel counts. It confirms 0%, 25%, 33.3333%, 34.3871% and 100%; tests keep the count/denominator exact and source payload hashes unchanged. The 34.3871% case is 168497 changed pixels / 490000 actual pixels, i.e. 34.387142857...%, rounded once to four decimals. All image fixtures are synthetic, with maximum edge 768. The initial independent oracle mistakenly assigned 34.3871% to 202823/589824; its retained error demonstrates this is 34.3870%. Correcting the review fixture to a mathematically suitable 700×700 case resolved the oracle expectation without changing implementation. Raw logs and scripts preserve both results.

## Boundary

Live05/live06 results belong to previous candidates and remain independent historical semantic failures; neither is credited as this candidate’s PASS. This is a CPU code review only. It does not certify UM-04 semantic correctness, UM10/10, Stage PASS, human experience or release. A separately authorized bounded real recheck and independent output review remain necessary.

## Development outline snapshot

|Stage|Completed/total|Existing summary|
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

当前坐标：R1/WP-R1-U3；本批完成：独立单位代码复核、19测试、Decimal精度复算及候选字节绑定；最后通过门禁：CPU代码审查；当前阻塞：新候选真实语义未验证；全局位置：统一切片不代替完整R1/R2；剩余工作：有限真实复验、独立语义裁决及人工签署；下一责任人：Codex门禁负责人；所需授权：母授权02内新有限子授权；证据目录：本目录；精确停止原因：CODE_REVIEW_COMPLETE_NEW_REAL_SEMANTICS_UNVERIFIED。
