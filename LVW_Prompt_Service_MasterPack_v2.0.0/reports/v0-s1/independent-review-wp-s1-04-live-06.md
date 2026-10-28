# V0-S1 / WP-S1-04 Fresh Independent Review — live-06

- Review role: isolated independent reviewer
- Review mode: offline/read-only; no ComfyUI, Ollama, GPU, port, network, browser, or real-media action
- Frozen execution candidate: `1d48142b95466954ca4da264fa06762abf1522f2`
- Raw evidence commit: `e45df309831ac1488cb3b465fab089f5da8432e0`
- Root sealing commit: `2cd1b59819f315efe52440b5ce95ce082937f4f3`
- Authorized harness SHA-256: `94953202138267ca988818a5ba75704d845c15e288fb406d8f7af21d1af4af52`
- Evidence slot: `reports/v0-s1/wp-s1-03-live-06/`

## Outcome

**Fatal 0 / Major 0 / Minor 0**

**Recommendation: READY_FOR_GATE_DECISION.** The live-06 evidence closes the four previously identified evidence defects under independent recomputation. This recommendation is limited to the WP-S1-04 gate decision: it is not a Stage PASS, does not convert any product case to PASS, and does not authorize a rerun. Authorization `AUTH-V0-S1-2026-10-28-06` is terminal and expired.

No false-green path was identified in the reviewed evidence. The recommendation depends on the immutable Git objects and hashes listed above, not on the receipt's PASS labels.

## Findings

No Fatal, Major, or Minor finding.

## Independent closure of the prior evidence defects

| Prior issue | Independent live-06 fact | Disposition |
|---|---|---|
| M-01 — executed production owner/workflow bytes were not candidate-bound | The evidence names six bridge Python files and the public image API workflow. Independent `git show` hashing of all seven candidate blobs equals both the local bytes and all seven recorded SHA-256 values. Candidate Python inventory is exactly the six recorded files. | Closed |
| M-02 — raw/suggestion/draft isolation and adopt epoch were not reconstructable | Independent canonical-JSON reconstruction reproduces all three complete state hashes. Actions are `start_run`, `model_success`, `adopt`; statuses are `running`, `succeeded`, `succeeded`; epochs are `0,0,1`. The empty draft remains unchanged through model success; public raw and suggestion hashes link unchanged into success and adopt; only explicit adopt changes the draft and epoch. | Closed |
| M-03 — target integrity and owned cleanup lacked terminal substates | The six named target aliases have complete pre/post values and compare equal. Both owned listeners have re-proven lineage, stop requested, and terminal absence; both owned wrappers have terminal `poll_after=255` and `exited=true`. The in-run post-cleanup snapshot records zero target listeners, zero target-process matches, and absent run temp. | Closed |
| m-01 — path redaction damaged loopback URLs | The sealed logs retain literal `http://127.0.0.1:11434` and `http://127.0.0.1:8191`; the former malformed redaction form is absent. Structural privacy scans found no private absolute path, secret, long Base64 value, command-line dump, traceback, or `current_inputs` overcollection. | Closed |

## Recomputed evidence

### Commit, authorization, and sealing chain

- Direct ancestry is candidate `1d48142b...` → request `1db99180...` → authorization `0142ab72...` → raw evidence `e45df309...` → root seal `2cd1b598...`.
- Candidate changes exactly two allowlisted files: the live harness and its offline test. Raw evidence adds exactly the run summary, artifact manifest, and implementation receipt.
- The request bytes independently hash to `6f7cb3f14e4f59df2c04b53c1b5c15ba5aebe596c46816e431bdad57fedbd008`; the authorization record at its authorization commit hashes to `e833f6c8c6653f0fda4c825f697a0d7e7f12723016bbf952c40d273e1bf7d4a4`.
- Request, authorization, run summary, receipt, and root seal agree on candidate, harness, authorization ID, run ID, sample hash, evidence destination, and budgets. The seal changes the authorization to terminal/expired and binds the receipt to raw evidence commit `e45df309...`; it does not rewrite the raw run artifacts.
- Historical live-01 through live-05 evidence is unchanged across the live-06 candidate/request/authorization/evidence/seal chain.

### Packet and artifact integrity

- `sha256sum -c .agent-governance/stages/V0-S1/PAYLOAD_MANIFEST.sha256`, executed from the packet directory, passes all nine entries.
- Repository `MANIFEST.sha256` passes in full at the root seal.
- `run-summary.json` is 49,753 bytes with SHA-256 `668ff7a4379d291ff647518df12eb5a505394a9f062bad9086fe3302ad77566a`; the one-entry, 93-byte artifact manifest contains this exact mapping. The manifest itself hashes to `32f48d5a45d618ce53e011ac29735b8d2b4e8ca7c07e01b86766cfb6011edb7e`.
- The current harness, candidate harness blob, authorization, summary, and receipt all bind SHA-256 `94953202138267ca988818a5ba75704d845c15e288fb406d8f7af21d1af4af52`.

