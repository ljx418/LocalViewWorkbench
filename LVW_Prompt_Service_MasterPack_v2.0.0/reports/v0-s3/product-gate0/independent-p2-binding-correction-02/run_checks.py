"""Guard first; one affected combination and one preserved oracle run."""
from pathlib import Path
import json, os, subprocess, sys, tempfile, time
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
records=[]
def run(name, argv):
    start=time.monotonic()
    with (OUT/(name+'.stdout')).open('w') as out, (OUT/(name+'.stderr')).open('w') as err:
        p=subprocess.run(argv,cwd=ROOT,stdout=out,stderr=err,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=180)
    record=dict(name=name,argv=argv,cwd=str(ROOT),exit=p.returncode,elapsed=time.monotonic()-start)
    records.append(record)
    (OUT/(name+'.exit')).write_text(str(p.returncode)+'\n')
    (OUT/'checks.json').write_text(json.dumps(records,indent=2)+'\n')
    return p.returncode
if run('guard',[sys.executable,'-B',str(OUT/'probes.py'),'guard']):
    raise SystemExit('guard failed: STOP, no tests')
sets=[['tools/test_v0_s3_runtime_binding.py','tools/test_v0_s3_budget_authority.py','LVW_V0_RuntimePatch/tests/test_s3_program_budget.py'],
      ['LVW_V0_RuntimePatch/tests/'+x for x in ['test_s2_measurements.py','test_s2_lifecycle_authorization.py','test_lvw_v0_bridge.py','test_s2_video_transport.py','test_s2_native_evidence.py','test_s2_warm_benchmark.py','test_s2_runtime.py']]]
for i, files in enumerate(sets,1):
    with tempfile.TemporaryDirectory(prefix='lvw-p2b-independent-check-') as tmp:
        run('check-'+str(i),[sys.executable,'-B','-m','pytest','-q','-s','-p','no:cacheprovider',*files,'--basetemp='+tmp+'/pytest'])
        records[-1]['owned_basetemp_parent']=tmp
    records[-1]['temporary_root_removed']=not Path(tmp).exists()
run('observer-probe',[sys.executable,'-B',str(OUT/'probes.py'),'observer'])
(OUT/'checks.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2))
