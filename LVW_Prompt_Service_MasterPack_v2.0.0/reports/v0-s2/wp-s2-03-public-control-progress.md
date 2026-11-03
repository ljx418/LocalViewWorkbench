# WP-S2-03 Comfy-local control integration

Status: IN_PROGRESS. Added registered LVWVideoPromptOwner using the integrated VideoRequestOwner and default trusted decoder/interruptible transport. Every execution gets a fresh run token; Comfy model cache is disabled for this node. Existing separate frame nodes remain available but do not claim integrated request-lifecycle coverage.

Comfy-local control protocol: GET /lvw/v0/video/status returns current token/status/resource state; POST /lvw/v0/video/cancel accepts only a JSON object with run_token (1..128 chars), body <=4096 bytes. Both require literal loopback peer/Host and X-LVW-Control: local-ui. Mutation requires matching HTTP Origin; read-only status also accepts browser Sec-Fetch-Site: same-origin when Origin is absent. Error codes use existing ORIGIN_FORBIDDEN/ATTEMPT_STALE/CONTRACT_UNSUPPORTED. No arbitrary path, executable, PID, model action or global Comfy interrupt is exposed. This is a V0 host extension protocol, not a new V1 business API.

Routes register only when an existing Comfy PromptServer instance is importable; offline imports never start a server. Default decoder executable lookup remains trusted environment/PATH configuration.

Verification: API/request/cancel/existing Bridge suites 33/33 PASS. Production route functions tested through an injected Comfy route registry and response adapter: actual current-owner status/cancel dispatch, cross-origin rejection, oversized/extra-field rejection and stale token protection. Registered integrated node test confirms fresh tokens and request-owner invocation. No server, real HTTP, model, GPU or checkpoint executed.

Remaining: wire the default video UI/API workflow to the integrated node; add user-visible cancel control and four-frame previews; validate actual Comfy/aiohttp registration, response timing and full native run. Global OpenAPI/Schema/error codes and fixed denominator unchanged. No Stage PASS.
