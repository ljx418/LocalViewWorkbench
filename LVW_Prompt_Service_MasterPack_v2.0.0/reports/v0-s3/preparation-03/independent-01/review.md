# S3-PREP-A — independent combined code + evidence review (independent-01)

**Reviewer:** separate Orca-visible ClaudeCode instance on `ljx418/lvw-v1-d0-review`
(Orca task `task_d317e381b8ea`, dispatch `ctx_262cf00e3a33`). This reviewer did
**not** implement the candidate and used **no** implementer conclusion as
evidence: every number below was recomputed from the artefacts.

**Verdict: NOT ACCEPTABLE AS IS — 1 Major, 0 Fatal, 7 Minor.**
The one Major is a false green on the exact rule this workpack exists to
protect. Everything else in the candidate reproduced exactly, and the
implementer's own evidence is genuine, reproducible and honestly disclosed.

This review is **PREPARATION_ONLY**. It is not a S3 Gate0, not a Stage PASS, not
a sample freeze, not a quality claim and not a human signature.

---

## 1. What was loaded, and the code identity

| item | value |
| --- | --- |
| root coordination commit | `d47c2a1571f15b592cfd0061f151de7e3eb11af3` |
| implementation terminal candidate | `311bdda937373f1055a6677f02322fb347c31cd1` |
| implementation pre-receipt | `77592cc0c2eea41aae515063d1ec181c73159273` |
| implementation **code** candidate | `d33893303f24da57216b63b4e0b9ef7e009d7613` |
| owner authority commit | `4f216700c917e20704b5edc90fa33de497441368` |
| scope approval `CHANGE-V1-S2-HANDOFF-01` | SHA-256 `bab47506…f3057` (matches the packet pin and the ADOPTED hash) |
| load | two clean merges into this review checkout (`f3f1284`, `a7bf1c9`); **0 conflicts, 0 hand repairs** |

All four production code files are **byte-identical to `d338933` after the
merge** (git blob comparison, `LVW_Prompt_Service_MasterPack_v2.0.0/` prefix
applied):

| file | blob | sha256 |
| --- | --- | --- |
| `tools/verify_s3_handoff.py` | `4a272a3bb221f78a719d1b4796b8e16c2b775b92` | `5944771fd3fe880014bcbecd06b1ba1fbe76a58d2b560ec74d8a679de5adfe9d` |
| `tools/s3_asset_inventory.py` | `b3f0ab2afc683a7e2ef005dc2db8b93c739775dc` | `333cfed9828fae22df524870fa691e553bcdb1965f30c1f5efb0b1882e3cbb30` |
| `tools/test_verify_s3_handoff.py` | `4b20a5723f392e96786b3b64d16fa83cf49ece78` | `c59b1c86af67d78bb2f4a8d372415eda0484a4170cf45f78fb80b239f235b023` |
| `tools/test_s3_asset_inventory.py` | `075786a09bb37db5086ac448097491abee74de07` | `2af8bf3e9526e0da4f5c42417f7437a0f62a4d73f429755ff55be06fa92957e0` |

The only delta against the candidate tree is the root coordination commit's own
six paths (`MANIFEST.sha256`, `plans/execution-control.json`, the task markdown,
the launch json/log and `independent-hash-child-01.json`). Those are exactly the
mutable execution-coordinate changes the prep contract allows; this review
edited none of them.

**Source fence:** 16 source-fence files and 10 packet payload files recomputed
to their pinned hashes before and after this review, with fence digest
`ce8a7f921225ef5a673c3998a424d112f1ddf3b0bb06f76fd97cd802c5c1291d`
unchanged. Nothing in the frozen set moved.

---

## 2. Mandatory commands, run once, in a fresh isolated copy

Both commands were executed **once** in `/tmp/lvw-s3prep-independent-01/package`,
a fresh byte copy of the merged review checkout. The two test files were read
**before** the run: every inventory test injects a fixture root, a fixture child
and fixture pins (`authority: FIXTURE_NON_AUTHORITY`), the CLI test uses a
deliberately broken binding so it refuses before any media access, and **no test
uses the production binding or the production receipt path**. The real inventory
therefore could not be re-triggered.

