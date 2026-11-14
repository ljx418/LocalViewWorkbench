# N1 correction 11: the table of the changed assertions

Every changed expectation is listed with the reason of the change and with the obligation that carries it.  No test was removed, no node was skipped, no denominator was shrunk and no assertion was replaced by a weaker one.

## `test_n03_r09_a_partial_windows_write_is_never_a_success`

* **the obligation**: N03-R09 / M08
* **the old expectation**: the fixture built the endpoint with ``_WindowsPipeEndpoint.__new__`` and assigned its attributes by hand
* **the new expectation**: the fixture builds the endpoint with the **real** constructor and with the injected primitives of the round
* **the reason**: The bypassed constructor never created the lock of the admission and the admission raised an ``AttributeError``.  The root forbids a fixture that bypasses the constructor without initialising the new invariant, and the production never receives a permissive admission.

## `test_n05_r04_a_cancellation_in_the_release_propagates_after_the_cleanup`

* **the obligation**: N05-R04 / m03
* **the old expectation**: the group asserted only the outcome of the pending pass
* **the new expectation**: the group asserts **added** that the close eligibility of the control handle is a callable over the original record and that the control handle is closed **exactly once**
* **the reason**: The eligibility was a frozen boolean and the pending pass could therefore never close the control handle of a process whose exit was confirmed later.  Every old assertion of the group is kept.

## `test_n05_r05_one_process_never_skips_the_wait_of_the_next_one`

* **the obligation**: N05-R05 / m03 + N10-R01
* **the old expectation**: ``assert not win32.live`` and ``assert core._pending.pending() == []`` after the first stop
* **the new expectation**: the expectation is **split by the actual facts**: the process whose exit was confirmed is closed exactly once, the process whose wait failed keeps its **original** control handle in its record and in the pending table with its owner, the round stays ``UNKNOWN_RETAINED``, the later process and the independent handles are released and the original error is preserved; a **recovery phase** proves the exit inside the **same** unextended deadline and closes the handle exactly once
* **the reason**: The blanket "every handle is closed" contradicted the obligation N10-R01: the control handle of a process whose exit was **not** confirmed may not be closed, because it is the only handle that may still stop that process.  The trigger, the node id and every original safety assertion are kept and the expectation is strengthened, not weakened.

## `test_n05_r11_no_role_is_created_or_resumed_after_the_deadline`

* **the obligation**: N05-R11 / m03 + N10-R01
* **the old expectation**: ``assert not win32.live`` in the scenario of the late creation
* **the new expectation**: the expectation is **split by the actual facts**: the control handle of the late process keeps its original reference and its owner and it is **not** closed, every other handle of the round is released, and the recovery of the same owner may not confirm the exit any more inside the same unextended deadline; the salvage of the owner of the test is recorded apart
* **the reason**: The late process was created after the lease of the round had expired, so the bounded wait of its exit never started and its exit was never confirmed.  The blanket expectation could not override the exit-confirmation safety and it is split by the facts.

## `test_n05_r14_an_await_that_is_running_reads_the_tightened_deadline`

* **the obligation**: N05-R14 / M08
* **the old expectation**: the fixture built the endpoint with ``__new__`` and the group entered the read without proving that it was admitted
* **the new expectation**: the fixture builds the endpoint with the **real** constructor, the request enters **unexpired**, the primitive-entered event is observed **before** the deadline is tightened and the group asserts that the lease of the round is never extended
* **the reason**: The root requires the group to begin with a real unexpired admitted request and to observe the real primitive-entered event before it tightens the deadline.  The initial expired refusal stays the separate obligation N10-R06 and it is not weakened.

## `test_n05_r20_the_closed_fact_is_committed_only_when_it_is_confirmed`

* **the obligation**: N05-R20 / M09
* **the old expectation**: the fixture built the endpoint with ``__new__``
* **the new expectation**: the fixture builds the endpoint with the **real** constructor
* **the reason**: The root forbids a fixture that bypasses the constructor of the endpoint.  No assertion was changed.

## `test_n07_r09_the_launcher_keeps_the_owner_of_the_process_and_the_channel`

* **the obligation**: N07-R09 / M07
* **the old expectation**: the group did not cover the close of the original handle of a process
* **the new expectation**: the group **adds** the M07 phase: the aggregate forgets the process only after the exit **and** the release of the original handle, a failed close keeps the process with its owner, the same owner retries **only** the incomplete part and the table of the launcher never resurrects a forgotten process
* **the reason**: The aggregate forgot the process on the exit alone and lost the recovery of a handle that could not be closed.

## `test_n10_r02_the_claim_of_the_recovery_and_the_handover_are_exclusive`

* **the obligation**: N10-R02 / M05
* **the old expectation**: the group covered only the pipes of the handover
* **the new expectation**: the group **adds** the M05 phase: the birth query of a created process blocks, the recovery of the facade claims the original entries, the return of the creation delivers **no** stale claimed handle to the core and there is exactly **one** closer of the original handle of the process
* **the reason**: The success of the creation and the direct cleanup of a failed creation bypassed the exclusive ownership protocol of the retained entries.

## `test_n10_r05_an_incomplete_channel_keeps_its_owner_and_the_cancel`

* **the obligation**: N10-R05 / M07
* **the old expectation**: the recovery phase expected ``order == ['channel', 'terminate', 'wait']``
* **the new expectation**: the recovery phase expects ``order == ['channel']`` and that the process is neither terminated nor waited a second time; a **distinct** phase with a still retained original handle proves that the recovery really retries the incomplete part
* **the reason**: The process of that launch was already **proved released** by the adoption phase, so the recovery coordinates the channel only.  The old expectation contradicted the ownership of the process; the still retained phase keeps the proof that the recovery retries.

## `test_n10_r06_an_expired_or_cancelled_call_performs_no_primitive_call`

* **the obligation**: N10-R06 / M08
* **the old expectation**: the group covered only the refusal at the entry of the call
* **the new expectation**: the group **adds** the linearization point: the request is admitted again after the readiness of the worker and immediately before the submission, and a cancellation or an expiry that is published before that admission causes **zero** primitive calls
* **the reason**: The check at the entry of the endpoint is not an atomic admission of the request and a request may not reach the worker after its admission was refused.

## `test_n10_r07_the_context_of_the_round_reaches_every_layer`

* **the obligation**: N10-R07 / M08
* **the old expectation**: the module of the group had **no import of the module subprocess** and the view of the module subprocess raised a NameError inside the launcher
* **the new expectation**: the import was added; no assertion of the group was changed
* **the reason**: The production launcher of the round was never reached: the view of the module subprocess asked for ``subprocess.PIPE`` and the name was not bound in the module of the group.

## `test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread`

* **the obligation**: N10-R09 / M08
* **the old expectation**: the three phases shared **one** deadline of the loop and the second phase inherited the budget that the first phase had consumed
* **the new expectation**: every phase is an **independent bounded scenario** with its own core, its own loop and its own deadline; the real result is published while the real thread is still alive and the join of every thread is unconditional
* **the reason**: The second phase was refused by the deadline of the round before its result was read.  No phase may borrow the expired budget of a previous phase.

## `test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation`

* **the obligation**: N10-R10 / M09
* **the old expectation**: the group covered the cancellation that arrives after the failure
* **the new expectation**: the group **adds** the coordination of a cancellation whose fault of the round is published **while** the coordination runs, and the auxiliary static proof that the outcome of the same generation is read before a new timeout is decided and again after the coordination
* **the reason**: The outcome selection was not unified across the cancellation, the timeout and the failed coordination: a new timeout or a failed coordination could hide the published failure of the generation.

