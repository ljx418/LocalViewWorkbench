"""Independent controller-bound synthetic checks; assertions reproduce defects, not acceptance."""
import contextlib,io,json,os,time,threading,hashlib
from pathlib import Path
import pytest
from tools import test_v0_s3_production_composition as data
from tools import v0_s3_production_controller as c
from tools import v0_s3_quality_worker as w
D=Path(__file__).parent
CAND='7c27a11111ede5bb2eb449211f5450270d884ee3'

def sha(b):return hashlib.sha256(b).hexdigest()
def save(name,obj):(D/(name+'.json')).write_text(json.dumps(obj,indent=2,default=str))
@pytest.fixture
def build(tmp_path,monkeypatch):
    monkeypatch.setattr(data,'CANDIDATE_SHA',CAND)
    monkeypatch.setattr(data._helpers(),'CANDIDATE_SHA',CAND)
    return lambda **kw:data._build_composition(tmp_path,**kw)
def run(comp,monkeypatch,*,fault='none',transition=None,factory=None,sealed=True,clock=None):
    seam=c.OfflineCompositionSeam(driver_factory=factory or (lambda ctx:data._helpers().SyntheticDriver(ctx.root,comp['driver_failure'])),context_sha256=comp['worker_context_sha256'] if sealed else None,fault=fault,clock=clock)
    seam.on_transition=transition
    original=c.ProductionController; held=[]
    class Injected(original):
        def __init__(self,context):
            super().__init__(context,seam=seam);held.append(self)
    output=io.StringIO();err=io.StringIO()
    with monkeypatch.context() as m:
        m.setattr(c,'ProductionController',Injected)
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(err):
            code=c.main(['--context',str(comp['controller_context_path']),'--context-sha256',sha(comp['controller_context_path'].read_bytes())])
    receipt=json.loads(output.getvalue()) if output.getvalue().strip() else None
    return code,receipt,held[0] if held else None,seam,err.getvalue()
def retain(name,result):
    code,r,obj,seam,err=result
    save(name,{'exit':code,'receipt':r,'stderr':err,'seam_spawns':seam.spawns,'thread_alive':getattr(seam,'_worker',None)._thread.is_alive() if hasattr(seam,'_worker') else False})
    return r

def test_positive_full_main_chain(build,monkeypatch):
    comp=build();res=run(comp,monkeypatch);r=retain('positive-full-chain',res)
    assert res[0]==0 and r['state']=='SUMMARY_PERSISTED'
    canonical=json.loads((comp['root']/'temp/s3-quality/qd-receipt.json').read_text())
    plan=json.loads((comp['root']/'temp/s3-quality/qd-source-plan.json').read_text())
    assert canonical['candidate_sha']==CAND and canonical['run_id']==r['run_id']
    assert canonical['projection_sha256']==sha(comp['projection'])
    assert len(canonical['rows'])==16 and r['supervision']['message_count']==66
    assert r['manifest']['reverification']['verified'] is True
    assert r['summary']['pass_count']==0 and r['summary']['key_count']==12
    assert r['fd_cleanup']['fd_leaked']==[] and r['fd_cleanup']['worker_thread_finished']
    # Record actual cross-owner ordinal/source binding without writing a canonical.
    save('positive-chain-oracle',{'source_plan':plan,'expected_projection_rows':comp['rows'],'canonical_row_bindings':[{k:row.get(k) for k in ['ordinal','asset_id','source_sha256','source_bytes','input_reference','execution_status']} for row in canonical['rows']], 'controller_context_actual_hash':sha(comp['controller_context_path'].read_bytes()),'manifest_hash':sha(c.canonical_json(r['manifest']).encode()),'thread_only':True})

@pytest.mark.parametrize('failure',['release-unproven','residue','provider-refusal'])
def test_real_failed_rows_not_hidden_by_outer_blocked(build,monkeypatch,failure):
    comp=build(driver_failure=failure);res=run(comp,monkeypatch);r=retain('failure-'+failure,res)
    assert r['state']=='SUMMARY_PERSISTED'
    can=json.loads((comp['root']/'temp/s3-quality/qd-receipt.json').read_text())
    assert can['test_counts']['FAIL']>0
    statuses={k:v['status'] for k,v in r['receipts'].items()}
    save('false-pass-'+failure,{'canonical_counts':can['test_counts'],'receipt_statuses':statuses,'summary_pass':r['summary']['pass_count'],'reproduction_is_acceptance':False})
    assert statuses['resource_budget']=='PASS' and statuses['no_overwrite']=='PASS'
    assert r['summary']['pass_count']==0

