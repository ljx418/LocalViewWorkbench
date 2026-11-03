# S2 native runtime and physical release progress

Implementation candidate: 49a909788b3a7c9f2f6b2b663ceb41d8628bb833. Packet: V0-S2/1.0.6. Full sealed receipt: offline-checkpoint-05/receipt.json. All five checks passed: 262 V0 subtree tests; production UI module VM; 1444 pack/schema checks; governance/negative self-test; whitespace. Execution payload pre/post seals matched. Synthetic fixtures prove control branches, not hardware behavior. No service/model/media/browser runs or Stage checkpoint attempts occurred in this batch.

Changes: native clock/lifecycle adapter using installed Comfy Python; birth-bound listener and sampler ownership, native worker absence before cleanup claims; separately charged twenty-preload limit and bounded clock/control calls; exclusive sampler PID lease; refusal of stale samples after worker exit or resource violation. Registered analysis nodes request actual re-execution for unchanged inputs while manual nodes retain their behavior.

Physical release now binds a cold baseline before inference, confirms unload and empty inventory, then waits for three consecutive one-second samples at or below baseline+1024 MiB inside the shared thirty-second deadline. Model-list unload alone is distinguished from physical release. Raw release origin, samples and final elapsed time are retained. Missing baseline/telemetry, incomplete stability and timeout cannot release quarantine. Independent measurement joins reject logical-only release, one-over memory, too few/too-fast samples, wrong baseline, invalid release origin and over-budget release.

Production paths: NativeRuntime -> existing owned lifecycle and pinned native sampler; registered bridge -> InterruptibleOllamaTransport.cleanup -> bounded native GPU probe; warm request -> cold baseline binding -> provider calls -> cleanup -> raw release evidence -> hot_record independent join. Runtime adapter construction has no native/socket side effects. There is no standalone authorized complete Stage runner yet.

Current coordinate: V0-S2 / WP-S2-04 / GATE1_OFFLINE_IMPLEMENTATION. Last passed gate: candidate-bound offline05, not Stage PASS. Current blocking gate: native public video/UI integration and complete checkpoint coordination. Last native GPU admission remains the historical refusal in expired native-component-01; current GPU readiness is unknown, not inferred from earlier messages.

Global route: accepted V0-Min/R1a -> S2 in progress -> S3 -> R1/R2 -> full V1. Remaining: real Stage/fault/browser coordinator; fresh program child bindings and all four video categories/security negatives; full fixed 10-image/10-four-frame performance and cancellation/cleanup; cumulative nine cases; isolated independent review; human experience signoff. No shrinking of cases or thresholds.

Next owner: Codex S2 implementer. Offline implementation requires no new authorization. Native runs require a fresh bounded child within AUTH-PROGRAM-V1-LOCAL-01; no run has been silently granted by this implementation. Stage human signoff and final V1 release remain human-only. S2 is unaccepted, so no Stage push is due; no remote push performed.

Evidence: reports/v0-s2/offline-checkpoint-05/; native-runtime-release-decision-01.md. Stop reason for this checkpoint: sealed offline runtime/release batch complete; actual Stage runner/native/browser/human gates pending. Full V1 objective remains active.
