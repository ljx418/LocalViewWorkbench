# S3-PREP-A correction-01 report — semantic guard fix for the actual old-S2 projection

**Decision: READY_FOR_REVIEW.**  This is not a Stage PASS, not product Gate0, not a
human signature, not a sample-quality claim and not a release.  The historical V0-S2
stage stays **7/8 with native human signoff PENDING**, and no new human
confirmation is requested: `CHANGE-V1-S2-HANDOFF-01` is already approved.

| item | value |
| --- | --- |
| blocker addressed | `S3P-A-MAJOR-01` (the only blocking finding of `S3P-A-INDEPENDENT-01`) |
| Codex adjudication | `reports/v0-s3/preparation-03/codex-review-resolution-01.json` → `CHANGES_REQUIRED_MAJOR01_NO_NEW_HUMAN_AUTHORIZATION` |
| Codex source commit loaded | `12a1594c12b57a62ce445e4cf7f11fd38423039d` (`docs: consolidate S3 guard correction and record independent-read process deviation`), merged into this child checkout as `137ce11549b4fe1b9006e5eaffaf21dbcb064c09` (0 conflicts) |
| previous code candidate | `d33893303f24da57216b63b4e0b9ef7e009d7613` |
| previous terminal candidate | `311bdda937373f1055a6677f02322fb347c31cd1` |
| **this code candidate** | `bc78869231e4dc320dfc9c7198a07aeabf9412fe` (`feat(S3-PREP-A): read the actual old-S2 projection in the handoff guard`) |
| branch | `ljx418/lvw-v1-d0-implement` (child worktree; **not** merged into `main`, **not** pushed) |
| scope | `HANDOFF_READINESS_ONLY` — the approved V1-only dependency predicate |

## 1. What was wrong

The guard compared only the **declared** old-S2 projection: the frozen predicate
snapshot `historical_s2_required_state` inside the three plan copies, the owner
approval record and the historical independent review.  It never read the live
authority `plans/execution-control.json`.

The independent reviewer showed the consequence: in a synthetic copy where **only**
`development_outline[V0-S2]` was changed to `completed_substeps = 8`,
`human_signoff = "APPROVED"` and the substep `S2 人工签署与Git同步` marked `DONE`,
the tool still answered `HANDOFF_READINESS_VERIFIED` with 0 failed checks out of
119 — while its own report asserted an old-S2 state of 7/8 that the document it
had just read contradicted.  The guard was not lax; it was pointed at the wrong
source of truth.

## 2. What changed (two files, both inside the allowed write set)

### 2.1 `tools/verify_s3_handoff.py` (SHA-256 `d2b3fd33…`)

A new function `check_actual_s2_projection()` reads
`plans/execution-control.json` — the **actual authority** — and asserts, with
fail-closed semantics, 20 new checks (`actual.*`):

| check | requirement |
| --- | --- |
| `actual.outline.container` | `development_outline` is a list |
| `actual.outline.v0_s2_occurrence` | **exactly one** entry with `stage_id == "V0-S2"` (missing *and* duplicate fail) |
| `actual.outline.completed_substeps` | integer, **non-bool**, equal to `7` |
| `actual.outline.total_substeps` | integer, **non-bool**, equal to `8` |
| `actual.outline.human_signoff` | `"PENDING"` |
| `actual.outline.substeps_container` / `.substep_count` | a list of **exactly 8** substeps |
| `actual.outline.substep_status_vocabulary` | only `DONE` / `PENDING` |
| `actual.outline.done_count` / `.pending_count` | exactly **7** `DONE`, exactly **1** `PENDING` |
| `actual.outline.done_substep_evidence` | every `DONE` substep carries non-empty evidence |
| `actual.outline.human_substep_present` | exactly **one** substep named `S2 人工签署与Git同步` |
| `actual.outline.human_substep_pending` | that substep is still `PENDING` |
| `actual.outline.human_substep_evidence_null` | its `evidence` is `null` |
| `actual.historical_s2_coordinate.container` / `.stage_id` / `.workpack_id` / `.gate` / `.state` / `.exact_keys` | the retained snapshot stays exactly `V0-S2` / `WP-S2-06` / `GATE5_HUMAN_EXPERIENCE_SIGNOFF` / `WAIT_HUMAN` |

Design constraints honoured:

* **The document is read and interpreted, never hash-frozen.**  `plans/execution-control.json`
  is not one of the 16 source-fence files and is not added to it; the live
  coordinate is not frozen.  No copied snapshot and no checksum stands in for
  the actual authority.
