import pathlib,sys,tempfile,json,hashlib
from PIL import Image
O=pathlib.Path(__file__).resolve().parent;P=O.parents[4];sys.path.insert(0,str(P/'tools'))
import s3_sample_preparation as s
with tempfile.TemporaryDirectory(prefix='s3-review-output-budget-') as td:
 base=pathlib.Path(td);src=base/'source';src.mkdir();(src/'x.mp4').write_bytes(b'fake')
 row={'file_id':'f'*64,'relative_path':'x.mp4','media_kind':'video','bytes':4,'sha256':hashlib.sha256(b'fake').hexdigest()}
 class Fake:
  run_log=[]
  def probe_video(self,*a):return {'exit_code':0},{'format':{'format_name':'mp4','duration':4},'streams':[{'codec_type':'video','width':8,'height':8}]}
  def extract_frame(self,path,offset,out,label):
   Image.new('RGB',(8,8),'red').save(out);out.write_bytes(out.read_bytes()+b'\0'*100000);return {'exit_code':0}
 limits=dict(s.EXPECTED_LIMITS);limits['output_bytes']=100000
 r=s.prepare(package_root=base,child={'selected_files':[row],'source_root':str(src),'limits':limits},runtime_root=base/'run',receipt_path=base/'receipt.json',adapter=Fake(),clock=lambda:0)
 result={'synthetic_only':True,'limit':100000,'retained':r['budget']['output_bytes_retained'],'staging':r['budget']['output_bytes_staging'],'decision':r['decision'],'defect_reproduced':r['budget']['output_bytes_staging']>100000 and r['budget']['output_bytes_retained']<100000 and r['decision']=='PREPARATION_COMPLETE_READY_FOR_REVIEW','staging_removed':r['cleanup']['staging_removed'],'owned_entries_before_cleanup':len(list(base.rglob('*')))}
result['owned_temp_absent_after']=not base.exists()
print(json.dumps(result,indent=2));(O/'output-budget-counterexample.json').write_text(json.dumps(result,indent=2)+'\n')
