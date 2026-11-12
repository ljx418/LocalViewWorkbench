# S3-P3B aggregate correction 06 — typed actual facts and named hierarchy custody

**READY_FOR_REVIEW only.**  This is an implementation batch.  It is not a Stage
pass, it is not a product Gate0 pass and it does not close the parent, native,
A06, registration, ledger, real-quality or human-release gates.  The independent
review of this candidate is the next step and it has to be performed by a
separate instance.

| Item | Value |
|---|---|
| Root disposition commit | `c05ee011a73a790917000e5ab0e615851053a2eb` (merged with `--no-edit`) |
| Independent review of the previous batch | `1618614798b7eaa23d603ab3d89b2e1176fc0e93` (Fatal0 / Major2 / Minor0, `CHANGES_REQUIRED`) |
| Baseline code / evidence | `44ad8c7a30ee418af41834de6cc87685f80d42fa` / `afb12e2a136b4a1bed05f1f766084c2b279e07b0` |
| Candidate code commit | `ba34b1581fc5e8e8b4de6ba469484e8eae416da1` |
| Product source sha256 | `c01b0103dcf436c8604a70234cef21978a0b52c644692db33b2612bd64105c67` (`tools/v0_s3_quality_phase.py`) |
| Test source sha256 | `9771baf7b68566a9b379de40a1474d821c3e2b3d7de54b796e0dcd6653e53456` (`tools/test_v0_s3_quality_phase.py`) |
| Guarded runner (immutable, reused unchanged) | `016e61a06d415266fe7442ad9dcd1672ff42a19e5c1fafb707727fc05c95bdb8` (`…/implementation-p3b-correction-05/run_guarded_checks.py`) |
| Counterexample probe sha256 | `6892409b377a737dd6161f55d33d0067aeceefe5ff6f5ac8f454805229c5a966` |
| Frozen contract / projection | `reports/v0-s3/product-gate0/p3b-quality-contract.md`, `reports/v0-s3/product-gate0/quality-execution-inputs.frozen.json` — **unchanged** |
| Contract change | none.  No threshold, no denominator, no public schema and no quality rule changed. |
| Files changed | `tools/v0_s3_quality_phase.py`, `tools/test_v0_s3_quality_phase.py`, plus this new report subtree. |

Both remaining roots of the correction-05 independent review are addressed in
this batch: **M01** (typed equality and extra fact binding) and **NM03** (the
named hierarchy during a bounded read).

---

## 1 — M01: the actual facts are typed and the key sets are closed

### What was wrong

The comparison of an authoritative actual fact used Python's `==`.  Python
accepts `True == 1` and `1 == 1.0`, so a caller could replace a recorded
boolean by the integer `1`, a recorded integer by the boolean `True` or a
recorded integer by the equal float `1.0` and the verdict still aggregated
true.  The top level key set of the supplied receipt was never closed, so a
caller could add an own top level fact.  The source evidence and the release
evidence were overlay declared, and their validators ignored an added key,
so a caller could add an own fact inside them as well.  The seal ordinal was
compared with `==`, so a seal that recorded `true` or `1.0` instead of the
integer `1` aligned with the canonical row.

### What was changed

* **A shared, type aware fact comparator.**  `tools/v0_s3_quality_phase.py`
  now has `_json_fact_equal(left, right)`.  A boolean is never an integer and
  never a float, an integer is never a float, `None` only equals `None`, and
  the comparison recurses into nested objects and into the elements of a
  list, so a typed substitution inside a nested fact is a difference too.
  Only JSON facts are compared; this is explicitly **not** a claim against
  arbitrary hostile Python objects and **not** a claim against a total
  forgery of the two trusted originals.
* **The comparator is the owner of the comparison.**  It is used in
  `_verify_execution_content` (top level and per row), in
  `_verify_seal_row_alignment` (including the five component identity list)
  and in `_row_evidence_complete` for the two evidence declarations.  There
  is no probe name special case and no per field special case: every
  published fact outside the closed overlay is bound with exact typed
  semantics, and a fact that the execution starts to record later is bound
  automatically.
