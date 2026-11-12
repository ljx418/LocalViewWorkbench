"""Bounded independent observations, actual public run/scorer, no real runtime."""
import copy,json,os,tempfile,shutil,hashlib,inspect
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT=Path(__file__).parent
ROOT=Path(tempfile.mkdtemp(prefix='focused-',dir=os.environ['TMPDIR']))
(OUT/'focused-fixtures.json').write_text(json.dumps({'root':str(ROOT),'owner':'task_6e497e41e8c1','retention':'removed by own finally'})+'\n')
RESULTS=[]
def record(name,**kw):RESULTS.append({'probe':name,**kw})
def prepare(name):return t._prepare(ROOT/name,clock=t.FakeClock(step=0.0))
def brief(r,d):return {'sends':d.submissions,'charged':r['public_submissions'],'reserved':r['provider_calls_reserved'],'counts':r['test_counts'],'first_error':r['rows'][0].get('error_code'),'last_error':r['rows'][-1].get('error_code')}
def outcome(fn):
    try:return {'value':fn()}
    except Exception as e:return {'rejected':type(e).__name__,'detail':str(e)}
try:
    p,d,_=prepare('baseline');r=p.run();scores=t._scores(r,r['projection_sha256'])
    def qs(doc,ss=None):return q.recompute_scores(doc,p.directory,ss or scores,independence=t._independence())
    def summary(doc,ss=None):
        out=qs(doc,ss);row=out['rows'][0]
        return {'aggregate_pass':out['aggregate_pass'],'usable':row['usable'],'resolved':row['resolved'],'reason':row['reason'],'evidence_reason':row.get('evidence_reason'),'critical':row['critical_hallucinations'],'thresholds':out['thresholds']}
    record('public_baseline',run=brief(r,d),score=summary(r),canonical_loaded=q.load_canonical_receipt(p.directory)['run_id'],handles_closed=all(x is None for x in [p._owned_root,p._owned_temp,p._owned_phase]))
    # Public scorer mutation matrix, both a technical PASS and a complete known FAIL.
    missing=object()
    cases=[]
    for owner in ['receipt','row']:
        for field in ['storage_unproven','cleanup_unproven']:
            for label,val in [('missing',missing),('null',None),('wrong_type',0)]:cases.append((owner+'.'+field+'.'+label,owner,[field],val))
    for field in ['path','bytes','sha256','identity']:
        for label,val in [('missing',missing),('null',None),('wrong_type',True)]:cases.append(('source.'+field+'.'+label,'row',['source_evidence',field],val))
    for i,key in enumerate(['device','inode','size','mtime','ctime']):
        cases.append(('source.identity.changed_'+key,'row',['source_evidence','identity',i],r['rows'][0]['source_evidence']['identity'][i]+1))
    cases.extend([('source.identity.allzero','row',['source_evidence','identity'],[0]*5),('source.path.foreign','row',['source_evidence','path'],'/foreign/input/image.png'),('source.bytes.mismatch','row',['source_evidence','bytes'],r['rows'][0]['source_bytes']+1),('source.sha.mismatch','row',['source_evidence','sha256'],'0'*64),('receipt.run_root.missing','receipt',['run_root'],missing),('receipt.run_root.null','receipt',['run_root'],None),('receipt.run_root.wrong_type','receipt',['run_root'],True),('receipt.baseline.missing','receipt',['parent_budget_baseline_gpu_mib'],missing),('receipt.baseline.null','receipt',['parent_budget_baseline_gpu_mib'],None)])
    for field in ['proven','loaded_models','elapsed_seconds','baseline_gpu_mib','gpu_samples']:
        for label,val in [('missing',missing),('null',None),('wrong_type','favorable')]:cases.append(('release.'+field+'.'+label,'row',['release_evidence',field],val))
    release_cases=[('loaded_bool',['loaded_models'],False),('loaded_nonzero',['loaded_models'],1),('elapsed_bool',['elapsed_seconds'],True),('elapsed_nan',['elapsed_seconds'],float('nan')),('elapsed_inf',['elapsed_seconds'],float('inf')),('elapsed_negative',['elapsed_seconds'],-1),('elapsed_over',['elapsed_seconds'],30.001),('baseline_foreign',['baseline_gpu_mib'],101),('samples_two',['gpu_samples'],r['rows'][0]['release_evidence']['gpu_samples'][:2]),('samples_33',['gpu_samples'],[{'monotonic_seconds':i,'gpu_used_mib':100} for i in range(33)]),('cadence_equal',['gpu_samples',1,'monotonic_seconds'],0),('cadence_gap',['gpu_samples',1,'monotonic_seconds'],1.6),('sample_time_bool',['gpu_samples',0,'monotonic_seconds'],False),('sample_time_nan',['gpu_samples',0,'monotonic_seconds'],float('nan')),('sample_used_bool',['gpu_samples',0,'gpu_used_mib'],True),('sample_used_negative',['gpu_samples',0,'gpu_used_mib'],-1),('stability_over',['gpu_samples',2,'gpu_used_mib'],1125)]
    cases.extend(('release.'+name,'row',['release_evidence']+path,val) for name,path,val in release_cases)
    for status in ['PASS','FAIL']:
        for name,owner,path,value in cases:
            doc=copy.deepcopy(r);row=doc['rows'][0]
            if status=='FAIL':row.update(execution_status='FAIL',error_code='PUBLIC_EXECUTION_NOT_SUCCESSFUL')
            node=doc if owner=='receipt' else row
            for key in path[:-1]:node=node[key]
            if value is missing:node.pop(path[-1],None)
            else:node[path[-1]]=copy.deepcopy(value)
            record('qs.'+status+'.'+name,expected='unknown/unresolved; never aggregate pass',actual=outcome(lambda:summary(doc)))
    # Thresholds preserved; complete semantic/technical failures need not all succeed.
    doc=copy.deepcopy(r);doc['rows'][0].update(execution_status='FAIL',error_code='PUBLIC_EXECUTION_NOT_SUCCESSFUL');ss=copy.deepcopy(scores);ss[0]['critical_hallucinations']=3
    record('known_failure_critical3',actual=summary(doc,ss))
    doc=copy.deepcopy(r);ss=copy.deepcopy(scores)
    for i in [0,1,10]:doc['rows'][i].update(execution_status='FAIL',error_code='PUBLIC_EXECUTION_NOT_SUCCESSFUL')
    record('thresholds_8_images_5_videos_known_failures',actual=summary(doc,ss))
    # Raw hash/bytes through public scorer.
    for field,value in [('raw_sha256','0'*64),('raw_bytes',True),('raw_bytes',r['rows'][0]['raw_bytes']+1)]:
        doc=copy.deepcopy(r);doc['rows'][0][field]=value
        record('raw_'+field+'_'+str(value),actual=outcome(lambda:summary(doc)))
    # Canonical evidence is removed/corrupted/substituted while staged bytes/booleans stay favorable.
    canonical=p.directory/q.CANONICAL_RECEIPT_NAME;raw=canonical.read_bytes()
    for name in ['missing_canonical_retained_stage','corrupt_canonical','foreign_canonical']:
        canonical.unlink()
        if name=='corrupt_canonical':canonical.write_bytes(b'{')
        elif name=='foreign_canonical':
            foreign=copy.deepcopy(r);foreign['run_id']='foreign-run';canonical.write_text(q.canonical_json(foreign))
        record(name,canonical_loader=outcome(lambda:q.load_canonical_receipt(p.directory).get('run_id')),public_scorer=outcome(lambda:summary(r)),staging_exists=(p.directory/q.STAGED_RECEIPT_NAME).exists())
        if canonical.exists():canonical.unlink()
        canonical.write_bytes(raw)
    # Both validators must actually run on QD and QS, trace without replacing their semantics.
    calls={'source':0,'release':0};osource=q.validate_source_evidence;orelease=q.validate_release_evidence
    def source(*a,**kw):calls['source']+=1;return osource(*a,**kw)
    def release(*a,**kw):calls['release']+=1;return orelease(*a,**kw)
    q.validate_source_evidence=source;q.validate_release_evidence=release
    try:
        local,driver,_=prepare('validator-trace');rr=local.run();qd=dict(calls);q.recompute_scores(rr,local.directory,t._scores(rr,rr['projection_sha256']),independence=t._independence());qs_calls={k:calls[k]-qd[k] for k in calls}
        record('shared_validator_calls',qd=qd,qs=qs_calls)
    finally:q.validate_source_evidence=osource;q.validate_release_evidence=orelease
    # Actual exclusive staging FD failures, retained nonauthority and no overwrite.
    for failure in ['write','flush','fsync','close']:
        local,driver,_=prepare('staging-'+failure);op=q.os.open;of=q.os.fdopen;ofs=q.os.fsync;fds=[];events=[]
        def opening(path,flags,*a,**kw):
            fd=op(path,flags,*a,**kw)
            if str(path)==q.STAGED_RECEIPT_NAME:fds.append(fd);events.append({'event':'open','exclusive':bool(flags&os.O_EXCL),'dir_fd':kw.get('dir_fd')})
            return fd
        class Stream:
            def __init__(self,fd):self.s=of(fd,'wb')
            def write(self,b):
                events.append({'event':'write','bytes':len(b)})
                if failure=='write':self.s.write(b[:17]);self.s.flush();raise OSError('independent staged partial write')
                return self.s.write(b)
            def flush(self):
                events.append({'event':'flush'})
                if failure=='flush':raise OSError('independent staged flush')
                return self.s.flush()
            def fileno(self):return self.s.fileno()
            def __enter__(self):return self
            def __exit__(self,*a):
                self.s.close();events.append({'event':'close'})
                if failure=='close':raise OSError('independent staged close')
        def fdopen(fd,*a,**kw):return Stream(fd) if fd in fds else of(fd,*a,**kw)
        def fsync(fd):
            if fd in fds:
                events.append({'event':'fsync'})
                if failure=='fsync':raise OSError('independent staged fsync')
            return ofs(fd)
        q.os.open=opening;q.os.fdopen=fdopen;q.os.fsync=fsync
        try:rr=local.run()
        finally:q.os.open=op;q.os.fdopen=of;q.os.fsync=ofs
        stage=local.directory/q.STAGED_RECEIPT_NAME;before=stage.read_bytes()
        local._open_owned_directories(allow_existing=True)
        try:again=local._write_receipt({'synthetic':True})
        finally:local._close_owned_directories()
        record('actual_run_staging_'+failure,events=events,canonical_exists=(local.directory/q.CANONICAL_RECEIPT_NAME).exists(),staged_bytes=len(before),retained_unchanged=stage.read_bytes()==before,replay_persisted=again,returned={k:rr.get(k) for k in ['decision','receipt_persisted','storage_unproven','terminal_status']},loader=outcome(lambda:q.load_canonical_receipt(local.directory)),handles_closed=local._owned_root is None)
    # Real exact/one-over caps, never monkeypatch cap constants.
    def pad(local,doc,target):
        doc['padding']=''
        for _ in range(12):
            raw,_=local._serialized_receipt(doc);delta=target-len(raw)
            if not delta:return raw
            count=len(doc['padding'])+delta
            if count<0:raise AssertionError('target too small')
            doc['padding']='x'*count
        raise AssertionError('padding did not converge')
    for bound in ['artifact','total','files']:
        for over in [0,1]:
            local,driver,_=prepare('realcap-'+bound+str(over));local._open_owned_directories()
            try:
                doc=q.receipt_document({'synthetic':True})
                if bound=='artifact':pad(local,doc,q.MAX_ARTIFACT_BYTES+over)
                elif bound=='files':
                    for i in range(q.MAX_ARTIFACT_FILES-2+over):local._artifact('fill-%03d'%i,b'')
                else:
                    # Choose >=small receipt, exact total includes two links; one extra byte in filler.
                    target=4096
                    remaining=q.MAX_TOTAL_ARTIFACT_BYTES-2*target+over
                    for i in range(16):
                        n=min(remaining,q.MAX_ARTIFACT_BYTES);local._artifact('fill-%02d'%i,b'x'*n);remaining-=n
                    assert remaining==0
                    pad(local,doc,target)
                ok=local._write_receipt(doc);files=[x for x in local.directory.rglob('*') if x.is_file()]
                record('realcap_'+bound+('_over' if over else '_exact'),persisted=ok,expected_persisted=not bool(over),error=doc.get('receipt_persistence_error'),disk_files=len(files),disk_bytes=sum(x.stat().st_size for x in files),reported_files=doc.get('artifact_files_including_receipt'),reported_bytes=doc.get('artifact_bytes_including_receipt'),caps=[q.MAX_ARTIFACT_BYTES,q.MAX_TOTAL_ARTIFACT_BYTES,q.MAX_ARTIFACT_FILES])
            finally:local._close_owned_directories();shutil.rmtree(local.root)
    # Later callback diminution, identity corruption, and full typed proof via public run.
    for name in ['later_capacity_zero','later_expiry','first_wrong_run','first_wrong_candidate','first_wrong_auth','first_interval_bool','first_capacity_bool']:
        local,driver,_=prepare(name);events=[]
        def authorize(action,subject):
            if action!='quality_public_submit':return
            if name.startswith('later') and driver.submissions!=1:return
            if events:return
            events.append(subject)
            if name=='later_capacity_zero':local.parent_budget['action_capacity']=0
            elif name=='later_expiry':local.parent_budget['expires_monotonic']=local.clock.now
            elif name=='first_wrong_run':local.parent_budget['run_id']='foreign'
            elif name=='first_wrong_candidate':local.parent_budget['candidate_sha']='c'*40
            elif name=='first_wrong_auth':local.parent_budget['authorization_sha256']='c'*64
            elif name=='first_interval_bool':local.parent_budget['issued_monotonic']=False
            else:local.parent_budget['action_capacity']=True
        local.authorize=authorize;rr=local.run();record(name,actual=brief(rr,driver),events=events)
    # Finite clock callback crosses phase deadline on the second read inside the final guard.
    local,driver,_=prepare('second-clock-read');local.parent_budget['expires_monotonic']=20000.0;clock=local.clock
    def crossing_clock():
        frame=inspect.currentframe().f_back
        if frame and frame.f_code.co_name=='_now':
            caller=frame.f_back
            if caller and caller.f_code.co_name=='_parent_proof_is_fresh' and caller.f_back and caller.f_back.f_code.co_name=='_send_admission_guard':clock.now=10801.0
        return clock.now
    local.clock=crossing_clock;rr=local.run();record('final_guard_second_clock_crosses_phase_deadline',actual=brief(rr,driver),clock_now=clock.now)
    # A supported driver's dynamic budget accessor executes AFTER final validation.
    for name in ['driver_accessor_capacity_zero','driver_accessor_phase_expired']:
        local,driver,_=prepare(name);local.parent_budget['expires_monotonic']=20000.0;trigger=[];limit=driver.max_public_submissions
        class ObservedDriver(type(driver)):
            @property
            def max_public_submissions(self):
                if not trigger:
                    trigger.append({'before':local.clock.now,'capacity_before':local.parent_budget['action_capacity']})
                    if name=='driver_accessor_capacity_zero':local.parent_budget['action_capacity']=0
                    else:local.clock.now=10801.0
                return limit
        driver.__class__=ObservedDriver
        rr=local.run();record(name,actual=brief(rr,driver),trigger=trigger,current_capacity=local.parent_budget['action_capacity'])
finally:
    shutil.rmtree(ROOT)
(OUT/'focused-observations.json').write_text(json.dumps({'results':RESULTS,'count':len(RESULTS),'owned_root':str(ROOT),'removed':not ROOT.exists(),'classification':'bounded observations, not additional product passing tests'},indent=2)+'\n')
print(json.dumps({'count':len(RESULTS),'removed':not ROOT.exists(),'results':RESULTS},indent=2))
