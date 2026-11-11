# S3-PREP-A correction-01 — append-only errata

**This file appends to, and never edits, the previous S3-PREP-A records.**  Every
statement below corrects a *record-accuracy* or *known-limit* wording issue
that the independent review raised as non-blocking.  Nothing here re-runs a
Stage, grants a permission, relabels a receipt, or changes a product or
quality contract.  The historical V0-S2 stage stays **7/8 with native human
signoff PENDING**.

Authority for this correction: `reports/v0-s3/preparation-03/codex-review-resolution-01.json`
(`CHANGES_REQUIRED_MAJOR01_NO_NEW_HUMAN_AUTHORIZATION`), review
`reports/v0-s3/preparation-03/independent-01/` (`S3P-A-INDEPENDENT-01`,
1 Major + 7 Minor), source commit `12a1594c12b57a62ce445e4cf7f11fd38423039d`.

---

## E-1 — `S3P-A-MINOR-01`: `INVENTORY_COMPLETE` is bounded-operation-complete, not corpus-complete

The machine-readable decision string of the inventory receipt is
`INVENTORY_COMPLETE`.  That string describes the **bounded operation**
(512 hashed files under the frozen 512-file cap) and must not be read as
corpus coverage:

| derived figure | value |
| --- | --- |
| supported-extension files in the approved root | 698 |
| hashed | 512 |
| **not hashed** (`hash_budget_exhausted`) | **186** |
| inventory input items | 512 |
| derived catalog candidates | 509 |
| distinct candidate content SHA-256 | 498 |
| excluded private-labelled paths | 3 |
| whole-corpus coverage | **false** |

The receipt as a whole already discloses this in `counts.skipped_by_reason`,
`unknown_coverage`, terminal-report section 3 / 4.1 and the terminal summary
`open_gaps`.  No inventory label, format, field or decision string is changed
by this correction (the inventory script and its test stay byte-identical to
`311bdda`); this paragraph is the explicit derived partial-coverage statement
the adjudication asked for.

## E-2 — `S3P-A-MINOR-02`: the cleanup sentence was inaccurate; the zero counters are declarations, not measurements

The previous terminal report said: *"Only the test suite's own
`TemporaryDirectory` fixtures were cleaned, by pytest's own teardown."*  That
sentence is inaccurate on two counts and is corrected here, append-only:

1. the two test files use pytest's **`tmp_path` fixture**, not
   `tempfile.TemporaryDirectory`; and
2. **pytest does not delete `tmp_path` directories** — it retains them (default
   `tmp_path_retention_count = 3`), so "were cleaned, by pytest's own
   teardown" is false.

The four `cleanup` counters in the inventory receipt (`source_files_modified`,
`source_files_deleted`, `temporary_directories_created`, `deletions_performed`,
all `0`) are **code-contract declarations, not measurements**.  They are true
for that tool — it opens files read-only and deletes nothing — but no
instrumentation backs them.

The corrected statement is: *pytest retains its `tmp_path` fixtures (the last
three runs); only synthetic fixture bytes are involved and no source media is
touched.*

For this correction the test runs were additionally isolated: each pytest run
used an **owned `tempfile.TemporaryDirectory` parent** as the pytest
`--basetemp` root, the exact argv is recorded in
`run_configuration.json`, and the parent was **verified to be gone after the
owning context exited** (`owned_parent_removed = true` for every owned
parent).  No pre-existing or shared pytest root was purged; the shared
`/tmp/pytest-of-*` roots were left exactly as they were.

## E-3 — `S3P-A-MINOR-03`: `AUTHORITATIVE` is a local pinned-files check, not a Git attestation

`authority = "AUTHORITATIVE"` in the guard's public report means: *this run
executed against the tool's own package root and the frozen proof hashes
matched*.  It does **not** attest the git origin, the branch or the candidate
commit.  The actual candidate and script binding is attested **externally**:
the pre-inventory pre-receipt commit `77592cc`, the preflight binding
`reports/v0-s3/preparation-03/implementation/inventory-01/preflight.json`, and
the independent review.  The label is left unchanged here; this paragraph
states its exact scope.

## E-4 — `S3P-A-MINOR-05`: the disclosed `ls -la` deviation stays a deviation

An unbounded metadata-only directory listing of the approved root was run
during the previous preparation planning, before the guard ran and outside the
bounded inventory attempt.  It is **disclosed, not retroactively granted**:
no retrospective authorisation is invented for it, it is not repeated, and it
is not converted into a Gate0 PASS.  Its scope impact was low (metadata only,
inside the approved root, no source byte read, decoded or hashed) and that
assessment stands.

## E-5 — `S3P-A-MINOR-06`: a failed attempt's terminal receipt is immutable

A failed attempt keeps its own terminal receipt at its own path; the path is
consumed.  A future attempt needs a **new finite child and a new receipt path
derived from the existing parent** — never an overwrite of the historical
receipt, never a refund of the consumed path, and never a renewed human
authorisation for the same already-approved scope.  The historical receipt
`reports/v0-s3/preparation-03/implementation/inventory-01/receipt.json`
(SHA-256 `05ab5d63…`) stays exactly as it is and stays bound to the original
candidate `d338933`.

## E-6 — `S3P-A-MINOR-07` and the independent-report wording correction

**Correction to the independent review's wording.**  The review wrote that the
three private-labelled inventoried files were *"never opened, decoded, viewed
or copied into Git"*.  That wording is **inaccurate on the "opened" point**:
hash computation necessarily **opened and read the bytes** of every hashed
file, including those three.  What did **not** happen is any decode, any
visual view, any raw-media copy into Git, and any cloud/provider call.  The
receipt contains no raw media bytes and no content — only paths, sizes,
timestamps and hashes.

The derived catalog excludes those 3 private-labelled paths from every future
inference, prelabelling, sample proposal and derived-frame operation unless
and until the owner affirmatively resolves that specific classification.  The
raw inventory stays historical and is not rewritten.

## E-7 — the independent reviewer's hash process deviation is retained, not absorbed

`reports/v0-s3/preparation-03/independent-hash-process-deviation-01.json`
records that the reviewer helper read the three source files in **3 passes /
9 file reads / 33 027 825 bytes**, with the preflight **not** validated before
each of the first two source accesses.  The final positive recheck therefore
does **not** erase the two preflight-failed source reads and this correction
does **not** reuse it to claim a fully compliant independent read.

The deviation stays open and separately owned (the reviewer helper correction
is assigned by root, not by this workpack).  The original implementation
inventory remains separately bound and unaffected, and the three-file hash
equality itself is correct.

## E-8 — what this errata does NOT do

- it does not re-run the Stage, the inventory or the quality set;
- it does not request, imply or manufacture a new human permission
  (`CHANGE-V1-S2-HANDOFF-01` is already approved and is **not** up for a new
  human confirmation);
- it does not change a product contract, a quality contract, a threshold, a
  budget or the frozen proof set;
- it does not edit any owner document, plan, contract, packet, approval,
  proof, old receipt, the parent worktree, the inventory script or the
  inventory test;
- it does not claim a Stage PASS, product Gate0, a human signature or a
  release.
