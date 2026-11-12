import runpy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
runpy.run_path(str(ROOT/'reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py'),run_name='guard')
import tempfile,shutil,json
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
root=Path(tempfile.mkdtemp(prefix='lvw-independent-p3b-bounds-139573-'));results=[]
def attempt(p,path,data):
 try:return p._artifact(path,data)['bytes']
 except Exception as e:return str(e)
try:
 p,_,_=t._prepare(root/'size');p.directory.mkdir()
 results.append({'probe':'file_bytes','exact':attempt(p,'exact',b'x'*q.MAX_ARTIFACT_BYTES),'one_over':attempt(p,'over',b'x'*(q.MAX_ARTIFACT_BYTES+1))})
 p,_,_=t._prepare(root/'total');p.directory.mkdir()
 for i in range(16):p._artifact(str(i),b'x'*q.MAX_ARTIFACT_BYTES)
 results.append({'probe':'total_bytes','exact':p._artifact_bytes,'one_over':attempt(p,'over',b'x')})
 p,_,_=t._prepare(root/'files');p.directory.mkdir()
 for i in range(256):p._artifact(str(i),b'')
 results.append({'probe':'file_count','exact':p._artifact_files,'one_over':attempt(p,'over',b'')})
 p,d,_=t._prepare(root/'existing');p.directory.mkdir();r=p.run()
 results.append({'probe':'existing_directory','decision':r['decision'],'new_receipt_written':(p.directory/'qd-receipt.json').exists(),'submissions':d.submissions})
finally:shutil.rmtree(root)
print(json.dumps({'results':results,'root':str(root),'removed':not root.exists()},indent=2))
