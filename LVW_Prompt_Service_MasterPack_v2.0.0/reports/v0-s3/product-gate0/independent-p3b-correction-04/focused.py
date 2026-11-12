"""Independent bounded public-owner probes. Execute only through inspected guard."""
import copy, hashlib, inspect, json, os, shutil, tempfile
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT=Path(__file__).resolve().parent
ROOT=Path(tempfile.mkdtemp(prefix='lvw-independent-c04-'))
RESULTS=[]
def record(name, **kw): RESULTS.append({'probe':name,**kw})
def prep(name): return t._prepare(ROOT/name,clock=t.FakeClock(step=0.0))
def brief(p,d,r):
    return {'sends':d.submissions,'charges':r['public_submissions'],'reserved':r['provider_calls_reserved'],'observed':r['provider_calls_observed'],'counts':r['test_counts'],'rows':len(r['rows']),'first_error':r['rows'][0].get('error_code'),'last_error':r['rows'][-1].get('error_code'),'storage_unproven':r['storage_unproven'],'cleanup_unproven':r['cleanup_unproven'],'closed':all(getattr(p,n) is None for n in ('_owned_root','_owned_temp','_owned_phase')),'retries':sum(x.get('automatic_retries',0) for x in r['rows'])}
def score(r,p,s=None):
    try:
        o=q.recompute_scores(r,p,s or t._scores(r,r['projection_sha256']),independence=t._independence())
        return {'aggregate':o['aggregate_pass'],'resolved':o['all_rows_resolved'],'thresholds':o['thresholds'],'first':o['rows'][0]}
    except Exception as e: return {'rejected':type(e).__name__,'detail':str(e)}
def canon(p,r):
    (p.directory/q.CANONICAL_RECEIPT_NAME).write_text(q.canonical_json(r))
