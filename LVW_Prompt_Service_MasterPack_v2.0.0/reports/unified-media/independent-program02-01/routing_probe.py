import importlib.util,json,pathlib,sys,tempfile
from unittest.mock import patch
OUT=pathlib.Path(__file__).resolve().parent;BASE=OUT.parents[2];sys.path.insert(0,str(BASE))
spec=importlib.util.spec_from_file_location('review_routing',BASE/'reports/unified-media/authority.py');h=importlib.util.module_from_spec(spec);spec.loader.exec_module(h)
results={}
with tempfile.TemporaryDirectory(dir=OUT) as td:
 root=pathlib.Path(td);(root/'plans').mkdir();(root/'reports').mkdir()
 (root/'plans/execution-control.json').write_text(json.dumps({'authorization_record':'reports/authorization-program-v1-local-02.approval.json'}))
 with patch.object(h,'ROOT',root),patch.object(h,'create_program02',return_value='PROGRAM02_VALIDATION_REQUIRED') as new:
  results['missing_approval_with_control_program02']=h.create('live-06',root/'unused',{},port=18780)
  results['new_validation_call_count']=new.call_count
 from tools import local_program_authority as a
 try:a.approved(root);results['missing_actual_approval']='ALLOWED'
 except Exception as e:results['missing_actual_approval']=type(e).__name__
(OUT/'routing-results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
