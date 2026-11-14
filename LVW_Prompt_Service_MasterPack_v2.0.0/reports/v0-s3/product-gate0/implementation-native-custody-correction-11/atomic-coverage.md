# N1 correction 11: the atomic coverage of the 72 frozen obligations

The 72 atoms of the four inherited groups (N03 16, N05 24, N07 18, N10 14) are kept with their **exact** ids.  No atom was replaced, no atom was dropped and no group was renamed.  The column "the change of the correction 11" names the strengthening that the correction 11 carried inside that very node; the empty cells are the atoms whose node and production path were **not** touched by this correction.

The dynamic status of every atom stays the one of the isolated pre review of the correction 10 (`CLOSED_STATIC` / `OPEN` / `UNCERTAIN`).  This delivery closes **no** Major and it signs **no** Stage.

| atom | major | the node that carries it | the change of the correction 11 |
|---|---|---|---|
| N03-R01 | M03 | `test_n03_r01_a_failed_birth_keeps_the_original_handles_with_the_api` | NONE |
| N03-R02 | M03 | `test_n03_r02_a_failed_cleanup_of_the_creation_still_releases_everything` | NONE |
| N03-R03 | M04 | `test_n03_r03_the_job_query_is_unknown_whenever_a_fact_does_not_agree` | NONE |
| N03-R04 | M05 | `test_n03_r04_a_job_that_could_not_be_closed_keeps_its_original_handle` | NONE |
| N03-R05 | M06 | `test_n03_r05_the_stop_runs_every_cleanup_after_an_ordinary_failure` | NONE |
| N03-R06 | M07 | `test_n03_r06_the_start_cleans_up_everything_that_it_acquired` | NONE |
| N03-R07 | M08 | `test_n03_r07_the_startup_is_bounded_by_the_absolute_deadline` | NONE |
| N03-R08 | M08 | `test_n03_r08_the_cleanup_of_the_broker_uses_one_absolute_deadline` | NONE |
| N03-R09 | M08/M09 | `test_n03_r09_a_partial_windows_write_is_never_a_success` | The fixture builds the endpoint with its **real** constructor and with the injected primitives: the lock of the admission is really initialised and the admission is never a permissive fallback.  No assertion was removed. |
| N03-R10 | M08 | `test_n03_r10_the_cancellation_of_a_worker_stops_it_from_entering_io` | NONE |
| N03-R11 | M08 | `test_n03_r11_a_failure_of_the_background_latches_the_unknown_state` | NONE |
| N03-R12 | M08 | `test_n03_r12_the_frame_budget_is_the_total_of_both_directions` | NONE |
| N03-R13 | M08 | `test_n03_r13_the_buffer_of_the_channel_is_bounded_and_a_partial_frame_is_named` | NONE |
| N03-R14 | M09 | `test_n03_r14_a_close_without_facts_keeps_the_original_broker` | NONE |
| N03-R15 | M11 | `test_n03_r15_the_default_launcher_refuses_with_its_own_code` | NONE |
| N03-R16 | all | `test_n03_r16_the_positive_lifecycle_still_closes_everything` | NONE |
| N05-R01 | M03 | `test_n05_r01_the_null_device_has_an_owner_from_the_moment_of_its_creation` | NONE |
| N05-R02 | M03 | `test_n05_r02_a_cancellation_in_the_cleanup_never_skips_the_other_finalizers` | NONE |
| N05-R03 | M05 | `test_n05_r03_the_ends_of_a_pipe_are_owned_from_the_moment_of_their_creation` | NONE |
| N05-R04 | M06 | `test_n05_r04_a_cancellation_in_the_release_propagates_after_the_cleanup` | The eligibility of the control handle is proved to be a **callable** over the original record and the control handle is proved to be closed **exactly once**.  Every old assertion is kept. |
| N05-R05 | M06 | `test_n05_r05_one_process_never_skips_the_wait_of_the_next_one` | The blanket "every handle of the round is closed" is **split by the actual facts**: the confirmed process is closed once, the unconfirmed control handle keeps its owner and its pending entry, the later processes and the independent handles are released and the original error is preserved.  A recovery phase proves the exit inside the **same** unextended deadline. |
| N05-R06 | M06 | `test_n05_r06_a_reader_that_never_started_is_never_joined` | NONE |
| N05-R07 | M07 | `test_n05_r07_a_background_start_that_did_not_return_keeps_its_owner` | NONE |
| N05-R08 | M07 | `test_n05_r08_a_start_that_raised_after_the_thread_started_keeps_the_thread` | NONE |
| N05-R09 | M07 | `test_n05_r09_a_closer_that_could_not_start_does_not_latch_the_round` | NONE |
| N05-R10 | M07 | `test_n05_r10_a_launch_that_could_not_be_handed_over_keeps_its_resources` | NONE |
| N05-R11 | M08 | `test_n05_r11_no_role_is_created_or_resumed_after_the_deadline` | The blanket "every handle of the round is closed" is **split by the actual facts**: the control handle of the late process keeps its original reference and its owner, every other handle is released and the recovery of the same owner may not extend the deadline. |
| N05-R12 | M08 | `test_n05_r12_the_cleanup_deadline_is_published_once_and_never_extended` | NONE |
| N05-R13 | M08 | `test_n05_r13_the_remaining_budget_is_recomputed_before_every_wait` | NONE |
| N05-R14 | M08 | `test_n05_r14_an_await_that_is_running_reads_the_tightened_deadline` | The fixture builds the endpoint with its **real** constructor; the request enters **unexpired**, the primitive-entered event is observed **before** the deadline is tightened and the lease of the round is never extended. |
| N05-R15 | M08 | `test_n05_r15_the_worker_coordinates_by_generation_and_keeps_its_handle` | NONE |
| N05-R16 | M08 | `test_n05_r16_the_unknown_state_is_latched_atomically` | NONE |
| N05-R17 | M08 | `test_n05_r17_the_frame_budget_has_one_owner_in_both_directions` | NONE |
| N05-R18 | M08 | `test_n05_r18_the_terminal_exchange_consumes_its_reservation` | NONE |
| N05-R19 | M09 | `test_n05_r19_the_unconfirmed_items_are_coordinated_again` | NONE |
| N05-R20 | M09 | `test_n05_r20_the_closed_fact_is_committed_only_when_it_is_confirmed` | The fixture builds the endpoint with its **real** constructor.  No assertion was changed. |
| N05-R21 | M09 | `test_n05_r21_the_endpoint_is_the_only_owner_of_the_files_of_the_channel` | NONE |
| N05-R22 | M09 | `test_n05_r22_the_strict_facts_of_the_close_are_required` | NONE |
| N05-R23 | M09 | `test_n05_r23_the_end_of_the_attempt_and_the_end_of_the_closer_are_two_facts` | NONE |
| N05-R24 | compatibility | `test_n05_r24_the_closed_items_and_the_frozen_groups_are_kept` | NONE |
| N07-R01 | M03 | `test_n07_r01_the_control_handle_of_an_unconfirmed_process_is_kept` | NONE |
| N07-R02 | M03 | `test_n07_r02_the_recovery_keeps_the_handle_until_the_exit_is_confirmed` | NONE |
| N07-R03 | M05 | `test_n07_r03_a_pipe_that_was_handed_over_has_exactly_one_owner` | NONE |
| N07-R04 | M05 | `test_n07_r04_the_ends_of_a_pipe_are_cleaned_up_independently` | NONE |
| N07-R05 | M06 | `test_n07_r05_the_read_end_of_a_live_reader_is_never_closed` | NONE |
| N07-R06 | M06 | `test_n07_r06_the_cancellation_of_a_wait_reaches_the_top` | NONE |
| N07-R07 | M06 | `test_n07_r07_the_recovery_of_a_record_synchronises_the_tables` | NONE |
| N07-R08 | M07 | `test_n07_r08_the_endpoint_owns_its_worker_before_the_start` | NONE |
| N07-R09 | M07 | `test_n07_r09_the_launcher_keeps_the_owner_of_the_process_and_the_channel` | The M07 phase was added: the aggregate forgets the process only after the exit **and** the release of the original handle, the same owner retries only the incomplete part and the table of the launcher never resurrects a forgotten process. |
| N07-R10 | M07 | `test_n07_r10_a_closer_whose_start_did_not_return_is_unknown` | NONE |
| N07-R11 | M08 | `test_n07_r11_the_cancellation_of_a_worker_is_repeated_and_bounded` | NONE |
| N07-R12 | M08 | `test_n07_r12_every_segment_of_a_partial_write_reads_the_latest_deadline` | NONE |
| N07-R13 | M08 | `test_n07_r13_every_side_effect_checks_the_shared_context` | NONE |
| N07-R14 | M08 | `test_n07_r14_the_startup_owner_releases_its_owner_after_the_real_exit` | NONE |
| N07-R15 | M09 | `test_n07_r15_the_real_chain_is_coordinated_again_by_the_same_owner` | NONE |
| N07-R16 | M09 | `test_n07_r16_the_endpoint_recomputes_the_state_of_its_workers` | NONE |
| N07-R17 | M09 | `test_n07_r17_the_second_generation_of_the_close_has_its_own_event` | NONE |
| N07-R18 | M09 | `test_n07_r18_the_first_public_stop_waits_for_the_real_closer` | NONE |
| N10-R01 | M03 | `test_n10_r01_the_control_handle_is_closed_only_after_the_exit` | NONE |
| N10-R02 | M05 | `test_n10_r02_the_claim_of_the_recovery_and_the_handover_are_exclusive` | The M05 phase was added: the creation of a process and the recovery of the facade are **one** ownership decision, there is exactly **one** closer of the original handle and no stale claimed handle is delivered to the core. |
| N10-R03 | M06 | `test_n10_r03_every_confirmed_close_notifies_the_owner_of_the_handle` | NONE |
| N10-R04 | M07 | `test_n10_r04_the_launch_aggregate_finds_the_partial_channel` | NONE |
| N10-R05 | M07 | `test_n10_r05_an_incomplete_channel_keeps_its_owner_and_the_cancel` | The recovery phase is **split by the actual facts**: an already proved released process is not terminated and not waited a second time, and a distinct **still retained** phase proves that the recovery really retries the incomplete part. |
| N10-R06 | M08 | `test_n10_r06_an_expired_or_cancelled_call_performs_no_primitive_call` | The linearization point of the admission was added: a cancellation and an expiry that are published **before** the final admission cause **zero** primitive calls. |
| N10-R07 | M08 | `test_n10_r07_the_context_of_the_round_reaches_every_layer` | The fixture of the group had **no import of the module subprocess** and the view of the module raised a NameError before the launcher was ever reached.  The import was added; no assertion was changed. |
| N10-R08 | M08 | `test_n10_r08_the_retry_of_a_cancellation_re_reads_the_context` | NONE |
| N10-R09 | M08 | `test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread` | The three phases are **independent bounded scenarios**: every phase has its own core, its own loop and its own deadline and no phase borrows the expired budget of a previous phase. |
| N10-R10 | M09 | `test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation` | The outcome of the **same** generation is inspected **again** after the coordination of the cancellation and the auxiliary static proof of the order of the two facts was added. |
| N10-R11 | M09 | `test_n10_r11_the_overflow_of_the_channel_is_a_named_failure` | NONE |
| N10-R12 | test-causality | `test_n10_r12_the_reader_publishes_its_wait_before_it_waits` | NONE |
| N10-R13 | M09 | `test_n10_r13_the_fault_is_unlocked_by_the_owner_and_observed_first` | NONE |
| N10-R14 | compatibility | `test_n10_r14_the_closed_obligations_of_the_package_do_not_regress` | NONE |

