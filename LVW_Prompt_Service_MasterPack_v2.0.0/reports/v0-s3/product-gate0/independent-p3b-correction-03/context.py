"""Five typed-context observations requested by root; public scorer only."""
import copy,json,tempfile,shutil
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT=Path(__file__).parent
ROOT=Path(tempfile.mkdtemp(prefix='lvw-independent-c03-context-6e497-'))
(OUT/'context-fixtures.json').write_text(json.dumps({'root':str(ROOT),'owner':'task_6e497e41e8c1'})+'\n')
results=[]
try:
    p,d,_=t._prepare(ROOT/'public',clock=t.FakeClock(step=0));r=p.run();scores=t._scores(r,r['projection_sha256'])
    for field,label,value in [('parent_budget_baseline_gpu_mib','float',100.0),('parent_budget_baseline_gpu_mib','bool',True),('parent_budget_baseline_gpu_mib','string','100'),('parent_budget_baseline_gpu_mib','negative',-1),('run_root','integer',0)]:
        doc=copy.deepcopy(r);doc[field]=value
        out=q.recompute_scores(doc,p.directory,scores,independence=t._independence())
        results.append({'probe':'context_'+field+'_'+label,'value':value,'aggregate_pass':out['aggregate_pass'],'row':{k:out['rows'][0][k] for k in ['usable','resolved','evidence_reason']}})
finally:shutil.rmtree(ROOT)
print(json.dumps({'results':results,'count':len(results),'owned_root':str(ROOT),'removed':not ROOT.exists()},indent=2))