try:
    p,d,_=prep('baseline'); r=p.run(); original=copy.deepcopy(r)
    record('baseline',run=brief(p,d,r),qs=score(r,p.directory),actual_files=sum(x.is_file() for x in p.directory.rglob('*')),actual_bytes=sum(x.stat().st_size for x in p.directory.rglob('*') if x.is_file()),seal_initial_bytes=(p.directory/q.SOURCE_PLAN_NAME).stat().st_size)
    # Missing, null and noninteger mandatory contexts on both PASS and known FAIL.
    for status in ('PASS','FAIL'):
        for key,values in [('run_root',['ABSENT',None,100.0,True]),('parent_budget_baseline_gpu_mib',['ABSENT',None,100.0,True])]:
            for value in values:
                doc=copy.deepcopy(r)
                if status=='FAIL': doc['rows'][0].update(execution_status='FAIL',error_code='PUBLIC_EXECUTION_NOT_SUCCESSFUL')
                if value=='ABSENT': doc.pop(key,None)
                else: doc[key]=value
                record('context.'+status+'.'+key+'.'+repr(value),qs=score(doc,p.directory))
    # All supplied execution evidence must describe the actual canonical run.
    for name,mutate in [('valid_but_fabricated_release_samples',lambda x:x['rows'][0]['release_evidence'].update(gpu_samples=[{'monotonic_seconds':i,'gpu_used_mib':0} for i in range(3)])),('fabricated_bound_baseline_and_release',lambda x:(x.update(parent_budget_baseline_gpu_mib=200),[a['release_evidence'].update(baseline_gpu_mib=200) for a in x['rows']])),('fabricated_terminal_counts',lambda x:x.update(test_counts={'fixed':16,'PASS':0,'FAIL':16,'BLOCKED':0,'NOT_RUN':0})),('fabricated_attempt_row',lambda x:x['rows'][0].update(public_submission_attempted=False))]:
        doc=copy.deepcopy(r); mutate(doc); record(name,qs=score(doc,p.directory),canonical_unchanged=json.loads((p.directory/q.CANONICAL_RECEIPT_NAME).read_text())['rows'][0]['release_evidence']==original['rows'][0]['release_evidence'])
    # Root ancestor redirect after a real run; no canonical/seal bytes rewritten.
    (p.root/'temp').rename(p.root/'retained-temp'); (p.root/'temp').symlink_to(p.root/'retained-temp',target_is_directory=True)
    record('qs_temp_ancestor_symlink',qs=score(r,p.directory),symlink=str(p.root/'temp'),canonical_original=True)
    (p.root/'temp').unlink(); (p.root/'retained-temp').rename(p.root/'temp')
    # Source-plan label alignment: mutate seal label only, rebind hash in canonical.
    planpath=p.directory/q.SOURCE_PLAN_NAME; planraw=planpath.read_bytes(); plan=json.loads(planraw)
    for field,value in [('asset_id','FOREIGN-ASSET'),('media_kind','video'),('input_reference','foreign.png')]:
        altered=copy.deepcopy(plan); altered['rows'][0][field]=value
        raw=q.canonical_json(altered).encode(); planpath.write_bytes(raw)
        doc=copy.deepcopy(r); doc['source_plan'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()); canon(p,doc)
        record('seal_label_alignment.'+field,qs=score(doc,p.directory),prerequisites='write seal bytes and canonical source_plan binding; preserve canonical execution rows and raw')
    planpath.write_bytes(planraw); canon(p,r)
    # Coherent original-identity rewrite requires control of BOTH trusted artifacts and supplied copy.
    altered=copy.deepcopy(plan); altered['rows'][0]['identity'][0]+=1
    raw=q.canonical_json(altered).encode(); planpath.write_bytes(raw)
    doc=copy.deepcopy(r); doc['rows'][0]['source_evidence']['identity'][0]+=1
    doc['source_plan'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()); canon(p,doc)
    record('consistent_seal_and_canonical_identity_rewrite',qs=score(doc,p.directory),prerequisites='write original seal, authoritative canonical row and source_plan hash, plus supplied receipt; no independent parent attestation supplied')
    planpath.write_bytes(planraw); canon(p,r)
    # Row mutation of a seal-only identity cannot pass unchanged canonical binding.
    for name,mutator in [('swap_whole_rows',lambda x:x['rows'].__setitem__(slice(0,2),list(reversed(x['rows'][:2])))),('swap_descriptor',lambda x:x['rows'][0].update(identity=x['rows'][1]['identity'],path=x['rows'][1]['path']))]:
        altered=copy.deepcopy(plan); mutator(altered); raw=q.canonical_json(altered).encode(); planpath.write_bytes(raw)
        doc=copy.deepcopy(r);doc['source_plan'].update(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest());canon(p,doc)
        record('seal_swap.'+name,qs=score(doc,p.directory))
    planpath.write_bytes(planraw);canon(p,r)
    # A genuine production run with one injected unknown validation failure after actual owner/oracle.
    p2,d2,_=prep('unknown-validation');validate=p2._validate_row
    def unknown(row,*args):
        validate(row,*args)
        if row['ordinal']==1: raise q.QualityContractError('INDEPENDENT_UNKNOWN_VALIDATION')
    p2._validate_row=unknown; r2=p2.run()
    record('published_unknown_failure',run=brief(p2,d2,r2),qs=score(r2,p2.directory))
    doc=copy.deepcopy(r2);doc['rows'][0]['error_code']='PUBLIC_EXECUTION_NOT_SUCCESSFUL'
    record('published_unknown_failure_supplied_known_error',qs=score(doc,p2.directory),canonical_error=r2['rows'][0]['error_code'],only_changed='supplied rows[0].error_code')
    # One genuine known structure failure; supplied PASS never makes it usable; critical remains global.
    p3,d3,_=prep('known-failure');validate=p3._validate_row
    def known(row,*args):
        validate(row,*args)
        if row['ordinal']==1: raise q.QualityContractError('PUBLIC_EXECUTION_NOT_SUCCESSFUL')
    p3._validate_row=known;r3=p3.run();doc=copy.deepcopy(r3);doc['rows'][0].update(execution_status='PASS',error_code=None)
    record('published_fail_supplied_pass',run=brief(p3,d3,r3),qs=score(doc,p3.directory))
    scores=t._scores(r3,r3['projection_sha256']);scores[0]['critical_hallucinations']=3
    record('published_fail_critical3',qs=score(r3,p3.directory,scores))
    # Dynamic submissions getter, submit binding, limit boundary and source identity handoff.
    for name in ('submissions_capacity0','submit_binding_clock10801','limit_source_identity_changed','later_capacity0'):
        p4,d4,_=prep(name);p4.parent_budget['expires_monotonic']=20000.0; trigger=[]
        if name=='later_capacity0':
            def authorize(action,subject):
                if action=='quality_public_submit' and d4.submissions==1:p4.parent_budget['action_capacity']=0
            p4.authorize=authorize
        else:
            originalclass=type(d4)
            class Driver(originalclass):
                def __getattribute__(self,key):
                    value=super().__getattribute__(key)
                    target={'submissions_capacity0':'submissions','submit_binding_clock10801':'submit','limit_source_identity_changed':'max_public_submissions'}[name]
                    if key==target and not trigger:
                        trigger.append(key)
                        if name=='submissions_capacity0':p4.parent_budget['action_capacity']=0
                        elif name=='submit_binding_clock10801':p4.clock.now=10801.0
                        else:
                            source=p4.root/'input'/'image-00.png'
                            # Locate the first source from the frozen synthetic projection, no external scanning.
                            source=p4.root/'input'/json.loads(p4.projection_bytes)['samples'][0]['input_reference']
                            st=source.stat();os.utime(source,ns=(st.st_atime_ns,st.st_mtime_ns+1000000))
                    return value
            d4.__class__=Driver
        r4=p4.run()
        extra={}
        if name=='limit_source_identity_changed':
            source=p4.root/'input'/r4['rows'][0]['input_reference'];actual=p4._identity(source.stat());sealed=json.loads((p4.directory/q.SOURCE_PLAN_NAME).read_text())['rows'][0]['identity']
            extra={'actual_identity':actual,'sealed_identity':sealed,'changed':actual!=sealed,'qs':score(r4,p4.directory)}
        record(name,run=brief(p4,d4,r4),trigger=trigger,**extra)
    # Production source plan failure must release all handles with no sends, all terminal rows.
    p5,d5,_=prep('seal-storage-failure'); artifact=p5._artifact
    def failing(path,raw):
        if path==q.SOURCE_PLAN_NAME:raise q.QualityContractError('ARTIFACT_WRITE_FAILED:independent')
        return artifact(path,raw)
    p5._artifact=failing;r5=p5.run();record('seal_storage_failure',run=brief(p5,d5,r5),canonical_exists=(p5.directory/q.CANONICAL_RECEIPT_NAME).exists())
    # Shared source validator actually runs initially and twice per send, release once per row.
    calls=[];src=q.validate_source_evidence;rel=q.validate_release_evidence
    def traced_src(*args,**kwargs):calls.append({'kind':'source','sealed':kwargs.get('sealed') is not None});return src(*args,**kwargs)
    def traced_rel(*args,**kwargs):calls.append({'kind':'release'});return rel(*args,**kwargs)
    q.validate_source_evidence=traced_src;q.validate_release_evidence=traced_rel
    try:
        p6,d6,_=prep('shared-trace');r6=p6.run();qd=copy.deepcopy(calls);calls.clear();qs=score(r6,p6.directory)
        record('shared_validator_execution',qd=qd,qs_calls=calls,run=brief(p6,d6,r6),qs=qs)
    finally:q.validate_source_evidence=src;q.validate_release_evidence=rel
finally:
    shutil.rmtree(ROOT)
(OUT/'focused-observations.json').write_text(json.dumps({'results':RESULTS,'count':len(RESULTS),'owned_root':str(ROOT),'removed':not ROOT.exists()},indent=2)+'\n')
print(json.dumps({'results':RESULTS,'count':len(RESULTS),'removed':not ROOT.exists()},indent=2))
