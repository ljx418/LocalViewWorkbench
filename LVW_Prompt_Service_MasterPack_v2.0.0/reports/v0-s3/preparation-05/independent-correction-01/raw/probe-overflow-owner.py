import pathlib,sys,tempfile,json,hashlib,time
from PIL import Image
sys.path.insert(0,str(pathlib.Path.cwd()/'tools'));import s3_sample_preparation as s
O=pathlib.Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='s3-overflow-owner-') as td:
 root=pathlib.Path(td);src=root/'source';src.mkdir();(src/'a.mp4').write_bytes(b'synthetic')
 doc={'format':{'format_name':'mp4','duration':4},'streams':[{'codec_type':'video','width':8,'height':8}]}
 exe=root/'probe';exe.write_text('#!'+sys.executable+'\nimport os\nos.write(1,'+repr(json.dumps(doc).encode())+'+b" "*(4*1024*1024))\n');exe.chmod(0o700)
 class Adapter(s.MediaAdapter):
  def __init__(self):super().__init__(exe,exe);self.frames=0
  def extract_frame(self,p,t,out,label):
   self.frames+=1;Image.new('RGB',(8,8),'red').save(out);return {'exit_code':0}
 adapter=Adapter();row={'file_id':'f'*64,'relative_path':'a.mp4','media_kind':'video','bytes':9,'sha256':hashlib.sha256(b'synthetic').hexdigest()}
 r=s.prepare(package_root=root,child={'source_root':str(src),'selected_files':[row],'limits':dict(s.EXPECTED_LIMITS)},runtime_root=root/'run',receipt_path=root/'terminal.json',adapter=adapter)
 result={'decision':r['decision'],'counts':r['counts'],'probe_error':adapter.run_log[0]['error'],'probe_exit':adapter.run_log[0]['exit_code'],'frames_after_failure':adapter.frames,'budget':r['budget'],'cleanup':r['cleanup'],'owned_bytes_before':sum(p.stat().st_size for p in root.rglob('*') if p.is_file()),'owned_entries_before':len(list(root.rglob('*')))}
 result['defect_observed']=result['probe_error'].endswith('VIDEO_PROCESS_OUTPUT_LIMIT') and r['counts']['eligible']==1 and r['decision']=='PREPARATION_COMPLETE_READY_FOR_REVIEW'
 (O/'probe-overflow-owner-receipt.json').write_text(json.dumps(r,indent=2)+'\n')
result['owned_temp_absent_after']=not root.exists();(O/'probe-overflow-owner.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
assert result['defect_observed']
