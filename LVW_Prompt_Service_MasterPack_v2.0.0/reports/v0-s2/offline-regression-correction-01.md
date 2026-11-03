# V0-S2 offline regression correction 01

Scope: repository-only regression; no service, real media, model or Stage live checkpoint. This navigation summary is not a formal live/Stage acceptance receipt.

Initial complete subtree command: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s LVW_V0_RuntimePatch/tests -p 'test_*.py' -q. Exit 1; 151 tests; failures=1, errors=7. Root cause: historical V0-S1 Harness correctly rejects the S2-expanded Python inventory rather than accepting it as the signed 1d48142 candidate. Initial pack validation also reported four stale current-file hashes.

Correction: keep historical Harness bytes unchanged; test it using actual Git blobs from its signed candidate in a mount-compatible temporary fixture, with byte comparison and inventory validation retained. Resolve the Harness's own test location to an identical copy. Added a negative proving current expanded inventory is still rejected. Fixture setup's first trial exposed mount/self-location constraints and was corrected without weakening Harness checks. Current manual/state behavior continues to be driven by current production imports in the suite.

Additional production correction: integrated owner explicitly rejects same-thread reentry while its current request resources remain unreleased. A regression test proves a nested invocation cannot replace the outer token/state.

Final verification:

- Full V0 subtree: exit 0, 153 tests, 88.044s, OK.
- Signed-Harness directed suite: exit 0, 15 tests, OK.
- Request-owner directed suite: exit 0, 4 tests, OK.
- Pack document/contract check: exit 0, 1374 passed, 0 failed.
- Governance self-test: exit 0, errors empty.
- Comfy web extension ES module syntax: exit 0.

Manifest now covers added S2 Python modules, web JS, tests and video workflow candidates and updates changed current-file hashes. No historical failure report was overwritten, no test was removed or skipped, and no acceptance threshold changed.

Remaining before actual Stage checkpoint: candidate-bound trusted runner/receipts and target bindings; real FFmpeg/Comfy/browser compatibility; hardware contention/preflight and full ten-image/ten-four-frame performance observations; native path, interruption, cleanup and independent review. No V0-A02/A07/A09/A10 PASS is claimed.
