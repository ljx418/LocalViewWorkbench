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
    attributes=Path(root/'.gitattributes')
    attr_entry=git('ls-tree','--name-only',candidate,'--','.gitattributes')
    attr_content=git('show',candidate+':'+prefix+'.gitattributes') if attr_entry else None
    if ((attributes.exists() or attributes.is_symlink()) != (attr_content is not None)
            or (attr_content is not None and (attributes.is_symlink() or attributes.read_bytes()!=attr_content))):
        raise SealError('PAYLOAD_ATTRIBUTES_MISMATCH')
    cmd_crlf=attr_content is not None and b'*.cmd text eol=crlf' in attr_content.splitlines()
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
    hashes={};blob_hashes={};transforms={}
    for relative in sorted(selected):
        content=git('show',candidate+':'+prefix+relative)
        blob_hashes[relative]=hashlib.sha256(content).hexdigest()
        if relative.endswith('.cmd') and cmd_crlf:
            # Git stores LF for this explicitly frozen text/eol rule; bind the
            # exact CRLF checkout bytes actually executed by Windows instead.
            # No other filter or whitespace normalization is accepted.
            if b'\r' in content:raise SealError('CMD_CANONICAL_BLOB_INVALID:'+relative)
            content=content.replace(b'\n',b'\r\n')
            transforms[relative]='text/eol=crlf'
        digest=hashlib.sha256(content).hexdigest()
        if hashlib.sha256((root/relative).read_bytes()).hexdigest()!=digest:
            raise SealError('PAYLOAD_BYTES_MISMATCH:'+relative)
        hashes[relative]=digest
    return {'candidate_sha':candidate,'execution_artifact_sha256':hashes,
            'git_blob_sha256':blob_hashes,'checkout_transforms':transforms,
            'attributes_sha256':hashlib.sha256(attr_content).hexdigest() if attr_content is not None else None,
            'payload_sha256':hashlib.sha256(''.join(f'{digest}  {path}\n' for path,digest in hashes.items()).encode()).hexdigest()}
