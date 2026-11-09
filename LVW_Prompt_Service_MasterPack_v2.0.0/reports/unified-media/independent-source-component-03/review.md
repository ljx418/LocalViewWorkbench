# Independent source-frame component03 review

Decision: **COMPONENT_SEMANTIC_FAIL**, Fatal0/Major1/Minor0. Completed final output is factually wrong about the sampled background/foreground relationship. This is an independent review of component source-frames-probe-03 at sealed03bec355cceec06f3cace4d69bde5a8844dd1c51, not a public/UI/full-slice checkpoint. Live14 remains unchanged:7 PASS/1 FAIL/2 BLOCKED of10, NO_GO. No actual Stage or human signature, full R1 or V1 acceptance is asserted.

## Major S1 — source-visible geometry is described as perfectly still

This review independently recomputed direct pixel evidence from the four retained exact PPMs, without decoding video or adopting a previous semantic verdict. Red foreground bbox is [322,156,445,301] inclusive in all four768x461 frames. In a top background strip, white vertical line centers start88.5,69.5,49.5,30.5px at1,3,5,7s, with96px periods. Thus the grid changes position left by19/20/19px between samples while the foreground stays at fixed image coordinates. The subject/grid spatial relationship changes. This fact does not require identifying physical camera motion or direction.

Actual observation4 says the red rectangle's position relative to the grid is constant; observation5 says their spatial arrangement is static. Both are false. Inference1 invents likely noise/compression instead of acknowledging geometric displacement. Inference2 calls the sequence static or camera stable without supporting evidence. Unknown1 even declares that the measured offset does not correspond to visible object motion, an unsupported certainty inside an uncertainty field. Both Chinese and English prompts describe the entire composition as perfectly still. English says no visible camera/subject motion; Chinese goes further, declaring no camera motion or object displacement. Negative suppresses camera motion/panning/zooming/object movement/flicker, and tags include static/no motion. camera_motion=none asserts a physical answer unavailable from the samples. subject_action=static is supportable only as foreground image-coordinate placement, not as a conclusion about the whole scene.

The rest of final content was checked: observations1–3 accurately state sample times, blue/white grid, centered red rectangle; observation6 correctly repeats measured3px component registration but omits its reduced128x77 analysis scale. Numeric differences(~34%,~20RGB delta) match retained pixels, but those numbers do not support an invented noise cause. Digital/graphic/high-contrast styling and colour/object tags agree with the scene. Physical graphic origin unknown is appropriate. Parsed fields repeat the factual errors; automatically added sparse-frame warning correctly states unsampled events/continuous motion/audio are unverified, but does not repair contrary fields. This single major finding covers the correlated false stability and unsupported explanation across output fields.

## Request and provenance verification

All authorization frozen files were retrieved from this probe's sealed Git commit into a separate snapshot and independently rehashed with no mismatch. Harness, original four PPM samples, parent approval/request and all executable bindings match. The installed native model receipt is gemma4:26b,25.8B Q4_K_M,17987581215bytes,digest5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251, matching child identity. Model/tag alone is not treated as a new weight-file audit.

Using only sealed source definitions, this review reconstructed four payload PNGs, each768x461, with RGB bytes identical to corresponding retained source PPMs, in1/3/5/7s attachment order. All four logged payload-image hashes match exactly; no resizing, source-panel crop or source duplication occurred in the prepared payload. Full request payload hash48a98bcdcedebe07f135f63f1e10ed51741f702600afbea242e80330f0a4d2ce, source-template hashe8b8471d810dcb79da1546d83ec116f2c8294af0e6b5d59838fe9f6769932569, concatenated image input hash and all numeric metadata reproduce exactly. Source protocol is source-frames/1, thinking=false,num_ctx4096,num_predict768,temperature0.2,keep_alive0. All four exact payload image hashes are recorded in payload-recomputed.json.

This verifies construction and the provider's retained outbound request identity. It does not independently instrument Ollama's native vision encoder, confirm which of four attachments the model attended to, or establish multi-image capability from the model's words. A separate synthetic distinct-frame visibility diagnostic may address that capability question, but cannot replace semantic quality on this fixed video sample.

## Raw response and privacy

The complete raw_response is retained because message.thinking is absent. Its SHA256 independently recomputes to ff49f6e3e23db74670fb92656403cd4b5c5ef16b051308e58f716a7cad310bfd, matching receipt and provider_response_received event. Parsed envelope.message.content equals retained final_content exactly. Its SHA256 independently recomputes to a8566f92c04577cfedde739c4d2bc852b666e4f9d0c173e0245dd081d5bbb3b7. The envelope completes with stop/eval523/prompt_eval2428. No hidden/internal reasoning content is present or saved by this review. Unlike a withheld whole-body record, both retained wire-text and final-text hashes and their extraction relationship are directly reproducible here. Hashes verify retained UTF-8 response text, not a packet capture/TLS transcript.

