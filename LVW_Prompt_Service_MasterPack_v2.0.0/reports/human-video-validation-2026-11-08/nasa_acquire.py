from pathlib import Path
import concurrent.futures,hashlib,json,requests,subprocess,urllib.parse
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;ASSETS=ROOT/'人工验收视频集';rows=json.loads((OUT/'nasa-candidates.json').read_text())
choices=[('clouds',0),('forest',0),('ocean',0),('wildlife',0),('helicopter',2),('rocket',2),('night',0),('simulation',2),('fluid',0),('moon',1),('earth',0)]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(task):
 index,(query,which)=task;item=[x for x in rows if x['query']==query][which]['item'];data=item['data'][0];id='V%02d'%index
 assert 'courtesy of' not in data.get('description','').lower()
 r=requests.get(item['href'],timeout=25);r.raise_for_status();collection=r.json();(OUT/(id+'-nasa-collection.json')).write_text(json.dumps(collection,indent=2)+'\n')
 urls=[u.replace('http://','https://',1) for u in collection if '~preview.mp4' in u or '~small.mp4' in u]
 assert urls
 url=next((u for u in urls if '~preview.mp4' in u),urls[0]);assert urllib.parse.urlparse(url).hostname=='images-assets.nasa.gov'
 original=ASSETS/'originals'/(id+'.mp4')
 with requests.get(url,stream=True,timeout=(15,30)) as response:
  response.raise_for_status();total=0
  with original.open('xb') as f:
   for chunk in response.iter_content(256*1024):
    total+=len(chunk)
    if total>50000000:raise ValueError('source cap exceeded')
    f.write(chunk)
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(original)]));duration=float(probe['format']['duration']);start=0 if query in ['wildlife','helicopter','night','fluid','simulation','moon'] else min(20,max(0,duration/4))
 video=ASSETS/'videos'/(id+'.mp4');poster=ASSETS/'posters'/(id+'.jpg')
 cmd=['ffmpeg','-nostdin','-v','error','-threads','2','-ss',str(start),'-i',str(original),'-t','10','-map','0:v:0','-an','-vf',"scale=w='trunc(min(960,iw)/2)*2':h=-2,fps=24",'-c:v','libx264','-threads','2','-preset','fast','-crf','22','-pix_fmt','yuv420p','-map_metadata','-1','-movflags','+faststart',str(video)]
 p=subprocess.run(cmd,capture_output=True,timeout=60);(OUT/(id+'-transcode.stderr.log')).write_bytes(p.stderr);assert p.returncode==0
 probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-show_streams','-of','json',str(video)]));v=next(x for x in probe['streams'] if x['codec_type']=='video');duration=float(probe['format']['duration']);assert 4<=duration<=12 and v['width']*v['height']<=8294400 and video.stat().st_size<256*1024**2
 p=subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(video),'-vf','fps=0.6,scale=320:-2,tile=3x2','-frames:v','1',str(poster)],capture_output=True,timeout=25);assert p.returncode==0
 p=subprocess.run(['ffmpeg','-nostdin','-v','error','-threads','2','-i',str(video),'-f','null','-'],capture_output=True,timeout=30);assert p.returncode==0
 result={'id':id,'query':query,'style':'PENDING_VISUAL_LABEL','title':data['title'],'source_url':'https://images.nasa.gov/details/'+urllib.parse.quote(data['nasa_id'],safe=''),'download_url':url,'creator':'NASA / '+data.get('center',''),'license':'NASA media usage guidelines: educational/informational use; no endorsement','license_url':'https://www.nasa.gov/nasa-brand-center/images-and-media/','original_path':str(original.relative_to(ROOT)),'original_sha256':sha(original),'original_bytes':original.stat().st_size,'downloaded_rendition':'NASA official preview; not full-resolution original','video_path':str(video.relative_to(ROOT)),'video_sha256':sha(video),'bytes':video.stat().st_size,'duration_seconds':duration,'width':v['width'],'height':v['height'],'codec':v['codec_name'],'poster':str(poster.relative_to(ROOT)),'transformation':{'source_start_seconds':start,'max_seconds':10,'audio_removed':True,'fps':24,'aspect_preserved':True},'full_decode_exit_code':0,'lvw_analysis_status':'NOT_RUN','metadata':data,'expected_observation_status':'PENDING_VISUAL_INSPECTION'}
 (ASSETS/(id+'.source.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(id,query,data['title'],duration,video.stat().st_size,flush=True);return result
all=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 for result in pool.map(one,enumerate(choices,1)):all.append(result)
(ASSETS/'assets.json').write_text(json.dumps({'kind':'UNRUN_HUMAN_VALIDATION_ASSETS','lvw_model_calls':0,'items':all},ensure_ascii=False,indent=2)+'\n')
