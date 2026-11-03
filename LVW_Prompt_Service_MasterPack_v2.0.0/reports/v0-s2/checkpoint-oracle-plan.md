# V0-S2 checkpoint oracle preparation

Implemented tools/v0_s2_checkpoint_oracles.py for deterministic recomputation only. It never starts services and never emits Stage PASS.

Performance input: exactly ten hot images and ten hot four-frame videos; one checkpoint run/candidate identity, unique sample-run IDs, succeeded outcome, OOM=false and exact one/four provider-call counts. Cold observations must use their own predeclared phase and cannot be removed from the hot list after slow results. P95 uses nearest rank (for n=10, the maximum). Frozen ceilings remain 180/300 seconds, GPU strictly below 23552MiB, RAM at least 2048MiB.

Measurement protocol for the pending runner: sample at one-second intervals; accepted inter-sample/terminal observation tolerance <=1.5 seconds, start observation <=0.5 seconds. Missing, nonmonotonic or incomplete traces fail rather than claiming peak coverage. These are evidence collection requirements, not relaxed product thresholds.

Cancellation input separates acknowledgement, actual stop and release timestamps; ack<=1s, release-after-stop<=30s, explicit late discard/draft preservation/owned-only control/cleanup and zero non-owned terminations required.

Directed tests: 6/6 PASS using explicitly synthetic observations, including fixed denominator, wrong candidate/run, skip/OOM, duplicates, missing traces, exact and one-over thresholds and P95 versus average. These tests are not product performance results.

Pending: complete candidate/authorization/executable/sample bindings, immutable runner identity, native service driver, fixed video-category/security matrix, public browser controls and raw observation capture. Existing S1 lifecycle ownership code has been inspected for reuse; no historical Harness or failure evidence changed. No external operation or checkpoint consumed.
