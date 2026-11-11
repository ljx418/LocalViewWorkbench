"""Read committed evidence only; no imported project modules or host/runtime queries."""
import base64, hashlib, json, subprocess, uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
E=ROOT/'reports/v0-s3/product-gate0/execution-p2-binding-correction-03'
R=E/'runtime-evidence'
C='975747218d0d002521d98e56c46b9da2c52ee612'
TIP='b7e36beefe3cbe4c7b32f66a99bd4ddfec506fb8'
REVIEWED='da6e7b5ed351baca3b74f003cfcf3622c4b382d6'
def sha(b): return hashlib.sha256(b).hexdigest()
def read(p):
    assert p.is_relative_to(ROOT)
    for q in [p,*p.parents]:
        assert not q.is_symlink(),str(q)
        if q==ROOT:break
    return p.read_bytes()
def obj(p): return json.loads(read(p))
def blob(rev,p): return subprocess.check_output(['git','show',rev+':LVW_Prompt_Service_MasterPack_v2.0.0/'+p],cwd=ROOT)
def encoded(d): return (json.dumps(d,indent=2,ensure_ascii=False,allow_nan=False)+'\n').encode()
pre=obj(R/'preflight.json'); idx=obj(R/'cross-os-lifecycle.json'); child=obj(E/'sealed-inputs/runtime-binding-correction-03.child.json'); act=obj(E/'sealed-inputs/p2-binding-correction-03.activation.json')
files=[]
for line in read(E/'SHA256SUMS').decode().splitlines():
    h,p=line.split('  ',1); data=read(ROOT/p); assert sha(data)==h;files.append({'path':p,'sha256':h,'bytes':len(data)})
sources=[]
for p,h in {**pre['source_hashes'],**act['code_blob_hashes']}.items():
    data=read(ROOT/p); assert sha(data)==h
    assert all(blob(v,p)==data for v in [C,TIP,REVIEWED])
    sources.append({'path':p,'sha256':h,'bytes':len(data),'git_blob':subprocess.check_output(['git','rev-parse',C+':LVW_Prompt_Service_MasterPack_v2.0.0/'+p],cwd=ROOT,text=True).strip()})
for p in (E/'sealed-inputs').iterdir():
    target='reports/v0-s3/product-gate0/'+p.name
    assert read(p)==blob(C,target)==read(ROOT/target)
assert child['status']=='AUTHORIZED' and child['child_id']==idx['child_id']==act['child_id']
assert sha(read(E/'sealed-inputs/p2-binding-correction-03.activation.json'))==child['activation_record_sha256']
assert sha(read(E/'sealed-inputs/runtime-binding-correction-03.child.json'))==idx['child_sha256']==pre['child_sha256']
assert sha(read(ROOT/child['contract']))==child['contract_sha256']==pre['contract_sha256']
assert sha(read(R/'preflight.json'))==idx['preflight_sha256']
assert pre['candidate']==idx['candidate']==C
assert idx['schema']=='lvw.p2b-terminal/3' and idx['status']=='READY_FOR_REVIEW'
assert idx['terminal_index_persisted'] and idx['finalization_proven'] and idx['claim_finalization']=='PROVEN'
assert idx['terminal_errors']==[] and idx['error'] is None
local=obj(R/'consumed.json'); shared=obj(E/'shared-claim.json'); assert local==shared
for x in [local,shared]:
    assert x['schema']=='lvw.p2b-consumption/2' and x['status']=='EXPIRED' and x['result']=='TERMINAL_REFERENCE_NOT_DECISION'
    assert x['terminal_sha256']==sha(read(R/'cross-os-lifecycle.json'))
    assert x['terminal_path']==pre['output_root']+'/cross-os-lifecycle.json'
    assert all(x[k]==idx[k] for k in ['candidate','child_id','child_sha256','preflight_sha256'])
initial={k:v for k,v in shared.items() if k not in ['schema','result','terminal_sha256','terminal_path']};initial['status']='RUNNING'
assert sha(json.dumps(initial).encode())==idx['initial_claim_sha256']
outer={}
for n in ['preflight','actual']:
    assert read(E/'outer-raw'/f'{n}.exit').strip()==b'0'
    assert read(E/'outer-raw'/f'{n}.stderr')==b''
    outer[n]=obj(E/'outer-raw'/f'{n}.stdout')