| command | exit | stdout SHA-256 | result |
| --- | --- | --- | --- |
| `python3 -B tools/verify_s3_handoff.py` | 0 | `12b1f73df49bca00c2c1c018851c252a23c2db3976c13a0e3a676c3d17a503df` | `HANDOFF_READINESS_VERIFIED`, 119/119 checks, 0 failed |
| `python3 -B -m pytest tools/test_verify_s3_handoff.py tools/test_s3_asset_inventory.py -q` | 0 | `1c18971ff9bc4fa892b33e4f04881b376337d497e6aea7e9f02f23eec125a835` | `48 passed in 0.36s` |

Both stdout digests are **byte-identical to the implementer's retained logs**,
and the 48-test count and the 119-check count both recompute. The implementer's
`checks/SHA256SUMS.txt` verifies fully (12/12 entries). Raw stdout/stderr/exit
and the timing of my own runs are in `independent-01/raw/`.

---

## 3. The Major finding

### S3P-A-MAJOR-01 — the guard validates the *declared* old-S2 projection, never the *live* one

**Position.** `tools/verify_s3_handoff.py` compares exactly three old-S2 state
sources, and all three are frozen artefacts:

* `check_predicate_shape` → the predicate snapshot's `historical_s2_required_state`
  (`tools/verify_s3_handoff.py:363-368`);
* `check_scope_approval` → the owner approval record's
  `historical_s2_native_human_approved` / `historical_s2_completed_substeps`
  (`tools/verify_s3_handoff.py:442-447`);
* `check_s2_independent` → the historical independent review's `human_signoff`
  (`tools/verify_s3_handoff.py:549-553`).

There is **no reference to `development_outline` anywhere in `tools/`**, and no
reference to the live `historical_s2_coordinate`.

**Trigger.** In a synthetic copy of the frozen authority, change **only**
`plans/execution-control.json` → the `development_outline` entry with
`stage_id == "V0-S2"`: `completed_substeps` 7 → 8, `human_signoff`
`"PENDING"` → `"APPROVED"`, and the last substep `PENDING` → `DONE`. Every
immutable proof, the declared predicate snapshot in all three plans and the
owner approval record stay untouched.

**Expected.** `HANDOFF_READINESS_REJECTED`. AGENTS.md rule 24 and ADR-14 require
the historical V0-S2 stage to stay 7/8 with native human signoff PENDING, and the
V0-S3 packet lists *"any attempt to change old S2 signature"* as a hard stop. The
owner rule preserves the **actual** old-S2 7/8 state, not only the declared
predicate.

**Actual.**

```
guard.live_s2_outline_8of8           HANDOFF_READINESS_VERIFIED   []   fence_failures: []
guard.live_s2_outline_8of8_substep_done  HANDOFF_READINESS_VERIFIED  []  fence_failures: []
```

Zero failed checks out of 119, and **no fence failure either** — because
`plans/execution-control.json` is deliberately *not* one of the 16 source-fence
files. This is therefore **not** a generic checksum gap and cannot be closed by
adding that file to the fence (that would freeze the mutable execution
coordinate, which the prep contract forbids). It is a **missing semantic check**.

While the live document says 8/8 `APPROVED`, the tool still prints:

```json
"historical_s2_projection": {"completed_substeps": 7, "total_substeps": 8, "human_signoff": "PENDING"}
```

so the published report states an old-S2 state that the live authority document
it just read contradicts. The terminal report's sentence *"The historical V0-S2
stage is unchanged at 7/8 with native human signoff PENDING"* is, for the same
reason, an unverified assertion.

