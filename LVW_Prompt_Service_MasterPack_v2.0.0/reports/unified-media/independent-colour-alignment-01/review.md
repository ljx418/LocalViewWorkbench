# Independent colour registration review

Decision: **CPU_CORRECTION_VERIFIED_REAL_SEMANTICS_NOT_RUN**. Fatal 0 / Major 0 / Minor 0 for the reviewed correction. This is not UM-04, UM10/10, R1 or V1 acceptance. The previous real live12 result remains independently **NO_GO, 9/10**, with its UM-04 Major unchanged. A fresh bound real checkpoint is still required.

Reviewer: isolated `/root/colour_alignment_review`, assigned under AGENTS.md rule 11. The reviewer read the frozen R1 1.0.3 packet, scope, acceptance matrix, actual uncommitted provider/test diff and request/response path directly. Review did not inherit the implementer's conclusions. Only this evidence directory was written. No candidate, tests, contracts, controls or budget ledger were changed.

## Source binding and frozen scope

`source-fence.json` records git HEAD `52736c9aabc769d49bbb9662f878d705c32e5ed2`, source/contract/packet hashes and successful verification of all nine packet-manifest entries. The correction is uncommitted relative to that HEAD. Exact reviewed source copies are under `source-snapshot/`, with the actual diff in `reviewed.diff`.

- provider.py SHA256: `15cbb5cccafbe35ab74bcf99b6fe9c5bc10d7a2dbd392cd5e7d1709033b4f94a`
- test_provider.py SHA256: `70d200cd04f822d33331139c66f07b1996eb1781f78691f916c2435703cd7a76`
- packet manifest SHA256: `c20246bd153136c91ce27f7e125716c8c0b3848ffa58e7fe9857ce5f2e343502`

Initial, post-oracle and final source hashes agree. Findings apply to these hashes; another candidate needs a new binding.

The actual change adds three generic scalar colour-component searches alongside the retained luminance search, revises model guidance, and increments presentation/template identity. It does not branch on filenames, fixture hashes, timestamps, colours or known sample offsets. Colour names denote algebraic channels, not semantic object labels. Registration changes input evidence; it does not calculate or inject camera/subject classifications. The source preserves the HTTP response text before parsing and returns it untouched. The new prompt asks the model to separate observed spatial change from uncertain physical cause.

No diff exists in `contracts/`, frozen R1 packet, acceptance cases or release gates. VIDEO_SCHEMA is unchanged in the reviewed diff. No public API/schema, fixed denominator (UM10/10), hard limit, GPU/resource threshold or budget behavior was changed. The new internal metadata and version hashes are presentation changes within the frozen sampled-video analysis scope.

## Reproducible CPU evidence

Run from repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lvw/backend python3 reports/unified-media/independent-colour-alignment-01/review_cpu.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=lvw/backend python3 -m pytest lvw/tests/test_provider.py -q -p no:cacheprovider --basetemp=reports/unified-media/independent-colour-alignment-01/pytest-temp
```

`review_cpu.py` is independently authored; its oracle uses signed integer/channel lists and exhaustive sums, not the production helper, Pillow crop/difference or ImageStat. It compares all emitted component result fields against independent search results. `cpu-evidence.json` retains every assertion, expected/actual scalar results and sanitized request payload. `cpu-run.log` and `pytest.log` retain raw execution output.

Results: **75/75 independent assertions; 23/23 current provider regressions pass**. Nonblocking Pillow getdata deprecation warnings are retained; they do not change results.

Coverage includes all 65,536 ordered 8-bit channel pairs for the exact Pillow `(first-second)/2+128` quantization, including negative odd differences; static texture; positive/negative/horizontal/vertical/radius-edge translation; fixed-area bounded search and tie ordering; equal-luminance chromatic motion with unusable luma; moving grey texture plus stationary chromatic region with different informative component offsets; untextured and narrow components; periodic aliases with explicit tie counts; differing dimensions; one frame; immutable source bytes. A border-only change is intentionally missed by central-window registration but detected by full-frame pixel counts. A shift outside the search radius is compared to the constrained oracle without claiming recovery of the true shift.

The integration check sends exactly one serialized `httpx.Request` through **in-process MockTransport** and checks its actual JSON body: one contact-sheet image, recomputed colour metadata, unchanged VIDEO_SCHEMA, source immutability, exact returned HTTP response text, and unchanged model camera/subject strings. This is an HTTP client serialization/path check with no socket, service or model; it is not a genuine server/model HTTP invocation.

## Findings and limitations

No Fatal/Major/Minor correction defect found within this scope. The arithmetic and bounded search results agree with independent integer/list computation. Tie counts disclose alias ambiguity and the prompt does not equate offsets with physical camera motion.

The CPU images are synthetic and no retained real image was needed. No model/GPU/service/browser, media probe/new video decode, network, dependency download or budget write occurred. No new real result is implied. This review does not demonstrate that the model understands the additional evidence or that prompt wording fixes live12's semantic contradiction.

The exhaustive oracle images are at most 48x40, avoiding thumbnail resampling. Larger-source Lanczos behavior is source-inspected and remains a limitation of independent numerical coverage. Registration ignores excluded borders, is limited to ±radius (maximum 10) at at-most-128-pixel analysis size, and is translation-only. Thumbnail filtering/quantization can suppress information; low texture, ties, repeated patterns, local movement, lighting, cuts or dominant regions can make an offset ambiguous or misleading. Opponent channels are correlated scalar pixel projections; distinct components do not prove semantic region identity. These are explicitly evidence limitations, not softened acceptance criteria.

Next owner: gate owner / authorized executor. Bind the frozen candidate to a fresh real checkpoint and independent semantic review; preserve live12 NO_GO history. Human signing remains separate.