* **The live coordinate stays free.**  `coordinate`, `current_blocking_gate` and
  `updated_at` are not checked and keep the verdict green when they advance
  (asserted by a dedicated positive test).
* **The retained snapshot is not a second live coordinate.**  Only
  `historical_s2_coordinate` is enforced; it is the historical record of where
  old S2 stopped, per the Codex memo.
* **The public report never asserts 7/8 when the actual value differs.**  The
  report now carries `historical_s2_projection` (the **observed** live values,
  `null` when the stage entry is missing or malformed),
  `historical_s2_declared_expected_state` (the declared contract),
  `historical_s2_projection_source` and `historical_s2_coordinate_observed`, and
  the free-text note states 7/8 **only** when the observed values actually
  match.  In the refused run below, the report shows `8 / 8 / APPROVED` as the
  observed projection next to the declared `7 / 8 / PENDING`.

### 2.2 `tools/test_verify_s3_handoff.py` (SHA-256 `9a46fd77…`)

26 → **43** tests.  All 25 remaining obligations of the old file are preserved
unchanged; one oracle was explicitly re-decided by the owner (below, now four
parameterised cases) and 14 further cases were added — 43 = 25 preserved
+ 4 re-decided + 14 new.

**Old → new oracle mapping (no silent deletion):**

| old test | old oracle | new test | new oracle | why |
| --- | --- | --- | --- | --- |
| `test_the_historical_s2_coordinate_state_is_not_required_to_stay_wait_human` | *the retained historical snapshot may be rewritten* | `test_the_historical_s2_coordinate_snapshot_must_not_be_rewritten[stage_id\|workpack_id\|gate\|state]` | *rewriting the retained historical snapshot must be **refused*** | `historical_s2_coordinate` is a **retained snapshot**, not a second live coordinate; the owner re-decided the permissive oracle (Codex memo) |
| `test_execution_coordinates_may_advance` | *the live coordinate may advance* | **kept unchanged** | same | the live coordinate is deliberately unfrozen |

**New semantic regressions** (each mutates **only** the actual outline in a
synthetic copy; every frozen proof file, both other predicate snapshots and the
owner approval record stay byte-identical):

`test_actual_outline_completed_substeps_eight_is_rejected` ·
`test_actual_outline_human_signoff_approved_is_rejected` ·
`test_actual_outline_pending_human_substep_marked_done_is_rejected` ·
`test_actual_outline_human_substep_renamed_is_rejected` ·
`test_actual_outline_human_substep_missing_is_rejected` ·
`test_actual_outline_duplicate_human_substep_is_rejected` ·
`test_actual_outline_substep_count_not_eight_is_rejected` ·
`test_actual_outline_without_a_v0_s2_entry_is_rejected` ·
`test_actual_outline_with_a_duplicate_v0_s2_entry_is_rejected` ·
`test_actual_outline_with_malformed_stage_value_types_is_rejected` ·
`test_actual_outline_with_a_done_substep_without_evidence_is_rejected` ·
`test_public_cli_rejects_a_faked_actual_outline` (public CLI, exit 1)

**New positives:** `test_the_real_owner_actual_s2_projection_is_seven_of_eight_pending`
(unmodified real owner root) and
`test_the_live_coordinate_may_advance_while_the_historical_snapshot_is_retained`.

Every negative case asserts the refusal is **semantic**: the expected `actual.*`
identifier must have failed **and** no `fence.*`, `predicate.*`, `approval.*`,
`request.*`, `decision.*`, `evidence.*`, `map.*`, `packet.*` or `plans.*` check
may have failed (`assert_semantically_refused`).  A generic checksum refusal
therefore cannot satisfy the suite.  No new test compares a constant against
itself: the new assertions use literal values and the observed values.

## 3. Evidence — exact commands, exits, hashes

Recorded in `run_configuration.json`; raw logs in `logs/`; hashes in
`checks/SHA256SUMS.txt`.

| run | command | exit | result |
| --- | --- | --- | --- |
| `verify_s3_handoff` | `python3 -B tools/verify_s3_handoff.py` | **0** | `HANDOFF_READINESS_VERIFIED`, 139/139 checks, authority `AUTHORITATIVE` |
| `pytest_packet_tests` | `python3 -B -m pytest tools/test_verify_s3_handoff.py tools/test_s3_asset_inventory.py -q` | **0** | `65 passed` (43 + 22) |
| `pytest_owned_basetemp` | the same command **+ `--basetemp=<owned TemporaryDirectory parent>/pytest-basetemp`** | **0** | `65 passed`; owned parent verified gone after the context |
| `cli_negative_fake_outline` | `python3 -B tools/verify_s3_handoff.py --root <synthetic fake outline>` | **1** | `HANDOFF_READINESS_REJECTED`, 133 passed / 6 failed — **all six are `actual.*`**; no fence failure; the report shows observed `8/8/APPROVED` next to declared `7/8/PENDING` |
| `guard_revert_regression` | the new suite against the **pre-correction** guard (`137ce11`) | **1** | **18 failed, 25 passed** — every new/re-decided test fails without the fix |

