"""Exercise only the guide's directory/copy prefix and parse its launch command.
Never execute its service/model launch or environment setup.
"""
import base64
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from tools import v0_verification_authority as authority

ROOT=Path(__file__).resolve().parents[2]
REPORT=Path(__file__).resolve().parent
slot=sys.argv[1] if len(sys.argv)>1 else '01'
if slot not in {'01','02'}:raise ValueError('finite check slot invalid')
command=(REPORT/'video-start-command.txt').read_text()
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
parent=json.loads((ROOT/authority.PROGRAM).read_text())
child=authority.child(parent,stage='V0-S2',run_id='manual-guide-native-copy-'+slot,candidate='719c74559393a6489b2f630a1e0d3bc3303eb655',harness_sha256=sha(__file__),program_sha256=sha(ROOT/authority.PROGRAM),budget={'native_parser_checks':1,'native_copy_prefix_checks':1,'copied_files_max':200,'product_services':0,'model_calls':0,'media_decodes':0,'cloud_calls':0,'paid_calls':0,'downloads':0},max_seconds=120)
child.update(scope='MANUAL_GUIDE_PARSE_AND_TEMP_SOURCE_COPY_ONLY',command_sha256=sha(REPORT/'video-start-command.txt'),tool={'path':'/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe','sha256':sha('/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')})
auth=REPORT/('native-copy-authorization-'+slot+'.json')
with auth.open('x') as f:f.write(json.dumps(child,indent=2)+'\n')
result={'kind':'NATIVE_GUIDE_COMMAND_PARSE_AND_COPY_PREFIX_NOT_SERVICE_VERIFICATION','candidate_sha':child['candidate_sha'],'harness_sha256':child['harness_sha256'],'command_sha256':child['command_sha256'],'product_services_started':0,'model_calls':0,'stage_pass_claim':False,'decision':'NO_GO'}
try:
 raw=base64.b64encode(command.encode()).decode()
 parse="$text=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+raw+"'));$t=$null;$e=$null;$null=[Management.Automation.Language.Parser]::ParseInput($text,[ref]$t,[ref]$e);if($e.Count){throw 'PARSE_FAILED'};"
 source="C:\\workSpace\\videoWorkLine\\LocalViewWorkbench\\LVW_Prompt_Service_MasterPack_v2.0.0\\LVW_V0_RuntimePatch\\custom_nodes\\lvw_v0_bridge"
 setup=command[command.index('$lvwSession ='):command.index("foreach ($lvwName in @('LVW_NATIVE_CHECKPOINT'")]
 assert '& $lvwPython' not in setup and 'Start-Process' not in setup and 'OLLAMA' not in setup
 script=("$ErrorActionPreference='Stop';$ProgressPreference='SilentlyContinue';[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);"+parse+"$lvwSource='"+source+"';$lvwSession=$null;try{"+setup+
  "$lvwActualRoot=(Get-Item -LiteralPath $lvwTarget).FullName;$lvwRows=@(Get-ChildItem -LiteralPath $lvwTarget -Recurse -File|ForEach-Object{[ordered]@{file=$_.FullName.Substring($lvwActualRoot.Length+1).Replace('\\','/');sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()}});if($lvwRows.Count -gt 200){throw 'COPY_COUNT_LIMIT'};[ordered]@{parsed=$true;files=$lvwRows}|ConvertTo-Json -Depth 5 -Compress"
  +"}finally{if($lvwSession -and (Test-Path -LiteralPath $lvwSession)){if((Split-Path $lvwSession -Leaf) -notlike 'lvw-s2-experience-*'){throw 'UNEXPECTED_ROOT'};Remove-Item -LiteralPath $lvwSession -Recurse -Force};Write-Output ('CLEANUP_ABSENT='+(-not (Test-Path -LiteralPath $lvwSession)))}")
 argv=[child['tool']['path'],'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(script.encode('utf-16le')).decode()]
 process=subprocess.run(argv,capture_output=True,timeout=40)
 stdout=process.stdout.decode('utf-8-sig');stderr=process.stderr.decode('utf-8-sig')
 (REPORT/('native-copy-'+slot+'.stdout.log')).write_text(stdout);(REPORT/('native-copy-'+slot+'.stderr.log')).write_text(stderr)
 result.update(exit_code=process.returncode,stdout_sha256=sha(REPORT/('native-copy-'+slot+'.stdout.log')),stderr_sha256=sha(REPORT/('native-copy-'+slot+'.stderr.log')))
 if process.returncode:raise ValueError('native parse/copy prefix failed')
 lines=stdout.strip().splitlines();value=json.loads(lines[0]);assert lines[-1]=='CLEANUP_ABSENT=True' and value['parsed'] is True
 expected={str(p.relative_to(ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge')):sha(p) for p in (ROOT/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge').rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
 actual={v['file']:v['sha256'] for v in value['files']}
 assert actual==expected
 result.update(decision='PARSE_AND_TEMP_COPY_VERIFIED_NOT_SERVICE_START',copied_files=len(actual),copied_hashes_match=True,owned_temp_absent=True,service_launch_executed=False)
except Exception as error:result['error']=type(error).__name__+':'+str(error)
finally:
 with (REPORT/('native-copy-receipt-'+slot+'.json')).open('x') as f:f.write(json.dumps(result,indent=2)+'\n')
 with (REPORT/('native-copy-authorization-'+slot+'.terminal.json')).open('x') as f:f.write(json.dumps(authority.expire(child,result['decision'],'native-copy-receipt-'+slot+'.json'),indent=2)+'\n')
print(json.dumps(result))
raise SystemExit(0 if result['decision']=='PARSE_AND_TEMP_COPY_VERIFIED_NOT_SERVICE_START' else 1)
