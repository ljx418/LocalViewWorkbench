# S3-PREP-A — Independent hash review: process correction and accounting correction 01

**Kind:** append-only reviewer record (reviewer-owned test harness, not the application candidate)
**Author:** the Orca-visible reviewer who authored the `independent-01` hash helper
**Root authority read:** `reports/v0-s3/preparation-03/independent-hash-process-deviation-01.json`
(commit `12a1594c12b57a62ce445e4cf7f11fd38423039d`), `codex-review-resolution-01.json`,
`candidate-catalog-filtered-01.json`
**Scope of writes:** `reports/v0-s3/preparation-03/independent-process-correction-01/` only
**Self-signature:** none. This document does **not** claim a Stage PASS, a Gate 0 pass, a
product acceptance, or a fully compliant independent hash recheck. The root Codex reviewer
inspects the helper and the test proof independently.

---

## 1. What this record is (and is not)

This is a **process correction** of the reviewer-owned helper that performed the finite
independent SHA-256 recheck under `reports/v0-s3/preparation-03/independent-hash-child-01.json`.
It records the true accounting of that recheck, corrects two inaccurate sentences in the
earlier independent report, and ships a corrected helper plus a bounded synthetic test proof.

It is **not**:

* a product-candidate implementation, review or approval;
* a re-run of the independent hash recheck — **no real media was read, stat'ed, opened,
  hashed or listed by this work**;
* a retroactive grant of the consumed real hash child. That child's terminal is expired and
  stays expired;
* a replacement for the implementation-side `S3P-A-MAJOR-01` guard fix, which is assigned to
  the implementer in a separate task. No file under `tools/` was touched by this work.

---

## 2. The process deviation, stated plainly

The independent hash recheck was executed **three times** over the same three approved source
files. Only the third pass had a valid preflight. The first two passes read the source files
anyway, because in the original helper the preflight verdict was a *report field*, not a
control-flow gate.

### 2.1 Per-pass facts (from the three retained result JSONs)

| pass | result file | `preflight_validated_before_source_access` | files hashed | bytes read | chunks | elapsed | decision string |
|---|---|---|---|---|---|---|---|
| 1 | `independent-01/hash-recheck/attempt1-hash-mismatch.json` | **false** | 3 | 11 009 275 | 15 | 0.627 s | `INDEPENDENT_HASH_RECHECK_VERIFIED` |
| 2 | `independent-01/hash-recheck/attempt2-hash-mismatch.json` | **false** | 3 | 11 009 275 | 15 | 0.473 s | `INDEPENDENT_HASH_RECHECK_VERIFIED` |
| 3 | `independent-01/hash-recheck/hash-recheck-final.json` | true | 3 | 11 009 275 | 15 | 0.582 s | `INDEPENDENT_HASH_RECHECK_VERIFIED` |

Passes 1 and 2 are the ones the file names call "hash-mismatch": in both, the *metadata*
checks failed (pass 1: the git blob comparison was made with a repository path that lacked
the `LVW_Prompt_Service_MasterPack_v2.0.0/` package prefix and the child worktree blob did
not match; pass 2: the worktree blob lookup returned an empty string). Both passes then read
11 009 275 bytes of real media anyway.

### 2.2 Aggregate (the numbers that matter)

| quantity | value | allowed | met |
|---|---|---|---|
| source read passes | **3** | 1 | **no** |
| file-read operations | **9** | 3 (3 files × 1 pass) | **no** |
| unique approved source files | 3 | 3 | yes |
| bytes read from source | **33 027 825** | 33 554 432 | yes |
| wall seconds | 1.682 | 60 | yes |
| preflight validated **before** each source access | 1 of 3 passes | all passes | **no** |

Per-file byte split (identical in all three passes): `动作参考-原始.mp4` 6 957 440 +
`图片-1 (1).jpeg` 423 206 + `参考.png` 3 628 629 = 11 009 275 bytes.

