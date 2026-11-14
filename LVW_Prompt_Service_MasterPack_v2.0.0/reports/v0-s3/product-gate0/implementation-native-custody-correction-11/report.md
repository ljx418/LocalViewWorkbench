# N1 correction 11: the consolidated repair of the four Majors, the one Minor and the seventeen failures

**Stage** R1 / **Workpack** WP-R1-U3 / **Gate**
`S3_P4_N1_CONSOLIDATED_OWNER_CONTEXT_AND_IO_OUTCOME_CORRECTION11`.  **Coordinate**
V1/R1/WP-R1-U3/S3_P4_OFFLINE_INTEGRATION_PREPARATION.  **Phase** the STATIC
implementation phase of the correction 11.  **Predecessor candidate**
`cdac445434ed129ca6c5fa8acc830f1f13261a6f`.  **Predecessor evidence**
`ecc70ee9a4275e829d4439aa7d7371e0f45739fa` (the one frozen batch, FAILED, 17
failures).

**This delivery closes no Major and it signs no Stage.**  The dynamic
verification, the independent review and the acceptance of the round belong to
the root.

## 1. What was read

* the product pack: `AGENTS.md`, the governance README, the current root
  execution control and `docs/24`;
* the root packet of the correction 11: `contract.md`, `decision.json`,
  `scope.json`, `implementation-prompt.md`, `capacity.json`;
* the raw failure report and the raw receipt of the failed batch of the
  correction 10: `attempt01/report.md`,
  `attempt01/guarded-validation.stdout.log`,
  `attempt01/commands.json` and the receipt of the inherited runner;
* the isolated final review of the production source: `review.md`,
  `review-6327bea-delta.md`, `final-receipt.json`, `receipt.json` and the
  numbered copies of the two sources.

## 2. The seventeen failures of the frozen batch

The raw output of the batch names the seventeen failures and their causes.  The
repair of every one of them is inside the seven allowed files and the mapping of
each failure to its cause, to its repair and to the frozen node that carries the
proof is in `residual-mapping.md` (the last table).

| the cause that the batch proved | the repair | the nodes |
|---|---|---|
| the constructor of the channel read `writer_endpoint` where the parameter is `write_endpoint`: **every** construction of a channel raised a `NameError` | the two names are never mixed again | the eight nodes that build a channel |
| the lock of the admission is only created by the constructor and an old node builds the endpoint without its constructor | the fixture uses the **real** constructor and the production creates the lock of the admission **per instance** on its first use: an endpoint that was built without its constructor still has a **real** admission and never a permissive one | `test_n03_r09`, `test_n05_r14`, `test_n05_r20` |
| the close eligibility of the pending entry was the **frozen boolean** of the moment of the creation | the eligibility is a **callable** over the original record and the record and the pending table ask the very same callable | `test_n05_r04`, `test_n05_r05`, `test_n05_r11`, `test_n10_r01` |
| the direct cleanup of a failed creation closed the original handles without a claim | the direct cleanup **claims** the entries under the lock of the table and a handle that the recovery claimed is never closed by it | `test_n10_r02` |
| the aggregate forgot the process of a launch on the exit alone and the table of the launcher resurrected the forgotten child | the aggregate forgets the process only after the exit **and** the release of the original handle and the table is rebuilt from the entries that are **still** in it | `test_n07_r09`, `test_n10_r05` |
| the rewrite of the adoption lost the registration of the raw streams of a process whose close failed | the raw streams that could not be closed are retained with their **original** reference | `test_n05_r10` |
| the failure of the termination skipped the independent bounded wait of the exit | the wait of the exit runs **independently** of the termination and the original failure is preserved | `test_n10_r01` |
| the module of `test_n10_r07` had **no import of the module subprocess**: the view of the module raised a `NameError` before the launcher was ever reached | the import was added | `test_n10_r07` |
| the three phases of `test_n10_r09` shared one deadline and the second phase inherited the consumed budget | every phase is an **independent bounded scenario** with its own core, its own loop and its own deadline | `test_n10_r09` |

## 3. The four Majors and the one Minor

The repairs follow the architecture of the root contract.  The detailed mapping
of every sub-path (the production path, the trigger, the oracle, the negative,
the returned facts, the salvage and the node) is in `residual-mapping.md`.

### m03 (the one Minor) — the pending process eligibility was a frozen bool

`BrokerCore._process_closeable` now returns a **callable** over the original
record.  The pending table asks it at the moment of its close and it reads the
**current** confirmed-exit fact; the release of the records asks the very same
callable through `BrokerCore._process_eligible`.  A frozen answer is not an
eligibility any more: `_PendingResources._is_closeable` protects a handle whose
eligibility is not a callable.  `BrokerCore._terminate_owned` no longer skips the
independent bounded wait of the exit when the termination failed: the original
failure is named and preserved, the wait still runs while the original deadline
permits it, and an expired cleanup retains the control and never opens a new
budget of its own.  A process is never closed because the termination was
**requested**.

