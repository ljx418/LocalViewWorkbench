# The persisted facts of the fifth failure of the N1 correction 08

This directory is the target of the group
`tools/test_v0_s3_native_custody_correction07.py::test_n07_r15_the_real_chain_is_coordinated_again_by_the_same_owner`.

The contract of the correction 08 requires the facts of the **first**
attempt, of the **second** attempt and of the **salvage** of the real chain
to be persisted as a bounded JSON document, and it requires them to be
written **before** the assertions of the phase: a group that fails has to
leave its evidence on the disk and it may never depend on the
representation of a failure of pytest.

The group writes three documents here:

| The document | It is written |
|---|---|
| `f5-first.json` | before the assertions of the first public stop |
| `f5-second.json` | before the assertions of the second public stop |
| `f5-salvage.json` | by the `finally` of the group, whatever the outcome was |

Every document is bounded and every value of it is the value that the
production returned.  Each document names the evidence of the round, the
facts of the close of the broker, the facts of the close of the channel,
the facts of the two endpoints of the channel with the identity of the
retained original handles of their threads, the state of every worker, the
ledger of the closes of the façade, the number of the targeted faults that
really fired and the original deadline of the cleanup.

The documents of a **failed** batch are evidence and they are never
deleted, never overwritten by a later run of the same batch and never
replaced by a summary.  The files of this directory are therefore part of
the raw evidence of the batch that writes them.
