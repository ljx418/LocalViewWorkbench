from __future__ import annotations

import hashlib
import json
import os
import re
import uuid
from collections.abc import MutableMapping
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path

from fastapi import UploadFile
from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import AppError
from .models import MediaRef
from .revisions import canonical_json
from .video_kernel import VideoKernel
import asyncio

MAX_BYTES = 20 * 1024 * 1024
MAX_PIXELS = 40_000_000
MAX_LONG_EDGE = 1024
CHUNK_SIZE = 1024 * 1024
ALLOWED_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
MEDIA_SCOPE = "media.upload"
# The name of an owned copy is a generated basename of the media root:
# it never carries a directory, a traversal or an absolute path.
OWNED_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class _OwnedMedia(MutableMapping):
    """The owned media of a store, read through the repository.

    The mapping keeps the shape that the existing service uses: the
    media of a round is read by its identifier and a missing identifier
    is a missing key.  The values are read from the repository, so they
    survive a restart and they are never a stale in memory copy.
    """

    def __init__(self, store: "MediaStore", attribute: str):
        self._store = store
        self._attribute = attribute
        self._cache: dict[str, object] = {}

    def __getitem__(self, media_id: str):
        if media_id in self._cache:
            return self._cache[media_id]
        loaded = self._store.load(media_id)
        if loaded is None:
            raise KeyError(media_id)
        ref, path = loaded
        value = ref if self._attribute == "ref" else path
        self._cache[media_id] = value
        return value

    def __setitem__(self, media_id: str, value) -> None:
        self._cache[media_id] = value

    def __delitem__(self, media_id: str) -> None:
        self._cache.pop(media_id, None)

    def __iter__(self):
        return iter(self._cache)

    def __len__(self) -> int:
        return len(self._cache)


