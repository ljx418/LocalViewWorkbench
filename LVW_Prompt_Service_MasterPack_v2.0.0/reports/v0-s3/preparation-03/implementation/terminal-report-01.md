# S3-PREP-A terminal report — V1-only handoff validator + bounded local asset inventory

**Decision: READY_FOR_REVIEW.** This is not a Stage PASS, not product Gate0, not a
sample quality claim and not a release. The historical V0-S2 stage stays **7/8 with
native human signoff PENDING**.

| item | value |
| --- | --- |
| Codex authority loaded | `4f216700c917e20704b5edc90fa33de497441368` (`docs: apply approved V1 S2 handoff and freeze bounded S3 preparation`), merged by clean fast-forward into this child checkout |
| stage / workpack | `V0-S3` / `S3-PREP-A` (`GATE0_PREPARATION_ONLY`) |
| scope approval | `CHANGE-V1-S2-HANDOFF-01`, approval SHA-256 `bab47506d5a13657edcabc33644c6b159f2967e696dff4c4c43859d54fbf3057` |
| predicate | `S3-V1-ONLY-S2-HANDOFF-01` — consumer `V0-S3`, dependency `V0-S2`, purpose `V1_DEVELOPMENT_ONLY` |
| code candidate | `d33893303f24da57216b63b4e0b9ef7e009d7613` |
| pre-inventory pre-receipt commit | `77592cc0c2eea41aae515063d1ec181c73159273` |
| branch | `ljx418/lvw-v1-d0-implement` (child worktree, not merged into `main`, not pushed) |

## 1. What was built

Four files, all inside the allowed write set of the frozen V0-S3 packet:

- `tools/verify_s3_handoff.py` — the approved V1-only handoff validator (public CLI).
- `tools/test_verify_s3_handoff.py` — 26 tests.
- `tools/s3_asset_inventory.py` — the bounded authorised local asset inventory (public CLI).
- `tools/test_s3_asset_inventory.py` — 22 tests.

No product source, contract, plan, packet, old evidence or parent worktree file was
edited. `MANIFEST.sha256` was **not** updated: it is outside this workpack's allowed
write set, so the four new tool files are not listed there.

### 1.1 `verify_s3_handoff` — what it decides

119 checks, all passing against the real repository tree. It verifies:

- the packet fence: the 16 source-fence hashes of
  `.agent-governance/stages/V0-S3/spec-manifest.json` and the 10 packet payload hashes of
  `PAYLOAD_MANIFEST.sha256`, with the payload manifest's own SHA-256
  `d167feb76e99dc3d9abcaa9892db6754e19e765a27c967ca8d012629a6e77a78`;
- the predicate is present **once** in `plans/tasks.json`
  (`dependency_gate_overrides`), in `plans/v1-revised-plan.json`
  (`v1_only_s2_handoff`) and in `plans/execution-control.json`
  (`v1_only_s2_handoff`), and that the three snapshots are **equal**;
- the only eligible edge is consumer `V0-S3` / dependency `V0-S2` / purpose
  `V1_DEVELOPMENT_ONLY`; a different purpose, consumer, dependency, an extra
  dependency-gate alias or a different predicate id is rejected;
- the actual owner approval record is `APPROVED`, carries id `CHANGE-V1-S2-HANDOFF-01`
  and binds the exact approved request (`8a603201…`), and the immutable original
  request is still the one that was approved;
- the old S2 machine evidence is candidate `719c745…` with exactly the nine required
  case ids `V0-A01..V0-A05, V0-A07..V0-A10`, every one `PASS`, `9 PASS / 0 others`,
  and the independent review is `9/9` with `Fatal=0, Major=0` and **no** human signoff;
- the current unified-media slice is signed by the project owner for candidate
  `621b1bf…` (`APPROVED`, slice `UNIFIED_MEDIA_EARLY`) and its independent coverage
  holds exactly `UM-01..UM-10`, all `PASS`;
- the frozen capability mapping keeps every retained duty: new S3 cases
  `V0-A06 / V0-A11 / V0-A12` and the cumulative twelve `V0-A01..V0-A12`, with
  `quality_coverage_inherited=false`, `historical_s2_signed=false`,
  `product_gate0=false`;
- the historical S2 projection is **7/8, native human PENDING** everywhere it is
  stated — the predicate snapshot and the approval record. A synthetic 8/8 or a
  `historical_s2_native_human_approved=true` record is rejected.

What it deliberately does **not** freeze: the mutable execution coordinates of
`plans/execution-control.json`. Advancing `coordinate`, `current_blocking_gate`,
`updated_at` or `historical_s2_coordinate.state` keeps the verdict
`HANDOFF_READINESS_VERIFIED` — this is asserted by two dedicated tests. Only the
immutable proof snapshot of the predicate is compared.

The report always states `scope=HANDOFF_READINESS_ONLY`, `product_gate0=false`,
`stage_pass_claim=false`, `product_execution_authorized=false`,
`authorizes_model_execution=false`.

### 1.2 `s3_asset_inventory` — what it decides

The public CLI is exactly the frozen packet command:

