# Independent live-13 review — NO_GO

Candidate `9d9cdad0d3ef45a6dd821984272b0cbaa351bb76`, frozen R1 packet 1.0.3, fixed UM-01 through UM-10: **9/10 PASS, Fatal 0 / Major 1 / Minor 0**. This is a slice review. Neither Stage PASS, human acceptance nor full V1 acceptance is granted.

Fresh isolated reviewer `/root/live13_independent_review` read the raw image/video responses, actual schema and prompt, browser harness, screenshot, public exports, cancellation terminals and native logs. Prior implementation and input-review conclusions were not acceptance oracles. All writes are confined to this review directory. No new model, GPU, service, browser, network request, download or video decode was performed; global accounting was opened with SQLite `mode=ro`.

## M13-01 — Major — UM-04 temporal content is incorrect and incomplete

**Location:** `reports/unified-media/live-13/video-model-run.json`: raw response observation 5, inference 2, Chinese and English reconstruction prompts, and parsed equivalents. It propagates into `video-adopted.json`, `after-cancel.json` and the exported video prompt.

**Trigger:** analyze the granted `tracking.mov` sample, source SHA `b08ea8b0b9fa3bcd4e62b2b0ad1c05b2bff09359539933f4581a5c2f2c69ff6d`, at actual source PTS 12288/36864/61440/86016 with time base 1/12288 (1/3/5/7 seconds).

**Expected:** compare all sampled frames, distinguish the nearly fixed red subject from the changing background grid, preserve supported temporal differences in reconstruction prompts and separate facts from unknown physical causes. Physical camera direction is not required. Nonempty JSON, any offset, or `camera_motion=unknown` alone cannot satisfy this obligation.

**Actual:** the raw response asserts that the rectangle's position **relative to the grid** appears consistent across all timestamps. The Chinese and English prompts describe a stable centered rectangle and a static graphic, omitting the background's supported spatial change. The inference speculates about sub-pixel alignment or specific colour shifts. That is not a grounded account of the clearly changing grid/subject relation. Listing sensor/compression/motion as unknown causes does not repair the false observation or omitted reconstruction content. Several observations also describe F/D panel metadata despite the instruction to report the scene.

**Independent evidence:** all four retained PNGs were converted back into canonical P6 PPM bytes; every SHA exactly matches live-13 frame references. Direct source-pixel measurement at row 50 finds the first vertical white grid center at **88.5 → 69.0 → 50.0 → 30.5** source pixels; all successive grid lines follow the same shifts. The red mask bounding boxes remain **[322,156,445,301]** for F1–F3 and **[323,156,445,301]** for F4, with x-centroids about 383.5. Thus the sampled grid changes position relative to the nearly fixed red rectangle. This conclusion uses direct landmarks and visual reading of all four source panels, not registration alone. No claim about actual camera mechanics or unsampled continuous motion is necessary.

Independent NumPy bounded registration exactly reproduced all three live luma/colour results: R-G offset (0,0), G-B and B-R (3,0) at analysis size 128×77, with G-B error reductions 62.1621%, 63.0930%, 63.6593%. Changed source pixels are 34.3871%, 34.1304%, 33.3726%. These computations validate the input measurements; they do not validate the model's semantic answer. The rebuilt actual contact sheet SHA is `323dc68033e330fae9e217cd26160ba5473fe3dc463a1a1a0d170aa617131843`, exactly the live provider input hash. Inspect `rebuilt-sheet.png`, `recomputed.json` and `recompute.py`.

## Remaining fixed coverage

UM-01: PASS. The actual image is a red square centered on blue; raw image output matches it. Browser assertions, image export and before-video-adopt export show manual text protection and explicit adoption provenance.

UM-02: PASS. Real public duration and corrupt rejections occur before model startup in launcher history, with retained structured errors. Reviewed candidate regression cases cover bytes, duration, pixels, container, empty/malformed metadata and streamed body limits. Parent CPU log's 136 checks are supporting branch evidence, not real semantic acceptance. No media probe was rerun here.

UM-03: PASS. All four canonical frame hashes match exactly; PTS and source SHA join the actual input. Short-frame count/limitations are covered by candidate tests and actual four-sample warning. This reviewer does not infer unobserved continuous events or audio.

