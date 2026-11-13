from pathlib import Path
import subprocess,json,time,sys
D=Path(__file__).parent.resolve();pack=D.parents[3]
label=sys.argv[1];entry=sys.argv[2];argv=[sys.executable,'-B',str(D/'guard.py'),str(D/entry),str(D/(label+'.guard.json')),*sys.argv[3:]]
start=time.time();p=subprocess.run(argv,cwd=pack,capture_output=True)
(D/(label+'.stdout.log')).write_bytes(p.stdout);(D/(label+'.stderr.log')).write_bytes(p.stderr)
rec={'label':label,'argv':argv,'cwd':str(pack),'start_wall':start,'end_wall':time.time(),'exit':p.returncode,'stdout':label+'.stdout.log','stderr':label+'.stderr.log'}
f=D/'commands.json';old=json.loads(f.read_text()) if f.exists() else [];old.append(rec);f.write_text(json.dumps(old,indent=2));print(json.dumps(rec));print(p.stdout.decode()[-5000:]);print(p.stderr.decode()[-1500:])