class MediaStore:
    """The owned media of the service.

    The store stages and validates the copy of an upload and it
    consumes the repository: the metadata of the upload and the identity
    of the owned copy are durable, and the file is staged first and
    registered afterwards, so a durable row never references a discarded
    staging copy.
    """

    def __init__(self, root: Path, repository):
        self.root = root / "media"
        self.root.mkdir(parents=True, exist_ok=True)
        self.repository = repository
        self.database = repository.database
        self.refs: MutableMapping[str, MediaRef] = _OwnedMedia(self, "ref")
        self.paths: MutableMapping[str, Path] = _OwnedMedia(self, "path")
        self.video = VideoKernel(self.root, root / "video-temp")

    # -- the owned copy ---------------------------------------------------
    def _owned_copy(self, stored_name: str) -> Path:
        """The path of an owned copy, refused when it is not one."""
        if (not isinstance(stored_name, str) or not stored_name
                or not OWNED_NAME.match(stored_name)
                or stored_name in (".", "..") or "/" in stored_name
                or "\\" in stored_name or "\x00" in stored_name):
            raise AppError("MEDIA_INVALID", "媒体副本的名称无效", status_code=404)
        path = self.root / stored_name
        if path.parent != self.root:
            raise AppError("MEDIA_INVALID", "媒体副本不在受控目录内", status_code=404)
        if path.is_symlink() or not path.is_file():
            raise AppError("MEDIA_INVALID", "媒体副本不可用", status_code=404)
        return path

    # -- the upload --------------------------------------------------------
    async def ingest(self, upload: UploadFile, *, idempotency_key: str) -> MediaRef:
        """Register one controlled upload durably and keep its owned copy."""
        staged = await (self._stage_video(upload)
                        if Path(upload.filename or "").suffix.lower() in {".mp4", ".mov"}
                        else self._stage_image(upload))
        try:
            return self._register(staged, idempotency_key)
        except BaseException:
            self._remove_staged(staged)
            raise

    async def _stage_image(self, upload: UploadFile) -> dict:
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
                stored_name = media_id + ".png"
                staged_path = self.root / (".staging-" + stored_name)
                final_path = self.root / stored_name
                try:
                    image.save(staged_path, format="PNG", optimize=False)
                except BaseException:
                    staged_path.unlink(missing_ok=True)
                    raise
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
        return {"ref": ref, "staged_path": staged_path, "final_path": final_path,
                "stored_name": stored_name,
                "stored_sha256": _file_sha256(staged_path),
                "stored_bytes": staged_path.stat().st_size}

    async def _stage_video(self, upload: UploadFile) -> dict:
        media_id = "med_" + uuid.uuid4().hex
        suffix = Path(upload.filename).suffix.lower()
        stored_name = media_id + suffix
        staged_path = self.root / (".staging-" + stored_name)
        final_path = self.root / stored_name
        total, digest = 0, hashlib.sha256()
        try:
            with staged_path.open("xb") as stream:
                while chunk := await upload.read(CHUNK_SIZE):
                    total += len(chunk)
                    if total > 256 * 1024 * 1024:
                        raise AppError("MEDIA_LIMIT_EXCEEDED", "视频不能超过256 MiB", status_code=422)
                    digest.update(chunk)
                    stream.write(chunk)
            if not total:
                raise AppError("MEDIA_INVALID", "视频文件为空", status_code=422)
            probe = await asyncio.to_thread(self.video.probe, staged_path, total)
        except BaseException:
            staged_path.unlink(missing_ok=True)
            raise
        ref = MediaRef(id=media_id, sha256=digest.hexdigest(), kind="video",
            display_name=re.sub(r"[\x00-\x1f]", "", (upload.filename or "video").replace("\\", "/").split("/")[-1])[:240],
            bytes=total, width=probe.width, height=probe.height,
            duration_seconds=float(probe.duration), source_root_id=None,
            relative_path=None, availability="available", frames=[])
        return {"ref": ref, "staged_path": staged_path, "final_path": final_path,
                "stored_name": stored_name,
                "stored_sha256": digest.hexdigest(),
                "stored_bytes": total}

    # -- the durable registration -----------------------------------------
    def _register(self, staged: dict, idempotency_key: str) -> MediaRef:
        """Register the staged upload in ONE write transaction."""
        ref = staged["ref"]
        payload_sha256 = ref.sha256
        with self.database.write() as connection:
            existing = self.repository.find_idempotency(connection, MEDIA_SCOPE, idempotency_key)
            if existing is not None:
                if existing["payload_sha256"] != payload_sha256:
                    raise AppError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他媒体", status_code=409)
                # The replay returns the ORIGINAL media and the new
                # uncommitted copy is removed: the committed copy and
                # every unrelated file are never touched.
                staged["staged_path"].unlink(missing_ok=True)
                original = self._load(connection, existing["response_ref"])
                if original is None:
                    raise AppError("MEDIA_INVALID", "找不到已上传的图片", status_code=404)
                return original[0]
            os.replace(staged["staged_path"], staged["final_path"])
            staged["registered"] = True
            self.repository.insert_media(connection, ref.id, ref.sha256, ref.kind,
                                        canonical_json(ref.model_dump(mode="json")),
                                        datetime.now(timezone.utc).isoformat(timespec="microseconds"))
            self.repository.insert_media_blob(connection, ref.id, staged["stored_name"],
                                              staged["stored_sha256"], staged["stored_bytes"])
            self.repository.record_idempotency(connection, MEDIA_SCOPE, idempotency_key,
                                               payload_sha256, ref.id)
        return ref

    @staticmethod
    def _remove_staged(staged: dict) -> None:
        """Remove the new uncommitted copy and nothing else."""
        for key in ("final_path", "staged_path"):
            path = staged.get(key)
            if path is None:
                continue
            try:
                path.unlink()
            except OSError:
                pass

    # -- the reads ----------------------------------------------------------
    def load(self, media_id: str) -> tuple[MediaRef, Path] | None:
        """The media and its owned copy, or None."""
        with self.database.read() as connection:
            return self._load(connection, media_id)

    def _load(self, connection, media_id: str) -> tuple[MediaRef, Path] | None:
        row = self.repository.get_media(connection, media_id)
        if row is None:
            return None
        blob = self.repository.get_media_blob(connection, media_id)
        if blob is None:
            raise AppError("MEDIA_INVALID", "媒体副本不可用", status_code=404)
        path = self._owned_copy(blob["stored_name"])
        ref = MediaRef(**json.loads(row["metadata_json"]))
        return ref, path

    def get(self, media_id: str) -> tuple[MediaRef, Path]:
        loaded = self.load(media_id)
        if loaded is None:
            raise AppError("MEDIA_INVALID", "找不到已上传的图片", status_code=404)
        return loaded

    def discard(self, media_id: str) -> None:
        """Forget the cached entries of a media.

        A registered copy is never deleted through this method: the
        committed canonical copy of a media is owned by the repository and
        the file of an upload is removed only by the registration that
        failed.
        """
        self.refs.pop(media_id, None)
        self.paths.pop(media_id, None)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