### 2.3 What was *not* exceeded

The approved root was **not** widened: only the three files already declared by the child
authority under `/mnt/c/workSpace/videoWorkLine/testSource` were read, and no directory walk,
listing, decode, EXIF probe, provider/model call, network access, service start, browser
action, product-database access, download, push or write to any original occurred. The
aggregate byte cap was respected. The original implementation's 512-file inventory is a
separate, unaffected artifact (`05ab5d63a69556c721b26191273cf60c20e4b3bb5826712688cefb06786ee2ef`).

### 2.4 Root cause in the original helper

`reports/v0-s3/preparation-03/independent-01/hash-recheck/hash-child-recheck.py`:

* line 99 computes `preflight_ok`, and line 192 only *reports* it as
  `preflight_validated_before_source_access`. The source loop at line 114 is **not** gated on
  it: a false preflight still reads every selected file.
* lines 60–63 run every git command with `check=False` and only take `stdout.strip()`. A
  failed `git rev-parse` prints the *argument* back on stdout (for example
  `d338933:tools/verify_s3_handoff.py`), so the echoed argument was compared as if it were an
  object id, and a non-zero git exit code was invisible.
* the git paths were not consistently repository-relative with the
  `LVW_Prompt_Service_MasterPack_v2.0.0/` prefix, which is why the code-binding comparison
  produced `"candidate_blob": "d338933...:tools/verify_s3_handoff.py"` in pass 1 and an empty
  `"checkout_blob": ""` in pass 2.

The three result JSONs are retained exactly as they were. **No failure was rewritten or
hidden**, and the last positive pass is **not** used to claim a single compliant recheck.

---

## 3. The corrected helper

`helper/hash_child_recheck_correction.py` (reviewer-owned harness copy; the file name uses
underscores so that the test suite can import it — the original used dashes).

What changed, in the order of the requirement list:

1. **No real root by default.** The helper has *no* default source root. It refuses any root
   inside `/mnt/c/workSpace/videoWorkLine` (the production media tree), refuses any root that
   is not inside a caller-supplied `--allow-source-root` allow-list, and refuses any root that
   does not carry the `.lvw-synthetic-fixture-root` marker file. The guard is lexical: it never
   stats or opens the production paths, so the guard itself cannot read real media.
2. **Correct repository-relative git prefix.** Every path handed to git is composed as
   `LVW_Prompt_Service_MasterPack_v2.0.0/` + package-relative path, and the composition is
   asserted before use.
3. **Actual git return code.** `run_git()` returns `(returncode, stdout, stderr)`; a git call
   is accepted only on exit code 0 **and** a syntactically valid object id (40/64 hex). A
   failed `git rev-parse` can no longer be mistaken for evidence.
4. **All preflight checks before any source access.** The preflight verifies: the declared
   package prefix; the child file's sha256 against an out-of-band anchor; the child file's
   git blob at the anchored commit against the worktree blob; that both candidate ids are
   existing **commit** objects that resolve to themselves; that every declared code file's
   blob at the implementation candidate is byte identical to the worktree blob; and that the
   inventory receipt's sha256 matches the child's declaration. Only if **all** of them pass is
   the source phase entered.
5. **Fail closed is control flow.** On any preflight failure the helper returns immediately
   with a stable `REJECTED` decision and a non-zero exit code; the source phase is
   unreachable. The report carries `source_phase_entered: false` and all counters at zero.
   A `VERIFIED` decision requires a passed preflight **and** a fully verified source set —
   hash equality alone can never produce `VERIFIED`.
6. **No broad exception success.** Unexpected exceptions are reported as
   `S3_PREP_INDEPENDENT_HASH_RECHECK_REJECTED_INTERNAL_ERROR` with exit code 4. No `except`
   clause converts a failure into a pass.
