import sys,json,os,time,uuid
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if not (root/'.s3-synthetic-fixture').is_file() or not str(root).startswith('/tmp/lvw-s3-p2b-'):raise SystemExit(2)
r=json.loads(sys.stdin.buffer.read(32769))
if str(uuid.UUID(r['request_id']))!=r['request_id']:raise SystemExit(2)
birth=int(Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19])
d=root/'.s3-owned-requests';d.mkdir(exist_ok=True)
j=d/(r['request_id']+'.json')
v=dict(request_id=r['request_id'],binding_sha256=r['binding_sha256'],pid=os.getpid(),birth={'linux_start_ticks':birth},state='ENTERED')
tmp=j.with_suffix('.writing')
with tmp.open('x') as f:json.dump(v,f)
os.link(tmp,j);tmp.unlink()
time.sleep(.3)
v['state']='FAULT_HELPER_RETURNED';tmp.write_text(json.dumps(v));os.replace(tmp,j)
r['request_id']='00000000-0000-0000-0000-000000000000'
print(json.dumps(r))
