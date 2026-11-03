"""Bounded read-only binding inventory; execution needs a program child receipt."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/mnt/c/workSpace/videoWorkLine/testSource')
TARGETS = {
    'COMFY_MAIN':Path('/mnt/c/ComfyUI-aki-v2/ComfyUI/main.py'),
    'COMFY_PYTHON':Path('/mnt/c/ComfyUI-aki-v2/python/python.exe'),
    'OLLAMA_EXE':Path('/mnt/c/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe'),
}


class BindingError(ValueError): pass


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024*1024): value.update(chunk)
    return value.hexdigest()


def sample_inventory(root):
    """Hash up to 24 allowed media files, <=256MiB each and <=1GiB total."""
    root = Path(root).resolve(strict=True)
    candidates = []
    for visited,path in enumerate(root.rglob('*')):
        if visited >= 4096: raise BindingError('SAMPLE_TREE_SCAN_BUDGET_EXCEEDED')
        if path.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.mp4','.mov'}:
            candidates.append(path)
            if len(candidates) > 24: raise BindingError('SAMPLE_INVENTORY_COUNT_OUT_OF_SCOPE')
    candidates.sort()
    if not candidates or len(candidates) > 24:
        raise BindingError('SAMPLE_INVENTORY_COUNT_OUT_OF_SCOPE')
    result = []; total = 0
    for index,path in enumerate(candidates):
        if path.is_symlink() or not path.is_file(): raise BindingError('SAMPLE_REFERENCE_INVALID')
        resolved = path.resolve(strict=True)
        try: resolved.relative_to(root)
        except ValueError as exc: raise BindingError('SAMPLE_REFERENCE_OUTSIDE_ROOT') from exc
        size = path.stat().st_size
        if not 0 < size <= 256*1024*1024: raise BindingError('SAMPLE_BYTE_BUDGET_EXCEEDED')
        total += size
        if total > 1024*1024*1024: raise BindingError('SAMPLE_TOTAL_BUDGET_EXCEEDED')
        before = path.stat()
        digest = file_hash(path)
        after = path.stat()
        if (before.st_size,before.st_mtime_ns,before.st_ino) != (after.st_size,after.st_mtime_ns,after.st_ino):
            raise BindingError('SAMPLE_CHANGED_DURING_HASH')
        result.append({'alias':f'TEST_SOURCE/sample-{index+1:02d}','suffix':path.suffix.lower(),
                       'bytes':size,'sha256':digest})
    return result


def validate_authority(auth, program, *, candidate, harness_sha):
    if not (program.get('status') == 'ACTIVE'
            and program.get('authorization_id') == 'AUTH-PROGRAM-V1-LOCAL-01'
            and 'V0-S2' in program.get('stages',[])
            and auth.get('status') == 'ACTIVE_ONE_SHOT'
            and auth.get('source_program_authorization') == program['authorization_id']
            and auth.get('stage_id') == 'V0-S2'
            and auth.get('scope') == 'READ_ONLY_BINDING_INVENTORY'
            and isinstance(auth.get('run_id'),str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',auth['run_id'])
            and auth.get('candidate_sha') == candidate
            and auth.get('harness_sha256') == harness_sha
            and auth.get('budget') == {'media_hash_files':24,'media_hash_bytes':1073741824,
                'native_path_queries':1,'service_starts':0,'provider_calls':0,'gpu_probes':0,
                'browser_runs':0,'downloads':0,'cloud_calls':0,'stage_checkpoints':0}):
        raise BindingError('INVENTORY_AUTHORITY_MISMATCH')


def native_decoder_paths():
    # Query native PATH only; do not execute FFmpeg or touch permanent config.
    script = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop'; @('ffmpeg.exe','ffprobe.exe') | ForEach-Object {$c=Get-Command $_ -CommandType Application -ErrorAction Stop; [pscustomobject]@{name=$_;path=$c.Source}} | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
        capture_output=True,timeout=30)
    if result.returncode: raise BindingError('NATIVE_DECODER_PATH_QUERY_FAILED')
    paths = {}
    for value in json.loads(result.stdout.decode('utf-8-sig','strict')):
        converted = subprocess.check_output(['wslpath','-u',value['path']],text=True,timeout=5).strip()
        path = Path(converted)
        if path.name.lower() not in {'ffmpeg.exe','ffprobe.exe'} or not path.is_file():
            raise BindingError('NATIVE_DECODER_IDENTITY_INVALID')
        paths[path.name.upper().replace('.EXE','_EXE')] = path
    if set(paths) != {'FFMPEG_EXE','FFPROBE_EXE'}: raise BindingError('NATIVE_DECODERS_INCOMPLETE')
    return paths


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--authorization',required=True)
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--execute-inventory',action='store_true')
    args=parser.parse_args()
    if not args.execute_inventory: raise BindingError('EXPLICIT_INVENTORY_FLAG_REQUIRED')
    auth_path=ROOT/args.authorization
    auth=json.loads(auth_path.read_text())
    program_path=ROOT/'reports/authorization-program-v1-local-01.json'
    program=json.loads(program_path.read_text())
    validate_authority(auth,program,candidate=args.candidate,harness_sha=file_hash(__file__))
    if auth.get('program_sha256') != file_hash(program_path): raise BindingError('PROGRAM_HASH_MISMATCH')
    # Candidate object must contain these exact Harness bytes before any target read.
    prefix=subprocess.check_output(['git','rev-parse','--show-prefix'],cwd=ROOT,text=True).strip()
    blob=subprocess.check_output(['git','show',args.candidate+':'+prefix+'tools/v0_s2_bindings.py'],cwd=ROOT)
    if hashlib.sha256(blob).hexdigest()!=file_hash(__file__): raise BindingError('CANDIDATE_HARNESS_MISMATCH')
    directory=ROOT/'reports/v0-s2'/auth['run_id']
    if directory.exists(): raise BindingError('EVIDENCE_SLOT_ALREADY_EXISTS')
    directory.mkdir()
    receipt={'schema_version':'lvw.s2.binding-inventory/1','candidate_sha':args.candidate,
             'authorization_id':auth['authorization_id'],'decision':'NO_GO','stage_pass_claim':False,
             'stage_checkpoint_consumed':False,'service_starts':0,'provider_calls':0}
    try:
        paths={**TARGETS,**native_decoder_paths()}
        receipt['executables']={alias:{'sha256':file_hash(path),'bytes':path.stat().st_size} for alias,path in paths.items()}
        receipt['samples']=sample_inventory(SOURCE)
        receipt['decision']='BINDINGS_COLLECTED_NOT_ACCEPTANCE'
    except Exception as exc:
        receipt['error_code']=str(exc) if isinstance(exc,BindingError) else type(exc).__name__
    finally:
        receipt['finished_at']=datetime.now(timezone.utc).isoformat()
        (directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        auth.update(status='EXPIRED_'+receipt['decision'],terminal_receipt=str((directory/'receipt.json').relative_to(ROOT)))
        auth_path.write_text(json.dumps(auth,indent=2)+'\n')
    print(json.dumps({'decision':receipt['decision'],'stage_checkpoint_consumed':False}))
    return 0 if receipt['decision']=='BINDINGS_COLLECTED_NOT_ACCEPTANCE' else 1


if __name__=='__main__': raise SystemExit(main())
