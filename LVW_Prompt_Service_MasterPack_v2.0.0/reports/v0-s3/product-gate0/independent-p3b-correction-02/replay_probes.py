"""Once-only observed replay of inspected correction01 counterexamples."""
import runpy, shutil, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
ns=runpy.run_path(str(ROOT/'reports/v0-s3/product-gate0/implementation-p3b-correction-02/replay_correction01_probes.py'),run_name='independent_review_replay')
owned=ns['ROOT']
try:
 doc=ns['main']()
 assert len(doc['results'])==21
finally:
 shutil.rmtree(owned)
doc['own_fixture_cleanup']=not owned.exists()
doc['owner']='task_185ef48a77aa; fresh unique mkdtemp from inspected replay'
print(json.dumps(doc,indent=2))
