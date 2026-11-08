# Independent static/offline review

Candidate: `e420eb5d26949d38711f53e38c98c415c9e1160b`.
Detached independent worktree: `/tmp/lvw-independent-e420eb5` (clean at review end).
Read AGENTS.md, governance README, execution control, docs/24, approved docs/27, and frozen R1 packet 1.0.2. No product files changed. No model calls, GPU probes, service starts, network requests, visible browser or holdout inference. The only Windows subprocesses were harmless `cmd.exe /d /c set LVW_REVIEW_ENV_MARKER` to verify interop environment transport.

Decision: CHANGES_REQUIRED for this candidate. Fatal 0 / Major 3 / Minor 0. This is not a Stage PASS or human signature. Real checkpoint evidence remains NOT_RUN / not supplied to this reviewer.

## Major M1: malformed provider envelope loses the original response

Location: `lvw/backend/app/provider.py:315-320`, publication `service.py:140-142,166-177`.
Trigger: Ollama returns HTTP 200 with non-JSON response text, e.g. `RAW MALFORMED RESPONSE`.
Expected: failed ModelRun preserves original response and is reachable through job.result_ref, as required by packet's original-content retention and docs/27 raw display.
Actual: error lacks raw_response; service reads empty raw and creates no ModelRun. Job is failed/PARSE_PARTIAL, result_ref null; run count zero.
Reproduction: `PYTHONPATH=lvw/backend python3 raw-probe.py` with the attached script. It executes real OllamaProvider response parsing and real AnalysisService publication with httpx.MockTransport; leases/telemetry are replaced with CPU fakes. `raw-probe.log` retains actual output. Existing 66 passing tests do not detect this failure.

## Major M2: Windows Ollama does not receive the intended environment protections

Location: `lvw/backend/app/runtime.py:81-85`; production `START_LVW.cmd` launches WSL Python and configures a Windows `ollama.exe` path. The runtime accepts only `ollama.exe`.
Trigger: normal WSL -> Win32 launch with WSLENV absent or not listing OLLAMA_HOST/OLLAMA_NO_CLOUD/NO_PROXY. No such registration exists in this production path.
Expected: actual Windows Ollama process receives explicit loopback binding, cloud disable and proxy bypass settings.
Actual: setting the Linux subprocess env dictionary alone does not transport those variables across WSL interop. Ollama inherits corresponding Windows environment/defaults instead; configured cloud-disable and local binding cannot be guaranteed. This can also prevent readiness under preexisting Windows OLLAMA_HOST settings.
Reproducible CPU evidence: `windows-env.log` shows a fresh marker in the Linux env is undefined in cmd.exe (exit 1) without WSLENV, and present (exit 0) with marker/w. No Ollama process was started. Repository's older tools/r1a_ollama_wrapper.ps1 sets env on Windows explicitly, but production runtime._spawn does not use it. Fix must preserve owned-process shutdown semantics and verify actual native server settings; importing old harness success is insufficient.

## Major M3: frozen wall-clock budgets do not enclose preparation and release awaits

Locations: `service.py:103-112,135,154`; `provider.py:168-170,198-216`.
Trigger: a slow/dribbling inventory/unload response, slow acquisition or preparation. HTTPX per-operation timeouts bound inactivity, not total request duration.
Expected: analysis total has a 420-second monotonic bound covering acquisition/preparation/inference; release has an independent 30-second total bound, retaining unknown/releasing if unproven.
Actual: the only 420-second wait_for starts after acquisition/decode and wraps inference only. release's 30-second condition is checked before awaits, but each unload/inventory/snapshot/sleep may run after deadline; release itself has no encompassing wait_for. Cancelling during acquire has no provider task to cancel, so it also relies on the unbounded acquisition completing. Fixed decoder subprocess bounds reduce ordinary duration, but do not implement the frozen total wall limit.
Offline proof: budget-probe.py supplies a virtual monotonic clock; a pending inventory returns at t=31 under a 30s budget, and release still calls snapshot and sleeps before returning. budget-probe.log records this. The probe deliberately models delayed dependencies; it does not claim a measured 31-second real Ollama hang. Production HTTPX streaming responses can keep read inactivity below the per-read timeout while exceeding a total deadline. Apply total timeout around the relevant scope, retain ownership/unknown semantics, and test acquisition/preparation cancellation and release deadline exhaustion.

## Coverage and boundaries

- `PYTHONDONTWRITEBYTECODE=1 LVW_DATA_ROOT=/tmp/lvw-review-default PYTHONPATH=lvw/backend python3 -m pytest lvw/tests -q -p no:cacheprovider`: exit 0, 66 tests. Full raw pytest log attached.
- Frontend copied to separate `/tmp/lvw-review-frontend-e420eb5`; dependencies reused from installed node_modules without download. npm test: 9/9; typecheck and build: exit 0. Built hashes/filenames match committed dist. frontend.log attached.
- Read actual FastAPI default_app/run_local -> MediaStore -> VideoKernel pure CPU modules -> AnalysisService -> OllamaProvider; decoder module loading avoids Comfy/torch/numpy. Real CPU FFmpeg fixture contract test executes VFR upload/decoding and checks source PTS and temp cleanup.
- Existing tests demonstrate queued cancellation, late provider success suppression, failed release maps to unknown, idempotency and body bounds. These tests use fake resource release and cannot establish actual GPU cleanup/native process ownership.
- React adoption binds export source to adoptedRun rather than latest selected media/run; choose/reanalysis leaves human draft intact. TXT is plain draft output; JSON carries the adopted source. Confirm-before-replace is implemented for existing nonempty or dirty draft. Static checks and domain tests do not replace real browser combinations.
- Actual native model digest/settings, external process protection, GPU three-sample release, real headless browser cancellation/adoption/export, and native launcher runtime remain unverified until candidate-bound raw real evidence is supplied. No claim of UM10/10.

## Required project status snapshot

|Stage|Completed/total|Scope/status|
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

1. Current coordinate: R1 / WP-R1-U1 / IMPLEMENTATION_INNER_LOOP (execution-control snapshot).
2. This batch: independent static/offline review only; three Major findings.
3. Last passed gate: R1_UNIFIED_GATE0 (scope approval, not implementation acceptance).
4. Blocking gate: UNIFIED_FRONTEND_IMPLEMENTATION_AND_VERIFICATION; findings require correction.
5. Global route: only V0-Min and R1a single-image accepted; S2 historical 7/8 retained.
6. Remaining: corrections, candidate-bound retests, fresh real checkpoint, independent raw-evidence recomputation, unified human signature.
7. Next owner: implementing/gate owner; reviewer available for corrected candidate and evidence.
8. Authorization: offline review used; no new live execution performed by reviewer.
9. Evidence: reports/unified-media/independent-static/.
10. Exact stop: STATIC_REVIEW_CHANGES_REQUIRED_AWAIT_CORRECTED_CANDIDATE_AND_LIVE_RAW_EVIDENCE.