def test_manifest_rewrite_is_consumed_without_reverification(build,monkeypatch):
    comp=build();changed={}
    def fault(state,obj):
        if state=='ORIGINALS_VERIFIED':
            raw=obj.manifest['originals']['raw'][0];p=comp['root']/raw['reference'];p.write_bytes(b'independent-after-manifest');changed.update(sealed=raw['sha256'],actual=sha(p.read_bytes()),reference=raw['reference'])
    res=run(comp,monkeypatch,transition=fault);r=retain('manifest-after-verify-tamper',res)
    assert changed['sealed']!=changed['actual'] and r['state']=='SUMMARY_PERSISTED'
    assert r['receipts']['file_safety']['status']=='PASS'
    save('manifest-after-verify-oracle',changed)

def test_canonical_rewrite_creates_contradictory_provenance(build,monkeypatch):
    comp=build()
    def fault(state,obj):
        if state=='ORIGINALS_VERIFIED':
            p=comp['root']/'temp/s3-quality/qd-receipt.json';p.write_bytes(p.read_bytes()+b' ')
    res=run(comp,monkeypatch,transition=fault);r=retain('canonical-after-manifest-tamper',res)
    assert r['state']=='SUMMARY_PERSISTED'
    assert r['summary']['provenance']['canonical']['sha256']!=r['manifest']['originals']['canonical'][0]['sha256']
    assert r['summary']['provenance']['controller_context']['sha256']!=sha(comp['controller_context_path'].read_bytes())

def test_summary_write_follows_outside_symlink(build,monkeypatch,tmp_path):
    comp=build();outside=tmp_path/'owned-outside';outside.mkdir()
    def fault(state,obj):
        if state=='RECEIPTS_BOUND':(comp['root']/'temp/s3-production-controller').symlink_to(outside,target_is_directory=True)
    res=run(comp,monkeypatch,transition=fault);r=retain('summary-outside-symlink',res)
    assert r['state']=='SUMMARY_PERSISTED' and list(outside.glob('summary-*.json'))
    save('summary-outside-oracle',{'claimed_root':str(comp['root']),'actual_destination':str(Path(r['summary_path']).resolve()),'outside_root':not Path(r['summary_path']).resolve().is_relative_to(comp['root'])})

def test_root_replaced_after_manifest_is_accepted(build,monkeypatch):
    comp=build();root=comp['root'];moved=root.with_name('retained-original-root')
    def fault(state,obj):
        if state=='ORIGINALS_VERIFIED':root.rename(moved);root.symlink_to(moved,target_is_directory=True)
    res=run(comp,monkeypatch,transition=fault);r=retain('root-after-manifest-symlink',res)
    assert r['state']=='SUMMARY_PERSISTED' and root.is_symlink()

def test_missing_canonical_after_manifest_escapes_cleanup(build,monkeypatch):
    comp=build();before=set(os.listdir('/proc/self/fd'))
    def fault(state,obj):
        if state=='ORIGINALS_VERIFIED':(comp['root']/'temp/s3-quality/qd-receipt.json').unlink()
    res=run(comp,monkeypatch,transition=fault);code,r,obj,seam,err=res
    leaked=set(os.listdir('/proc/self/fd'))-before
    save('unhandled-read-error',{'exit':code,'receipt':r,'stderr':err,'fd_leaked_before_independent_cleanup':sorted(leaked),'spawns':seam.spawns,'owner_state':obj.state})
    seam.close() # independent cleanup of this controlled probe, not a claim the controller cleaned it.
    assert code==c.EXIT_INTERNAL and r is None and leaked

def test_preexisting_summary_does_not_prevent_repeat_spawn(build,monkeypatch):
    comp=build();dest=comp['root']/'temp/s3-production-controller';dest.mkdir();p=dest/('summary-'+data.RUN_ID+'.json');p.write_bytes(b'prior-summary')
    res=run(comp,monkeypatch);r=retain('summary-preexisting-spawn',res)
    assert res[3].spawns==1 and r['state']=='UNKNOWN_RETAINED' and p.read_bytes()==b'prior-summary'

