# N1 correction 13 — the actual outcome of the frozen batch

Candidate `b5e92af41ba6d27a0a2a52c5442de4f95df1a8e3`.  Root plan
`native-custody-correction-13/validation-plan-01/plan.json` SHA256 `27d017823e43cae6dfa6697cd3d05beb398cfe07bc238ca101b755fc63417da7`.
Root ACK `ACK_ONE189_NODE_GUARDED_OFFLINE_BATCH`.

**This is the outcome of one finite batch.  It is NOT a Stage, a product or a native PASS,**
no Major is closed by it and the sole remaining M07 stays OPEN until an independent
source review **and** an actual validation are both in place.  M08 stays source-closed only.
No repair, no rerun and no self repair was performed: the failed candidate and every
artefact of the batch are preserved exactly as they are.

## 1. The three commands

| # | Label | Exit | Wall |
|---|---|---|---|
| 1 | counter-absence-before | 0 | not separately instrumented |
| 2 | guarded-validation | 1 | 51.197 s (the runner: 50.962 s; the guard: 51.133 s) |
| 3 | counter-absence-after | 0 | not separately instrumented |

Each command was executed **exactly once** with the absolute argv, the cwd and the
per-command environment of the plan.  No wrapper, no extra test, no retry and no
self repair.  The raw stdout and stderr of each command are in this directory.

## 2. The batch

| Fact | Value |
|---|---|
| collected / selected | 189 / 189 — the collected order is **identical** to the frozen list |
| call / pass / fail / skip | 189 / 184 / 5 / 0 |
| functional pass (the two integrity-only nodes excluded) | 182 |
| pytest exit | 1 |
| cleanup proven for the batch | **true** |
| threads before / after | `["MainThread"]` / `["MainThread"]` |
| file descriptors before / after | the same three rows with the same (dev, ino, mode); `new_or_reused_fds` is empty; no unknown entry |
| stdlib preload | exactly one `ctypes.dlopen(None)`, the window **CLOSED** before the candidate and before pytest |
| guard | precedes the candidate and pytest; the eight self-test denials fired; `runtime_denials` is **empty** |

## 3. The counter

The parent and the counter were **MISSING (errno 2)** in the observation before the batch
and in the observation after it.  The content was never read, nothing was created,
written, reset or refunded and the expired grant was not revived.  The historical
continuity stays `UNAVAILABLE_NOT_PROVEN`: two exact metadata observations prove the
continued absence only.

## 4. The five failed nodes — the actual cause from the raw evidence

### `tools/test_v0_s3_native_custody_correction05.py::test_n05_r10_a_launch_that_could_not_be_handed_over_keeps_its_resources`

```
tools/test_v0_s3_native_custody_correction05.py:1229: in test_n05_r10_a_launch_that_could_not_be_handed_over_keeps_its_resources
    aggregate_c, cancellation_c, first_c, facts = run_fault_scenario(
tools/test_v0_s3_native_custody_correction05.py:1172: in run_fault_scenario
    assert scoped.items() == [], \
E   AssertionError: the table of the launcher kept an item of the launch
E   assert [{'detail': '...7ca02a90e00>}] == []
E     
E     Left contains one more item: {'detail': 'launch', 'kind': 'aggregate', 'launch': None, 'resource': <tools.v0_s3_native_broker._LaunchAggregate object at 0x77ca02a90e00>}
E     Use -v to get more diff
```

Cause: the aggregate of the launch reports an original as **retained** after the raw retry of the same release closed it: the recovery report is `released: [process, stdout]` and `retained: [stdout]`, so the table of the launcher keeps the aggregate and it never converges.  The reconciliation of the registered originals appends the unresolved ones to the retained list **before** the raw retry of the same release closes them.

### `tools/test_v0_s3_native_custody_correction07.py::test_n07_r02_the_recovery_keeps_the_handle_until_the_exit_is_confirmed`

