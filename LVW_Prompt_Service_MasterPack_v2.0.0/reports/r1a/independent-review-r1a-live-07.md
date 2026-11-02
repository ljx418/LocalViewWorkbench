# LIVE-07 independent review

Reviewer: isolated agent /root/live07_review. Input: isolated git archive of evidence commit 9371666 and product candidate 53b77cfff8a0d57929dd219f24f9d16e5e51a641. Read-only deterministic inspection; no services, browser, model or media executed.

Decision: NO_GO / changes required. No Stage PASS.

## Findings

- Major: R1A-M05 failed the document scrollWidth/clientWidth oracle at 360px. Browser exit 1 and horizontal overflow are recorded in live-receipt.json. The harness throws before screenshot capture; measured widths and offending element are unavailable. 1280/1920 checks were not reached. Layout was not independently reproduced.
- Evidence integrity: the Stage manifest at evidence commit 9371666 was stale after terminal stage-control mutation. Coordinator subsequently reconciled manifests in commit 3b0c642; governance 20/20 and pack 1338/1338 passed. This reconciliation does not change the failed live outcome.

## Independent recomputation

All four bound harness/guard/wrapper hashes, offline-checkpoint hash and request hash match authorization. No product or bound Harness changes exist between candidate and evidence commit. Receipt authorization hash matches the active authorization in the parent commit; terminal expiry explains its later change.

One submission, one browser run and one provider started/completed pair with matching call ID are evidenced. Fixed seven-ID denominator hash recomputes correctly. All seven receipt dispositions remain PENDING; no completed case PASS is inferred.

Cleanup receipt records model UNLOADED, both services STOPPED, Windows/WSL ports EMPTY, runtime REMOVED, wrapper child exited, and zero cleanup errors. Harness checks support these recorded claims; the reviewer cannot observe past machine state independently.

Manual and adopted exports exist, adopted values match TXT, and harness order supports successful adoption/clipboard/export checks before overflow. Missing browser-result.json, screenshots, raw response and structured domains prevent independent semantic quality, raw/PromptSpec linkage and complete network-oracle verification. R1A-M06 remains unproven.

LIVE-07 expired at receipt completion. Corrections may proceed offline; another real run needs fresh authority.
