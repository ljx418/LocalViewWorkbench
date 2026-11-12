import hashlib,json,os,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent
R=P.parents[3]
def write(name,b):
 with (P/name).open('xb') as f:f.write(b);f.flush();os.fsync(f.fileno())
def save(name,d):write(name,(json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode())
def main():
 c=json.loads((P/'child.json').read_bytes());ch=hashlib.sha256((P/'child.json').read_bytes()).hexdigest()
 assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==c['executor_sha256']
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=R.parent,text=True).strip()==c['candidate_sha']
 a=R/c['parent_approval'];ap=json.loads(a.read_bytes());assert hashlib.sha256(a.read_bytes()).hexdigest()==c['parent_approval_sha256'] and ap['decision']=='APPROVED'
 assert hashlib.sha256((R/c['parent_request']).read_bytes()).hexdigest()==ap['request_sha256']
 raw=(P/'native-probe.py.txt').read_bytes();assert hashlib.sha256(raw).hexdigest()==c['native_probe_sha256']
 exe=Path(c['command'][0]);assert exe.is_file() and not exe.is_symlink() and exe.stat().st_size==104952
 assert hashlib.sha256(exe.read_bytes()).hexdigest()==c['native_python_sha256']
 claim=Path(c['claim_path']);claim.parent.mkdir(parents=True,exist_ok=True)
 with claim.open('xb') as f:f.write(json.dumps({'status':'RUNNING','child_sha256':ch}).encode());f.flush();os.fsync(f.fileno())
 started=time.monotonic();result={'kind':'A06_WFP_READ_ONLY_FACTS_NOT_ACCEPTANCE','candidate_sha':c['candidate_sha'],'child_sha256':ch,'stage_pass_claim':False,'product_gate0':False,'native_processes_started':0,'status':'UNPROVEN','termination_signals':0}
 try:
  save('command.json',{'argv':c['command'],'timeout_seconds':8})
  result['native_processes_started']=1;proc=subprocess.Popen(c['command'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:out,err=proc.communicate(timeout=8)
  except subprocess.TimeoutExpired as e:
   write('stdout.log',e.output or b'');write('stderr.log',e.stderr or b'');result['exit_proven']=False;result['owned_interop_pid']=proc.pid;raise RuntimeError('timeout: no retries, exit unproven')
  write('stdout.log',out);write('stderr.log',err);write('exit.log',(str(proc.returncode)+'\n').encode());result['exit_proven']=True
  assert len(out)+len(err)<=4096 and proc.returncode==0 and not err
  obs=json.loads(out);assert obs['mutation_calls']==0 and type(obs['open_result']) is int
  result['observation']=obs;result['status']='FACTS_COLLECTED_NOT_RUNTIME_ACCEPTANCE'
 except BaseException as e:result['error']={'type':type(e).__name__,'message':str(e)}
 finally:
  result['wall_seconds']=time.monotonic()-started;result['child_expired']=True;result['effects']={k:0 for k in ('models','media','gpu','services','network','downloads','system_changes','production_ledger','full_checkpoints')};save('receipt.json',result)
  final=claim.with_suffix('.final.tmp')
  with final.open('xb') as f:f.write(json.dumps({'status':'EXPIRED','child_sha256':ch,'receipt_sha256':hashlib.sha256((P/'receipt.json').read_bytes()).hexdigest()}).encode());f.flush();os.fsync(f.fileno())
  os.replace(final,claim)
 print(json.dumps(result,ensure_ascii=False))
 return 0 if result['status']=='FACTS_COLLECTED_NOT_RUNTIME_ACCEPTANCE' else 1
if __name__=='__main__':raise SystemExit(main())
