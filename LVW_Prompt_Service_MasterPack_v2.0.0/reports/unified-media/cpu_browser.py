from pathlib import Path
import json,subprocess
from .authority import ROOT,create,terminal
out,auth=create('ui-cpu-01',Path(__file__).with_name('cpu_browser.cjs'),{'api_starts':1,'headless_browser_starts':1,'contexts':2,'public_submissions':8,'provider_calls':0,'model_calls':0,'downloads':0,'cloud_calls':0,'paid_calls':0,'holdout_model_calls':0},port=18781,samples=[ROOT/'reports/unified-media/dev-image.png',ROOT/'reports/v0-s2/fixture-preparation-02/fixtures/vfr.mp4'],seconds=240)
result={'kind':'UI_FIXTURE_SERVER_ONLY_NOT_REAL_MODEL_OR_STAGE_ACCEPTANCE','decision':'NO_GO','model_calls':0,'stage_pass_claim':False}
try:
 p=subprocess.run(['node',str(Path(__file__).with_name('cpu_browser.cjs')),str(out)],cwd=ROOT,capture_output=True,timeout=180)
 (out/'runner.stdout.log').write_bytes(p.stdout);(out/'runner.stderr.log').write_bytes(p.stderr)
 result=json.loads((out/'ui-result.json').read_text());assert p.returncode==0
finally:terminal(out,auth,result)
print(json.dumps(result))
raise SystemExit(0 if result['decision']=='CPU_UI_CHECKS_PASSED_NOT_MODEL_ACCEPTANCE' else 1)
