from probes import *
# Only new boundary probes in this file; imported pytest functions are deselected by the runner.
@pytest.mark.parametrize('kind',['exact','changed'])
def test_read_oracle_actual(tmp_path,monkeypatch,kind):
 p=tmp_path/'regular';p.write_bytes(b'x'*16);real=os.read;returned=[];requests=[];changed=[]
 def read(fd,n):
  requests.append(n);b=real(fd,n);returned.append(len(b))
  if kind=='changed' and b and not changed:p.write_bytes(b'y'*16);changed.append(1)
  return b
 monkeypatch.setattr(safe.os,'read',read);error=None;value=None
 try:value=safe.read_bounded_regular(p,16)
 except safe.ControllerIOError as e:error=e.code
 save('read-oracle-'+kind,{'actual_bytes':sum(returned),'requests':requests,'returned':returned,'error':error,'oracle_correction':'Read syscalls requesting an EOF byte do not mean that byte was returned; the original sum(requests) assertion was too strong.'})
 assert sum(returned)<=17
 if kind=='exact':assert value==b'x'*16
 else:assert error=='FILE_CHANGED_DURING_READ'

@pytest.mark.parametrize('reference',['projection','source_identity','parent_budget','binding','dependency_manifest'])
def test_actual_worker_reference_ancestor(build,monkeypatch,tmp_path,reference):
 comp=build();ctx=w.WorkerContext.load(comp['worker_context_path'],expected_sha256=comp['worker_context_sha256']);doc=ctx.document
 key={'projection':'projection_path','source_identity':'source_identity_path','parent_budget':'parent_budget_path','binding':'binding_path','dependency_manifest':'dependency_manifest_path'}[reference]
 p=Path(doc[key]);parent=p.parent;outside=tmp_path/('owned-outside-'+reference);parent.rename(outside);parent.symlink_to(outside,target_is_directory=True)
 actual=getattr(ctx,reference)();save('M04-actual-worker-'+reference,{'read_accepted':True,'path':str(p),'resolved':str(p.resolve()),'outside_root':not p.resolve().is_relative_to(comp['root']),'value_type':type(actual).__name__,'expected':'Reject ancestor redirection for referenced files; final component nofollow is insufficient.'})
 assert actual is not None and not p.resolve().is_relative_to(comp['root'])

@pytest.mark.parametrize('target',['root','temp','controller'])
def test_write_object_boundaries(build,monkeypatch,tmp_path,target):
 comp=build();changed=[]
 def fault(state,obj):
  if state!='RECEIPTS_BOUND':return
  p=comp['root'] if target=='root' else comp['root']/'temp' if target=='temp' else comp['root']/'temp/s3-production-controller'
  held=p.with_name(p.name+'-retained');p.rename(held);p.mkdir();changed.append({'path':str(p),'old':str(held),'old_inode':held.stat().st_ino,'new_inode':p.stat().st_ino})
 v,seam,obj=run(comp,monkeypatch,transition=fault);new=(comp['root']/'temp/s3-production-controller');newfiles=[p.name for p in new.glob('*.json')];save('M06-object-'+target,{**v,'changes':changed,'new_files':newfiles})
 assert changed and any(n.startswith('receipt-') for n in newfiles)
 if target=='controller':assert v['receipt']['summary_persisted']
 else:assert not v['receipt']['summary_persisted']

def test_write_ancestor_link(build,monkeypatch,tmp_path):
 comp=build(name='envelope/run');outside=tmp_path/'owned-external';outside.mkdir();(outside/'run').mkdir()
 def fault(state,obj):
  if state!='RECEIPTS_BOUND':return
  parent=comp['root'].parent;parent.rename(tmp_path/'retained-envelope');parent.symlink_to(outside,target_is_directory=True)
 v,seam,obj=run(comp,monkeypatch,transition=fault);external=[str(p.relative_to(outside)) for p in outside.rglob('*')];save('M06-root-ancestor-link',{**v,'external_files':external})
 assert any(x.endswith('receipt-'+data.RUN_ID+'.json') for x in external)

def test_m08_deleted_canonical(build,monkeypatch):
 comp=build();before=set(os.listdir('/proc/self/fd'))
 def fault(state,obj):
  if state=='ORIGINALS_VERIFIED':(comp['root']/'temp/s3-quality/qd-receipt.json').unlink()
 v,seam,obj=run(comp,monkeypatch,transition=fault);save('M08-deleted-canonical',v);assert v['receipt']['state']=='UNKNOWN_RETAINED' and v['receipt']['receipt_persisted'] and set(os.listdir('/proc/self/fd'))==before

def test_m08_persistence_unexpected(build,monkeypatch):
 comp=build();before=set(os.listdir('/proc/self/fd'));original=safe.os.fsync
 def fault(state,obj):
  if state=='RECEIPTS_BOUND':monkeypatch.setattr(safe.os,'fsync',lambda fd:(_ for _ in ()).throw(RuntimeError('independent-unexpected-write')))
 try:v,seam,obj=run(comp,monkeypatch,transition=fault)
 finally:monkeypatch.setattr(safe.os,'fsync',original)
 save('M08-unexpected-persistence',{**v,'fd_delta':sorted(set(os.listdir('/proc/self/fd'))-before),'object_state':obj.state,'receipt_persistence_error':obj.receipt_persistence_error})
 assert v['receipt'] is None and v['exit']==c.EXIT_INTERNAL and set(os.listdir('/proc/self/fd'))==before


def test_m07_complete_obligations(build,monkeypatch):
 comp=build();v,seam,obj=run(comp,monkeypatch);r=v['receipt'];can=obj.canonical
 save('M07-obligation-oracle',{'receipts':{k:r['receipts'][k] for k in ('output_contract','resource_budget','no_overwrite')},'canonical_has_native_resource_limits':any(k in can for k in ('gpu_peak_mib','minimum_ram_mib','peak_memory','vram_peak')),'canonical_provider_counts':{k:can.get(k) for k in ('provider_calls_reserved','provider_calls_observed','parent_budget_capacity')},'canonical_bounds':can.get('bounds'),'real_execution_performed':can['real_execution_performed'],'scope':'Synthetic provider accounting and artifact ownership do not cover the fixed A03/A05/A09 product obligations.'})
 assert r['receipts']['resource_budget']['status']=='PASS' and can['real_execution_performed'] is False
