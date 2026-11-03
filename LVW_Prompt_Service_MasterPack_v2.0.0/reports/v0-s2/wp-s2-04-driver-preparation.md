# WP-S2-04 trusted driver preparation

Repository-only implementation; not a Stage acceptance receipt.

Added tools/v0_s2_http.py: fixed literal-loopback Comfy/Ollama endpoints, explicit control path/method allowlist, no redirects or proxies, bounded request/response, total response deadline, same-origin video-control headers, and connection/response cleanup. A close-after-response socket remains deadline-controlled after HTTPConnection detaches it. Global interrupt is not an allowed path.

Added tools/v0_s2_driver.py: reuse the unchanged historical S1 lifecycle ownership and terminal checks. Override HTTP, UTF-8 native PowerShell output, explicit bounded submission accounting (failed submissions consume budget), and process-local LVW_FFMPEG_EXE/LVW_FFPROBE_EXE settings. Import or construction does not start a service. This is a low-level adapter: the pending orchestrator must validate child authority and all sealed identities before invoking it.

Added tools/v0_s2_seal.py: compare the complete selected execution inventory and every file's bytes with candidate Git objects, including JS, workflow and configuration files when selected. Added files, altered bytes, missing files and symlinks fail closed. A real temporary Git repository test first exposed cwd-relative ls-tree output; fixed using --full-name, then verified nested pack prefix handling. No historical Harness changed.

Verification: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest LVW_V0_RuntimePatch.tests.test_s2_seal LVW_V0_RuntimePatch.tests.test_s2_driver LVW_V0_RuntimePatch.tests.test_s2_http LVW_V0_RuntimePatch.tests.test_s2_bindings -q; exit 0, 16 tests, 1.423s. Tests use synthetic HTTP/process substitutes and a temporary Git fixture; they are not target service results. Initial seal-test failure and its correction are recorded above rather than counted as product evidence.

Contract changes: none. Provider calls: zero. Services started: zero. Stage live checkpoints consumed: zero.

Current pack validation after updating the three stale entries and adding six execution/test files: exit 0, 1373 passed, 0 failed. Governance self-test: exit 0, errors empty. git diff --check: exit 0. These structural results do not establish product acceptance.

Binding inventory 03 is terminal NO_GO / BUNDLED_DECODER_SCAN_LIMIT. Three target identities were recorded before the existing-installation search reached its fixed 20000-entry cap; no sample hashes were collected. Services/provider/checkpoints remain zero. Authorization expired at terminal. Do not repeat the same broad scan; resolve a specific existing decoder location from historical inventories or configured launch paths first.

Remaining: exact decoder/sample bindings; candidate-bound orchestrator and fixed sample/category matrix; real decoder/native node/browser compatibility; raw 10+10 resource/performance observations, negative cases, scoped cancellation and cleanup; independent review and human acceptance. No V0.1 or full V0 PASS claim.
