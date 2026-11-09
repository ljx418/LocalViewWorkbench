import asyncio,json,sys,hashlib
from pathlib import Path
from types import SimpleNamespace
R=Path.cwd();sys.path[:0]=[str(R/'lvw/backend'),str(R/'lvw/tests')]
from app.models import AnalyzeRequest
from app.service import AnalysisService
import app.service as service_module
from app.video_appearance import parse_appearance
from test_video_appearance import appearance_envelope
from app.video_temporal import measure_video_evidence
frames=[b'P6\n2 2\n255\n'+bytes([10,20,30])*4]*4
manifest=[{'time_seconds':1+2*i,'index':i+1,'pts':i,'time_base_num':1,'time_base_den':1,'sha256':hashlib.sha256(f).hexdigest()} for i,f in enumerate(frames)]
decoded=SimpleNamespace(frames=frames,manifest=manifest,source_sha256='a'*64,duration_seconds=8)
media=SimpleNamespace(kind='video',sha256='a'*64)
class Media:
    refs={'media_cpu':media}
    video=SimpleNamespace(decode=lambda path,cancel:decoded)
    def get(self,key):return media,Path('unused-synthetic')
wire=json.dumps(appearance_envelope(),ensure_ascii=False,indent=2)
class Provider:
    model='synthetic'
    async def analyze_video(self,decoded,**options):return wire,parse_appearance(json.loads(wire),mode=options['mode'],frame_times=[1,3,5,7])
# CPU composition validates evidence version. Inject only this internal failure, no model/network.
def rejected_policy(images,cancel):
    value=measure_video_evidence(images,cancel);value['policy_version']='rejected-policy';return value
service_module.measure_video_evidence=rejected_policy
async def main():
    owner=AnalysisService(Media(),Provider());request=AnalyzeRequest(media_ref_id='media_cpu',mode='realistic',config_profile='local-default');job=owner.submit(request,'cpu-raw-proof');await owner.run(job.id,request)
    actual=owner.get_job(job.id);run=owner.runs.get(actual.result_ref)
    result={'trigger':'composition rejects internal temporal policy after successful appearance response','expected':'failed run retains original raw response; parsed_spec absent','actual_status':actual.status,'actual_error':actual.error_code,'actual_result_ref':actual.result_ref,'actual_runs_count':len(owner.runs),'original_wire_sha256':hashlib.sha256(wire.encode()).hexdigest(),'actual_raw_preserved':run is not None and run.raw_response==wire,'model_network_service_actions':0}
    print(json.dumps(result,indent=2))
asyncio.run(main())