```
python3 -B tools/s3_asset_inventory.py \
  --binding reports/v0-s3/preparation-03/implementation/inventory-01/preflight.json \
  --receipt reports/v0-s3/preparation-03/implementation/inventory-01/receipt.json
```

Order of operations, enforced by the code and by the tests:

1. the preflight binding must carry `candidate_sha`, `inventory_script_sha256`,
   `handoff_script_sha256`, `inventory_child_sha256`, `scope_approval_sha256` and
   `frozen_proof_hashes`; the two script hashes, the child hash and the approval hash
   are compared against the **actual files on disk**, and the frozen proof hashes
   against the pinned owner proofs;
2. the **real** handoff guard (`tools/verify_s3_handoff.py`) runs — any refusal
   happens before a single byte of source media is stat'ed or read;
3. only then the child authorisation is read, the single approved root is resolved
   from it (no CLI root, no arbitrary root), and the bounded walk runs;
4. the terminal receipt is written once. An existing receipt is never overwritten and
   a receipt outside the tool's own report root is refused.

The inventory launches **no** subprocess (git identity is captured by the preflight
outside it), performs **no** media decode, **no** EXIF read and **no** visual
analysis, and only ever records `stat` + SHA-256 + relative path + extension.

Budgets, taken from the child authorisation and re-checked against the frozen
values: 8192 directory entries, 2048 regular files examined, 512 files hashed,
8 GiB total bytes, 512 MiB single file, 1 MiB read chunk, 180 s wall clock — and the
wall clock is checked **inside** the hashing loop, not only between files.

## 2. Required commands actually run (raw logs retained)

Raw stdout, stderr and exit code of every command are in
`reports/v0-s3/preparation-03/implementation/checks/` with a `SHA256SUMS.txt`.
The exit codes below are copied from the retained `*.exit.log` files, not
retyped.

| command | exit | wall / user / sys (s) | raw stdout SHA-256 |
| --- | --- | --- | --- |
| `python3 -B tools/verify_s3_handoff.py` | 0 | 0.05 / 0.02 / 0.02 | `12b1f73df49bca00c2c1c018851c252a23c2db3976c13a0e3a676c3d17a503df` |
| `python3 -B -m pytest tools/test_verify_s3_handoff.py tools/test_s3_asset_inventory.py -q` | 0 | 0.72 / 0.53 / 0.16 | `1c18971ff9bc4fa892b33e4f04881b376337d497e6aea7e9f02f23eec125a835` |
| `python3 -B tools/verify_governance.py` (governance verification) | 0 | 0.06 / 0.03 / 0.02 | `e8927ccbca17c63e6ca696c254e5e232add8617ec564f840df4907579089d7cf` |
| `python3 -B tools/verify_pack.py` (document/contract verification) | 0 | 0.47 / 0.32 / 0.14 | `0371f30cb93e716494e6b74eaad7b72b54e728d9a75e7bae570480e75a4073a5` |

Raw pytest stdout: `48 passed in 0.36s`. Raw checker stdout:
`HANDOFF_READINESS_VERIFIED`, `{"checks": 119, "passed": 119, "failed": 0}`,
`authority=AUTHORITATIVE`, `scope=HANDOFF_READINESS_ONLY`, `product_gate0=false`.
Governance verification reports `errors: [] / failed: 0`; pack verification reports
`passed 7717 / failed 0`. Neither is product acceptance.

The 48 tests drive the public entry points and the owner path, not constant
mirroring. They include: the complete positive owner proof against the real
repository; a synthetic copy that must verify and must be labelled non-authority;
wrong purpose / consumer / dependency / alias; a second generic alias entry; a
predicate that differs between the three plans; a shrunk case list; a fake old 8/8
signature; an approval that claims an old S2 signature; an approval that does not
bind the exact request; a missing capability map; a wrong machine candidate; a
non-`PASS` machine case; a missing UM case; malformed JSON in a plan; a malformed
payload manifest; a missing approval; a tampered fence file; and the two
"must not freeze" cases above. The inventory tests cover the exact-and-one-over
boundaries of the file-count, total-byte and single-file budgets, the directory
entry budget, the wall budget tripping **inside** hashing, the declared chunk size
(read sizes are observed on the real file object), a symlink escaping the approved
root, a file changed between the before- and after-stat, a missing root, a rejected
guard, a malformed proof, a missing / wrong / malformed binding, a terminal receipt
that is never overwritten, a receipt outside the report root, source immutability,
and the CLI exposing **only** `--binding` and `--receipt`.

## 3. The single bounded inventory run

One invocation only, executed after the code candidate and the pre-receipt were
committed and bound. Raw logs: `reports/v0-s3/preparation-03/implementation/inventory-01/`.

| item | value |
| --- | --- |
| exit code | 0 |
| decision | `INVENTORY_COMPLETE` |
| authority | `AUTHORITATIVE` |
| guard verdict | `HANDOFF_READINESS_VERIFIED` (119/119 checks, 0 failed) |
| elapsed (measured inside the tool) | **6.498 s** wall |
| CPU cost | hashing 1 049 735 799 bytes; no model, provider, GPU, network, download, service, browser or decoder |
| entries examined | 1006 |
| regular files examined | 888 |
| files hashed | 512 (the frozen cap) |
| bytes hashed | 1 049 735 799 (≈1.05 GB) |
| eligible | **512** |
| skipped | **376** — 190 `unsupported_extension`, 186 `hash_budget_exhausted` |
| traversal stop reason | none |
| receipt SHA-256 | `05ab5d63a69556c721b26191273cf60c20e4b3bb5826712688cefb06786ee2ef` |