* **Closed key sets.**  The top level key set of the supplied receipt and the
  key set of a supplied row are closed: a field that the published document
  does not have is refused.  The source evidence and the release evidence
  declarations have their own closed key sets
  (`QS_SOURCE_EVIDENCE_KEYS`, `QS_RELEASE_EVIDENCE_KEYS`,
  `QS_GPU_SAMPLE_KEYS`), and the GPU sample entries are closed as well.  The
  permissive verdict overlay may only *constrain* the published document; it
  can no longer smuggle an actual fact.
* **A strict integer ordinal.**  The seal row ordinal and the canonical row
  ordinal are strict integers (`_is_int`, so `bool` and `float` are
  rejected), and the seal alignment compares them with the typed comparator.
* **The publication bookkeeping is part of the published document.**  The two
  fields that the publication itself records — `staged_receipt_retained` and
  `staged_receipt_bytes` — are now serialized into the published document as
  well, so the returned receipt and the published document carry exactly the
  same fields and the top level key set can be closed without an exception
  for them.  The staged entry holds exactly the published payload, so its
  length is the length of the published receipt.

### What was deliberately *not* changed

The monotone known-failure handling of correction 05 is preserved exactly: a
published unknown failure stays unresolved under a supplied known error, a
published known failure supplied as a pass stays resolved and never usable, a
published pass downgraded by a supplied known failure keeps its resolved and
not usable obligation, and an independently scored critical count of three
stays visible and blocks the aggregate.  The existing typed context checks,
the null and missing negatives and the contradictory seal alignment are
untouched.  There is **no** all-technical-success rule and **no** threshold
change.  A missing, malformed or unknown source, storage or cleanup
declaration stays unknown; it is never silently ignored because the
canonical document happens to be good.

### Tests (all new, none deleted or weakened)

| Test | Negative that it pins |
|---|---|
| `test_correction06_m01_a_boolean_is_not_an_integer_actual_fact` | `public_submission_attempted` `true` → `1` is refused |
| `test_correction06_m01_an_integer_counter_is_not_a_boolean_actual_fact` | `provider_calls` `1` → `true` is refused |
| `test_correction06_m01_an_equal_float_is_not_an_integer_actual_fact` | `public_submissions` `int` → equal `float` is refused |
| `test_correction06_m01_an_equal_float_in_a_nested_count_is_refused` | `fixed_denominator.total` `16` → `16.0` is refused |
| `test_correction06_m01_a_nested_identity_substitution_is_unknown` | a boolean inside the sealed identity is unknown |
| `test_correction06_m01_a_nested_counter_substitution_is_unknown` | a boolean inside the GPU sample counter is unknown |
| `test_correction06_m01_a_caller_only_receipt_fact_is_refused` | a caller only top level field is refused |
| `test_correction06_m01_a_caller_only_source_evidence_fact_is_unknown` | a caller only fact inside the source evidence is unknown |
| `test_correction06_m01_a_caller_only_release_evidence_fact_is_unknown` | a caller only fact inside the release evidence is unknown |
| `test_correction06_m01_a_caller_only_gpu_sample_fact_is_unknown` | a caller only fact inside a GPU sample is unknown |
| `test_correction06_m01_a_seal_only_typed_ordinal_is_refused` (`true`, `1.0`) | the seal only typed ordinal is refused with a consistent seal hash and length |
| `test_correction06_m01_the_published_and_the_returned_receipt_carry_the_same_fields` | the top level key set is closed by construction |

### Oracle, negative and terminal state

