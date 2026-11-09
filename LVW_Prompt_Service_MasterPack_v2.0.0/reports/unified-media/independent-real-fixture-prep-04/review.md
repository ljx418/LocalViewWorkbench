# Independent real rejection fixture preparation review 04

Disposition: Fatal0/Major0/Minor0; no open source/CPU safety blockers before sealing/one actual preparation. Base HEAD23e967bd3d8cc38640cb5749d467d9e34c510c29. This is fixture-preparation review, not real fixture existence, rejection-path acceptance or Stage PASS.

Harness preflight rejects either reused report/artifact root, checks tracked Git/source cleanliness (ignoring only untracked __pycache__), freezes app/kernel/helper/harness files, checks ffmpeg/ffprobe against live14 SHA, and child-binds source/tool/root. Source/runtime/helper are unchanged from HEAD. Tool SHA is rechecked per attempted command. No model/GPU/browser/network/download/Comfy start is present. Reservation is CPU fixture=True,0model/0provider/0full,120seconds; existing reserve rejects nonzero model/full/starts for CPU fixtures. Candidate sealing is still required before harness preflight can pass for its currently untracked source.

Artifact root is explicit external .lvw-runtime/.../R1-unified-fixtures/real-rejection-fixtures-04, atomically mkdir(exist_ok=False) claimed with owner record. The script never recursively deletes this retained-input root. Existing collision is a no-op preflight rejection. Generated/failure inputs remain outside Git and are explicitly unusable unless final ready assertions complete; this declared retention is distinct from a private temporary directory.

Exactly three media assets are created: one CPU libx264 black3842x2160/one-frame MP4, sparse all-zero logical256MiB+1 MP4, and empty MP4. There is also a small nonmedia owner record.3842*2160=8,298,720 exceeds the unchanged8,294,400-pixel gate. The FFmpeg output is asserted0<size<14MiB; combined with256MiB+1 and0, integer total≤270MiB. Sparse creation uses exclusive xb/truncate and fsync; it does not fill256MiB in memory. The first MP4 is probed as constrained local mov with protocol whitelist file,pipe and enable_drefs0; actual width/height and positive bounded duration must match before ready. Thread1 software encoder, one command per tool, captured total output≤1MiB,60s/15s direct-tool waits are fixed. Bytecap proof is by code/math, not actual generation; per-command resource limits and final wall settlement still govern actual execution.

Existing process_module.run_bounded launches shell=False/direct handle, bounded stdout+stderr, terminates/waits its own handle on timeout, joins pipe readers and closes pipes before invoking on_result. Nonzero exit/timeouts/output caps can still emit cleanup receipt before throwing; these remain unusable fixture failures. Callback writes raw logs+hashes before marking completed. Missing callback or uncertain pipe cleanup makes attempted≠completed, closes reservation retaining budget, and writes NO_GO_CLEANUP_PENDING. Settling0 requires every actually attempted handle to have that callback; unattempted tools require no fabricated receipt.

Independent tiny-file/mock checks: two valid exit callbacks with deliberately wrong probe dimensions→NO_GO/unusable/settle0; missing first callback→NO_GO_CLEANUP_PENDING/retain; existing artifact collision→no reserve/tool call and untouched sentinel; reserve failure→terminal receipt/no settlement. No actual FFmpeg/ffprobe, large logical allocation, ledger, GPU, network, browser or model action occurred. Mock files are tiny and all reviewer writes remain inside this report root. Source hashes before/after match; production subtree manifest and full tracked staged+unstaged pack diff are preserved. Untracked harness snapshot is harness.py.txt.

No broad suite was repeated because app/source143 is unchanged. Actual preparation must still produce raw tool receipts, probed metadata, retained asset sizes/hashes, source binding and terminal settlement. Prepared assets would enable later public negative coverage; they cannot themselves close UM02, original temporal-quality UM04, full fixed acceptance or human signoff. Original tracking video and human holdouts remain untouched.

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

Current coordinate:R1/WP-R1-U3; completed:isolated fixture-preparation safety review; last review gate:CPU/static/mock; blocker:actual prepared inputs followed by real public negative coverage and other full gates; route:unified-media correction,V0–V3 unchanged; remaining:sealed preparation/UM02/UM04/full coverage/human signoff; next owner:parent Codex; authorization:approved03 CPU generated inputs scope; evidence:this directory; stop reason:isolated pre-execution review complete.


## Final safety addendum

Reviewed the only subsequent harness changes: immediately before each real direct tool action, recheck program.approved(), unchanged parent grant SHA and child expiry; map WAIT_AUTH/WAIT_BUDGET exception details to terminal decision. Those checks occur before incrementing attempted or invoking run_bounded. A denied action cannot manufacture a tool callback requirement or run the tool. Source/tool/replay/retention rules remain as reviewed. Hash/TTL assertions fail closed; their generic assertion text is NO_GO rather than an invented authorization diagnosis.

All four prior tiny-file/mock scenarios were rerun against harness-final.py.txt with program.approved() stubbed: both exit callbacks with rejected dimensions, missing callback, existing root collision, and reserve rejection. All pass; raw logs are *-final.log. No actual FF tools, ledger, model/GPU/network or large allocations occurred. Final-before/final-after source hashes match. Initial snapshots/logs are preserved; final source diff is git-diff-HEAD-final.patch. Disposition remains Fatal0/Major0/Minor0, no open pre-execution safety blockers, no product acceptance.
