import sys,json,hashlib,runpy
from pathlib import Path
D=Path(__file__).parent
plan=json.loads((D/'plan.json').read_text())
for path,digest in {**plan['sourcepins'],**plan['toolpins'],**plan['dependency_pins']}.items():
 if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:raise RuntimeError('PIN_DRIFT:'+path)
sys.path.append(plan['dependency_root'])
sys.path.insert(0,plan['cwd'])
# pytest supplies MonkeyPatch only; no pytest.main, collection or plugins.
runpy.run_path(str(D/'probes.py'),run_name='__main__')