The oracle is the public scoring entry point `recompute_scores` of the real
product module, driven with a genuine public-owner run (the real production
node classes, the real `BridgeOwner` and the real S2 oracles; only the
native HTTP/provider boundary and the media decoder are replaced by bounded
synthetic fixtures).  The negative is the *intended guard and reason*, not a
malformed setup: the observed reasons are
`QS_EXECUTION_CONTENT_MISMATCH:<field>` for a typed substitution or an own
fact, `SOURCE_EVIDENCE_UNEXPECTED_FIELD`,
`RELEASE_EVIDENCE_UNEXPECTED_FIELD`, `RELEASE_EVIDENCE_GPU_SAMPLES_INVALID`,
`SOURCE_IDENTITY_INVALID` and `QS_SOURCE_PLAN_ORDER_INVALID`.  The terminal
state of every negative is *refused* or *unresolved with
`aggregate_pass=false`*; no negative reaches an aggregate pass.  The cleanup
is the ordinary one of the product: the fixture roots are the temporary
directories of the runner and of pytest and they are removed by the runner
and by pytest.

---

## 2 — NM03: the named hierarchy during a bounded read

### What was wrong

`_ArtifactBoundary.verify` only `fstat`ed the already open descriptors
against their own recorded identities.  It never re-observed the *named*
entries, so a run root, a `temp` directory or a phase directory that was
renamed and replaced by a symlink during the first canonical read was never
detected: the pinned descriptors kept reading the original genuine bytes, the
aggregate returned true and the selected path no longer named the pinned
hierarchy.  The run root was opened by absolute path, so the trusted parent
of the run root was never pinned, and a literal equality of the declared run
root returned before any boundary verification.

### What was changed

* **The trusted parent is pinned.**  `_ArtifactBoundary` opens the parent of
  the run root once as a directory and only ever uses it to open the run root
  *by name*.  It is never used to resolve an artifact path and there is no
  fallback to an absolute path.
* **Every level is recorded as a triple.**  The run root, the `temp`
  directory and the phase directory are recorded as
  `(parent_fd, child_name, pinned identity)`.
* **The current named entry is verified.**  `_verify_named_entry` performs a
  no-follow, parent relative `stat` of the *current* directory entry and
  compares it with the pinned handle and with the original identity.  A
  renamed entry that was replaced by a symlink, by another directory or by
  another file is refused; it is never resolved, adopted or followed away.
  The verification runs before a read, after a read and before a successful
  completion (`recompute_scores` verifies the boundary once more before it
  returns the verdict).
* **The read directories and the leaf are covered.**  Every directory level
  and the leaf that is opened for a read are recorded the same way and their
  named entries are verified *while the handles are still held* — the child
  directory of the raw artifact and the raw leaf itself are verified before
  their descriptors are closed.  The canonical receipt, the source seal and
  every raw artifact are read through this one boundary, so no evidence type
  can have a weaker ancestry rule than another.
* **An identical literal declared run root is not a shortcut.**
  `_verify_run_root_binding` now performs the boundary verification in both
  branches, so a literal equality never returns before the pinned hierarchy
  has been verified.
* **No descriptor is leaked.**  The trusted parent descriptor is closed with
  the other descriptors of the boundary, on the ordinary path, on every error
  path and when the constructor fails.  The descriptors that a read opens are
  closed when the read ends; the custody is not extended.

### The honest limitation

This is a cooperative, finite observation of inodes and directory names
inside the existing audited Python/filesystem trust model.  It is **not** a
universal concurrency guarantee, **not** immunity against a hostile kernel,
**not** immunity against a native Windows reparse point and **not** a claim
that the filesystem cannot move inodes underneath the process.  No new
filesystem platform, native extension or native test was invented here.

### Tests (all new, none deleted or weakened)

