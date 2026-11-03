# Native decoder adapter correction

Scope: WP-S2-01/03/04, existing installed PyAV metadata probe plus FFmpeg CLI frames. Binding decision: decoder-binding-decision-01.md. No dependency download or public contract/denominator change.

Production corrections include an isolated bounded native metadata process, explicit MOV demuxer/external-reference restriction, declared decoder provenance, owned-client preview events and inactive-workflow event rejection. Native component Harness admits one public decoder submission, zero provider calls, no browser and no Stage acceptance claim.

Resource admission now checks host RAM before CPU preparation and GPU/RAM after tensor allocation, before inference. Invalid media must invoke no GPU telemetry or provider. Cancellation during allocation must stop before model admission. Both paths release the shared slot.

Directed verification: the combined 34-test run had one error in the newly added invalid-media fixture (missing required BridgeError subcode), while the production video-controls VM test passed. Corrected the fixture without removing its no-GPU/no-provider/released assertions. The affected request/resource suites then passed 13/13 (0.121 seconds). The next sealed offline checkpoint will rerun the full subtree and all five checks against the new candidate; historical baseline evidence does not certify these changed bytes.

Native compatibility, video UI raw/adoption/manual export, full performance denominator, Stage independent review and human signoff remain incomplete. No services, media decoding, browser or provider were run for this correction note.