7. **Full budget, identity and escape checks on synthetic data only.** File-count, byte and
   wall-clock budgets are enforced during reading; a size or digest change is reported as
   `SOURCE_CHANGED_NOT_VERIFIED`; a symlink or a path resolving outside the root is reported
   as `*_ESCAPE_REJECTED_NOT_VERIFIED` before any byte is read.
8. **No new product service and no permanent configuration.** The helper is a single file
   next to this document; it reads no configuration file, starts no service and writes only
   the JSON result path given on the command line.

Exit codes: `0` verified, `2` rejected (preflight / source), `3` guard rejection, `4`
internal error, `5` usage error.

---

## 4. Test proof (synthetic only)

`tests/test_hash_child_recheck_correction.py`, 24 tests, all passing. Every fixture is
synthetic: three small files written by the test inside the pytest basetemp, and a throw-away
git repository created by the test. The expected digests come from an **independent oracle**
(`hashlib` over the whole file, cross-checked against the external `sha256sum` binary), not
from the helper's chunked reader.

The failure modes that the historical run actually hit are reproduced:

| test | reproduced condition | asserted outcome |
|---|---|---|
| `test_wrong_git_prefix_is_rejected_with_zero_source_access` | git path loses the package prefix | rejected, **zero** adapter calls |
| `test_git_layer_rejects_a_prefix_less_path` | `git rev-parse <commit>:tools/alpha.py` | git layer raises, fail closed |
| `test_nonzero_git_exit_is_rejected_with_zero_source_access` | anchor commit does not exist | rejected, **zero** adapter calls |
| `test_missing_repository_is_rejected_with_zero_source_access` | `git -C` on a non-repository | rejected, **zero** adapter calls |
| `test_mismatched_child_sha256_is_rejected_with_zero_source_access` | child digest anchor mismatch | rejected, **zero** adapter calls |
| `test_mismatched_child_git_blob_is_rejected_with_zero_source_access` | child blob ≠ anchored commit blob | rejected, **zero** adapter calls |
| `test_code_binding_mismatch_is_rejected_with_zero_source_access` | code file drifts from the bound commit | rejected, **zero** adapter calls |
| `test_inventory_receipt_sha_mismatch_is_rejected_with_zero_source_access` | receipt sha256 mismatch | rejected, **zero** adapter calls |
| `test_hashes_alone_never_produce_a_verified_decision` | source hashes still correct, metadata drifts | **not** `VERIFIED`, zero opens |
| `test_preflight_verdict_is_control_flow_not_only_a_report_field` | false preflight | `source_phase_entered: false`, `bytes_read: 0`, no adapter call at all |
| `test_production_real_root_is_hard_disabled` | child points at the production root | guard rejection (exit 3), zero adapter calls |
| `test_production_root_child_is_refused_without_any_allow_list` | no allow-list supplied | guard rejection, zero adapter calls |
| `test_source_root_without_the_fixture_marker_is_refused` | fixture marker removed | guard rejection, zero adapter calls |
| `test_cli_without_an_allow_list_refuses_to_run` | CLI without `--allow-source-root` | exit 3 |
| `test_symlink_escape_is_rejected_and_the_outside_file_is_not_read` | symlink out of the root | escape rejected, outside file never opened |
| `test_changed_identity_is_not_verified` | file content changed under the same size | `SOURCE_CHANGED_NOT_VERIFIED`, not verified |
| `test_byte_budget_exhaustion_is_rejected` | byte budget too small | `BUDGET_EXCEEDED`, not verified |
| `test_wall_budget_exhaustion_is_rejected` | wall budget exhausted | `BUDGET_EXCEEDED`, not verified |
| `test_file_count_limit_is_enforced` | file count above the limit | rejected before any source access |
| `test_missing_selected_file_is_not_verified` | selected file absent | `MISSING_NOT_VERIFIED`, not verified |
| `test_every_preflight_failure_mode_keeps_the_source_phase_untouched` | all preflight modes | source phase untouched in each |

