import runpy
from pathlib import Path
root=Path(__file__).resolve().parents[4]
runpy.run_path(str(root/'reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py'),run_name='guard')
import shutil,json
owned=Path('/tmp/lvw-independent-p3b-139573-suite')
assert owned.is_dir() and not owned.is_symlink()
files=[p for p in owned.rglob('*') if p.is_file()]
receipt={'owned_root':str(owned),'file_count_before':len(files),'bytes_before':sum(p.stat().st_size for p in files),'original_pytest_roots_scanned':False}
shutil.rmtree(owned)
receipt['exists_after']=owned.exists()
print(json.dumps(receipt,indent=2))
