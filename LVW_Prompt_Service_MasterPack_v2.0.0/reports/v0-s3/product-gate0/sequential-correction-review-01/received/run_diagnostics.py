from pathlib import Path
import subprocess,sys,json,time,hashlib
p=Path(__file__).resolve().parent
for script,label in [('negative_probes.py','negative'),('idempotency_deadline_probes.py','idempotency-deadline')]:
 argv=[sys.executable,'-B',str(p/script)]
 s=time.time();r=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 for stream,data in [('stdout',r.stdout),('stderr',r.stderr)]: (p/(label+'.'+stream+'.log')).write_bytes(data)
 (p/(label+'.outer.json')).write_text(json.dumps({'argv':argv,'cwd':str(Path.cwd()),'returncode':r.returncode,'started_wall':s,'finished_wall':time.time(),'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()},indent=2))
 print(label,r.returncode,r.stdout.decode().splitlines()[-1:]);print(r.stderr.decode())
