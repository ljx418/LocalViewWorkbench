"""Preserve native .NET UTF-8 BOM output; derive BOM-free JSON for the pack's strict JSON reader."""
from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
rows=[]
for rel in ['self-test.json','native-video.json','02/self-test.json','02/native-video.json']:
 p=root/rel;data=p.read_bytes();value=json.loads(data.decode('utf-8-sig'))
 raw=p.with_suffix('.native-utf8-bom.txt')
 with raw.open('xb') as f:f.write(data)
 p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
 rows.append({'derived_json':rel,'raw_native_output':str(raw.relative_to(root)),'raw_sha256':hashlib.sha256(data).hexdigest(),'derived_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'operation':'UTF-8 BOM removal and JSON indentation only; parsed values unchanged'})
(root/'json-normalization.json').write_text(json.dumps(rows,indent=2)+'\n')