UM-04: FAIL. M13-01. One real successful joint request carries four source hashes and the exact rebuilt sheet, but semantic obligation fails.

UM-05: PASS. Real public cancelled job `job_2f6ce7881d6f469f823c8f32394a07e7` ends cancelled/released with null result and cancel_epoch 1. The original adopted run and manual edit survive. Raw provider lease evidence confirms release. Reviewed queued/preparing and late-success regression barriers supplement real running cancel; these controlled error branches do not claim additional real inference outcomes.

UM-06: PASS. Before-video-adopt retains image run identity; video-adopted uses video run `run_7208344170784e1e8eb2795c16e44901`; after-cancel preserves that source and `AFTER_ADOPT_MANUAL_KEEP`. Actual harness accepts the dirty-draft confirmation explicitly. TXT/JSON exports are retained.

UM-07: PASS. Native service is actually stopped (`reachable=false`); retained offline export changes video prompt to `OFFLINE_EDIT_AND_EXPORT`, and TXT contains it. Public UI screenshot shows cancel error and editable manual draft. Candidate controlled failures supplement this real offline sequence.

UM-08: PASS. Exactly three provider starts and three releases; GPU peak 21123 MiB, minimum available RAM 7766 MiB. Release samples show empty model inventory and return to approximately 2.9 GiB GPU usage. Native actual log witnesses loopback host, `OLLAMA_NO_CLOUD:true` and cloud disabled. Browser has no external requests; endpoint code requires literal loopback. No cloud packet capture is claimed.

UM-09: PASS. Actual Windows command launched the built React/default FastAPI app; launcher history serves the bound JS/CSS, real browser errors are empty, screenshot and exports join the same sequence. Comfy starts = 0 in child accounting. This is a headless browser slice check, not human experience signoff.

UM-10: PASS for identity/authorization/cleanup and this independent review completion. Candidate HEAD and frozen/source/sample/harness/tool bindings all matched at review capture. Recomputed source build ID `d671363cb358fa18eab4d7cd95872f77f497f0067e4abbfcf81e384e6dbf00f7` matches the live health/receipt. Candidate provider SHA is `15cbb5cccafbe35ab74bcf99b6fe9c5bc10d7a2dbd392cd5e7d1709033b4f94a`. Actual installed model is gemma4:26b, digest `5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251`, GGUF Q4_K_M 25.8B; native logs show its vision renderer. Per-model-run digest fields are null; identity is established by the same-run installed-model inventory plus native tag/vision load evidence, not invented from the null field.

Native owner nonce `ae439a155c5547e3b0f3b90654354f70`, PID 26800, birth ticks 639298266851106044 has terminal exited/listener_owned=false, matching the stop nonce. Inspected native supervisor retains the original process handle and waits for exit. API PID 3530826 birth 10627350 has actual launcher shutdown and is absent under /proc. Runtime unreachable, launcher exit, browser_closed, all jobs terminal, and removal receipt agree. Independent directory listing finds only the empty enclosing `native-temp` directory; its actual per-launch run child and media/database/provider files are absent. The parent state container itself is not the removed per-launch data root.

Read-only global ledger has live-13 calls=3, checkpoint=1, elapsed=64, active=0, exact authorization/bindings hashes. Snapshot global totals: 18 model actions, 6 checkpoints, 1227 seconds, zero active children, within 1024/24/48h program limits. These are a snapshot, not permission to reset budgets.

## Reproduction and limits

From the package root at the reviewed candidate, run `python3 -B reports/unified-media/independent-live-13/recompute.py`. It reads existing retained images and hashes, reconstructs the sheet using only the inspected pure AST function, and computes alignment independently with NumPy. Independent static and known-shift negative checks both pass. It never imports the service or decodes a video. Results and all live-13 raw file hashes are in `recomputed.json`; the receipt hashes review artifacts. If implementation advances, use frozen candidate bytes: subsequent changes are outside this verdict. Original live-13 raw history was not rewritten.

This review does not certify the complete old S2 nine-item, S3 twelve-item, or V1 twenty-one-item denominators. Human signoff remains null. The blocker is actual temporal semantic fidelity, not a requirement to guess physical camera direction.
