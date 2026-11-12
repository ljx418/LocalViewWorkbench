"""Assemble textual independent review from captured evidence; no product imports."""
import hashlib,json,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent;PACK=OUT.parents[3];REPO=PACK.parent
read=lambda n:json.loads((OUT/n).read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def write(n,v):(OUT/n).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
root=read('root-current-control.json');audit=read('static-audit.json');obligations=read('test-obligation-audit.json')
labels=['suite','guard','replay','targeted'];runs={x:read(x+'.receipt.json') for x in labels};outer={x:read(x+'.outer.json') for x in labels}
for label,r in runs.items():
 assert r['exit_code']==outer[label]['exit_code']==0
 assert r['owned_root_removed'] and r['source_unchanged_during_run'] and r['runner_unchanged_during_run'] and r['probe_unchanged_during_run']
 for stream in ['stdout','stderr']:assert sha(OUT/(label+'.'+stream+'.log'))==r[stream+'_sha256']
assert len(obligations['identical_old_definitions'])==155 and not obligations['changed_old_definitions'] and not obligations['deleted_old_definitions'] and not obligations['missing_old_nodeids']
assert all(x['matches'] for x in audit['checksums'])
assert all(s['retained_matches'] for r in audit['implementation_receipts'] for s in r['streams'])
targeted=read('targeted-observations.json');replay=read('focused-observations.json')
assert targeted['count']==33 and targeted['removed'] and replay['count']==22
names=['after_canonical_read_symlink','after_canonical_read_plain','after_seal_read_missing','after_raw_read_leaf_symlink','after_raw_read_parent_plain','completion_canonical_leaf_redirect']
examples=[x for x in targeted['observations'] if x['name'] in names]
assert len(examples)==6 and all(x['result']['aggregate_pass'] and x['result']['all_rows_resolved'] and x['hook_fired']==1 for x in examples)
finding={
'id':'NM03','severity':'Major','status':'PARTIALLY_FIXED_REMAINS_OPEN',
'title':'Earlier-read child directories and leaves lose named custody before QS completion',
'locations':[{'path':'tools/v0_s3_quality_phase.py','line':2790,'symbol':'_ArtifactBoundary.verify'},{'path':'tools/v0_s3_quality_phase.py','line':2809,'symbol':'_ArtifactBoundary.read'},{'path':'tools/v0_s3_quality_phase.py','line':3465,'symbol':'recompute_scores final verification'}],
'contract':'Frozen correction06 task requires parent_fd/name/originalidentity/type comparisons for read child directories/leaves before and after reads and before successful completion while handles remain held.',
'prerequisites':'A genuine completed synthetic public-owner run; bounded controlled in-process mutation of only this probe fixture during another artifact os.read. No caller receipt modification, no canonical/seal byte rewrite, no host process or native attacker.',
'evidence':examples,
'expected':'A renamed/replaced/missing earlier evidence name must prevent successful completion; retain necessary custody until final entry checks finish.',
'actual':'All six controlled handoffs return aggregate_pass=true/all_rows_resolved=true,10 usable images/6 videos/critical0. Canonical may be a symlink/different file, seal absent, raw leaf a symlink or earlier raw directory replaced at return.',
'cause':'read() verifies only its current leaf/child directories then closes all their descriptors and discards their names/identities. _levels contains only run_root/temp/phase. Final verify() cannot inspect previously read canonical/seal/raw names or raw parent directories.',
'fixed_portion':'Trusted parent pinned; run_root/temp/phase current named-entry comparisons close earlier during-read ancestry reproductions, including literal root equality. Current-read canonical/source-plan/raw child directory and leaf replacements/missing entries refuse with intended reasons.',
'recommendation':'Extend the existing reader custody owner to retain the necessary child directory/leaf bindings through final verification, recheck their current names while corresponding descriptors remain held, and close all descriptors on success and errors. No new platform or cryptographic infrastructure is requested.',
'boundary':'Cooperative finite Python inode/name observations only; universal hostilekernel/concurrency/nativeWindows immunity outside scope.'}
write('findings.json',{'recommendation':'CHANGES_REQUIRED','counts':{'Fatal':0,'Major':1,'Minor':0},'findings':[finding],'stage_pass_claim':False,'product_pass_claim':False})
closure=[]
for x in read('../independent-p3b-correction-05/closure-map.json'):
 if x['id']=='M01':x.update(status='CLOSED_SCOPED_OFFLINE',evidence='232 combined suite;22 replay;33 independent observations. Recursive typed bindings and closed keysets exercised through public QS; conservative unknown and known failure/critical semantics preserved.')
 elif x['id']=='M08':x.update(status='CLOSED_SCOPED_OFFLINE_PRESERVED',evidence='All original seal label/descriptor/swap obligations preserved; strict-int seal ordinals True/1.0 reject with QS_SOURCE_PLAN_ORDER_INVALID without execution row changes.')
 elif x['id']=='NM03':x.update(status='PARTIALLY_FIXED_REMAINS_OPEN',evidence='Earlier during-current-read ancestry and leaf attacks now refuse;6 new cross-read/final-completion named custody counterexamples still aggregate true. See findings.json.')
 elif x['id'] not in ['E01','E02']:x['evidence']='Original206 nodeids retained;155 original definitions/helpers AST-identical;232 once passed; candidate diff and corresponding tests inspected. '+x['evidence']
 elif x['id']=='E02':x['evidence']='Current232 product cases once;guard4 once;correction06 replay22 once;independent33 once. These observations are not additional product tests; no old21/32/10 broad reruns.'
 closure.append(x)
write('closure-map.json',closure)
remaining=['NM03 earlier-read named entry custody remains Major', 'Parent original archive/retained attestation and selected-root binding NOTPROVEN', 'Parent hard watchdog UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER; synchronous callbacks not preempted', 'Native residue/admission and A06 enforcement/attempt observation NOTPROVEN', 'Actual registration baseline, installation and rollback NOTPROVEN', 'Authentic parent ledger debit NOTPROVEN', 'Real quality16/full12/productGate0/human-release NOTPROVEN']
ten={'1_current_coordinate':root['coordinate'],'2_this_batch':'Independent CHANGES_REQUIRED F0/M1/m0;232 product cases once,guard4 once,replay22 once,targeted33 observations once','3_last_passed_gate':root['last_passed_gate'],'4_current_blocking_gate':root['current_blocking_gate'],'5_route_position':'Root adjudication -> bounded component correction -> isolated independent review -> parent/native/A06/Gate0 -> finite real quality and human/release gates','6_remaining_work':remaining,'7_next_owner':'Root architecture/gate owner for disposition; implementation remains separate from review','8_authorization':'Already authorized offline independent review only; no new human approval required; no actual product runtime authorization inferred','9_evidence_directory':'reports/v0-s3/product-gate0/independent-p3b-correction-06/','10_exact_stop_reason':'Assigned review completed; hand off report/counts/full commit SHA; keep terminal visible'}
commands={x:outer[x] for x in labels};write('commands.json',commands)
final_pins={p:sha(PACK/p) for p in audit['current_pins']};assert final_pins==audit['current_pins'];write('final-bindings.json',final_pins)
receipt={'kind':'INDEPENDENT_P3B_CORRECTION06_AGGREGATE_REVIEW','recommendation':'CHANGES_REQUIRED','counts':{'Fatal':0,'Major':1,'Minor':0},'code_sha':'ba34b1581fc5e8e8b4de6ba469484e8eae416da1','evidence_sha':'b66aebaddedab3eb2bee88dda18d7657b94ff6d4','integrated_head':subprocess.run(['git','rev-parse','HEAD'],cwd=REPO,check=True,capture_output=True,text=True).stdout.strip(),'root_gitshow_only_revision':'08caf9f0e93ff7ff5acee7783c730346fc3c2c9c','prior_review_sha':'1618614798b7eaa23d603ab3d89b2e1176fc0e93','root_adjudication_sha':'c05ee011a73a790917000e5ab0e615851053a2eb','sources_final':final_pins,'invocations':runs,'outer_invocations':outer,'replay_original_before_asserted_sha256':final_pins['reports/v0-s3/product-gate0/implementation-p3b-correction-06/probe_correction06_counterexamples.py'],'replay_original_after_read_sha256':sha(OUT.parent/'implementation-p3b-correction-06/probe_correction06_counterexamples.py'),'replay_adapter_only_change':'In-memory OUT assignment; immutable original script compiled at original filename under inspected guard','counts_separate':{'product_cases':232,'guard_selftest_events':4,'replay_observations':22,'targeted_independent_observations':33,'new_product_cases':26,'original_product_cases_preserved':206,'original_definitions_ast_identical':155,'adapted_original_definitions':0,'deleted_original_definitions':0},'implementation_diagnostics_and_bindings':audit['implementation_receipts'],'implementation_checksum_entries':audit['checksums'],'prior_closure_mapping':closure,'ten_fields':ten,'development_outline':root['development_outline'],'remaining':remaining,'cleanup':{'runner_owned_roots_removed':all(x['owned_root_removed'] for x in runs.values()),'targeted_own_root_removed':targeted['removed'],'targeted_registered_roots':targeted['registered_roots'],'old_roots_scanned_or_deleted':False,'fixture_boundary':'fresh4x4PNG/tinyfakevideo via real ControlledImageOwner/BridgeOwner/public oracles; only syntheticprovider/HTTP/tinydecoder boundaries'},'zero_actual':['Windows','WSL','PowerShell','parser','hostexe hashing','real media','FFmpeg','models','GPU','services','network','download','real ledger','claims','full checkpoint'],'product_gate0':False,'stage_pass_claim':False,'product_pass_claim':False,'audit_guard_limit':'Named Python audit events only; no direct-syscall/native-extension immunity claim','original_correction03_unguarded12':'UNKNOWN_UNCREDITED per immutable erratum; no cosmetic reruns or retroactive zero-external certification'}
write('receipt.json',receipt)
md='''# Independent P3B correction06 aggregate review

**CHANGES_REQUIRED — Fatal0 / Major1 / Minor0.** Component recommendation only; no StagePASS or productPASS. M01 is closed within the frozen offline scope; NM03 has concrete progress but still loses custody of earlier-read entries before successful completion.

Candidate code `ba34b1581fc5e8e8b4de6ba469484e8eae416da1` and evidence `b66aebaddedab3eb2bee88dda18d7657b94ff6d4` were integrated using the requested `git merge --no-edit` (fast-forward; both are actual ancestors). Initial worktree was clean. Root intake/current outline was read only with gitshow `08caf9f0e93ff7ff5acee7783c730346fc3c2c9c`; no root metadata/V2 merge was added. AGENTS/routing, contract/projection, independent review1618614 and root adjudicationc05ee01 were inspected. Implementation narrative guided navigation only.

| Invocation | Single result | Inner / outer true exit |
|---|---|---|
| Combined suite |232 passed,81.33s pytest time|0 / 0|
| Guard selftest |4 blocked events|0 / 0|
| Immutable correction06 replay via output-only adapter |22 observations|0 / 0|
| Independent bounded targeted observations |33 observations, including6 reproduced residual custody cases|0 / 0|

All executable product/test observations used the inspected immutable correction05 runner with auditguard installed before pytest/plugins/ANY product/test import, plugin autoload/cache/bytecode disabled. connect/bind/DNS/Popen/system/exec/spawn/fork events are blocked. This is named Python audit coverage, not direct-syscall immunity. Exact argv/cwd and outer exits appear in commands.json; each invocation retains raw stdout/stderr, inner/outer receipts and stream hashes. Observation exit0 means capture completed, including reproduced defects; observations are not additional product tests. No repeated206/26 selections, historical21/32/10 probes, cap matrices, P3A121/P2B237 or project suite.

## NM03 — Major, partially fixed and still open

**Locations:** tools/v0_s3_quality_phase.py:2790 `_ArtifactBoundary.verify`,2809 `read`,3465 final QS verification.

**Trigger:** Start from a genuine completed public-owner synthetic run. During the bounded source-plan read, rename the already-read canonical receipt and replace its entry with a symlink to the untouched original. Alternatively replace the canonical with a different same-byte plain file during raw0 read; remove the already-read seal during raw0 read; replace raw0 leaf with a symlink or its parent with another plain directory during raw1 read. Every mutation is a controlled in-process handoff in this probe's own registered fixture. Supplied receipt and original canonical/seal/raw bytes are unchanged. A sixth companion probe changes canonical at the explicit final verify call.

**Expected:** The frozen correction06 task explicitly requires named-entry comparisons for read child directories/leaves before/after reads and before successful completion, while handles remain held. A removed/replaced evidence name must prevent successful completion, including when previously read bytes were genuine.

**Actual:** All six probes return `aggregate_pass=true/all_rows_resolved=true`,10 usable images/6 videos/critical0 while the selected canonical/raw entry is redirected/replaced, seal missing, or earlier raw directory replaced. All hooks fired once. For file mutations, before hashes and retained original hashes match; plain replacements copy identical bytes. No coherent trusted-original rewrite is involved.

**Cause:** `read()` checks only the current read's child directories and leaf, then closes their handles and discards the entry bindings. `_levels` retains only run_root/temp/phase. Final `verify()` therefore cannot revalidate earlier canonical/seal/raw leaves or their child directories. Pinning the three ancestors fixes the original during-current-read cases but does not fulfill the completion custody obligation.

**Evidence:** targeted-observations.json entries `after_canonical_read_symlink`, `after_canonical_read_plain`, `after_seal_read_missing`, `after_raw_read_leaf_symlink`, `after_raw_read_parent_plain`, `completion_canonical_leaf_redirect`; raw targeted.stdout.log; targeted inner/outer receipts. findings.json contains complete observations, expected/actual/trigger and locations.

**Recommendation:** Extend the existing bounded reader's custody through the final checks: retain the needed child-directory/leaf bindings, verify their current parent-relative names against held object identities/types at completion, then close all descriptors on success and errors. This remains a finite cooperative Python filesystem observation, not a new platform, signing scheme, hostilekernel/nativeWindows or universal concurrency guarantee.

The corrected portion is independently supported: replay rejects run_root/temp/phase symlinks during canonical read and raw parent/leaf redirects; targeted seal-read root symlink/temp plain/leaf plain replacements, canonical leaf plain/temp missing, and raw parent plain/leaf missing refuse with intended canonical/source-plan/raw reasons. Literal run-root equality now invokes verify. Parent descriptors are pinned; current read descriptors stay held through current-entry checks with no absolute-path fallback. Normal close, read-error close and partial constructor failure all return descriptor counts8->8. Tiny exact4 read succeeds; cap3 and growth4->5 refuse. These are bounded observations, not a claim that every OS exception has been simulated.

## M01 — closed within scoped offline review

The shared recursive `_json_fact_equal` distinguishes bool/int/finitefloat and compares full object keysets/list elements. Every actual use was inspected: recursive calls560/566; seal row alignment3019/3026/3029; release/source canonical comparison3220/3222; top/row exhaustive content comparison3307/3316. Call graph details are in static-audit.json. This is an active public QS path, not an unused helper.

The genuine baseline passes16 rows with16 submissions/34 reserved provider calls. Caller attempted true->int1/float1 and providerint1->true/float1 now reject at their content bindings. Nested source identity/bytes and release baseline/elapsed/GPU sample numeric type substitutions unresolve with aggregatefalse. Extra top/row fields reject; source/release/GPU extras unresolve. Optional native evidence fields added only by caller also unresolve. Missing source, null release, storage integer0, cleanupnull and malformed baseline remain unknown. Conservative evidence overlays remain effective, and published observations cannot be replaced by caller observations.

Seal-only ordinal true/1.0 updates only seal bytes and canonical hash/length binding; execution rows remain untouched by `_rewrite_seal`, and QS refuses with QS_SOURCE_PLAN_ORDER_INVALID. The replay's `execution_rows_unchanged` convenience flag compares two different fixture runs and is false; it is not used as proof. Helper body and retained combined test assertions establish the intended unchanged-within-run setup.

Published unknown error cannot become resolved under caller-known error; published knownFAIL suppliedPASS remains resolved/notusable; publishedPASS callerknownFAIL remains resolved/notusable and can retain aggregate when9/10 images+6/6 videos meet fixed thresholds. The original three canonical-verdict cases are AST-identical and present in the232 run. Independently verified critical3 remains visible and forces globalFAIL in replay. No all-technical-success rule or threshold change was introduced. Total coherent rewrite of both trusted originals remains outside signature obligations; parent archive/attestation is still required.

## Prior closures and test obligations

All206 prior collected nodeids remain in the232 collection;155 prior definitions, decorators, bodies and old helpers are AST-identical,0 adapted/0 deleted.25 added definitions produce26 new cases. test-obligation-audit.json records all new assertions/calls/lines and exact nodeid set differences. The new typed tests drive public QS after genuine `_own_run`, assert target reason and unresolved/refused outcome; the seal cases rebuild only seal length/hash, while named-entry tests fire during the selected artifact inode read and verify unchanged bytes. Literal-equality, tiny bounded/growth, FD cleanup and receipt-keyset checks are focused owner checks, not a substitute for public QS evidence. The new cases cover current-read handoffs; they do not cover the earlier-read completion counterexamples above.

M08 complete label/full descriptor alignment remains closed, including strict ordinal residual now fixed under M01. Source row labels, order, full five-part identities, path/bytes/hash and swaps remain checked. NM04 is preserved: all driver submissions/limit/submit getters resolve before final bounded ORIGINAL sealed-source validation, then one coherent clock/proof/ownership guard precedes reservation/attempt charge/cachedsubmit. No extra getter/callback/clock appears in that interval; no refunds/retries. Original NM01 capacity/time accessors and NM02 exact10800/oneover10801/laterproof tests remain AST-identical and pass. Earlier M02/M03/M04/M05/M06/M07/M09/m01 are not reopened absent concrete regression. See closure-map.json.

Real ControlledImageOwner/BridgeOwner/public production nodes and oracles are exercised; only synthetic provider, HTTP and tiny decoder are substituted. Fresh4x4PNG/tinyfakevideo remain bounded and locally owned. Fixed16/34, score>=8,images8/10,videos5/6,critical0, raw/storage/cleanup and production owner source remain unchanged.

## Source, retained history and cleanup bindings

'''
md+='\n'.join('- `'+p+'`: `'+h+'`' for p,h in final_pins.items())+'\n\n'
md+='''All four independent invocation receipts bind source/runner/probe before+after, actual imported absolute module paths/hashes and raw byte lengths/hashes. Guard mode imports no product module. The replay adapter asserts the immutable original probe hash before compile; static/final binding reads verify it after execution (its SystemExit exits before the adapter\'s trailing assertion). Runner hashes bind the adapter separately. Candidate argument is not attestation.

Independently verified31 repo-relative checksum entries, all6 final implementation raw streams, and final2 source identities. The earlier root pack-relative resolver mistake was not an artifact defect. static-audit.json additionally retains exact declared historical output paths and moved retained paths, stream hashes,8 diagnostic/final receipt bindings and true exits: dev-focus-1=0,dev-focus-2=1,dev-focus-3=0,dev-focused-1=0,dev-suite-1=0,final focused/guard/suite=0. Earlier test hashes052502… and b12a12… are preserved, not recertified from final9771ba… green. Actual runner/probe hashes and import paths for each historical invocation remain recorded. No historical raw was regenerated or relabeled. Original correction03 unguarded12 stay UNKNOWN/uncredited under immutable erratum; no cosmetic reruns.

All four runner-owned roots were removed. Targeted script registers each fixture root, restores its owned rename handoffs where necessary and removes its own root; replay root is inside the enclosing runner-owned root, whose removal is recorded. No old root was scanned/deleted. Only new text files in this review subtree are authored. No product/tools/tests/contracts/projection/quality/prelabels/coordinate/manifest/old reports modified; no binaries/DB/ZIP/copied product source, push or permanent configuration. Actual Windows/WSL/PowerShell/parser/hostexe hashing/realmedia/FFmpeg/models/GPU/services/network/download/realledger/claims/fullcheckpoint all0. No testSource/holdout/fullprelabels read.

Parent owned original archive/retained attestation and selectedroot binding remain NOTPROVEN; parent hardwatchdog remains UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER. Native residue/admission/A06, registration-installrollback, authenticdebit, realquality/full12/Gate0/human-release remain NOTPROVEN. Machine synthetic checks and this independent review do not complete any product Stage.

## Ten-field handoff

'''
md+='\n\n'.join(str(i)+'. '+k.split('_',1)[1].replace('_',' ')+': '+(json.dumps(v,ensure_ascii=False) if not isinstance(v,str) else v) for i,(k,v) in enumerate(ten.items(),1))+'\n\n'
md+='## Full V0–V3 outline from current root\n\nSource: gitshow08caf9f only; current Stage **'+root['coordinate']['stage_id']+'**. No progress counts or implementation/machine/independent/human states are changed by this component review. Full source evidence references and early-slice scope are retained in root-current-control.json and receipt.json.\n\n|Delivery|Stage|Done/total|Implementation|Machine|Independent|Human|\n|---|---|---:|---|---|---|---|\n'
for x in root['development_outline']:
 md+='|'+str(x['delivery'])+'|'+x['stage_id']+'|'+str(x['completed_substeps'])+'/'+str(x['total_substeps'])+'|'+'|'.join(x[k] for k in ['implementation','machine_acceptance','independent_review','human_signoff'])+'|\n'
md+='\nFull declared substeps:\n\n'
for x in root['development_outline']:md+='- **'+x['stage_id']+'**: '+'; '.join(s['name']+' ['+s['status']+']' for s in x['substeps'])+'.\n'
(OUT/'review.md').write_text(md)
print('Wrote aggregate review F0/M1/m0,232 suite,guard4,replay22,targeted33; all raw/source/checksum bindings verified')
