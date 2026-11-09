from pathlib import Path
import subprocess,tempfile,json,hashlib,types,shutil
from unittest.mock import patch
source=Path('/tmp/lvw-runtime-review-1d1db/authority.py').read_text();scope=json.loads(Path('/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/unified-media/independent-runtime-transition-01/source-fence-scope-1d1db.json').read_text());frozen_paths=scope['frozen_paths'];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
class ReachedAllocation(Exception):pass
for case,path,committed in [('dirty_system_template','templates/analysis_system_zh.txt',False),('committed_video_kernel','LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/core.py',True)]:
 root=Path(tempfile.mkdtemp(prefix='lvw-fence-git-'));folder=root/'reports/unified-media';folder.mkdir(parents=True);packet=root/'.agent-governance/stages/R1';packet.mkdir(parents=True)
 def git(*args):return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.DEVNULL).decode().strip()
 git('init','-q');git('config','user.email','cpu-review@example.invalid');git('config','user.name','CPU Review')
 (root/'reports/authorization-program-v1-local-01.json').write_text(json.dumps({'status':'ACTIVE','stages':['R1']}));(folder/'approval.json').write_text(json.dumps({'decision':'APPROVED'}))
 for i in range(4):
  run=folder/f'live-{i+1:02}';run.mkdir();(run/'authorization.json').write_text('{}');(run/'receipt.json').write_text(json.dumps({'stage_checkpoint_consumed':i!=0}))
 leaf=packet/'scope.md';leaf.write_text('approved');manifest=packet/'PAYLOAD_MANIFEST.sha256';manifest.write_text(sha(leaf)+'  scope.md\n');harness=folder/'live_checkpoint.py';harness.write_text('INERT CPU fixture; never executed')
 changed=root/path;changed.parent.mkdir(parents=True);changed.write_text('baseline tracked production input\n');git('add','.');git('commit','-qm','CPU baseline');baseline=git('rev-parse','HEAD')
 req={'authorization_id':'CPU_SYNTHETIC_GRANT_NOT_REAL_AUTH','run_id':'live-05','max_full_rechecks':1,'budget':{'model_calls':0},'max_seconds':30,'port':18780,'samples':[],'harness_sha256':sha(harness),'proposed_packet_manifest_sha256':sha(manifest),'candidate_sha':baseline,'frozen_paths':frozen_paths};request=folder/'authorization-runtime-transition-01.request.json';request.write_text(json.dumps(req));grant=folder/'authorization-runtime-transition-01.approval.json';grant.write_text(json.dumps({'decision':'APPROVED','request_sha256':sha(request),'authorization_id':req['authorization_id']}))
 changed.write_text('changed tracked production input\n')
 if committed:git('add',path);git('commit','-qm','CPU production-input drift')
 diff=git('diff','--name-only',baseline,'HEAD') if committed else git('diff','--name-only')
 frozen_return=subprocess.run(['git','-C',str(root),'diff','--quiet',baseline,'HEAD','--',*frozen_paths]).returncode
 module=types.ModuleType('authority_fence_review');module.__file__='/tmp/review/reports/unified-media/authority.py';exec(compile(source,'exact_1d1db_authority.py','exec'),module.__dict__);module.ROOT=root;allocation=[False];out=folder/'live-05';original_mkdir=Path.mkdir
 def prevent_allocate(self,*args,**kwargs):
  if self==out:allocation[0]=True;raise ReachedAllocation('allocation reached for drifted production input')
  return original_mkdir(self,*args,**kwargs)
 with patch.object(Path,'mkdir',prevent_allocate):
  try:module.create('live-05',harness,req['budget'],port=18780,seconds=30,full=True);result='UNEXPECTED_RETURN'
  except Exception as error:result=type(error).__name__+': '+str(error)
 print(json.dumps({'case':case,'changed_file':path,'actual_git_diff_detects':diff.splitlines(),'frozen_diff_returncode':frozen_return,'authority_reached_allocation':allocation[0],'result':result,'new_run_directory_created':out.exists(),'model_calls':0,'services':0,'browser_starts':0,'media_probes':0}))
 shutil.rmtree(root)
