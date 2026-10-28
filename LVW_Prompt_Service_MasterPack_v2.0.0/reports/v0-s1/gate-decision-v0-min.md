# V0-Min Gate Decision

- Engineering decision: `PASS — V0_MIN_ENGINEERING_READY`
- Final product decision: `PASS — V0_MIN_ACCEPTED`
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

Allowed claim after project-owner sign-off: `V0_MIN_ACCEPTED`.

Still forbidden: `V0.1_ACCEPTED`, `V0.2_ACCEPTED`, `V0_ACCEPTED`, or
production-release approval.

## Remaining gate

The project owner supplied the exact requested human experience/product
sign-off for product candidate `1d48142b95466954ca4da264fa06762abf1522f2`.
The signed scope accepts the V0-Min non-goals and explicitly excludes V0.1,
V0.2, the legacy V0 alias and production release.

- Sign-off: `reports/v0-s1/human-signoff-v0-min.json`
- Acceptance receipt: `reports/v0-s1/v0-min-acceptance.json`
- Next owner: `project_owner`
- Required authorization/sign-off: `NONE_V0_MIN_COMPLETE`
- Exact stop reason: `V0_MIN_COMPLETE_AWAIT_NEXT_VERSION_DIRECTION`
