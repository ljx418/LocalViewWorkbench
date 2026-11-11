import tempfile,subprocess,os,json,pathlib
out=pathlib.Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='s3-independent-correction-suite-') as td:
 root=pathlib.Path(td)
 cmd=['python3','-B','-m','pytest','tools/test_s3_sample_preparation.py','-q','-rP','-p','no:cacheprovider','--basetemp='+str(root/'pytest')]
 env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
 p=subprocess.run(cmd,env=env,capture_output=True)
 for suffix,data in [('stdout.log',p.stdout),('stderr.log',p.stderr),('exit.log',str(p.returncode).encode())]: (out/('suite.'+suffix)).write_bytes(data)
 files=[x for x in root.rglob('*') if x.is_file()]
 measured={'entries':len(list(root.rglob('*'))),'files':len(files),'bytes':sum(x.stat().st_size for x in files)}
(out/'suite-command-cleanup.json').write_text(json.dumps({'argv':cmd,'env':{'PYTHONDONTWRITEBYTECODE':'1'},'exit':p.returncode,'owned_root':str(root),'before_cleanup':measured,'absent_after':not root.exists()},indent=2)+'\n')
print(p.stdout.decode());print('exit',p.returncode,'cleaned',not root.exists())
