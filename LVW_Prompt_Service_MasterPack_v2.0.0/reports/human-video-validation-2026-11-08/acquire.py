from pathlib import Path
import concurrent.futures,hashlib,html,json,re,requests,subprocess,urllib.parse
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;ASSETS=ROOT/'人工验收视频集'
rows=json.loads((OUT/'candidates.json').read_text())+json.loads((OUT/'candidates-extra.json').read_text())
choices=[('nature','Ocean surface waves 06',0),('timelapse','Moving clouds timelapse',0),('macro','Butterfly-1026790',0),('wildlife','Mallards pond',0),('city','File:City at night.webm',0),('sport','Skateboarding - 0022',0),('underwater','Underwater Videos 5',0),('space2','Galileo flyby (PIA00114).webm',0),('animation2','Куб 1280-720',0),('science2','s007.ogv',0),('fire2','srep36145-s4.ogv',0),('archive2','Arrival of a Train at La Ciotat (The Lumière Brothers, 1895)',12)]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
clean=lambda s:html.unescape(re.sub('<[^>]+>',' ',s)).strip()
def one(task):
 index,(group,title,start)=task;row=next(x for x in rows if x['id']==group and title in x['title'] and x['eligible']);i=row['info'];meta=i['extmetadata'];id='V%02d'%index
 url=i['url'].split('?')[0];assert urllib.parse.urlparse(url).hostname=='upload.wikimedia.org'
 original=ASSETS/'originals'/(id+Path(urllib.parse.urlparse(url).path).suffix)
 with requests.get(url,stream=True,headers={'User-Agent':'LVWValidationAssets/1.0 (local evaluation)'},timeout=(15,50)) as response:
  response.raise_for_status();assert urllib.parse.urlparse(response.url).hostname=='upload.wikimedia.org';total=0
  with original.open('xb') as f:
   for chunk in response.iter_content(1024*1024):
    total+=len(chunk)
    if total>50000000:raise ValueError('source byte budget exceeded')
    f.write(chunk)
 assert original.stat().st_size==i['size'],(id,'source size mismatch')
 video=ASSETS/'videos'/(id+'.mp4');poster=ASSETS/'posters'/(id+'.jpg')
 cmd=['ffmpeg','-nostdin','-v','error','-threads','2','-ss',str(start),'-i',str(original),'-t','10','-map','0:v:0','-an','-vf',"scale=w='trunc(min(960,iw)/2)*2':h=-2,fps=24",'-c:v','libx264','-threads','2','-preset','fast','-crf','22','-pix_fmt','yuv420p','-map_metadata','-1','-movflags','+faststart',str(video)]
 p=subprocess.run(cmd,capture_output=True,timeout=70)
 (OUT/(id+'-transcode.stderr.log')).write_bytes(p.stderr);assert p.returncode==0
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(video)]));vs=next(s for s in probe['streams'] if s['codec_type']=='video');duration=float(probe['format']['duration']);assert 4<=duration<=12 and vs['width']*vs['height']<=8294400 and video.stat().st_size<256*1024**2
 p=subprocess.run(['ffmpeg','-nostdin','-v','error','-threads','2','-i',str(video),'-vf','fps=0.6,scale=320:-2,tile=3x2','-frames:v','1',str(poster)],capture_output=True,timeout=30);assert p.returncode==0
 # Full decode, not just a header probe.
 p=subprocess.run(['ffmpeg','-nostdin','-v','error','-threads','2','-i',str(video),'-map','0:v:0','-f','null','-'],capture_output=True,timeout=40);assert p.returncode==0
 item={'id':id,'style':row['style'],'title':row['title'],'source_url':i['descriptionurl'],'download_url':url,'creator':clean(meta.get('Artist',{}).get('value','')),'license':row['license'],'license_url':meta.get('LicenseUrl',{}).get('value',''),'attribution_required':meta.get('AttributionRequired',{}).get('value',''),'original_path':str(original.relative_to(ROOT)),'original_sha256':sha(original),'original_bytes':original.stat().st_size,'video_path':str(video.relative_to(ROOT)),'video_sha256':sha(video),'bytes':video.stat().st_size,'duration_seconds':duration,'width':vs['width'],'height':vs['height'],'codec':vs['codec_name'],'poster':str(poster.relative_to(ROOT)),'transformation':{'source_start_seconds':start,'max_seconds':10,'audio_removed':True,'scaling':'width<=960, aspect preserved','fps':24},'full_decode_exit_code':p.returncode,'lvw_analysis_status':'NOT_RUN','expected_observation_status':'PENDING_INDEPENDENT_VISUAL_INSPECTION','metadata':meta}
 (ASSETS/(id+'.source.json')).write_text(json.dumps(item,ensure_ascii=False,indent=2)+'\n');print(id,row['style'],row['title'],duration,flush=True);return item
all=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for item in pool.map(one,enumerate(choices,1)):all.append(item)
(ASSETS/'assets.json').write_text(json.dumps({'kind':'UNRUN_HUMAN_VALIDATION_ASSETS','lvw_model_calls':0,'items':all},ensure_ascii=False,indent=2)+'\n')