### Public production path and semantic Oracle

- The sealed public graph is `LVWControlledImageInput` → `LVWImagePromptBridge`; it records a real prompt ID, `/prompt` payload, and `/history` UI outputs. Static harness inspection confirms submission and retrieval use the public `/prompt` and `/history` interfaces, not direct owner calls or a mock substitution.
- The Comfy service log independently contains five `got prompt` events, matching the five public submissions: image, state start, state success, state adopt, and manual CPU route.
- The first history output parses as the raw Ollama envelope. The second parses as a `lvw.prompt/1` PromptSpec with the exact expected top-level and domain keys, non-empty observation list, and non-empty English text. Their recomputed hashes equal both the image Oracle and state-chain links.
- The raw response, suggestion, and draft remain separate. The adopted draft hash is `83768e772a470a31d623a240e09dad0fcf9798eb3613ba005a79c28de9f611c8`; draft epoch advances only on `adopt`.
- The manual public route occurs after the owned Ollama stop. Its output independently validates against `contracts/v0-result.schema.json` and records `source_type=manual`, `run_id=null`, `analysis_status=not_requested`, `suggestion=null`, and zero model calls.

### Budgets, local-only execution, and resource gates

- Observed budgets are image attempts `1/1`, model calls `1/1`, Ollama starts `1/1`, Comfy starts `1/1`, public submissions `5/8`, browser runs `0/0`, and external cost `0/0`. The one-shot command records exit code 0 and no retry.
- Preflight records one GPU at 3,881 MiB, below the 4,096 MiB start limit; target-process and target-listener counts are both zero. Runtime peak is 4,458 MiB, below the 23,552 MiB abort threshold.
- The no-cloud gate records `OLLAMA_NO_CLOUD`, at least 10 seconds and five samples. Every sample has zero nonloopback connections; runtime nonloopback count is also zero. Raw service logs retain literal loopback listeners/clients.
- Exact local model evidence is `gemma4:26b`, exactly one match, digest `5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251`; no download or upgrade is recorded.
- The raw Ollama log has exactly one successful `/api/chat`, two successful `/api/generate` cleanup calls, and one successful terminal `/api/ps`. Structured evidence records cleanup HTTP 200 and terminal model count zero.

### Integrity, cleanup, privacy, and fixed denominator

- Target pre/post aliases are `main.py`, `folder_paths.py`, `nodes.py`, `comfy/cli_args.py`, `extra_model_paths.yaml`, and `prompt_assistant_state`; every value is present and equal.
- Cleanup has no failures, zero final target listeners, both listeners terminal-absent, both wrappers exited, run-owned temp removed, target integrity PASS, and `cleanup.proven=true`. The separate in-run post-cleanup snapshot corroborates listener/process/temp absence.
- Evidence minimization preserves only aliases and redacted target paths while retaining loopback URL fidelity. No secret, private absolute path, reversible long token, raw command line, traceback, or input dump was found.
- The frozen denominator independently hashes from `V0-A01\nV0-A03\nV0-A04\nV0-A05\nV0-A08\n` to `4b52485dbaa7daeccb31b5c91771b51f8106ab6e49267328990ad4da3b5f85c5`. The packet, receipt, and run summary retain all five cases as `NOT_RUN`; denominator is 5 with pass/fail/blocked/skipped all zero. No product case is promoted by this review.

## Offline verification performed

All commands below were read-only except creation of this report; none contacted a service or external interface.

```text
git show / git diff-tree / git merge-base ancestry and blob checks
sha256sum -c .agent-governance/stages/V0-S1/PAYLOAD_MANIFEST.sha256
sha256sum -c MANIFEST.sha256
independent Python canonical-JSON, SHA-256, schema, state-link, target-map,
cleanup, budget, network-sample, privacy, and fixed-denominator checks
PYTHONDONTWRITEBYTECODE=1 python3 -B -m unittest discover \
  -s LVW_V0_RuntimePatch/tests -p 'test_*.py'
python3 -B reports/v0-s1/wp-s1-03-phase-a/live_probe.py --self-check
```

Results: full offline suite **87/87 PASS**; harness self-check exit 0 with `live_actions=0`; packet and root manifests pass. These offline tests support the evidence checks but do not replace the sealed live trace.

## Gate limitation

The root gate owner may now decide WP-S1-04 using the sealed live-06 evidence. This report neither declares V0-S1 PASS nor authorizes further execution. A Stage PASS would still require the frozen governance conditions and formal root decision; the fixed product cases remain `NOT_RUN`.
