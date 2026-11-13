import sys,json,os,threading,time
from pathlib import Path
import pytest
D=Path(__file__).parent;sys.path.insert(0,str(D))
class Recorder:
 def __init__(self):self.nodes=[];self.reports=[]
 def pytest_collection_finish(self,session):self.nodes=[i.nodeid for i in session.items]
 def pytest_runtest_logreport(self,report):
  r=report
  if r.when=='call' or r.failed:self.reports.append({'node':r.nodeid,'when':r.when,'outcome':r.outcome,'failure':str(r.longrepr) if r.failed else None})
p=Recorder();fds=os.listdir('/proc/self/fd');start=time.time()
names=['test_canonical_parsed_before_sealed_bytes']
code=pytest.main(['-q','-s','--tb=short','-p','no:cacheprovider','--basetemp',str(D/'parse-boundary-temp'),*[str(D/'parse_boundary.py')+'::'+n for n in names]],plugins=[p])
(D/'parse-boundary-results.json').write_text(json.dumps({'exit':int(code),'collected':p.nodes,'reports':p.reports,'duration':time.time()-start,'fd_before':fds,'fd_after':os.listdir('/proc/self/fd'),'threads_after':[(t.name,t.ident,t.daemon) for t in threading.enumerate()]},indent=2));raise SystemExit(code)
