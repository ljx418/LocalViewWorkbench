from pathlib import Path
import subprocess,sys,json,hashlib,time
OUT=Path(__file__).resolve().parent
argv=[sys.executable,'-B',str(OUT/'negative_probes.py')];start=time.time()
r=subprocess.run(argv,cwd=OUT.parents[3],capture_output=True)
for kind,data in [('stdout',r.stdout),('stderr',r.stderr)]: (OUT/('negative.'+kind+'.log')).write_bytes(data)
(OUT/'negative.outer.json').write_text(json.dumps({'argv':argv,'cwd':str(OUT.parents[3]),'returncode':r.returncode,'started_wall':start,'finished_wall':time.time(),'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()},indent=2))
print(r.returncode,r.stdout.decode()[-1600:],r.stderr.decode())
