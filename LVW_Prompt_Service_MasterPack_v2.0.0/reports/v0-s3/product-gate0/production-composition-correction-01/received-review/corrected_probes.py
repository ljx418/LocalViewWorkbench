import pytest,json
from pathlib import Path
D=Path(__file__).parent
names=['test_real_failed_rows_not_hidden_by_outer_blocked','test_worker_second_load_does_not_enforce_preflight_seal','test_blocked_thread_is_retained_and_can_write_after_return','test_last_row_release_failure_still_claims_output_contract_pass']
class Capture:
 def __init__(self):self.nodes=[];self.results=[]
 def pytest_collection_finish(self,session):self.nodes=[i.nodeid for i in session.items]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'nodeid':report.nodeid,'outcome':report.outcome,'when':report.when,'error':str(report.longrepr) if report.failed else None})
p=Capture();code=pytest.main(['-q','-s','--tb=short','-p','no:cacheprovider','--basetemp',str(D/'corrected-temp'),*[str(D/'probe_test.py')+'::'+name for name in names]],plugins=[p])
(D/'corrected-results.json').write_text(json.dumps({'exit':int(code),'nodes':p.nodes,'results':p.results,'reason':'Correct three independent oracle assumptions observed in first batch (first-row failure blocks later outputs; budget-zero cannot publish; closed stream stops phase file writes) and add final-row output false-PASS probe; preserve all original failed logs.'},indent=2))
raise SystemExit(code)
