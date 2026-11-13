import sys,json
from pathlib import Path
import pytest
D=Path(__file__).resolve().parent
selection=json.loads((D/'ast-selection.json').read_text())
if sys.argv[1]=='collect':
 old=json.loads((D.parent/'independent-originals-correction-04/selection.json').read_text())
 class Capture:
  def pytest_collection_finish(self,session):
   nodes=[i.nodeid for i in session.items]
   (D/'collected-nodes.json').write_text(json.dumps({'unique_nodes':len(set(nodes)),'nodes':nodes,'execution_count':0},indent=2))
 args=['--collect-only','-q','-p','no:cacheprovider',*old,*selection['new_selectors']]
 code=pytest.main(args,plugins=[Capture()])
else:
 code=pytest.main(['-q','-p','no:cacheprovider','--basetemp',str(D/'pytest-temp'),*selection['new_selectors']])
raise SystemExit(code)
