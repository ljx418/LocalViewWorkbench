"""Bounded read-only binding inventory; execution needs a program child receipt."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import re
from email.parser import BytesParser

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path('/mnt/c/workSpace/videoWorkLine/testSource')
TARGETS = {
    'COMFY_MAIN':Path('/mnt/c/ComfyUI-aki-v2/ComfyUI/main.py'),
    'COMFY_PYTHON':Path('/mnt/c/ComfyUI-aki-v2/python/python.exe'),
    'OLLAMA_EXE':Path('/mnt/c/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe'),
}
PACKAGE_BUDGET={'metadata_hash_files':129,'metadata_hash_bytes':536870912,
                'target_processes':0,'service_starts':0,'provider_calls':0,'gpu_probes':0,
                'browser_runs':0,'downloads':0,'cloud_calls':0,'stage_checkpoints':0}


class BindingError(ValueError): pass


def file_hash(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        while chunk := stream.read(1024*1024): value.update(chunk)
    return value.hexdigest()


def sample_inventory(root, selection=None):
    """Hash up to 24 allowed media files, <=256MiB each and <=1GiB total."""
    root = Path(root).resolve(strict=True)
    candidates = []
    for visited,path in enumerate(root.rglob('*')):
        if visited >= 4096: raise BindingError('SAMPLE_TREE_SCAN_BUDGET_EXCEEDED')
        if path.suffix.lower() in {'.png','.jpg','.jpeg','.webp','.mp4','.mov'}:
            candidates.append(path)
            if selection is None and len(candidates) > 24: raise BindingError('SAMPLE_INVENTORY_COUNT_OUT_OF_SCOPE')
    candidates.sort()
    if selection is not None:
        validate_sample_selection(selection)
        selected=[]
        for kind,extensions in [('image',{'.png','.jpg','.jpeg','.webp'}),('video',{'.mp4','.mov'})]:
            matching=[path for path in candidates if path.suffix.lower() in extensions]
            count=selection[kind]
            if len(matching)<count:raise BindingError('DECLARED_SAMPLE_SELECTION_UNAVAILABLE')
            selected.extend(matching[:count])
        candidates=sorted(selected)
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


def validate_sample_selection(selection):
    if (not isinstance(selection,dict) or set(selection)!={'image','video'}
            or any(type(value) is not int or value < 1 for value in selection.values())
            or sum(selection.values())>24):
        raise BindingError('SAMPLE_SELECTION_INVALID')


def validate_authority(auth, program, *, candidate, harness_sha, package_mode=False):
    if 'sample_selection' in auth:validate_sample_selection(auth['sample_selection'])
    if not (program.get('status') == 'ACTIVE'
            and program.get('authorization_id') == 'AUTH-PROGRAM-V1-LOCAL-01'
            and 'V0-S2' in program.get('stages',[])
            and auth.get('status') == 'ACTIVE_ONE_SHOT'
            and auth.get('source_program_authorization') == program['authorization_id']
            and auth.get('stage_id') == 'V0-S2'
            and auth.get('scope') == ('READ_ONLY_NATIVE_DECODER_PACKAGE_INVENTORY' if package_mode else 'READ_ONLY_BINDING_INVENTORY')
            and isinstance(auth.get('run_id'),str) and re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,79}',auth['run_id'])
            and auth.get('candidate_sha') == candidate
            and auth.get('harness_sha256') == harness_sha
            and auth.get('budget') == (PACKAGE_BUDGET if package_mode else {'media_hash_files':24,'media_hash_bytes':1073741824,
                'native_path_queries':1,'service_starts':0,'provider_calls':0,'gpu_probes':0,
                'browser_runs':0,'downloads':0,'cloud_calls':0,'stage_checkpoints':0})):
        raise BindingError('INVENTORY_AUTHORITY_MISMATCH')


def bundled_decoder_paths(root=Path('/mnt/c/ComfyUI-aki-v2')):
    """Check named tool locations only; never walk Python or model trees."""
    if not Path(root).is_dir(): raise BindingError('BUNDLED_DECODER_ROOT_MISSING')
    locations=('', 'ffmpeg/bin', 'ffmpeg', 'tools/ffmpeg/bin', 'tools/ffmpeg',
               'tools', 'ComfyUI', 'python', 'python/Scripts', 'python/Library/bin')
    for relative in locations:
        directory=Path(root)/relative
        cursor=Path(root)
        for part in Path(relative).parts:
            cursor=cursor/part
            if cursor.is_symlink():raise BindingError('NATIVE_DECODER_IDENTITY_INVALID')
        paths={key:directory/name for key,name in [('FFMPEG_EXE','ffmpeg.exe'),('FFPROBE_EXE','ffprobe.exe')]}
        if all(path.is_file() for path in paths.values()):
            if any(path.is_symlink() for path in paths.values()):raise BindingError('NATIVE_DECODER_IDENTITY_INVALID')
            return paths
    raise BindingError('BUNDLED_DECODER_NAMED_PATHS_MISSING')


def native_decoder_paths():
    # Query native PATH only; do not execute FFmpeg or touch permanent config.
    script = "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference='Stop'; @('ffmpeg.exe','ffprobe.exe') | ForEach-Object {$c=Get-Command $_ -CommandType Application -ErrorAction Stop; [pscustomobject]@{name=$_;path=$c.Source}} | ConvertTo-Json -Compress"
    result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
        capture_output=True,timeout=30)
    if result.returncode:
        try:return bundled_decoder_paths()
        except BindingError as exc:
            if str(exc) != 'BUNDLED_DECODER_NAMED_PATHS_MISSING':raise
            return installed_decoder_paths()
    paths = {}
    for value in json.loads(result.stdout.decode('utf-8-sig','strict')):
        converted = subprocess.check_output(['wslpath','-u',value['path']],text=True,timeout=5).strip()
        path = Path(converted)
        if path.name.lower() not in {'ffmpeg.exe','ffprobe.exe'} or not path.is_file():
            raise BindingError('NATIVE_DECODER_IDENTITY_INVALID')
        paths[path.name.upper().replace('.EXE','_EXE')] = path
    if set(paths) != {'FFMPEG_EXE','FFPROBE_EXE'}: raise BindingError('NATIVE_DECODERS_INCOMPLETE')
    return paths


def installed_decoder_paths(*, direct=None, winget=None):
    """Existing FFmpeg installation metadata only; no recursive disk search."""
    if direct is None:
        direct=[Path('/mnt/c/ffmpeg/bin'),Path('/mnt/c/tools/ffmpeg/bin'),
                Path('/mnt/c/Program Files/ffmpeg/bin'),
                Path('/mnt/c/Users/Administrator/scoop/apps/ffmpeg/current/bin')]
    if winget is None:winget=Path('/mnt/c/Users/Administrator/AppData/Local/Microsoft/WinGet/Packages')
    directories=list(direct)
    if winget.is_dir():
        packages=list(winget.glob('Gyan.FFmpeg*'))
        if len(packages)>16:raise BindingError('INSTALLED_DECODER_METADATA_LIMIT')
        for package in packages:
            if package.is_symlink():raise BindingError('NATIVE_DECODER_IDENTITY_INVALID')
            builds=list(package.glob('ffmpeg-*'))
            if len(builds)>16:raise BindingError('INSTALLED_DECODER_METADATA_LIMIT')
            directories.extend(build/'bin' for build in builds)
    for directory in directories:
        if directory.is_symlink() or any(p.is_symlink() for p in directory.parents):
            raise BindingError('NATIVE_DECODER_IDENTITY_INVALID')
        pair={key:directory/name for key,name in [('FFMPEG_EXE','ffmpeg.exe'),('FFPROBE_EXE','ffprobe.exe')]}
        if all(path.is_file() for path in pair.values()):
            if any(path.is_symlink() for path in pair.values()):raise BindingError('NATIVE_DECODER_IDENTITY_INVALID')
            return pair
    raise BindingError('NATIVE_DECODER_INSTALLATION_NOT_FOUND')


def native_package_inventory(python_home):
    """Read only two named decoder packages; do not import or execute them."""
    root=Path(python_home).resolve(strict=True);site=root/'Lib/site-packages'
    files=[];total=0
    def record(path):
        nonlocal total
        path=Path(path)
        if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
            raise BindingError('NATIVE_PACKAGE_REDIRECT_FORBIDDEN')
        path.resolve(strict=True).relative_to(root)
        before=path.stat();size=before.st_size
        if len(files)>=PACKAGE_BUDGET['metadata_hash_files'] or total+size>PACKAGE_BUDGET['metadata_hash_bytes']:
            raise BindingError('NATIVE_PACKAGE_HASH_BUDGET_EXCEEDED')
        digest=hashlib.sha256();count=0
        with path.open('rb') as stream:
            while chunk:=stream.read(min(1024*1024,PACKAGE_BUDGET['metadata_hash_bytes']-total-count+1)):
                count+=len(chunk)
                if total+count>PACKAGE_BUDGET['metadata_hash_bytes']:raise BindingError('NATIVE_PACKAGE_HASH_BUDGET_EXCEEDED')
                digest.update(chunk)
        after=path.stat()
        if count!=size or (before.st_size,before.st_mtime_ns,before.st_ino)!=(after.st_size,after.st_mtime_ns,after.st_ino):
            raise BindingError('NATIVE_PACKAGE_CHANGED_DURING_HASH')
        total+=count
        alias='COMFY_PYTHON_HOME/'+path.relative_to(root).as_posix()
        files.append({'alias':alias,'bytes':count,'sha256':digest.hexdigest()})
        return alias
    record(root/'python.exe')
    packages={}
    for name,folder,pattern in [('av','av','av-*.dist-info/METADATA'),
                                ('imageio-ffmpeg','imageio_ffmpeg','imageio_ffmpeg-*.dist-info/METADATA')]:
        for directory in (site/folder,site/'av.libs'):
            if directory.is_symlink():raise BindingError('NATIVE_PACKAGE_REDIRECT_FORBIDDEN')
        metadata=sorted(site.glob(pattern))
        if len(metadata)>1:raise BindingError('NATIVE_PACKAGE_DISTRIBUTION_AMBIGUOUS')
        info={'entry_present':(site/folder/'__init__.py').is_file(),'version':None,'native_artifacts':[]}
        if metadata:
            if metadata[0].stat().st_size>1024*1024:raise BindingError('NATIVE_PACKAGE_METADATA_LIMIT')
            record(metadata[0]);message=BytesParser().parsebytes(metadata[0].read_bytes())
            info['version']=message.get('Version')
            if (message.get('Name','').lower().replace('_','-')!=name
                    or not re.fullmatch(r'[0-9][A-Za-z0-9.+-]{0,63}',info['version'] or '')):
                raise BindingError('NATIVE_PACKAGE_METADATA_INVALID')
        if info['entry_present']:record(site/folder/'__init__.py')
        if (site/folder).is_dir():
            for index,path in enumerate((site/folder).rglob('*')):
                if index>=1024:raise BindingError('NATIVE_PACKAGE_TREE_LIMIT')
                if path.suffix.lower() in {'.pyd','.dll','.exe'} and path.is_file():info['native_artifacts'].append(record(path))
        if name=='av' and (site/'av.libs').is_dir():
            for index,path in enumerate((site/'av.libs').iterdir()):
                if index>=128:raise BindingError('NATIVE_PACKAGE_TREE_LIMIT')
                if path.suffix.lower()=='.dll' and path.is_file():info['native_artifacts'].append(record(path))
        packages[name]=info
    return {'packages':packages,'files':files,'bytes_hashed':total,'native_compatibility_verified':False}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--authorization',required=True)
    parser.add_argument('--candidate',required=True)
    parser.add_argument('--execute-inventory',action='store_true')
    parser.add_argument('--execute-package-inventory',action='store_true')
    args=parser.parse_args()
    if args.execute_inventory==args.execute_package_inventory: raise BindingError('ONE_EXPLICIT_INVENTORY_MODE_REQUIRED')
    auth_path=ROOT/args.authorization
    auth=json.loads(auth_path.read_text())
    program_path=ROOT/'reports/authorization-program-v1-local-01.json'
    program=json.loads(program_path.read_text())
    validate_authority(auth,program,candidate=args.candidate,harness_sha=file_hash(__file__),package_mode=args.execute_package_inventory)
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
        if args.execute_package_inventory:
            receipt['native_decoder_packages']=native_package_inventory(TARGETS['COMFY_PYTHON'].parent)
            receipt['decision']='NATIVE_PACKAGES_INVENTORIED_NOT_COMPATIBILITY'
        else:
            receipt['executables']={}
            for alias,path in TARGETS.items():
                receipt['executables'][alias]={'sha256':file_hash(path),'bytes':path.stat().st_size}
            receipt['samples']=sample_inventory(SOURCE,auth.get('sample_selection'))
            for alias,path in native_decoder_paths().items():
                receipt['executables'][alias]={'sha256':file_hash(path),'bytes':path.stat().st_size}
            receipt['decision']='BINDINGS_COLLECTED_NOT_ACCEPTANCE'
    except Exception as exc:
        receipt['error_code']=str(exc) if isinstance(exc,BindingError) else type(exc).__name__
    finally:
        receipt['finished_at']=datetime.now(timezone.utc).isoformat()
        (directory/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        auth.update(status='EXPIRED_'+receipt['decision'],terminal_receipt=str((directory/'receipt.json').relative_to(ROOT)))
        auth_path.write_text(json.dumps(auth,indent=2)+'\n')
    print(json.dumps({'decision':receipt['decision'],'stage_checkpoint_consumed':False}))
    return 0 if receipt['decision'] in {'BINDINGS_COLLECTED_NOT_ACCEPTANCE','NATIVE_PACKAGES_INVENTORIED_NOT_COMPATIBILITY'} else 1


if __name__=='__main__': raise SystemExit(main())