### M05 — the creation bypassed the exclusive ownership protocol

`WindowsApi._decide_entries` is the **one** atomic decision of the holding
table and it covers the process and the thread of one creation together.  The
successful return of `CreateProcess` reserves the two entries and commits them
(`_commit_entries`); the direct cleanup of a failed creation **claims** them
(`_release_created`) and gives a claim that did not end with a confirmed close
back.  A handle that the recovery of the facade claimed is never delivered to
the core and never closed twice, and the lock of the table is never held through
a blocking primitive.

### M07 — the aggregate lost the recovery of the original handle

`_LaunchAggregate.release` forgets the process only after the exit **and** the
release of the original handle; a failed close keeps the process with its owner
and the **same** owner retries **only** the incomplete part (the termination and
the wait of a confirmed exit are never repeated).  `_LauncherCustody.release`
reads the deadline of the context **again** for every resource and rebuilds the
table from the entries that are **still** in it, so that a forgotten child is
never resurrected.  The raw streams that could not be closed are returned with
their **original** reference and they stay reachable owned resources.
`StreamChannel.close` no longer reads a `RuntimeError` of the join as a finished
reader: the state of the reader stays **unknown** and the read end is never
closed underneath a possibly late target.

### M08 — the admission and the waits were not enforced

* The **final** admission of a generation is asked after the readiness of the
  worker and **immediately before** the submission, under the lock of the
  admission.  That is the linearization point: a cancellation or an expiry that
  is published **before** it causes **zero** primitive calls, and a cancellation
  that arrives **after** it follows the bounded cancellation.  No claim is made
  that an operating system call that already began may be undone atomically.
* The cancel flag and the deadline of the call **travel with the request**: the
  worker asks them itself before it enters the operation.
* The default launcher of the broker checks the **original** context before the
  directory, the plan and the process and it checks it **again** after the
  preparatory work and before the creation of the process.
* The child binds the **actual absolute deadline** to the core **before** the
  transport of the round exists: the reader of the channel and the workers of
  the endpoints never start with an unbound context.  The context of the round
  is also bound to the table of the primitives that a parent owned endpoint owns.
* `StartupOwner.start` is inside the ownership of its owner and inside the
  `finally` of the step, and the budget of the settle is **recomputed after the
  await** and immediately before every join, with no positive floor beyond the
  time that is really left.  The aggregate, the process helper and the table of
  the launcher read the **original** context of the launch dynamically, after
  the channel was coordinated and before the wait of the process.

### M09 — a new timeout hid a published failure

The outcome selection is unified.  Before a **new** timeout is decided, the
immutable published original error of the **same** generation is inspected, and
it is inspected **again** after the coordination.  The published failure remains
the primary error of the round; the timeout, the cancellation and a failed
coordination are **parallel** facts and they never replace it and never hide it.
Two actual public stops of the round keep the first error of the reader.

## 4. The changed files and their pins

Only the seven allowed files and the **new** report directory of this
correction were touched.  The pins are in `source-pins.json` and in
`validation-plan-request.json`.

| the file | the state | the sha256 |
|---|---|---|
| `tools/v0_s3_native_broker.py` | changed | `4e1b63a982d820056093c1ac53bef4dba30668d35549b159d25627b7dffd7433` |
| `tools/v0_s3_native_custody.py` | unchanged | `9b7e68969f2cbf8763664ba57fa3e5ee4133a0beed076a64f037e6344f336d8d` |
| `tools/test_v0_s3_native_custody.py` | unchanged | `fe96d2ffd353d3f3f6df4da2b023dd6cfaf58fe730ab6655afbca723ed507d32` |
| `tools/test_v0_s3_native_custody_regressions.py` | changed | `e520ab832f50ec6e2037623f83c5adcafa1293089670174cfd5edef472f948f3` |
| `tools/test_v0_s3_native_custody_correction05.py` | changed | `82b0d16e400d8d64643ca8c159e2a5ec9f81783b8505a709c535219c5ce7d936` |
| `tools/test_v0_s3_native_custody_correction07.py` | changed | `26c7d9e4b01be6302c442928dc20a0c370eede1a3e2a58bff7b9da81169351ee` |
| `tools/test_v0_s3_native_custody_correction10.py` | changed | `0299315266a322b67e0ee43e85d3b6028d97ddbb2a6417e58d77f4021ea853a7` |

The digest of the seven files (the sha256 of the sorted list of the pairs
`path sha256`) is `