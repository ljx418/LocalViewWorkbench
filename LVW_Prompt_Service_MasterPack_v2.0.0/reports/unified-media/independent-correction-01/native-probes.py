import asyncio,json,tempfile,base64,subprocess
from pathlib import Path
from unittest.mock import patch
from app.native_runtime import prepare
from app.runtime import OllamaRuntime

root=Path(tempfile.mkdtemp(prefix='lvw-native-review-'))
with patch('app.native_runtime.windows',side_effect=lambda p:'C:\\review\\'+Path(p).name):
 plan=prepare(root,root/'ollama.exe')
script=plan['argv'][-1]
encoded=base64.b64encode(script.encode()).decode()
parse="$s=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"'));$tokens=$null;$errors=$null;$a=[System.Management.Automation.Language.Parser]::ParseInput($s,[ref]$tokens,[ref]$errors);$errors|ForEach-Object{$_.Message};Write-Output ('AST_ERROR_COUNT='+$errors.Count)"
r=subprocess.run([plan['argv'][0],'-NoProfile','-NonInteractive','-Command',parse],cwd='/mnt/c/Windows',capture_output=True)
print('native_AST',r.returncode,r.stdout.decode(errors='replace').strip(),r.stderr.decode(errors='replace').strip())
print('explicit_windows_env',all(v in script for v in ["$env:OLLAMA_HOST='http://127.0.0.1:11434'","$env:OLLAMA_NO_CLOUD='true'","$env:NO_PROXY='127.0.0.1,localhost'"]))

class Provider:
 async def readiness(self):return {'ready':False,'model':'gemma4:26b','reason':'OLLAMA_UNAVAILABLE','loaded':False}
class ExitedWrapper:
 returncode=1;pid=123
async def exit_proof_probe():
 runtime=OllamaRuntime(Provider(),root/'ollama.exe',root)
 runtime.process=ExitedWrapper(); runtime._native=plan
 plan['owner'].write_text(json.dumps({'nonce':plan['nonce'],'pid':444,'birth_ticks':123456,'state':'starting','listener_owned':False}))
 await runtime.close()
 status=await runtime.status()
 print('unproven_native_exit_close',{'exception':None,'process_cleared':runtime.process is None,'native_ownership_unresolved':runtime._native is not None,'runtime_state':status['ollama']['state'],'can_start':status['actions']['can_start']})
asyncio.run(exit_proof_probe())
