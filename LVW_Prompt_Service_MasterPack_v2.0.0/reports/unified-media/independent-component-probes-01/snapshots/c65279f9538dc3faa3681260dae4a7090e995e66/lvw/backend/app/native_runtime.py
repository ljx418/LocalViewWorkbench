"""Windows owns the original Ollama process handle; WSL controls only its stop nonce."""
from pathlib import Path
import json,subprocess,uuid,shutil


def literal(value):return "'"+str(value).replace("'","''")+"'"
def windows(path):return subprocess.check_output(['wslpath','-w',str(path)],text=True,timeout=3).strip()

def prepare(root:Path, executable:Path):
    token=uuid.uuid4().hex
    owner=root/(token+'.owner.json');stop=root/(token+'.stop');stdout=root/(token+'.stdout.log');stderr=root/(token+'.stderr.log')
    q=lambda p:literal(windows(p))
    script=("$ErrorActionPreference='Stop';$env:OLLAMA_HOST='http://127.0.0.1:11434';$env:OLLAMA_NO_CLOUD='true';"
        "$env:NO_PROXY='127.0.0.1,localhost';$p=$null;$nonce="+literal(token)+";$owner="+q(owner)+";$stop="+q(stop)+";"
        "function SaveOwner($state,$listening){$row=[ordered]@{nonce=$nonce;state=$state;pid=$ownedId;birth_ticks=$birth;listener_owned=$listening};[IO.File]::WriteAllText($owner,($row|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))};"
        "try{$p=Start-Process -FilePath "+q(executable)+" -ArgumentList 'serve' -PassThru -NoNewWindow -RedirectStandardOutput "+q(stdout)+" -RedirectStandardError "+q(stderr)+";"
        "$nativeHandle=$p.Handle;$ownedId=$p.Id;$birth=$p.StartTime.ToUniversalTime().Ticks;SaveOwner 'starting' $false;"
        "while(!$p.HasExited){if(Test-Path -LiteralPath $stop){if([IO.File]::ReadAllText($stop) -eq $nonce){break}};"
        "$listener=@(Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue|Where-Object{$_.OwningProcess -eq $p.Id});"
        "if($listener.Count){SaveOwner 'listening' $true};Start-Sleep -Milliseconds 200}"
        "}finally{if($p){if(!$p.HasExited){$p.Kill()};$p.WaitForExit();SaveOwner 'exited' $false}}")
    powershell=shutil.which('powershell.exe') or '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    return {'nonce':token,'owner':owner,'stop':stop,'stdout':stdout,'stderr':stderr,'argv':[powershell,'-NoProfile','-NonInteractive','-Command',script]}

def proof(value):
    if not value:return {}
    try:
        p=json.loads(value['owner'].read_text())
        if p.get('nonce')==value['nonce'] and type(p.get('pid')) is int and p['pid']>0 and type(p.get('birth_ticks')) is int:return p
    except (OSError,ValueError):pass
    return {}
