# Focused read-only review — c131789

Candidate: `c1317894c72b425cadf88d34fda07defc9e65285`.
Method: inspect exact Git delta from independently reviewed 87c64a3, including product provider.py and checkpoint. No new service/GPU/model/browser/network execution, no holdout read, no product writes. No new CPU suite was run for this one-line product logging addition.

Product change: admission_snapshot now records the baseline before capacity comparison. GPU free >=19047 MiB, GPU used <23552 MiB and available RAM >=2048 MiB remain unchanged. This will preserve the raw admission numbers on the capacity-rejection path. Inventory rejection or failed telemetry still occurs before the event; absence of this event must not be called proof of a capacity shortfall.

Windows health addition uses bounded native curl with proxy bypass against actual WSL /health, and preserves its response. It checks return code but does not itself assert the returned build identity. Existing independent source_build_id binding remains necessary. This added probe is configured, not executed by this reviewer.

For admission-rejected live-02-like failures with no active/queued job, public runtime stop before archive corrects the specific ordering that lost its native exited proof. cleanup-stop-response is now retained. Historical live-02 is unchanged and its missing terminal proof remains missing.

## Residual Major L1 scope: active/queued failure cleanup still archives too early

Locations: new checkpoint finally block: runtime stop -> archive -> job cancellation -> API SIGTERM; AnalysisService.runtime_control rejects runtime operations while active or queued.

Trigger: browser/checkpoint fails while an analysis is active or queued. The early runtime/ollama/stop returns RESOURCE_BUSY/409. The harness records cleanup_error but proceeds immediately to archive owner/logs. Only afterwards does it discover ledger jobs, send cancel and SIGTERM API. Shutdown may produce the native exited proof later, which START_LVW removes along with the run root. Thus the original loss mechanism is still possible on that error branch.

Expected: collect the native terminal proof after the actual cancellation/runtime shutdown sequence and before temporary-root deletion, or preserve an explicit unresolved record without deleting its evidence. Cancellation must keep the frozen cleanup/resource budget and original process ownership constraints.

Actual: no wait for job terminal state occurs before the new stop call or before archive; a non-200 stop does not defer the archive. This is directly reproducible by following the actual service's active-job 409 branch and checkpoint statement order; no service was run to simulate it.

Recommendation for the remaining slot: cancel owned jobs and wait for bounded terminal/release first; stop owned runtime and verify native terminal proof; archive then end API/launcher. Keep failure records when any step remains unknown. This is harness preparation, not justification for a new live attempt while resource admission is still below the frozen threshold.

Focused result: no new product-code Fatal/Major found in this logging-only delta; one residual harness evidence-capture Major remains for active/queued failure paths. WAIT_RESOURCE is an accurate operational stopping reason. Full real acceptance remains NO_GO/incomplete and human signoff must not be requested yet.

Required progress: V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1/R2/R3/R4/R5a/R5b/R5c each 0/4; current R1. Coordinate: unified early slice. Batch: focused logging/harness review. Last gate: scope-only R1_UNIFIED_GATE0. Blockers: WAIT_RESOURCE, incomplete real sequence and residual L1 error path. Route/counts unchanged. Remaining: prepare error-path evidence retention, bounded live-03 only when admissible, independent evidence review and human signature. Next owner: gate owner/executor. Reviewer used read-only CPU diff inspection. Evidence: independent-correction-01/. Stop: WAIT_RESOURCE_NOT_STAGE_PASS_NOT_HUMAN_SIGNATURE.
