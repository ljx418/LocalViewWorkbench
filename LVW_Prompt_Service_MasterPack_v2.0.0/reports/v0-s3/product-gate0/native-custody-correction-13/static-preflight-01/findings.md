# Correction13 root static preflight — validation deferred

Candidate a69170c446ff4af2955ddac1707af91d00c5dfcd. All7 committed source/test bytes verified, namespace scans clear, actual AST test definitions reproduce exact189 node list/order. No imports, collection, pytest or runtime probes. Independent immutable production review proceeds separately; defer implementation follow-up until its full findings can be consolidated.

## PF13-01: M07 cross-product obligations have no new executable drivers

The candidate changes progress/release code but N07-R09/N05-R10/N10-R05 tests only retain their ordinary raw-failure or cancelled-raw retry paths (R05 gains isolation/final recovery). No event-driven test was added for original HANDLE close failing together with raw close, KI/SystemExit at each raw position after earlier releases, or live original context tightening between initial raw closes. atom-matrix.md describes required cross-product but source test drivers do not implement it. A matrix is not execution proof. Require subcases inside existing IDs with real same-owner calls, exact original HANDLE/stream identities, all confirmed per-resource call counts, recovery after controlled fault release, and before-salvage retained facts. In particular interrupted stdout may leave a later stderr that must stay reachable; earlier ordinary raw failure followed by later KI must not be lost with helper return. No extra nodes or denominator reduction.

## PF13-02: millisecond exact boundary fixture uses cancellation-prone epoch

N07-R02 constructs deadline1000.0+0.001 and subtracts1000.0 before int(ms). A float labelled1ms need not remain exactly1ms after this subtraction; the production floor can correctly refuse it while the test demands1. Use a common zero clock origin or explicitly representable values, bind the actual remaining and assert recorded primitive bounds from those values. No standalone numeric/runtime probe or ceil/floor relaxation. Cover zero, belowunit, exactunit and oneover through API/Core adapters, including recovery adapter. The finite no-positive-floor rule stays unchanged.

## PF13-03: parent supervisor and launch subpath evidence incomplete

M08-C.1 adds child-loop driver, but no actual parentpump/StreamChannel queue and parentreply event-wait schedule after current-context tightening. Drive real owners and record next requested arguments with transparent wrappers; original context identity and zero-expired behavior must be observable. M08-E new schedule pauses during hash and refuses channel; the required stop while Popen is admitted, then refuse next executable read/hash, has no new test driver. Add both actual schedules using scoped in-process seams only under future rootguard. Do not infer zero hash/channel work from owner.channel None alone; record attempted effects/entry to actual seam.

These are missing coverage and fixture observations, not new Major counts or a Stage verdict. Root will combine with complete independent production findings before returning one correction. Existing189 IDs/order and previous failures are preserved. New candidate required before root pins a finite validation plan.
