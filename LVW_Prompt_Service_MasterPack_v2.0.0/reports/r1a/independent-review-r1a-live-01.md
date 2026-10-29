# R1a Live 01 Independent Review

- Reviewer role: `codex_r1a_independent_reviewer`
- Review isolation: fresh delegated context, read-only repository review
- Runtime actions: none
- Candidate: `605d954c8161af2ad5690301f7942d8c7e93f66a`
- Authorization: `AUTH-V1-R1A-2026-10-29-LIVE-01`
- Decision: **NO_GO**
- Severity: **Fatal 0 / Major 4 / Minor 1**

## Major findings

1. `listener()` uses Windows `Get-NetTCPConnection` only. It missed a pre-existing, non-owned WSL listener on port 8765, so both preflight and `ports_empty=true` were invalid. The unrelated process was not terminated.
2. Ollama cleanup identifies the listener only by executable basename and does not prove that the stopped process is the run-owned child or resist listener replacement.
3. The real acceptance did not run: the receipt records attempts/model calls/browser runs as `0/0/0`. It lacks stage-specific failure, identity snapshots, dual-domain port snapshots and fixed-denominator dispositions.
4. A terminal receipt consumed the one-shot authorization, while the pre-review control plane still described it as active and executable.

## Minor finding

`SERVICE_START_TIMEOUT` and Boolean cleanup fields conflate not-started, stopped and unproven states.

## Exact stop reason

```text
NO_GO:
PREEXISTING_WSL_LISTENER_8765_UNDETECTED
+ LIVE_ACCEPTANCE_NOT_EXECUTED
+ CLEANUP_EVIDENCE_UNPROVEN
+ ONE_SHOT_AUTHORIZATION_EXPIRED_ON_TERMINAL_RECEIPT
```

## Required correction

- Preserve the failed receipt and expire the authorization.
- Add Windows and WSL preflight/cleanup checks and refuse non-owned listeners.
- Bind backend and Ollama process ownership, parentage, creation time and socket identity before termination.
- Persist phase-specific, candidate- and authorization-bound terminal evidence.
- Add negative tests for WSL-only/Windows-only listeners, replacement, timeout and non-owned cleanup refusal.
- Produce a new candidate and checkpoint, then request a fresh run ID and one-shot authorization.

The candidate must not enter the human experience gate until A02/F01/Q01 really run, dual-domain cleanup is proven and a later independent review reports Fatal 0 / Major 0.
