from pathlib import Path
import sys,tempfile,shutil,threading,json,hashlib
from io import BytesIO
from PIL import Image,ImageChops,ImageStat
sys.path.insert(0,'/tmp/lvw-independent-87c64a3/LVW_Prompt_Service_MasterPack_v2.0.0/lvw/backend')
from app.video_kernel import VideoKernel
root=Path('/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0')
out=root/'reports/unified-media/independent-live-03';private=Path(tempfile.mkdtemp(prefix='lvw-live03-decode-'));media=private/'media';media.mkdir()
shutil.copyfile(root/'reports/v0-s2/fixture-preparation-02/fixtures/tracking.mov',media/'tracking.mov')
decoded=VideoKernel(media,private/'temp').decode(media/'tracking.mov',threading.Event());images=[]
for i,payload in enumerate(decoded.frames):
 im=Image.open(BytesIO(payload)).convert('RGB');im.save(out/f'frame-{i}.png');images.append(im)
montage=Image.new('RGB',(images[0].width*2,images[0].height*2))
for i,im in enumerate(images):montage.paste(im,((i%2)*im.width,(i//2)*im.height))
montage.save(out/'four-frames.png')
run=json.loads((root/'reports/unified-media/live-03/video-model-run.json').read_text())
checks={'source_sha256':decoded.source_sha256,'source_matches_run':decoded.source_sha256==run['input_sha256'],'frames':decoded.manifest,'frame_sha_match':[x['sha256']==y['sha256'] for x,y in zip(decoded.manifest,run['frames'])],'consecutive_pixel_differences':[{'different_bbox':ImageChops.difference(a,b).getbbox(),'mean_abs_RGB':ImageStat.Stat(ImageChops.difference(a,b)).mean} for a,b in zip(images,images[1:])],'temp_empty':not list((private/'temp').iterdir())}
(out/'independent-decoder-recompute.json').write_text(json.dumps(checks,indent=2)+'\n');print(json.dumps(checks,indent=2));shutil.rmtree(private)