assert outer['preflight']['sha256']==idx['preflight_sha256']
assert outer['actual']['status']==idx['status'] and outer['actual']['finalization_proven']
refs=idx['artifact_refs']; assert len(refs)==22
art={}; commands=[]; observers=[]
for r in refs:
    p=Path(r['path']); assert not p.is_absolute() and p.parts[0]=='details' and len(p.parts)==2 and '..' not in p.parts
    data=read(R/p);assert len(data)==r['bytes']<=1048576 and sha(data)==r['sha256'];d=json.loads(data);art[r['path']]=d
    if r['kind']=='command':
        streams=[base64.b64decode(d[k],validate=True) for k in ['stdout_base64','stderr_base64']]
        assert [len(x) for x in streams]==d['stream_bytes'] and [sha(x) for x in streams]==d['stream_sha256']
        assert d['raw_complete'] and d['threads_joined'] and all(d['pipe_closed']) and not d['reader_errors'] and d['exit_code']==0
        assert d['elapsed']<30 and d['command'][0]==pre['tools']['windows_python']
        commands.append({'ref':r,'argv':d['command'],'argv_json_sha256':sha(json.dumps(d['command'],ensure_ascii=False).encode()),'elapsed':d['elapsed'],'interop_pid':d['interop_pid'],'interop_birth':d['interop_birth'],'stream_bytes':d['stream_bytes'],'stream_sha256':d['stream_sha256']})
    if r['kind']=='observer':
        times=[s['elapsed'] for s in d['samples']]; assert times==d['sampling_times'] and len(times)==d['sample_count']<=160
        assert all(b>a for a,b in zip(times,times[1:]));gap=max(b-a for a,b in zip(times,times[1:]));assert gap==d['max_interval']<=.25 and d['elapsed']<30
        ids={};absent={};entered=set()
        for s in d['samples']:
            for o in s['owners']:
                rid=o['request_id'];assert str(uuid.UUID(rid))==rid
                identity=[o['pid'],o['birth']['linux_start_ticks']]
                assert rid not in ids or ids[rid]==identity;ids[rid]=identity
                if o['state']=='ENTERED':entered.add(rid)
                absent[rid]=0 if o['same_birth_alive'] else absent.get(rid,0)+1
                if o['same_birth_alive']:assert o['observed_birth']==o['birth']
                else:assert o.get('absence_errno') in (2,3) or o.get('observed_birth')!=o['birth']
        assert ids==d['identities'] and absent==d['absence_counts'] and sorted(entered)==d['entered']
        assert ids and all(n>=2 for n in absent.values()) and d['two_absences'] and d['error'] is None
        observers.append({'ref':r,'sample_count':len(times),'max_interval':gap,'elapsed':d['elapsed'],'started_monotonic':d['started_monotonic'],'identities':ids,'absence_counts':absent,'joined':d['joined']})
