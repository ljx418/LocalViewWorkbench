"""Bounded streaming upload into Comfy's input root; no model or decoder."""
from hashlib import sha256
import os
from pathlib import Path
import tempfile
import uuid

from .core import BridgeError
from .video_files import reject_redirect
from .video_input import MAX_VIDEO_BYTES


async def receive_video(input_root, extension, chunks, *, max_bytes=MAX_VIDEO_BYTES):
    if extension not in {'.mp4','.mov'}:
        raise BridgeError('MEDIA_INVALID','只支持 MP4/MOV 视频',subcode='VIDEO_EXTENSION_UNSUPPORTED')
    if type(max_bytes) is not int or not 0 < max_bytes <= MAX_VIDEO_BYTES:
        raise ValueError('invalid upload byte cap')
    root=Path(input_root)
    temporary=None;published=None;published_owned=False;success=False
    try:
        reject_redirect(root.lstat())
        root=root.resolve(strict=True)
        descriptor,name=tempfile.mkstemp(prefix='lvw-upload-',suffix='.part',dir=root)
        temporary=Path(name);digest=sha256();count=0
        with os.fdopen(descriptor,'wb') as output:
            async for chunk in chunks:
                if not isinstance(chunk,bytes):raise ValueError('invalid upload chunk')
                count+=len(chunk)
                if count>max_bytes:
                    raise BridgeError('MEDIA_LIMIT_EXCEEDED','视频不能超过 256 MiB',subcode='VIDEO_BYTE_LIMIT')
                output.write(chunk);digest.update(chunk)
        if count==0:
            raise BridgeError('MEDIA_INVALID','视频文件为空',subcode='VIDEO_EMPTY')
        # Atomically claim an opaque destination without overwriting any file.
        # Only publish after the complete bounded stream has been received.
        published=root/('lvw-upload-'+uuid.uuid4().hex+extension)
        os.link(temporary,published)
        published_owned=True
        temporary.unlink();temporary=None
        success=True
        return {'video_reference':published.name,'bytes':count,'sha256':digest.hexdigest(),
                'validation':'uploaded; container, duration and frame checks run before analysis'}
    except OSError as exc:
        raise BridgeError('MEDIA_INVALID','视频上传写入失败',subcode='VIDEO_UPLOAD_IO_FAILED') from exc
    finally:
        cleanup_error=None
        for path in (temporary,published if published_owned and not success else None):
            if path is not None:
                try:path.unlink(missing_ok=True)
                except OSError as exc:
                    cleanup_error=exc
        if cleanup_error is not None:
            raise BridgeError('RESOURCE_RELEASE_PENDING','上传临时文件清理未完成',subcode='VIDEO_UPLOAD_CLEANUP_FAILED') from cleanup_error
