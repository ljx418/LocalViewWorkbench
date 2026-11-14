# Correction12 root preflight — actual M09 schedule still missing

Candidate 025146bc41c914b870ffe991c2e0b6dd3a49c160. Static source inspection only. No imports, collection or tests. Seven namespace scans clear and requested189 node list/order equals root11 frozen list; those checks do not prove behavior.

## PF12-01: M09 publication-before-timeout schedule not driven

`tools/test_v0_s3_native_custody_correction10.py` `_m09_timeout_phase` lines2118–2132 tightens channel deadline and advances clock BEFORE waiting for the read fault. `_M09TimeoutApi.cancel_synchronous_io` lines2035–2043 then publishes the fault DURING timeout coordination. This drives fault-during-timeout-coordination, not the contract's distinct fault-ALREADY-published then timeout-before-consumption path. The latter is explicitly required by root contract. Keep the existing late fault subcase if useful, but add the missing actual order inside the same N10-R10 identity.

Use a transparent event gate at the actual await wait/selection boundary: call the original production wait, hold the endpoint before it rechecks/consumes its generation, independently publish primitive fault, wait until THAT generation's immutable error/object exists, then publish/advance effective timeout, release endpoint and observe the real error selection and downstream channel/BrokerProcess/two Session.stop histories. Record publication→timeout→consumption order and current generation. A generic outcome_published event may be stale from READY/STATUS; wait the specific outcome. Do not overwrite outcome selection/history or return synthetic facts. Both successful and failed real coordination, parallel timeout facts and bounded unconditional teardown remain required.

Candidate is NOT admitted to run yet. No budget consumed, no native or Stage acceptance. Static test-only follow-up may correct PF12-01 and receipt. Production blobs are independently reviewed frozen at025146bc; do not change production until findings return, unless asking root first. Keep all historical receipts; no bulkadd/remove/untracked cleanup. New candidate identity and pins required after edit.