| Test | Negative that it pins |
|---|---|
| `test_correction06_nm03_a_run_root_redirected_during_the_canonical_read_is_refused` | rename + symlink of the run root during the canonical read |
| `test_correction06_nm03_a_temp_redirected_during_the_canonical_read_is_refused` | rename + symlink of `temp` during the canonical read |
| `test_correction06_nm03_a_phase_redirected_during_the_canonical_read_is_refused` | rename + symlink of the phase directory during the canonical read |
| `test_correction06_nm03_a_run_root_replaced_by_another_directory_during_the_read_is_refused` | rename + a *different plain directory* at the same path |
| `test_correction06_nm03_a_source_plan_leaf_redirected_during_its_read_is_refused` | rename + symlink of the seal leaf during the seal read |
| `test_correction06_nm03_a_source_plan_parent_redirected_during_its_read_is_refused` | rename + symlink of the seal parent during the seal read |
| `test_correction06_nm03_a_raw_parent_redirected_during_the_raw_read_is_refused` | rename + symlink of the raw parent during the raw read |
| `test_correction06_nm03_a_raw_leaf_replaced_by_another_file_during_the_raw_read_is_refused` | same path, different plain file, same bytes |
| `test_correction06_nm03_a_missing_named_entry_during_the_raw_read_is_refused` | the named entry disappears |
| `test_correction06_nm03_an_identical_declared_run_root_does_not_skip_the_verification` | the literal declared run root never returns before the verification |
| `test_correction06_nm03_a_bounded_tiny_read_is_exact_and_one_over` | the bounded read is exact at the cap and refuses one over |
| `test_correction06_nm03_a_growing_leaf_is_refused_by_the_final_bound` | a leaf that grows during the read is refused by the final `cap + 1` check |
| `test_correction06_nm03_no_descriptor_is_leaked_by_the_boundary` | no descriptor is leaked on the ordinary path and on a failed construction |

### Oracle, negative and terminal state

The oracle is again the public scoring entry point with a genuine public-owner
run.  The mutation happens *inside* the bounded read of the named artifact
(the read hook fires exactly once on the descriptor of that artifact, so the
genuine bytes are never changed — only the names are).  The negative is the
intended guard and reason: `CANONICAL_RECEIPT_REDIRECT_FORBIDDEN`,
`QS_SOURCE_PLAN_REDIRECT_FORBIDDEN`, `QS_RAW_ARTIFACT_REDIRECT_FORBIDDEN` and
`CANONICAL_RECEIPT_ABSENT` / `QS_RAW_ARTIFACT_UNREADABLE` for a missing
entry.  The terminal state is a refusal; the aggregate never passes while the
names no longer bind.  The cleanup is the ordinary one: the runner owns and
removes its temporary root, pytest removes its own, and the descriptors of
the boundary are closed on every path.

---

## 3 — The obligation audit of the 206 frozen cases

`reports/v0-s3/product-gate0/implementation-p3b-correction-06/obligation-audit.json`
is a static `ast` audit.  It compares the text of the frozen correction-05
candidate test module with the text of this candidate and compares the
collected node ids of the frozen correction-05 acceptance suite with the node
ids that this candidate collects.

| Measure | Value |
|---|---|
| Baseline test definitions | 155 |
| Identical definitions | **155** (AST identical, decorators included) |
| Adapted definitions | **0** |
| Deleted definitions | **0** |
| Changed old helper or class definitions | **0** |
| Added test definitions | 25 (26 collected cases) |
| Frozen collected node ids | 206 |
| Frozen node ids missing in this candidate | **0** |
| Collected node ids of this candidate | 232 |

The audit is a *git read operation*: it imports no product module, it executes
no product code and it is run outside the offline audit guard, which blocks
host processes by design.  Every other observation in this batch was produced
under the guard.

---

## 4 — The invocations of this batch

The immutable correction-05 guarded runner was reused **unchanged**.  It
installs the `sys.addaudithook` guard *before* pytest, before any plugin and
before any product or test import, disables the plugin autoload, the cache
provider and the bytecode writing, and blocks `socket.connect`,
`socket.connect_ex`, `socket.bind`, `socket.getaddrinfo`,
`socket.gethostbyname`, `socket.gethostbyaddr`, `socket.getnameinfo`,
`subprocess.Popen`, `os.system`, `os.exec`, `os.spawn`, `os.posix_spawn`,
`os.fork` and `os.forkpty`.  The runner is immutable, so the `kind` string of
its receipts still reads `S3_P3B_CORRECTION_05_GUARDED_CHECK_RECEIPT`; the
label and the output directory identify this correction-06 batch.

