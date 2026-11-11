import pathlib,sys,json,tempfile,time
sys.path.insert(0,str(pathlib.Path.cwd()/'tools'));import s3_sample_preparation as s
O=pathlib.Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='s3-probe-failure-') as td:
 p=pathlib.Path(td)/'probe';p.write_text('#!'+sys.executable+'\nimport os\nos.write(1,b\'{}\'+b\' \'*(4*1024*1024))\n');p.chmod(0o700)
 a=s.MediaAdapter(p,p);a.budget=s.OutputAccountant(deadline=time.monotonic()+5)
 entry,doc=a.probe_video(pathlib.Path(td)/'unused','overflow')
 result={k:v for k,v in entry.items() if k not in ['stdout_text','stderr_text']};result['document']=doc
result['temp_absent']=not pathlib.Path(td).exists();(O/'probe-failure.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