Eligible set by extension: `.jpg` 325, `.png` 115, `.mp4` 68, `.jpeg` 2, `.webp` 2.
Sizes: smallest 409 B, median ≈ 120 KB, largest ≈ 144 MB. Every entry carries a
stable content-and-path addressed `file_id`, its SHA-256, its byte count, and
`origin=unknown`, `rights=unknown`, `labels=unknown`.

Cleanup: `source_files_modified=0`, `source_files_deleted=0`,
`deletions_performed=0`, `temporary_directories_created=0`. The source tree is
untouched; the inventory deletes nothing at all. Only the test suite's own
`TemporaryDirectory` fixtures were cleaned, by `pytest`'s own teardown.

Duplicate content: 512 eligible items carry **501 distinct SHA-256 values** — 11
content groups cover 22 items (for example the same asset stored both at the root
and inside an `edit/…/assets/` tree). Any later sample selection must deduplicate
by SHA, not by path.

### 3.1 Protected human holdouts

The 11 protected human holdout hashes were compared by hash only
(`人工验收视频集/FREEZE.json`, SHA-256
`3a8313c6e44dbf22dfbe8abd84f24a42ff15539ec4d19da13ac9d68b5419288c`).
**No overlap** was found with the 512 hashed files. No holdout media was read and
no holdout was fed to any model. The comparison covers only the hashed subset; for
the 186 files that were skipped by the hash budget, overlap stays **unknown**.

### 3.2 Disclosure

During preparation planning a single read-only directory listing of the approved
root was run to confirm the root exists (`ls -la`). It returned names, sizes and
timestamps only; no media byte was read, decoded or hashed outside the bounded
inventory, and no file was opened for content. No other local root was listed.

## 4. Genuine gaps that remain open (not resolved by this preparation)

1. **Partial root coverage.** The child authorises at most 512 hashed files. The
   approved root contains 698 files with a supported extension; 186 of them were
   therefore *not* hashed and their content, size and holdout overlap are unknown.
   A further pass needs a new child authorisation; this workpack authorises exactly
   one attempt, and a partial run is a retained terminal receipt, not a retry.
2. **No independent prelabels.** S3 needs `V0-A11` (independent 10 images, ≥ 8
   usable, 0 critical hallucination) and `V0-A12` (independent 6 videos, ≥ 5 usable,
   0 critical hallucination). The inventory produces *candidates only*; it selects
   nothing, labels nothing and freezes nothing, and an inventory entry is never a
   quality `PASS`.
3. **V1 Q01** needs an independent 12 images + 6 videos set with unchanged
   thresholds — not started, and not blocked by anything this preparation did.
4. **MS** needs 12 clips / 47 shots / 21 hard cuts and 18 pre-selected quality
   segments with independent prelabels — not started; the inventory performs no
   shot or hard-cut segmentation and produces no labels.
5. **Disjointness is unproven.** Overlap with the 11 human holdouts is proven absent
   only for the 512 hashed files. Disjointness against the future development set,
   the Q01 set and the MS sets is entirely unproven.
6. **Rights and origin are unknown for every file.** The child authorisation grants
   user-supplied, non-private *local test use*; that is **not** a redistribution
   licence, and origin metadata was deliberately not read.
7. **`V0-A06`** (reversible install / offline cold start / rollback with old workflow
   preservation) and the packaging contract, the exact model/tool/process config
   binding, the execution adapter and the concrete finite production budget remain
   open — they are product Gate0 items outside this preparation.
8. **A directory named `私人图片-单人多视角图`** in the approved root contributed 3
   inventoried items. The owner of that root classified the material as non-private
   test input, but the inventory cannot verify that classification; the relative
   path names are retained in the receipt because the receipt is the auditable
   artefact.

## 5. Budget accounting

| counter | value |
| --- | --- |
| model actions | 0 |
| effective full checkpoints | 0 |
| product runtime | 0 s |
| service starts | 0 |
| network / downloads | 0 |
| GPU | 0 |
| subprocesses started by the inventory | 0 |
| global counter reset | none |
| CPU duration (measured separately) | 0.05 s checker + 0.72 s pytest + 0.06 s governance + 0.47 s pack + 6.498 s inventory wall |

## 6. Statement

The approved V1-only dependency predicate is verified against the exact owner
approval and the exact frozen proof hashes, and the bounded local inventory of the
single approved root completed once and is retained as a terminal receipt. The
historical V0-S2 stage is unchanged at 7/8 with native human signoff PENDING. No
quality set was selected, tuned or frozen, no model was run, no Stage PASS and no
product Gate0 is claimed.

**READY_FOR_REVIEW** — an independent reviewer must audit the candidate separately.
The window stays open.
