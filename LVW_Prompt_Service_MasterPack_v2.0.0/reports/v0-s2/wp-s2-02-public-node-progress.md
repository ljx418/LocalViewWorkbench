# WP-S2-02 public video node progress

Status: IN_PROGRESS, no Stage acceptance. Added LVWControlledVideoInput to actual Python node registration and supplied draft video_reverse_prompt_v0 UI/API workflows wired to LVWVideoFramesPromptBridge. Registry coverage updated for the additional controlled input owner; existing bridge assertions retained.

The adapter resolves trusted Comfy input/temp directories and installed decoder executable configuration, invokes VideoDecoder, converts bounded PPM images into CPU NHWC float tensors, and emits source hash/size, duration, four PTS frame references and sampling limitations into node UI/history metadata. Media input cannot set executable paths or command arguments.

Verification: public node plus existing Bridge directed suites 29/29 PASS. Real local numpy/Pillow/torch CPU tensor conversion checked. Public input-to-public Bridge composition with injected decoder/provider proves four ordered calls, four cleanup calls, four raw responses and structured observations. UI/API files reference registered owners and consistent ports; file-path failure does not invoke tensor builder. No real media, FFmpeg, Comfy server, GPU model or external network used.

Pending: target Comfy registration/import/run validation and actual installed decoder discovery; visible four-frame previews; request-wide lock spanning preparation and inference; cancellation/late-result and release integration. Workflow files are implementation candidates, not verified target-runtime workflows. Global Schema/error codes and fixed denominator unchanged. V0-A02/A07/A09/A10 remain unaccepted.
