# Independent thinking component probe review

Final disposition: no open execution blockers found in corrected source. Fatal 0 / Major 0 / Minor 0. This is a CPU/source review of a single component diagnostic, not a Stage PASS or model-quality result.

Initial TP01 Major reproduced a missing-GPU-tool setup exception after reserve/bind with neither terminalization nor receipt. Corrected harness starts its guarded try before reserve, initializes absent provider/runtime and tracks successful reservation. Independent mocked reruns now prove missing GPU tool and bind rejection write terminal NO_GO receipts and settle zero actions; reserve rejection writes a terminal receipt without settling an unissued reservation. A synthetic settlement failure invokes close_retaining_reservation and writes NO_GO_CLEANUP_PENDING. TP01 is CLOSED by reproduced evidence, with original findings, frozen harness and reproduction preserved. TP02 Minor inaccurate no-lease comment is corrected and CLOSED by inspection.

Default actual image and video request payloads exactly equal HEAD in independent MockTransport comparisons. No extra metadata request occurs by default. Explicit thinking=True requires live /api/show capability list-of-strings containing exact thinking before debit/send. None, strings, maps, mixed-type lists and unsupported empty lists fail closed in the extended provider test. Independent event recording confirms unsupported capability → /show only, supported → /show, debit, /chat. A non-bool opt-in fails before HTTP. Production public calls retain false, ctx4096/predict768 video settings, schema, source sheet, measurements and raw behavior.

Harness source checks bind tracked provider/template/authority/harness, tool hashes, model digest and four retained source hashes. model_action rechecks child expiry, sample/source hashes and execution bindings before one permitted inference debit. No new decode, holdout, public workflow or full checkpoint is requested. Reservation is one call/600 seconds; analysis/monitor wait420, owned startup65, release32 and close25 remain bounded. Source/raw request tests use synthetic bytes only.

By static inspection: failed acquire reaches owned runtime.close; inference and resource monitor are canceled and awaited together; a release exception still reaches runtime.close; unproven release/owner/listener state retains reservation. Fresh runtime ownership proof and original native nonce/handle are required; no foreign-service stop is introduced. These runtime/lease/cancellation branches were source-reviewed, not real-runtime executed. No claim of successful native cleanup is made from mocks.

Final model content is retained verbatim with wire hash, including partial-content extraction on parse failure. Internal thinking body is not written by the harness; only presence/count metadata may be recorded. Parsed content is separate from original final content. Non-AppError failure details now survive, with WAIT_AUTH/WAIT_BUDGET classification. No product acceptance denominator, fixed limits or human-signature gate is changed. Prior live14 NO_GO remains independent evidence and is not reassigned to this opt-in diagnostic.

CPU evidence: 22 provider tests passed, two ledger writers excluded; one existing Pillow deprecation warning. Request comparison and guard logs pass. Four setup/terminalization mock scenarios pass. No actual runtime, model, GPU, network, browser, media decode or ledger action was executed by this reviewer. All reviewer files stay under this evidence root. Final source hashes before/after match. Complete tracked pack git diff HEAD is git-diff-HEAD-final.patch; untracked harness content is harness-final.py.txt.

## Development outline (authority copied, no advancement)

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

Current coordinate: R1/WP-R1-U3; completed: independent component source/CPU review; last gate: offline review only; blocker: actual component outcome and remaining real product coverage; route: unified-media correction with V0–V3 unchanged; remaining: bounded component evidence, independent diagnosis, full quality/public coverage and human signoff; next owner: parent Codex; authorization: no new request from this review; evidence: this directory; stop reason: isolated pre-execution review complete.
