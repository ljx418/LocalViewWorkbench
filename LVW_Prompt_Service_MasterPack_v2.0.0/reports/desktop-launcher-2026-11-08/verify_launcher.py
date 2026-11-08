"""Finite native build/self-test/idle-service start verification; never opens a browser or runs a model."""
from pathlib import Path
import hashlib,json,subprocess,sys
from tools import v0_verification_authority as authority

ROOT=Path(__file__).resolve().parents[2]
REPORT=Path(__file__).resolve().parent
slot=sys.argv[1] if len(sys.argv)>1 else '01'
if slot not in {'01','02'}:raise ValueError('finite slot invalid')
if slot=='02':REPORT=REPORT/'02';REPORT.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
win=lambda p:subprocess.check_output(['wslpath','-w',str(p)],text=True).strip()
compiler=Path('/mnt/c/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
ps=Path('/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe')
parent=json.loads((ROOT/authority.PROGRAM).read_text())
child=authority.child(parent,stage='V0-S2',run_id='desktop-launcher-directed-'+slot,candidate='719c74559393a6489b2f630a1e0d3bc3303eb655',harness_sha256=sha(__file__),program_sha256=sha(ROOT/authority.PROGRAM),budget={'native_builds':1,'native_self_tests':1,'comfy_starts':1,'loopback_requests':90,'model_calls':0,'media_reads':0,'visible_browser_starts':0,'downloads':0,'max_seconds':240},max_seconds=300)
child.update(scope='USER_REQUESTED_DESKTOP_LAUNCHER_DIRECTED_VERIFICATION_NOT_FULL_CHECKPOINT',source_sha256=sha(ROOT/'launcher/Launcher.cs'),compiler={'path':str(compiler),'sha256':sha(compiler)},powershell_sha256=sha(ps),port=8191,process_policy='Only the newly started original idle Comfy handle may be terminated. Never submit jobs.',cleanup='Native self-test and video-check remove only their fresh GUID temp root; no GUI/browser/model.',inputs=[])
with (REPORT/'authorization-01.json').open('x') as f:f.write(json.dumps(child,indent=2)+'\n')
result={'kind':'DESKTOP_LAUNCHER_DIRECTED_VERIFICATION_NOT_STAGE_ACCEPTANCE','decision':'NO_GO','checks':[],'stage_pass_claim':False,'human_signoff':None}
def run(name,args,timeout):
 p=subprocess.run(args,capture_output=True,timeout=timeout)
 (REPORT/(name+'.stdout.log')).write_bytes(p.stdout);(REPORT/(name+'.stderr.log')).write_bytes(p.stderr)
 result['checks'].append({'name':name,'exit_code':p.returncode})
 if p.returncode:raise RuntimeError(name+' failed; see raw logs')
try:
 run('build',[str(compiler),'/nologo','/target:winexe','/platform:anycpu','/optimize+','/codepage:65001','/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.dll','/reference:System.Core.dll','/win32icon:'+win(ROOT/'launcher/LVW.ico'),'/out:'+win(ROOT/'LVW.exe'),win(ROOT/'launcher/Launcher.cs')],30)
 script="$ErrorActionPreference='Stop';$s=New-Object -ComObject WScript.Shell;$l=$s.CreateShortcut('"+win(ROOT/'启动LVW.lnk')+"');$l.TargetPath='"+win(ROOT/'LVW.exe')+"';$l.WorkingDirectory='"+win(ROOT)+"';$l.IconLocation=$l.TargetPath+',0';$l.Description='LVW local image and video workbench';$l.Save();if($l.TargetPath -ne '"+win(ROOT/'LVW.exe')+"'){throw 'shortcut target mismatch'}"
 run('shortcut',[str(ps),'-NoProfile','-NonInteractive','-Command',script],20)
 run('self-test',[str(ROOT/'LVW.exe'),'--self-test',win(REPORT/'self-test.json')],40)
 run('native-video',[str(ROOT/'LVW.exe'),'--verify-video',win(REPORT/'native-video.json')],150)
 result.update(decision='DIRECTED_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE',exe_sha256=sha(ROOT/'LVW.exe'),shortcut_sha256=sha(ROOT/'启动LVW.lnk'),source_sha256=sha(ROOT/'launcher/Launcher.cs'))
except Exception as e:result['error']=type(e).__name__+':'+str(e)
finally:
 (REPORT/'receipt.json').write_text(json.dumps(result,indent=2)+'\n')
 (REPORT/'authorization-01.terminal.json').write_text(json.dumps(authority.expire(child,result['decision'],'receipt.json'),indent=2)+'\n')
print(json.dumps(result))
raise SystemExit(0 if result['decision']=='DIRECTED_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE' else 1)
