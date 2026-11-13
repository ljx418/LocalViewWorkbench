import json,pytest
from pathlib import Path
O=Path(__file__).resolve().parent
old=json.loads((O/'correction01-tests-derived.json').read_text())['names'];new=json.loads((O/'new-tests.json').read_text())['added']
class C:
 def pytest_collection_finish(self,session):
  ids=[i.nodeid for i in session.items];(O/'actual-added-collection.json').write_text(json.dumps({'prior_added_actual':[x for x in ids if x.split('::')[-1].split('[')[0] in old],'current_added_actual':[x for x in ids if x.split('::')[-1].split('[')[0] in new],'total_collected':len(ids),'execution':False},indent=2))
raise SystemExit(pytest.main(['--collect-only','-q','-p','no:cacheprovider']+['tools/test_v0_s3_supervisor.py::'+n for n in old+new],plugins=[C()]))
