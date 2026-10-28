# WP-S1-04 Independent Review

Review role: `codex_isolated_reviewer`

Review mode: frozen Git objects and offline tests only. No ComfyUI, Ollama, GPU, port, network, real-media, or live-probe action was invoked.

Frozen inputs:

- checkpoint seal: `a14ced9edccbc9d6ff0568d0e0b5c29af66747e1`
- execution candidate: `919f7fc47150bf164d8d90898fcc4dd69943568e`
- raw evidence: `c2c0bd6a17ef504463d8caa68651a0ea83f50293`
- harness SHA-256: `27a50fa125eada342e99ddaa135f25ae3ea14857d86ce3aff44448886f9e27ab`
- live run: `reports/v0-s1/wp-s1-03-live-05/`

## Outcome

**Fatal 0 / Major 3 / Minor 1**

Recommendation: **NO_GO**.

The run has credible evidence that a loopback public Comfy route executed and produced a structurally valid PromptSpec, but the evidence cannot bind the executed production owner/workflow bytes to the frozen candidate and cannot independently reconstruct two required state/integrity proofs. These are Major false-green risks under the frozen packet. The one-shot authorization is terminal and expired; this report does not authorize or recommend reusing it.

This is not a Stage PASS. `V0-A01`, `V0-A03`, `V0-A04`, `V0-A05`, and `V0-A08` remain `NOT_RUN`.

## Findings

### M-01 — Major — Executed product owner and workflow bytes are not bound to the execution candidate

- **Location:** `reports/v0-s1/wp-s1-03-phase-a/live_probe.py`, `candidate_identity()` and `execute()`; `run-summary.json#evidence.identity`.
- **Trigger:** Recompute which local bytes are identity-checked, then compare them with which local bytes are copied/read for the live public route.
- **Expected:** Before any service start, every executable production artifact used by the run—at minimum the six `custom_nodes/lvw_v0_bridge/*.py` files and `image_reverse_prompt_v0.api.json`—must match blobs at candidate `919f7fc...`. A clean/dirty assertion alone would not replace file/blob hashes.
- **Actual:** `candidate_identity()` hashes only `git diff 64ec38c..919f7fc`, which contains exactly two files: the harness and its test. The live run then copies the entire local `custom_nodes/lvw_v0_bridge` subtree and reads the local API workflow without hashing either against the candidate. The summary correspondingly records only those two changed-file hashes. Uncommitted or otherwise drifted product-owner/workflow bytes could therefore execute while `identity_match=true`.
- **Evidence:** Candidate diff contains only `LVW_V0_RuntimePatch/tests/test_s1_wp03_live_probe.py` and `reports/v0-s1/wp-s1-03-phase-a/live_probe.py`; the candidate tree contains six production Python files under `custom_nodes/lvw_v0_bridge`, none present in `evidence.identity.file_sha256`. Harness lines 175–210 derive identity from changed files; lines 596–599 copy the unverified local product subtree; line 614 reads the unverified local workflow.
- **Reproduction:** `git diff --name-only 64ec38c22b6d200f18ca5c0d85f91faa1fadf206 919f7fc47150bf164d8d90898fcc4dd69943568e`; `git ls-tree -r --name-only 919f7fc... | rg 'custom_nodes/lvw_v0_bridge/'`; compare both sets with `run-summary.json#evidence.identity.file_sha256` and the `copytree`/workflow-read call sites.
- **Impact:** The `/prompt` and `/history` transport is real, but the evidence cannot prove that the public class owners behind it were the frozen candidate owners. This blocks the production-owner gate and makes the current READY conclusion unsafe.

### M-02 — Major — Raw/suggestion/draft isolation and explicit-adopt epoch cannot be independently recomputed

- **Location:** `run-summary.json#evidence.state_oracle`; harness `execute()` state transition block.
- **Trigger:** Attempt to reconstruct the live `start_run -> model_success -> adopt` state from sealed raw evidence.
- **Expected:** Persist minimized state facts or hashes sufficient to prove: public raw remains raw; suggestion parses separately; model success leaves draft bytes empty and epoch 0; explicit adopt alone writes the chosen draft and increments epoch to 1; the run token matches. Private payloads need not be retained.
- **Actual:** The harness checks the live state in memory but discards `started`, `succeeded`, and `adopted`. The sealed summary retains only `draft_epoch_before=0`, `draft_epoch_after=1`, and `automatic_draft_write=false`. It does not retain the state/run token, raw hash, suggestion hash, draft hashes/emptiness, action, or adopted-field hash. Therefore the independent reviewer can inspect the intended comparison code but cannot recompute the actual live transition from evidence.
- **Evidence:** `run-summary.json#evidence.state_oracle` has only three scalar fields. By contrast, public raw/suggestion hashes are available under `image_oracle`, but no state artifact links those hashes to `LVWDraftStateOwner` output. Comfy logs only show five prompt executions and cannot recover state values.
- **Reproduction:** List keys under `evidence.state_oracle`; inspect harness lines 632–646 and observe that `started`, `succeeded`, and `adopted` are never copied into the terminal evidence.
- **Impact:** This is the primary proof against frozen risk R-S1-01 (model callback overwriting an artificial draft). A derived PASS-like triple is insufficient for an isolated recomputation, so the state-isolation gate remains unproven.

