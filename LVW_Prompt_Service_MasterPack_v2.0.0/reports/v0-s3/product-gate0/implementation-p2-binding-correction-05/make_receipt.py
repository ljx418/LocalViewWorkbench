"""Build the handoff from observed test receipts and read-only artifact verification."""
import hashlib, json
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
load=lambda name:json.loads((OUT/name).read_text())
combined=load('combined-receipt.json');verification=load('verification.json')
assert combined['exit']==0 and combined['removed'] and combined['parser_invocations']==1
parser=load('combined-parser.json');assert len(parser)==1 and parser[0]['exit']==0
assert sum(len(x.encode()) for x in parser[0]['argv'])+len(parser[0]['stdout'].encode())+len(parser[0]['stderr'].encode())<=65536
assert not combined['denied']
sources={s:hashlib.sha256((ROOT/s).read_bytes()).hexdigest() for s in ('tools/v0_s3_runtime_binding.py','tools/test_v0_s3_runtime_binding.py')}
assert sources==load('combined-command.json')['source_hashes']
control=json.loads((ROOT/'plans/execution-control.json').read_text())
outline=[dict(stage_id=x['stage_id'],delivery=x['delivery'],completed=x['completed_substeps'],total=x['total_substeps']) for x in control['development_outline']]
receipt=dict(status='READY_FOR_REVIEW',base='57373135ab629bcd08c429fd18477fb516c94dfb',source_hashes=sources,
    final_tests=237,retained_old_nodeids=227,new_failure_matrix=10,verification='verification.json',
    test_runs={p:load(p+'-receipt.json') for p in ('directed','directed2','directed3','combined')},
    actual_driver_calls=0,wsl_calls=0,host_executable_hash_reads=0,real_claim_accesses=0,mother_ledger_accesses=0,
    old_roots_or_pids_accessed=0,media_gpu_models_services_network_download_checkpoint=0,
    parser_invocations=1,actual03='DRAFT_NOT_AUTHORIZED',coordinate=control['coordinate'],development_outline=outline,
    schema=dict(terminal='lvw.p2b-terminal/3',consumption='lvw.p2b-consumption/2',
        result='TERMINAL_REFERENCE_NOT_DECISION',terminal_path='absolute canonical index path',
        terminal_persisted='compatibility alias: final returned decision index was successfully persisted; never sufficient for acceptance',
        terminal_index_persisted='the final returned decision index was persisted; if repair failed an older FINALIZING index may still exist',
        finalization_proven='both consumption references and artifacts read-verified before the final atomic index publication; false after finalization faults',
        claim_finalization='PROVEN or UNPROVEN; independent of status, so a proven BLOCKED group is still a refusal'),
    oracle_migrations=[
        'All 227 previous pytest nodeids retained; successful EXPIRED claim still must hash the exact canonical terminal bytes.',
        'Public maximum helper extracted without changing nine existing test IDs or their phase/debit/capacity/ref rejection obligations.',
        'Added local EXPIRED/hash check and finalization_proven to all old public chains; consumption result cannot equal READY_FOR_REVIEW.',
        'New UNPROVEN fallback branches may retain original RUNNING shared claim; this is tested only for injected finalization faults, not used to weaken old successful-chain EXPIRED assertions.',
        'Factory binary/source copies replaced by per-file textual size/hash inventory before cleanup; required raw command/observer/phase/life data retained.'
    ],risks=[
        'Synthetic Linux factory/SQLite and host-boundary replacements only; no actual Windows/WSL/resource/product evidence.',
        'Unwritable storage can leave no final index or an older FINALIZING index; return is BLOCKED/UNPROVEN and original capacity is never refunded.',
        'An uncommitted terminal-candidate.json can remain after failure; only canonical cross-os-lifecycle.json plus verified references can authorize review success.',
        'A crash between reference writes and final publication leaves FINALIZING, not success; no automatic retry, identity reset, or recovery activation is implemented.',
        'Independent review and root decision are pending; no Stage/Gate0/quality/human/release signature.'
    ])
