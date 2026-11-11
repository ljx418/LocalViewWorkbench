# S3-PREP-C correction-02 implementation

READY_FOR_REVIEW only; candidate `9fc71b9551959c351016939196056b98b25a8acc`, base `08daf12b87340eb5fcdd64c3d4444ee686ef712b`. No independent review, Stage PASS, or product Gate0 claim.

Local adapter changes preserve true OS exit, runner error, byte/hash evidence and capture limit; reject error-bearing probe documents and frame bytes even without budget. Owner also rejects error-bearing operation results. Probe capture overflow stops globally with sticky `probe_capture_limit_exceeded` / `PREPARATION_FAILED_PROBE_CAPTURE_LIMIT_EXCEEDED`; this is a 4MiB operational metadata cap, not an assertion of exceeding the 80MiB preview budget. Existing ffmpeg output and timeout sticky semantics remain intact.

New six-case matrix: two real owned Python probes emitting valid JSON plus stdout/stderr overflow; four explicit error cases for probe/frame with/without budget. Real runner unchanged, genuine exit0 retained; CLI exit1, zero frames and later resolve/stat/hash/decode, child waitpid confirms reaped, staging and enclosing owned roots removed. The poll wrapper waits at most two seconds for actual OS exit after readers start, selecting the short-lived-child timing without fabricating returncode. Full receipts and bounded output hashes appear in raw test stdout.

First matrix had 2 pass/4 fail due to missing test-only Image import, retained as draft-matrix. Corrected first matrix 6 pass. First complete suite 76 pass/1 fail because the child raced to real -15 rather than required exit0; retained as first-suite. Deterministic timing correction followed by final matrix and full suite is recorded separately; this extra complete run is disclosed and was necessary after the observed test failure. Original 71 test bytes and oracles preserved unchanged.

Only two tools and this new evidence directory changed. Old raw/quality-set/prelabels/manifest/plans unchanged; original successful run identities e1798f33/335a8b97 and frozen10+6 stay untouched. No real-source, old-preview, new-real-child, model, GPU, service, network, download or product checkpoint action. Synthetic CPU children did run; zero-action claims describe execution paths, not comprehensive OS auditing. Linux/WSL and L02-L07 limitations remain.

十字段：当前坐标 R1/WP-R1-U3/S3_PREP_C_RUNNER_FAILURE_PROPAGATION_CORRECTION；本批完成局部实现及合成自检；最后通过门禁为统一切片UM10与范围人签；当前阻塞门禁IC-MAJ-01待隔离复核；全局路线S3→V1准备；剩余独审/root裁决与产品Gate0；下一责任人协调者及独审；无需新增授权；证据目录本目录；精确停止原因为实现交付完成等待独审。

|阶段|已完成/总数|
|---|---|
|V0-S0|1/2|
|V0-S1|5/5|
|R0|1/2|
|R1a|5/5|
|V0-S2|7/8|
|V0-S3|0/6|
|R1|0/4|
|V1-M1|0/3|
|R2|0/4|
|R3|0/4|
|R4|0/4|
|R5a|0/4|
|R5b|0/4|
|R5c|0/4|

Current Stage R1; all formal counts unchanged. Four-role status details are copied from the authoritative execution-control into receipt.json.

Final result: full suite **77 passed in 21.76s, exit0**; final matrix **6 passed / 71 deselected, exit0**. All recorded owned TemporaryDirectory roots absent after cleanup.
