# WP-S2-02 integrated workflow and controls

Status: IN_PROGRESS pending real Comfy validation and Stage checkpoint.

Default video UI/API workflows now call registered LVWVideoPromptOwner directly, so decoder and inference share the request owner and resource slot. The node emits a started event before decoding and a preview event after sampling, both bound to node ID and run token. Four bounded decoded images are converted to inline PNG previews with actual frame time metadata and an explicit sampling limitation. No preview image files are created.

Added Comfy web extension via WEB_DIRECTORY: four-frame gallery, current state/resource polling, scoped cancellation button and acknowledgement, removal of event listeners/timers on node removal. Cancel uses the frozen Comfy-local control protocol and does not call global interrupt. Human draft remains separate.

Verification: API/request/node directed suites 11/11 PASS before the added preview-event test; API/request suites 7/7 PASS after that test. Tests verify workflow registry/port contracts, started-before-preview, matching run token, four actual PNG data URIs, current owner dispatch and rejection paths. JS ES module syntax check PASS. This is not browser layout or real Comfy event validation.

Remaining: real node registration and workflow import, target FFmpeg/model compatibility, actual browser controls/preview, resource timing and privacy/cleanup checkpoint. No real media, service, model, browser or checkpoint was executed in this increment. Fixed acceptance denominator unchanged.
