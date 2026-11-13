import os,json,copy,hashlib,threading,time
from pathlib import Path
from tools import v0_s3_coordinator as c
O=Path(__file__).resolve().parent
results={}
B={'run_id':'independent','candidate_sha':'a'*40}
def receipts():
 return {n:{'kind':c.AGGREGATE_RECEIPT_KIND,'status':'PASS',**B,'stage_pass_claim':False,'real_isolation':True,'independent':True,'cleanup_proven':True} for req in c.TWELVE_REQUIREMENTS.values() for n in req}
variants={
 'missing':None,'bad_kind':{'kind':'foreign'},'bad_status':{'status':'true'},
 'wrong_binding':{'candidate_sha':'b'*40},'string_true':{'cleanup_proven':'true'},
 'string_false':{'cleanup_proven':'false'},'false':{'cleanup_proven':False},
 'integer_one':{'cleanup_proven':1},'FAIL':{'status':'FAIL'},
 'BLOCKED':{'status':'BLOCKED'},'NOT_RUN':{'status':'NOT_RUN'},'stage_claim':{'stage_pass_claim':True}}
checks={}
for name,change in variants.items():
 r=receipts()
 if change is None:del r['cleanup']
 else:r['cleanup'].update(change)
 s=c.aggregate_twelve_keys(receipts=r,binding=B);assert s['pass_count']==0
 checks[name]={'counts':{k:s[k] for k in ('pass_count','fail_count','blocked_count','not_run_count')},'cleanup_proven':s['cleanup_proven']}
for field in ('kind','status','run_id','candidate_sha','stage_pass_claim','cleanup_proven'):
 r=receipts();del r['cleanup'][field];s=c.aggregate_twelve_keys(receipts=r,binding=B);assert s['pass_count']==0;checks['missing_'+field]=s['keys']['V0-A01']
r=receipts();good=c.aggregate_twelve_keys(receipts=r,binding=B);assert good['pass_count']==12 and not good['stage_pass_claim']
for name in ('independent_score','a06_isolation'):
 r=receipts();del r[name];s=c.aggregate_twelve_keys(receipts=r,binding=B);assert s['pass_count']<12;checks['missing_'+name]=s['pass_count']
r=receipts();r['a06_isolation']['real_isolation']=False;assert c.aggregate_twelve_keys(receipts=r,binding=B)['pass_count']==0
r=receipts();r['cleanup']['status']='FAIL';r['stage_binding']['status']='NOT_RUN';assert c.aggregate_twelve_keys(receipts=r,binding=B)['fail_count']==12
old=c.aggregate_twelve_keys(receipts={'old9':{'status':'PASS'}},binding=B);assert old['pass_count']==0
results['C']={'variants':checks,'legal_synthetic_all12':good['pass_count'],'old9':old['pass_count'],'product_pass':False}

rows=[{'ordinal':i,'asset_id':'I%02d'%i,'media_kind':'image','source_sha256':'d'*64,'source_bytes':1} for i in range(1,17)]
def evidence(name):
 root=O/name;root.mkdir();(root/'canonical').write_bytes(b'{}');(root/'source').write_bytes(b'[]');(root/'raw').write_bytes(b'ORIGINAL')
 e=c.ParentOriginalEvidence(**B,child_sha256='b'*64,root=root,projection_sha256='c'*64);e.seal_plan(rows);st=root.stat();e.seal_root([st.st_dev,st.st_ino]);e.seal_originals(canonical='canonical',source_plan='source',raw=['raw']);return root,e
def refuse(fn):
 try:fn()
 except c.S3IntegrationError as e:return str(e)
 raise AssertionError('expected refusal')
fd_before=len(list(Path('/proc/self/fd').iterdir()))
root,e=evidence('mutation-window')
real_read=os.read;target=(root/'raw').stat().st_ino;trigger=[]
def mutate_after_read(fd,size):
 block=real_read(fd,size)
 if block and os.fstat(fd).st_ino==target and not trigger:
  trigger.append(True);(root/'raw').write_bytes(b'MODIFIED')
 return block
os.read=mutate_after_read
try:manifest=e.manifest()
finally:os.read=real_read
actual=hashlib.sha256((root/'raw').read_bytes()).hexdigest();sealed=manifest['originals']['raw'][0]['sha256']
assert trigger and manifest['reverification']['verified'] and actual!=sealed
results['O_read_window']={'defect_reproduced':True,'manifest_verified':True,'sealed_sha256':sealed,'current_sha256':actual,'guarded_same_process_only':True}
results['O_next_reverify_refuses']=refuse(e.manifest)
root,e=evidence('same-bytes-window');target=(root/'raw').stat().st_ino;trigger=[]
def rewrite_same(fd,size):
 block=real_read(fd,size)
 if block and os.fstat(fd).st_ino==target and not trigger:
  trigger.append(True);(root/'raw').write_bytes(b'ORIGINAL')
 return block
os.read=rewrite_same
try:manifest=e.manifest()
finally:os.read=real_read
assert trigger and manifest['reverification']['verified']
results['O_same_bytes_window']={'defect_reproduced':True,'manifest_verified':True,'next_reverify':refuse(e.manifest)}

root,e=evidence('fifo-window');(root/'raw').unlink();os.mkfifo(root/'raw');box={}
def consume():
 try:e.manifest();box['accepted']=True
 except Exception as ex:box['exception']=str(ex)
t=threading.Thread(target=consume);start=time.monotonic();t.start();t.join(.06);blocked=t.is_alive();assert blocked
writer=os.open(root/'raw',os.O_WRONLY|os.O_NONBLOCK);os.close(writer);t.join(2);assert not t.is_alive() and 'ORIGINAL' in box['exception']
(root/'raw').unlink()
results['O_fifo']={'blocked_until_external_writer':blocked,'elapsed_seconds':time.monotonic()-start,'eventual':box,'thread_settled':not t.is_alive()}
root,e=evidence('safe-open-unsupported');original=c._no_follow_open_supported;c._no_follow_open_supported=lambda:False
try:results['O_missing_primitive']=refuse(e.manifest)
finally:c._no_follow_open_supported=original
for i in range(12):
 root2=O/('exception-'+str(i));root2.mkdir();e2=c.ParentOriginalEvidence(**B,child_sha256='b'*64,root=root2,projection_sha256='c'*64);e2.seal_plan(rows);st=root2.stat();e2.seal_root([st.st_dev,st.st_ino]);refuse(lambda:e2.seal_originals(canonical='missing',source_plan='missing'))
fd_after=len(list(Path('/proc/self/fd').iterdir()));assert fd_after==fd_before
results['O_fd_cleanup']={'before':fd_before,'after':fd_after,'missing_artifact_attempts':12}
(O/'owner-checks.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
