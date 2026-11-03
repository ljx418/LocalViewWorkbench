# WP-S2-03 interruptible transport progress

Status: IN_PROGRESS; fixed contracts and acceptance denominator unchanged.

Integrated VideoRequestOwner now defaults to InterruptibleOllamaTransport and binds its per-run cancel event. Cancellation signals the event and shuts down a duplicated socket handle belonging to this request; no process-global interrupt or non-owned connection is used. A cancelled connection is not auto-reconnected for chat. Post-connect checks cover cancellation during connect. Reads have a monotonic deadline and a 4MiB cap, and response/connection handles are closed on terminal paths.

Verification: transport, request owner, cancel and existing Bridge suites 33/33 PASS. Offline connection/socket doubles exercise pre-cancel with zero sends, blocked read interruption, unrelated socket preservation, sanitized error, successful response and non-200 failure. No TCP connection, real model or checkpoint executed.

Limitations: these doubles do not prove native socket shutdown behavior or Ollama actually stopping model inference. Existing cleanup still issues unload through base transport; positive /api/ps and GPU release evidence, public integrated node/cancel route, preview and native Windows behavior remain mandatory before Stage PASS. Interrupting a client connection alone is not resource-release proof.