Positives: `test_positive_run_verifies_small_files_against_independent_oracle`,
`test_positive_cli_exit_code_is_zero_and_matches_external_oracle`,
`test_code_binding_uses_the_package_prefix_in_every_git_path` — these verify the three
synthetic files against the independent oracle, assert exit code 0 and assert that every git
path carries the package prefix.

"Zero real-media-adapter calls" is proven by a spy adapter that records every source-side
`resolve` / `stat` / `open_read`; a rejected run records **no** call at all, and the run
counters in the result payload agree with the spy.

### 4.1 Raw evidence (this directory)

| file | content |
|---|---|
| `raw/test-run-summary.json` | the exact pytest command line, exit code, elapsed seconds, basetemp and parent paths, and the post-exit existence check |
| `raw/pytest.stdout.log`, `raw/pytest.stderr.log`, `raw/pytest.exit.log`, `raw/pytest.time` | the raw pytest run |
| `raw/helper-runs.json` | three helper CLI runs with their exact commands, exit codes, stdout/stderr, decisions, counters and payload digests |
| `raw/helper-run-*.stdout.log`, `*.stderr.log`, `*.exit.log` | the raw helper CLI runs |

The three captured helper runs (synthetic fixtures):

* `positive` → exit **0**, `S3_PREP_INDEPENDENT_HASH_RECHECK_VERIFIED`, 3 opens, 1 562 bytes
  read, every digest equal to the independent oracle;
* `metadata-drift` → exit **2**, `..._REJECTED_PREFLIGHT`, `source_phase_entered: false`,
  `adapter_open_calls: 0`, rejection reason
  `code_files_byte_identical_to_candidate: ...`;
* `production-root` → exit **3**, `..._REJECTED_GUARD`, `source_phase_entered: false`,
  `adapter_open_calls: 0`.

### 4.2 Cleanup record (declared vs measured)

The test run used an owned `tempfile.TemporaryDirectory` parent
(`/tmp/lvw-process-correction-*/`) with `pytest --basetemp` pointing **inside** it. The
runner records `parent_exists_during_run: true` and, after the context exited,
`parent_exists_after_exit: false` — i.e. the owned parent was measured gone.