### M-03 — Major — Target integrity and owned cleanup lack independently recomputable terminal substates

- **Location:** `run-summary.json#cleanup`; sealed implementation receipt cleanup/check results; harness `target_hashes()` and `finally`.
- **Trigger:** Recompute pre/post target equality, owned-process terminal state, and the post-terminal recheck from sealed artifacts.
- **Expected:** Persist minimized pre/post hashes for the frozen target set, run-owned Popen/PID terminal states, final listener facts, and temp absence. `cleanup.proven` must be derivable from those terminal substates. A post-terminal check must have a raw/minimized artifact, not only a receipt assertion.
- **Actual:** The harness calculates `before == after` in memory and persists only `target_integrity="PASS"`. The actual pre/post hash maps are discarded. Cleanup records only `owned_count=2`, `failures=[]`, listener count 0, temp removed, and `proven=true`; it does not retain Popen/PID terminal states. The receipt adds a claimed read-only postcheck with zero process/listener/temp counts, but no raw artifact or command result is present in the evidence commit. Thus target equality and complete owned-resource absence cannot be independently recomputed.
- **Evidence:** The artifact manifest contains only `run-summary.json`; that summary has no `target_integrity_pre`, `target_integrity_post`, owned terminal-state list, or post-terminal artifact. `target_hashes()` covers the intended critical set, but the `finally` block stores only a comparison string.
- **Reproduction:** Inspect `run-summary.json#cleanup` keys and the one-entry artifact manifest; search the evidence commit for `target_integrity_pre|target_integrity_post|owned_popen|post_terminal` and compare with the receipt claims.
- **Impact:** Authorization required unchanged target fingerprints and complete owned-only cleanup. Since those facts are not reconstructable, the cleanup/integrity exit gate is unproven even though the aggregate fields are internally consistent.

### m-01 — Minor — Path redaction corrupts non-private URL text in raw service logs

- **Location:** harness `redact()` Windows-path regular expression; `run-summary.json#evidence.service_logs`.
- **Trigger:** Compare URL-shaped log text after redaction with the redaction expression.
- **Expected:** Private filesystem paths are replaced while loopback and documentation URLs remain syntactically faithful, or are replaced with an explicit URL marker.
- **Actual:** The unanchored drive-path expression treats the `p:/` suffix inside `http://` or `https://` as a drive path, producing strings such as `htt<PRIVATE_WINDOWS_PATH>` and `http<PRIVATE_WINDOWS_PATH>`. This damages raw-log fidelity.
- **Evidence:** The stored server config, Ollama informational URLs, and Comfy GUI URL contain the malformed forms. The same log still separately preserves `Listening on 127.0.0.1:11434` and GIN loopback peers, so this defect does not independently invalidate the loopback finding.
- **Reproduction:** Apply the candidate `redact()` function to a synthetic loopback URL offline; no network is required.
- **Impact:** Minor for this run because other structured/static evidence preserves the loopback boundary, but it should be corrected before future raw evidence is sealed.

## Independently recomputed controls

### Commit ancestry, allowed diff, authorization, and sealing

- Direct chain is `70590f1 request -> da1d7a4 authorization -> c2c0bd6 raw evidence -> a14ced9 seal`; candidate `919f7fc` is an ancestor of the request.
- Request bytes independently hash to `7fd042ca...`; authorization bytes at `da1d7a4` hash to `b4daa395...`; both match the sealed receipt.
- Candidate harness Git blob and current sealed file both hash to the authorized `27a50fa...`.
- Candidate diff from the prior authorized seal contains two allowlisted files. This passes path allowlisting but does not close M-01's executed-product identity gap.
- Seal changes the authorization from one-shot granted to terminal expired, binds receipt evidence commit to `c2c0bd6`, and updates governance/manifest coordinates consistently. It does not rewrite raw run evidence.

### Artifact manifest and changed files

- `run-summary.json` is 44,400 bytes and hashes to `380f2af0...`, exactly matching the one-entry artifact manifest.
- Raw evidence commit adds exactly three allowed files: run summary, artifact manifest, and receipt. The sealed receipt lists the same three paths.
- The manifest itself hashes to `e21aff34...`; the sealed receipt hashes to `5e82db10...`.
- Packet payload manifest passes 9/9 and the pack root manifest passes.

