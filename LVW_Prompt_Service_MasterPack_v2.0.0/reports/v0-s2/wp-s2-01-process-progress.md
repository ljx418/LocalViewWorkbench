# WP-S2-01 bounded process progress

Status: IN_PROGRESS; public decoder/node integration pending. No contract changes.

Added internal video_process.run_bounded: argv without shell, no stdin, combined stdout/stderr byte cap, monotonic timeout, cancellation before spawn and during execution, direct owned-child terminate/kill/wait and pipe draining. Error bodies omit process output and paths. The utility is internal and must only receive trusted decoder argv; it is not an arbitrary command API.

Verification: metadata/file/process suites 23/23 PASS. Process tests execute only local Python synthetic children: exact/one-over combined output, short overflow followed by sleep, nonzero exit, missing executable, pre-cancel, running cancel and timeout with child.poll terminal proof. No FFmpeg, Comfy, Ollama, real media, network or provider used.

Remaining: bind trusted FFmpeg/ffprobe executables and fixed safe arguments; output quotas on actual frame artifacts; decode real PTS; connect snapshot lifetime and Comfy node. Native Windows child/pipe cleanup remains a real checkpoint obligation. Detached child processes are outside this direct-child runner and must not be spawned by its trusted adapters. This work does not establish V0-A10 product timing or resource PASS.
