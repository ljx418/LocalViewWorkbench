from pathlib import Path
import subprocess,json,hashlib,time,sys
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent/('offline-'+(sys.argv[1] if len(sys.argv)>1 else '01'));OUT.mkdir(exist_ok=False)
commands=[['python3','-B','-m','pytest','lvw/tests','LVW_V0_RuntimePatch/tests/test_s2_video_input.py','LVW_V0_RuntimePatch/tests/test_s2_video_files.py','LVW_V0_RuntimePatch/tests/test_s2_video_process.py','LVW_V0_RuntimePatch/tests/test_s2_video_decoder.py','-q'],['npm','run','test'],['npm','run','typecheck'],['npm','run','build'],['python3','-B','tools/verify_governance.py','--self-test']]
result={'kind':'UNIFIED_OFFLINE_CHECKPOINT_NOT_REAL_OR_HUMAN_ACCEPTANCE','candidate_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'checks':[],'decision':'NO_GO','model_calls':0}
for i,cmd in enumerate(commands):
 cwd=ROOT/'lvw/frontend' if cmd[0]=='npm' else ROOT
 try:
  p=subprocess.run(cmd,cwd=cwd,capture_output=True,timeout=180)
 except subprocess.TimeoutExpired as error:
  from types import SimpleNamespace
  p=SimpleNamespace(stdout=error.stdout or b"",stderr=(error.stderr or b"")+b"\nOFFLINE_COMMAND_TIMEOUT_180_SECONDS\n",returncode=124)
 (OUT/f'{i+1}.stdout.log').write_bytes(p.stdout);(OUT/f'{i+1}.stderr.log').write_bytes(p.stderr)
 result['checks'].append({'command':cmd,'exit_code':p.returncode,'stdout_sha256':hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':hashlib.sha256(p.stderr).hexdigest()})
 if p.returncode:break
if len(result['checks'])==len(commands) and all(c['exit_code']==0 for c in result['checks']):result['decision']='OFFLINE_CHECKPOINT_VERIFIED_NOT_LIVE_OR_HUMAN'
(OUT/'receipt.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
raise SystemExit(0 if result['decision'].startswith('OFFLINE_CHECKPOINT_VERIFIED') else 1)
