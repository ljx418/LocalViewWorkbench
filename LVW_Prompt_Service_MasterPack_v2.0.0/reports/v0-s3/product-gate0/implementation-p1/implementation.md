# S3-P1 implementation receipt — READY_FOR_REVIEW

Code candidate: `c3c6bcb6a96576d9ed542acb4eb25c55d6b204d0`.
Baseline: `28cf4211674fb89d2661474109e6f2d8ef42a0a1` (initial worktree clean, fast-forward merge).
Author: ljx418 <1173696783@qq.com>.

The frozen P1 contract is unchanged. Only its nine source/test whitelist files changed; fifteen packet/spec hashes were recomputed unchanged. `receipt.json` contains source hashes, exact commands, actual exits, coverage, earlier failures, ten reporting fields and the complete V0–V3 outline. This is implementation/self-check evidence, not an independent review or Stage PASS.

## Production path and accounting

Default `BridgeOwner.analyze_image` reaches `call_one_frame` → `OllamaLoopbackTransport._post`, which debits the exact compact UTF-8 body immediately before `opener.open`. The separate interruptible `chat` owner debits after its final owner/cancel checks and body serialization, before `connection.request`; it does not call the default `_post`. Four-frame owner execution therefore debits four times. Cancellation after debit refuses the send but retains the debit. Cleanup/status/unload do not enter this debit branch.

`NativeRuntime.preload(..., *, s3_budget_binding=None)` debits once, separately from measured chat, using the exact `json.dumps(..., allow_nan=False)` bytes used by `v0_s2_http`. Caller accounting must not pre-debit S3 preload. Ordinary runs without S3 mode retain the prior product behavior. The existing warm20, native64, four-attempt limits remain enforced by their original owners.

All debits go through the unchanged `local_program_authority.model_action(child_path)`. The shim loads that module by its sealed root-relative filename and pinned source hash; it never rewrites module globals or budget policy. Thus `ROOT`, approval chain, frozen source files and execution binding verification resolve at the authority root, not at the native client installation or a guessed worktree ledger. Before invoking the transactional API, the shim requires an existing ledger and read-only checks the exact bound row; production requires `samefile` identity with that root's historical live15 ledger pointer. No substitute DB is created. Fixture mode requires an explicit marker under the OS temporary root and a ledger within that fixture root.

## Internal protocol version 1

Entry: `authorize_model_action(action_kind, payload, *, binding=None)`. `payload` is the actual wire **bytes**, not a digest of a different serialization. `action_kind` is only `chat` or `preload`. `binding`, when provided by trusted runtime code, is exactly `{path, sha256}`; otherwise the two `LVW_S3_BUDGET_BINDING[_SHA256]` variables provide it. `LVW_S3_BUDGET_REQUIRED`, any configured binding, or an active S3 profile requires admission. No public API accepts an executable, shell or argv.

The binding uses `schema=lvw.s3-budget/1` and these exact fields (missing/unknown keys reject):

```
schema program approval_sha256 run_id stage_id candidate_sha
child_path child_sha256 ledger_path execution_path execution_sha256
authority_root tools issued_at expires_at transport harness_transport distribution
binding_path client_binding_path model model_digest ollama_pid ollama_start_ticks
```

`program` is COMPLETE03; `stage_id` is V0-S3. `tools` contains exactly `authority`, `shim`, `python`, `wsl`; each present role is `{path, client_path, sha256}`. The WSL role is null for local modes. Authority/shim roles must name their fixed filenames under authority_root. Paths are explicit: `binding_path` and child/execution/tool authority paths are WSL paths, `client_binding_path` is the Windows-readable binding path in Windows mode. Windows never uses `pathlib` to read the Linux child path. The same binding is loaded at the WSL path by the runtime's explicit preload/profile capability.

Windows argv is only:

```
<sealed wsl.exe> -d <sealed distribution> --exec <sealed Python> -I -B <sealed shim>
```

`transport=wsl` pairs with `harness_transport=local-wsl`; on the WSL harness the fixed argv is `<Python> -I -B <shim>`. `local-wsl` and `local-fixture` have null distribution, with matching fixed harness mode. No shell, HTTP bridge, daemon or executable discovery occurs. `_command` is private; model/media input cannot choose any of these roles.

