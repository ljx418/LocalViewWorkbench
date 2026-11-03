# WP-S2-03 cancellation propagation progress

Status: IN_PROGRESS. Frozen node input contract and Stage denominator unchanged.

BridgeOwner.analyze_video accepts an internal cancellation event, propagated by the registered LVWVideoFramesPromptBridge instance. Checks occur before starting every frame and after a started frame and cleanup return. Cancellation discards late success rather than compiling a suggestion, preserves prior raw responses, prevents subsequent frame calls, and retains the existing inference lock while a call is still active.

Directed verification: cancellation and existing Bridge suites 27/27 PASS. Pre-cancel causes zero provider/cleanup actions. Cancellation during a successful fake call causes one call and cleanup, returns JOB_CANCELLED with raw evidence and no suggestion. A blocked-call concurrency test confirms that another public bridge request gets RESOURCE_BUSY and zero provider calls until the original call stops/cleans. Next request can acquire the released slot.

Limitations: current synchronous urllib transport is not actively interrupted by the event. This change does not establish actual model stop latency, public cancel endpoint/UI, cancellation epoch ownership, request-wide lock spanning decoder and inference, or cleanup failure quarantine. Those remain required before A10 PASS. No real HTTP, GPU, model, media, Comfy server or checkpoint was run.
