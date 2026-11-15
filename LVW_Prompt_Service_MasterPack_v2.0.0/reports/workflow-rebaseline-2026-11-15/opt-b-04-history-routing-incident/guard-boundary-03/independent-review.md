# Boundary03 minimum compatibility source review

READY for rootACK of exactly one pinned owncanary feedback attempt; Fatal0 / Major0 / Minor0 in this narrow revision. This is a source-readiness judgment, not runtimeACK, candidate readiness, F06-M2 dynamic closure, N2 or Stage clearance. No guard/canary/candidate was executed, imported, compiled or collected.

## Binding and delta

Plan SHA256 `a41b5f6082ddfb005991e0686bd5dfae8801b72031f10e4a7f4a8a8ea80fb005` matches the dispatched pin. All3 plan pins match; base02 guard SHA256 `f2f97d2d1191112f60b170b9a0bf69ed5c4ab569f1bffef5903c1ec28a6d6d6c` matches scope. Scope SHA256 `2f0afc6fde281ec8349628caabf23542bb12f28ac05af370f3af72edebe652b3`. Exact source/tool hashes, labels, paths and delta counts are in source-binding.json. The planned selftest-01 parent is absent at review; root must recheck before admission. Review compares only boundary02 to03 and the unchanged hard-veto callsite; concurrent implementation changes were not read or modified. Prior c2c0880/raw and all earlier reports remain unchanged.

Guard03 `b25b640fd0b66cc5d6aba066e0e83eb5f4f310dc423dd421d094d0f34d5b694c`; payload `00790a0d42dab9fb304e2243b77a328254de62daab30f86e72773930a2f5a692`; launcher `77cc3b5168abd87167031a795631d4b184d96f4afe4df797313487451f0e47cf`.

## Actual control flow assessed

At guard.py:82-132, symlink audit takes the dedicated narrow branch. Nondefault dirfd is rejected, including absolute-source calls with an explicit descriptor. Both operands reject lexical '..'; destination must be a direct child of canonical NEW R/pytest-temp. Relative source is a basename resolved against that link parent. Absolute source must be a direct sibling. Destination requires nonempty prefix+'current'; source is that prefix plus nonempty ASCII decimal suffix. Parent/source lstat must be directories and neither can be a symlink; realpath(parent) must equal lexical parent. Cached parent device/inode cannot change after first admission. Existing destination, including dangling symlink, is refused. Both source/destination then pass unchanged writable/root identity checks. This permits pytest's expected direct numbered/current siblings without generic symlink permissions. Subsequent operations still traverse original writable containment/hardlink checks; outside rename destinations remain refused.

At41-47, normal three-argument symlink policy denials retain complete structured source/destination/dirfd alongside the old clipped summary. At124-126, admission records retain resolved target and parent identity. These are **admission** records before actual OS creation, not proof that symlink creation succeeded. Helper-generated writable/rootidentity failures may still retain only the failing path; no complete caller-stack or universal syscall logging claim is made.

Generic mutation branches, exact literal /dev/null character-device identity allowance, relative write-open dirfd refusal, singleton preload controls and candidate outer denial veto are unchanged. Unchanged validator:23-27 rejects missing/non-list or any nonempty runtime ledger before runner success claims. The18 expected owncanary denials are an isolated negative selftest allowance, never a candidate whitelist. Old106 denials and rejected feedback06 remain rejected.

## Canary calls and cleanup

Independent text/control-flow count is18 real rejected operations plus5 positive/cleanup checks =23 payload checks. Original11/9 is preserved; two actual symlink operations add absolute alias write/read/remove and basename-relative alias resolve. New9 denials exercise outside target, outside destination, nested source parent, mismatched prefix, missing numbered directory, regular-file target, destination beneath a symlink, explicit dirfd and traversal. Existing destination, source symlink leaf and replaced parent are statically checked but have no dedicated new operation in these23; the canary does not claim exhaustive branch coverage. The destination-under-symlink case is rejected by the direct-parent predicate before canonical-parent checks, which is sufficient for its stated safety oracle.

