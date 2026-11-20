"""Windows owns the original Ollama process handle; WSL controls only its stop nonce."""
from pathlib import Path
import json,subprocess,uuid,shutil,os


def literal(value):return "'"+str(value).replace("'","''")+"'"
def windows(path):return str(path) if os.name == 'nt' else subprocess.check_output(['wslpath','-w',str(path)],text=True,timeout=3).strip()

def prepare(root:Path, executable:Path):
    token=uuid.uuid4().hex
    from .native_private import create_root
    root, privacy_preamble = create_root(token, windows)
    owner=root/(token+'.owner.json');stop=root/(token+'.stop');stdout=root/(token+'.stdout.log');stderr=root/(token+'.stderr.log')
    q=lambda p:literal(windows(p))
    from .native_job import JOB_SOURCE
    script=("$ErrorActionPreference='Stop';"+privacy_preamble+"$env:OLLAMA_HOST='http://127.0.0.1:11434';$env:OLLAMA_NO_CLOUD='true';"
        "$env:NO_PROXY='127.0.0.1,localhost';$env:TEMP="+q(root)+";$env:TMP="+q(root)+";$job=$null;$nonce="+literal(token)+";$owner="+q(owner)+";$stop="+q(stop)+";"
        "function SaveOwner($state,$listening){$row=[ordered]@{nonce=$nonce;state=$state;pid=$ownedId;birth_ticks=$birth;listener_owned=$listening;job_owned=$true;job_empty=$job.Empty};[IO.File]::WriteAllText($owner,($row|ConvertTo-Json -Compress),[Text.UTF8Encoding]::new($false))};"
        "try{Add-Type -TypeDefinition "+literal(JOB_SOURCE)+";$job=[LvwOwnedJob]::new();$job.Start("+q(executable)+","+q(stdout)+","+q(stderr)+");"
        "$ownedId=[int]$job.Pid;$birth=$job.BirthTicks;SaveOwner 'starting' $false;"
        "while(!$job.HasExited){if(Test-Path -LiteralPath $stop){if([IO.File]::ReadAllText($stop) -eq $nonce){break}};"
        "$listener=@(Get-NetTCPConnection -State Listen -LocalPort 11434 -ErrorAction SilentlyContinue|Where-Object{$_.OwningProcess -eq $ownedId});"
        "if($listener.Count){SaveOwner 'listening' $true};Start-Sleep -Milliseconds 200}"
        "}finally{if($job){try{if(!$job.Stop(5000)){SaveOwner 'needs_attention' $false;throw 'OWNED_JOB_EXIT_UNPROVEN'};SaveOwner 'exited' $false}finally{$job.Dispose()}}}")
    powershell=shutil.which('powershell.exe') or '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe'
    return {'job_required':True,'nonce':token,'owner':owner,'stop':stop,'stdout':stdout,'stderr':stderr,'argv':[powershell,'-NoProfile','-NonInteractive','-Command',script]}

def proof(value):
    if not value:return {}
    try:
        p=json.loads(value['owner'].read_text())
        if isinstance(p,dict) and p.get('nonce')==value['nonce'] and type(p.get('pid')) is int and p['pid']>0 and type(p.get('birth_ticks')) is int:
            if value.get('job_required') and (p.get('job_owned') is not True or p.get('state') == 'exited' and p.get('job_empty') is not True):return {}
            return p
    except (OSError,ValueError):pass
    return {}