The raw streams are captured at the file descriptor level by the runner; no
stream is piped, no exit code is masked and no log is reconstructed.

| Invocation | Mode | Once-only result | Inner / outer true exit |
|---|---|---|---|
| Guard self test | `guard` | 4 of 4 audit events blocked before any external action | 0 |
| Combined candidate suite | `suite` | **232/232 passed** (206 frozen + 26 new), 72.33 s | 0 |
| Remaining independent counterexamples | `script` | 22 observations, 0 still open | 0 |

Per invocation the receipt records the actual argv, the raw stdout and stderr
hashes and sizes, the sha256 of the runner, of the probe and of both bound
source files *before and after* the run, the absolute path and the hash of
the actually imported product and test modules, the collected node ids, the
guard results and the removal of the owned temporary root.

**Truthful account of the development diagnostics.**  The full suite was
executed twice in this batch: once as an editing diagnostic before the
candidate was committed (`editing-diagnostics/dev-suite-1.*`, exit 0, the same
source content) and once as the final committed-candidate run (`suite.*`,
exit 0).  The editing diagnostics are retained with their own distinct source
hashes and their own exits: `dev-focus-1` (focused `qs or correction05`, 59
collected, exit 0, the frozen test module), `dev-focus-2` (focused
`correction06`, 26 collected, **exit 1** — one new test failed on its own
assertion about the replaced run root and was corrected), `dev-focus-3`
(focused `correction06`, 26 collected, exit 0), `dev-focused-1` (the counter
example probe, exit 0) and `dev-suite-1` (232 collected, exit 0).  The
historical 21 / 32 / 10 broad observations, the separate 175 / 31 runs, the
P3A 121, the P2B 237 and the project suites were **not** repeated.  The
original correction-03 unguarded twelve remain UNKNOWN and uncredited; no
cosmetic rerun was made.

### The 22 focused counterexamples of the previous review, replayed once

| Observation | Terminal state |
|---|---|
| `honest_baseline` | aggregate pass (the honest path still closes) |
| `attempt_true_to_int1` | refused, `QS_EXECUTION_CONTENT_MISMATCH:public_submission_attempted` |
| `attempt_true_to_float` | refused, `QS_EXECUTION_CONTENT_MISMATCH:public_submission_attempted` |
| `counter_one_to_bool` | refused, `QS_EXECUTION_CONTENT_MISMATCH:provider_calls` |
| `counter_one_to_float` | refused, `QS_EXECUTION_CONTENT_MISMATCH:provider_calls` |
| `nested_identity_int_to_bool` | unresolved, `SOURCE_IDENTITY_INVALID`, aggregate false |
| `nested_counter_int_to_bool` | unresolved, `RELEASE_EVIDENCE_GPU_SAMPLES_INVALID`, aggregate false |
| `source_extra_fact` | unresolved, `SOURCE_EVIDENCE_UNEXPECTED_FIELD`, aggregate false |
| `release_extra_fact` | unresolved, `RELEASE_EVIDENCE_UNEXPECTED_FIELD`, aggregate false |
| `gpu_sample_extra_fact` | unresolved, `RELEASE_EVIDENCE_GPU_SAMPLES_INVALID`, aggregate false |
| `receipt_extra_fact` | refused, `QS_EXECUTION_CONTENT_MISMATCH:independent_added_fact` |
| `row_extra_fact` | refused, `QS_EXECUTION_CONTENT_MISMATCH:independent_added_fact` |
| `seal_only_ordinal_true` | refused, `QS_SOURCE_PLAN_ORDER_INVALID` |
| `seal_only_ordinal_float` | refused, `QS_SOURCE_PLAN_ORDER_INVALID` |
| `known_overlay_with_critical_three` | resolved, not usable, aggregate false (the critical evidence stays visible) |
| `redirect_during_read_run_root` | refused, `CANONICAL_RECEIPT_REDIRECT_FORBIDDEN` |
| `redirect_during_read_temp` | refused, `CANONICAL_RECEIPT_REDIRECT_FORBIDDEN` |
| `redirect_during_read_phase` | refused, `CANONICAL_RECEIPT_REDIRECT_FORBIDDEN` |
| `redirect_during_read_raw_parent` | refused, `QS_RAW_ARTIFACT_REDIRECT_FORBIDDEN` |
| `rename_to_another_plain_directory_during_read` | refused, `CANONICAL_RECEIPT_REDIRECT_FORBIDDEN` |
| `missing_named_entry_during_read` | refused, `CANONICAL_RECEIPT_ABSENT` |
| `redirected_raw_leaf_during_read` | refused, `QS_RAW_ARTIFACT_REDIRECT_FORBIDDEN` |

