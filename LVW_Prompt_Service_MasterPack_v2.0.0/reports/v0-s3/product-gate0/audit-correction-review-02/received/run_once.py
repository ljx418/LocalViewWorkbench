"""Outer shell-equivalent supervisor: no candidate imported in this process."""
import subprocess,sys,json,os
from pathlib import Path
out=Path(__file__).resolve().parent
pack=out.parents[3]
select='refused_start or machine_accounting or real_guard_refusal or copied_marker or replayed_real_guard or settlement_failed or proof_of_a_child or guard_installation or complete_effective_command'
for mode in ('focused','guard'):
 label='independent-audit02-'+mode
 command=[sys.executable,'-B',str(out/'launch.py'),'--mode',mode,'--label',label,'--outdir','reports/v0-s3/product-gate0/independent-audit-correction-02']
 if mode=='focused':command+=['--modules','tools/test_v0_s3_supervisor.py','--select',select]
 with (out/(label+'.outer.stdout.log')).open('wb') as so,(out/(label+'.outer.stderr.log')).open('wb') as se:
  result=subprocess.run(command,cwd=pack,stdout=so,stderr=se,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
 (out/(label+'.outer.json')).write_text(json.dumps({'command':command,'returncode':result.returncode},indent=2))
 print(mode,result.returncode)
