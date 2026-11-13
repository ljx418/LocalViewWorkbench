"""Only outer launcher may read (never write) the existing shared counter."""
import sys,subprocess,json,hashlib,time
from pathlib import Path
O=Path(__file__).resolve().parent
P=next(p for p in O.parents if (p/'tools/v0_s3_supervisor.py').is_file())
counter=Path('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json')
before=hashlib.sha256(counter.read_bytes()).hexdigest()
assert before=='8f12beb38c78378e51d3164cf02f54e54d619f55f2286a8d128b81249dc0fb18'
steps=[]
for label in sys.argv[1:]:
 argv=[sys.executable,'-B',str(O/'guard.py'),str(O/(label+'.py')),str(O/(label+'.guard.json'))]
 start=time.monotonic()
 result=subprocess.run(argv,cwd=P,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45)
 (O/(label+'.stdout')).write_bytes(result.stdout)
 (O/(label+'.stderr')).write_bytes(result.stderr)
 steps.append({'argv':argv,'cwd':str(P),'exit':result.returncode,'seconds':time.monotonic()-start,'label':label})
 print(label,result.returncode,result.stdout.decode()[-1500:],result.stderr.decode()[-1500:])
after=hashlib.sha256(counter.read_bytes()).hexdigest()
assert before==after
(O/('commands-'+ '-'.join(sys.argv[1:])+'.json')).write_text(json.dumps({'steps':steps,'counter_before':before,'counter_after':after,'counter_unchanged':True},indent=2))