The request is exactly `{schema: lvw.s3-debit/1, request_id: UUID, action_kind, payload_sha256, model, binding_path, binding_sha256}`. The success response is exactly the request echo plus `{status: DEBITED, run_id, child_sha256, authority_sha256}`. No image/base64/prompt is transmitted to the shim or included in its receipt. JSON rejects duplicate keys and nonfinite numbers. Binding/child/request/response JSON and each stdout/stderr buffer are capped at 32768 bytes. Each invocation has a fresh UUID, at most ten seconds and no more than the sealed remaining lifetime; no retry, reconnect, child substitution, refund or auto-replay is provided.

The client requires a matching receipt **and** actual exit 0 **and** no pipe/timeout/limit error **and** owned-process reap/read-thread completion. It preserves true exit and error independently, request UUID and output hashes on protocol/process failure. Malformed or lost receipts after a successful debit leave the authority reservation and call count unchanged. The terminal coordinator must preserve the exception and resolve the uncertain-send case explicitly; it must not call again as a retry.

## Sealing order for the later P2 coordinator

1. Freeze candidate authority-root source, shim/protocol/authority/Python/WSL roles and the original ledger identity; discover actual installed Windows roles only in a later authorized run.
2. Reserve a finite child in that **same** ledger, with explicit root and ledger arguments; this P1 never reserves a real child.
3. Write execution bindings with `s3_authority`, `s3_shim`, `s3_python`, optional `s3_wsl` and `s3_protocol` path/hash entries, plus required runtime tools. Freeze/hash this file.
4. Construct the complete binding except `child_sha256`; put exactly that dictionary in the child's `s3_budget`. Child also binds run/stage/candidate/program/hash/ledger, nonempty `frozen_files`, and `execution_bindings_required=true`. Issue times/expiry must fit the reserved row. Freeze child, `bind`, `bind_execution`, then fill the binding's child hash and publish identical binding bytes to the two declared OS-visible locations. This order avoids circular hashes.
5. Publish binding hash/environment to the owned native process; pass explicit binding reference into WSL preload/profile generation. Native and warm S3 profile validators match child hash/path, candidate, run, model digest, PID/birth and binding hash. Expiry fits the child and 21600 seconds; old scopes still have 7200 seconds. Runtime-generated profiles reject candidate/model/PID mismatch before writing.

The stdio capability trusts the frozen owned files and processes. It is not a defense against an actively malicious local user with equal permissions. Windows transport construction is unit-tested only. Actual WSL subprocess lifetime after killing a Windows wrapper, cross-OS file visibility, PID/model seals, P2 cleanup/settlement, complete Gate0 and real product acceptance all still need their own evidence.

## Validation and retained failures

`check-1.log`: frozen packet command, **66 passed**, real exit **0**.
`check-2.log`: affected existing bridge/interruptible/native profile/warm profile/runtime owners, **77 passed**, real exit **0**. `checks.json` records complete command arrays, elapsed time, candidate and log hashes. No broad checkpoint, network, model/GPU/service, source media, old preview, download, real ledger read/reserve/debit or real acceptance was run.

The tests drive default and interruptible production owners through one/four HTTP boundaries and runtime preload through one boundary, with real fixture SQLite commits already visible before the substituted final network call. Negative paths include cap/concurrency, stale seals, missing ledger, invalid COMPLETE03, wrong echo, actual exit7 after valid stdout, exit0 with a separate transport error, lost receipt, real owned subprocess timeout/output overflow, and cancellation after debit. Fixture roots are removed in `finally`; local timeout verifies actual reap, joined pipe threads and closed handles.

Earlier development attempts are retained in receipt metadata: an initial path mistake ran no tests (exit4); the first real attempt had 52 pass/11 fail because the HTTP substitute lacked `debuglevel`; fixing that exposed the real misplaced debit insertion in the cleanup loop (52/11). Moving it to the exact chat body boundary then gave 63 pass. Added long-expiry, WSL-path and post-debit cancellation coverage produced the final 66/77. These are distinct findings and corrections, not two no-progress retries; no old failure artifact was rewritten. Prior outputs were observed in the terminal; only final raw logs were separately saved.

## Route and remaining owner

V0-S0 1/2 (historical NO_GO); V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; **V0-S3 0/6, current P1**; R1 0/4; V1-M1 0/3; R2 0/4; V2 R3 0/4 and R4 0/4; V3 R5a/R5b/R5c each 0/4. V1-D0 preparation remains its separate accepted 2/2; unified early slice remains human accepted only in its signed scope. None of those denominators changed.

Next owner: separate read-only reviewer, then root architect/gate owner for P2 and real runtime binding. Implementation status is only **READY_FOR_REVIEW**.
