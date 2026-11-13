import sys,json
from pathlib import Path
import pytest
out=Path(__file__).resolve().parent
selection=json.loads((out/'new-tests.json').read_text())['added']
selection += ['test_the_blocking_partial_frame_stays_incomplete','test_the_nonfinite_frame_is_complete_and_is_refused','test_the_message_count_negative_case_fits_the_frozen_byte_caps','test_the_parent_accepts_exactly_the_message_limit','test_the_frozen_caps_of_the_protocol_are_unchanged']
class Results:
 def __init__(self):self.collected=[];self.results=[]
 def pytest_collection_finish(self,session):self.collected=[i.nodeid for i in session.items]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.skipped or report.failed:self.results.append({'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,'detail':str(report.longrepr) if report.longrepr else None})
r=Results()
rc=pytest.main(['-q','-p','no:cacheprovider','--basetemp',str(out/'pytest-temp')]+['tools/test_v0_s3_supervisor.py::'+n for n in selection],plugins=[r])
(out/'selected-results.json').write_text(json.dumps({'exit_code':rc,'collected':r.collected,'results':r.results},indent=2))
raise SystemExit(rc)
