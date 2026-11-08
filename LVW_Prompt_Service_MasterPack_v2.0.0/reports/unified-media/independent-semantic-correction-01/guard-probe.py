import tempfile,json,types,shutil
from pathlib import Path
from unittest.mock import patch
source=Path('/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/unified-media/authority.py').read_text()
module=types.ModuleType('review_authority');module.__file__='/tmp/review/reports/unified-media/authority.py';exec(compile(source,'candidate_authority.py','exec'),module.__dict__)
for count in [3,0]:
 root=Path(tempfile.mkdtemp(prefix='lvw-guard-review-'));folder=root/'reports/unified-media';folder.mkdir(parents=True)
 (root/'reports/authorization-program-v1-local-01.json').write_text(json.dumps({'status':'ACTIVE','stages':['R1']}));(folder/'approval.json').write_text(json.dumps({'decision':'APPROVED'}))
 for i in range(count):
  run=folder/f'live-{i+1:02}';run.mkdir();(run/'authorization.json').write_text('{}');(run/'receipt.json').write_text(json.dumps({'stage_checkpoint_consumed':i!=0}))
 packet=root/'.agent-governance/stages/R1/PAYLOAD_MANIFEST.sha256';packet.parent.mkdir(parents=True);packet.write_text('dummy packet manifest')
 harness=root/'dummy.py';harness.write_text('no execution');module.ROOT=root
 with patch.object(module.subprocess,'check_output',return_value='ad4265cb657f5a0c1837ac236a7d9a7c6b4c726a'),patch.object(module.subprocess,'run',return_value=types.SimpleNamespace(returncode=0)):
  try:module.create('live-04',harness,{'model_calls':0},port=18780,seconds=30,full=True);error='UNEXPECTED_ALLOW'
  except Exception as e:error=type(e).__name__+': '+str(e)
 print(json.dumps({'existing_live_slots':count,'approval_present':False,'outcome':error,'live04_directory_created':(folder/'live-04').exists(),'services_started':0,'model_calls':0}))
 shutil.rmtree(root)
