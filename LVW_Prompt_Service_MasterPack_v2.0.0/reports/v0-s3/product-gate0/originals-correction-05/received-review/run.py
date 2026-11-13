"""Outer recorder: no counter writes; every inner failure preserved and propagated."""
from pathlib import Path
import subprocess,sys,json,hashlib,time
D=Path(__file__).resolve().parent;P=D.parents[3]
assert (P/'tools').is_dir(),P
R=Path('/mnt/c/workspace/videoworkline/localviewworkbench/LVW_Prompt_Service_MasterPack_v2.0.0/reports/v0-s3/product-gate0/originals-correction-review-04/received')
author=json.loads((R/'run.receipt.json').read_text());nodes=author['directed_nodes'];assert len(nodes)==31 and len(set(nodes))==31
(D/'selection.json').write_text(json.dumps(nodes,indent=2))
steps=[('guard-selftest','guard_selftest.py',[]),('independent-probe','probe.py',[]),('directed-31','pytest_entry.py',['-q','-p','no:cacheprovider','--basetemp='+str(D/'pytest-temp'),*nodes])]
records=[]
for label,entry,args in steps:
 argv=[sys.executable,'-B',str(D/'guard.py'),str(D/entry),str(D/(label+'.guard.json')),*args];begin=time.monotonic()
 with (D/(label+'.stdout.log')).open('xb') as out,(D/(label+'.stderr.log')).open('xb') as err:
  run=subprocess.run(argv,cwd=P,stdout=out,stderr=err,timeout=40)
 records.append({'label':label,'argv':argv,'cwd':str(P),'exit':run.returncode,'seconds':time.monotonic()-begin})
(D/'commands.json').write_text(json.dumps(records,indent=2));print(json.dumps(records,indent=2));raise SystemExit(int(any(r['exit'] for r in records)))
