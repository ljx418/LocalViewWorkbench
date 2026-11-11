import sys, os, json, errno, tempfile, importlib.util
from pathlib import Path
from types import SimpleNamespace
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
def audit(event,args):
    if event in ('subprocess.Popen','os.system','os.exec','os.posix_spawn','socket.connect','socket.bind'):raise RuntimeError('probe process/network denied')
    if event=='open' and isinstance(args[0],(str,bytes)) and os.fsdecode(args[0]).startswith('/mnt/'):raise RuntimeError('probe host denied')
sys.addaudithook(audit)
spec=importlib.util.spec_from_file_location('independent_harness',ROOT/'tools/v0_s3_runtime_binding.py')
h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
results=[]
def save():
    p=OUT/'probes.json';t=p.with_suffix('.writing')
    t.write_text(json.dumps(results,indent=2));os.replace(t,p)
with tempfile.TemporaryDirectory(prefix='lvw-p2b-independent-probes-') as tmp:
    root=Path(tmp);original=dict(h.FIXED)
    sizes={'windows_python':7,'wsl':11,'python':13}
    h.FIXED={r:str(root/r) for r in sizes}
    for r,p in h.FIXED.items():Path(p).write_bytes(b'x'*sizes[r])
    charged=7+32*11+32*13
    for cap in (charged-1,charged,charged+1):
        h.LIMITS['metadata_hash_bytes']=cap;m=h.Meter();error=None;reads=0
        try:
            reservation=h.reserve_metadata(m)
            # Actual partial synthetic read followed by I/O failure, no refund.
            with Path(h.FIXED['wsl']).open('rb') as f:
                reads=len(f.read(2));raise OSError(errno.EIO,'independent partial read')
        except ValueError as e:error=str(e)
        except OSError as e:error=str(e)
        results.append(dict(kind='reservation',cap=cap,charged=m.used['metadata_hash_bytes'],partial_synthetic_bytes=reads,error=error,reservation=getattr(m,'metadata_reservation',None)))
        save()
        assert m.used['metadata_hash_bytes']==(charged if cap>charged else 0)
        assert reads==(2 if cap>charged else 0)
    h.FIXED=original
    obs=root/'observer';obs.mkdir();(obs/'.s3-synthetic-fixture').touch();d=obs/'.s3-owned-requests';d.mkdir()
    rid='00000000-0000-0000-0000-000000000099';path=d/(rid+'.json')
    original_sleep=h.time.sleep;h.time.sleep=lambda _:None
    for scenario in ('eio','bad-observed-birth','bad-bound-birth'):
        journal=dict(request_id=rid,pid=321,birth={'linux_start_ticks':20},binding_sha256='b',state='ENTERED')
        if scenario=='bad-bound-birth':journal['birth']['linux_start_ticks']='20'
        path.write_text(json.dumps(journal));lookups=[]
        def birth(pid):
            lookups.append(pid)
            if scenario=='eio':raise OSError(errno.EIO,'synthetic I/O failure')
            return {'linux_start_ticks':'20'}
        h.protocol=lambda root:SimpleNamespace(process_birth=birth)
        o=h.Observer(obs,'b');o.stop.set();o.thread.start();r=o.finish()
        results.append(dict(kind='observer',scenario=scenario,result=r,lookups=lookups));save()
        assert r['error'] and not r['two_absences'] and r['joined']
        if scenario=='bad-bound-birth':assert not lookups
    h.time.sleep=original_sleep
results.append(dict(kind='cleanup',owned_tmp=tmp,removed=not Path(tmp).exists()));save()
print(json.dumps({'probes':len(results)-1,'owned_removed':not Path(tmp).exists()}))
