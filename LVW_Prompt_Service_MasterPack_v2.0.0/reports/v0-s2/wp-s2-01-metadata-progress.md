# WP-S2-01 metadata and time boundary progress

Status: IN_PROGRESS, not a completed Workpack or product acceptance.

Implemented video_input.py: strict MP4/MOV probe shape, 256MiB/60s/source pixel limits, one selected non-cover video stream, exact rational time base and origin, four temporal window midpoint seek targets, decoder-PTS frame manifest and normalized frame hashes. Tags are ignored. Duplicate/nonmonotonic or out-of-range PTS fail explicitly; seek targets are never presented as decoded timestamps.

Directed verification: Python unittest test_s2_video_input, 8/8 PASS; git diff --check PASS. Includes exact/one-over, malformed/rational/nonfinite values, VFR PTS, duplicate/count bounds and metadata injection. No external execution, real media or provider call.

Remaining before WP-S2-01 completion: safe root-relative file owner including Windows reparse handling, bounded ffprobe/FFmpeg process/output/temporary quota, cancellation integration and actual decoder output binding. Module is not yet connected to the public Comfy entry. No V0-A02/A07/A09/A10 PASS is claimed.

Contract changes: none. Stage denominator and resource thresholds unchanged.
