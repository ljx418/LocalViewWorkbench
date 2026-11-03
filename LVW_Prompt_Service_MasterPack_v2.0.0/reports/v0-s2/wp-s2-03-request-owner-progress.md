# WP-S2-03 request owner progress

Status: IN_PROGRESS; no product PASS. Added internal VideoRequestOwner spanning decoder preparation, tensor conversion, existing four-frame Bridge and terminal publication. Shared inference lock is reentrant only for its owning thread so integrated preparation can call the existing Bridge without releasing the slot; other threads remain excluded.

State tracks bounded run token, cancel epoch, preparing/running/cancelling/terminal status and busy/releasing/released/unknown resource state. Replayed/current-mismatched tokens fail. Repeated cancellation is idempotent. Cancellation and success publication are serialized under the state guard. Failed cleanup latches a shared quarantine flag; existing image/video Bridge entrypoints and integrated owners reject further acquisition until positive recovery is separately provided.

Directed verification: request-owner, cancellation and existing Bridge suites 30/30 PASS. Tests prove preparation-time global exclusion, cancellation epoch stability, late rejection, successful next acquisition, and cleanup-failure quarantine across video and image entrypoints. Tests clear the simulated quarantine in teardown only; no production auto-reset exists.

Limitations: internal owner not yet connected to public integrated Comfy/HTTP cancel controls. No active urllib interruption, real release confirmation, external GPU contention proof or four-frame preview added in this increment. Native real checkpoint is still required. No real model, media or external service executed. Global public contracts and Stage denominator unchanged.
