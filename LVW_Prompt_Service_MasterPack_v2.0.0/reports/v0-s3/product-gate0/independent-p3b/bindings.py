"""Read-only Git/file binding audit; never imports product code."""
import hashlib,json,subprocess
from pathlib import Path
out=Path(__file__).parent
prefix='LVW_Prompt_Service_MasterPack_v2.0.0/'
candidate='cea5bf328ea35a5aa1d1feb51ac3ef8946a964fa';evidence='e0e54a4b889050de218d483a36532cec9127dd0a';authority='35f1ee4df74e3a6054e021ee9cbbd066eaba5490'
commands=[]
def git(label,*args):
 cmd=['git',*args];r=subprocess.run(cmd,capture_output=True)
 for ext,data in [('stdout.log',r.stdout),('stderr.log',r.stderr),('exit.log',str(r.returncode).encode()+b'\n')]: (out/(label+'.'+ext)).write_bytes(data)
 commands.append({'label':label,'argv':cmd,'exit_code':r.returncode})
 return r.stdout
checks={}
for a,b,label in [(authority,candidate,'authority-ancestry'),(candidate,evidence,'evidence-ancestry')]:git(label,'merge-base','--is-ancestor',a,b)
git('final-diff','diff',candidate,evidence,'--stat')
git('rebind-diff','show',evidence,'--',prefix+'reports/v0-s3/product-gate0/implementation-p3b')
git('candidate-change','show',candidate,'--',prefix+'tools/test_v0_s3_quality_phase.py')
git('status','status','--short')
impl=json.loads(Path('reports/v0-s3/product-gate0/implementation-p3b/receipt.json').read_text())
paths=dict(impl['source_files']);paths[impl['contract']]=impl['contract_sha256'];paths[impl['projection']]=impl['projection_sha256']
for n,(path,expected) in enumerate(paths.items()):
 raw=Path(path).read_bytes();h=hashlib.sha256(raw).hexdigest()
 blob=subprocess.check_output(['git','show',candidate+':'+prefix+path])
 checks[path]={'sha256':h,'bytes':len(raw),'receipt_matches':h==expected,'candidate_matches':blob==raw}
for path in [impl['contract'],impl['projection']]:
 blob=subprocess.check_output(['git','show',authority+':'+prefix+path]);checks[path]['authority_matches']=blob==Path(path).read_bytes()
logs={}
for label in ('combined-final','qd-directed','qs-directed'):
 p=Path('reports/v0-s3/product-gate0/implementation-p3b');r=json.loads((p/(label+'.receipt.json')).read_text());logs[label]={}
 for s in ('stdout','stderr'):
  b=(p/(label+'.'+s+'.log')).read_bytes();logs[label][s]={'hash_matches':hashlib.sha256(b).hexdigest()==r[s+'_sha256'],'bytes_match':len(b)==r[s+'_bytes'],'text':b.decode()}
 logs[label]['candidate_matches']=r['candidate_sha']==candidate
coordinate=json.loads(subprocess.check_output(['git','show','215c60f:'+prefix+'plans/execution-control.json']))
(out/'coordinate.json').write_text(json.dumps({k:v for k,v in coordinate.items() if k in ('stage_id','current_stage','state','current_workpack','development_outline','target_version')},ensure_ascii=False,indent=2)+'\n')
(out/'binding-results.json').write_text(json.dumps({'candidate':candidate,'evidence':evidence,'authority':authority,'files':checks,'implementation_streams':logs,'git_commands':commands},indent=2)+'\n')
print(json.dumps({'all_file_bindings_match':all(x['candidate_matches'] and x['receipt_matches'] for x in checks.values()),'file_count':len(checks),'git_audit_exit_codes':[x['exit_code'] for x in commands]},indent=2))
