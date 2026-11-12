"""Supplementary small seal/content/read cleanup observations; no replay rerun."""
import copy, hashlib, json, os, shutil, tempfile
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT=Path(__file__).resolve().parent;ROOT=Path(tempfile.mkdtemp(prefix='independent-c05-boundaries-'));results=[]
try:
 p,d,_=t._prepare(ROOT/'seal',clock=t.FakeClock(step=0.0));r=p.run();path=p.directory/q.SOURCE_PLAN_NAME;raw=path.read_bytes();canonical=p.directory/q.CANONICAL_RECEIPT_NAME;canonraw=canonical.read_bytes()
 for field,value in [('source_bytes',1),('source_sha256','0'*64),('path','/foreign'),('identity',[0]*5),('ordinal',True)]:
  seal=json.loads(raw);seal['rows'][0][field]=value;altered=q.canonical_json(seal).encode();path.write_bytes(altered)
  doc=copy.deepcopy(r);doc['source_plan'].update(bytes=len(altered),sha256=hashlib.sha256(altered).hexdigest());canonical.write_text(q.canonical_json(doc))
  try:
   o=q.recompute_scores(doc,p.directory,t._scores(doc,doc['projection_sha256']),independence=t._independence());v={'aggregate_pass':o['aggregate_pass'],'resolved':o['all_rows_resolved']}
  except Exception as e:v={'error':str(e)}
  results.append({'name':'seal_only_'+field,'result':v,'execution_rows_unchanged':doc['rows']==r['rows']})
 path.write_bytes(raw);canonical.write_bytes(canonraw)
 # Count only descriptors opened by controlled Python calls, no /proc/global scan.
 opening=q.os.open;closing=q.os.close;live=set()
 def op(*a,**kw):
  fd=opening(*a,**kw);live.add(fd);return fd
 def cl(fd):
  live.discard(fd);return closing(fd)
 q.os.open=op;q.os.close=cl
 try:
  for name in ['missing_leaf','oversize','path_escape','success']:
   fixture=p.directory/'small.bin';fixture.write_bytes(b'abcd');boundary=q._ArtifactBoundary(p.directory)
   try:
    result=boundary.read({'missing_leaf':'absent','path_escape':'../small.bin'}.get(name,'small.bin'),3 if name=='oversize' else 4)
    value={'bytes':len(result)}
   except Exception as e:value={'error':str(e)}
   finally:boundary.close();fixture.unlink()
   results.append({'name':'descriptor_cleanup_'+name,'result':value,'live_owned_descriptors':sorted(live)})
  # A bounded file grows after the initial fstat; final max+1 check refuses.
  fixture=p.directory/'growing.bin';fixture.write_bytes(b'abcd');boundary=q._ArtifactBoundary(p.directory);read=q.os.read;hit=[];maximum=[]
  def growing(fd,n):
   maximum.append(n)
   if not hit:
    hit.append(True)
    with fixture.open('ab') as f:f.write(b'e')
   return read(fd,n)
  q.os.read=growing
  try:
   data=boundary.read(fixture.name,4);value={'bytes':len(data)}
  except Exception as e:value={'error':str(e)}
  finally:q.os.read=read;boundary.close();fixture.unlink()
  results.append({'name':'bounded_growth_one_over','result':value,'requests':maximum,'live_owned_descriptors':sorted(live)})
 finally:q.os.open=opening;q.os.close=closing
finally:shutil.rmtree(ROOT)
payload={'count':len(results),'results':results,'owned_root':str(ROOT),'removed':not ROOT.exists()}
(OUT/'boundary-observations.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n');print(json.dumps(payload,indent=2,sort_keys=True))