Every observation records that the hook fired exactly once and that the
genuine bytes were unchanged, so the refusal is about the names and not about
changed content.

---

## 5 — The preserved closures

The closures of the previous batches are preserved and were re-executed by the
206 frozen cases of this batch: M02, M03, M04, M05, M06, M07, M09 and `m01`
stay closed scoped offline; the M08 label and full descriptor alignment and
the NM04 source handoff stay closed (the shared boolean ordinal residual is
inside M01 and is not counted twice); NM01 (capacity and time driver
accessors) and NM02 (one final coherent clock, exact 10800, one over 10801,
the later proof) stay closed cooperatively.  The fixed 16 / 34 call counts,
the `score >= 8` rule, the 8/10 images and 5/6 videos rule, the critical
zero rule, the genuine known failure and critical evidence and the raw
preservation are unchanged.  The final driver getters still precede the final
bounded original source check, which precedes the one coherent clock and
proof guard, which precedes the reservation, the attempt and the cached
submit; there is no refund, no retry and no unchecked callback.

The parent trust decision is unchanged: a total coherent rewrite of *both*
trusted originals is not a new cryptographic signature obligation.  The
contradictory and the caller only records and the path mismatches remain
enforceable, and the parent archive binding is still required before a real
run.

---

## 6 — The offline discipline and the cleanup

Zero actual Windows, WSL, PowerShell, parser or host executable hashing; zero
real media, FFmpeg, model, GPU, service, network, download, real ledger,
claim or full checkpoint actions.  No test source, holdout or full prelabel
was read.  The only fixtures are the fresh 4x4 PNG and the tiny fake video
behind the actual production owners; no real decoder and no server was
started.  The task scoped `MAX_RETRIES` and `RETRY_WATCHDOG` controls are
`0` (only these two retry keys were read, no secret was read).  No Claude
429 was observed; there was no retry, no provider, model, account or harness
switch, no fallback and no Codex takeover, and no purchase.  The git
operations were read, merge and identity only; there was no push and no
permanent configuration.

Every owned temporary root is registered and removed: the runner owned root
of each of the three invocations is removed (`owned_root_removed: true` in
each receipt), the pytest basetemp is under the runner owned root, and the
counterexample probe registers its own root and its nine sub-roots and removes
them in its `finally` block.  No older root was scanned or deleted.  No
binary, media, database, ZIP or copied source was committed.

---

## 7 — The risks and what stays NOT_PROVEN

* The parent hard watchdog is still `UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER`; a
  synchronous callback that never returns is not preempted.
* The parent owned original archive or an independently retained original
  attestation and the selected root binding are **NOT_PROVEN**.  The parent
  has to bind an owned original archive or a retained attestation before a
  real run; an arbitrary unbound archive is not accepted as truth.
* Native Windows and WSL deployment, residue admission and A06 enforcement
  and attempt observation are **NOT_PROVEN**.
* The actual registration baseline, the installation and the rollback are
  **NOT_PROVEN**.
