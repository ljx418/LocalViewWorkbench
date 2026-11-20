#!/usr/bin/env python3
"""Lossless historical process-tree archive; verify before removing exact files.

Never follows symlinks or archives application data/dependencies. Restore is
allowed only into a new/empty directory, never into a running checkout.
"""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import stat
import subprocess
import tarfile

PACK = Path(__file__).resolve().parents[1]
REPO = PACK.parent
SELECTORS = {'combined-raw', 'candidate-source', 'extraction', 'pytest-temp', 'pytest-tmp',
             'pytest-recheck-tmp', 'pytest-recheck-temp', 'final-pytest-temp', 'recheck-pytest-temp', 'recheck-pytest-tmp'}
CATALOG = PACK / 'archives/history-2026-11-20/catalog.json'
ARCHIVE = CATALOG.parent / 'process-artifacts.tar.gz'


def verify(catalog_path=CATALOG):
    catalog = json.loads(catalog_path.read_text())
    archive = catalog_path.parent / catalog['archive']
    if hashlib.sha256(archive.read_bytes()).hexdigest() != catalog['archive_sha256']:
        raise ValueError('ARCHIVE_HASH_MISMATCH')
    expected = {r['path']: r for r in catalog['files']}
    if len(expected) != len(catalog['files']): raise ValueError('DUPLICATE_PATH')
    seen = set()
    with tarfile.open(archive, 'r:gz') as tar:
        for member in tar:
            if not member.isfile() or member.name not in expected or member.name in seen:
                raise ValueError('UNEXPECTED_MEMBER')
            row = expected[member.name]
            if member.size != row['size']: raise ValueError('SIZE_MISMATCH')
            h = hashlib.sha256()
            with tar.extractfile(member) as stream:
                while chunk := stream.read(1024 * 1024): h.update(chunk)
            if h.hexdigest() != row['sha256']: raise ValueError('MEMBER_HASH_MISMATCH')
            seen.add(member.name)
    if seen != set(expected): raise ValueError('MISSING_MEMBER')
    return catalog


def create():
    if CATALOG.exists() or ARCHIVE.exists(): raise ValueError('ARCHIVE_ALREADY_EXISTS')
    dirty = set(subprocess.check_output(['git','diff','--name-only'],cwd=REPO,text=True).splitlines())
    entries = []
    for record in subprocess.check_output(['git','ls-files','-s','-z'],cwd=REPO).split(b'\0'):
        if not record: continue
        metadata, rawpath = record.split(b'\t',1); mode, blob, stage = metadata.decode().split()
        name = rawpath.decode(); path = Path(name)
        if (not name.startswith(PACK.name + '/reports/') or mode not in {'100644','100755'}
                or not SELECTORS.intersection(path.parts)
                or name.startswith(PACK.name + '/reports/resource-cleanup/') or name in dirty): continue
        current = REPO / path
        if current.resolve() != current or not stat.S_ISREG(current.lstat().st_mode): continue
        entries.append((name, blob, mode))
    ARCHIVE.parent.mkdir(parents=True,exist_ok=True)
    rows=[]
    with ARCHIVE.open('xb') as output, gzip.GzipFile(filename='',mode='wb',fileobj=output,mtime=0) as compressed, tarfile.open(fileobj=compressed,mode='w|') as tar:
        for name, blob, mode in entries:
            payload = (REPO/name).read_bytes()
            git_hash=hashlib.sha1(b'blob '+str(len(payload)).encode()+b'\0'+payload).hexdigest()
            if git_hash != blob: raise ValueError('WORKTREE_CHANGED:'+name)
            sha=hashlib.sha256(payload).hexdigest(); info=tarfile.TarInfo(name)
            info.size=len(payload);info.mode=0o755 if mode=='100755' else 0o644;info.mtime=0
            tar.addfile(info,io.BytesIO(payload));rows.append({'path':name,'git_blob':blob,'sha256':sha,'size':len(payload)})
            if len(rows)%1000==0:print('archived',len(rows),flush=True)
    catalog={'schema_version':'lvw.history-archive/1','archive':ARCHIVE.name,
             'archive_sha256':hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
             'source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
             'scope':'historical process fixtures and duplicate source trees; canonical reports/logs/signatures/contracts retained',
             'logical_bytes':sum(r['size'] for r in rows),'files':rows}
    CATALOG.write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    verify()
    # Verify every working file again before unlinking any selected file.
    for row in rows:
        q=REPO/row['path']
        if q.resolve()!=q or hashlib.sha256(q.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('WORKTREE_CHANGED_BEFORE_REMOVAL:'+row['path'])
    for row in rows:(REPO/row['path']).unlink()
    print(json.dumps({'archived_files':len(rows),'logical_bytes':catalog['logical_bytes'],'compressed_bytes':ARCHIVE.stat().st_size,'catalog':str(CATALOG)},ensure_ascii=False))


def restore(destination, catalog_path=CATALOG):
    catalog=verify(catalog_path)
    destination=destination.absolute()
    if destination.resolve()!=destination or destination.exists() and any(destination.iterdir()):
        raise ValueError('RESTORE_REQUIRES_NEW_EMPTY_DIRECTORY')
    for row in catalog['files']:
        name=Path(row['path'])
        if name.is_absolute() or '..' in name.parts: raise ValueError('UNSAFE_ARCHIVE_PATH')
    destination.mkdir(parents=True,exist_ok=True)
    with tarfile.open(catalog_path.parent/catalog['archive'],'r:gz') as tar:
        for member in tar:
            target=destination/member.name;target.parent.mkdir(parents=True,exist_ok=True)
            with tar.extractfile(member) as source,target.open('xb') as out:
                while chunk:=source.read(1024*1024):out.write(chunk)
            target.chmod(member.mode & 0o777)
    print(json.dumps({'restored_files':len(catalog['files']),'destination':str(destination)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['create','verify','restore'])
    parser.add_argument('--destination',type=Path)
    args=parser.parse_args()
    if args.action=='create':create()
    elif args.action=='verify':print(json.dumps({'verified_files':len(verify()['files'])}))
    elif not args.destination:parser.error('restore requires --destination')
    else:restore(args.destination)
