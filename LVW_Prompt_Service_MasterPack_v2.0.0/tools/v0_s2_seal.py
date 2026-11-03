"""Bind the complete execution payload to a committed candidate before launch."""
import hashlib
from pathlib import Path
import re
import subprocess


class SealError(ValueError):
    pass


def seal_candidate(root, candidate, relative_paths):
    root=Path(root).resolve(strict=True)
    if not re.fullmatch('[0-9a-f]{40}',candidate):
        raise SealError('CANDIDATE_SHA_INVALID')
    def git(*args):
        result=subprocess.run(['git',*args],cwd=root,capture_output=True,timeout=60)
        if result.returncode:raise SealError('CANDIDATE_GIT_OBJECT_UNAVAILABLE')
        return result.stdout
    prefix=git('rev-parse','--show-prefix').decode().strip()
    selected=set()
    for relative in relative_paths:
        path=Path(relative)
        if path.is_absolute() or '..' in path.parts or not path.parts or '\\' in str(relative):
            raise SealError('PAYLOAD_PATH_INVALID')
        cursor=root
        for part in path.parts:
            cursor=cursor/part
            if cursor.is_symlink():raise SealError('PAYLOAD_SYMLINK_FORBIDDEN')
        target=root/path
        if not target.exists() or target.is_symlink():raise SealError('PAYLOAD_PATH_INVALID')
        candidates=[target] if target.is_file() else list(target.rglob('*'))
        local=set()
        for file in candidates:
            if '__pycache__' in file.relative_to(root).parts:continue
            if file.is_symlink():raise SealError('PAYLOAD_SYMLINK_FORBIDDEN')
            if file.is_file():local.add(file.relative_to(root).as_posix())
        stored=git('ls-tree','-r','--full-name','--name-only','-z',candidate,'--',relative)
        committed={entry.decode('utf-8')[len(prefix):] for entry in stored.split(b'\0') if entry}
        if local != committed or not local:
            raise SealError('PAYLOAD_INVENTORY_MISMATCH')
        selected.update(local)
    if not selected:raise SealError('EMPTY_PAYLOAD')
    hashes={}
    for relative in sorted(selected):
        content=git('show',candidate+':'+prefix+relative)
        digest=hashlib.sha256(content).hexdigest()
        if hashlib.sha256((root/relative).read_bytes()).hexdigest()!=digest:
            raise SealError('PAYLOAD_BYTES_MISMATCH')
        hashes[relative]=digest
    return {'candidate_sha':candidate,'execution_artifact_sha256':hashes,
            'payload_sha256':hashlib.sha256(''.join(f'{digest}  {path}\n' for path,digest in hashes.items()).encode()).hexdigest()}
