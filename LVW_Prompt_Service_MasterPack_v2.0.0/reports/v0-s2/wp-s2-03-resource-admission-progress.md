# WP-S2-03 resource admission progress

Status: IN_PROGRESS; no target-machine probe or hardware PASS.

Integrated owner now performs read-only native resource admission before preparation and again before model entry. Native Windows RAM comes from GlobalMemoryStatusEx; bounded nvidia-smi subprocesses query one GPU's total/used/free memory and compute PIDs. Existing S0/S1 prestart threshold used<=4096MiB is retained; available RAM must be >=2048MiB and GPU capacity must support the frozen <23GiB runtime ceiling. Foreign compute PIDs are rejected; only the current Comfy process PID is excluded. No process is stopped or reconfigured. Missing, malformed, multi-device or unproven telemetry fails closed with RESOURCE_BUSY.

Preflight evidence is returned alongside token/frame metadata for the run. The second check prevents decode-time changes in external occupancy from silently entering model inference. This is an admission snapshot, not a promise that an external client cannot start later; runtime sampling and resource-stop Harness remain required.

Directed verification: resource/request/API suites 14/14 PASS. Exact 4096MiB/2048MiB boundaries and one-over/one-under, unknown telemetry, foreign PIDs, multiple GPUs, missing executable with zero spawn, denial before decoder, and new contention after decode with zero model invocation covered. All telemetry is injected; nvidia-smi and native RAM APIs were not run.

Current coordinate updated to WP-S2-03 implementation. Next: candidate-bound runtime runner, trusted executable/sample bindings and offline receipts, then program-scoped child authorization before native probes/checkpoint. Existing Stage fixed denominator and performance thresholds unchanged.
