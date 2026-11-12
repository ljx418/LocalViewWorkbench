"""Bounded independent observations, run only under the immutable pre-import guard."""
import copy, hashlib, json, os, shutil, tempfile
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT = Path(__file__).resolve().parent
ROOT = Path(tempfile.mkdtemp(prefix='independent-c05-focused-'))
results = []
owned = []
def prep(name):
    root = ROOT / name
    owned.append(str(root))
    return t._prepare(root, clock=t.FakeClock(step=0.0))
def observe(name, r, p, scores=None, **extra):
    try:
        v = q.recompute_scores(r, p.directory, scores if scores is not None else t._scores(r, r['projection_sha256']), independence=t._independence())
        v = {k:v[k] for k in ('aggregate_pass','all_rows_resolved','thresholds','rows')}
        v['rows'] = [v['rows'][0]]
    except Exception as e:
        v = {'rejected':type(e).__name__, 'error':str(e)}
    results.append({'name':name, 'result':v, **extra})
def brief(r,d):
    return {'sends':d.submissions,'charges':r['public_submissions'],'reserved':r['provider_calls_reserved'],'counts':r['test_counts'],'errors':[x['error_code'] for x in r['rows']], 'attempts':r['public_submissions_attempted']}
try:
    p,d,_ = prep('overlays'); r=p.run()
    observe('honest_baseline',r,p)
    mutations = [
        ('attempt_true_to_int1',lambda x:x['rows'][0].update(public_submission_attempted=1)),
        ('counter_one_to_bool',lambda x:x['rows'][0].update(provider_calls=True)),
        ('source_extra_fact',lambda x:x['rows'][0]['source_evidence'].update(independent_added_fact='fabricated')),
        ('receipt_extra_fact',lambda x:x.update(independent_added_fact='fabricated')),
        ('row_extra_fact',lambda x:x['rows'][0].update(independent_added_fact='fabricated')),
        ('release_extra_fact',lambda x:x['rows'][0]['release_evidence'].update(independent_added_fact='fabricated')),
        ('known_fail_overlay',lambda x:x['rows'][0].update(execution_status='FAIL',error_code='PUBLIC_EXECUTION_NOT_SUCCESSFUL')),
        ('unknown_fail_overlay',lambda x:x['rows'][0].update(execution_status='FAIL',error_code='INDEPENDENT_UNKNOWN')),
        ('cleanup_null',lambda x:x['rows'][0].update(cleanup_unproven=None)),
        ('storage_int0',lambda x:x.update(storage_unproven=0)),
        ('source_null',lambda x:x['rows'][0].update(source_evidence=None)),
        ('baseline_omitted',lambda x:x.pop('parent_budget_baseline_gpu_mib')),
        ('run_root_null',lambda x:x.update(run_root=None)),
        ('attempt_omitted',lambda x:x['rows'][0].pop('public_submission_attempted')),
        ('release_vector_welltyped',lambda x:x['rows'][0]['release_evidence'].update(gpu_samples=[{'monotonic_seconds':i,'gpu_used_mib':101} for i in range(3)])),
    ]
    for name,fn in mutations:
        doc=copy.deepcopy(r); fn(doc); observe(name,doc,p, canonical_unchanged=json.loads((p.directory/q.CANONICAL_RECEIPT_NAME).read_text())==r)
    scores=t._scores(r,r['projection_sha256']); scores[0]['critical_hallucinations']=3
    doc=copy.deepcopy(r);doc['rows'][0].update(execution_status='FAIL',error_code='PUBLIC_EXECUTION_NOT_SUCCESSFUL')
    observe('known_overlay_critical3_visible',doc,p,scores)
    # Shared validators really execute in QD and QS; instrument only counters.
    counters={'source':0,'release':0}; source=q.validate_source_evidence;release=q.validate_release_evidence
    def sv(*a,**kw): counters['source']+=1; return source(*a,**kw)
    def rv(*a,**kw): counters['release']+=1; return release(*a,**kw)
    q.validate_source_evidence=sv;q.validate_release_evidence=rv
    p2,d2,_=prep('validators');r2=p2.run();qd=dict(counters);observe('shared_validators',r2,p2,qd_counts=qd)
    results[-1]['total_counts']=dict(counters)
    q.validate_source_evidence=source;q.validate_release_evidence=release
    # Bounded content boundary exact n / n+1 with tiny fixture, same owner read call.
    fixture=p.directory/'independent-small.raw'; fixture.write_bytes(b'abcd')
    boundary=q._ArtifactBoundary(p.directory)
    for limit in (4,3):
        try: value={'bytes':len(boundary.read(fixture.name,limit))}
        except Exception as e:value={'error':str(e)}
        results.append({'name':'bounded_read_limit_'+str(limit),'result':value})
    boundary.close();fixture.unlink()
    # Missing/staged/corrupt/foreign canonical, each restore original bytes.
    canonical=p.directory/q.CANONICAL_RECEIPT_NAME;raw=canonical.read_bytes()
    for mode in ('missing_staged_remains','corrupt','foreign'):
        if mode=='missing_staged_remains':canonical.unlink()
        elif mode=='corrupt':canonical.write_bytes(b'{')
        else:
            doc=copy.deepcopy(r);doc['run_id']='foreign-run';canonical.write_text(q.canonical_json(doc))
        observe('canonical_'+mode,r,p)
        canonical.write_bytes(raw)
    # Deterministic single-thread redirect AFTER opening pinned descriptors,
    # during canonical read, leaving all genuine artifacts byte-identical.
    for level in ('run_root','temp','phase','raw_parent'):
        px,dx,_=prep('race-'+level);rx=px.run()
        target={'run_root':px.root,'temp':px.root/'temp','phase':px.directory,'raw_parent':(px.directory/rx['rows'][0]['raw_artifact']).parent}[level]
        retained=target.with_name(target.name+'-retained');hits=[];read=q.os.read
        def hooked(fd,n):
            value=read(fd,n)
            if not hits:
                hits.append(1);target.rename(retained);target.symlink_to(retained,target_is_directory=True)
            return value
        q.os.read=hooked
        try:observe('redirect_during_read_'+level,rx,px,trigger='first bounded canonical os.read; unchanged original artifacts')
        finally:q.os.read=read
        results[-1]['redirect_executed']=bool(hits)
        results[-1]['symlink_at_return']=target.is_symlink()
        target.unlink();retained.rename(target)
    # Accessor changes to source content/path/identity, first and later rows.
    for accessor,mutation,index in [('submissions','content',0),('submit','path',0),('max_public_submissions','ctime',0),('submit','content',5),('submissions','path',5)]:
        name='handoff-'+accessor+'-'+mutation+'-'+str(index)
        px,dx,projection=prep(name); samples=json.loads(projection)['samples'];hits=[];base=type(dx)
        class Driver(base):
            def __getattribute__(self,key):
                value=super().__getattribute__(key)
                if key==accessor and not hits and px._sealed_identities and px._submissions==index:
                    hits.append(key);target=px.root/'input'/samples[index]['input_reference']
                    if mutation=='content':
                        data=bytearray(target.read_bytes());data[-1]^=1;target.write_bytes(data)
                    elif mutation=='path':
                        saved=target.with_name(target.name+'.retained');target.rename(saved);target.write_bytes(saved.read_bytes())
                    else:os.chmod(target,0o600)
                return value
        dx.__class__=Driver
        rx=px.run();results.append({'name':name,'trigger':hits,'result':brief(rx,dx)})
finally:
    shutil.rmtree(ROOT)
payload={'results':results,'count':len(results),'owned_root':str(ROOT),'registered_roots':owned,'removed':not ROOT.exists()}
(OUT/'focused-observations.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
print(json.dumps(payload,indent=2,sort_keys=True))
