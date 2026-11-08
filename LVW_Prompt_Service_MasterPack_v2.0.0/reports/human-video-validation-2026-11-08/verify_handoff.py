from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote,urlparse
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;ASSETS=ROOT/'人工验收视频集';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
a=json.loads((ASSETS/'assets.json').read_text());f=json.loads((ASSETS/'FREEZE.json').read_text());e=json.loads((ASSETS/'expected-results.frozen.json').read_text());h=json.loads((OUT/'history.json').read_text());assert len(a['items'])>=10
assert sha(ASSETS/'assets.json')==f['assets_manifest_sha256'];assert sha(ASSETS/'expected-results.frozen.json')==f['expected_sha256'];assert a['lvw_model_calls']==e['lvw_model_calls']==0
for x in a['items']:
 assert sha(ROOT/x['video_path'])==x['video_sha256'];assert (ROOT/x['poster']).exists();assert x['lvw_analysis_status']=='NOT_RUN';assert x['bytes']<256*1024**2 and 0<x['duration_seconds']<=60 and x['width']*x['height']<=8294400;assert x['full_decode_exit_code']==0
 assert (ROOT/x['original_path']).stat().st_size==x['original_bytes'];assert sha(ROOT/x['original_path'])==x['original_sha256']
 assert next(y for y in e['items'] if y['id']==x['id'])['video_sha256']==x['video_sha256']
with zipfile.ZipFile(ASSETS/'人工验证视频_11段.zip') as z:
 assert z.testzip() is None
 assert len([x for x in z.namelist() if x.endswith('.mp4')])==11
 for x in a['items']:assert hashlib.sha256(z.read('videos/'+x['id']+'.mp4')).hexdigest()==x['video_sha256']
for x in h['source_copies']:assert sha(OUT/'historical'/x['file'])==x['sha256']
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[];self.ids=set()
 def handle_starttag(self,tag,attrs):
  d=dict(attrs)
  if 'id' in d:self.ids.add(d['id'])
  for k in ['href','src','poster']:
   if k in d:self.links.append(d[k])
p=Links();p.feed((ROOT/'验收报告与盲测视频.html').read_text());local=0
for link in p.links:
 if link.startswith('#'):assert link[1:] in p.ids
 elif not urlparse(link).scheme:assert (ROOT/unquote(link.split('#')[0])).exists(),link;local+=1
u=json.loads((OUT/'ui-receipt.json').read_text());assert len(u['checks'])==10 and not u['page_errors'] and not u['network_requests'] and u['owned_browser_terminal'] and u['owned_temp_removed'];play=json.loads((OUT/'playback-receipt.json').read_text());assert len(play['checks'])==15 and play['owned_temp_removed'];control=json.loads((ROOT/'plans/execution-control.json').read_text());assert control['human_signoff'] is None and control['coordinate']['state']=='WAIT_HUMAN'
result={'kind':'HUMAN_VALIDATION_REPORT_HANDOFF_NOT_STAGE_ACCEPTANCE','decision':'HANDOFF_CHECKS_PASSED','historical_video_count':4,'verified_historical_source_copies':len(h['source_copies']),'local_html_links':local,'downloaded_holdout_count':len(a['items']),'holdout_lvw_status':'ALL_NOT_RUN','new_lvw_model_calls':0,'ui_checks':10,'local_browser_playbacks':15,'zip_bytes':(ASSETS/'人工验证视频_11段.zip').stat().st_size,'zip_sha256':sha(ASSETS/'人工验证视频_11段.zip'),'html_sha256':sha(ROOT/'验收报告与盲测视频.html'),'expected_sha256':f['expected_sha256'],'formal_stage_denominator_changed':False,'human_signoff':None,'stage_pass_claim':False}
(OUT/'handoff-receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
