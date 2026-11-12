"""Bounded independent observations; execute only through inspected guarded runner."""
import copy, hashlib, json, os, shutil, tempfile
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT=Path(__file__).resolve().parent
ROOT=Path(tempfile.mkdtemp(prefix='independent-c06-'))
owned=[]; results=[]
def prep(name):
    root=ROOT/name;owned.append(str(root))
    p,d,projection=t._prepare(root,clock=t.FakeClock(step=0.0));r=p.run()
    return p,d,r

def observe(name,p,r,**extra):
    try:
        v=q.recompute_scores(r,p.directory,t._scores(r,r['projection_sha256']),independence=t._independence())
        result={k:v[k] for k in ('aggregate_pass','all_rows_resolved','thresholds')}
        result['row0']=v['rows'][0]
    except Exception as e:result={'error':type(e).__name__+':'+str(e)}
    results.append({'name':name,'result':result,**extra})

def hook(inode,action):
    original=q.os.read;state={'fired':0}
    def read(fd,n):
        value=original(fd,n)
        if not state['fired'] and os.fstat(fd).st_ino==inode:
            state['fired']+=1;action()
        return value
    q.os.read=read
    return original,state

def change(target,mode):
    retained=target.with_name(target.name+'.retained')
    target.rename(retained)
    if mode=='symlink':target.symlink_to(retained,target_is_directory=retained.is_dir())
    elif mode=='plain':
        if retained.is_dir():target.mkdir()
        else:target.write_bytes(retained.read_bytes())
    return retained

