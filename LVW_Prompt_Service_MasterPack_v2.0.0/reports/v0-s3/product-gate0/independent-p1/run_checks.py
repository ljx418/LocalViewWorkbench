import hashlib,json,os,subprocess,tempfile,time
from pathlib import Path
ROOT=Path.cwd(); OUT=ROOT/'reports/v0-s3/product-gate0/independent-p1'
checks=[]
commands=[['tools/test_v0_s3_budget_authority.py','LVW_V0_RuntimePatch/tests/test_s3_program_budget.py','LVW_V0_RuntimePatch/tests/test_s2_measurements.py','LVW_V0_RuntimePatch/tests/test_s2_lifecycle_authorization.py'],['LVW_V0_RuntimePatch/tests/test_lvw_v0_bridge.py','LVW_V0_RuntimePatch/tests/test_s2_video_transport.py','LVW_V0_RuntimePatch/tests/test_s2_native_evidence.py','LVW_V0_RuntimePatch/tests/test_s2_warm_benchmark.py','LVW_V0_RuntimePatch/tests/test_s2_runtime.py']]
for index,files in enumerate(commands,1):
    with tempfile.TemporaryDirectory(prefix='lvw-independent-p1-') as owned:
        argv=['python3','-B','-m','pytest',*files,'-q','-p','no:cacheprovider','--basetemp='+owned+'/pytest']
        start=time.monotonic();result=subprocess.run(argv,capture_output=True,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
        for stream in ('stdout','stderr'):(OUT/f'check-{index}.{stream}').write_bytes(getattr(result,stream))
        entry=dict(argv=argv,cwd=str(ROOT),exit=result.returncode,elapsed=time.monotonic()-start,owned_root=owned)
    entry['temporary_root_removed']=not Path(owned).exists();checks.append(entry)
    print(json.dumps(entry));print(result.stdout.decode());print(result.stderr.decode())
(OUT/'checks.json').write_text(json.dumps(checks,indent=2)+'\n')
assert all(c['exit']==0 and c['temporary_root_removed'] for c in checks)
