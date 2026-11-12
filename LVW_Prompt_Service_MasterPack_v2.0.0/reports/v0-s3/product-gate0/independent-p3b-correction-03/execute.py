"""Bookkeeping only; guarded validation runs in a separate interpreter."""
import sys,os,json,subprocess,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent;PACK=OUT.parents[3]
mode=sys.argv[1]
cmd=[sys.executable,'-B',str(OUT/'launch.py'),mode]
files=[PACK/'tools/v0_s3_quality_phase.py',PACK/'tools/test_v0_s3_quality_phase.py',OUT/'launch.py']
if mode=='focused':files.append(OUT/'focused.py')
if mode=='replay':files.append(PACK/'reports/v0-s3/product-gate0/implementation-p3b-correction-03/replay_correction02_probes.py')
def hashes():return {str(p.relative_to(PACK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
r={'command':cmd,'cwd':str(PACK),'candidate_sha':'630853c63a919433ccf31958d36179e4e0b3bdee','before':hashes()}
(OUT/(mode+'.command.json')).write_text(json.dumps(r,indent=2)+'\n')
with (OUT/(mode+'.stdout.log')).open('wb') as out,(OUT/(mode+'.stderr.log')).open('wb') as err:
    p=subprocess.run(cmd,cwd=PACK,stdout=out,stderr=err,env={**os.environ,'PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1','PYTHONDONTWRITEBYTECODE':'1'})
r.update(exit_code=p.returncode,after=hashes(),streams={k:{'sha256':hashlib.sha256((OUT/(mode+'.'+k+'.log')).read_bytes()).hexdigest(),'bytes':(OUT/(mode+'.'+k+'.log')).stat().st_size} for k in ['stdout','stderr']})
(OUT/(mode+'.command.json')).write_text(json.dumps(r,indent=2)+'\n')
print(json.dumps(r))
sys.exit(p.returncode)
