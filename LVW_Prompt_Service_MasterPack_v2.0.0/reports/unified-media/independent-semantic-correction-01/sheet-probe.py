from pathlib import Path
from io import BytesIO
import asyncio,hashlib,json,tempfile
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image,ImageDraw
import httpx
from app.provider import OllamaProvider,build_temporal_sheet,VIDEO_PRESENTATION_VERSION
root=Path(tempfile.mkdtemp(prefix='lvw-sheet-review-'));frames=[]
for color,size in [('red',(800,200)),('green',(200,800)),('blue',(800,600)),('yellow',(600,800))]:
 im=Image.new('RGB',size,color);draw=ImageDraw.Draw(im);draw.rectangle((0,0,15,15),fill='white');draw.rectangle((size[0]-16,size[1]-16,size[0]-1,size[1]-1),fill='black');b=BytesIO();im.save(b,format='PPM');frames.append(b.getvalue())
times=[.125,1.5,3.25,7.875];decoded=SimpleNamespace(frames=frames,manifest=[{'time_seconds':t,'sha256':hashlib.sha256(f).hexdigest()} for t,f in zip(times,frames)])
sheet=build_temporal_sheet(decoded);Image.open(BytesIO(sheet)).save(root/'synthetic-sheet.png');captured=[]
content={'observations':['REVIEW_RESPONSE_SENTINEL'],'inferences':[],'unknowns':[],'prompt_zh':'测试','prompt':'Test','negative':'none','tags':[],'camera_motion':'unknown','subject_action':'unknown'}
real=httpx.AsyncClient
async def handler(request):
 captured.append(json.loads(request.content));return httpx.Response(200,json={'model':'gemma4:26b','done':True,'done_reason':'stop','message':{'content':json.dumps(content)}})
async def scenario():
 p=OllamaProvider('http://127.0.0.1:11434/api/chat','gemma4:26b',10,ledger_path=root/'ledger.jsonl')
 with patch('app.provider.httpx.AsyncClient',lambda **kw:real(**kw,transport=httpx.MockTransport(handler))):await p.analyze_video(decoded,mode='realistic')
asyncio.run(scenario())
ledger=[json.loads(x) for x in (root/'ledger.jsonl').read_text().splitlines()];start=ledger[0];wire=captured[0]
report={'presentation':VIDEO_PRESENTATION_VERSION,'sheet_size':Image.open(BytesIO(sheet)).size,'wire_images':len(wire['messages'][-1]['images']),'frame_count_recorded':start['frame_count'],'payload_count_recorded':start['payload_image_count'],'source_frame_hashes_match':start['source_frame_hashes']==[hashlib.sha256(x).hexdigest() for x in frames],'payload_sha_matches_sheet':start['input_sha256']==hashlib.sha256(sheet).hexdigest(),'actual_times_in_prompt':json.dumps(times) in wire['messages'][-1]['content'],'panel_count_in_prompt':'Actual populated panel count: 4' in wire['messages'][-1]['content'],'no_single_image_task_conflict':'Analyze the attached single image' not in wire['messages'][-1]['content'],'no_response_oracle_leak':'REVIEW_RESPONSE_SENTINEL' not in json.dumps(wire),'options':wire['options'],'synthetic_panel_colors_match':[Image.open(BytesIO(sheet)).getpixel(point)==color for point,color in zip([(192,206),(576,206),(192,590),(576,590)],[(255,0,0),(0,128,0),(0,0,255),(255,255,0)])],'crop_policy_from_source_inspection':'thumbnail and paste only; no crop operation','temporary_output':str(root),'request_content':wire['messages'][-1]['content']}
print(json.dumps(report,indent=2));destination=Path('/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/unified-media/independent-semantic-correction-01');(destination/'synthetic-sheet.png').write_bytes(sheet)
import shutil;shutil.rmtree(root)
