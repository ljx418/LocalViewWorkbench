# WP-S2-01 decoder composition progress

Status: IN_PROGRESS. Contracts and fixed denominator unchanged.

VideoDecoder now composes stage_video, bounded ffprobe JSON, validate_probe, four fixed CPU FFmpeg calls, bounded RGB PPM parsing, showinfo time-base/PTS checks and frame_manifest. Seek windows use exact rational source ticks; manifest only records timestamps from decoder logs. Each invocation captures at most 3MiB and returns one frame at longest edge <=768. Total output is four frames; pipe output avoids disk frame accumulation. Snapshot lifetime encloses probe and all decodes and is cleaned on failure or return.

Verification: 28/28 directed tests across video input, files, subprocess and decoder. Adapter tests inject process results, exercise production composition, verify original path is not passed, reject over-limit probe before decoding, reject incorrect/missing time-base evidence and invalid PPM, and prove snapshot cleanup on decoder failure. No FFmpeg executable, real media or model was run.

Pending: actual FFmpeg version/command compatibility, native Windows subprocess/NTFS behavior, real VFR/short/corrupt videos and target resource measurements. Current implementation uses four bounded decodes rather than a full-resolution frame batch; actual CPU/runtime performance remains to be measured against frozen thresholds. Public Comfy node/tensor adapter, workflow, request-wide cancellation and resource lock integration remain unfinished.

This is offline implementation evidence, not V0-A02/A07/A09/A10 PASS. Next responsibility: implement public Comfy video owner/workflow and directed tests, then bind a program-scoped runtime sub-authorization before any target execution.
