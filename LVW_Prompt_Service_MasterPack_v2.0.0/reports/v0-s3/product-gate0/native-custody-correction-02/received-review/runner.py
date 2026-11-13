import sys,os,json,hashlib,threading,errno,runpy,time
from pathlib import Path
D=Path(__file__).parent
P=json.loads((D/'plan.json').read_text())
for path,digest in {**P['sourcepins'],**P['toolpins'],**P['dependency_pins']}.items():
    if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise RuntimeError('PIN_DRIFT:'+path)
sys.path.append(P['dependency_root']);sys.path.append(P['cwd'])
def inventory():
    rows={};filtered=[];unknown=[]
    for name in os.listdir('/proc/self/fd'):
        if not name.isdigit():continue
        n=int(name)
        try:s=os.fstat(n);rows[n]=[s.st_dev,s.st_ino,s.st_mode]
        except OSError as e:
            if e.errno==errno.EBADF:filtered.append(n)
            else:unknown.append([n,e.errno])
    return {'rows':rows,'filtered_ebadf':filtered,'unknown':unknown}
before=inventory();tb=[t.name for t in threading.enumerate()];results=[];start=time.monotonic()
module=runpy.run_path(str(D/'probes.py'))
for name in P['selection']:
    root=D/'synthetic'/name
    passed,detail=module['run_case'](name,root)
    row={'name':name,'oracle_pass':passed,'detail':detail};results.append(row);print(json.dumps(row),flush=True)
after=inventory();ta=[t.name for t in threading.enumerate()]
clean=before['rows']==after['rows'] and not before['unknown'] and not after['unknown'] and tb==ta==['MainThread']
receipt={'selection':P['selection'],'results':results,'oracle_pass':sum(x['oracle_pass'] for x in results),'oracle_fail':sum(not x['oracle_pass'] for x in results),'fd_before':before,'fd_after':after,'threads_before':tb,'threads_after':ta,'cleanup_proven_for_batch':clean,'wall_seconds':time.monotonic()-start,'native_proven':False,'stage_pass':False}
(D/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
raise SystemExit(0 if clean and all(x['oracle_pass'] for x in results) else 1)
