"""Review-only entry: use inspected candidate guard before any pytest/project import."""
import os, sys, runpy
from pathlib import Path
ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ.pop('PYTEST_ADDOPTS',None)
os.environ.pop('PYTEST_PLUGINS',None)
runner = ROOT/'reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py'
ns = runpy.run_path(str(runner),run_name='inspected_guard')
if sys.argv[1] == 'probes':
    runpy.run_path(str(Path(__file__).with_name('probes.py')),run_name='__main__')
else:
    if sys.argv[1] == 'suite':
        os.environ['PYTEST_ADDOPTS']='--basetemp=/tmp/lvw-independent-p3b-139573-suite'
    args=['--outdir',str(Path(__file__).parent),'--label',sys.argv[1], '--candidate-sha','cea5bf328ea35a5aa1d1feb51ac3ef8946a964fa']
    if sys.argv[1] == 'guard-selftest':args += ['--guard-selftest']
    sys.exit(ns['main'](args))