**Why this is Major and not a wording nit.** The guard's own docstring claims it
proves the predicate is *"still projecting the historical S2 stage as 7/8 with
native human signoff PENDING"*. It proves that the **snapshot** says so. A
reviewer, a gate owner or a future reader of `HANDOFF_READINESS_VERIFIED` will
reasonably read that as a fact about the live old-S2 stage, and it is not one.
The single existing "fake old S2 human" negative
(`test_fake_old_s2_signoff_is_rejected`) exercises only the declared snapshot, so
the suite currently *proves* the declared side and *silences* the live side; and
`test_the_historical_s2_coordinate_state_is_not_required_to_stay_wait_human`
positively asserts that the live old-S2 coordinate may advance unchecked, so the
gap is currently encoded as intended behaviour. **That permissive test must be
re-decided by the owner (Codex), not silently deleted.**

**Fix direction (guard-strengthening only).** Read the live old-S2 human
projection out of `plans/execution-control.json` and assert it explicitly:
`development_outline["V0-S2"]` must keep `completed_substeps == 7`,
`total_substeps == 8`, `human_signoff == "PENDING"` and the
`"S2 人工签署与Git同步"` substep must remain `PENDING`; the live
`historical_s2_coordinate` must likewise not claim a granted signature. Stage /
workpack / gate / state and `current_blocking_gate` stay free to advance — those
are the genuinely mutable coordinates.

**Blocks Codex acceptance** until fixed or explicitly waived by the gate owner.

---

## 4. The Minor findings (non-blocking, with rationale)

| id | finding | why it is not blocking |
| --- | --- | --- |
| S3P-A-MINOR-01 | `INVENTORY_COMPLETE` + `traversal_stop_reason: null` does not itself encode that **186 of 698** supported-extension files were never hashed (the file-count and total-byte budgets are per-file skips, not stop reasons). | The disclosure *is* present and correct in `counts.skipped_by_reason`, `unknown_coverage`, terminal report §3/§4.1 and the terminal summary `open_gaps`. A reader who joins only two headline fields can over-read it. Documentation-level. |
| S3P-A-MINOR-02 | The receipt's four cleanup counters are **hardcoded literals**, not measurements; and terminal report §3 says *"Only the test suite's own `TemporaryDirectory` fixtures were cleaned, by `pytest`'s own teardown."* That is wrong twice: the tests use pytest's `tmp_path` fixture (not `tempfile.TemporaryDirectory`), and pytest **retains** `tmp_path` directories rather than deleting them (default `tmp_path_retention_count = 3`). | After my run, `/tmp/pytest-of-administrator/` still holds `pytest-49`, `pytest-50`, `pytest-51`. Those contain only **synthetic** fixture bytes — no source media, no private data, no credential — and the source tree is read-only by construction. No acceptance denominator depends on the sentence. Recorded as an inaccurate cleanup claim, **not** as a Stage PASS basis in either direction. |
| S3P-A-MINOR-03 | `authority: "AUTHORITATIVE"` is **path-relative** (`ROOT = Path(__file__).resolve().parents[1]`), not a provenance attestation: a full byte copy of the package in `/tmp` reports `AUTHORITATIVE` / `evaluated_root_is_canonical: true`. | No media-scope consequence — in authoritative mode the approved root still comes from the hash-pinned frozen child, so a copy reads the same authorised root and cannot widen it. The risk is a reader over-reading the label. |
| S3P-A-MINOR-04 | The binding's `candidate_sha` is only checked against a 40-hex regex; it is never resolved against the repository. | The material binding is intact: the two script hashes are checked against the files on disk **and** are independently pinned by the committed pre-inventory pre-receipt `77592cc`, which was committed *before* the inventory ran. A rewrite would require rewriting that commit — no bootstrap on a candidate-owned hash rewrite. |
| S3P-A-MINOR-05 | An unbounded `ls -la` of the approved root was run outside the single authorised bounded attempt, before the guard (disclosed, terminal report §3.2). | Metadata only (names/sizes/timestamps), inside the approved root, no media byte read, decoded or hashed, no other root listed. Low scope impact; no retrospective grant is invented here. The **tool's** own ordering (guard before any stat/read of source) is correct and was reproduced independently. |
| S3P-A-MINOR-06 | A pre-media refusal still writes a refusal receipt at the terminal path, which then blocks that path with `terminal_receipt_already_exists`. | The intended follow-up practice (a NEW receipt path for a NEW candidate; the historical terminal receipt never relabelled) already covers it. |
| S3P-A-MINOR-07 | **Data-handling:** 3 of the 512 inventoried items sit under the obviously private-labelled directory `私人图片-单人多视角图`, and their relative paths are committed in the receipt. | Metadata only — content never opened, decoded, viewed or copied into Git. A directory *name* is not proof of private content, and the root owner classified the whole `testSource` root as non-private local test input; but that classification is the owner's to make and it is unresolved for this subdirectory. **Root must exclude this path prefix from every future inference or sample proposal.** This review did not open or view those files. |

