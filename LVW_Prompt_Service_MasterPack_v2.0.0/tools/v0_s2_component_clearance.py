"""Recompute directed-run resource closure; authorization expiry is separate."""
import hashlib
import json
import os
import stat
from pathlib import Path

SCOPE='DIRECTED_BROWSER_COMPONENT_DEPENDENCIES_NOT_FULL_STAGE_SEAL'


def raw_record(path):
    path=Path(path)
    if not path.is_absolute() or any(p.is_symlink() for p in (path,*path.parents)) or path.resolve(strict=True)!=path:
        raise ValueError('clearance record redirect forbidden')
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size>16*1024*1024:raise ValueError('clearance record not bounded/plain')
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(16*1024*1024+1)
        after=os.fstat(fd)
        if len(raw)!=before.st_size or any(getattr(before,k)!=getattr(after,k) for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']):
            raise ValueError('clearance record changed during read')
        return raw
    finally:os.close(fd)


def document(path):return json.loads(raw_record(path))


def digest(path):return hashlib.sha256(raw_record(path)).hexdigest()


def native_clean(value):
    if (value.get('proven') is not True or type(value.get('final_target_listener_count')) is not int or value.get('final_target_listener_count')!=0
            or type(value.get('owned_count')) is not int or not 0<=value['owned_count']<=2):return False
    listeners=value.get('owned_listener_terminal_states',[]);wrappers=value.get('owned_wrapper_terminal_states',[])
    if (len(wrappers)!=value['owned_count'] or len(listeners)>2
            or any(r.get('terminal_absent') is not True or r.get('unknown_descendants_absent') is not True for r in listeners)
            or any(r.get('exited') is not True or r.get('native_wrapper_absent') is not True for r in wrappers)):return False
    pending=value.get('http_workers_pending')
    if not isinstance(pending,dict) or not pending or any(type(v) is not int or v!=0 for v in pending.values()):return False
    workers=value.get('sampler_workers',[])
    return len(workers)<=2 and all(r.get('proven') is True and r.get('native_worker_absent') is True
        and r.get('receipt',{}).get('owned_gpu_query_exited') is True for r in workers)


def resource_proof(directory,terminal,child):
    directory=Path(directory)
    if (terminal.get('kind')!=SCOPE or terminal.get('stage_pass_claim') is not False
            or terminal.get('stage_checkpoint_consumed') is not False
            or terminal.get('authorization_sha256')!=digest(directory/'claimed-child.json')
            or any(terminal.get(k)!=child.get(k) for k in ['run_id','candidate_sha'])):return False
    commands=list(directory.glob('metadata-*.command.json'));results=list(directory.glob('metadata-*.result.json'))
    if len(commands)!=len(results) or any(document(p).get('command_terminal') is not True for p in results):return False
    lease_path=directory/'default-root-lease.json'
    if not lease_path.exists():
        # No runtime can start before its fresh root is registered. Metadata
        # helpers must be terminal; an unregistered leftover root is uncertainty.
        return (not terminal.get('runtime_evidence') and 'browser' not in terminal and 'cleanup' not in terminal
            and not list(directory.glob('lvw-s2-*')))
    lease=document(lease_path);root=Path(lease['root'])
    if (root.parent!=directory or not root.name.startswith('lvw-s2-default-') or os.path.lexists(root)
            or lease.get('run_id')!=child['run_id'] or lease.get('candidate_sha')!=child['candidate_sha']
            or lease.get('authorization_sha256')!=digest(directory/'claimed-child.json')):return False
    proof=terminal
    if 'cleanup' not in proof:
        failure=directory/'default-preparation-failure.json'
        if not failure.exists():return False
        proof=document(failure)
        if any(proof.get(k)!=child.get(k) for k in ['run_id','candidate_sha']):return False
    if not native_clean(proof.get('cleanup',{})):return False
    browser=terminal.get('browser')
    if browser is not None:
        independent=browser.get('independent_cleanup',{})
        if (browser.get('browser_cleanup_proven') is not True or type(browser.get('callbacks_pending')) is not int or browser.get('callbacks_pending')!=0
                or browser.get('node_original_terminal') is not True
                or independent.get('decision')!='BROWSER_CLEANUP_PROVEN'
                or any(independent.get(k) is not True for k in ['browser_original_absent','group_empty','profile_absent'])
                or browser.get('linux_temp_cleanup',{}).get('proven') is not True):return False
    archive=proof.get('archive',{})
    if archive.get('proven') is not True or archive.get('manifest_file')!='default-raw/ARCHIVE_MANIFEST.json':return False
    manifest=directory/archive['manifest_file']
    if digest(manifest)!=archive.get('manifest_sha256'):return False
    value=document(manifest)
    return all(value.get(k)==child.get(k) for k in ['run_id','candidate_sha']) and value.get('authorization_sha256')==digest(directory/'claimed-child.json')


def write_clearance(directory):
    directory=Path(directory);child=document(directory/'claimed-child.json');terminal=document(directory/'terminal.json')
    try:safe=resource_proof(directory,terminal,child)
    except Exception:safe=False
    result={'kind':'DIRECTED_RESOURCE_CLEARANCE_NOT_STAGE_ACCEPTANCE','run_id':child['run_id'],'candidate_sha':child['candidate_sha'],
        'child_sha256':digest(directory/'claimed-child.json'),'terminal_sha256':digest(directory/'terminal.json'),
        'safe_for_next_runtime':safe,'stage_pass_claim':False}
    with (directory/'runtime-clearance.json').open('x') as output:output.write(json.dumps(result,sort_keys=True)+'\n');output.flush();os.fsync(output.fileno())
    return result


def require_clearance(directory):
    directory=Path(directory);value=document(directory/'runtime-clearance.json')
    child=document(directory/'claimed-child.json');terminal=document(directory/'terminal.json')
    if (value.get('kind')!='DIRECTED_RESOURCE_CLEARANCE_NOT_STAGE_ACCEPTANCE' or value.get('safe_for_next_runtime') is not True
            or value.get('stage_pass_claim') is not False or value.get('run_id')!=directory.name
            or value.get('candidate_sha')!=child.get('candidate_sha')
            or value.get('child_sha256')!=digest(directory/'claimed-child.json') or value.get('terminal_sha256')!=digest(directory/'terminal.json')
            or not resource_proof(directory,terminal,child)):raise ValueError('directed runtime resource cleanup remains unproven; finite recovery required')
