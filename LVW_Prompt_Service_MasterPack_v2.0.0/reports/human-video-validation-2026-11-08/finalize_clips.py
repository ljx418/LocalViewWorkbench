from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent;ASSETS=ROOT/'人工验收视频集'
changes={'V04':(15,10),'V06':(20,6),'V07':(12,10),'V08':(20,10),'V09':(20,10)}
for id,(start,length) in changes.items():
 side=ASSETS/(id+'.source.json');v=json.loads(side.read_text());(OUT/(id+'-initial-selection.json')).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
 dest=ROOT/v['video_path'];poster=ROOT/v['poster']
 cmd=['ffmpeg','-y','-nostdin','-v','error','-threads','2','-ss',str(start),'-i',str(ROOT/v['original_path']),'-t',str(length),'-map','0:v:0','-an','-vf',"scale=w='trunc(min(960,iw)/2)*2':h=-2,fps=24",'-c:v','libx264','-threads','2','-preset','fast','-crf','22','-pix_fmt','yuv420p','-map_metadata','-1','-movflags','+faststart',str(dest)]
 subprocess.run(cmd,check=True,capture_output=True,timeout=45)
 subprocess.run(['ffmpeg','-y','-nostdin','-v','error','-i',str(dest),'-vf',('fps=1' if length==6 else 'fps=0.6')+',scale=320:-2,tile=3x2','-frames:v','1',str(poster)],check=True,capture_output=True,timeout=20)
 v.update(video_sha256=hashlib.sha256(dest.read_bytes()).hexdigest(),bytes=dest.stat().st_size,duration_seconds=float(json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(dest)]))['format']['duration']))
 v['transformation'].update(source_start_seconds=start,max_seconds=length)
 v['pre_freeze_selection_reason']='Remove title slates based on independent viewing before any LVW inference.' if id!='V06' else 'End excerpt before third-party SpaceX-credited shot; selected excerpt shows NASA material only.'
 side.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
items=[json.loads(p.read_text()) for p in sorted(ASSETS.glob('V*.source.json'))]
(ASSETS/'assets.json').write_text(json.dumps({'kind':'UNRUN_HUMAN_VALIDATION_ASSETS','lvw_model_calls':0,'items':items},ensure_ascii=False,indent=2)+'\n')
print('final clips',len(items))
