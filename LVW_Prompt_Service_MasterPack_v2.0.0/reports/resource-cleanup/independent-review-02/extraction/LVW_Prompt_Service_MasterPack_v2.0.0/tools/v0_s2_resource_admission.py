"""Approved, finite resource admission before the one exact fresh S2 full slot.

Authority/prepare read only repository and controlled historical evidence.
Native/WSL probes require a separately claimed, candidate-bound child.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from tools.v0_s2_checkpoint_oracles import EvidenceError
from tools.v0_s2_supplemental import expire

REQUEST='reports/v0-s2/authorization-s2-resource-ready-01.request.json'
APPROVAL='reports/v0-s2/authorization-s2-resource-ready-01.approval.json'
REQUEST_SHA='985521544eddcb9cd9afd0b1597df24962124d1f3e49aa30cb1617baece49ea0'
SLOT='full-resource-ready-01'
READY='resource-admission-01'
HARNESS='tools/v0_s2_resource_admission.py'


def authority(candidate, *, require_ready):
    from tools import v0_s2_stage_checkpoint as cp
    request=cp.repository_json(REQUEST);approval=cp.repository_json(APPROVAL)
    if (cp.file_hash(cp.ROOT/REQUEST)!=REQUEST_SHA or approval.get('request_sha256')!=REQUEST_SHA
            or approval.get('status')!='ACTIVE' or approval.get('granted_by')!='project_owner'
            or approval.get('authorization_id')!='AUTH-V1-S2-RESOURCE-READY-01'
            or approval.get('grant_statement')!='GPU 已释放；批准 AUTH-REQUEST-V1-S2-RESOURCE-READY-01，按请求文件完整范围执行，终态后自动过期。'
            or approval.get('additional_complete_native_runs')!=1 or approval.get('additional_full_rechecks')!=0
            or not approval['issued_at']<=time.time()<approval['expires_at']
            or not 0<approval['expires_at']-approval['issued_at']<=21600
            or request.get('native_runtime_budget')!=cp.BUDGET or request.get('acceptance_hash')!=cp.ACCEPTANCE):
        raise EvidenceError('resource-ready authority missing, expired or broadened')
    cp.program_authority()
    if cp.file_hash(cp.ROOT/request['offline_receipt'])!=request['offline_receipt_sha256']:
        raise EvidenceError('approved offline baseline changed')
    for name,digest in request['seed_artifact_sha256'].items():
        if cp.file_hash(cp.ROOT/cp.SEEDS[name])!=digest:raise EvidenceError('fixed model/sample/SDK binding changed')
    subprocess.run(['git','merge-base','--is-ancestor',request['corrected_candidate'],candidate],cwd=cp.ROOT,check=True,timeout=30)
    prefix=subprocess.check_output(['git','rev-parse','--show-prefix'],cwd=cp.ROOT,text=True,timeout=30).strip()
    names=subprocess.check_output(['git','diff','--name-only',request['corrected_candidate'],candidate],cwd=cp.ROOT,text=True,timeout=30).splitlines()
    allowed={'tools/v0_s2_stage_checkpoint.py','tools/v0_s2_supplemental.py',HARNESS,'tools/v0_s2_stage_runtime.py',
        'LVW_V0_RuntimePatch/tests/test_s2_resource_admission.py','LVW_V0_RuntimePatch/tests/test_s2_stage_runtime.py',
        'LVW_V0_RuntimePatch/tests/test_s2_supplemental.py',
        'plans/execution-control.json','MANIFEST.sha256'}
    for name in names:
        if not name.startswith(prefix):raise EvidenceError('resource-ready candidate outside package')
        relative=name[len(prefix):]
        if relative.startswith(('reports/v0-s2/frozen-structural-inputs','reports/v0-s2/fixture-preparation-',
                'reports/v0-s2/authorization-fixtures-')):
            raise EvidenceError('fixed structural media changed')
        if relative not in allowed and not relative.startswith(('reports/v0-s2/','.agent-governance/stages/V0-S2/')):
            raise EvidenceError('candidate changed product/contract outside approved transport: '+relative)
    spec='.agent-governance/stages/V0-S2/stage-control.json'
    old=json.loads(subprocess.check_output(['git','show',request['corrected_candidate']+':'+prefix+spec],cwd=cp.ROOT,timeout=30))
    current=cp.repository_json(spec)
    if current.get('resource_ready_authorization')!={'approval':APPROVAL,'request':REQUEST,'slot':SLOT,'max_runs':1,'max_rechecks':0}:
        raise EvidenceError('frozen resource-ready scope missing/broadened')
    for value in (old,current):
        value.pop('stage_packet_version',None);value.pop('resource_ready_authorization',None)
    if old!=current:raise EvidenceError('frozen obligations changed')
    for prior in request['prior_failed_runs']:
        report=cp.repository_json(prior['receipt'])
        if cp.file_hash(cp.ROOT/prior['receipt'])!=prior['receipt_sha256'] or report['decision']!='NO_GO':
            raise EvidenceError('prior failure changed')
        closed=cp.STATE_ROOT/prior['run_id']/'lease.closed'
        if closed.read_bytes()!=b'1':raise EvidenceError('prior run not terminal')
    cleanup=request['existing_cleanup']
    if (cp.file_hash(cp.ROOT/cleanup['receipt'])!=cleanup['receipt_sha256']
            or cp.repository_json(cleanup['receipt']).get('decision')!='CLEANUP_PROVEN_NOT_PRODUCT_ACCEPTANCE'):
        raise EvidenceError('prior cleanup proof changed')
    if require_ready:
        auth=cp.repository_json('reports/v0-s2/authorization-resource-admission-01.json')
        report=cp.repository_json(auth['terminal_receipt'])
        if (auth.get('status')!='EXPIRED_RESOURCE_READY' or auth.get('candidate_sha')!=candidate
                or cp.file_hash(cp.ROOT/auth['terminal_receipt'])!=auth.get('terminal_receipt_sha256')
                or report.get('decision')!='RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE' or report.get('sample_count')!=3
                or (cp.STATE_ROOT/READY/'lease.closed').read_bytes()!=b'1'):
            raise EvidenceError('resource admission not proven for final candidate')
    return {'approval':APPROVAL,'approval_sha256':cp.file_hash(cp.ROOT/APPROVAL),'request':REQUEST,
        'request_sha256':REQUEST_SHA,'expires_at':approval['expires_at']}


def expected_tools(cp):
    public=cp.repository_json('reports/v0-s2/full-supplemental-01/receipt.json')
    directory=cp.STATE_ROOT/'full-supplemental-01'
    if cp.file_hash(directory/'terminal.json')!=public['raw_terminal_sha256']:raise EvidenceError('old terminal changed')
    terminal=json.loads((directory/'terminal.json').read_bytes())
    proof=terminal['runtime_evidence']['default']['binding_proof']
    snapshot=json.loads((directory/'installed-bindings.json').read_bytes())
    manifest=hashlib.sha256(json.dumps(snapshot['files'],ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
    if manifest!=proof['manifest_sha256']:raise EvidenceError('old installed bindings changed')
    result={key:proof['tool_bindings'][key] for key in ('powershell','nvidia_exe')}
    result['wsl_nvidia']={'path':'/usr/lib/wsl/lib/nvidia-smi','sha256':next(row['sha256'] for row in snapshot['files'] if row['alias']=='WSL_NVIDIA')}
    return result


def prepare(candidate,offline,*,profile=None):
    from tools import v0_s2_stage_checkpoint as cp
    policy=profile or sys.modules[__name__]
    REQUEST,READY,HARNESS=policy.REQUEST,policy.READY,policy.HARNESS
    authority=policy.authority
    scope_key=getattr(policy,'SCOPE_KEY','readiness_child')
    refs=authority(candidate,require_ready=False);identity=cp.source_gate(candidate,offline)
    tools=expected_tools(cp)  # Recorded bytes only; no installed tool read.
    path=cp.ROOT/('reports/v0-s2/authorization-'+READY+'.json')
    if (cp.STATE_ROOT/READY).exists():raise EvidenceError('readiness already claimed')
    now=time.time();request=cp.repository_json(REQUEST)
    auth={'schema_version':'lvw.resource-admission-child/1','status':'ACTIVE_ONE_SHOT','run_id':READY,
        'candidate_sha':candidate,'harness_sha256':cp.file_hash(cp.ROOT/HARNESS),'payload_sha256':identity['payload_sha256'],
        'offline_receipt':offline,'offline_receipt_sha256':cp.file_hash(cp.ROOT/offline),'program_sha256':cp.program_authority(),
        'supplemental_authorization':refs,'tools':tools,'scope':(policy.readiness_scope() if callable(getattr(policy,'readiness_scope',None)) else request[scope_key]),
        'issued_at':now,'expires_at':min(now+900,refs['expires_at']),'execution_max_seconds':60,'stage_pass_claim':False}
    cp.write_new(path,auth);return auth


def oracle(native,wsl):
    """Shared approved resource budget; differing read times are diagnostic."""
    from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.resource_policy import admit,PolicyError
    if (not isinstance(native,dict) or type(native.get('ram_available_mib')) is not int
            or native['ram_available_mib']<2048 or type(native.get('target_listener_count')) is not int
            or native['target_listener_count']!=0 or type(native.get('target_process_count')) is not int
            or native['target_process_count']!=0):raise EvidenceError('RESOURCE_NOT_READY: RAM, ports, processes')
    rows=native.get('gpus')
    if isinstance(rows,dict):rows=[rows]
    try:evidence=admit(rows,wsl)
    except PolicyError as error:raise EvidenceError(error.reason) from error
    return {**evidence,'ram_available_mib':native['ram_available_mib'],'target_listener_count':0,'target_process_count':0}


def probe(*,profile=None):
    from tools import v0_s2_stage_checkpoint as cp
    policy=profile or sys.modules[__name__]
    REQUEST,APPROVAL,REQUEST_SHA,READY,HARNESS=policy.REQUEST,policy.APPROVAL,policy.REQUEST_SHA,policy.READY,policy.HARNESS
    authority=policy.authority
    scope_key=getattr(policy,'SCOPE_KEY','readiness_child')
    from tools.v0_s2_execution_bindings import plain
    path=cp.ROOT/('reports/v0-s2/authorization-'+READY+'.json');raw=path.read_bytes();auth=json.loads(raw)
    refs=authority(auth['candidate_sha'],require_ready=False)
    if (auth.get('schema_version')!='lvw.resource-admission-child/1' or auth.get('status')!='ACTIVE_ONE_SHOT'
            or auth.get('run_id')!=READY or auth.get('stage_pass_claim') is not False or auth['scope']!=(policy.readiness_scope() if callable(getattr(policy,'readiness_scope',None)) else cp.repository_json(REQUEST)[scope_key])
            or auth['tools']!=expected_tools(cp) or auth['supplemental_authorization']!=refs
            or auth.get('execution_max_seconds')!=60 or not 0<auth['expires_at']-auth['issued_at']<=900 or auth['harness_sha256']!=cp.file_hash(cp.ROOT/HARNESS)
            or auth['program_sha256']!=cp.program_authority() or cp.file_hash(cp.ROOT/auth['offline_receipt'])!=auth['offline_receipt_sha256']
            or not auth['issued_at']<=time.time()<auth['expires_at']
            or cp.source_gate(auth['candidate_sha'],auth['offline_receipt'])['payload_sha256']!=auth['payload_sha256']):
        raise EvidenceError('readiness child binding invalid')
    directory=cp.STATE_ROOT/READY;directory.mkdir(exist_ok=False)
    cp.write_new(directory/'active-child.json',auth)
    with (directory/'lease.closed').open('xb') as output:output.write(b'0');output.flush();os.fsync(output.fileno())
    started=time.monotonic();commands=[];samples=[]
    result={'run_id':READY,'candidate_sha':auth['candidate_sha'],'decision':'NO_GO','stage_pass_claim':False,
        'model_calls':0,'service_starts':0,'media_reads':0,'browser_starts':0,'foreign_process_terminations':0}
    def guard():
        if (path.read_bytes()!=raw or cp.file_hash(cp.ROOT/APPROVAL)!=refs['approval_sha256']
                or cp.file_hash(cp.ROOT/REQUEST)!=REQUEST_SHA or time.time()>=min(auth['expires_at'],refs['expires_at'])
                or time.monotonic()-started>60):raise EvidenceError('resource admission revoked/expired/over time')
    def execute(key,argv):
        guard();tool=auth['tools'][key];exe=plain(Path(tool['path']))
        if cp.file_hash(exe)!=tool['sha256']:raise EvidenceError('resource tool bytes changed')
        wsl=key=='wsl_nvidia'
        if sum(row['kind']==('wsl' if wsl else 'native') for row in commands)>=(3 if wsl else 3):raise EvidenceError('resource command budget exceeded')
        row={'kind':'wsl' if wsl else 'native','argv':[str(exe),*argv],'exit_code':None};commands.append(row)
        cp.write_new(directory/('command-'+str(len(commands))+'.json'),row)
        # Each PowerShell command additionally invokes one pinned native NVIDIA
        # executable: 3 PS + 3 NVIDIA <= 6 native commands; 3 WSL commands.
        process=subprocess.run(row['argv'],capture_output=True,timeout=max(.1,min(15,60-(time.monotonic()-started))))
        row['exit_code']=process.returncode
        for name in ('stdout','stderr'):
            data=getattr(process,name)
            if len(data)>65536:raise EvidenceError('resource output limit')
            (directory/('command-'+str(len(commands))+'.'+name+'.log')).write_bytes(data)
            row[name+'_sha256']=hashlib.sha256(data).hexdigest()
        guard()
        if process.returncode:raise EvidenceError('resource command failed')
        return process.stdout.decode('utf-8-sig','strict').strip()
    try:
        native=auth['tools']['nvidia_exe'];nvidia=plain(Path(native['path']))
        if cp.file_hash(nvidia)!=native['sha256']:raise EvidenceError('native NVIDIA bytes changed')
        windows='C:/'+native['path'].removeprefix('/mnt/c/')
        if not native['path'].startswith('/mnt/c/'):raise EvidenceError('unexpected native NVIDIA path')
        script="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop';"
        script+="$gpu=@(& "+cp.base.ps_quote(windows)+" --query-gpu=index,memory.total,memory.used,memory.free --format=csv,noheader,nounits);if($LASTEXITCODE -ne 0){throw 'NVIDIA_FAILED'};"
        script+="$ports=@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue|Where-Object {$_.LocalPort -in 8191,11434});"
        script+="$processes=@(Get-CimInstance Win32_Process);$ollama=@($processes|Where-Object {$_.Name -match 'ollama'});$comfy=@($processes|Where-Object {($_.Name -match 'python') -and ($_.CommandLine -match 'ComfyUI')});"
        script+="[ordered]@{gpu_csv=($gpu -join [Environment]::NewLine);ram_available_mib=[long][Math]::Floor((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1024.0);target_listener_count=$ports.Count;busy_ports=@($ports.LocalPort|Sort-Object -Unique);target_process_count=($ollama.Count+$comfy.Count);ollama_process_count=$ollama.Count;comfy_process_count=$comfy.Count}|ConvertTo-Json -Depth 5 -Compress"
        for index in range(3):
            if index:time.sleep(1)
            guard()
            if cp.file_hash(nvidia)!=native['sha256']:raise EvidenceError('native NVIDIA drift before probe')
            native_data=json.loads(execute('powershell',['-NoProfile','-NonInteractive','-Command',script]))
            native_data['gpus']=[[int(part.strip()) for part in line.split(',')] for line in native_data['gpu_csv'].splitlines() if line.strip()]
            wsl_data=execute('wsl_nvidia',['--query-gpu=index,memory.total,memory.used,memory.free','--format=csv,noheader,nounits'])
            rows=[[int(part.strip()) for part in line.split(',')] for line in wsl_data.splitlines() if line.strip()]
            sample={'ordinal':index+1,'native':native_data,'wsl':rows,'wall_seconds':time.time()};samples.append(sample)
            sample['admission']=oracle(native_data,rows)
        guard()
        result['decision']='RESOURCE_READY_NOT_PRODUCT_ACCEPTANCE'
    except BaseException as error:result['error_code']=type(error).__name__+':'+str(error)
    finally:
        result.update(sample_count=len(samples),samples=samples,commands=commands,
            native_commands=sum(row['kind']=='native' for row in commands),
            native_nvidia_invocations_upper_bound=sum(row['kind']=='native' for row in commands),
            native_command_upper_bound=sum(row['kind']=='native' for row in commands)*2,wsl_commands=sum(row['kind']=='wsl' for row in commands),
            elapsed_seconds=time.monotonic()-started)
        with (directory/'lease.closed').open('r+b') as output:output.write(b'1');output.flush();os.fsync(output.fileno())
        published=False;public_dir=cp.ROOT/'reports/v0-s2'/READY
        try:
            cp.write_new(directory/'terminal.json',result);public_dir.mkdir(exist_ok=False)
            public=cp.base.redact_value(result,{str(cp.ROOT):'PACK_ROOT',str(cp.STATE_ROOT):'STATE'})
            public['raw_terminal_sha256']=cp.file_hash(directory/'terminal.json');cp.write_new(public_dir/'receipt.json',public);published=True
        finally:
            auth['status']='EXPIRED_RESOURCE_READY' if published and result['decision'].startswith('RESOURCE_READY') else 'EXPIRED_NO_GO'
            if published:auth.update(terminal_receipt=str((public_dir/'receipt.json').relative_to(cp.ROOT)),terminal_receipt_sha256=cp.file_hash(public_dir/'receipt.json'))
            try:
                if path.read_bytes()==raw:
                    temporary=path.with_suffix('.terminal.tmp');cp.write_new(temporary,auth);os.replace(temporary,path)
            finally:
                if auth['status']=='EXPIRED_NO_GO':expire(refs,decision='NO_GO',terminal=auth.get('terminal_receipt','STATE/'+READY+'/terminal.json'))
    return result


def main():
    parser=argparse.ArgumentParser();commands=parser.add_subparsers(dest='command',required=True)
    ready=commands.add_parser('prepare');ready.add_argument('--candidate',required=True);ready.add_argument('--offline-receipt',required=True)
    commands.add_parser('probe');args=parser.parse_args()
    result=prepare(args.candidate,args.offline_receipt) if args.command=='prepare' else probe()
    print(json.dumps({key:result.get(key) for key in ('run_id','status','decision','error_code')}))
    return int(result.get('decision')=='NO_GO')


if __name__=='__main__':raise SystemExit(main())
