"""Finite public installed-code inventory; never starts a target or browser."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from tools.v0_s2_bindings import ROOT,TARGETS,file_hash
from tools.v0_s2_seal import seal_candidate

BUDGET={'source_files':32,'source_bytes':67108864,'sdk_files':8192,'sdk_bytes':268435456,
        'browser_binaries':2,'browser_bytes':1073741824,'metadata_commands':2,
        'media_reads':0,'service_starts':0,'provider_calls':0,'gpu_probes':0,'browser_starts':0,
        'downloads':0,'cloud_calls':0,'stage_checkpoints':0}
PAYLOAD=['tools/v0_s2_frontend_bindings.py','tools/v0_s2_bindings.py','tools/v0_s2_seal.py']
MARKERS=('--user-directory','set_user_directory','apiURL','fetchApi','createSocket','loadGraphData','queuePrompt','/ws','/api','connectWebSocket')


def snapshot_sources(named,roots):
    rows=[];queue=[(alias,path,0) for alias,path in named];seen=set();total=0
    roots={name:Path(root).resolve() for name,root in roots.items()}
    while queue:
        alias,path,depth=queue.pop(0);path=Path(path)
        if not path.exists():
            if depth==0:rows.append({'alias':alias,'status':'MISSING'})
            continue
        resolved=path.resolve(strict=True)
        if path.is_symlink() or not path.is_file() or not any(resolved.is_relative_to(r) for r in roots.values()):raise ValueError('FRONTEND_SOURCE_OUTSIDE_ROOT')
        if resolved in seen:continue
        seen.add(resolved)
        if len(seen)>BUDGET['source_files'] or path.stat().st_size>16*1024*1024:raise ValueError('FRONTEND_SOURCE_LIMIT')
        before=path.stat();total+=before.st_size
        if total>BUDGET['source_bytes']:raise ValueError('FRONTEND_SOURCE_LIMIT')
        raw=path.read_bytes();after=path.stat()
        if (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):raise ValueError('FRONTEND_SOURCE_CHANGED')
        text=raw.decode('utf-8','replace');snippets=[]
        for marker in MARKERS:
            index=text.find(marker)
            if index>=0:snippets.append({'marker':marker,'offset':index,'text':text[max(0,index-160):index+640]})
        rows.append({'alias':alias,'status':'HASHED','bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'snippets':snippets})
        if depth<2 and path.suffix in ('.js','.mjs'):
            imports=re.findall(r'''(?:from\s*|import\s*)["']([^"']+)["']''',text)
            for reference in imports[:32]:
                if not reference.startswith('.'):continue
                child=(path.parent/reference).resolve()
                if child.suffix not in ('.js','.mjs') or not child.exists():continue
                match=next(((name,root) for name,root in roots.items() if child.is_relative_to(root)),None)
                if match:queue.append((match[0]+'/'+child.relative_to(match[1]).as_posix(),child,depth+1))
    return {'files':rows,'source_bytes_read':total}


def sdk_snapshot(roots):
    rows=[];total=0;count=0
    for alias,root in roots.items():
        root=Path(root).resolve(strict=True)
        for path in sorted(root.rglob('*')):
            if not path.is_file():continue
            rel=path.relative_to(root)
            if not (rel.parts[0]=='lib' or str(rel) in {'index.js','index.mjs','cli.js','cli.mjs','package.json','browsers.json'}):continue
            if path.suffix not in {'.js','.mjs','.cjs','.json','.wasm','.node','.html','.css'}:continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('SDK_SYMLINK_FORBIDDEN')
            count+=1;total+=path.stat().st_size
            if count>BUDGET['sdk_files'] or total>BUDGET['sdk_bytes']:raise ValueError('SDK_BINDING_LIMIT')
            rows.append({'alias':alias+'/'+rel.as_posix(),'bytes':path.stat().st_size,'sha256':file_hash(path)})
    canonical=''.join(v['sha256']+'  '+v['alias']+'\n' for v in rows).encode()
    return {'files':rows,'bytes_hashed':total,'manifest_sha256':hashlib.sha256(canonical).hexdigest()}


def execute(relative):
    path=ROOT/relative;auth=json.loads(path.read_text());program_path=ROOT/'reports/authorization-program-v1-local-01.json'
    program=json.loads(program_path.read_text())
    if (program.get('status')!='ACTIVE' or program.get('authorization_id')!='AUTH-PROGRAM-V1-LOCAL-01'
            or 'V0-S2' not in program.get('stages',[]) or auth.get('source_program_authorization')!=program.get('authorization_id')
            or auth.get('status')!='ACTIVE_ONE_SHOT' or auth.get('scope')!='READ_ONLY_FRONTEND_BINDINGS'
            or auth.get('stage_id')!='V0-S2' or auth.get('budget')!=BUDGET
            or auth.get('run_id') not in ('frontend-bindings-01','frontend-bindings-02')
            or file_hash(program_path)!=auth.get('program_sha256') or file_hash(__file__)!=auth.get('harness_sha256')):
        raise ValueError('FRONTEND_BINDING_AUTHORITY_INVALID')
    identity=seal_candidate(ROOT,auth['candidate_sha'],PAYLOAD)
    directory=ROOT/'reports/v0-s2'/auth['run_id'];directory.mkdir(exist_ok=False)
    raw_auth=path.read_bytes();(directory/'active-authorization.json').write_bytes(raw_auth)
    result={'kind':'READ_ONLY_INSTALLED_BINDINGS_NOT_PRODUCT_ACCEPTANCE','candidate_sha':auth['candidate_sha'],
        'authorization_sha256':hashlib.sha256(raw_auth).hexdigest(),'identity':identity,'decision':'NO_GO',
        'stage_pass_claim':False,'target_process_starts':0,'browser_starts':0,'provider_calls':0,'media_reads':0,'gpu_probes':0,'stage_checkpoint_consumed':False}
    try:
        commands=[];result['metadata_commands']=commands
        def query(argv,env=None):
            executable=Path(shutil.which(argv[0]) or '').resolve(strict=True)
            row={'argv':argv,'executable_sha256':file_hash(executable)};commands.append(row)
            if len(commands)>2:raise ValueError('METADATA_COMMAND_BUDGET')
            value=subprocess.run(argv,env=env,capture_output=True,timeout=30)
            row.update(exit_code=value.returncode,stdout_original_sha256=hashlib.sha256(value.stdout).hexdigest(),stderr_original_sha256=hashlib.sha256(value.stderr).hexdigest())
            if value.returncode:raise ValueError('METADATA_COMMAND_FAILED')
            return value.stdout.decode('utf-8').strip()
        npm_root=query(['npm','root','-g'],env={**os.environ,'NPM_CONFIG_OFFLINE':'true','NPM_CONFIG_UPDATE_NOTIFIER':'false','NPM_CONFIG_AUDIT':'false','NPM_CONFIG_FUND':'false'})
        script="const p=require('path');const entry=require.resolve('playwright');console.log(JSON.stringify({entry,core:require.resolve('playwright-core/package.json',{paths:[p.dirname(entry)]})}));"
        modules=json.loads(query(['node','-e',script],env={**os.environ,'NODE_PATH':npm_root}))
        entry=Path(modules['entry']).resolve(strict=True);playwright=entry.parent;core=Path(modules['core']).parent.resolve(strict=True)
        global_root=Path(npm_root).resolve(strict=True)
        if not playwright.is_relative_to(global_root) or not core.is_relative_to(global_root):raise ValueError('SDK_ROOT_NOT_GLOBAL_PACKAGE')
        result['metadata_commands']=commands
        cli_root=TARGETS['COMFY_MAIN'].parent
        web_roots={'COMFY_WEB':cli_root/'web','FRONTEND_PACKAGE':TARGETS['COMFY_PYTHON'].parent/'Lib/site-packages/comfyui_frontend_package/static'}
        named=[('COMFY_ROOT/comfy/cli_args.py',cli_root/'comfy/cli_args.py'),('COMFY_ROOT/server.py',cli_root/'server.py')]
        for alias,root in web_roots.items():
            for name in ('scripts/app.js','scripts/api.js','index.html'):named.append((alias+'/'+name,root/name))
        result['frontend']=snapshot_sources(named,{'COMFY_ROOT':cli_root,**web_roots})
        result['sdk']=sdk_snapshot({'PLAYWRIGHT':playwright,'PLAYWRIGHT_CORE':core})
        result['sdk_entry']={'alias':'NODE_GLOBAL/'+entry.relative_to(global_root).as_posix(),'sha256':file_hash(entry),
            'playwright_version':json.loads((playwright/'package.json').read_text())['version'],
            'core_version':json.loads((core/'package.json').read_text())['version']}
        cache=Path.home()/'.cache/ms-playwright';binaries=[];total=0
        if cache.exists():
            dirs=sorted(p for p in cache.iterdir() if re.fullmatch(r'chromium(?:_headless_shell)?-[0-9]+',p.name))
            if len(dirs)>16:raise ValueError('BROWSER_CACHE_DIRECTORY_LIMIT')
            for sub in dirs:
                for suffix in ('chrome-linux/chrome','chrome-linux64/chrome','chrome-linux/headless_shell','chrome-headless-shell-linux64/chrome-headless-shell'):
                    binary=sub/suffix
                    if not binary.is_file():continue
                    if binary.is_symlink() or not binary.resolve().is_relative_to(cache.resolve()):raise ValueError('BROWSER_BINARY_OUTSIDE_CACHE')
                    total+=binary.stat().st_size
                    if len(binaries)>=2 or total>BUDGET['browser_bytes']:raise ValueError('BROWSER_BINARY_LIMIT')
                    binaries.append({'alias':'BROWSER_CACHE/'+binary.relative_to(cache).as_posix(),'bytes':binary.stat().st_size,'sha256':file_hash(binary)})
        result['browser_binaries']=binaries
        if not binaries:raise ValueError('INSTALLED_BROWSER_NOT_FOUND')
        if seal_candidate(ROOT,auth['candidate_sha'],PAYLOAD)!=identity:raise ValueError('BINDING_HARNESS_CHANGED')
        result['decision']='INSTALLED_BINDINGS_COLLECTED_NOT_NATIVE_ACCEPTANCE'
    except Exception as error:result['error_code']=type(error).__name__+':'+str(error)
    finally:
        result['finished_at']=datetime.now(timezone.utc).isoformat();result['cleanup']={'target_writes':0,'owned_queries_terminal':True,'new_services':0,'new_profiles':0}
        (directory/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
        auth['status']='EXPIRED_SUCCESS' if result['decision'].startswith('INSTALLED_BINDINGS_COLLECTED') else 'EXPIRED_NO_GO'
        auth['terminal_receipt']=str((directory/'receipt.json').relative_to(ROOT));path.write_text(json.dumps(auth,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--authorization',required=True);args=parser.parse_args()
    value=execute(args.authorization);print(json.dumps({k:value.get(k) for k in ('decision','error_code','browser_starts','provider_calls')}))
    raise SystemExit(0 if value['decision'].startswith('INSTALLED_BINDINGS_COLLECTED') else 1)
