"""Review-only launcher; guards are installed in inspected immutable children."""
import os, sys, json, subprocess, hashlib, tempfile, shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
CANDIDATE='9ed09513eac35636175b24a514b05d9d0c180717'
mode=sys.argv[1]
env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONDONTWRITEBYTECODE='1')
for key in ['PYTEST_ADDOPTS','PYTEST_PLUGINS','PYTHONPYCACHEPREFIX']:env.pop(key,None)
base=None
if mode=='suite':
 base=tempfile.mkdtemp(prefix='lvw-independent-p3bc02-185ef48a-suite-')
 (OUT/'owned-suite-root.json').write_text(json.dumps({'path':base,'owner':'task_185ef48a77aa','cleanup':'only this unique root'})+'\n')
 env['PYTEST_ADDOPTS']='--basetemp='+base+' -vv'
runner=ROOT/'reports/v0-s3/product-gate0/implementation-p3b/run_offline_checks.py'
args=[sys.executable,'-B',str(runner),'--outdir',str(OUT),'--label',mode,'--candidate-sha',CANDIDATE]
if mode=='guard':args+=['--guard-selftest']
if mode in ['replay','focused']:
 args=[sys.executable,'-B',str(ROOT/'reports/v0-s3/product-gate0/implementation-p3b-correction-02/run_guarded_probe.py'),'--script',str(OUT/(mode+'_probes.py')),'--outdir',str(OUT),'--label',mode,'--candidate-sha',CANDIDATE]
try:
 r=subprocess.run(args,cwd=ROOT,env=env,capture_output=True)
 for name,raw in [('stdout',r.stdout),('stderr',r.stderr)]:(OUT/(mode+'.runner.'+name+'.log')).write_bytes(raw)
 doc={'argv':args,'cwd':str(ROOT),'environment_overrides':{k:env[k] for k in ['PYTEST_DISABLE_PLUGIN_AUTOLOAD','PYTHONDONTWRITEBYTECODE','PYTEST_ADDOPTS'] if k in env},'exit_code':r.returncode}
 for name,raw in [('stdout',r.stdout),('stderr',r.stderr)]:doc[name+'_bytes']=len(raw);doc[name+'_sha256']=hashlib.sha256(raw).hexdigest()
finally:
 if base:
  shutil.rmtree(base)
  (OUT/'suite-cleanup.json').write_text(json.dumps({'path':base,'removed':not Path(base).exists()})+'\n')
(OUT/(mode+'.command.json')).write_text(json.dumps(doc,indent=2)+'\n')
print(mode,r.returncode)
sys.exit(r.returncode)