try:
    p,d,r=prep('typed')
    observe('genuine_baseline',p,r,submissions=d.submissions,provider_calls=r['provider_calls_reserved'])
    for field in ('bytes','identity'):
        doc=copy.deepcopy(r)
        if field=='bytes':doc['rows'][0]['source_evidence'][field]=float(doc['rows'][0]['source_evidence'][field])
        else:doc['rows'][0]['source_evidence'][field][1]=float(doc['rows'][0]['source_evidence'][field][1])
        observe('source_nested_equal_float_'+field,p,doc)
    for field in ('elapsed_seconds','baseline_gpu_mib'):
        doc=copy.deepcopy(r);v=doc['rows'][0]['release_evidence'][field]
        doc['rows'][0]['release_evidence'][field]=float(v) if type(v) is int else int(v)
        observe('release_nested_type_'+field,p,doc,original_type=type(v).__name__)
    for field in ('monotonic_seconds','gpu_used_mib'):
        doc=copy.deepcopy(r);v=doc['rows'][0]['release_evidence']['gpu_samples'][0][field]
        doc['rows'][0]['release_evidence']['gpu_samples'][0][field]=float(v) if type(v) is int else int(v)
        observe('gpu_nested_type_'+field,p,doc,original_type=type(v).__name__)
    for name,mutate in [
        ('missing_source',lambda x:x['rows'][0].pop('source_evidence')),
        ('null_release',lambda x:x['rows'][0].update(release_evidence=None)),
        ('storage_int0',lambda x:x.update(storage_unproven=0)),
        ('cleanup_null',lambda x:x['rows'][0].update(cleanup_unproven=None)),
        ('malformed_context',lambda x:x.update(parent_budget_baseline_gpu_mib=True)),
        ('known_failure_overlay',lambda x:x['rows'][0].update(execution_status='FAIL',error_code='PUBLIC_EXECUTION_NOT_SUCCESSFUL')),
        ('optional_native_proof_added',lambda x:x['rows'][0]['release_evidence'].update(run_token='fabricated')),
    ]:
        doc=copy.deepcopy(r);mutate(doc);observe(name,p,doc)
    # Named custody during reads: include seal read and plain/missing variants.
    for name,trigger_kind,target_kind,mode in [
        ('seal_read_run_root_symlink','seal','root','symlink'),
        ('seal_read_temp_plain','seal','temp','plain'),
        ('seal_read_leaf_plain','seal','seal','plain'),
        ('canonical_read_temp_missing','canonical','temp','missing'),
        ('canonical_read_leaf_plain','canonical','canonical','plain'),
        ('raw_read_parent_plain','raw0','raw_parent','plain'),
        ('raw_read_leaf_missing','raw0','raw0','missing'),
        # Earlier artifacts are replaced AFTER their read, during another read.
        ('after_canonical_read_symlink','seal','canonical','symlink'),
        ('after_canonical_read_plain','raw0','canonical','plain'),
        ('after_seal_read_missing','raw0','seal','missing'),
        ('after_raw_read_leaf_symlink','raw1','raw0','symlink'),
        ('after_raw_read_parent_plain','raw1','raw_parent','plain'),
    ]:
        px,dx,rx=prep(name)
        paths={'root':px.root,'temp':px.root/'temp','canonical':px.directory/q.CANONICAL_RECEIPT_NAME,'seal':px.directory/rx['source_plan']['path'],'raw0':px.directory/rx['rows'][0]['raw_artifact'],'raw1':px.directory/rx['rows'][1]['raw_artifact']}
        paths['raw_parent']=paths['raw0'].parent
        trigger=paths[trigger_kind];target=paths[target_kind]
        before={k:hashlib.sha256(v.read_bytes()).hexdigest() for k,v in paths.items() if k in ('canonical','seal','raw0')}
        retained=target.with_name(target.name+'.retained')
        original,state=hook(trigger.stat().st_ino,lambda:change(target,mode))
        try:observe(name,px,rx,trigger_kind=trigger_kind,target_kind=target_kind,mutation=mode)
        finally:q.os.read=original
        results[-1].update(hook_fired=state['fired'],entry_symlink_at_return=target.is_symlink(),entry_exists_at_return=target.exists(),before_hashes=before)
        # Verify unchanged original bytes of target; no rewritten canonical/seal.
        if retained.is_file():results[-1]['retained_sha256']=hashlib.sha256(retained.read_bytes()).hexdigest()
        # Keep cleanup local: restore original directory structure, then delete own root below.
        if mode!='missing':
            if target.is_symlink() or target.is_file():target.unlink()
            else:shutil.rmtree(target)
        retained.rename(target)
    # Successful completion callback: mutate a previously read leaf at final verification.
    px,dx,rx=prep('completion_leaf')
    target=px.directory/q.CANONICAL_RECEIPT_NAME
    verify=q._ArtifactBoundary.verify;state={'fired':0}
    def final_verify(self):
        # Final verification is invoked directly by recompute_scores, not by read.
        import sys
        if sys._getframe(1).f_code.co_name=='recompute_scores' and not state['fired']:
            state['fired']+=1;change(target,'symlink')
        return verify(self)
    q._ArtifactBoundary.verify=final_verify
    try:observe('completion_canonical_leaf_redirect',px,rx)
    finally:q._ArtifactBoundary.verify=verify
    results[-1].update(hook_fired=state['fired'],entry_symlink_at_return=target.is_symlink())
    # Descriptor counts: normal close, read error, constructor partial open.
    px,dx,rx=prep('fd')
    count=lambda:len(os.listdir('/proc/self/fd'))
    n=count();b=q._ArtifactBoundary(px.directory);b.read(q.CANONICAL_RECEIPT_NAME,q.MAX_ARTIFACT_BYTES);b.close()
    results.append({'name':'fd_normal','before':n,'after':count()})
    n=count();b=q._ArtifactBoundary(px.directory)
    original=q.os.read
    def failread(fd,n):raise OSError('independent bounded read failure')
    q.os.read=failread
    try:
        try:b.read(q.CANONICAL_RECEIPT_NAME,q.MAX_ARTIFACT_BYTES)
        except OSError as e:error=str(e)
    finally:q.os.read=original;b.close()
    results.append({'name':'fd_read_error','before':n,'after':count(),'error':error})
    broken=ROOT/'partial';owned.append(str(broken));broken.mkdir();(broken/'temp').write_bytes(b'x');n=count()
    try:q._ArtifactBoundary(broken/'temp'/'s3-quality')
    except Exception as e:error=str(e)
    results.append({'name':'fd_constructor_partial','before':n,'after':count(),'error':error})
    # Tiny bounded reads and one-byte growth through actual common reader.
    small=px.directory/'small.raw';small.write_bytes(b'abcd');b=q._ArtifactBoundary(px.directory)
    for cap in (4,3):
        try:value={'length':len(b.read('small.raw',cap))}
        except Exception as e:value={'error':str(e)}
        results.append({'name':'tiny_cap_'+str(cap),'result':value})
    original,state=hook(small.stat().st_ino,lambda:small.open('ab').write(b'e'))
    try:
        try:value={'length':len(b.read('small.raw',4))}
        except Exception as e:value={'error':str(e)}
    finally:q.os.read=original;b.close()
    results.append({'name':'tiny_growth','result':value,'hook_fired':state['fired']})
finally:
    shutil.rmtree(ROOT)
payload={'kind':'INDEPENDENT_BOUNDED_OBSERVATIONS_NOT_PRODUCT_TESTS','count':len(results),'observations':results,'owned_root':str(ROOT),'registered_roots':owned,'removed':not ROOT.exists()}
(OUT/'targeted-observations.json').write_text(json.dumps(payload,indent=2)+'\n')
print(json.dumps(payload,indent=2))
