"""Controlled, CPU-only image input and preprocessing for the V0 owner."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath

from .core import BridgeError

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_IMAGE_PIXELS = 40_000_000
IMAGE_LONG_EDGE = 1024
ALLOWED_FORMATS = frozenset({"JPEG", "PNG", "WEBP"})


def validate_image_byte_count(count: int) -> None:
    if not isinstance(count, int) or count < 0:
        raise BridgeError("MEDIA_INVALID", "image byte count is invalid", subcode="IMAGE_BYTE_COUNT_INVALID")
    if count > MAX_IMAGE_BYTES:
        raise BridgeError("MEDIA_LIMIT_EXCEEDED", "image exceeds max_image_bytes", subcode="IMAGE_BYTE_LIMIT")


def validate_image_pixel_count(width: int, height: int) -> None:
    if not isinstance(width, int) or not isinstance(height, int) or width < 1 or height < 1:
        raise BridgeError("MEDIA_INVALID", "image dimensions are invalid", subcode="IMAGE_DIMENSIONS_INVALID")
    if width * height > MAX_IMAGE_PIXELS:
        raise BridgeError("MEDIA_LIMIT_EXCEEDED", "image exceeds max_image_pixels", subcode="IMAGE_PIXEL_LIMIT")


def _safe_candidate(root: Path, reference: str) -> Path:
    if not isinstance(reference, str) or not reference.strip() or "\\" in reference:
        raise BridgeError("PATH_FORBIDDEN", "image reference must be a non-empty relative POSIX path",
                          subcode="IMAGE_REFERENCE_FORBIDDEN")
    relative = PurePosixPath(reference)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise BridgeError("PATH_FORBIDDEN", "image reference must remain inside the input root",
                          subcode="IMAGE_REFERENCE_FORBIDDEN")
    try:
        authority = root.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise BridgeError("PATH_FORBIDDEN", "Comfy input root is unavailable",
                          subcode="IMAGE_INPUT_ROOT_UNAVAILABLE") from exc
    candidate = root.joinpath(*relative.parts)
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise BridgeError("PATH_FORBIDDEN", "symlink image references are forbidden",
                              subcode="IMAGE_REFERENCE_SYMLINK")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(authority)
    except (OSError, RuntimeError, ValueError) as exc:
        raise BridgeError("PATH_FORBIDDEN", "image reference is unavailable or outside the input root",
                          subcode="IMAGE_REFERENCE_FORBIDDEN") from exc
    if not resolved.is_file():
        raise BridgeError("MEDIA_INVALID", "image reference is not a regular file",
                          subcode="IMAGE_NOT_REGULAR_FILE")
    return resolved


@dataclass(frozen=True)
class PreprocessedImage:
    image: object
    metadata: dict


class ControlledImageOwner:
    """Resolve one Comfy input-relative image and preprocess it without disk output."""

    def __init__(self, input_root: Path):
        self.input_root = Path(input_root)

    def preprocess(self, reference: str) -> PreprocessedImage:
        try:
            from PIL import Image, ImageOps, UnidentifiedImageError
            import numpy as np
            import torch
        except ImportError as exc:
            raise BridgeError("MODEL_UNAVAILABLE", "Pillow, numpy, and torch are required",
                              subcode="IMAGE_PREPROCESSOR_UNAVAILABLE") from exc

        path = _safe_candidate(self.input_root, reference)
        try:
            byte_count = path.stat().st_size
            validate_image_byte_count(byte_count)
            raw = path.read_bytes()
            validate_image_byte_count(len(raw))
            if len(raw) != byte_count:
                raise BridgeError("MEDIA_INVALID", "image changed while being read",
                                  subcode="IMAGE_READ_RACE")
            source_hash = sha256(raw).hexdigest()
            source = Image.open(BytesIO(raw))
            actual_format = (source.format or "").upper()
            if actual_format not in ALLOWED_FORMATS:
                raise BridgeError("MEDIA_INVALID", "actual image format must be JPEG, PNG, or WebP",
                                  subcode="IMAGE_FORMAT_UNSUPPORTED")
            original_size = list(source.size)
            validate_image_pixel_count(*source.size)
            source.load()
            oriented = ImageOps.exif_transpose(source)
            oriented_size = list(oriented.size)

            alpha_composited = oriented.mode in {"RGBA", "LA"} or (
                oriented.mode == "P" and "transparency" in oriented.info
            )
            if alpha_composited:
                rgba = oriented.convert("RGBA")
                white = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
                white.alpha_composite(rgba)
                processed = white.convert("RGB")
            else:
                processed = oriented.convert("RGB")

            resized = max(processed.size) > IMAGE_LONG_EDGE
            if resized:
                processed.thumbnail((IMAGE_LONG_EDGE, IMAGE_LONG_EDGE), Image.Resampling.LANCZOS)
            array = np.asarray(processed, dtype=np.float32) / 255.0
            tensor = torch.from_numpy(array.copy()).unsqueeze(0)
            metadata = {
                "source_sha256": source_hash,
                "output_rgb_sha256": sha256(processed.tobytes()).hexdigest(),
                "source_bytes": len(raw),
                "actual_format": actual_format,
                "original_dimensions": original_size,
                "oriented_dimensions": oriented_size,
                "output_dimensions": list(processed.size),
                "exif_transpose": original_size != oriented_size,
                "exif_strategy": "applied_before_limits" if original_size != oriented_size else "not_required",
                "alpha_strategy": "white_background" if alpha_composited else "not_applicable",
                "resize_strategy": "lanczos_long_edge_1024" if resized else "not_required",
            }
            return PreprocessedImage(tensor, metadata)
        except BridgeError:
            raise
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            raise BridgeError("MEDIA_INVALID", "image bytes are corrupt or undecodable",
                              subcode="IMAGE_DECODE_FAILED") from exc
