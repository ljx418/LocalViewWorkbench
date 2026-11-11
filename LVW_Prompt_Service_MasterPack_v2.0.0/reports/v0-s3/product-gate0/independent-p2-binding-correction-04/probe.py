"""Single independent public-run claim-finalization failure probe; no parser."""
import sys, os, json, tempfile, shutil, runpy
from pathlib import Path
OUT=Path(__file__).resolve().parent
# Reuse identical audited guard initialization only (does not run pytest/parser).
sys.argv=[str(OUT/'runner.py'),'combined']
exec((OUT/'runner.py').read_text().split("files=['tools/test_v0_s3_runtime_binding.py']")[0])
import pytest
sys.path.insert(0,str(ROOT/'tools'))
import test_v0_s3_runtime_binding as tests
h=tests.harness
realrun=h.run
result={}
def run():
    oldwrite=h.write
    def write(path,value):
        if Path(path).name=='shared.claim' and value.get('status')=='EXPIRED':raise OSError('independent synthetic claim-finalization failure')
        return oldwrite(path,value)
    h.write=write
    try:
        life=realrun()
        result['returned_status']=life['status'];result['terminal_persisted']=life['terminal_persisted']
        result['terminal']=json.loads((h.BASE/'cross-os-lifecycle.json').read_bytes())
        result['claim']=json.loads((h.BASE.parent/'shared.claim').read_bytes())
        result['local_consumed']=json.loads((h.BASE/'consumed.json').read_bytes())
        shutil.copytree(h.BASE,OUT/'probe-raw')
        return life
    finally:h.write=oldwrite
h.run=run
os.environ.pop('P2B_RAW_DIR',None)
with tempfile.TemporaryDirectory(prefix='lvw-independent-claim-') as tmp:
    mp=pytest.MonkeyPatch()
    try:
        tests.test_correction04_public_run_maximum(Path(tmp),mp,None)
    except AssertionError:
        result['original_success_oracle']='REJECTED_AS_EXPECTED'
    finally:mp.undo()
result['owned_tmp']=tmp;result['removed']=not Path(tmp).exists()
result['denied']=denied;result['processes']=records
result['reproduced']=result['returned_status']=='BLOCKED' and result['terminal']['status']=='READY_FOR_REVIEW' and result['claim']['status']=='RUNNING' and result['local_consumed']['result']=='READY_FOR_REVIEW'
(OUT/'probe-receipt.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('terminal','claim','local_consumed','processes')}))
assert result['reproduced']
