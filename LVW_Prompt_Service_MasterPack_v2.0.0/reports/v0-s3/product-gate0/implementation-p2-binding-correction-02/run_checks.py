from pathlib import Path
import json, subprocess, tempfile, time, os
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
sets=[['tools/test_v0_s3_runtime_binding.py','-k','correction02','-s'],['tools/test_v0_s3_runtime_binding.py','tools/test_v0_s3_budget_authority.py','LVW_V0_RuntimePatch/tests/test_s3_program_budget.py'],['LVW_V0_RuntimePatch/tests/'+x for x in ['test_s2_measurements.py','test_s2_lifecycle_authorization.py','test_lvw_v0_bridge.py','test_s2_video_transport.py','test_s2_native_evidence.py','test_s2_warm_benchmark.py','test_s2_runtime.py']]]
records=[]
for i,files in enumerate(sets,1):
 with tempfile.TemporaryDirectory(prefix='lvw-independent-p2b-') as tmp:
  argv=['python3','-B','-m','pytest','-q','-p','no:cacheprovider',*files,'--basetemp='+tmp+'/pytest']
  start=time.monotonic()
  with (OUT/f'check-{i}.stdout').open('w') as out,(OUT/f'check-{i}.stderr').open('w') as err:
   result=subprocess.run(argv,cwd=ROOT,stdout=out,stderr=err,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'),timeout=180)
  records.append(dict(argv=argv,cwd=str(ROOT),exit=result.returncode,elapsed=time.monotonic()-start,owned_root=tmp))
 records[-1]['temporary_root_removed']=not Path(tmp).exists()
(OUT/'checks.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps(records,indent=2))
