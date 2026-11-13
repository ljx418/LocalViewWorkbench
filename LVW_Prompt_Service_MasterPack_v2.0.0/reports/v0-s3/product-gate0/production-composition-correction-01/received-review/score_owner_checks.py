"""Narrow verification of remaining QS owner concern; real recomputation, no score-owner mock."""
from pathlib import Path
import pytest,json
D=Path(__file__).parent
names=['test_the_independent_score_is_recomputed_by_the_accepted_owner','test_an_independent_score_that_does_not_match_is_refused']
class Capture:
 def __init__(self):self.nodes=[];self.results=[]
 def pytest_collection_finish(self,session):self.nodes=[i.nodeid for i in session.items]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'nodeid':report.nodeid,'outcome':report.outcome,'when':report.when,'error':str(report.longrepr) if report.failed else None})
p=Capture();code=pytest.main(['-q','--tb=short','-p','no:cacheprovider','--basetemp',str(D/'score-temp'),*['tools/test_v0_s3_production_composition.py::'+name for name in names]],plugins=[p])
(D/'score-results.json').write_text(json.dumps({'exit':int(code),'nodes':p.nodes,'results':p.results,'scope_reason':'Remaining QS concern: verify real owner recomputation and foreign raw hash rejection through controller, not isolated internal receipt adapter or patched verdict.'},indent=2));raise SystemExit(code)
