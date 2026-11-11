import json,tarfile,hashlib
from pathlib import Path,PurePosixPath
O=Path(__file__).resolve().parent;I=O.parent/'implementation-p2-binding-correction-04'
rows=[]
for a in sorted(I.glob('*.tar.gz')):
 with tarfile.open(a) as t:
  for m in t.getmembers():
   if not m.name.endswith('/cross-os-lifecycle.json'):continue
   base=PurePosixPath(m.name).parent
   raw=t.extractfile(m).read();v=json.loads(raw)
   for ref in v['artifact_refs']:
    p=PurePosixPath(ref['path']);assert not p.is_absolute() and '..' not in p.parts
    member=t.getmember(str(base/p));assert member.isfile() and member.size==ref['bytes']<=1048576
    assert hashlib.sha256(t.extractfile(member).read()).hexdigest()==ref['sha256']
   c=json.loads(t.extractfile(str(base/'consumed.json')).read());assert c['status']=='EXPIRED' and c['terminal_sha256']==hashlib.sha256(raw).hexdigest()
   assert len(raw)<=16384
   rows.append(dict(archive=a.name,terminal=m.name,refs=len(v['artifact_refs']),status=v['status']))
(O/'archive-refs.json').write_text(json.dumps(dict(verified_terminal_records=len(rows),not_test_case_count=True,records=rows),indent=2)+'\n')
print(json.dumps({'verified_archived_terminals':len(rows),'not_test_cases':True}))
