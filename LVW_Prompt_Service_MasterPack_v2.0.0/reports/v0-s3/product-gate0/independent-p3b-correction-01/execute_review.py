"""Review orchestration only: child guards precede pytest/product imports."""
import os, sys, json, subprocess, hashlib, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
candidate='376ea9283cb7096c2fc35f6eab561919c07b6d1f'
mode=sys.argv[1]
env=dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
for k in ['PYTEST_ADDOPTS','PYTEST_PLUGINS','PYTHONPYCACHEPREFIX']: env.pop(k,None)
if mode=='suite':
    base=tempfile.mkdtemp(prefix='lvw-independent-p3bc01-f4ad-suite-')
    (OUT/'owned-suite-root.json').write_text(json.dumps({'path':base,'ownership':'created exclusively by this review; cleanup only this root'}))
    env['PYTEST_ADDOPTS']='--basetemp='+base
runner=ROOT/'reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py'
args=[sys.executable,'-B',str(runner),'--outdir',str(OUT),'--label',mode,'--candidate-sha',candidate]
if mode=='guard':args+=['--guard-selftest']
if mode=='probes':args=[sys.executable,'-B',str(ROOT/'reports/v0-s3/product-gate0/implementation-p3b-correction-01/run_guarded_probe.py'),'--script',str(OUT/'targeted_probes.py'),'--outdir',str(OUT),'--label',mode,'--candidate-sha',candidate]
r=subprocess.run(args,cwd=ROOT,env=env,capture_output=True)
for name,raw in [('stdout',r.stdout),('stderr',r.stderr)]: (OUT/(mode+'.runner.'+name+'.log')).write_bytes(raw)
(OUT/(mode+'.command.json')).write_text(json.dumps({'argv':args,'cwd':str(ROOT),'environment_overrides':{k:env[k] for k in ['PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONDONTWRITEBYTECODE','PYTEST_ADDOPTS'] if k in env},'exit_code':r.returncode,'stdout_sha256':hashlib.sha256(r.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(r.stderr).hexdigest()},indent=2)+'\n')
print(mode,r.returncode)
sys.exit(r.returncode)
