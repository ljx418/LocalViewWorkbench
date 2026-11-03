# WP-S2-03 positive release confirmation

Status: IN_PROGRESS; no real resource or product PASS.

InterruptibleOllamaTransport cleanup now issues its own model unload, requires done=true, then polls fixed loopback /api/ps until the models list is positively empty within the bounded cleanup window. Cancel does not cancel cleanup. Missing/malformed/occupied inventory or deadline exhaustion yields RESOURCE_RELEASE_PENDING; integrated owner retains unknown state and quarantines the shared slot. Other loaded models are observed but never unloaded or killed. Last release evidence records checks, zero loaded models and elapsed time only after positive confirmation.

Control requests use direct http.client with no proxy or redirect handling, fixed internal paths, bounded response bytes and monotonic read deadline. No arbitrary URL is accepted.

Directed verification: transport/request/cancel/Bridge suites 37/37 PASS. Added tests for delayed empty inventory, cancellation-independent cleanup, invalid unload acknowledgement, malformed inventory, persistent other-model occupancy without extra unload, and redirect rejection. Network/control results are injected; no real Ollama, GPU, media, network or checkpoint run. Real model-stop and GPU/RAM timing, native platform behavior and public cancel entry remain pending.
