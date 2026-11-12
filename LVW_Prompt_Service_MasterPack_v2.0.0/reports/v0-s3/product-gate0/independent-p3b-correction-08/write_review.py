"""Assemble text reports from immutable and independently captured evidence; no product imports."""
import hashlib,json
from pathlib import Path
O=Path(__file__).resolve().parent; P=O.parents[3]
def read(n): return json.loads((O/n).read_text())
def write(n,v): (O/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
a=read('static-audit.json'); control=read('root-current-control.json'); target=read('targeted-observations.json'); replay=read('counterexample-observations.json')
assert target['count']==25 and not target['violations'] and not replay['violations']
labels=['suite','guard','replay','targeted']; executions=[]
for label in labels:
 r=read(label+'.receipt.json'); outer=read(label+'.outer.json')
 assert r['exit_code']==outer['exit_code']==0 and r['source_unchanged_during_run'] and r['runner_unchanged_during_run'] and r['probe_unchanged_during_run'] and r['owned_root_removed']
 streams={}
 for s in ['stdout','stderr']:
  p=O/(label+'.'+s+'.log'); assert sha(p)==r[s+'_sha256'] and p.stat().st_size==r[s+'_bytes']
  streams[s]={'path':str(p.relative_to(P)),'sha256':sha(p),'bytes':p.stat().st_size}
 executions.append({'label':label,'inner':r,'outer':outer,'verified_streams':streams})
assert all(x['matches'] for x in a['pins'].values()) and all(x['matches'] for x in a['implementation_checksums'])
assert all(s['matches'] for x in a['history'] for s in x['streams'])
closures=[]
prior=json.loads((O.parent/'independent-p3b-correction-07/closure-map.json').read_text())
for old in prior:
 item={'id':old['id'],'prior_status':old['status'],'prior_review_commit':'9d2c51de4e8df6e5f882405cbff1332356dc8269',
       'status':'PRESERVED_SCOPED_OFFLINE','evidence':['static-audit.json:test_audit','suite.receipt.json:collected_nodeids'],
       'scope':'193 original test definitions/decorators/bodies and old helpers identical; all 245 prior cases retained in once257; inspected product diff'}
 if old['id']=='NM03': item.update(status='CLOSED_SCOPED_COOPERATIVE_RESOURCE_AND_NAMED_CUSTODY',evidence=['targeted-observations.json','counterexample-observations.json','suite.receipt.json'])
 if old['id']=='E01': item.update(status='ORIGINAL_CORRECTION03_UNGUARDED12_UNKNOWN_UNCREDITED',scope='No historical recertification or cosmetic rerun')
 if old['id']=='E02': item.update(status='COUNT_ERRATA_PRESERVED',scope='Current independent257 once, guard4 once, replay5 once, targeted25 once; no focused12 rerun')
 closures.append(item)
closed=[{'id':'NM03-R1_POST_OPEN_METADATA_EXCEPTION_DESCRIPTOR_LEAK','prior_severity':'Major','status':'CLOSED_SCOPED_OFFLINE',
 'locations':['tools/v0_s3_quality_phase.py:2894 _open_child_directory','tools/v0_s3_quality_phase.py:2929 _open_leaf','tools/v0_s3_quality_phase.py:2682 _NamedCustody.take','tools/v0_s3_quality_phase.py:3736 recompute_scores'],
 'trigger':'Actual successful child-directory or leaf os.open followed by exactly one EIO at its first fstat, before custody insertion',
 'expected':'One owner closes the refused descriptor once; existing entries and capacity survive; public QS refuses without residual live FDs',
 'actual':'Both owner faults close once before boundary.close, all existing custody preserved and retry admitted; public canonical leaf and raw child-directory faults each fire once, scoring raises EIO and finally closes every acquired FD once; no probe FD remediation',
 'evidence':['targeted-observations.json:leaf_fstat','targeted-observations.json:directory_fstat','targeted-observations.json:public_leaf_postopen_fstat','targeted-observations.json:public_directory_postopen_fstat','counterexample-observations.json','targeted.receipt.json','suite.receipt.json'],
 'limits':'Injected ordinary errors on cooperative Linux Python boundary; not observation of an actual OS EIO, universal allocator failure, native Windows or hostile kernel'},
 {'id':'NM03-r2_CAP_CHECK_AFTER_EXCESS_OPEN','prior_severity':'Minor','status':'CLOSED_SCOPED_OFFLINE',
 'locations':['tools/v0_s3_quality_phase.py:2654 _NamedCustody.reserve','tools/v0_s3_quality_phase.py:3032 _retain_directory','tools/v0_s3_quality_phase.py:3063 _retain_leaf'],
 'trigger':'72 distinct four-byte leaf names retained, then dedup miss for 73rd and repeats at full capacity',
 'expected':'Refuse before excess open, zero transient FD increase, no lost entries, no consumed failed slot, final baseline',
 'actual':'Exactly72 entries/opens;73rd zero opens and high-water84 unchanged; all72 reused and verified, unchanged registry,0 pending reservations; close8; genuine public16 uses35 entries and closes47 to8',
 'evidence':['targeted-observations.json:exact72_excess73_repeat72','targeted-observations.json:genuine_full16_public_success','counterexample-observations.json','targeted.receipt.json','suite.receipt.json'],
 'limits':'72 is unchanged internal capacity, not public threshold or platform/concurrency guarantee'}]
process=[{'id':'EXECUTION_DISCIPLINE_PRECOMMIT_FULL_SUITE','type':'ACKNOWLEDGED_HISTORICAL_DEVIATION','blocking':False,
 'location':'implementation-p3b-correction-08/debug/debug-suite.receipt.json',
 'trigger':'Full257 run during precommit editing despite focused-editing plan',
 'expected':'Focused checks during editing and one final combined acceptance on committed candidate',
 'actual':'Retained debug-suite exit0,257 passed90.67s pytest /95.06s runner duration; final suite is a separate invocation exit0,257 passed84.73s pytest /88.777s runner duration',
 'disposition':'Actual execution-discipline deviation, not repaired by final green; retain history; no mandatory fresh correction or cosmetic rerun just for prose',
 'evidence':['static-audit.json:history','implementation-p3b-correction-08/debug/debug-suite.stdout.log','root-intake.json:execution_notes']},
 {'id':'REDUNDANT_FINAL_FOCUSED12','type':'REDUNDANT_EXECUTION_NO_COVERAGE_CREDIT','blocking':False,
 'location':'implementation-p3b-correction-08/focused.receipt.json',
 'actual':'Distinct final focused invocation inner0,12 passed245 deselected,11.427s runner; all12 already in257',
 'disposition':'Retain distinct invocation, zero added coverage credit, not rerun independently',
 'evidence':['static-audit.json:history','root-intake.json:execution_notes']}]
# Use actual retained stdout for timing text, never reconstruct historical logs.
for x in process:
 if x['id']=='EXECUTION_DISCIPLINE_PRECOMMIT_FULL_SUITE':
  x['actual']='Retained debug-suite inner0,257 passed90.67s pytest /95.06s runner; distinct final suite inner0,257 passed'+(O.parent/'implementation-p3b-correction-08/suite.stdout.log').read_text().strip().split('257 passed in ')[1]+' pytest /88.777s runner'
findings={'kind':'INDEPENDENT_P3B_CORRECTION08_AGGREGATE_FINDINGS','recommendation':'ACCEPT_COMPONENT_SCOPED_OFFLINE_F0_M0_m0',
 'counts':{'fatal':0,'major':0,'minor':0},'open_current_findings':[],'closed_assigned_findings':closed,
 'prior_closure_mapping':closures,'historical_process_observations':process,'stage_pass_claim':False,'product_gate0':False}
write('findings.json',findings)
remaining=['Parent owned original archive/retained independent attestation and selected-root binding NOTPROVEN','Parent hardwatchdog UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER','Native residue-admission/A06 NOTPROVEN','Registration-installrollback NOTPROVEN','Authentic parent ledger debit NOTPROVEN','Realquality/full12/Gate0/human-release NOTPROVEN']
handoff={'1_current_coordinate':control['coordinate'],'2_this_batch':'Independent component recommendation F0/M0/m0;257 cases once,guard4 once,replay5 once,targeted25 once',
 '3_last_passed_gate':control['last_passed_gate'],'4_current_blocking_gate':control['current_blocking_gate'],
 '5_route_position':'Root disposition of independent review -> parent/native/A06/Gate0 -> finite real quality -> human/release',
 '6_remaining_work':remaining,'7_next_owner':'Root architecture/gate owner; implementation remains separate',
 '8_authorization':'Already authorized offline isolated review; configured default Codex, no override/new human permission, no product runtime authority inferred',
 '9_evidence_directory':str(O.relative_to(P))+'/',
 '10_exact_stop_reason':'Assigned independent aggregate review complete; hand off full local commit/report/counts; keep terminal visible'}
receipt={'kind':'INDEPENDENT_P3B_CORRECTION08_AGGREGATE_REVIEW','recommendation':findings['recommendation'],'counts':findings['counts'],
 'candidate_sha':a['git_identity']['candidate'],'evidence_sha':a['git_identity']['evidence'],'root_gitshow_only':'1b93f1711337f3351ddbf7b6fc11b735a7513fc5',
 'prior_review_commit':'9d2c51de4e8df6e5f882405cbff1332356dc8269','adjudication_commit':'94ade2aa32740830c17849b04dc2d3c365857c3e',
 'integration':'git merge --no-edit evidence833c847 code6c9a0a0 fast-forwarded clean existing review worktree; no extra rootmetadata/V2 merge',
 'reviewer':{'role':'independent isolated Codex, not implementer','task_id':'task_67a35b278655','dispatch_id':'ctx_82a28efdc14f','helpers':0},
 'pins':a['pins'],'execution_receipts':executions,'implementation_history':a['history'],'test_obligation_audit':a['test_audit'],
 'prior_closure_mapping':closures,'closed_assigned_findings':closed,'historical_process_observations':process,
 'resource_proof':{'independent_observations':25,'immutable_replay_observations':5,'violations':0,'cap':72,'distinct_four_byte_leaves':72,'excess_opens':0,'fd_baseline':8,'cap_fd_highwater':84,'genuine16_entries':35,'genuine16_fd_highwater':47,'after_close':8,
 'fault_coverage':'leaf+child open/fstat/stat/type/identity/registry insertion/FD-list transfer;7 constructor partial acquisitions;public canonical+raw-directory fstat;existing custody preservation and retry;fullcap dedup;genuine16',
 'constructor_transfer_append_failure':'Source audited cleanup branches; not separately injected in independent observations',
 'probe_cleanup_masks_fd_leak':False,'no_double_close':'Instrumented close calls and post-close reused sentinel survives second close','no_stale_parent':'All genuine16 custody parent descriptors owned through final verification'},
 'raw_binding':'Each independent invocation verifies both raw streams SHA256/bytes, exact argv/cwd, true inner/outer exit, source+runner+probe beforeafter and actual imported paths/hashes; candidate argument is not attestation',
 'cleanup':{'all_four_runner_roots_removed':True,'replay_registered_roots_removed':replay['removed'],'targeted_registered_roots_removed':target['owned_root_removed'],'probe_fd_remediation':False,'old_roots_deleted':False},
 'history_limits':['Retained implementation receipts record actual inner exits/durations/source+runner+probe/import hashes; outer exits and absolute start/end times not recorded there, so remain UNKNOWN rather than inferred from prose','Early debug-focused test hash differs from final;first debug probe hash differs and exit1;negative-control old product hash and exit1 with10fail2pass are diagnostics, not current candidate failures','Prior429/taskresume/stop_unknown history retained; explicit same-Claude restoration and observed resume accepted as task-supplied/root-recorded evidence, not freshly re-inspected process','Original correction03 unguarded12 remain UNKNOWN/uncredited under immutable erratum'],
 'scope_zero':{x:0 for x in ['actual_Windows','actual_WSL','PowerShell','parser','hostexe_hashing','realmedia','FFmpeg','models','GPU','services','network','download','realledger','claims','fullcheckpoint']},
 'not_proven':remaining,'trust_limits':['Cooperative in-process Python inode/name checks and named audit events','No universal hostile-kernel/native-Windows/direct-syscall/concurrency immunity','No total trusted-root forgery or signing platform obligation added','Allocation exhaustion and arbitrary malicious replacement of Python containers outside finite injected branches not certified'],
 'ten_field_handoff':handoff,'development_outline':control['development_outline'],'stage_pass_claim':False,'product_gate0':False,'human_signoff':False}
# Bind all evidence bytes available at assembly; self/report excluded to avoid recursive hash claims.
receipt['evidence_files']={str(p.relative_to(O)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(O.iterdir()) if p.is_file() and p.name not in ('receipt.json','review.md','SHA256SUMS')}
write('receipt.json',receipt)
lines=['# Independent P3B correction08 aggregate review','',
 '**ACCEPT_COMPONENT_SCOPED_OFFLINE — Fatal0 / Major0 / Minor0.** Both assigned resource findings are closed within the audited cooperative offline scope. This is a component recommendation for root disposition; no StagePASS, productPASS, Gate0 or human signoff.',
 '',f"Candidate `{receipt['candidate_sha']}`; evidence `{receipt['evidence_sha']}`. The requested merge fast-forwarded the clean existing review worktree; code is an ancestor of evidence. Root intake/current outline were read only through gitshow1b93f17, with no extra rootmetadata/V2 merge. AGENTS, governance/routing, frozen P3B contract/projection, prior review9d2c51d and adjudication94ade2a were read; implementation claims served as navigation.",
 '', '|Independent invocation, once each|Result|True inner/outer exit|Runner duration|','|---|---|---|---|']
results=['257 passed in79.39s pytest','4 audit events blocked','5 immutable resource observations,0 violations','25 new bounded resource observations,0 violations']
for e,result in zip(executions,results): lines.append(f"|{e['label']}|{result}|{e['inner']['exit_code']}/{e['outer']['exit_code']}|{e['inner']['duration_seconds']}s|")
lines += ['', 'All product/test execution used the inspected immutable correction05 runner, which installs its auditguard before pytest/plugins/any product or test import. Plugin autoload/cache/bytecode are disabled; connect/bind/DNS/Popen/system/exec/spawn/fork are blocked. Outer invoke.py only captures the child runner and imports no product/test modules. Exact argv/cwd, actual imported paths/hashes, before/after source/runner/probe identities, raw streams/lengths and true exits are in the per-invocation receipts and aggregate receipt.json. This is named Python audit coverage, with no direct-syscall immunity claim.',
 '', 'NM03-R1 is closed: `_open_child_directory`2894 and `_open_leaf`2929 keep each successful open inside exception cleanup through fstat, named stat, type and identity validation. Their callers3032/3063 reserve before opening, cancel on failure and transfer into `_NamedCustody.take`2682. Registry insertion and FD-list append share rollback; previous entries remain owned. Constructor2798 catches partial acquisition and closes previously registered anchors; append-failure branches close the newly acquired descriptor before propagation. Custody closes children in reverse order before anchor descriptors; repeated close clears all references and does nothing.',
 '', 'Independent owner injections cover open, first-fstat EIO, named-stat EIO, wrong type, changed identity, insertion refusal and FD-list transfer refusal for both child directories and leaves, each with an existing genuine entry retained. The post-open hooks fire once; the target descriptor is closed once before boundary.close, no live target remains, prior entries verify unchanged, reservations return0 and a subsequent retry admits normally. FD counts return8 after boundary.close. Close instrumentation shows no duplicate close; a fresh reused descriptor survives another boundary.close. No probe remediation closes leaked product FDs. Constructor open failures at acquisitions1–4 and first-fstat failures at levels2–4 close every actual acquisition once and restore8; constructor append-failure branches were source audited, not independently injected.',
 '', 'Public `recompute_scores`3736 reaches the same precise post-open EIO for both the canonical leaf and the first raw row child directory. Both hooks fire1, no score result returns, each acquired FD closes once in the same finally3760, and8->8 is measured. This distinguishes failed scores from successful resource cleanup; it does not claim an actual operating-system EIO occurred. The immutable replay independently reproduces both owner faults and a public canonical fault.',
 '', 'NM03-r2 is closed: `_NamedCustody.reserve`2654 checks entries plus pending reservations after dedup misses and before os.open. Exact72 distinct four-byte leaves produce72 entries/opens; the73rd refuses with ZERO extra opens and no transient FD growth (high-water84 stays84). All72 retained entries verify and every repeated name reuses the original descriptor with zero opens. Refused open/metadata/insertion/transfer paths cancel their reservation without losing earlier custody. Final close restores8. The cap remains internal72=4*(16+2), not a public threshold. A genuine public16 evaluation retains35 entries,0 reservations, all parent references owned,47 FDs at final close and8 after; it aggregates with the existing fixed quality rules.',
 '', 'Evidence for each assigned finding, locations/trigger/expected/actual/limits and prior closure mapping appears in findings.json. Raw targeted output retains all25 observations; replay output retains5 observations. Observations are not additional product tests. The output-only replay adapter checks the immutable probe hash before and after and changes only its OUT assignment in memory; the immutable source filename is retained.',
 '', 'All245 prior nodeids remain in257. All193 prior test definitions, decorators/bodies and old helpers are AST-identical,0 adapted/0 deleted;12 added definitions generate12 cases. Each new case has inspected assertions/calls/locations in static-audit.json. The owner tests reach their post-open/type/identity/insertion/admission conditions; the public test reaches canonical fstat EIO; the constructor test reaches first level fstat; the genuine16 test consumes actual canonical/seal/raw names. They passed without procfs skips on this host. The retained old-candidate negative control shows10 failures/2 passes and inner1; four failures reflect the new reserved() API absent in old code, so10 is not10 independent leak reproductions. It supplies useful discrimination, not current-candidate failure counts; it was not rerun.',
 '', 'Named custody lifetime and the six earlier-read/completion substitutions remain closed: their original tests run within257 without adaptation, not through a redundant old replay. Canonical symlink during seal read, canonical same-byte plain replacement during raw0, seal missing during raw0, raw0 leaf symlink during raw1, raw0 parent plain replacement during raw1, and canonical redirect before completion still refuse. No old broad8/20 histories, focused12 separately,245+12 split, capmatrix, P3A121/P2B237 or fullproject run was performed.',
 '', 'M01 recursive typed facts/full keysets, M08 full seal order/label/source identity/path/bytes/hash alignment and NM04 final original-source ordering remain intact. Apart from the two resource-owner classes and the new close helper, prior top-level product definitions are unchanged. Actual QS typed-equality call sites3313/3320/3323/3514/3516/3601/3610 and public final verify3757 remain active. `_execute_row`1743 resolves driver getters/cached submit,1750 validates the sealed ORIGINAL source,1758 performs coherent clock/proof/ownership guard,1763 reserves,1767 charges,1770 invokes cached submit with no intervening driver getter/callback/extra clock. Exact10800/oneover10801/laterproof/no-refund/no-retry and capacity0 regressions remain in the original passing suite. Fixed16/34,score>=8,8/10 images,5/6 videos,critical0; knownFAIL resolved/notusable, unknownFAIL unresolved, critical3 visible, raw storage/cleanup are preserved. No all-technical-success rule or total trusted-root forgery/signature obligation was added; olderM02/M03/M04/M05/M06/M07/M09/m01 are not reopened absent a regression.',
 '', 'The precommit debug-suite is an **actual execution-discipline deviation** from the focused-editing plan. It remains diagnostic, not final committed acceptance, and later green does not erase it. Retained stdout says257 passed90.67s; its runner receipt records95.06s and inner0. The distinct final implementation suite records257 passed in'+(O.parent/'implementation-p3b-correction-08/suite.stdout.log').read_text().strip().split('257 passed in ')[1]+'; runner88.777s,inner0. The final focused12 is a distinct redundant invocation (11.427s runner,inner0) with no added coverage credit. No mandatory fresh correction just for prose or cosmetic rerun is recommended.',
 '', 'All37 implementation checksum entries and20 retained debug/final raw streams match. static-audit.json retains every historical source/runner/probe before/after hash, actual imported paths/hashes, inner exit and duration. Early debug-focused used testc57127dc… rather than finaleb8327f9…; first debug probe11981b44… exited1 for the missing projection binding, while final probee664f586… exits0. Negative control used old producte670b330… and exits1. Historical outer shell exits and absolute start/end timestamps are not in those inner receipts and remain UNKNOWN, despite prose claiming0/0; durations and content bindings are proven. No earlier logs were relabelled, regenerated or deleted. The prior429/taskresume/stop_unknown history remains; the task/root records explicitly restored the same Claude task and observed its resume. No settled implementer was reopened. Original correction03 unguarded12 remain UNKNOWN/uncredited under the immutable erratum.',
 '', 'All four runner-owned roots and registered replay/targeted roots were removed. FD cleanup was measured before filesystem teardown. Fresh4x4 PNG/tiny fake video fixtures use actual ControlledImageOwner/BridgeOwner/oracles through existing synthetic transport helpers; no real decoder/server or original quality sources/prelabels/holdouts were used. Only new text in this subtree was authored; candidate/tools/tests/spec/oldreports/runners/checksums/logs/coordinate/manifest remain unchanged. No copied product source/binaries/DB/ZIP, push, permanent config or history rewrite. Actual Windows/WSL/PowerShell/parser/hostexe hashing/realmedia/FFmpeg/models/GPU/services/network/download/realledger/claims/fullcheckpoint are all0.',
 '', 'Limitations remain explicit: cooperative Python/filesystem observations, not universal concurrency/hostile-kernel/native-Windows/direct-syscall immunity or exhaustive allocation-failure certification. Parent archive/attestation and selected-root binding remain NOTPROVEN; parent hardwatchdog remains UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER; native residue-admission/A06, registration-installrollback, authenticdebit, realquality/full12/Gate0/human-release remain NOTPROVEN.',
 '', 'Ten-field handoff (root gitshow1b93f17):','']
for k,v in handoff.items(): lines.append(k.replace('_',' ',1)+': '+(json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v)+'\n')
lines += ['Full V0–V3 outline from root gitshow1b93f17, current Stage **R1**. This review changes no formal completion or human-signoff counts. Full evidence paths and substep statuses are in root-current-control.json and receipt.json.','', '|Delivery|Stage|Done/total|Implementation|Machine|Independent|Human|','|---|---|---:|---|---|---|---|']
for row in control['development_outline']:
 lines.append('|'+ '|'.join([row['delivery'],row['stage_id'],str(row['completed_substeps'])+'/'+str(row['total_substeps']),row['implementation'],row['machine_acceptance'],row['independent_review'],row['human_signoff']])+'|')
lines+=['','Full declared substeps:','']
for row in control['development_outline']:
 lines.append('- **'+row['stage_id']+'**: '+'; '.join(s['name']+' ['+s['status']+']' for s in row['substeps'])+'.')
(O/'review.md').write_text('\n'.join(lines)+'\n')
print('Reports assembled: F0/M0/m0;257+guard4+replay5+targeted25; no product gate claim')
