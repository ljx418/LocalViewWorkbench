# R1a Live 02 Independent Review

- Reviewer role: `codex_r1a_independent_reviewer`
- Review isolation: fresh delegated context, read-only repository review
- Runtime actions: none
- Candidate: `7735a697591e3207183a2d0714c73078565f8219`
- Authorization: `AUTH-V1-R1A-2026-10-29-LIVE-02`
- Decision: **NO_GO**
- Severity: **Fatal 0 / Major 5 / Minor 2**

## Evidence verification

The frozen packet, candidate ancestry, three harness blobs, request hash, authorization hash and receipt time chain are internally consistent. The receipt was not yet committed at review time and lacks wrapper exit/stderr evidence, so it proves an internally consistent failure receipt rather than the absence of every possible orphan process.

## Major findings

1. Real acceptance did not execute: phase `OLLAMA_START`, error `OLLAMA_OWNER_RECORD_TIMEOUT`, attempts/model/browser `0/0/0`, and all seven fixed cases remain pending.
2. The terminal receipt consumed the authorization while the pre-review control plane still described it as active and executable.
3. `ollama=NOT_STARTED` is inaccurate after the PowerShell wrapper was launched. Owner timeout must be represented as `START_ATTEMPTED_OWNER_UNPROVEN`, and port emptiness alone cannot prove that no idle child exists.
4. Wrapper stdout/stderr were sent to `DEVNULL`, early wrapper exit was not detected, and its temporary inputs were deleted. The evidence cannot distinguish wrapper parsing, UNC/redirection, process start, early child exit or owner visibility failures.
5. Later success could still be false-green: cleanup does not atomically revalidate PID/start/path/listener ownership; the browser observes rather than pre-blocks non-loopback requests; UI submissions are not a real model-call ledger; and the browser oracle does not fully cover all four outputs, manual zero-model path, draft separation or the full F01 criteria.

## Minor findings

1. The authorization record had no bound approval commit before terminal reconciliation.
2. The immutable request remains `PENDING_PROJECT_OWNER_APPROVAL`; consumers must treat the separate authorization record as the status authority.

## Exact stop reason

```text
NO_GO:
AUTH-V1-R1A-2026-10-29-LIVE-02_EXPIRED_ON_TERMINAL_RECEIPT
+ OLLAMA_OWNER_RECORD_TIMEOUT
+ OLLAMA_START_AND_PROCESS_CLEANUP_UNPROVEN
+ LIVE_PRODUCT_PATH_NOT_EXECUTED_0_0_0
+ FIXED_DENOMINATOR_7_OF_7_PENDING
+ STALE_ACTIVE_AUTHORIZATION_CONTROL_PLANE
+ MAJOR_INDEPENDENT_FINDINGS_PRESENT
```

## Required correction

- Preserve and commit the failure receipt, expire the authorization and stop all live-02 reuse.
- Capture bounded wrapper exit/stderr, detect early exit and represent attempted-but-unproven process state accurately.
- Use a Windows-native temporary control directory and atomically verify PID, creation identity, executable and listener before termination.
- Abort non-loopback browser requests before dispatch and obtain model-call counts from the backend/provider boundary.
- Cover all four outputs, manual zero-model workflow, raw/suggestion/draft separation and remaining F01 oracles.
- Add negative tests, produce a new candidate/checkpoint, and request a new run ID and authorization.

The candidate must not enter WP-R1A-05 until a later live run completes and an isolated review reports Fatal 0 / Major 0.
