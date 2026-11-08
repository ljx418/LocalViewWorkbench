from pathlib import Path
from unittest.mock import patch
import types,tempfile,json,hashlib,shutil
source=Path('/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/unified-media/authority.py').read_text();digest=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for case in ['missing_approval','request_hash','sample_hash','harness_hash','packet_manifest','packet_leaf_bytes','packet_extra_file','ancestor','frozen_diff']:
 root=Path(tempfile.mkdtemp(prefix='lvw-authority-negative-'));folder=root/'reports/unified-media';folder.mkdir(parents=True);packet=root/'.agent-governance/stages/R1';packet.mkdir(parents=True)
 (root/'reports/authorization-program-v1-local-01.json').write_text(json.dumps({'status':'ACTIVE','stages':['R1']}));(folder/'approval.json').write_text(json.dumps({'decision':'APPROVED'}))
 for i in range(3):
  run=folder/f'live-{i+1:02}';run.mkdir();(run/'authorization.json').write_text('{}');(run/'receipt.json').write_text(json.dumps({'stage_checkpoint_consumed':i!=0}))
 leaf=packet/'scope.md';leaf.write_text('approved content');manifest=packet/'PAYLOAD_MANIFEST.sha256';manifest.write_text(digest(leaf)+'  scope.md\n')
 harness=root/'harness.py';harness.write_text('inert CPU fixture');sample=root/'sample.bin';sample.write_bytes(b'not media')
 request={'authorization_id':'CPU_FAKE_GRANT_NOT_REAL_AUTH','run_id':'live-04','max_full_rechecks':1,'budget':{'model_calls':0},'max_seconds':30,'port':18780,'samples':[{'path':'sample.bin','sha256':digest(sample)}],'harness_sha256':digest(harness),'proposed_packet_manifest_sha256':digest(manifest),'candidate_sha':'CPU_BASE','frozen_paths':['lvw/backend']}
 if case=='sample_hash':request['samples'][0]['sha256']='0'*64
 if case=='harness_hash':request['harness_sha256']='0'*64
 if case=='packet_manifest':request['proposed_packet_manifest_sha256']='0'*64
 req=folder/'authorization-semantic-correction-01.request.json';req.write_text(json.dumps(request));grant=folder/'authorization-semantic-correction-01.approval.json';grant.write_text(json.dumps({'decision':'APPROVED','request_sha256':('0'*64 if case=='request_hash' else digest(req)),'authorization_id':request['authorization_id']}))
 if case=='missing_approval':grant.unlink()
 if case=='packet_leaf_bytes':leaf.write_text('tampered content')
 if case=='packet_extra_file':(packet/'unapproved.md').write_text('extra')
 module=types.ModuleType('authority_review');module.__file__='/tmp/review/reports/unified-media/authority.py';exec(compile(source,'candidate_authority.py','exec'),module.__dict__);module.ROOT=root
 def run(argv,**kwargs):return types.SimpleNamespace(returncode=1 if (case=='ancestor' and 'merge-base' in argv) or (case=='frozen_diff' and '--quiet' in argv) else 0)
 with patch.object(module.subprocess,'check_output',return_value='CPU_HEAD'),patch.object(module.subprocess,'run',side_effect=run):
  try:module.create('live-04',harness,request['budget'],port=18780,samples=[sample],seconds=30,full=True);outcome='UNEXPECTED_ALLOW'
  except Exception as e:outcome=type(e).__name__+': '+str(e)
 print(json.dumps({'case':case,'rejected':outcome!='UNEXPECTED_ALLOW','outcome':outcome,'live04_directory_created':(folder/'live-04').exists(),'external_commands':0,'services':0,'model_calls':0}))
 shutil.rmtree(root)
