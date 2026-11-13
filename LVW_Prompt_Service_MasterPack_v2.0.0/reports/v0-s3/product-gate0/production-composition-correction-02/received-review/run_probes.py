import sys,json,os,threading,time
from pathlib import Path
import pytest
D=Path(__file__).parent
class Recorder:
 def __init__(self):self.nodes=[];self.results=[]
 def pytest_collection_finish(self,session):self.nodes=[x.nodeid for x in session.items]
 def pytest_runtest_logreport(self,report):
  if report.when=='call' or report.failed:self.results.append({'node':report.nodeid,'when':report.when,'outcome':report.outcome,'duration':report.duration,'failure':str(report.longrepr) if report.failed else None})
p=Recorder();before=os.listdir('/proc/self/fd');tb=[(t.name,t.ident,t.daemon) for t in threading.enumerate()];start=time.time()
nodes=[str(D/'probes.py'),*['tools/test_v0_s3_supervisor.py::'+n for n in ['test_the_worker_really_invokes_the_quality_phase','test_the_history_wait_is_announced_before_the_row_finishes','test_the_production_command_is_the_fixed_worker']]]
(D/'selection.json').write_text(json.dumps({'nodes':nodes,'whole_old_suites':False},indent=2))
code=pytest.main(['-q','-s','--tb=short','-p','no:cacheprovider','--basetemp',str(D/'probe-temp'),*nodes],plugins=[p])
(D/'probe-results.json').write_text(json.dumps({'exit':int(code),'collected':p.nodes,'reports':p.results,'duration':time.time()-start,'fd_before':before,'fd_after':os.listdir('/proc/self/fd'),'threads_before':tb,'threads_after':[(t.name,t.ident,t.daemon) for t in threading.enumerate()]},indent=2))
raise SystemExit(code)
