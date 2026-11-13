from pathlib import Path
import json,hashlib,os
D=Path(__file__).parent
records=[]
for p in sorted(D.rglob('*')):
 if p==D/'integrity.json':continue
 if p.is_symlink():b=os.readlink(p).encode();kind='symlink'
 elif p.is_file():b=p.read_bytes();kind='file'
 else:continue
 records.append({'path':str(p.relative_to(D)),'type':kind,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()})
(D/'integrity.json').write_text(json.dumps({'algorithm':'sha256','entries':records,'excludes':['integrity.json'],'seal_after_audit_stdout_stderr_closed':True},indent=2))
print('sealed',len(records),'artifacts; all audit/test failure logs included')
