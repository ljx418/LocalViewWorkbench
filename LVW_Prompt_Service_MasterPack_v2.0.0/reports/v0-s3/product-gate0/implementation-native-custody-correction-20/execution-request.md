# Correction 20 — finite execution REQUEST (not executed)

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
| Baseline delivery | `7bf0c53822b396be3ea2091bdd6d3e18df0bf7b4` |
| Baseline source candidate | `c3286cce2cc4e4e8f4bb25fde60fa8f998e2fdce` |
| Candidate of this correction | `tools/test_v0_s3_native_custody_correction10.py` (SHA256 `662f6a2a0b1af5dd5b2baad737c2b6fc82edcab755beac49c67848f6fff6102a`, see `pins.json`) |
| Denominator | 189 identifiers, unchanged (static AST proof) |
| Other sources | 6 sources byte identical (SHA256 pins in `pins.json`) |
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
correction 14 stays historical; this run is the **first dynamic** run of the
correction 20 candidate.

### 2 — the group of the counterexamples (≤ 40 s)

```sh
cd <PACK_ROOT> && python3 -m pytest -q -p no:cacheprovider \
  tools/test_v0_s3_native_custody_correction10.py::test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation \
  tools/test_v0_s3_native_custody_correction10.py::test_n10_r07_the_context_of_the_round_reaches_every_layer
```

Expected: 2 passed. These are the two nodes whose cleanup regions carry the
seven repairs of this correction.

### 3 — the durable evidence of the group (≤ 20 s)

```sh
cd <PACK_ROOT> && python3 - <<'PY'
import json, pathlib
root = pathlib.Path('reports/v0-s3/product-gate0/implementation-native-custody-correction-20/evidence')
names = ['n10-r10-final-summary.json', 'n10-r10-early-salvage.json',
         'n10-r10-coordination.json', 'n10-r10-timeout-confirmed.json',
         'n10-r10-timeout-failed.json', 'n10-r10-barrier-absent.json',
         'n10-r10-barrier-wrong-generation.json',
         'n10-r10-published-before-timeout.json']
for name in names:
    path = root / name
    print(name, 'PRESENT' if path.exists() else 'MISSING')
    if path.exists():
        doc = json.loads(path.read_text(encoding='utf-8'))
        print('   status=', doc.get('status'),
              'states=', len(doc.get('states', {})),
              'write_errors=', len(doc.get('write_errors', [])),
              'not_persisted=', doc.get('not_persisted'))
PY
```

Expected: every name `PRESENT`; the summary carries the 28 terminal states
of the inventory, an empty list of write errors and an empty list of names
that were not persisted.

## What the run must produce and what it does **not** prove

The run produces the raw results, the events, the oracles, the negatives, the
returned states and the bounded cleanup evidence of the 189 nodes and of the
group of the counterexamples. It does **not** prove the native behaviour, the
native API, the product acceptance or the Stage gate: the native evidence
stays `NOT_PROVEN` until the independent review of the actual results and the
human acceptance.

## Stop rules

* A `429` of the model or of the budget: **STOP**, write `WAIT_BUDGET`, end
  the turn; no retry, no switch of route, no takeover of the root.
* A refused or timed-out approval: **STOP**, no bypass and no edit of a
  configuration file.
* Any failure of a command: report it as it is, with the raw output; do not
  repair the candidate in this route and do not claim a partial PASS.
