"""Eight bounded observations closing remaining boundary coverage gaps."""
import copy,json,tempfile,shutil,os
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT=Path(__file__).parent
ROOT=Path(tempfile.mkdtemp(prefix='lvw-independent-c03-supplement-6e497-'))
(OUT/'supplement-fixtures.json').write_text(json.dumps({'owner':'task_6e497e41e8c1','root':str(ROOT)})+'\n')
results=[]
try:
    p,d,_=t._prepare(ROOT/'true-later-expiry',clock=t.FakeClock(step=0.0));p.parent_budget['expires_monotonic']=2.0
    def authorize(action,subject):
        if action=='quality_public_submit' and d.submissions==1:p.clock.now=2.0
    p.authorize=authorize;r=p.run()
    results.append({'probe':'later_true_interval_expiry','issued':p.parent_budget['issued_monotonic'],'expires':p.parent_budget['expires_monotonic'],'clock':p.clock.now,'sends':d.submissions,'charged':r['public_submissions'],'reserved':r['provider_calls_reserved'],'second_error':r['rows'][1]['error_code'],'counts':r['test_counts']})
    p,d,_=t._prepare(ROOT/'release-boundaries',clock=t.FakeClock(step=0.0));r=p.run();scores=t._scores(r,r['projection_sha256'])
    cases=[('samples32',{'gpu_samples':[{'monotonic_seconds':i*0.5,'gpu_used_mib':1124} for i in range(32)],'elapsed_seconds':30}),('elapsed0',{'elapsed_seconds':0}),('elapsed30',{'elapsed_seconds':30}),('cadence1.5',{'gpu_samples':[{'monotonic_seconds':i*1.5,'gpu_used_mib':1124} for i in range(3)]}),('cadence1.500001',{'gpu_samples':[{'monotonic_seconds':i*1.500001,'gpu_used_mib':1124} for i in range(3)]}),('elapsed30.000001',{'elapsed_seconds':30.000001}),('loaded_models_false',{'loaded_models':False})]
    for name,changes in cases:
        doc=copy.deepcopy(r);doc['rows'][0]['release_evidence'].update(changes)
        out=q.recompute_scores(doc,p.directory,scores,independence=t._independence())
        results.append({'probe':'release_boundary_'+name,'aggregate_pass':out['aggregate_pass'],'row':{k:out['rows'][0][k] for k in ['usable','resolved','evidence_reason']}})
finally:shutil.rmtree(ROOT)
print(json.dumps({'results':results,'count':len(results),'owned_root':str(ROOT),'removed':not ROOT.exists()},indent=2))