def test_write_failure_retains_partial_no_retry(build,monkeypatch):
    comp=build();original=c.os.fsync
    def fault(state,obj):
        if state=='RECEIPTS_BOUND':monkeypatch.setattr(c.os,'fsync',lambda fd:(_ for _ in ()).throw(OSError('independent-fsync-fault')))
    res=run(comp,monkeypatch,transition=fault);r=retain('summary-write-failure',res)
    monkeypatch.setattr(c.os,'fsync',original)
    assert r['state']=='UNKNOWN_RETAINED' and r['reservation_retained'] and res[3].spawns==1
    assert list((comp['root']/'temp/s3-production-controller').glob('summary-*.json'))

def test_worker_second_load_does_not_enforce_preflight_seal(build,monkeypatch):
    comp=build();original=comp['worker_context_path'].read_bytes();seen=[]
    def factory(ctx):
        # First load was sealed; mutate exactly between that load and formal worker.main's second load.
        doc=json.loads(original);doc['driver_arguments']['powershell']='C:/independent-after-preflight.exe';data._write_json(comp['worker_context_path'],doc)
        driver=data._helpers().SyntheticDriver(ctx.root);seen.append(driver);return driver
    res=run(comp,monkeypatch,factory=factory);r=retain('worker-second-load-context-drift',res)
    assert original!=comp['worker_context_path'].read_bytes() and r['state']=='SUMMARY_PERSISTED'
    assert r['receipts']['stage_binding']['status']=='PASS'
    assert seen[0].submissions==16

def test_native_references_are_json_identity_rejected_not_verified(build,monkeypatch):
    comp=build();context=c.ControllerContext.load(comp['controller_context_path']);doc=json.loads((comp['root']/'contexts/admission.json').read_text())
    class BudgetSpy:
        def __init__(self,**kw):self.kw=kw
        def sealed(self):return ({},'spy-no-ledger')
    monkeypatch.setattr(c,'S3BudgetBindingProvider',BudgetSpy)
    proof_fields={'native_custody':['descendant_handles_closed','native_services_stopped'],'gpu_release':['gpu_released'],'install':['installed'],'rollback':['rollback_verified'],'grant':['grant_active']}
    for name in c.ADMISSION_REFERENCE_KEYS:
        p=comp['root']/'contexts'/('own-'+name+'.json');proof={'run_id':context.run_id,'candidate_sha':CAND,'status':'PROVEN'}
        for key in proof_fields.get(name,[]):proof[key]=True
        if name=='grant':proof.update(expires_at=0,scope='outside-authorized-scope',budget=0,authorization_sha256='e'*64)
        if name=='tool_closure':proof['files']=[{'path':str(comp['controller_context_path']),'sha256':sha(comp['controller_context_path'].read_bytes())}]
        data._write_json(p,proof);doc['admission_references'][name]={'path':str(p),'sha256':sha(p.read_bytes())}
    report=c.verify_native_admission(context,doc)
    reasons=[];normal=json.loads(json.dumps({'run_id':context.run_id,'candidate_sha':CAND,'status':'PROVEN','grant_active':True}))
    json_ok=c._bound_receipt(normal,context,label='grant',reasons=reasons,required={'status':'PROVEN','grant_active':True})
    direct_reasons=[];direct={'run_id':context.run_id,'candidate_sha':CAND,'status':'PROVEN','grant_active':True,'expires_at':0,'budget':0,'authorization_sha256':'e'*64}
    direct_ok=c._bound_receipt(direct,context,label='grant',reasons=direct_reasons,required={'status':'PROVEN','grant_active':True})
    save('native-json-proof-comparison',{'report':report,'normal_json_ok':json_ok,'normal_json_reasons':reasons,'identical_python_literal_ok':direct_ok,'budget_spy_only':True,'no_native_spawn':True,'no_ledger_read':True,'direct_invalid_grant':direct})
    assert not report['accepted'] and all(name+':PROOF_MISSING:status' in report['reasons'] for name in proof_fields)
    assert not json_ok and direct_ok

