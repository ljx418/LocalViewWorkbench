# WP-S2-00 offline reuse audit

Scope: repository-only review after R1a human signoff. No media, executable, model or target service probed.

Dependencies: V0-S1 PASS and R1a candidate df4943cef1726350d5e9f1d4111800094c1a8d99 signed by project owner. R1a gate decision and human signature retained under reports/r1a/.

Reuse: LVWVideoFramesPromptBridge and BridgeOwner already validate one-to-four ordered bounded frames, sequential provider calls, raw/parsed split and cleanup; ControlledImageOwner demonstrates root-relative media validation. Existing process-wide inference lock is reusable, but is not a complete cancel/resource terminal owner.

Missing production obligations: local MP4/MOV owner, bounded ffprobe result parsing, CPU FFmpeg sampling with real PTS/time base/hash manifest, public Comfy video UI/API workflow, cancellation feedback and late-result isolation, independently measured resource release. No existing frame-array unit test proves these video-file obligations.

Frozen inherited limits: 256MiB input, 60 seconds, source frame 8294400 pixels, four output frames with longest edge 768; eight-frame profile remains disabled. Stage cases A02/A07/A09/A10 and V0.1 nine-case cumulative denominator unchanged. Resource oracle remains GPU <23552MiB, available RAM >=2048MiB, hot image/video ten runs each and P95 <=180/300 seconds, zero OOM.

Next: implement offline video owner and negative fixtures, then workflow/resource owners. Before real checkpoint, bind actual installed executable identities, fixed samples, ports, per-action budgets and cleanup in a child receipt under AUTH-PROGRAM-V1-LOCAL-01. Those runtime bindings remain pending and are not represented by this repository audit.
