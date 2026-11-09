import socket,subprocess,sys,json,hashlib
from pathlib import Path
from io import BytesIO
from decimal import Decimal,ROUND_HALF_EVEN
def deny(*a,**k):raise AssertionError("forbidden external action")
socket.socket.connect=deny;socket.socket.connect_ex=deny;subprocess.Popen=deny
sys.path.insert(0,str(Path.cwd()/"lvw/backend"))
from PIL import Image
from app.provider import temporal_pixel_measurements,VIDEO_TASK
def encode(im):
 out=BytesIO();im.save(out,format="PPM");return out.getvalue()
rows=[]
for width,height,changed,expected_percent in [(2,2,0,0),(2,2,1,25),(3,1,1,33.3333),(700,700,168497,34.3871),(768,768,589824,100)]:
 total=width*height
 first=encode(Image.new("RGB",(width,height),"black"))
 second=encode(Image.frombytes("RGB",(width,height),bytes([12,24,36])*changed+bytes((total-changed)*3)))
 before=[hashlib.sha256(x).hexdigest() for x in [first,second]]
 value=temporal_pixel_measurements([first,second])[0]
 percent=float((Decimal(changed)*100/Decimal(total)).quantize(Decimal(".0001"),rounding=ROUND_HALF_EVEN))
 expected=dict(from_frame=1,to_frame=2,changed_pixel_count=changed,frame_pixel_count=total,different_pixel_percent=expected_percent,mean_absolute_rgb_delta=round(24*changed/total,6))
 assert percent==expected_percent and value==expected,(value,expected)
 assert before==[hashlib.sha256(x).hexdigest() for x in [first,second]]
 assert "different_pixel_fraction" not in value
 rows.append(dict(total_pixels=total,changed_pixels=changed,exact_percent_decimal=str(Decimal(changed)*100/Decimal(total)),metadata=value))
assert "already in percent units (0 to 100); do NOT divide it by 100 again" in VIDEO_TASK
print(json.dumps(dict(result="PASS",rounding="4 decimal percent places; exact counts retained",cases=rows,source_payloads_unchanged=True,network_subprocess_forbidden=True),indent=2))
