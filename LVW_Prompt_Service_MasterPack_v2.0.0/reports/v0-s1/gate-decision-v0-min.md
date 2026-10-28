# V0-Min Gate Decision

- Decision: `PASS — V0_MIN_ENGINEERING_READY`
- Candidate: `6fcd114f6e781d143f713e82996720180a94434b`
- Independent review: `reports/v0-s1/independent-review-v0-min-privacy-correction-02.md`
- Review result: Fatal 0 / Major 0 / Minor 0
- Historical checkpoint: `checkpoint-01` remains `NO_GO / CASE_PRIVACY_VIOLATION`

## Scope

This decision applies only to the reduced V0-Min denominator defined by
`docs/22_V0_MIN_REBASELINE.md`: V0-A01, V0-A03, V0-A04, V0-A05 and V0-A08.
Video/resource work is V0.1; packaging, migration and rollback are V0.2.

The historical one-shot checkpoint is not rewritten. The gate relies on the
independently recomputed product facts plus the offline privacy correction that
removes raw log persistence and counts Windows/WSL paths in the fail-closed
aggregate. No further live run is required or authorized.

## Claim boundary

Allowed claim: `V0_MIN_ENGINEERING_READY`.

Forbidden until the project owner signs: `V0_MIN_ACCEPTED`, `V0.1_ACCEPTED`,
`V0.2_ACCEPTED`, `V0_ACCEPTED`, or production-release approval.

## Remaining gate

The only remaining V0-Min item is human experience/product sign-off. Codex does
not substitute for that judgment.

- Next owner: `project_owner`
- Required authorization/sign-off: `HUMAN_V0_MIN_EXPERIENCE_SIGNOFF`
- Exact stop reason: `WAIT_HUMAN_V0_MIN_EXPERIENCE_SIGNOFF`
