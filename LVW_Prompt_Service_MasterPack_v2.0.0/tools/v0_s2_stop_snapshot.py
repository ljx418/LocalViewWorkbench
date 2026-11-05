"""Durable original-child identities before deliberate native fault injection."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat

from tools.v0_s2_execution_bindings import plain


def prepare(driver,pid,ticks):
    root=plain(Path(driver.evidence['owned_run_root']))
    temporary=plain(root/'temp')
    value={'kind':'OWNED_PRE_STOP_CHILD_SNAPSHOT','run_id':driver.args.run_id,
        'candidate_sha':driver.evidence['candidate_sha'],'authorization_sha256':driver.evidence['authorization_sha256'],
        'root_pid':pid,'root_start_ticks':ticks,'nonce':secrets.token_hex(32)}
    path=temporary/('owned-pre-stop-'+value['nonce']+'.json')
    if os.path.lexists(path):raise ValueError('pre-stop snapshot must be fresh')
    lease={'file':str(path),'identity':value}
    driver.evidence['owned_pre_stop_snapshot']=lease
    encoded=base64.b64encode(json.dumps(value,separators=(',',':')).encode()).decode()
    native=driver._windows_path(str(path))
    quoted="'"+native.replace("'","''")+"'"
    script=("$snapshot=([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"'))|ConvertFrom-Json);"
        "$snapshot|Add-Member -NotePropertyName children -NotePropertyValue @($out);"
        "$bytes=[Text.Encoding]::UTF8.GetBytes(($snapshot|ConvertTo-Json -Depth 8 -Compress));"
        "$saved=[IO.FileStream]::new("+quoted+",[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None,4096,"
        "[IO.FileOptions]::WriteThrough);try{$saved.Write($bytes,0,$bytes.Length);$saved.Flush($true)}finally{$saved.Dispose()};")
    return lease,script


def validate_children(values,pid,root_start_ticks):
    # Compare exact GetProcess births, retaining the separate per-process
    # CIM precision check. An alleged child cannot predate its parent.
    known={pid:root_start_ticks}
    if not isinstance(values,list) or len(values)>16:raise ValueError('descendant denominator invalid')
    for child in values:
        if (not isinstance(child,dict) or set(child)!={'pid','parent_pid','start_ticks','process_start_ticks'}
                or any(type(child[k]) is not int or child[k]<=0 for k in child)
                or child['parent_pid'] not in known or child['pid'] in known
                or child['process_start_ticks']<known[child['parent_pid']]
                or not 0<=child['process_start_ticks']-child['start_ticks']<10):raise ValueError('descendant birth/chain invalid')
        known[child['pid']]=child['process_start_ticks']
    return values


def restore(driver,lease):
    path=plain(Path(lease['file']));fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    try:
        before=os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 0<before.st_size<=65536:raise ValueError('pre-stop snapshot size/type invalid')
        with os.fdopen(fd,'rb',closefd=False) as stream:raw=stream.read(65537)
        after=os.fstat(fd)
        if len(raw)!=before.st_size or any(getattr(before,k)!=getattr(after,k) for k in ['st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns']):
            raise ValueError('pre-stop snapshot changed during read')
    finally:os.close(fd)
    def pairs(rows):
        result={}
        for k,v in rows:
            if k in result:raise ValueError('duplicate snapshot key')
            result[k]=v
        return result
    value=json.loads(raw,object_pairs_hook=pairs)
    if set(value)!={*lease['identity'],'children'} or any(value.get(k)!=v for k,v in lease['identity'].items()):
        raise ValueError('pre-stop snapshot identity mismatch')
    children=validate_children(value['children'],lease['identity']['root_pid'],lease['identity']['root_start_ticks'])
    driver._cleanup_descendants[11434]=children
    driver.evidence['owned_pre_stop_snapshot_sha256']=hashlib.sha256(raw).hexdigest()
    return children