The aliases and all newly created dirs/files are owned setup data. Payload86 uses real shutil.rmtree on ownedpytesttree and records its absence; stdlib rmtree uses directory descriptors for removals and does not recurse through symlinks. Original writable resolves relative removal anchors by fd; readonly dirfd opens remain supported. Setup cleanup in launcher50-60 removes only owned escape/hardlink/outside, then the empty owned directory. File descriptors opened by the canary have try/finally os.close. No candidate lifecycle is substituted, because this canary has no candidate lifecycle at all.

Launcher source differs only in expected counts23/18. It checks exit0, all passed, outside bytes unchanged,8 startup denial probes (separate from18), guard ledger explicitly nonclean for this selftest, and unchanged pins. It creates a fresh parent with exist_ok=False. It still copies inherited environment plus owncanary vars; this is unchanged and is not the candidate's future frozen replacement environment. Child subprocess timeout is20s,1batch/0retry; setup/postchecks are outside that timeout, so no claim of an independent end-to-end20s kill bound.

Inherited setup-before-try/finally and cleanup-failure limitations remain: a setup error can leave artifacts without a receipt; a failing unlink can interrupt finally. The passed flag is set before cleanup and is insufficient alone. Root must reject missing/unknown cleanup even if a success field exists. Owncanary supplies no FD/thread inventory or candidate singleton-preload CLOSED proof; it cannot clear those future requirements. Check/use races, inherited descriptors, direct native writes and adversarial tampering remain outside this cooperative Python policy, with no OS sandbox claim.

## Required actual oracle and exit

After rootACK only, the precise pinned entry may run once with no retry and the frozen20s childtimeout. Root must consume actual outer/guard/payload receipts, exact23 labels/all outcomes,18 expected runtime denials with full structured operands and8 separate startup probes, exactly2 alias admissions correlated with completed payload operations, outside unchanged, ownedpytesttree absent, all3 setupcanaries removed, child termination and unchanged postpins. Missing receipts, mismatched labels/operands, extra denials/admissions or unknown cleanup are not PASS. The20s owncanary is finite feedback under ADR16 O1, not runtime permission issued by this reviewer.

F06-M2 remains OPEN pending actual canary and separately frozen cooperative candidate feedback with a genuinely empty ordinary runtime ledger. Nothing in this source review accepts the earlier106 operations, closes the other four c2c0880 Majors/incident, endorses a checkpoint or establishes product29/9 native unknowns. Necessary next owner is root for exactACK and evidence adjudication; implementation scope remains separate.

## Full V0–V3 outline

From authoritative execution-control: V0-S0 1/2; V0-S1 5/5; R0 1/2; R1a 5/5; V0-S2 7/8; V0-S3 0/6; R1 0/4; V1-M1 0/3; R2 0/4; R3 0/4; R4 0/4; R5a 0/4; R5b 0/4; R5c 0/4. Current R1/WP-R1-U3/S3_P4; fullR1 remains0/4. Unified-media early slice alone has prior UM10 machine/independent acceptance and actual human signoff. S2 is7/8 with its historical signoff boundary unchanged. No implementation, machine acceptance or human status is advanced by this review.

## Ten fields

1. Coordinate: V1 / R1 / WP-R1-U3 / S3_P4, root-harness compatibility subtask.
2. Last passed scope: prior unified-media UM10 early slice, not fullR1.
3. Current batch: source-only boundary03 versus02 review complete, owncanary not run here.
4. Blockers: none for precise rootACK owncanary feedback; F06-M2 formal/runtime exit and other c2c0880 findings/incident remain OPEN.
5. Route: ADR16 O1 single bounded owncanary, then separate evidence review/freeze before candidate feedback.
6. Remaining: actual23/18 receipts, complete operands/alias facts, clean owned cleanup and postpins; no automatic candidate clearance.
7. Next owner: root for ACK/execution adjudication; ClaudeCode concurrent test corrections remain independent.
8. Authority: this reviewer issues neither runtimeACK nor candidate/Stage/N2 clearance.
9. Evidence: review.md, findings.json and source-binding.json in this new directory; exact root boundary03 pins above.
10. Stop: READY_FOR_ROOT_ACK_OWNCANARY_FEEDBACK_ONLY; implementation source prepared, runtime PENDING, independent source review F0/M0/m0, human/product/native acceptance not supplied.