* The authentic parent ledger debit is **NOT_PROVEN**.
* The real quality sixteen, the full twelve, the product Gate0 and the human
  and release acceptance are **NOT_PROVEN**.
* The frozen 8 MiB / 128 MiB / 256 MiB matrices were **not** repeated here;
  they remain proven by the earlier independent runs and this batch does not
  recertify them.  Every read of this batch stays at most `cap + 1`.
* No claim of hostile kernel, native Windows reparse, native extension or
  direct syscall immunity is made anywhere in this batch.
* The original correction-03 unguarded twelve remain UNKNOWN and uncredited.

---

## 8 — Ten-field handoff

1. **current coordinate** — `{"stage_id": "R1", "workpack_id": "WP-R1-U3", "gate": "S3_P3B_QUALITY_INTEGRATION_INDEPENDENT_REVIEW", "state": "READY"}` (from `plans/execution-control.json`).
2. **this batch** — S3-P3B aggregate correction 06 implemented: M01 typed actual facts and closed key sets, NM03 named hierarchy custody; 232 product cases once (206 frozen plus 26 new), guard four once, focused twenty-two observations once; state `READY_FOR_REVIEW`.
3. **last passed gate** — `UNIFIED_MEDIA_FIXED_UM10_AND_INDEPENDENT_REVIEW`, candidate `621b1bf386db71bfe08ca2f533fa8ec396b0504b`, receipt `reports/unified-media/independent-live-15/receipt.json`, decision `10PASS_0FAIL_0BLOCKED_FATAL0_MAJOR0_HUMAN_ACCEPTED_SCOPE_ONLY`.
4. **current blocking gate** — `S3_P3B_CORRECTION06_INDEPENDENT_REVIEW_PENDING`.
5. **route position** — root aggregate disposition → bounded correction → separate independent review → parent / native / A06 / Gate0 → finite real quality and human and release gates.
6. **remaining work** — the independent review of this candidate; the parent owned original archive or retained independent attestation and the selected root binding (NOT_PROVEN); the parent hard watchdog (`UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER`); native Windows and WSL deployment, residue admission and A06 (NOT_PROVEN); the actual registration baseline, installation and rollback (NOT_PROVEN); the authentic parent ledger debit (NOT_PROVEN); the real quality sixteen, the full twelve, the product Gate0 and the human and release acceptance (NOT_PROVEN).
7. **next owner** — the root architecture and gate owner for the disposition; the independent review instance is next and it stays separated from this implementation.
8. **authorization** — the completed authorized offline implementation only; no new human approval is needed for this frozen offline scope and no real runtime authority is inferred.
9. **evidence directory** — `reports/v0-s3/product-gate0/implementation-p3b-correction-06/`.
10. **exact stop reason** — the two remaining roots are implemented, the candidate `ba34b1581fc5e8e8b4de6ba469484e8eae416da1` is committed and the evidence is complete; the implementer reports `READY_FOR_REVIEW` only and keeps the terminal visible.

---

## 9 — Full V0–V3 outline from the current root control

Source: `plans/execution-control.json` of this worktree, read after the merge of
`c05ee01`.  Current Stage **R1**.  The counts and the implementation, machine
acceptance, independent review and human sign-off states are unchanged; this
batch is a correction inside V0-S3 and it does not change any of them.

