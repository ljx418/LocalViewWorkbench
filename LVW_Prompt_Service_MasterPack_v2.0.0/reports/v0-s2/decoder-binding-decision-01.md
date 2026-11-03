# V0-S2 decoder binding decision 01

Decision: APPROVED_IMPLEMENTATION_BINDING_ONLY by codex_gate_owner. This is not Stage acceptance or a new external-action authorization.

Evidence: native-decoder-packages-01/receipt.json binds the existing Comfy Python, PyAV 18.0.0 native modules/DLLs and imageio-ffmpeg 0.6.0's Windows FFmpeg 7.1 executable. Seventy-nine files, 156318040 bytes were hashed without importing packages or launching a target process. Package presence does not prove compatibility. Previous native ffprobe discovery failures remain unchanged.

Resolution: retain the existing bounded FFmpeg CLI frame sampler. When no ffprobe executable is available, obtain the same typed container/stream probe document through a short-lived native Python/PyAV metadata-only child. Force the MOV/MP4 demuxer and disable external data references. Do not fabricate ffprobe logs; record the actual backend in result metadata. Keep ffprobe CLI support for existing configurations. Resolve only already-installed imageio-ffmpeg binaries; never invoke a downloader or add dependencies.

Preserved contracts: local MP4/MOV, 256MiB, 60s, 8294400 source pixels, four samples, normalized edge 768, exact reported PTS/timebase, source/frame hashes, one request owner, cancellation and cleanup. Probe remains bounded to 15s/256KiB; each frame child to 30s/3MiB. Public node inputs, PromptSpec/HTTP schemas, error-code enums, Stage cases A02/A07/A09/A10, nine-case cumulative denominator and all quality/resource thresholds remain unchanged.

Isolation: PyAV is imported only by the metadata child using the current native Python with isolated mode and bytecode writes disabled. It does not accumulate or return frames and runs no model; libavformat may inspect packets while discovering stream metadata. The child is owned and reaped through run_bounded; public media cannot select a program, script, protocol or output destination. File-root validation and snapshot ownership precede probing. The existing FFmpeg executable performs actual sampling/frame decoding.

Packet impact: record this internal runtime binding in packet 1.0.1. No new public API or expanded product scope. Native compatibility, public Comfy node execution and complete live checkpoint require fresh child receipts under the existing program. No package-presence evidence or Linux CPU result may replace those checks. No V0-S3 work is activated.
