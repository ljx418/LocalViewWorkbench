import sys,socket,subprocess,os,json,hashlib,time,resource
from pathlib import Path
from io import BytesIO
def deny(*a,**k):raise AssertionError("forbidden external action")
socket.socket.connect=deny;socket.socket.connect_ex=deny;subprocess.Popen=deny
sys.path.insert(0,str(Path.cwd()/"lvw/backend"))
from PIL import Image
from app.provider import temporal_pixel_measurements
def ppm(im):
 out=BytesIO();im.save(out,format="PPM");return out.getvalue()
arrays=[[(i*31+j*17)%256 for j in range(18)] for i in range(4)]
frames=[ppm(Image.frombytes("RGB",(3,2),bytes(a))) for a in arrays]
expected=[]
for i,(a,b) in enumerate(zip(arrays,arrays[1:]),1):
 changed=sum(a[p:p+3]!=b[p:p+3] for p in range(0,18,3))
 expected.append(dict(from_frame=i,to_frame=i+1,different_pixel_fraction=round(changed/6,6),mean_absolute_rgb_delta=round(sum(abs(x-y) for x,y in zip(a,b))/18,6)))
actual=temporal_pixel_measurements(frames);assert actual==expected
large=[ppm(Image.new("RGB",(768,768),(x,x//2,255-x))) for x in [0,41,103,255]]
before=[hashlib.sha256(x).hexdigest() for x in large];start=time.monotonic();got=temporal_pixel_measurements(large);elapsed=time.monotonic()-start
assert before==[hashlib.sha256(x).hexdigest() for x in large];assert len(got)==3
print(json.dumps(dict(independent_byte_oracle=actual,expected=expected,bounded_frame_count=4,bounded_frame_size=[768,768],elapsed_seconds=elapsed,peak_process_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,source_bytes_unchanged=True,network_subprocess_forbidden=True),indent=2))
