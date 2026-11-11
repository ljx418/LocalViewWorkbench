# P2B correction-05 implementation — READY_FOR_REVIEW

Base `57373135ab629bcd08c429fd18477fb516c94dfb` merged fast-forward from a clean worktree; only the two authorized tools and this new evidence directory changed. The C05 contract pointer now matches root's already-frozen DRAFT child03. No child or contract was modified or activated.

Terminal publication now writes FINALIZING_NOT_PASS, stages the exact final bytes, writes both EXPIRED consumption references, strictly re-reads their hash/child/candidate identity and all artifacts, then uses one atomic replace as the last fallible success operation. No persistence, verification, or status-reversing step follows successful publication. Consumption result is TERMINAL_REFERENCE_NOT_DECISION: neither claim is itself a READY decision. The final index references only the initial RUNNING claim hash, avoiding a hash cycle.

Any finalization failure enters one bounded BLOCKED/UNPROVEN repair pass. A permanently unwritable shared claim retains its original exclusive RUNNING tombstone; local consumed is never a success decision. No unlink/refund/new identity or recursive retry was added. A failed repair is explicitly unproven, even if an older nonpassing index remains. terminal_persisted is a compatibility alias for terminal_index_persisted, which only attests persistence of the final returned decision; acceptance also requires READY status and finalization_proven. PROVEN with status BLOCKED remains a refusal. Internal schemas and all oracle migrations are enumerated in receipt.json; the public product API is unchanged.

Validation: final combination **237 passed / 0 failed / 0 skipped**, including all old 227 nodeids and 10 new public-run failure cases, exit 0, 179.60s. Fixed pure Parser.ParseInput ran once under allowance05, exit 0; no other exe was allowed. Guard denial events: 0. These guards are Python audit/Popen boundaries, not a claim of an OS sandbox. The source hashes in combined-command.json match the final files.

Intermediate evidence is retained, not rewritten: directed had 19 contract-seal setup failures because the tool initially still named C04 after root migrated child03; directed2 had 18 passing / 1 failing due to the synthetic afterwrite label being incorrectly treated as a before-write permanent fault. The test injector was corrected; early-index permanent injection was strengthened to reject both writes and all-storage injection to reject cleanup-detail persistence too. directed3 passed all three affected cases. Only the final combination establishes complete final-candidate coverage; directed2 reflects its loaded intermediate test code, not the final source fingerprint.

The maximum positive chain retains normal/bad-receipt/timeout, six 160-sample four-owner traces, exact three stdout captures of 262144 bytes and stderr captures of 256000 bytes, including non-UTF8 data. Recomputed refs: 22; detail bytes: 4513811; evidence tree logical bytes: 4522928; two fixture logical bytes: 296286. Recomputed logical bytes stay below 16MiB; this is not disk block allocation or cumulative disk I/O. 32KiB controls, 1MiB detail, 16KiB terminal, 8MiB detail reserve, 64KiB terminal reserve and existing nonrefundable counters remain unchanged.

Failure matrix (all run the public owner with real synthetic factory/role/admission/SQLite, at most three substituted host phases):

| Fault | Return | Canonical disk | Shared | Local | Finalization proven |
|---|---|---|---|---|---|
| all-permanent | BLOCKED | absent | RUNNING | absent | False |
| early-permanent | BLOCKED | absent | RUNNING | absent | False |
| early-transient | BLOCKED | BLOCKED | EXPIRED | EXPIRED | False |
| local-permanent | BLOCKED | BLOCKED | EXPIRED | absent | False |
| local-transient | BLOCKED | BLOCKED | EXPIRED | EXPIRED | False |
| publish-permanent | BLOCKED | BLOCKED | EXPIRED | EXPIRED | False |
| publish-transient | BLOCKED | BLOCKED | EXPIRED | EXPIRED | False |
| shared-afterwrite | BLOCKED | BLOCKED | EXPIRED | EXPIRED | False |
| shared-permanent | BLOCKED | BLOCKED | RUNNING | EXPIRED | False |
| shared-transient | BLOCKED | BLOCKED | EXPIRED | EXPIRED | False |

Each new oracle saves returned state, disk index, both consumption states, terminal hash, attempted write sequence and phase count before asserting. All late-failure cases retain phase1 and observed debit=1; all-storage failure is injected only after already-persisted phases and independently prevents cleanup-detail plus every terminal control write. It does not pretend historical evidence can be recreated. Pure read-only verify.py rechecks raw artifacts and exact capture-byte conservation, plus nodeid retention, without following saved runtime paths or changing decisions.

All new owned test roots are removed; each public case has a serializable cleanup observation and each runner records its basetemp deletion. The 19 final public cases have 38 per-fixture textual inventories before deletion. No new SQLite/source binary archive was committed; historical archives and raw remain untouched. New raw, receipts, scripts, commands, stderr and counts are retained directly as text. Uncommitted terminal-candidate files in failure raw are forensic staging files, never canonical decisions.

Ten-field handoff: (1) R1 / WP-R1-U3 / S3_P2B_FINALIZATION_PUBLICATION_CONSISTENCY; (2) localized terminal publication fix; (3) last accepted slice remains 621b1bf386db71bfe08ca2f533fa8ec396b0504b; (4) C04 M1 awaits independent closure; (5) target V1, old S2 7/8 unchanged; (6) independent review/root decision remain; (7) next owner coordinator and independent reviewer; (8) no new actual authorization or human signature requested; (9) this receipt, verification and raw form the evidence; (10) implementation stops READY_FOR_REVIEW, no Stage/Gate0/quality/human/release signoff.

Development outline from unchanged execution-control: V0 V0-S0 1/2; V0-Min V0-S1 5/5; V1前置 R0 1/2; V1早期切片 R1a 5/5; V0.1 V0-S2 7/8; V0.2 V0-S3 0/6; V1 R1 0/4; V1 V1-M1 0/3; V1 R2 0/4; V2 R3 0/4; V2 R4 0/4; V3 R5a 0/4; V3 R5b 0/4; V3 R5c 0/4

Implementation submitted for review; machine tests passed; independent review pending; human signoff not added.