assert len(commands)==3 and len(observers)==6
phase_rows=[]
for i,name in enumerate(['normal','bad-receipt','timeout']):
    n=i*7; phase=art[f'details/{n+5:03d}-phase.raw']; verdict=art[f'details/{n+6:03d}-phase.raw']; native=art[f'details/{n+3:03d}-native.raw'];resp=art[f'details/{n+4:03d}-response.raw']
    assert phase['phase']==verdict['phase']==name and not phase['missing'] and verdict['verdict']=='EXPECTED_BOUNDARY'
    assert phase['artifacts']==refs[n+3:n+5] and resp['native_identity']==native and native['os_name']=='nt'
    assert observers[2*i+1]['joined'] and not observers[2*i]['joined']
    assert observers[2*i]['identities']==observers[2*i+1]['identities']
    assert phase['driver_plan']['candidate']==C and phase['driver_plan']['source_hashes']==pre['source_hashes']
    for b in phase['bindings']:
        assert sha(encoded(b['binding']))==b['binding_sha256']
        assert sha(encoded(b['child']))==b['binding']['child_sha256']
        assert sha(encoded(b['execution']))==b['binding']['execution_sha256']
        assert b['binding']['candidate_sha']==C
    assert all(x['model_sends']==0 for x in resp['cases'])
    res=resp['cases'][0]['result']; process=res.get('process',res.get('details'))
    if i==0:
        assert res['status']=='DEBITED' and process['exit_code']==0
        assert resp['cases'][1]['result']['details']['subcode']=='S3_BUDGET_BINDING_OR_BRIDGE_INVALID'
    elif i==1:assert process['exit_code']==0 and process['subcode']=='S3_BRIDGE_RECEIPT_INVALID'
    else:assert process['exit_code']==1 and process['error']=='TIMEOUT'
    assert process['reaped'] and process['readers_joined'] and process['pipe_closed'] and not any(process['thread_alive'])
    phase_rows.append({'phase':name,'native_python':native,'native_wsl_process':process,'debits':verdict['debits'],'verdict':verdict['verdict']})
assert len({next(iter(o['identities'])) for o in observers[1::2]})==3
assert len({tuple(next(iter(o['identities'].values()))) for o in observers[1::2]})==3
assert sum(r['bytes'] for r in refs)==idx['detail_actual_bytes']==126988
assert len(read(R/'cross-os-lifecycle.json'))<=16384
clean=art['details/021-cleanup.raw'];m=clean['metadata']; installed=obj(R/'installed-seal.json')
old=obj(ROOT/'reports/v0-s3/product-gate0/implementation-p2-binding/installed-seal.json')
assert sha(read(ROOT/'reports/v0-s3/product-gate0/implementation-p2-binding/installed-seal.json'))==pre['old_installed_seal_sha256']
for role,s in installed.items():assert s['sha256']==old['tools'][role]['sha256'] and s==clean['installed'][role]
charge=sum(m['role_sizes'][k]*m['read_count_bounds'][k] for k in m['role_sizes'])
assert charge==m['charged_bytes']==idx['counters']['metadata_hash_bytes']==265032184
assert child['limits']['metadata_hash_bytes']-charge==m['remaining_budget']==3403272
assert m['actual_digest_bytes'] is None and m['measurement']=='NOT_MEASURED'
assert idx['counters']['process_starts']==10+sum(art[f'details/{n:03d}-command.raw']['process_start_reservation'] for n in (0,7,14))==26
assert all(idx['counters'][k]<=v for k,v in pre['limits'].items())
assert all(x['state']=='AUDIT_RETAINED' for x in clean['cleanup'])
assert all(not o['same_birth_alive'] for x in clean['cleanup'] for o in x['owners'])
control=json.loads(blob('92239ba210bc466808de2cbf5bbcbdd3fdbf1569','plans/execution-control.json'))
receipt={'scope':'committed-text independent recomputation, not runtime rerun','evidence_tip':TIP,'execution_candidate':C,'reviewed_code':REVIEWED,'source_hashes':sources,'snapshot_files':files,'terminal_sha256':sha(read(R/'cross-os-lifecycle.json')),'terminal_bytes':len(read(R/'cross-os-lifecycle.json')),'initial_claim_reconstruction_sha256':sha(json.dumps(initial).encode()),'artifact_refs':refs,'commands':commands,'observers':observers,'phases':phase_rows,'metadata':m,'counters':idx['counters'],'detail_actual_bytes':126988,'new_actual_runs':0,'new_tests':0,'new_parser':0,'host_runtime_reads':0,'findings':{'fatal':0,'major':0,'minor':1},'minor':['C03-m01: lock acquired/released and wrapper-return monotonic timestamps exist only in transient life; not persisted in the 22 artifacts. Timing/causal lock claim cannot be independently recovered.'],'development_outline':control['development_outline'],'product_gate0':False,'stage_pass':False,'human_signature':False}
(OUT/'receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'verified_snapshot_files':len(files),'refs':len(refs),'commands':len(commands),'observers':len(observers),'detail_actual_bytes':126988,'F':0,'M':0,'m':1}))