The last row is the closure proof: the pre-correction guard's SHA-256 is
`5944771fd3fe880014bcbecd06b1ba1fbe76a58d2b560ec74d8a679de5adfe9d`, exactly the
`handoff_script_sha256` recorded in the preflight binding, so the regression run
uses the reviewed bytes.

**Machine-extracted counts.**  `65 passed` (43 handoff + 22 inventory), `0 failed`;
guard `139` checks / `0` failed on the real root; refused run `139` checks /
`133` passed / `6` failed; regression run `43` collected / `18` failed / `25` passed.

**Test isolation.**  Every pytest run used an owned
`tempfile.TemporaryDirectory` parent as the `--basetemp` root
(`PYTEST_DEBUG_TEMPROOT` was *not* used); the parent path, the argv and the
"parent gone after context" observation are recorded per run.  No shared or
pre-existing pytest root was purged.

## 4. Inventory reuse analysis (explicit)

The bounded inventory is **not** re-run and **not** re-bound.

* The terminal receipt
  `reports/v0-s3/preparation-03/implementation/inventory-01/receipt.json`
  keeps SHA-256 `05ab5d63a69556c721b26191273cf60c20e4b3bb5826712688cefb06786ee2ef`
  and stays bound to the **original** candidate `d33893303f24da57216b63b4e0b9ef7e009d7613`.
  It is **not** relabelled as a new candidate.
* `tools/s3_asset_inventory.py` (`333cfed9828fae22df524870fa691e553bcdb1965f30c1f5efb0b1882e3cbb30`)
  and `tools/test_s3_asset_inventory.py` are **byte-identical to `311bdda`**
  (`git diff 311bdda -- tools/s3_asset_inventory.py tools/test_s3_asset_inventory.py`
  is empty).  The hash algorithm, the input set and the actual S2 projection that
  was inventoried are unchanged.
* **The old preflight binding is now stale and is not re-sealed.**  It pins the
  pre-correction guard (`5944771f…`); the corrected guard hashes to `d2b3fd33…`,
  so the old inventory CLI would refuse that binding.  The inventory CLI was
  **not** run to force it through, and no owner file was re-sealed.
* **No new full inventory is authorised and none is needed**: the correction
  changes only the handoff guard; it does not change the inventory script, its
  test, its inputs, its output path or its counts.
* Known limits carried unchanged: `INVENTORY_COMPLETE` is bounded-operation
  completeness, not corpus completeness (512 of 698 supported files hashed,
  **186 unhashed**); the derived catalog holds **509** candidates / **498**
  distinct content hashes and **excludes 3 private-labelled paths**; the
  reviewer's 3-pass/preflight deviation stays recorded and is not treated as a
  fully compliant independent read (see `errata.md` E-1, E-6, E-7).

## 5. Changed files

| file | change |
| --- | --- |
| `tools/verify_s3_handoff.py` | modified — the actual old-S2 projection is read and asserted; the report separates observed from declared |
| `tools/test_verify_s3_handoff.py` | modified — one oracle re-decided, 18 semantic cases added |
| `reports/v0-s3/preparation-03/implementation/correction-01/**` | added — this report, the append receipt, the errata, the candidate record, the raw logs, the run configuration and their hashes |

Nothing else was edited: no owner document, plan, contract, packet, approval,
proof, old receipt, the inventory script, the inventory test, the parent
worktree.  The only other commit in this branch is the source load of
`12a1594` (`137ce11`), which carries Codex's own documents and the Codex
update of `plans/execution-control.json`; no owner file was rewritten by hand.

## 6. What remains open

* The root commissions a **bounded Major-closure recheck** next; this worker
  does not claim the Major is closed by its own tests.
* The reviewer's helper correction (fail-closed preflight before any source
  access) is **separately owned by root** and untouched here.
* The independent review's hash-process deviation stays open (E-7).
* `S3P-A-MINOR-01..07` stay non-blocking; no code fix or inventory
  label/format change was made for them, per the adjudication.
* Product Gate0, the S3 quality set, the V1 Q01 set, the MS sets, packaging,
  the execution adapter, the finite production budget and every later human
  signature remain open product items — untouched by this correction.