|Delivery|Stage|Done/total|Implementation|Machine|Independent|Human|
|---|---|---:|---|---|---|---|
|V0|V0-S0|1/2|ARCHIVED|NO_GO_HISTORICAL|COMPLETED_WITH_BLOCKERS|NOT_SIGNED|
|V0-Min|V0-S1|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|
|V1前置|R0|1/2|PARTIAL_REUSED|SINGLE_IMAGE_SUBSET_ONLY|NO_SEPARATE_R0_VERDICT|NO_SEPARATE_R0_SIGNOFF|
|V1早期切片|R1a|5/5|DELIVERED|ACCEPTED_SCOPE_ONLY|COMPLETED|APPROVED|
|V0.1|V0-S2|7/8|IMPLEMENTED|COMPLETE_FIXED9_PASSED|COMPLETE_FATAL0_MAJOR0_MINOR0|PENDING|
|V0.2|V0-S3|0/6|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V1|R1|0/4|EARLY_SLICE_IMPLEMENTED_FULL_R1_PENDING|EARLY_SLICE_UM10_ONLY|EARLY_SLICE_FATAL0_MAJOR0|EARLY_SLICE_APPROVED_FULL_R1_PENDING|
|V1|V1-M1|0/3|DESIGN_ONLY|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V1|R2|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V2|R3|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V2|R4|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5a|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5b|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|
|V3|R5c|0/4|NOT_DELIVERED|NOT_RUN|NOT_RUN|NOT_SIGNED|

Full declared substeps:

- **V0-S0**: 盘点与探索记录 [DONE]; 完整生产基线 [FAILED_HISTORICAL].
- **V0-S1**: 独立人工稿与导出 [DONE]; 真实图片与预处理 [DONE]; 四输出与草稿保护 [DONE]; 固定证据及独立审查 [DONE]; 人工签署 [DONE].
- **R0**: 独立单图路径在R1a验证 [DONE]; 完整复用/许可清单单独闭合 [NOT_VERIFIED].
- **R1a**: 正式合同子集与前后端 [DONE]; 真实单图链路 [DONE]; 失败/服务控制与人工稿保护 [DONE]; 独立审查七项 [DONE]; 人工体验签署 [DONE].
- **V0-S2**: WP-S2-00 冻结准备 [DONE]; WP-S2-01 媒体owner [DONE]; WP-S2-02 公开视频路径 [DONE]; WP-S2-03 安全/资源/取消 [DONE]; WP-S2-04 离线集中收口 [DONE]; WP-S2-05 完整真实验收 [DONE]; WP-S2-06 独立审查 [DONE]; S2 人工签署与Git同步 [PENDING].
- **V0-S3**: 包/清单/使用说明 [PENDING]; 安装诊断与回滚 [PENDING]; 独立质量集与标注 [PENDING]; 离线集中收口 [PENDING]; 真实十二项及质量 [PENDING]; 独审/人工签署/同步 [PENDING].
- **R1**: 受控媒体与人工镜头 [PENDING]; 六模式四目标 [PENDING]; SQLite/修订/导入 [PENDING]; 组合回归及阶段审查 [PENDING].
- **V1-M1**: M1-A detection/PTS/boundaries/timeline [PENDING]; M1-B per-shot evidence and serial child jobs [PENDING]; M1-C per-shot drafts/exports/fixed8 full validation [PENDING].
- **R2**: 异步任务/CAS/取消 [PENDING]; 真实图视频及质量 [PENDING]; CLI/导出/便携包 [PENDING]; V1累计独审及人工签署 [PENDING].
- **R3**: 真实PTS/切镜 [PENDING]; 资产/FTS5/配方 [PENDING]; 对比/QC/JSONL [PENDING]; 阶段验收 [PENDING].
- **R4**: MCP真客户端 [PENDING]; 批量/lease/幂等 [PENDING]; 备份恢复 [PENDING]; V2累计验收签署 [PENDING].
- **R5a**: 对端握手 [PENDING]; Navia证据 [PENDING]; Narralens建议/冲突 [PENDING]; 阶段真实验收 [PENDING].
- **R5b**: Comfy allowlist/映射 [PENDING]; 收据/outbox [PENDING]; GPU/取消协作 [PENDING]; 阶段真实验收 [PENDING].
- **R5c**: 集成UI [PENDING]; 升级回滚 [PENDING]; 三系统E2E [PENDING]; V3独审及人工签署 [PENDING].

---

**Final state of this batch: `READY_FOR_REVIEW`.  No Stage pass, no product
Gate0 pass, no human acceptance.**