---

## 5. What I independently recomputed (not taken from the implementer)

**Inventory receipt** `05ab5d63a69556c721b26191273cf60c20e4b3bb5826712688cefb06786ee2ef`
(matches the hash child's `inventory_receipt_sha256`):

* 1006 entries examined = 888 regular files + 118 directories/symlinks;
* 888 − 190 `unsupported_extension` = **698** supported-extension files;
* **512** hashed / **1 049 735 799** bytes = 512 eligible; **376** skipped =
  190 `unsupported_extension` + 186 `hash_budget_exhausted`;
* **501** distinct SHA-256 over 512 items; **11** duplicate groups covering 22 items;
* extensions `.jpg` 325 (incl. one `.JPG`), `.png` 115, `.mp4` 68, `.jpeg` 2, `.webp` 2;
* sizes min 409 B, p50 119 736 B, p90 2 944 066 B, max 144 156 307 B;
* **0** `file_id` recomputation mismatches (all 512 ids reproduce);
* holdouts: 11 distinct hashes in `人工验收视频集/FREEZE.json`
  (`3a8313c6…9288c`) vs the hashed subset → **0 overlap**; scope is the 512 hashed
  files only, the 186 skips stay **unknown**;
* the receipt contains **no** absolute path (`/mnt/c`, `C:\`, `videoWorkLine` all
  absent), **no** `..` segment and **no** raw media bytes.

**Frozen proofs:** all 11 pinned hashes recompute exactly (scope request,
approval, approved decision, S2 machine receipt, S2 independent review, unified
human signoff, unified coverage, capability map, inventory child, spec manifest,
payload manifest).

**Historical S2 evidence:** machine candidate `719c745…`, exactly
`V0-A01..V0-A05` + `V0-A07..V0-A10` all `PASS` with `9 PASS / 0 others` and
`stage_pass_claim false`; independent review `9/9` cumulative, `Fatal 0 / Major 0`,
`human_signoff null`, `context_isolated true`, `read_only true`, no stage pass.
The unified slice is genuinely signed (`APPROVED`, `project_owner`,
candidate `621b1bf…`, `UNIFIED_MEDIA_EARLY`) with independent coverage
`UM-01..UM-10` all `PASS` and `fixed_denominator 10`.

**Commit order (no bootstrap on candidate-owned hash rewrites):**
`4f21670` (frozen child) → `d338933` (the four tools) → `77592cc` (pre-receipt +
preflight binding, `f9725ead…`, committed **before** the inventory) → `311bdda`
(terminal receipt + report). The preflight binding and the pre-receipt were
committed together before the run, so the script hashes were not self-certified
by the receipt.

**Negative probes — 27, all on synthetic fixtures:** wrong alias, wrong purpose,
wrong proof pin in the predicate, tampered proof file, fake old-S2 *declared*,
approval claiming an S2 signature, missing UM case, missing S2 case, shrunk case
list, malformed plan JSON, malformed payload manifest, missing approval, missing
UM signoff, predicate divergence, capability map claiming inherited quality,
malformed input, guard denied → **0 media bytes read and 0 observed opens under
the fixture media root**, hash budget exact vs one over, total-byte and
single-file boundaries, directory-entry budget, wall budget tripping inside
hashing, chunk size, symlink escape (never followed, outside SHA absent from the
results), file changed during the walk (excluded), existing terminal receipt
(never overwritten), binding with a non-SHA candidate, and a fixture child
attempting to widen the budget (correctly labelled non-authority). Each probe
records whether the refusal was **semantic** (no `fence.source_files` failure) or
a **generic checksum** (fence failure present) — this distinction is what makes
S3P-A-MAJOR-01 a missing semantic check rather than a checksum gap.

**CLI wiring:** `python3 -B tools/s3_asset_inventory.py --help` exposes exactly
`--binding` and `--receipt` (no `--root`, `--limits`, `--pins`, `--override`).
Running the *frozen* inventory command against an existing receipt exits 1 with
`terminal_receipt_already_exists`, `media_bytes_read 0`, and the original
receipt's SHA-256 unchanged — the no-overwrite guard is real, and the
authoritative/synthetic modes cannot be confused: the CLI cannot be pointed at a
fixture root, and in authoritative mode the root comes from the hash-pinned child.

---

## 6. The finite independent hash recheck (one child, three files)

Authority: `reports/v0-s3/preparation-03/independent-hash-child-01.json`
(root supplied, **unmodified**; its git blob at `d47c2a1` equals the worktree
blob). Preflight validated **before** any source access: expected candidates
`311bdda…` / `d338933…` present in this checkout, the four code files
byte-identical to `d338933`, and the inventory receipt hash matching
`05ab5d63…`.

| file | expected sha256 | actual sha256 | bytes | result |
| --- | --- | --- | --- | --- |
| `动作参考-原始.mp4` | `b788ac80…a227` | `b788ac80…a227` | 6 957 440 | VERIFIED |
| `图片-1 (1).jpeg` | `0295d0e1…8f46` | `0295d0e1…8f46` | 423 206 | VERIFIED |
| `参考.png` | `1f03a235…1ac0f` | `1f03a235…1ac0f` | 3 628 629 | VERIFIED |

3 files / 11 009 275 bytes / 15 chunks of 1 MiB / 0 escapes / 0 identity
changes / 0 writes; elapsed 0.582 s against a 60 s cap. The three `file_id`
values reproduce. **No walk, no second full inventory, no decode, no EXIF, no
visual analysis, no original written.** The 11 protected holdouts and the
obviously private-labelled paths were not touched.

**Disclosure:** my own harness computed the git blob identities with a wrong
repository path prefix on the first two passes, so its preflight boolean was
misreported as `false` although the source hashes were identical and correct
every time. The recheck therefore read the same three files **three** times:
11 009 275 bytes per attempt, **33 027 825 bytes cumulative (31.498 MiB)**, still
under the child's 32 MiB cap, wall 0.627 s / 0.473 s / 0.582 s against a 60 s
cap. All three attempts and all three raw results are retained under
`independent-01/hash-recheck/`.

---

## 7. Candidate catalogue for the next S3 quality selection

Derived from the receipt only — extensions, unique SHA and grouped relative-path
origin hints. **This assigns no visual ground truth, no usability verdict, no
quality label; it freezes nothing and says nothing about the S3 10/6, the V1
Q01 12/6 or the MS 12 clips / 47 shots / 21 hard cuts denominators.**

| path group | items | distinct SHA | extensions | bytes |
| --- | --- | --- | --- | --- |
| `edit/…` | 442 | 433 | .jpg 293, .png 90, .mp4 59 | 644 670 782 |
| `<root>` | 27 | 27 | .jpg 8, .png 9, .mp4 8, .jpeg 2 | 261 512 212 |
| `婚礼场景/` | 18 | 18 | .jpg 18 | 120 553 424 |
| `多图片参考3/` | 9 | 9 | .png 7, .webp 2 | 7 969 060 |
| `多角度参考/` | 6 | 6 | .png 6 | 7 277 818 |
| `多图片参考/` | 4 | 4 | .jpg 4 | 1 591 828 |
| `私人图片-单人多视角图/` | 3 | 3 | .png 3 | 5 719 456 |
| `多图片参考2/` | 2 | 2 | .jpg 2 | 294 140 |
| `_seedvr2_smoke/` | 1 | 1 | .mp4 1 | 147 079 |
| **total** | **512** | **501** | .jpg 325, .png 115, .mp4 68, .jpeg 2, .webp 2 | **1 049 735 799** |

Origin hints are **relative-path shapes only**: a large `edit/…/assets/` working
tree dominates, alongside a few themed reference folders. 11 content groups
cover 22 items (the same asset stored at the root and inside an
`edit/…/assets/` tree), so any later selection must deduplicate **by SHA, not
by path**. The `私人图片-单人多视角图/` prefix must be excluded from any future
inference or sample proposal until the owner resolves that classification.
The 186 unhashed supported-extension files remain **unknown** in content, size
and holdout overlap; a further pass needs a **new finite child derived from the
existing parent** (no new human approval), and this three-file hash recheck is
explicitly **not** a second full inventory.

---

## 8. Reuse if the Major is fixed

No **new full inventory** is required for a guard-strengthening fix to
`verify_s3_handoff.py`: the tool is not one of the 16 source-fence files, the 10
packet payload files, or any frozen proof hash; the hash algorithm, chunk size,
approved root, file set and the actual S2 projection that was inventoried are
all unchanged, so the original terminal receipt remains a valid record of what
was hashed. The original terminal receipt stays **historical** and must never be
relabelled as a new candidate — a corrected candidate takes its own candidate
identity and its own receipt path.

---

## 9. Remaining Gate0 gaps (unchanged by this preparation)

Unchanged from the implementer's own list and confirmed by this review: 186
supported-extension files unhashed; no independent prelabels for `V0-A11`
(10 images) / `V0-A12` (6 videos); no V1 Q01 12+6 set; no MS 12 clips / 47 shots
/ 21 hard cuts / 18 quality segments; disjointness against the development, Q01
and MS sets unproven; rights, origin and labels unknown for every file (test-use
authority is **not** a redistribution licence); `V0-A06` install / offline cold
start / rollback, the packaging contract, the model-tool-process binding, the
execution adapter and the finite production budget still open.

**Old S2 stays 7/8 with native human signoff PENDING** (verified in the live
`plans/execution-control.json`, unmodified by this review). The unified
frontend signature remains scoped to candidate `621b1bf` and the
`UNIFIED_MEDIA_EARLY` slice only.

---

## 10. Review budget and side effects

Model / GPU / provider / network / download / service / browser / media decode /
EXIF / visual analysis / production DB / install / push: **0**.
Product runtime 0 s, effective full checkpoints 0, source media read: **3 files,
33 027 825 bytes** (the finite hash child only). One metadata-only listing of
the **parent** of the approved root was performed by this reviewer to confirm
the mount exists; it returned sibling project directory names only, no media
content was opened and no file under the approved root was listed — disclosed
for completeness. Files written by this review: `reports/v0-s3/preparation-03/independent-01/`
only, plus the two load merges, which are upstream commits. All fixtures were
fresh owned `TemporaryDirectory`/`tmp_path` roots; no shared marker, no wildcard
delete, no source write.

---

## 11. Verdict

**NOT ACCEPTABLE AS IS.** One Major — S3P-A-MAJOR-01, the unvalidated live
old-S2 human projection — blocks Codex acceptance of the candidate until it is
fixed or explicitly waived by the gate owner. The seven Minor findings are
non-blocking and are recorded with rationale; the cleanup-wording item
(S3P-A-MINOR-02) should still be corrected because a terminal report should not
assert a cleanup that did not happen.

The implementer's evidence is genuine and reproducible: every raw log digest,
the 48-test count, the 119-check count, all eleven proof pins, the entire
inventory count/byte/duplicate/holdout structure and the three finite hash
recomputations reproduce exactly. No Stage PASS, no product Gate0, no sample
freeze and no human signature is claimed here or implied.

**Remaining Gate0 gaps** are listed in §9 and are unchanged.
