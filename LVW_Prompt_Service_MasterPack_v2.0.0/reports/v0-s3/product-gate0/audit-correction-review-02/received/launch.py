import sys
from pathlib import Path
OUT=Path(__file__).resolve().parent
exec(compile((OUT/'outer_boundary.py').read_bytes(),str(OUT/'outer_boundary.py'),'exec'))
import runpy
pack=OUT.parents[3]
runner=pack/'reports/v0-s3/product-gate0/implementation-integration-01/run_guarded_checks.py'
sys.argv=[str(runner)]+sys.argv[1:]
runpy.run_path(str(runner),run_name='__main__')
