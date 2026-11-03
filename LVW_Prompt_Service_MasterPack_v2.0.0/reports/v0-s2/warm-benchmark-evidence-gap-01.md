# Warm benchmark evidence gap 01

Gate-owner finding: OPEN / Major, before the first full S2 checkpoint. Evidence clarification approved against existing docs/02_UX_TARGET.md (temporary warm retention and restoration), docs/13_V0_IMPLEMENTATION.md (default unload), docs/06_ACCEPTANCE.md and the frozen V0-A09 obligations. No denominator, numeric threshold, business contract or external budget is changed.

Production default `core.build_chat_payload` uses keep_alive=0, and the video path performs cleanup after each frame. Resource admission also rejects prestart GPU usage above 4096 MiB and foreign compute PIDs. Thus a naive loop with phase='hot' would mislabel cold calls; loading the model externally before that loop is not a safe substitute for an owned warm profile.

Required implementation remains OPEN: a bounded, process-local warm benchmark profile; verified ownership of the retained model/runtime; real pre-call residency observations for each image/four-frame call; error/cancel cleanup; restoration to default unload with /api/ps and GPU evidence. Preserve actual full request latency and all 10+10 samples. Never subtract load time to manufacture a passing latency or call an unverified cold run hot.

Oracle correction: performance_oracle now requires a frozen model digest and one raw /api/ps model snapshot per measured call (one image, four video), with ordered same-run elapsed times, correct model tag/digest and positive GPU residency. Missing/foreign/unloaded/CPU-only/different-digest or incomplete observations fail closed. Exact P95/resource thresholds and 20-record denominator stay unchanged. Caller acquisition and raw log/source binding still need the real runner and independent recomputation; this pure oracle cannot establish evidence truth by itself.

Directed command: python3 -B -m unittest LVW_V0_RuntimePatch.tests.test_s2_checkpoint_oracles -q. Actual result: 7 tests, exit 0, OK (0.014 seconds). These are offline synthetic oracle tests, not real hardware measurements.

The original offline-checkpoint-02 and workbench-directed-01 receipts retain their original candidate identities. They do not certify this later oracle correction. Stage acceptance and all performance outcomes remain NOT_RUN.