def test_default_worker_main_builds_native_and_error_stream_bug(build,monkeypatch):
    comp=build();calls=[]
    def deny(ctx):calls.append(ctx.run_id);raise w.WorkerError('INDEPENDENT_NATIVE_CONSTRUCTION_SPY')
    monkeypatch.setattr(w,'build_native_driver',deny)
    err=io.StringIO();assert w.main(['--context',str(comp['worker_context_path'])],stream=io.BytesIO(),error_stream=err)==2
    assert calls==[data.RUN_ID]
    with pytest.raises(TypeError):w.main(['--context',str(comp['worker_context_path'])],stream=io.BytesIO(),error_stream=io.BytesIO())
    save('worker-main-default-and-stream',{'native_factory_calls':len(calls),'text_stream_error':err.getvalue(),'binary_stream_error_type':'TypeError','no_native_launch':True})

def test_controller_read_bound_is_checked_after_whole_read(build,monkeypatch):
    comp=build();path=comp['root']/'contexts/oversized.json';path.write_bytes(b' '* (8*1024*1024+1));calls=[];original=Path.read_bytes
    def spy(p):
        raw=original(p)
        if p==path:calls.append(len(raw))
        return raw
    monkeypatch.setattr(Path,'read_bytes',spy)
    with pytest.raises(c.ControllerError):c.ControllerContext.load(path)
    save('context-read-bound',{'whole_file_read_sizes':calls,'limit':8*1024*1024,'bounded_before_read':False})
    assert calls==[8*1024*1024+1]

def test_blocked_thread_is_retained_and_can_write_after_return(build,monkeypatch):
    comp=build();entered=threading.Event();release=threading.Event();baseline=time.monotonic();drivers=[]
    class Blocking(data._helpers().SyntheticDriver):
        def submit(self,graph):
            entered.set();release.wait(55)
            return super().submit(graph)
    def clock():return baseline+22000 if entered.is_set() else time.monotonic()
    seam=None
    def factory(ctx):
        driver=Blocking(ctx.root);drivers.append(driver);return driver
    try:
        started=time.monotonic();res=run(comp,monkeypatch,factory=factory,clock=clock);elapsed=time.monotonic()-started
        code,r,obj,seam,err=res
        before={str(p.relative_to(comp['root'])):sha(p.read_bytes()) for p in (comp['root']/'temp/s3-quality').rglob('*') if p.is_file()}
        alive=seam._worker._thread.is_alive();daemon=seam._worker._thread.daemon;calls_at_return=drivers[0].counter[0]
        assert code==4 and r['reservation_retained'] and alive and not r['fd_cleanup']['worker_thread_finished']
        release.set();seam._worker._thread.join(5)
        after={str(p.relative_to(comp['root'])):sha(p.read_bytes()) for p in (comp['root']/'temp/s3-quality').rglob('*') if p.is_file()}
        save('blocked-thread-late-write',{'receipt':r,'elapsed':elapsed,'daemon':daemon,'alive_at_return':alive,'alive_after_independent_release_join':seam._worker._thread.is_alive(),'provider_calls_at_return':calls_at_return,'provider_calls_after_independent_release':drivers[0].counter[0],'files_changed_after_return':sorted(k for k in after if before.get(k)!=after[k]),'before':before,'after':after,'independent_event_release_is_not_owner_kill':True})
        assert daemon and drivers[0].counter[0]>calls_at_return and not seam._worker._thread.is_alive()
    finally:
        release.set()
        if seam is not None:seam._worker._thread.join(5);seam.close()

def test_last_row_release_failure_still_claims_output_contract_pass(build,monkeypatch):
    comp=build()
    class LastFailure(data._helpers().SyntheticDriver):
        def release_preload(self,binding,worker):
            self.failure='release-unproven' if self.submissions==16 else None
            return super().release_preload(binding,worker)
    res=run(comp,monkeypatch,factory=lambda ctx:LastFailure(ctx.root));r=retain('last-row-release-output-pass',res)
    can=json.loads((comp['root']/'temp/s3-quality/qd-receipt.json').read_text())
    save('last-row-release-oracle',{'canonical_counts':can['test_counts'],'final_row':can['rows'][-1],'receipt_statuses':{k:v['status'] for k,v in r['receipts'].items()},'test_exit_zero_is_defect_reproduction_only':True})
    assert can['test_counts']['FAIL']==1 and can['test_counts']['PASS']==15
    assert r['receipts']['output_contract']['status']=='PASS' and r['receipts']['resource_budget']['status']=='PASS'
