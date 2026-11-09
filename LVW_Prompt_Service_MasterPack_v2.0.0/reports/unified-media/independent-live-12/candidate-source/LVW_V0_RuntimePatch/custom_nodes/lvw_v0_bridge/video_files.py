"""Run-owned video snapshots; never pass a user path directly to a decoder."""
from contextlib import contextmanager
from dataclasses import dataclass
from hashlib import sha256
import os
import errno
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile

from .core import BridgeError
from .video_input import MAX_VIDEO_BYTES


def forbidden():
    return BridgeError("PATH_FORBIDDEN", "video reference must be a regular local file inside the input root",
                       subcode="VIDEO_REFERENCE_FORBIDDEN")


def reject_redirect(info):
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise forbidden()


def resolve_video(root, reference):
    if (not isinstance(reference, str) or not reference or "\\" in reference
            or ":" in reference or "\x00" in reference):
        raise forbidden()
    parts = reference.split("/")
    if PurePosixPath(reference).is_absolute() or any(p in {"", ".", ".."} for p in parts):
        raise forbidden()
    if Path(reference).suffix.lower() not in {".mp4", ".mov"}:
        raise BridgeError("MEDIA_INVALID", "video extension must be MP4 or MOV", subcode="VIDEO_EXTENSION_UNSUPPORTED")
    root = Path(root)
    try:
        reject_redirect(root.lstat())
        authority = root.resolve(strict=True)
        current = root
        for part in parts:
            current = current / part
            reject_redirect(current.lstat())
        resolved = current.resolve(strict=True)
        resolved.relative_to(authority)
        if not stat.S_ISREG(resolved.stat().st_mode):
            raise forbidden()
        return resolved
    except (OSError, ValueError, RuntimeError) as exc:
        if isinstance(exc, BridgeError):
            raise
        raise forbidden() from exc


@dataclass(frozen=True)
class VideoSnapshot:
    path: Path
    source_sha256: str
    byte_count: int


@contextmanager
def stage_video(input_root, reference, temp_parent, *, max_bytes=MAX_VIDEO_BYTES):
    """Bounded immutable-to-the-run copy, deleted on success and every failure.

    temp_parent is a trusted application configuration, never a media input.
    The optional lower byte cap supports constrained tests, not higher limits.
    """
    if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or not 0 < max_bytes <= MAX_VIDEO_BYTES:
        raise ValueError("invalid snapshot byte cap")
    source = resolve_video(input_root, reference)
    owned = None
    descriptor = None
    try:
        descriptor = os.open(source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0))
        before = os.fstat(descriptor)
        reject_redirect(before)
        if not stat.S_ISREG(before.st_mode):
            raise forbidden()
        # Re-resolve after opening; a renamed/replaced entry cannot silently bind
        # metadata from one file to the contents of another.
        check = resolve_video(input_root, reference).stat()
        if (before.st_dev, before.st_ino) != (check.st_dev, check.st_ino):
            raise forbidden()
        if before.st_size <= 0:
            raise BridgeError("MEDIA_INVALID", "video file is empty", subcode="VIDEO_EMPTY")
        if before.st_size > max_bytes:
            raise BridgeError("MEDIA_LIMIT_EXCEEDED", "video byte limit exceeded", subcode="VIDEO_BYTE_LIMIT")
        owned = Path(tempfile.mkdtemp(prefix="lvw-video-", dir=Path(temp_parent)))
        destination = owned / ("source" + source.suffix.lower())
        digest = sha256()
        count = 0
        with destination.open("xb") as output:
            while True:
                chunk = os.read(descriptor, min(1024 * 1024, max_bytes - count + 1))
                if not chunk:
                    break
                count += len(chunk)
                if count > max_bytes:
                    raise BridgeError("MEDIA_LIMIT_EXCEEDED", "video grew beyond byte limit", subcode="VIDEO_BYTE_LIMIT")
                output.write(chunk)
                digest.update(chunk)
        after = os.fstat(descriptor)
        if count != before.st_size or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise BridgeError("MEDIA_INVALID", "video changed while being copied", subcode="VIDEO_READ_RACE")
        os.close(descriptor)
        descriptor = None
        yield VideoSnapshot(destination, digest.hexdigest(), count)
    except OSError as exc:
        code = "DISK_FULL" if exc.errno == errno.ENOSPC else "MEDIA_INVALID"
        raise BridgeError(code, "video snapshot I/O failed", subcode="VIDEO_SNAPSHOT_IO_FAILED") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if owned is not None:
            try:
                shutil.rmtree(owned)
            except OSError as exc:
                raise BridgeError("RESOURCE_RELEASE_PENDING", "video temporary cleanup failed",
                                  subcode="VIDEO_SNAPSHOT_CLEANUP_FAILED") from exc
