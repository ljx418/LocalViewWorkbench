import sys,os,json,hashlib,threading,time,errno,runpy
from pathlib import Path
D=Path(__file__).parent
P=json.loads((D/'plan.json').read_text())
for path,digest in {**P['sourcepins'],**P['toolpins'],**P['dependency_pins']}.items():
 if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise RuntimeError('PIN_DRIFT:'+path)
for item in P['stdlib_pins'].values():
 if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('STDLIB_PIN_DRIFT:'+item['path'])
if 'ctypes' in sys.modules:raise RuntimeError('PRE_GUARD_CTYPES')
control=sys.modules['lvw_root_preload_control'];control.begin()
try:import ctypes
finally:control.finish()
sys.path.append(P['dependency_root']);sys.path.append(P['cwd'])
def inventory():
 rows={};filtered=[];unknown=[]
 for name in os.listdir('/proc/self/fd'):
  try:
   n=int(name);s=os.fstat(n);rows[n]=[s.st_dev,s.st_ino,s.st_mode]
  except OSError as e:
   if e.errno==errno.EBADF:filtered.append(name)
   else:unknown.append([name,repr(e)])
 return dict(rows=rows,filtered=filtered,unknown=unknown)
before=inventory();tb=[t.name for t in threading.enumerate()];start=time.monotonic();ns=runpy.run_path(str(D/'probes.py'))
selection=[n for n,f in ns['CASES']]
if selection!=P['selection']:raise RuntimeError('SELECTION_DRIFT')
results=ns['run']();after=inventory();ta=[t.name for t in threading.enumerate()];clean=before['rows']==after['rows'] and not before['unknown'] and not after['unknown'] and tb==ta==['MainThread'];r=dict(selection=selection,results=results,oracle_pass=sum(x['oracle_pass'] for x in results),oracle_fail=sum(not x['oracle_pass'] for x in results),fd_before=before,fd_after=after,threads_before=tb,threads_after=ta,cleanup_proven_for_batch=clean,preload_events=control.events,duration_seconds=time.monotonic()-start,stage_pass_claim=False,native_proven=False)
(D/'receipt.json').write_text(json.dumps(r,indent=2,default=repr)+'\n');print(json.dumps({k:r[k] for k in ['oracle_pass','oracle_fail','cleanup_proven_for_batch','duration_seconds']}));raise SystemExit(0 if clean and all(x['oracle_pass'] for x in results) else 1)
