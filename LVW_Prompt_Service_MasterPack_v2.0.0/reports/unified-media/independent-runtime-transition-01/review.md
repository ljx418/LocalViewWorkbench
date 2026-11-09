# Independent runtime-transition correction review

Final candidate: `57aa9de6052effa4b1043ac0920e54d083204be4`.
Result: **offline correction reviewed; WAIT_AUTH**, Fatal 0 / Major 0 / Minor 0 for this final inspected candidate. Live-04's UI Major/waiter Minor and the later 1d source-fence Major are code-closed with the evidence below. Failed real live-04 remains NO_GO; corrected temporal-sheet semantics have still not been verified by a real result. No Stage PASS or human experience signature.

Reviewer used exact candidate source snapshots, existing CPU artifacts and isolated CPU probes only. No new API, browser, model, GPU/media probe or media decode was launched. Original product/run artifacts were not modified.

## UI and waiter correction

App gates both the analysis button and handler entry on runtimeAction, and tells the user to wait for service switching. Backend controller-busy protection is unchanged; manual editing/export stays available.

The existing controlled CPU02 test is meaningful owner-level evidence: real production React/static bundle, FastAPI/MediaStore/AnalysisService, and explicitly fake Runtime/Provider boundaries. HeldRuntime exposes ready=true while the real runtime_control transaction awaits a barrier. The browser waits until the actual page poll shows model available, verifies analysis is disabled, probes the real backend's busy rejection, checks no extra Job/FakeProvider call, exports manual text, releases the transition and verifies accepted UI analysis after start/reset. It covers start/reset/stop held windows and two completion cases: five conditions, not just five labels.

CPU02's authorized 74328 source/fixture/browser and tested 1d source are byte-equivalent in the relevant paths; 57aa changes only source-fence policy and does not change any product/UI/fixture/waiter bytes. Authorized browser SHA 6a2b4e76766f374870570df2345b8fb0b127fab409aaad7288edcbe1616b2863 matches. Raw server log has three intentional 409 requests, two post-release 202 requests, one 200 each for start/reset/stop and two ModelRun reads. Three manual exports contain the expected sentinels and manual source. stdout JSON equals ui-result, and receipt adds only runner exit 0. Source assertions establish two FakeProvider analyses, not real inference. API PID 1846783 finishes cleanly; browser/API/temp cleanup is recorded and no page errors/external requests are reported.

CPU01's NO_GO/405 control-route failure remains intact. The repair moved only test-app fixture routes before its static mount; it did not change production routing or relabel CPU01 as successful.

The real-browser waiter now recognizes a role=alert submission failure even without a Job. Independent pure Node VM evaluation of exact committed old/new callbacks verifies five states: old no-Job error=false/new=true; busy+alert=false; terminal Job=true; idle/no result=false; busy Job=false. No Playwright/browser was launched. This is predicate verification; CPU02's direct 409 calls separately verify backend protection, not an injected UI error/network run.

Frontend unit/type/build raw hashes/exits match their receipts. A final-candidate 1d backend 108 CPU run reports 108 passed in 5.42s, with stdout/stderr hashes matching; 57aa production/backend/contracts are unchanged. Reviewer audited those existing artifacts without rerunning their service/browser/media operations.

## Source-fence Major found and corrected

Completed1d review found a new Major: the dirty/frozen path lists omitted the actual system-template directory and shared VideoKernel source. Both affect real model/decoder input and build_id. Actual private Git experiments demonstrated that a dirty system template and a committed core.py edit passed every 1d source check to allocation; reviewer intercepted mkdir before any directory was created. The1d finding, original scope/request/authority and failure logs are retained in review-1d1db.md and source-fence-probe.log.

Final 57aa adds templates and LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge to both the initial dirty fence and the pending request's frozen paths. This covers all six specifically identified production dependencies. Repeating the identical actual-Git counterexamples now rejects dirty template at the initial drift check and committed core at the approved-source diff; neither reaches allocation. This closes the demonstrated gap, not merely its error message. No real project source was changed during either experiment.

## New authorization remains locked

Fifteen final-authority negative CPU cases also reject missing new approval despite an old grant, old grant copied to the new path, old live-04 replay, missing/extra history, unknown live-06, request/sample/Harness/packet hash changes, packet leaf/file-set changes, wrong ancestry/frozen diff and a second recheck. Each rejects before a new run directory is created. These tests use private roots and explicitly synthetic grants; they do not issue a real child. Two additional real-Git source-fence cases also reject: 17 guard cases in total.

The registry permits only named live-05 with exactly four historical attempts and the separate runtime-transition grant. Request/approval hash+authid, one recheck, budget/seconds/port/samples/Harness, exact active packet manifest/every leaf/file set, candidate ancestry and zero approved frozen-source differences are checked before allocation. Future child metadata binds the new grant. Old live-04 remains terminal and cannot be replayed.

Current request SHA: `8cade296f1e6d7f034ee4510bffa1e17c8506aa668ca41f1ebb21890518e5e9a`, binding final 57aa and checkpoint SHA b125119d071c333e0f5435a9bf827b4d118c16675697d125e50a0417528b4202. It supersedes the unapproved 1d request d9ff…; the old hash is not approval for 57aa. Active packet 1.0.3 and samples match, and new approval/live-05 were absent at review.

The request transparently asks for a new whole attempt and service startup. The numerical model-call maximum 8 / expected 3 is not an automatic refund or a transferable surviving old grant. A new explicit approval bound to this complete updated request is required. Actual temporal semantics must then be judged from fresh raw output, not HTTP/schema success or offline synthetic responses.

## Gate boundary and project status

This supports presenting the concrete updated authorization request. It does not prove UM 10/10 or close historical UM-04 through a real model response. All old failures and original receipts remain unchanged. No eleven human holdout input was read or inferred.

Outline: V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1/R2/R3/R4/R5a/R5b/R5c each 0/4; current R1.

1. Coordinate: R1/WP-R1-U3/RUNTIME_TRANSITION_CORRECTION_RECHECK/WAIT_AUTH.
2. Completed: old UI/waiter closure, CPU01/02/raw frontend/backend audit, five predicate states, fifteen guard negatives and two actual-Git source-fence rejection tests.
3. Last machine evidence: RUNTIME_TRANSITION_OFFLINE_REGRESSION, tested 1d CPU 108 / frontend 9 / browser 5, source-equivalent final 57aa; this is not real-model/human acceptance.
4. Blocking gate: new explicit supplemental authorization, followed by fresh complete real verification and independent semantic review.
5. Route: early unified slice only; historical accepted V0-Min/R1a scopes retained, full R1/V1 incomplete.
6. Remaining: if approved, one bounded fresh whole attempt, original artifact review, then later human experience signature.
7. Next owner: gate owner/human authorizer. Reviewer does not issue an execution grant.
8. Reviewer authorization: CPU/read-only only; zero services/browser/GPU/model/media probes or extra decode.
9. Evidence: independent-runtime-transition-01/review.md, final-57aa9de-recomputed.json, preserved historical/raw logs and manifest.
10. Exact stop: OFFLINE_CORRECTION_REVIEWED_WAIT_UPDATED_AUTH_REAL_SEMANTICS_UNVERIFIED_NOT_STAGE_PASS.