### Frozen denominator

- Sorted `V0-A01,V0-A03,V0-A04,V0-A05,V0-A08` plus trailing LF independently hashes to `4b52485d...`.
- Packet, plan, run summary, and receipt all retain the same five IDs as `NOT_RUN`; test counts are denominator 5, not_run 5, pass 0.

### One-shot budgets and observed execution counts

- Summary records one effective image attempt, one model call, one Ollama start, one Comfy start, five public submissions, no rerun, no browser, no cloud/paid cost, and no download/upgrade.
- Raw Ollama log has exactly one `/api/chat` HTTP 200, two `/api/generate` HTTP 200 events (owner per-call cleanup plus harness terminal unload), and one terminal `/api/ps` 200.
- Raw Comfy log has exactly five `got prompt` events: one 15.96-second image route plus four 0.00-second CPU/state/manual routes. This matches the harness flow and the public-submission counter.
- All observed counts are within the authorized maxima. The authorization is terminal and cannot be reused.

### Public route and PromptSpec Oracle

- Sealed trace uses `LVWControlledImageInput -> LVWImagePromptBridge`, with a real prompt ID and two history UI text outputs. Candidate harness calls public loopback `/prompt` then `/history/{prompt_id}`; Comfy log corroborates real prompt execution. No mock/internal helper is used by the live branch.
- Raw envelope independently parses as model `gemma4:26b`, `done=true`, `done_reason=stop`; content has the exact image fields, six non-empty observations, and a non-empty grounded prompt.
- Suggestion hash is `bab2ec5d...`, raw hash is `56c81670...`, and the values differ. Suggestion passes `contracts/prompt-spec.schema.json` with zero schema errors; its observations/inference/unknowns and `text_en` match the raw model content.
- The route mechanics are credible, but M-01 prevents asserting that the executed owners were candidate-bound.

### Manual CPU path

- Harness order proves `stop_ollama()` revalidates listener ownership, stops the owned listener, and waits for port 11434 to disappear before the manual submission.
- After that point, the manual public output contains `model_calls=0`; its result passes `contracts/v0-result.schema.json`, with `analysis_status=not_requested`, `run_id=null`, no model/raw/suggestion, and manual draft origin.
- Raw log has no second model chat. This is credible evidence for the manual CPU path, subject to M-01's owner-byte binding gap.

### GPU, network, model, and unload

- Preflight aggregate is one GPU at 3649 MiB, below the 4096 MiB start limit. Harness code compares Windows-native and WSL rows within 128 MiB before returning this aggregate.
- Runtime aggregate max is 3987 MiB, below the 23552 MiB abort threshold.
- No-cloud is preserved in raw log (`Ollama cloud disabled: true`); structured gate has five samples over at least 10 seconds with zero nonloopback connections. Static transport accepts only literal loopback endpoints; raw server/GIN lines independently retain loopback listener/client facts despite m-01.
- Exact model summary is `gemma4:26b`, one local match, digest `5571076f...`; raw log corroborates local model load and one chat. Harness `/api/tags` gate forbids download or a non-exact local match.
- Per-call/terminal cleanup has two unload HTTP 200 completions and terminal `/api/ps` model count 0.

### Privacy and immutable history

- Structural scan of summary and receipt finds no private Windows/WSL/home absolute path, long media Base64, auth secret, unrelated CommandLine, traceback, or `current_inputs`. Authorized media appears only as alias/hash and semantic text; original media bytes are absent.
- Redacted logs retain extensive model/runtime diagnostics but no identified secret or private path. m-01 concerns fidelity, not leakage.
- Diff from the prior live-04 seal through checkpoint seal does not modify live-01..04 raw evidence or receipts. Historical NO_GO/BLOCKED outcomes remain immutable.

## Verification performed

- `PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover -s LVW_V0_RuntimePatch/tests -p 'test_*.py'` — **80/80 PASS**.
- Harness `--self-check` — exit 0, `live_actions=0`.
- Harness without `--execute-live` — exit 2, `LIVE_FLAG_REQUIRED`, `external_actions=0`.
- PromptSpec and manual-result schemas independently validated offline — zero errors.
- Packet and root manifests verified offline — PASS.

The 80 passing tests do not cover M-01: the existing identity test binds the harness blob and outside-allowlist diff, but has no negative fixture for an uncommitted/drifted production owner or workflow outside the candidate diff. They also do not make discarded live state or target fingerprints recoverable.

## Required gate disposition

Root should retain **NO_GO** for WP-S1-04. A future correction should, before any new live authorization, bind every executed product/workflow blob to a sealed candidate and persist privacy-minimized raw state-transition plus target/cleanup terminal substates. Because the current one-shot authorization is expired and the missing facts cannot be reconstructed after the run, the existing evidence cannot be upgraded by receipt editing or root sealing.