(OUT/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
rows=verification['cases'];success=next(x for x in rows if x['case']=='None')
text=f'''# P2B correction-05 implementation — READY_FOR_REVIEW

Base `{receipt['base']}` merged fast-forward from a clean worktree; only the two authorized tools and this new evidence directory changed. The C05 contract pointer now matches root's already-frozen DRAFT child03. No child or contract was modified or activated.

Terminal publication now writes FINALIZING_NOT_PASS, stages the exact final bytes, writes both EXPIRED consumption references, strictly re-reads their hash/child/candidate identity and all artifacts, then uses one atomic replace as the last fallible success operation. No persistence, verification, or status-reversing step follows successful publication. Consumption result is TERMINAL_REFERENCE_NOT_DECISION: neither claim is itself a READY decision. The final index references only the initial RUNNING claim hash, avoiding a hash cycle.

Any finalization failure enters one bounded BLOCKED/UNPROVEN repair pass. A permanently unwritable shared claim retains its original exclusive RUNNING tombstone; local consumed is never a success decision. No unlink/refund/new identity or recursive retry was added. A failed repair is explicitly unproven, even if an older nonpassing index remains. terminal_persisted is a compatibility alias for terminal_index_persisted, which only attests persistence of the final returned decision; acceptance also requires READY status and finalization_proven. PROVEN with status BLOCKED remains a refusal. Internal schemas and all oracle migrations are enumerated in receipt.json; the public product API is unchanged.

Validation: final combination **237 passed / 0 failed / 0 skipped**, including all old 227 nodeids and 10 new public-run failure cases, exit 0, {combined['elapsed']:.2f}s. Fixed pure Parser.ParseInput ran once under allowance05, exit 0; no other exe was allowed. Guard denial events: {len(combined['denied'])}. These guards are Python audit/Popen boundaries, not a claim of an OS sandbox. The source hashes in combined-command.json match the final files.

Intermediate evidence is retained, not rewritten: directed had 19 contract-seal setup failures because the tool initially still named C04 after root migrated child03; directed2 had 18 passing / 1 failing due to the synthetic afterwrite label being incorrectly treated as a before-write permanent fault. The test injector was corrected; early-index permanent injection was strengthened to reject both writes and all-storage injection to reject cleanup-detail persistence too. directed3 passed all three affected cases. Only the final combination establishes complete final-candidate coverage; directed2 reflects its loaded intermediate test code, not the final source fingerprint.

The maximum positive chain retains normal/bad-receipt/timeout, six 160-sample four-owner traces, exact three stdout captures of 262144 bytes and stderr captures of 256000 bytes, including non-UTF8 data. Recomputed refs: {success['refs']}; detail bytes: {success['detail_bytes']}; evidence tree logical bytes: {success['tree_bytes']}; two fixture logical bytes: {success['factory_bytes']}. Recomputed logical bytes stay below 16MiB; this is not disk block allocation or cumulative disk I/O. 32KiB controls, 1MiB detail, 16KiB terminal, 8MiB detail reserve, 64KiB terminal reserve and existing nonrefundable counters remain unchanged.

Failure matrix (all run the public owner with real synthetic factory/role/admission/SQLite, at most three substituted host phases):

| Fault | Return | Canonical disk | Shared | Local | Finalization proven |
|---|---|---|---|---|---|
'''
for x in rows:
    if x['case'] not in ('shared-permanent','shared-transient','shared-afterwrite','local-permanent','local-transient','publish-permanent','publish-transient','early-permanent','early-transient','all-permanent'):continue
    text+=f"| {x['case']} | {x['status']} | {x['disk_status'] or 'absent'} | {x['claim_status']} | {x['local_status'] or 'absent'} | {x['finalization_proven']} |\n"
text+='''
Each new oracle saves returned state, disk index, both consumption states, terminal hash, attempted write sequence and phase count before asserting. All late-failure cases retain phase1 and observed debit=1; all-storage failure is injected only after already-persisted phases and independently prevents cleanup-detail plus every terminal control write. It does not pretend historical evidence can be recreated. Pure read-only verify.py rechecks raw artifacts and exact capture-byte conservation, plus nodeid retention, without following saved runtime paths or changing decisions.

All new owned test roots are removed; each public case has a serializable cleanup observation and each runner records its basetemp deletion. The 19 final public cases have 38 per-fixture textual inventories before deletion. No new SQLite/source binary archive was committed; historical archives and raw remain untouched. New raw, receipts, scripts, commands, stderr and counts are retained directly as text. Uncommitted terminal-candidate files in failure raw are forensic staging files, never canonical decisions.

Ten-field handoff: (1) R1 / WP-R1-U3 / S3_P2B_FINALIZATION_PUBLICATION_CONSISTENCY; (2) localized terminal publication fix; (3) last accepted slice remains 621b1bf386db71bfe08ca2f533fa8ec396b0504b; (4) C04 M1 awaits independent closure; (5) target V1, old S2 7/8 unchanged; (6) independent review/root decision remain; (7) next owner coordinator and independent reviewer; (8) no new actual authorization or human signature requested; (9) this receipt, verification and raw form the evidence; (10) implementation stops READY_FOR_REVIEW, no Stage/Gate0/quality/human/release signoff.

Development outline from unchanged execution-control: '''
text+='; '.join(f"{x['delivery']} {x['stage_id']} {x['completed']}/{x['total']}" for x in outline)
text+='\n\nImplementation submitted for review; machine tests passed; independent review pending; human signoff not added.\n'
(OUT/'review-handoff.md').write_text(text)
print(json.dumps(dict(status=receipt['status'],final_tests=237,parser=1)))
