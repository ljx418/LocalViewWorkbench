# WP-S2-02 controlled video upload progress

Implements the existing frozen V0-R02/A02/A07 local video-input obligation inside the Comfy extension. POST /lvw/v0/video/upload is an internal native-UI adapter; the V1 OpenAPI, schemas, fixed denominator, quality thresholds and ownership are unchanged. It does not claim container validity or model success.

Production path: native node file input -> same-origin scoped POST -> 256KiB stream reads -> receive_video -> exclusive owned .part file -> atomic no-overwrite opaque reference in Comfy input -> existing VideoRequestOwner -> snapshot/ffprobe/FFmpeg validation before provider calls. The original local filename is never used as a server path. Complete uploads remain as Comfy input media; partial uploads are removed on failure/cancellation. Live test isolation must delete its entire run-owned input root at terminal.

The form accepts MP4/MOV, <=256MiB, and states the 60s analysis limit. Server independently enforces bytes, format extension, an upload deadline and origin/peer/header restrictions. Empty, one-over, interrupted, redirected-root and collision cases leave no new input. A destination collision cannot overwrite or delete an existing file. Selecting a new upload does not replace the reference until success. In-flight analysis disables upload selection; node removal aborts upload and removes control listeners.

Directed Python command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest LVW_V0_RuntimePatch.tests.test_s2_video_upload LVW_V0_RuntimePatch.tests.test_s2_video_api LVW_V0_RuntimePatch.tests.test_s2_bindings -q. Exit 0; 18 tests. The API handler test drives production receive_video with chunked content and checks rejection before the stream is read.

Production JS module syntax check: exit 0. node --experimental-vm-modules tools/v0_s2_video_controls_test.cjs: exit 0; exercises unchanged production module with explicit Comfy/DOM substitutes for upload binding, failure preservation, one-over rejection, active-run lock and listener cleanup. This is not a real-browser result.

Environment evidence: inventory04 confirms no pair in the ten named Comfy locations. Inventory05 stopped at its all-media count cap before standalone-tool discovery. Inventory06 predeclared one image plus one video, saved their hashes, then returned NATIVE_DECODER_INSTALLATION_NOT_FOUND for the declared native search scope. Each child expired at terminal, with zero services/provider calls/Stage checkpoints. Historical S0 FFmpeg 6.1.1 calls used WSL executables; they do not prove Windows-native availability. No further broad disk search or download is scheduled; an existing native decoder location has been requested asynchronously.

Pending: native decoder binding and public Comfy/browser compatibility; complete candidate-bound checkpoint driver; actual fixed 10+10 performance/cancellation/failure evidence; independent review. No Stage PASS claim.