## Finite budget, guards, resource release and exact cleanup

SQLite was opened mode=ro. Child row has cap1,calls1,full0,checkpoint0,active0,elapsed27s; starts bind Ollama1,API0,browser0,Comfy0. Ledger child/execution-binding hashes match actual files. One provider_call_started, one completed, one lease_released, and one native /api/chat log entry agree; event timestamps fit600s child window. Declared sample-read cap16 is consistent with four reads in the sealed harness; observed metadata requests10 are below200 and recorded telemetry is below450. Source guard debits the bound child before chat send with LVW_REQUIRE_BUDGET=1 and exact child environment. Resource monitor thresholds remain23552MiB GPU and2048MiB RAM; observed peak21946MiB/minRAM9641MiB. Declared caps without independent counters are not represented as measured counters.

Release has three inventory_empty=true samples, GPU3485/3484/3484MiB and RAM9760/9772/9761MiB. Native owner nonce485818fa52c8444e9ffd09e2959b201f/PID41592/birth639298307210016998 matches retained terminal owner, exited/listener_owned=false. Sealed native controller holds original child handle, uses nonce stop ownership and waits for exit. Native log confirms loopback/no-cloud setting. No new Windows process query or termination was performed; native physical exit is assessed from retained ownership/controller/terminal evidence.

Authorization owned_temp_root and receipt run_root bind exactly `/mnt/c/workspace/videoworkline/.lvw-runtime/lvw-prompt-service/thinking-866f0ad2d4174ac19bb6ac0cc52588b0`. Source atomically claims it with mkdir(exist_ok=False), marks temp_claimed only on success, limits archive/delete to that claimed root, then asserts absence before settlement. Receipt run_root_claimed=true/run_root_removed=true agree. This review independently checked that exact original path is absent. The path binding is protected by matching immutable child hash in SQLite. This closes the previous component-specific inability to recheck an unrecorded randomized root, without retroactively altering any older evidence.

## Reproduction and limits

Run `PYTHONDONTWRITEBYTECODE=1 python3 -B reports/unified-media/independent-source-component-03/recompute.py` and then `PYTHONDONTWRITEBYTECODE=1 python3 -B reports/unified-media/independent-source-component-03/payload_cpu.py`. Both read retained PPMs/sealed Git/SQLite read-only and write only this review directory. Snapshot provider definitions are imported without application startup; no inference/client method is invoked. These CPU computations verify bytes/math and do not count as model quality passes.

No new model/GPU/service/browser/network/download/media probe/video decode or ledger mutation occurred. No public UI/cancel/adopt/export/offline full workflow is exercised by this private call. Current conclusion is limited to this model/config/input/request's actual retained final output; it is not proof that all models/configurations fail, and successful transport is not semantic acceptance.

## Exact final content

```json
{
  "observations": [
    "The video sequence consists of four frames at timestamps 1s, 3s, 5s, and 7s.",
    "Each frame features a dark blue background with a white grid pattern.",
    "A solid red rectangle is positioned in the center of each frame.",
    "Across all frames, the red rectangle's position relative to the grid remains visually constant.",
    "The grid lines and the red rectangle appear static in their spatial arrangement across the sequence.",
    "Image registration analysis shows small pixel offsets (3px) in certain color components between consecutive frames."
  ],
  "inferences": [
    "The high percentage of different pixels (~34%) and mean absolute RGB delta (~20) are likely due to sensor noise or compression artifacts rather than physical movement, as the structural elements (grid and red rectangle) show no semantic displacement.",
    "The sequence represents a static digital graphic or a highly stable camera shot of a static pattern."
  ],
  "unknowns": [
    "The cause of the measured 3-pixel offset in grayscale and specific color channels is unknown, but it does not correspond to visible object motion.",
    "The physical origin of the graphic (digital render vs. filmed screen) is unknown."
  ],
  "prompt_zh": "一段静态的数字图形视频，画面由深蓝色背景、白色网格线和一个位于中心位置的红色矩形组成。画面结构在整个序列中保持完全静止，没有任何相机运动或物体位移。色彩饱和度高，呈现出清晰的数字矢量风格，具有极高的对比度和均匀的光照。",
  "prompt": "A static digital graphic video sequence featuring a dark blue background with a white grid pattern and a solid red rectangle centered in the frame. The composition remains perfectly still throughout the sequence, with no visible camera motion or subject movement. High color saturation, clean digital vector style, high contrast, uniform lighting, and sharp edges.",
  "negative": "camera motion, panning, zooming, object movement, flickering, blurry edges, organic textures, depth of field, shaky footage",
  "tags": [
    "static",
    "digital graphic",
    "grid pattern",
    "red rectangle",
    "blue background",
    "no motion"
  ],
  "camera_motion": "none",
  "subject_action": "static"
}
```
