# Independent video system routing review 01

Decision: offline routing/source review PASS; Fatal 0 / Major 0 / Minor 0. This is not real-model semantic acceptance or a Stage PASS.

Reviewed HEAD 9d9cdad0d3ef45a6dd821984272b0cbaa351bb76 plus uncommitted provider.py, test_provider.py, new analysis_video_system_zh.txt, and build_info.py/test_run_local.py addendum. Exact bindings are source-hashes-before.json, source-hashes-addendum-before.json and source-hashes-after.json; all match. git-diff-HEAD.patch captures staged plus unstaged tracked pack changes; candidate-template.txt separately captures the untracked supplement (git diff cannot include untracked files). Control-file changes are captured for completeness, not approved by this review.

The common system remains the exact prefix of the video system message. Its existing image wording is broadened explicitly by the appended video supplement. Shared JSON, fact/inference/unknown, data-as-low-priority-preferences and hidden-reasoning boundaries remain intact. The supplement is trusted local policy, never assembled from custom guidance. A hostile closing-guidance/system-spoof preference remains only in the user message and cannot mutate the system message or message roles. This proves request-role separation, not model resistance to arbitrary injection.

The supplement requires sampled-sequence evidence for temporal assertions, separates background/subject/relative relation, and leaves measured-change causes and physical camera direction unknown when unsupported. Pixel/color registration is expressly nonsemantic and cannot establish object identity. It contains no fixture names, sample-specific expected motion answers, parser changes or added schema fields.

Independent in-process MockTransport compared public analyze_video on synthetic PPM bytes and image analysis against an executed HEAD provider. For image, the full actual request equals HEAD. For video, the sole actual payload difference is messages[0].content. Source sheet PNG, frame times, numeric measurements, one image/request, options, format/schema and user task are identical. Exact mocked raw response strings are preserved. Video metadata becomes 1.5.0; image remains 1.1.0. VIDEO_TEMPLATE_SHA256 independently recomputes to 4fdfc6aa195dfb0eba51f8842e9ba4aeea2207354f8c592012e5c1a71c2d4b0d and changes under a supplement-only mutation.

build_info.py now includes both common and video policy in the deterministic source identity. The isolated temporary-root test proves supplement-only changes invalidate the identity, guarding stale-server detection. No denominator, acceptance oracle, hard limits, model settings or raw-response normalization changed in this correction.

Validation: 21 provider tests pass; two ledger-writing tests intentionally deselected to honor review isolation. Seven launcher/build tests pass. One pre-existing Pillow getdata deprecation warning remains. Raw command results: pytest.log, pytest-build.log, payload-comparison.log; reproducible independent harness and full captured requests are included. No real model/GPU/service/network/browser/download/media decode/ledger write was performed. Synthetic images alone were decoded in-process for sheet/measurement verification. All reviewer writes stayed beneath this report root.

Existing live13 UM04 and earlier failures are historical evidence of their own candidates. They neither prove nor disprove this unexecuted system-routing correction. Real-model semantics, fixed full UM matrix and human signoff remain required.

## Development outline (copied current authority; unchanged)

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

Current coordinate: R1/WP-R1-U3; batch: isolated offline review complete; last review gate: request routing and CPU tests only; blocking gate: fresh real-model semantic verification; route: approved unified media slice, no stage advancement; remaining: real matrix, independent result review and human signature; next owner: parent Codex; authorization: no new request from this review; evidence: this directory; exact stop reason: isolated review scope complete.
