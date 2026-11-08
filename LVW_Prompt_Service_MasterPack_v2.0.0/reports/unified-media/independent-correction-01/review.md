# Correction candidate independent review

Candidate: `5f154dcab3edec5ed79b1475029d45be44d9ba11`.
Independent detached worktree: `/tmp/lvw-independent-5f154dc`; clean at completion. Product files unchanged. Read implementation diff independently before its correction receipt; existing report was navigation, not acceptance evidence. `offline-02` was not present in the candidate worktree and was not used as proof.

Decision: CHANGES_REQUIRED. Fatal 0 / Major 1 / Minor 0. Previously raised M1/M2/M3 are corrected in the inspected paths, but the newly added native ownership code has an unproven-exit path. No Stage PASS, real GPU/model acceptance or human signature is asserted.

## Major C1: exited Windows wrapper bypasses native terminal proof and permits replacement

Location: `lvw/backend/app/runtime.py:130-137`, `status:40-69`, `_spawn:98`, and native owner lifecycle `native_runtime.py:16-23`.

Trigger: PowerShell/WSL wrapper exits or fails after launching the Windows Ollama process, while its owner JSON is missing or remains starting/listening. Wrapper returncode does not prove the native process exited; the wrapper may have been terminated before its finally block completed. The same path also handles process=None with unresolved _native state.

Expected: retain unresolved native ownership and report RESOURCE_RELEASE_PENDING/unknown; prevent start/reset replacement until original native terminal proof is established. Never claim stopped/clean just from wrapper termination. Recovery must remain constrained to the original process identity/handle and must not kill unrelated processes.

Actual: `_stop_owned` returns early before checking `_native` or state=exited. It clears self.process, and close returns without error. status derives stopped/can_start=true from provider readiness and wrapper state. Subsequent _spawn overwrites the unresolved descriptor. This loses the only native owner/nonce binding even though shutdown is unproven.

CPU reproduction: native-probes.py constructs the actual runtime with an already exited fake wrapper (returncode=1) and a valid nonce-bound owner record state=starting. It calls actual runtime.close/status. native-probes.log records: exception=None, process_cleared=true, native_ownership_unresolved=true, runtime_state=stopped, can_start=true. No real service was launched. This is an error-path test; it does not claim a real orphan was observed on this host.

## Previous findings recomputed

- M1, raw preservation: original independent raw probe rerun against this candidate now yields failed/PARSE_PARTIAL with a non-null run reference and retained_runs=1. The provider explicitly attaches exact raw text on invalid envelope; failed publication now remains queryable. raw-probe.log attached.
- M2, WSL environment: production prepare now constructs a Windows PowerShell script that explicitly sets OLLAMA_HOST/OLLAMA_NO_CLOUD/NO_PROXY before Start-Process. runtime also adds corresponding /w WSLENV entries. Independently generated the script and passed it only to PowerShell Parser.ParseInput: AST_ERROR_COUNT=0, explicit_windows_env=true. The script itself was not executed. This corrects the missing transport configuration; actual native server environment remains a live evidence obligation.
- Native ownership positive path: script obtains the original Process.Handle before polling; Kill/WaitForExit acts through that Process object, not a rediscovered PID. Nonce stop marker is unique; listener ownership compares native PID; owner includes birth ticks; WSL stops the wrapper through its nonce path. No global PID/name kill or environment persistence was introduced. Positive-path inspection does not close C1.
- M3, total budgets: AnalysisService now sets one loop-time deadline before acquire and passes remaining budget to acquisition, shielded preparation and inference. acquire is registered for cancellation. Decode cleanup is bounded and combined with release under a 30s remaining cleanup budget. Provider.release has asyncio.timeout(30) and checks monotonic deadline after inventory and telemetry awaits. Original virtual-clock probe now has no snapshot_after_deadline event. A separate CPU probe scales the outer release timeout to 0.02s and blocks inventory for 20s: actual elapsed 0.021s, released=false, lease retained. budget-probe.log and release-bound.log attached. Actual FFmpeg/GPU release remains unverified.

## Verification and boundary

`PYTHONDONTWRITEBYTECODE=1 LVW_DATA_ROOT=/tmp/lvw-review-5f-default PYTHONPATH=lvw/backend python3 -m pytest lvw/tests -q -p no:cacheprovider`: exit 0, 69 tests. Raw log attached. These tests do not cover C1 and mostly inject runtime spawn.

No model calls, GPU probes, real services, network, holdout input or visible browser. Native AST parsing is a CPU-only PowerShell process; no generated Start-Process script was executed. No claim that the new native launcher has run successfully. Await corrected candidate and candidate-bound live-01 raw evidence for independent recomputation.

## Required status snapshot

V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1/R2/R3/R4/R5a/R5b/R5c each 0/4. Current R1. Counts remain execution-control facts and were not incremented for this review.

1. Coordinate: R1 / WP-R1-U1 / IMPLEMENTATION_INNER_LOOP.
2. Completed: corrected-candidate independent review and CPU checks; prior three findings closed in inspected paths, one new Major.
3. Last gate: R1_UNIFIED_GATE0 scope approval only.
4. Blocker: C1 native exit proof and real checkpoint verification.
5. Route: unified early slice; historical S2 retained, full R1/V1 incomplete.
6. Remaining: C1 correction, candidate-bound recheck/live evidence, independent recomputation, human signature.
7. Next owner: implementer/gate owner.
8. Authorization: CPU/AST only used; no live launch by reviewer.
9. Evidence: reports/unified-media/independent-correction-01/.
10. Stop: CHANGES_REQUIRED_NATIVE_EXIT_PROOF_GAP.
