"""Run exact candidate statistics AST on synthetic in-memory pixel arrays; no image/media decode."""
import ast,json,subprocess,statistics
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
CANDIDATE='8d43c1dcb79cedd16ce5143c8f68887de38e6572'
prefix=subprocess.check_output(['git','rev-parse','--show-prefix'],cwd=ROOT,text=True).strip()
source=subprocess.check_output(['git','show',CANDIDATE+':'+prefix+'lvw/backend/app/provider.py'],cwd=ROOT,text=True)
node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='temporal_pixel_measurements')
class Plane:
 def __init__(self,data):self.data=data
 def histogram(self):return [self.data.count(n) for n in range(256)]
class PixelImage:
 def __init__(self,data):self.data=data;self.width=len(data);self.height=1;self.size=(self.width,1)
 def __enter__(self):return self
 def __exit__(self,*_):pass
 def convert(self,_):return self
 def split(self):return [Plane([p[n] for p in self.data]) for n in range(3)]
class Image:
 @staticmethod
 def open(payload):return PixelImage(payload)
class Chops:
 @staticmethod
 def difference(a,b):return PixelImage([tuple(abs(x-y) for x,y in zip(p,q)) for p,q in zip(a.data,b.data)])
 @staticmethod
 def lighter(a,b):return Plane([max(x,y) for x,y in zip(a.data,b.data)])
class Stat:
 def __init__(self,img):self.mean=[statistics.mean(p[n] for p in img.data) for n in range(3)]
ns={'Image':Image,'ImageChops':Chops,'ImageStat':type('Stats',(),{'Stat':Stat}),'BytesIO':lambda v:v,'AppError':RuntimeError}
exec(compile(ast.Module(body=[node],type_ignores=[]),'candidate-statistics-ast','exec'),ns)
black=[(0,0,0)]*4
cases=[('identical',black,black,0,0),('one_pixel_one_channel',black,[(255,0,0)]+black[1:],.25,21.25),('one_third_pixels',[(0,0,0)]*3,[(255,255,255),(0,0,0),(0,0,0)],round(1/3,6),85),('all_pixels',black,[(255,255,255)]*4,1,255)]
results=[]
for name,a,b,f,m in cases:
 actual=ns['temporal_pixel_measurements']([a,b])[0]
 assert actual['different_pixel_fraction']==f and actual['mean_absolute_rgb_delta']==m
 results.append({'case':name,'actual':actual,'independent_expected_fraction':f,'independent_expected_mean':m})
(OUT/'pixel-math-results.json').write_text(json.dumps({'candidate':CANDIDATE,'method':'Exact candidate function AST, isolated fake pixel primitives; no PIL, source frame, model, FFmpeg or service execution','results':results},indent=2)+'\n')
print('PASS: four independent synthetic fraction/mean oracles')
