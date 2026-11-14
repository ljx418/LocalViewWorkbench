# The persisted facts of the fifth failure of the N1 correction 09

This directory is the target of the group
`tools/test_v0_s3_native_custody_correction07.py::test_n07_r15_the_real_chain_is_coordinated_again_by_the_same_owner`.

The contract of the correction 08 requires the facts of the **first**
attempt, of the **second** attempt and of the **salvage** of the real chain
to be persisted as a bounded JSON document, and it requires them to be
written **before** the assertions of the phase: a group that fails has to
leave its evidence on the disk and it may never depend on the
representation of a failure of pytest.

**The documents of this directory do not exist yet.**  Nothing was run:
the batch of the root was not executed and the group was never called.
The table below is the list of the **expected product paths** of the next
batch and it is **not** a list of facts that were observed.  The only file
of this directory that exists today is this note.

The group writes its documents here:

| The document | It is written | Its state today |
|---|---|---|
| `f5-first.json` | before the assertions of the first public stop | `NOT_RUN` |
| `f5-second.json` | before the assertions of the second public stop | `NOT_RUN` |
| `f5-salvage.json` | by the `finally` of the group, whatever the outcome was | `NOT_RUN` |
| `f5-close-cancellation.json` | before the assertions of the first bounded sub scenario (the cancellation that the close really initiated) | `NOT_RUN` |
| `f5-unrelated-cancellation.json` | before the assertions of the second bounded sub scenario (a cancellation of another owner) | `NOT_RUN` |
| `f5-unrelated-cancellation-second.json` | before the assertions of the **second** public stop of the second bounded sub scenario | `NOT_RUN` |
| `f5-read-fault.json` | before the assertions of the third bounded sub scenario (an ordinary failure of the read) | `NOT_RUN` |
| `f5-read-fault-second.json` | before the assertions of the **second** public stop of the third bounded sub scenario | `NOT_RUN` |
| `f5-partial-frame.json` | before the assertions of the fourth bounded sub scenario (a frame that never ends) | `NOT_RUN` |
| `f5-partial-frame-second.json` | before the assertions of the **second** public stop of the fourth bounded sub scenario | `NOT_RUN` |

Every document is bounded and every value of it is the value that the
production returned.  Each document names the evidence of the round, the
facts of the close of the broker, the facts of the close of the channel,
the facts of the two endpoints of the channel with the identity of the
retained original handles of their threads, the state of every worker, the
ledger of the closes of the façade, the number of the targeted faults that
really fired and the original deadline of the cleanup.

The document of the second bounded sub scenario carries **one** more
bounded fact: the confirmation of the external owner of the cancel flag
(`external_cancel_owner`).  It names the confirmation that was published,
the fact that the flag was really set, the origin of the cancellation that
the flag really names (`null`), the fact that the reader of the chain was
really inside its read and the identity of the exact thread of the owner.

The three documents of the **second** public stop of the sub scenarios that
carry a real error of the reader carry the **history** of that error: the
error of the reader is the history of the round, a repeated close may never
turn it into a `None` and the broker of the round may never be released
because the second attempt copied the facts of the first one.

## The five real documents of the correction 08 are not here

The failed batch of the correction 08 really wrote **five** of the ten
documents and it stopped at the failed assertion of the second bounded sub
scenario.  Those five documents live in the directory of the **correction
08**
(`implementation-native-custody-correction-08/f5-evidence/`) and they are
**never** overwritten, never deleted and never replaced by a summary.  The
diagnostics of the correction 09 are written in **this** directory and the
two directories are never mixed.

The five documents that the failed batch did not write are missing because
the batch stopped:

| The document | Its state in the failed batch of the correction 08 |
|---|---|
| `f5-unrelated-cancellation-second.json` | **not written**: the group stopped at the first assertion of that sub scenario |
| `f5-read-fault.json` | **not written**: the group stopped before that sub scenario |
| `f5-read-fault-second.json` | **not written** |
| `f5-partial-frame.json` | **not written** |
| `f5-partial-frame-second.json` | **not written** |

The missing phases are **five documents** and not the four sub scenarios of
the group: the second public stop of the sub scenario of the unrelated
owner is a document of its own.  The four sub scenarios of the group are
not the count of the missing files.

The documents of a **failed** batch are evidence and they are never
deleted, never overwritten by a later run of the same batch and never
replaced by a summary.  The files of this directory are therefore part of
the raw evidence of the batch that writes them.
