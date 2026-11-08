from pathlib import Path
import subprocess,json,hashlib
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
win=lambda p:subprocess.check_output(['wslpath','-w',str(p)],text=True).strip()
csc='/mnt/c/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe'
args=[csc,'/nologo','/target:winexe','/platform:anycpu','/optimize+','/codepage:65001','/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.dll','/reference:System.Core.dll','/win32icon:'+win(ROOT/'launcher/LVW.ico'),'/out:'+win(ROOT/'LVW.exe'),win(ROOT/'launcher/Launcher.cs')]
r=subprocess.run(args,capture_output=True,timeout=30);(OUT/'launcher-build.stdout.log').write_bytes(r.stdout);(OUT/'launcher-build.stderr.log').write_bytes(r.stderr)
if r.returncode:raise RuntimeError('native compiler failed; see logs (no processes terminated)')
r=subprocess.run([str(ROOT/'LVW.exe'),'--self-test',win(OUT/'launcher-self-test.json')],capture_output=True,timeout=30)
assert r.returncode==0
print(json.dumps({'build_exit_code':0,'self_test_exit_code':0,'exe_sha256':hashlib.sha256((ROOT/'LVW.exe').read_bytes()).hexdigest()}))
