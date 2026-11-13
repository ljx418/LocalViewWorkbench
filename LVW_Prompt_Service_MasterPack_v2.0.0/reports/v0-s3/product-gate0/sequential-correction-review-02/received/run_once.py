from pathlib import Path
import subprocess,sys,json,hashlib,time
OUT=Path(__file__).resolve().parent
PACK=OUT.parents[3]
launch=OUT/'launch.py'
commands=[('focused',[sys.executable,'-B',str(launch),'--mode','focused','--label','independent-sequential02-focused','--outdir',str(OUT),'--modules','tools/test_v0_s3_supervisor.py','--select','slot or reconciliation or sequential or finalizer']),('guard',[sys.executable,'-B',str(launch),'--mode','guard','--label','independent-sequential02-guard','--outdir',str(OUT)])]
for name,argv in commands:
 start=time.time()
 result=subprocess.run(argv,cwd=PACK,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 for ext,data in [('stdout',result.stdout),('stderr',result.stderr)]: (OUT/(name+'.outer.'+ext+'.log')).write_bytes(data)
 (OUT/(name+'.outer.json')).write_text(json.dumps({'argv':argv,'cwd':str(PACK),'returncode':result.returncode,'started_wall':start,'finished_wall':time.time(),'stdout_sha256':hashlib.sha256(result.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(result.stderr).hexdigest()},indent=2))
 print(name,result.returncode,result.stdout.decode()[-1200:],result.stderr.decode()[-800:])