```
tools/test_v0_s3_native_custody_correction07.py:819: in test_n07_r02_the_recovery_keeps_the_handle_until_the_exit_is_confirmed
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=None,
tools/v0_s3_native_broker.py:2348: in __init__
    self.run_root = Path(run_root)
                    ^^^^^^^^^^^^^^
/usr/lib/python3.12/pathlib.py:1164: in __init__
    super().__init__(*args)
/usr/lib/python3.12/pathlib.py:373: in __init__
    raise TypeError(
E   TypeError: argument should be a str or an os.PathLike object where __fspath__ returns a str, not 'NoneType'
```

Cause: the new millisecond subcase builds the production core with `run_root=None` and the production core does `Path(run_root)`: `TypeError: argument should be a str or an os.PathLike object ... not 'NoneType'`.  The adapter never ran.

### `tools/test_v0_s3_native_custody_correction10.py::test_n10_r07_the_context_of_the_round_reaches_every_layer`

```
tools/test_v0_s3_native_custody_correction10.py:1841: in test_n10_r07_the_context_of_the_round_reaches_every_layer
    assert queue_waits, \
E   AssertionError: the parent pump never waited for a frame of the round
E   assert []
```

Cause: the phase document `n10-r07-pump-current-minimum.json` records `queue_waits: []` and `reply_waits: []`: the transparent recorder of the queue of the channel and of the event of the reply was never called, so the real parent pump performed no further admission that the group could observe.

### `tools/test_v0_s3_native_custody_correction10.py::test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread`

```
tools/test_v0_s3_native_custody_correction10.py:2424: in test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread
    thread.join(5.0)
/usr/lib/python3.12/threading.py:1142: in join
    raise RuntimeError("cannot join thread before it is started")
E   RuntimeError: cannot join thread before it is started
```

Cause: the M08-C phase of the node **passed** (the phase document records the observations apart from the bounded waits and the waits cropped from 0.05 to 0.0099...), the node then failed later in the pre-existing M08-D part, which joins the thread of a step whose start never returned: `RuntimeError: cannot join thread before it is started`.

### `tools/test_v0_s3_native_custody_correction10.py::test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation`

```
tools/test_v0_s3_native_custody_correction10.py:3143: in test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation
    _m09_timeout_phase(document, plan, tmp_path,
tools/test_v0_s3_native_custody_correction10.py:2627: in _m09_timeout_phase
    assert isinstance(parallel, dict), \
E   AssertionError: the timeout did not stay a parallel fact of the failure
E   assert False
E    +  where False = isinstance(None, dict)
```

Cause: the first coordination schedule produced **real** evidence (`n10-r10-timeout-confirmed.json`: the parallel timeout of the original error object with the code BROKER_PIPE_TIMEOUT, the generation 3 and a null coordination error); the **second** schedule — the failed coordination — did not attach the parallel fact and the phase stopped there.

## 5. The phase statuses

Every phase document is written **before** the assertions of its phase.  A phase whose
assertion failed has **no** document and is `NOT_RUN`; the phases after a failed
assertion of the same node are `NOT_RUN` as well.

