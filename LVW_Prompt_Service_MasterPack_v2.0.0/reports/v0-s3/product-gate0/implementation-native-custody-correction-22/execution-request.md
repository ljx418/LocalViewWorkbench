# Correction 22 — finite execution REQUEST (not executed)

**STATUS: REQUEST ONLY. NOTHING WAS EXECUTED.** This document asks the root
for a separate, frozen and finite runtime authorisation. It must not be run
before that ACK. The candidate of this correction is STATIC only: no
candidate import, no collection, no pytest, no ctypes, no runtime, no native
call, no OS business process, no model, no GPU, no service, no network, no
media, no database, no ledger or counter side effect was performed while it
was produced.

## Binding of the request

| Item | Value |
|---|---|
| Coordinate | V1/R1/WP-R1-U3/S3_P4 |
| Baseline delivery | `08e2096ed67a3c0a158dfa2239bdbc549b6fba12` |
| Baseline source candidate | `ed4afb50e3d6c12e8784d05dc40b9beb501a3668` |
| Candidate of this correction | `tools/test_v0_s3_native_custody_correction10.py` (SHA256 in `pins.json`) |
| Denominator | 189 identifiers, unchanged (static AST proof) |
| Assertions | 414 → 414, 8 predicates **moved**, 0 added, 0 removed |
| Other sources | 6 sources byte identical (SHA256 pins in `pins.json`) |
| Evidence root of the candidate | `reports/v0-s3/product-gate0/implementation-native-custody-correction-22/evidence` |
| Total budget requested | **≤ 300 s** for the three commands together |
| Retries | none — one attempt per command, no retry, no switch of route |
| Scope of the run | the five modules of the frozen denominator, this candidate only |

## The three commands (in this order)

### 1 — the frozen 189-node batch (≤ 240 s)

```sh
cd <PACK_ROOT> && python3 -m pytest -q -p no:cacheprovider \
  tools/test_v0_s3_native_custody.py \
  tools/test_v0_s3_native_custody_regressions.py \
  tools/test_v0_s3_native_custody_correction05.py \
  tools/test_v0_s3_native_custody_correction07.py \
  tools/test_v0_s3_native_custody_correction10.py
```

Expected: 189 collected, 189 passed. The historical 189 PASS of the
correction 14 stays historical; the dynamic 15–21 stay `NOT_RUN`; this run is
the **first dynamic** run of the correction 22 candidate.

### 2 — the group of the counterexamples (≤ 40 s)

```sh
cd <PACK_ROOT> && python3 -m pytest -q -p no:cacheprovider \
  tools/test_v0_s3_native_custody_correction10.py::test_n10_r07_the_context_of_the_round_reaches_every_layer \
  tools/test_v0_s3_native_custody_correction10.py::test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread \
  tools/test_v0_s3_native_custody_correction10.py::test_n10_r11_the_overflow_of_the_channel_is_a_named_failure \
  tools/test_v0_s3_native_custody_correction10.py::test_n10_r12_the_reader_publishes_its_wait_before_it_waits \
  tools/test_v0_s3_native_custody_correction10.py::test_n10_r13_the_fault_is_unlocked_by_the_owner_and_observed_first \
  tools/test_v0_s3_native_custody_correction10.py::test_n10_r14_the_closed_obligations_of_the_package_do_not_regress
```

Expected: 6 passed. These are the six nodes whose cleanup regions carry the
repairs of this correction: the controlled subcases and their final verdict,
the post-drain query of the registry of the zero expiry, the startup owners
and the interrupted start, the await of the endpoint, the round of R12 and the
salvage stops of R11, R13 and R14.

### 3 — the durable evidence of the group (≤ 20 s)

```sh
cd <PACK_ROOT> && python3 - <<'PY'
import json, pathlib
root = pathlib.Path('reports/v0-s3/product-gate0/'
                    'implementation-native-custody-correction-22/evidence')
names = ['n10-r07-zero-salvage.json', 'n10-r07-parent-salvage.json',
         'n10-r07-dispatch-cancel.json', 'n10-r07-dispatch-expire.json',
         'n10-r07-await-context.json', 'n10-r08-retry.json',
         'n10-r09-brokererror.json', 'n10-r09-keyboardinterrupt.json',
         'n10-r09-systemexit.json', 'n10-r09-await-wait.json',
         'n10-r09-interrupted-start.json', 'n10-r11-second.json',
         'n10-r12-stop.json', 'n10-r12-owner.json']
for name in names:
    path = root / name
    print(name, 'PRESENT' if path.exists() else 'MISSING')
    if not path.exists():
        continue
    doc = json.loads(path.read_text(encoding='utf-8'))
    print('   cleanup_errors=', doc.get('cleanup_errors'),
          'interrupts=', doc.get('interrupts'),
          'registry_errors=', doc.get('registry_errors'),
          'proof_failure=', doc.get('proof_failure'),
          'alive=', doc.get('worker_alive') or doc.get('owner_alive')
                   or doc.get('reader_alive') or doc.get('recovery_alive'))
PY
```

Expected: every name `PRESENT`; every document of a cleanup carries the
**actual** `cleanup_errors` and the **actual** `interrupts` of its region; the
document of the round of the zero expiry carries the **actual**
`registry_errors` next to its `registry` snapshot and its `proof_failure`; the
documents of the dispatch, of the await, of the retry, of the startup owners,
of the interrupted start and of the round of R12 carry the **actual** liveness
of their owner.

## What the run must produce and what it does **not** prove

The run produces the raw results, the events, the oracles, the negatives, the
returned states and the bounded cleanup evidence of the 189 nodes and of the
group of the counterexamples. It does **not** prove the native behaviour, the
native API, the product acceptance or the Stage gate: the native evidence
stays `NOT_PROVEN` until the independent review of the actual results and the
human acceptance.

**The run is the first real check of the risk that this correction takes.**
The candidate now fails a round when the stop of the round, the close of an
endpoint or of a channel, the join of an owner or the write of the evidence
raises an ordinary error. The repeated stop of the round is exercised by the
body of the tests of R11, R12, R13 and R14 **before** the salvage stop of the
`finally`, so the repeated path of the production is already known to return;
a failure of the run is a failure of the candidate and it is reported as it
is.

## Stop rules

* A `429` of the model or of the budget: **STOP**, write `WAIT_BUDGET`, end
  the turn; no retry, no switch of route, no takeover of the root.
* A refused or timed-out approval: **STOP**, no bypass and no edit of a
  configuration file.
* Any failure of a command: report it as it is, with the raw output; do not
  repair the candidate in this route and do not claim a partial PASS.
