# Correction-08 privacy containment

- Status: `CONTAINED_IN_CURRENT_TREE / NO_GO`
- Finding source: `reports/v0-s0/independent-review-correction-08.md`
- Affected immutable source commit: `8fa8140dc7d58bb65fe9eefbc9992f7ad08a8f70`
- Publication rule: do not push, publish, attach, or quote artifacts from that commit.
- Current-tree action: removed 385 over-collected process rows from `preflight-baseline.json` and the duplicated receipt details; retained only aggregate counts and an R-03 marker.
- Evidence rule: the sanitized files are navigation/containment derivatives, not replacements for the original acceptance evidence and cannot support PASS.
- Remaining limitation: Git history still contains the quarantined local object. Rewriting repository history requires separate explicit destructive authorization.
- Required prevention: minimize preflight persistence to target matches only; reject encoded credential/identity-shaped command-line fields; never embed the full process table in a receipt.