| Group | Status | The documents |
|---|---|---|
| the real chain of the round (F5) | **PRESENT** — all ten expected documents were written | `f5-close-cancellation.json`, `f5-first.json`, `f5-partial-frame-second.json`, `f5-partial-frame.json`, `f5-r02-millisecond-floor-recovery.json`, `f5-r02-millisecond-floor.json`, `f5-r09-completed-channel-first.json`, `f5-r09-completed-channel-second.json`, `f5-r09-raw-stream-first.json`, `f5-r09-raw-stream-second.json`, `f5-r13-launch-cleanup.json`, `f5-r13-launch-stop-during-hash-recovery.json`, `f5-r13-launch-stop-during-hash.json`, `f5-r13-launch-stop.json`, `f5-r13-stop-while-popen.json`, `f5-read-fault-second.json`, `f5-read-fault.json`, `f5-salvage.json`, `f5-second.json`, `f5-unrelated-cancellation-second.json`, `f5-unrelated-cancellation.json` |
| the N05 group (the new fault scenarios of M07-A.2) | **PRESENT** for the first two scenarios; the third scenario produced its first document and its recovery document and the node failed on the convergence of the table | `n05-r10-cancel-first-first.json`, `n05-r10-cancel-first-recovery.json`, `n05-r10-ordinary-then-cancel-first.json`, `n05-r10-ordinary-then-cancel-recovery.json`, `n05-r10-success-then-handle-first.json`, `n05-r10-success-then-handle-recovery.json` |
| the N10 group | **PRESENT** except the phases of the failed nodes | `n10-r01-first.json`, `n10-r01-second.json`, `n10-r02-claim.json`, `n10-r02-creation.json`, `n10-r02-handed-over.json`, `n10-r02-report.json`, `n10-r03-first.json`, `n10-r03-second.json`, `n10-r04-partial.json`, `n10-r04-release.json`, `n10-r05-adoption.json`, `n10-r05-bound-between-closes.json`, `n10-r05-bound-during-wait.json`, `n10-r05-bound-expired-repeat.json`, `n10-r05-bound-positive.json`, `n10-r05-final-recovery.json`, `n10-r05-owned-retry-recovery.json`, `n10-r05-owned-retry.json`, `n10-r05-recovery.json`, `n10-r05-retained-recovery.json`, `n10-r06-admission.json`, `n10-r06-expiry.json`, `n10-r06-linearization.json`, `n10-r07-launcher.json`, `n10-r07-pump-current-minimum.json`, `n10-r08-retry.json`, `n10-r09-await-wait.json`, `n10-r09-brokererror.json`, `n10-r09-interrupted-start.json`, `n10-r09-keyboardinterrupt.json`, `n10-r09-systemexit.json`, `n10-r10-coordination.json`, `n10-r10-first.json`, `n10-r10-second.json`, `n10-r10-timeout-confirmed-first.json`, `n10-r10-timeout-confirmed-second.json`, `n10-r10-timeout-confirmed.json`, `n10-r11-exact.json`, `n10-r11-first.json`, `n10-r11-frames.json`, `n10-r11-oversize.json`, `n10-r11-second.json`, `n10-r12-owner.json`, `n10-r12-stop.json`, `n10-r13-fault.json`, `n10-r13-partial.json`, `n10-r14-compatibility.json` |

### The M09 schedules

| Schedule | Status | Evidence |
|---|---|---|
| r10-published-before-timeout (the required order) | **NOT_RUN** — it follows the failed coordination schedule of the same node | no document |
| r10-timeout-confirmed (a confirmed coordination) | **REAL EVIDENCE** | `n10-r10-timeout-confirmed.json`, `n10-r10-timeout-confirmed-first.json`, `n10-r10-timeout-confirmed-second.json` |
| r10-timeout-failed (a failed coordination) | **NOT_RUN** — the parallel fact was not attached and the phase stopped | no document |

The interrupted-start join of N10-R09 was reached and it produced its phase document
(`n10-r09-interrupted-start.json`); the node failed later, in the join of the
never-started thread of the M08-D part.

## 6. What is not claimed

* No Stage PASS, no product acceptance, no native proof and no human signature.
* The sole remaining **M07** is **not** closed: it needs an independent source review
  **and** an actual validation.  **M08** remains source-closed only.
* The native behaviour, the native cleanup, the GPU, the port, the sampler, the parent
  crash recovery and the stdin EOF of Windows stay `NOT_PROVEN`.
* The historical counter continuity stays `UNAVAILABLE_NOT_PROVEN`.
* The failed candidate `b5e92af` and every artefact of this batch are preserved; there
  was no repair, no rerun and no self repair.
