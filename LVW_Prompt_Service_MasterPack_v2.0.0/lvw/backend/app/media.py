from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path
import re
import uuid

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import AppError
from .models import MediaRef
from .video_kernel import VideoKernel
import asyncio

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_LONG_EDGE = 1024
CHUNK_SIZE = 1024 * 1024
ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}


class MediaStore:
    def __init__(self, root: Path):
        self.root = root / "media"
        self.root.mkdir(parents=True, exist_ok=True)
        self.refs: dict[str, MediaRef] = {}
        self.paths: dict[str, Path] = {}
        self.video = VideoKernel(self.root, root / "video-temp")

    async def ingest(self, upload: UploadFile) -> MediaRef:
        if Path(upload.filename or "").suffix.lower() in {".mp4", ".mov"}:
            return await self.ingest_video(upload)
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await upload.read(CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_BYTES:
                raise AppError("MEDIA_LIMIT_EXCEEDED", "图片不能超过 20 MiB", status_code=422,
                               details={"limit_bytes": MAX_BYTES})
            chunks.append(chunk)
        payload = b"".join(chunks)
        if not payload:
            raise AppError("MEDIA_INVALID", "图片文件为空", status_code=422)
        digest = hashlib.sha256(payload).hexdigest()
        try:
            with Image.open(BytesIO(payload)) as probe:
                fmt = probe.format
                width, height = probe.size
                if fmt not in ALLOWED_FORMATS:
                    raise AppError("MEDIA_INVALID", "仅支持 JPEG、PNG 或 WebP", status_code=422)
                if width * height > MAX_PIXELS:
                    raise AppError("MEDIA_LIMIT_EXCEEDED", "图片不能超过 4000 万像素", status_code=422,
                                   details={"limit_pixels": MAX_PIXELS})
                probe.verify()
            with Image.open(BytesIO(payload)) as source:
                source.load()
                image = ImageOps.exif_transpose(source)
                if image.mode in {"RGBA", "LA"} or "transparency" in image.info:
                    rgba = image.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                    background.alpha_composite(rgba)
                    image = background.convert("RGB")
                else:
                    image = image.convert("RGB")
                image.thumbnail((MAX_LONG_EDGE, MAX_LONG_EDGE), Image.Resampling.LANCZOS)
                media_id = "med_" + uuid.uuid4().hex
                path = self.root / f"{media_id}.png"
                image.save(path, format="PNG", optimize=False)
        except AppError:
            raise
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise AppError("MEDIA_INVALID", "图片无法安全解码", status_code=422) from exc
        display = Path(upload.filename or "image").name
        display = re.sub(r"[\x00-\x1f]", "", display)[:240] or "image"
        ref = MediaRef(
            id=media_id, sha256=digest, kind="image", display_name=display, bytes=total,
            width=width, height=height, duration_seconds=None, source_root_id=None,
            relative_path=None, availability="available", frames=[],
        )
        self.refs[media_id] = ref
        self.paths[media_id] = path
        return ref

    async def ingest_video(self, upload: UploadFile) -> MediaRef:
        media_id = "med_" + uuid.uuid4().hex
        path = self.root / (media_id + Path(upload.filename).suffix.lower())
        total, digest = 0, hashlib.sha256()
        try:
            with path.open("xb") as stream:
                while chunk := await upload.read(CHUNK_SIZE):
                    total += len(chunk)
                    if total > 256 * 1024 * 1024:
                        raise AppError("MEDIA_LIMIT_EXCEEDED", "视频不能超过256 MiB", status_code=422)
                    digest.update(chunk)
                    stream.write(chunk)
            if not total:
                raise AppError("MEDIA_INVALID", "视频文件为空", status_code=422)
            probe = await asyncio.to_thread(self.video.probe, path, total)
            ref = MediaRef(id=media_id, sha256=digest.hexdigest(), kind="video",
                display_name=re.sub(r"[\x00-\x1f]", "", (upload.filename or "video").replace("\\", "/").split("/")[-1])[:240],
                bytes=total, width=probe.width, height=probe.height,
                duration_seconds=float(probe.duration), source_root_id=None,
                relative_path=None, availability="available", frames=[])
            self.refs[media_id], self.paths[media_id] = ref, path
            return ref
        except BaseException:
            path.unlink(missing_ok=True)
            raise

    def get(self, media_id: str) -> tuple[MediaRef, Path]:
        ref = self.refs.get(media_id)
        path = self.paths.get(media_id)
        if ref is None or path is None or not path.is_file():
            raise AppError("MEDIA_INVALID", "找不到已上传的图片", status_code=404)
        return ref, path

    def discard(self, media_id: str) -> None:
        path = self.paths.pop(media_id, None)
        self.refs.pop(media_id, None)
        if path and path.is_file():
            path.unlink()
