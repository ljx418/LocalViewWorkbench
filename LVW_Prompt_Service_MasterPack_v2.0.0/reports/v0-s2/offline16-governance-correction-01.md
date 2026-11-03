# Offline checkpoint16 correction

Checkpoint16 on candidate8aa68348e744483dd0266b4bac727bf46f607152 is retained as NO_GO. All431 unit tests, native UI module, pack/contracts/manifests and whitespace passed; the governance negative `reject_unauthorized_external_run` failed. No complete native child, target service, model or Chromium run occurred.

Cause: the new program-eligibility validator allowed RUNNING in the frozen packet's readiness field. That field is immutable specification; actual running state now belongs to execution-control.json. A mutation of the frozen packet therefore must remain invalid. Restrict eligibility to the frozen FROZEN_READY_OFFLINE field; mutable execution state is independently checked against its explicit allowed states. Governance self-tests then passed without weakening the negative.

The driver-listener wildcard-address negative now substitutes a synthetic wildcard row while retaining an actual literal127.0.0.1 fixture socket. The first fixture version used a transient wildcard listener, created no clients and served no data; future negative tests need no wildcard binding. Original checkpoint16 evidence is preserved. The targeted five kernel-owner tests passed after this fixture change.

Run a fresh full offline checkpoint on the corrected source before preparing any actual complete child. This correction changes neither the fixed product denominator nor the native full checkpoint/recheck budget, both still unused.
