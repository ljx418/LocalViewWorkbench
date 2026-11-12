"""Bookkeeping launcher for one bounded supplement, using inspected immutable guard."""
import subprocess,sys,json,hashlib
from pathlib import Path
OUT=Path(__file__).resolve().parent;PACK=OUT.parents[3]
runner=PACK/'reports/v0-s3/product-gate0/implementation-p3b-correction-03/run_guarded_probe.py'
script=OUT/'supplement.py'
cmd=[sys.executable,'-B',str(runner),'--script',str(script),'--outdir',str(OUT),'--label','supplement','--candidate-sha','630853c63a919433ccf31958d36179e4e0b3bdee']
def hashes():return {str(p.relative_to(PACK)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [runner,script,PACK/'tools/v0_s3_quality_phase.py',PACK/'tools/test_v0_s3_quality_phase.py']}
r={'command':cmd,'cwd':str(PACK),'before':hashes()}
with (OUT/'supplement.runner.stdout.log').open('wb') as out,(OUT/'supplement.runner.stderr.log').open('wb') as err:p=subprocess.run(cmd,cwd=PACK,stdout=out,stderr=err)
r.update(real_exit_code=p.returncode,after=hashes())
(OUT/'supplement.command.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r));sys.exit(p.returncode)
