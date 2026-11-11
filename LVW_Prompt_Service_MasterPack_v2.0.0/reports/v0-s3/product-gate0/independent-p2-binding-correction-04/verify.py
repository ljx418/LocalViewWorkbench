import base64, hashlib, json, tarfile, shutil
from pathlib import Path, PurePosixPath
O=Path(__file__).resolve().parent
I=O.parent/'implementation-p2-binding-correction-04'
def sha(b):return hashlib.sha256(b).hexdigest()
def save(n,v):(O/n).write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
archives=[]
for index in json.loads((I/'archives.json').read_bytes()):
 p=I/index['path'];assert sha(p.read_bytes())==index['sha256'] and p.stat().st_size==index['bytes']
 expected={e['path']:e for e in index['entries']};seen=[];size=0;sql=[];source=[]
 with tarfile.open(p,'r:gz') as t:
  for e in t:
   path=PurePosixPath(e.name);assert not path.is_absolute() and '..' not in path.parts and not e.issym() and not e.islnk()
   if e.isdir():continue
   assert e.isfile() and e.size<4*1048576
   size+=e.size;assert size<128*1048576
   data=t.extractfile(e).read(e.size+1);assert len(data)==e.size
   x=expected[e.name];assert e.size==x['bytes'] and sha(data)==x['sha256'];seen.append(e.name)
   if data.startswith(b'SQLite format 3\x00'):sql.append(e.name)
   if e.name.endswith('.py'):source.append(e.name)
 assert set(seen)==set(expected)
 archives.append(dict(path=p.name,bytes=p.stat().st_size,uncompressed_bytes=size,entries=len(seen),sqlite=sql,source_snapshots=source,hashes_match=True,no_extraction=True))
save('archive-review.json',archives)
results=[]
for p in sorted((O/'combined-raw').glob('public-*/cross-os-lifecycle.json')):
 t=json.loads(p.read_bytes());b=p.parent;commands=[];samples=[];refs=[]
 for r in t['artifact_refs']:
  q=b/r['path'];assert not q.is_symlink() and q.resolve().is_relative_to(b.resolve())
  data=q.read_bytes();assert len(data)==r['bytes']<=1048576 and sha(data)==r['sha256'];refs.append(r)
  if r['kind']=='command':
   c=json.loads(data)
   if 'stdout_base64' in c:
    streams=[base64.b64decode(c[k],validate=True) for k in ('stdout_base64','stderr_base64')]
    assert list(map(len,streams))==c['stream_bytes'] and [sha(s) for s in streams]==c['stream_sha256']
    commands.append(dict(bytes=c['stream_bytes'],raw_complete=c['raw_complete'],error=c.get('error')))
  if r['kind']=='observer':samples.append(json.loads(data)['sample_count'])
 c=json.loads((b/'consumed.json').read_bytes());assert c['status']=='EXPIRED' and c['terminal_sha256']==sha(p.read_bytes())
 actual=sum(x['bytes'] for x in refs);assert actual==t['detail_actual_bytes']<=8388608
 assert p.stat().st_size<=16384 and t['counters']['output_bytes']<=16777216
 suffix=b.name.removeprefix('public-');factories=list((O/'combined-raw').glob('factory-'+suffix+'-*'))
 factory_bytes=sum(q.stat().st_size for f in factories for q in f.rglob('*') if q.is_file())
 if not factories and (O/'fixture-cleanup.json').exists():
  factory_bytes=sum(e['bytes'] for f in json.loads((O/'fixture-cleanup.json').read_bytes())['removed_synthetic_snapshot_trees'] if Path(f['path']).name.startswith('factory-'+suffix+'-') for e in f['entries'])
 evidence_bytes=sum(q.stat().st_size for q in b.rglob('*') if q.is_file())
 life=O/'combined-raw'/('life-'+suffix+'.json')
 results.append(dict(case=suffix,status=t['status'],terminal_bytes=p.stat().st_size,details_bytes=actual,evidence_tree_bytes=evidence_bytes,factory_bytes=factory_bytes,physical_current_bytes=evidence_bytes+factory_bytes,metered_output=t['counters']['output_bytes'],refs=len(refs),samples=samples,commands=commands,old_life_bytes=life.stat().st_size,claim='EXPIRED'))
save('verification.json',dict(test_cases_are_not_verifier_assertions=True,verified_current_terminals=len(results),terminals=results))
# Text index keeps all synthetic fixture hashes; do not commit runtime SQLite/source duplicates.
removed=[]
for d in sorted((O/'combined-raw').glob('factory-*')):
 entries=[]
 for p in sorted(d.rglob('*')):
  if p.is_file():entries.append(dict(path=str(p.relative_to(d)),bytes=p.stat().st_size,sha256=sha(p.read_bytes())))
 removed.append(dict(path=str(d.relative_to(O)),entries=entries))
 shutil.rmtree(d)
if removed:save('fixture-cleanup.json',dict(removed_synthetic_snapshot_trees=removed,absence_confirmed=all(not (O/x['path']).exists() for x in removed),note='Original test-owned roots were removed by tests; these were review-owned copied snapshots only. No historical roots touched.'))
print(json.dumps(dict(archive_count=len(archives),archive_entries=sum(a['entries'] for a in archives),current_terminals=len(results),maximum=next(x for x in results if x['case']=='None')),ensure_ascii=False))
