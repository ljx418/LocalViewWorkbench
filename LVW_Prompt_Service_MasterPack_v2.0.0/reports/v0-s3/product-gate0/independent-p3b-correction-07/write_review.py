"""Assemble text reports from retained results; never imports product/test code."""
import hashlib, json
from pathlib import Path
OUT=Path(__file__).resolve().parent
PACK=OUT.parents[3]
def read(name): return json.loads((OUT/name).read_text())
def write(name,value): (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
static=read('static-audit.json'); audit=read('test-obligation-audit.json')
targeted=read('targeted-observations.json'); replay=read('counterexample-observations.json')
target={x['name']:x for x in targeted['observations']}
root=read('root-current-control.json')
findings=[
 dict(id='NM03-R1',severity='Major',status='OPEN',title='A post-open metadata failure loses descriptor ownership before custody insertion',
      locations=[dict(path='tools/v0_s3_quality_phase.py',line=2822,function='_ArtifactBoundary._open_child_directory'),dict(path='tools/v0_s3_quality_phase.py',line=2850,function='_ArtifactBoundary._open_leaf'),dict(path='tools/v0_s3_quality_phase.py',line=2948,function='_ArtifactBoundary._retain_directory'),dict(path='tools/v0_s3_quality_phase.py',line=2965,function='_ArtifactBoundary._retain_leaf')],
      trigger='In a fresh bounded fixture, let os.open succeed, then inject one ordinary OSError(EIO) in the first os.fstat of that just-opened child directory or leaf; invoke boundary.close after refusal.',
      expected='Every descriptor opened by the boundary has an owner immediately and is closed on refusal, including failures before identity extraction/custody transfer; no error-dependent growth across evaluations.',
      actual='Both hooks fired exactly once; close left the opened descriptor live and procfs count changed 8 to 9 for each isolated observation. Only explicit probe remediation closed the leaked FD, restoring 8. The helper calls fstat before any try/finally or registration; neither _fds nor _custody knows this descriptor.',
      evidence=['targeted-observations.json:postopen_fstat_error_leaf','targeted-observations.json:postopen_fstat_error_directory','targeted.stdout.log','targeted.receipt.json','targeted.outer.json'],
      observations=[target['postopen_fstat_error_leaf'],target['postopen_fstat_error_directory']],
      scope='Observed at the actual boundary.read owner path, not through public recompute_scores for this injected error. Public recompute_scores uses the same helpers and its finally closes this same boundary; source inspection establishes that it cannot recover an unregistered descriptor. This pre-existing open-helper gap is material to the explicitly assigned NM03 resource/error closure, not a reopened unrelated historical finding.',
      impact='Refusal is fail-closed for scores but not for resources. Repeated metadata failures can accumulate live descriptors outside the finite custody registry; an unconditional cleanup/finite-FD claim is unsupported.',
      recommendation='Keep each successfully opened descriptor under cleanup ownership until transfer into custody succeeds, including metadata/error paths; preserve the original pinned entry on reuse.'),
 dict(id='NM03-r2',severity='Minor',status='OPEN',title='The custody cap refuses only after opening the excess entry',
      locations=[dict(path='tools/v0_s3_quality_phase.py',line=2649,function='_NamedCustody.take'),dict(path='tools/v0_s3_quality_phase.py',line=2948,function='_ArtifactBoundary._retain_directory'),dict(path='tools/v0_s3_quality_phase.py',line=2965,function='_ArtifactBoundary._retain_leaf')],
      trigger='Fill a fresh boundary with exactly72 distinct four-byte leaves, then read a73rd leaf while counting actual os.open calls and live descriptors.',
      expected='After a dedup miss at the internal72-entry cap, refuse before any excess child/leaf open; retain every existing entry and release all resources.',
      actual='Exact72 succeeds and all old entries remain. The73rd os.open succeeds, transient procfs count grows84 to85, and take then closes the excess FD and raises QS_ARTIFACT_CUSTODY_LIMIT_EXCEEDED:f72. Final boundary cleanup returns8. Thus score refusal and normal finiteness hold, but the explicit before-excess-open obligation does not.',
      evidence=['targeted-observations.json:exact72_oneover73_admission','targeted.stdout.log','targeted.receipt.json','targeted.outer.json'],observations=[target['exact72_oneover73_admission']],
      impact='Normal operation has a finite transient bound of4 anchor FDs+72 retained entries+1 unregistered open, rather than the requested4+72 admission bound. No successful aggregate, dropped entry, or unbounded normal growth was observed. This is an internal implementation bound, not a public threshold.',
      recommendation='Check/reserve capacity after the dedup lookup and before opening a new entry, with exception-safe ownership transfer.')
]
counts=dict(Fatal=0,Major=1,Minor=1)
write('findings.json',dict(decision='CHANGES_REQUIRED',component_only=True,counts=counts,findings=findings,stage_pass_claim=False,product_gate0=False))
closure=[]
prior=json.loads((OUT.parent/'independent-p3b-correction-06/closure-map.json').read_text())
for row in prior:
    item=dict(row)
    item['prior_review_commit']='4fb52ff3d4ef0b6bb4bcadabbd0598ce581a81af'
    if row['id']=='NM03':
        item.update(status='NAMED_LIFETIME_CLOSED_RESOURCE_ERROR_AND_ADMISSION_REMAIN_OPEN',evidence='Six prior public QS counterexamples now refuse at intended hooks;9 adjacent/final mutations also refuse;35-entry full16 shape repeats without growth; explicit resource/error findings NM03-R1 and NM03-r2 remain.')
    elif row['id']=='E02':
        item.update(status='COUNT_ERRATA_PRESERVED',evidence='245 combined product cases once;guard4 once;immutable replay8 observations once;independent targeted20 observations once. No focused13 separately and no old broad matrices.')
    elif row['id']=='E01':
        item['evidence']='Original correction03 unguarded12 remain UNKNOWN/uncredited and zero external actions NOT_PROVEN; no historical regeneration or cosmetic rerun.'
    else:
        item['evidence']='Preserved here by180 AST-identical prior test definitions and old helpers, all232 prior nodeids in the once245 passing suite, inspected candidate diff and actual call sites. '+row['evidence']
    closure.append(item)
write('closure-map.json',closure)
invocations=[]
for label in ('suite','guard','replay','targeted'):
    r=read(label+'.receipt.json'); outer=read(label+'.outer.json')
    streams=[]
    for stream in ('stdout','stderr'):
        p=OUT/(label+'.'+stream+'.log')
        streams.append(dict(stream=stream,path=str(p.relative_to(PACK)),sha256=sha(p),bytes=p.stat().st_size,matches=sha(p)==r[stream+'_sha256'] and p.stat().st_size==r[stream+'_bytes']))
    invocations.append(dict(label=label,outer=outer,inner_exit=r['exit_code'],inner_receipt=r,streams=streams))
write('commands.json',dict(invocations=[dict(label=i['label'],command=i['outer']['command'],cwd=i['outer']['cwd'],inner_exit=i['inner_exit'],outer_exit=i['outer']['exit_code']) for i in invocations],static_command=['python3','-B',str(OUT/'static_audit.py')],static_exit=0,report_assembly_attempts=[dict(exit_code=1,error="KeyError: current_stage; corrected report-only root-key lookup to coordinate; no product/test code imported"),dict(exit_code=0)],static_operations='Git show and AST/hash/JSON reads only; no product/test imports or product execution',navigation_error='One read-only git diff used a mistyped baseline hash and exited128 before correct baseline was read; no validation or candidate change occurred.'))
blockers=['Parent owned original archive/retained attestation and selected-root binding NOTPROVEN','Parent hardwatchdog UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER','Native residue/admission and A06 NOTPROVEN','Registration/installation/rollback NOTPROVEN','Authentic parent ledger debit NOTPROVEN','Real quality/full12/productGate0/human-release NOTPROVEN']
ten=[('current coordinate',root['coordinate']),('this batch','Independent CHANGES_REQUIRED F0/M1/m1;245 product cases once,guard4 once,replay8 observations once,targeted20 observations once'),('last passed gate',root['last_passed_gate']),('current blocking gate',root['current_blocking_gate']),('route position','Root adjudication -> bounded resource correction -> isolated review -> parent/native/A06/Gate0 -> finite real quality and human/release gates'),('remaining work',['NM03-R1 descriptor ownership on post-open error','NM03-r2 capacity admission before excess opens']+blockers),('next owner','Root architecture/gate owner for disposition; implementation remains separate'),('authorization','Already authorized offline review; no new human approval required and no product runtime authority inferred'),('evidence directory','reports/v0-s3/product-gate0/independent-p3b-correction-07/'),('exact stop reason','Assigned independent review completed; hand off full local commit SHA/report/counts and keep terminal visible')]
receipt=dict(kind='INDEPENDENT_P3B_CORRECTION07_AGGREGATE_REVIEW',decision='CHANGES_REQUIRED',counts=counts,candidate_sha='fd96cbc37574b382f483e757e8d7235ed5d2598c',evidence_commit='55e5463ae1bd1dd9f6c9c19bda347fe5900051ff',root_gitshow_only='5f7701988f25cb2a52cc27900856d8750e29a449',prior_review='4fb52ff3d4ef0b6bb4bcadabbd0598ce581a81af',root_adjudication='d0cc0f99ed33c73bd2a33d717e8eecee1c5e9abe',merge='Requested git merge --no-edit evidence then code; evidence fast-forward from4fb52ff and code already ancestor; initial worktree clean, no rootmetadata/V2 merge beyond evidence ancestry',product_tests=245,preserved_cases=232,preserved_definitions=180,new_definitions=13,adapted_definitions=0,deleted_definitions=0,changed_old_helpers=0,guard_events=4,replay_observations=8,targeted_observations=20,stage_pass_claim=False,product_gate0=False,component_recommendation_only=True,invocations=invocations,static_audit=static,test_obligation_audit=audit,closure_mapping=closure,findings=findings,replay=replay,targeted=targeted,blockers=blockers,ten_fields=dict(ten),development_outline=root['development_outline'],before_pins=static['current_pins'],after_pins={p:sha(PACK/p) for p in static['current_pins']},zero_actual_actions=['Windows','WSL','PowerShell','parser','hostexe hashing','realmedia','FFmpeg','models','GPU','services','network','download','real ledger','claims','fullcheckpoint'],history='Retained diagnostic/final raw bytes and per-run identities read as-is; correction03 unguarded12 UNKNOWN/uncredited; current green cannot recertify old runner bytes',fixture_cleanup='All four runner roots removed; replay and targeted roots registered/removed; tiny and broken fixtures are declared children of the targeted registered root; two injected fstat leaks measured then explicitly closed by probe before root cleanup; no old root scanning/deletion',audit_limit='Named Python auditguard, not native direct-syscall immunity or universal host concurrency/hostilekernel/nativeWindows guarantee')
write('receipt.json',receipt)
text='''# Independent P3B correction07 aggregate review

**CHANGES_REQUIRED — Fatal0 / Major1 / Minor1.** Component recommendation only; no StagePASS or productPASS. All six previous named-custody counterexamples are now closed. NM03 resource/error closure remains incomplete: a post-open metadata failure leaks an unregistered descriptor; capacity is checked after the excess open.

Code `fd96cbc37574b382f483e757e8d7235ed5d2598c` and evidence `55e5463ae1bd1dd9f6c9c19bda347fe5900051ff` were integrated using the requested `git merge --no-edit`: evidence fast-forwarded the clean existing review worktree, and code was already an ancestor. Root intake/current outline was read only by gitshow `5f7701988f25cb2a52cc27900856d8750e29a449`. AGENTS, governance/routing, frozen contract/projection, prior review4fb52ff and root adjudicationd0cc0f9 were inspected. Implementation statements were navigation only. No rootmetadata/V2 merge was added beyond actual evidence ancestry.

|Invocation, once each|Result|Inner / outer true exit|
|---|---|---|
|Combined suite|245 passed in92.45s|0 / 0|
|Guard selftest|4 audit events blocked|0 / 0|
|Immutable correction07 replay with output-only adapter|8 observations, including6 intended counterexamples refused|0 / 0|
|Independent bounded targeted observations|20 observations, including2 cleanup defects and1 admission defect|0 / 0|

All executable product/test observations used the inspected immutable correction05 runner. Its auditguard installs before pytest/plugins/ANY product/test imports; plugin autoload, cache and bytecode are disabled. connect/bind/DNS/Popen/system/exec/spawn/fork are blocked. This is named Python audit coverage, not native direct-syscall immunity. Exact argv/cwd, raw stdout/stderr byte hashes/lengths, imported absolute paths/hashes and true inner/outer exits are retained. Exit0 for an observation means capture completed, including reproduced defects; observations are not extra product tests. No focused13 separately, old22/33 matrices,232+13 separately, capmatrix, P3A121/P2B237 or fullproject run.

## Major NM03-R1: ownership gap on a post-open metadata failure

**Locations:** tools/v0_s3_quality_phase.py:2822 `_open_child_directory`,2850 `_open_leaf`; transfer callers2948/2965.

**Trigger and expectation:** In a fresh four-byte fixture, let the actual boundary's os.open succeed, then inject one ordinary OSError(EIO) into the first fstat of that new descriptor. Every successful open must be owned immediately and released if acquisition refuses, including before custody insertion.

**Actual:** Both leaf and child-directory hooks fire exactly once. `boundary.close()` leaves the opened descriptor alive and procfs count rises8->9 in each isolated observation. The descriptor is absent from both `_fds` and `_custody`: fstat runs before guarded cleanup or ownership transfer. The probe measures the leak, then explicitly closes that known descriptor, restoring8. This is owner-level injected error evidence, not a claim to have observed an actual OS EIO or this injected error through public QS. Public QS uses these same helpers and finally calls this same boundary.close, so source inspection establishes that its cleanup cannot find the unregistered descriptor.

This is an existing open-helper gap within the explicitly assigned NM03 resource/error obligation, not a reopening of an unrelated historical closure. Scores fail closed, but repeated metadata failures can accumulate FDs outside the registry; unconditional cleanup/finite-FD claims are unsupported. Recommend keeping every successful open under cleanup ownership until safe custody transfer. No fix was made.

Evidence: targeted-observations.json `postopen_fstat_error_leaf` and `postopen_fstat_error_directory`; targeted raw stdout, inner receipt and outer receipt. findings.json records complete locations/trigger/expected/actual/evidence.

## Minor NM03-r2: cap admission happens after the excess open

**Locations:** tools/v0_s3_quality_phase.py:2649 `_NamedCustody.take`,2948 `_retain_directory`,2965 `_retain_leaf`.

**Trigger and expectation:** Fill custody with72 distinct four-byte leaves, then request a73rd. The internal cap72=4*(16+2) must refuse after a dedup miss and before any excess open.

**Actual:** Exact72 succeeds, all old entries remain, and final close returns8. The73rd request nevertheless performs one actual os.open, growing procfs count84->85 transiently; only then does take close that new FD and raise `QS_ARTIFACT_CUSTODY_LIMIT_EXCEEDED:f72`. Admission is late. Normal retained use remains finite and no aggregate was incorrectly accepted; severity is Minor because this observation is one extra transient descriptor, not unbounded normal growth. Recommend capacity admission before opening a new distinct entry, with exception-safe transfer. The cap is internal, not a public threshold or a demand to alter the frozen16 shape.

Evidence: targeted-observations.json `exact72_oneover73_admission`, raw targeted output and receipts.

## Named lifetime, final completion and deduplication now hold

`_NamedCustody.take` stores `(parent_fd,name,originalidentity,kind,actualfd)` on first acquisition. All parents are either the pinned phase anchor or previously retained directories. `_retain_directory/_retain_leaf` find by pinned parent FD and name, verify the original identity/current no-follow name, and return the original descriptor. They do not reopen/adopt replacements. `_verify_custody_entry` compares fstat of the actual held FD to the original identity, then checks the current parent-relative name/type. `read` resets offsets with lseek, validates the current chain and invokes whole-boundary verify after the read. Public recompute_scores uses the same boundary for canonical, seal and raw reads and calls final verify at3638 before return, then closes in finally. No earlier entry is silently dropped. The duplicate branch in take is not used by ordinary repeated-read callers because their verified find returns first; all parent FDs remain owned until close, so ordinary dedup keys cannot acquire recycled-descriptor aliases.

The immutable replay's six intended hooks all fire exactly once with unchanged genuine originals/caller receipts: canonical symlink during seal read; canonical same-byte plain replacement during raw0; seal missing during raw0; raw0 leaf symlink during raw1; raw0 parent plain replacement during raw1; canonical redirect immediately before final completion verify. All refuse at the intended source-plan/raw/custody checks. None is a setup-only refusal and none aggregates. Clean genuine baseline remains16 submissions/34 reservations,10 usable images/6 videos/critical0.

Nine independent adjacent/final cases also refuse: canonical missing; seal plain/symlink; raw0 leaf plain/missing; raw0 parent missing/symlink; seal missing at completion; raw0 parent plain at completion. Every hook fires1, retained original SHA and caller receipt stay unchanged, and FD counts return8->8. Three same-name repeated-read replacements (plain/missing/symlink) refuse with the original registry entry and descriptor identity unchanged.

Finite normal FD proof: full16 shape consumes35 distinct entries:2 top leaves+shared rows directory+16 row directories+16 raw leaves. Four anchor descriptors add39 to the observed baseline8, giving47. Three full rereads keep47 and the exact original registry; idempotent close returns8. Replay's three-name/eight-repeat observation independently holds5 entries and17 FDs, closing to8. At the cap, normal owned FDs are4+72, and the implementation has the one transient extra open described above. This bound excludes unrelated host FDs and fails as an unconditional error bound because of NM03-R1. Constructor refusal and retained read/lseek/stat errors close back to8; the two new pre-transfer fstat errors are the explicit exceptions. No universal host concurrency, hostilekernel or nativeWindows guarantee is demanded.

## Prior closures and original obligations preserved

All232 prior nodeids remain in the245 collected suite; all180 original test definitions/decorators/bodies and old helpers are AST-identical,0 adapted/0 deleted.13 added definitions generate13 cases. test-obligation-audit.json records each new test's assertions/calls/locations. Seven new handoff/final tests invoke public recompute_scores after genuine owner runs, assert fired hooks and target errors; success/refusal cleanup and baseline also use public QS. Three repeated/growing-byte/FD tests directly exercise the actual boundary owner. These are appropriate focused owner checks, not replacements for public QS tests. They omit post-open fstat failure and pre-open cap admission, explaining the remaining findings despite245 green.

M01 remains closed: active recursive `_json_fact_equal` compares JSON types including bool/int/finitefloat, full keysets and list elements. Actual call sites in seal alignment, release/source binding and exhaustive top/row content checks were inspected; static-audit.json lists them. Typed equality/strict integer seal ordinals, closed top/row/source/release/GPU keysets and monotone verdict handling are unchanged. Supplied facts cannot replace canonical facts; unknown failures cannot become known, knownFAIL stays resolved/notusable, conservative downgrade remains allowed, and critical3 remains visible and forces failure under the preserved tests. No all-technical-success requirement was added.

M08 full seal label/order/source identity/path/bytes/hash alignment and NM04 final original-source check remain closed. The inspected `_execute_row` resolves all driver getters including cachedsubmit, then validates the sealed ORIGINAL source, takes one coherent clock/proof/ownership guard, reserves provider budget, charges attempt and calls cachedsubmit. No new getter/callback/clock appears in that interval. Original capacity0/clock10801/exact10800/oneover10801/laterproof/no-refund/no-retry tests remain AST-identical and passed in245. M02/M03/M04/M05/M06/M07/M09/m01 are not reopened absent regression. closure-map.json preserves prior mapping and explicitly splits NM03 lifetime closure from current resource issues.

Fixed16/34 calls, images8/10, videos5/6, score>=8, critical0, raw preservation/storage/cleanup remain unchanged. Actual public production nodes, ControlledImageOwner/BridgeOwner and production oracles run with only synthetic provider/HTTP/tinydecoder substitutions. Fresh4x4PNG/tinyfakevideo remain within owned bounded roots; no real decoder/server was used. A coherent rewrite of BOTH trusted originals remains outside the signature obligation. Parent archive/retained-attestation selectedroot binding is a real integration prerequisite, not arbitrary unbound archive trust.

## Evidence identity, retained history and scope

'''
for p,h in static['current_pins'].items(): text+='- `'+p+'`: `'+h+'`\n'
text+='''
All four independent receipts bind source/runner/probe before+after and actual imported paths/hashes; guard imports no product module. Replay adapter verifies immutable probe bytes and changes only OUT in the in-memory program before execution; the immutable probe's filename remains its own. The runner additionally pins the adapter. Static/final reads bind the original probe before/after. Candidate argument is never attestation. Read-only Git/AST/hash auditing imports no product/test code and is separate from guarded execution.

Independently checked all25 implementation checksum entries and retained raw stream bindings (the8 final streams plus4 retained debug streams); no mismatch. All6 debug/final implementation invocation exits are0. Per-invocation source/runner/probe/import identities remain in static-audit.json; diagnostic paths moved under debug are resolved to retained bytes without relabeling. Earlier diagnostics and any historical source changes remain as recorded, not regenerated or recertified from final green. Original correction03 unguarded12 remain UNKNOWN/uncredited under the preserved erratum, with no cosmetic rerun.

All4 runner-owned roots and registered replay/targeted roots were removed. The targeted root owns its declared tiny/broken children. Explicit probe remediation closed only the two known leaked descriptors after measurement; runner removal is not proof that the product closed them. No old root was scanned/deleted. Only new text under this review subtree is authored; no candidate/tools/tests/spec/oldreports/runners/logs/checksums/coordinate/manifest were changed. No binaries/DB/ZIP/copied product source, push, permanent config or history rewrite. Actual Windows/WSL/PowerShell/parser/hostexe hashing/realmedia/FFmpeg/models/GPU/services/network/download/realledger/claims/fullcheckpoint all0. No testSource/holdouts/fullprelabels were read.

Parent owned original archive/retained attestation and selected-root binding remain NOTPROVEN. Parent hardwatchdog remains UNIMPLEMENTED_PRODUCT_GATE0_BLOCKER; native residue-admission/A06, registration-installrollback, authenticdebit, realquality/full12/Gate0/human-release remain NOTPROVEN. This component review completes no product Stage.

## Ten-field handoff

'''
for i,(name,value) in enumerate(ten,1):
    rendered=value if isinstance(value,str) else json.dumps(value,ensure_ascii=False)
    text+=str(i)+'. '+name+': '+rendered+'\n\n'
text+='## Full V0–V3 outline from root gitshow5f77019\n\nCurrent Stage **R1**; this component review changes none of these implementation/machine/independent/human counts. Full source and evidence paths are retained in root-current-control.json and receipt.json.\n\n|Delivery|Stage|Done/total|Implementation|Machine|Independent|Human|\n|---|---|---:|---|---|---|---|\n'
for row in root['development_outline']:
    text+='|'+str(row['delivery'])+'|'+row['stage_id']+'|'+str(row['completed_substeps'])+'/'+str(row['total_substeps'])+'|'+row['implementation']+'|'+row['machine_acceptance']+'|'+row['independent_review']+'|'+row['human_signoff']+'|\n'
text+='\nFull declared substeps:\n\n'
for row in root['development_outline']:
    text+='- **'+row['stage_id']+'**: '+'; '.join(s['name']+' ['+s['status']+']' for s in row['substeps'])+'.\n'
(OUT/'review.md').write_text(text)
write('final-bindings.json',dict(before=static['current_pins'],after={p:sha(PACK/p) for p in static['current_pins']},unchanged=static['current_pins']=={p:sha(PACK/p) for p in static['current_pins']}))
checks=[]
for path in sorted(OUT.rglob('*')):
    if path.is_file() and path.name!='SHA256SUMS': checks.append(sha(path)+'  '+str(path.relative_to(OUT)))
(OUT/'SHA256SUMS').write_text('\n'.join(checks)+'\n')
print(json.dumps(dict(decision='CHANGES_REQUIRED',counts=counts,product_tests=245,guard=4,replay_observations=8,targeted_observations=20,unchanged_pins=receipt['before_pins']==receipt['after_pins']),indent=2))
