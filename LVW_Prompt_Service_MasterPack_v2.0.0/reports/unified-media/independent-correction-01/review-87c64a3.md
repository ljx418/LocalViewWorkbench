# Independent correction recheck — 87c64a3

Candidate: `87c64a311e1608dc6abfc9a35fb6651eedb92307`.
New independent detached worktree `/tmp/lvw-independent-87c64a3`, clean at completion. Read exact delta from 5f154dc before testing. This supersedes the C1-open finding for this new candidate only; the original 5f154dc report and logs remain historical.

Static/offline result: Fatal 0 / Major 0 / Minor 0 within reviewed scope. All four previously identified findings (M1, M2, M3, C1) are closed in this candidate's inspected paths. This is not a Stage PASS, UM10/10, real runtime acceptance or human signature.

## C1 independent recomputation

runtime._stop_owned now examines native ownership before wrapper returncode. Missing/starting/listening owner state keeps descriptor and reports RESOURCE_RELEASE_PENDING. start also runs this gate before replacing native ownership; status suppresses can_start and reports error. Public stop handles unresolved native even when wrapper is dead. Proven exited owner permits clearing.

An independent CPU probe covers missing, starting and listening owner states, each through close/start/stop, plus the proven-exited close path. Nine unproven combinations returned RESOURCE_RELEASE_PENDING, kept both original wrapper reference and native descriptor, state=error and can_start=false. Only valid exited proof cleared both and returned stopped/can_start=true. Raw probe source/output attached as 87c64a3-native-probe.py/.log. No native service was started.

## Previous corrections retained

Original raw-response probe rerun: failed PARSE_PARTIAL has non-null result_ref and retained_runs=1 (87c64a3-raw.log). Outer release timeout rechecked at a CPU-scaled .02s with a blocked inventory await: timely false return and retained lease (87c64a3-release.log). Native PowerShell generation is unchanged from the prior independent AST review (0 parser errors); the source still explicitly sets Windows-side OLLAMA_HOST/OLLAMA_NO_CLOUD/NO_PROXY before starting the original process object, retains its Handle, uses nonce stop, and records native PID/birth/listener/exit. Native actual environment/process exit remains a live evidence obligation.

The launcher in this candidate checks Windows GetActiveTcpListeners and performs the WSL bind check instead of treating curl timeout as a free-port/occupied-port verdict. Its CPU contract test passes. Real launcher behavior is not inferred from the string assertions.

## Checks and boundary

`PYTHONDONTWRITEBYTECODE=1 LVW_DATA_ROOT=/tmp/lvw-review-87-default PYTHONPATH=lvw/backend python3 -m pytest lvw/tests -q -p no:cacheprovider`: exit 0, 70 tests. Full log attached. No model, GPU probe, services, network or holdout/browser execution by this reviewer. No product writes. Await candidate-bound live-02 terminal raw evidence for independent recomputation; ongoing execution is not yet accepted.

## Required status snapshot

V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1/R2/R3/R4/R5a/R5b/R5c each 0/4; current R1. No progress count was incremented by offline review.

1. Coordinate: R1 / unified early slice.
2. Completed: independent corrected-candidate CPU/static review; four findings closed.
3. Last passed gate: R1_UNIFIED_GATE0 scope approval, not implementation acceptance.
4. Current blocking gate: real checkpoint and its independent evidence recomputation.
5. Route: early unified React/FastAPI slice; complete R1/V1 remain incomplete.
6. Remaining: live raw-evidence recomputation and human unified signature.
7. Next owner: trusted executor/gate owner; independent reviewer awaits terminal evidence.
8. Authorization: reviewer used CPU/AST scope only.
9. Evidence: reports/unified-media/independent-correction-01/.
10. Stop: OFFLINE_RECHECK_CLEAR_AWAIT_LIVE_TERMINAL_EVIDENCE_NOT_STAGE_PASS.