**No pre-existing or shared pytest root was deleted or modified by this work.** The shared
root `/tmp/pytest-of-administrator/` still holds `pytest-53`, `pytest-54`, `pytest-55` from
other sessions; this run created nothing there (no directory under it carries any of this
suite's test names) and nothing there was removed.

---

## 5. Corrections to earlier wording (append-only)

The original records stay as they are. This section states the corrected facts; it does not
edit `independent-01/`, the implementation receipts or any authority file.

### 5.1 "The private-labelled files were never opened" — corrected

`independent-01/findings.json` (S3P-A-MINOR-07) and `independent-01/review.md` §S3P-A-MINOR-07
state, for the three inventoried items under `私人图片-单人多视角图`, that *"the file content
was never opened, decoded, viewed or copied into Git"*, and the helper's own note says
*"the 11 protected human holdouts and the obvious private-labelled paths were not touched"*.

**Corrected fact:** hashing necessarily *opened and read the bytes* of those files. The
original 512-file inventory hashed them and their SHA-256 digests are recorded in
`implementation/inventory-01/receipt.json`:

| relative path | sha256 | bytes |
|---|---|---|
| `私人图片-单人多视角图/1.png` | `5d58f178b7c8342cf851dec864c501c5229ad08535a6a8c5fcbf188364f6cce0` | 1 944 675 |
| `私人图片-单人多视角图/2.png` | `7417497ac6630774152928df78104911ce118f182df2239ae57342a86877bf99` | 1 659 434 |
| `私人图片-单人多视角图/3.png` | `e0baf52a79b93813a2454e3efbb3d3846bcc91a485ee98a55a9b52262944619e` | 2 115 347 |

What did **not** happen, and remains true: no decode, no EXIF read, no serialized image, no
visual view, no upload, no provider/model call, no raw media copied into Git, and no
prelabelling or inference derived from them. The exposure was metadata plus a byte-level
digest, not content handling.

**Mitigation already in force:** `candidate-catalog-filtered-01.json` excludes exactly those
three file ids
(`1ef610c07b13a928609748cd74e7be6d21b98cf4e62a35868633214007b7f81a`,
`281d0f20f76a79ef952bc506b567313c857d5111126eff099dcaa422cb33694b`,
`68a1713e958b7441ce9f106e807fd3630e5e4ccb1b756baccd732ce9286c0dfc`)
from *all* future inference, prelabelling, sample proposal and derived frames until the
classification is affirmatively resolved. The 3-file hash recheck itself covered three
**other**, non-excluded files (`动作参考-原始.mp4`, `图片-1 (1).jpeg`, `参考.png`).

The claim about the **11 protected human holdouts** is *not* corrected: their digests were
compared against the 512 hashed files and the overlap is 0, so no holdout media was read by
the inventory or by the recheck.

### 5.2 "Cleanup counters are zero" — qualified as declared, not measured

`implementation/inventory-01/receipt.json` `cleanup` reports
`source_files_modified: 0`, `source_files_deleted: 0`, `temporary_directories_created: 0`,
`deletions_performed: 0`, and `implementation/terminal-report-01.md` §3 adds *"Only the test
suite's own `TemporaryDirectory` fixtures were cleaned, by `pytest`'s own teardown."*

**Corrected fact:** those four counters are **code-contract declarations, not measurements** —
the inventory is read-only by construction and creates no temporary directory at all, so the
zeroes restate the contract rather than evidence a measurement. The trailing sentence is
also inaccurate in two ways: the tests use pytest's `tmp_path` fixture (not
`tempfile.TemporaryDirectory`), and pytest **retains** `tmp_path` directories (default
`tmp_path_retention_count = 3`) rather than deleting them. The old fixtures were therefore
**not** deleted, and this record does not claim that they were. This correction run instead
uses an owned `TemporaryDirectory` parent with an explicit `--basetemp` and *measures* the
parent's absence after exit (`parent_exists_after_exit: false`), and deletes nothing outside
the directory it created itself.

---

## 6. Limits of this correction

* No real media was read, stat'ed, opened, hashed, listed or decoded by this work; no
  provider, model, GPU, service, browser, product database, download or push was used.
* No original record was edited, and no failure was rewritten: the three retained result
  JSONs, the deviation record and the original helper are untouched.
* The consumed real hash child is **not** reused or renewed; the corrected helper only ever
  runs against synthetic fixture roots.
* The corrected helper is reviewer-owned test harness. It is not the application candidate,
  it is not self-signed, and it is not product acceptance.
* The implementation-side `S3P-A-MAJOR-01` guard fix is assigned to the implementer
  separately; this work does not touch `tools/` and does not review or approve any corrected
  application candidate.
* The 512-file implementation inventory, its receipt and its terminal report are separate
  artifacts and are unaffected by this record.
* The corrected helper and its tests are evidence for the root reviewer to inspect
  independently; the root may reject or require changes to them.

---

## 7. File manifest (this directory)

| path | purpose |
|---|---|
| `accounting-correction.md` | this document |
| `receipt.json` | machine-readable receipt (counts, commands, exits, digests, limits) |
| `helper/hash_child_recheck_correction.py` | the corrected, fixture-only helper |
| `helper/fixture-child.template.json` | the shape of a synthetic child authority |
| `tests/conftest.py`, `tests/test_hash_child_recheck_correction.py` | the bounded synthetic test suite |
| `run_tests.py` | the owned-`TemporaryDirectory` test runner that writes `raw/` |
| `capture_helper_runs.py` | the raw CLI capture of the three helper runs |
| `raw/*` | raw logs, exit codes, command lines and digests |
