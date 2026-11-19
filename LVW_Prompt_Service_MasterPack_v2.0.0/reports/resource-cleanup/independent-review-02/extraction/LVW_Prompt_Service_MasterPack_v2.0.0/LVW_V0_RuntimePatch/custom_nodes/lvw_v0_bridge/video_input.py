"""CPU video metadata boundaries and exact sampling coordinates.

Only decoder-reported PTS can become frame evidence. Seek targets are a plan,
never an assertion that a frame exists at that timestamp.
"""
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import re

from .core import BridgeError

MAX_VIDEO_BYTES = 256 * 1024 * 1024
MAX_VIDEO_SECONDS = 60
MAX_SOURCE_PIXELS = 8_294_400
VIDEO_LONG_EDGE = 768
DEFAULT_FRAMES = 4


def invalid(message, subcode="VIDEO_PROBE_INVALID"):
    return BridgeError("MEDIA_INVALID", message, subcode=subcode)


def integer(value):
    if isinstance(value, bool) or len(str(value)) > 32 or not re.fullmatch(r"-?[0-9]+", str(value)):
        raise invalid("expected an integer video field")
    return int(value)


def rational(value):
    try:
        if isinstance(value, bool) or len(str(value)) > 128:
            raise ValueError()
        result = Fraction(str(value))
    except (ValueError, ZeroDivisionError, TypeError, OverflowError) as exc:
        raise invalid("invalid rational video field") from exc
    return result


@dataclass(frozen=True)
class VideoProbe:
    stream_index: int
    width: int
    height: int
    duration: Fraction
    time_base: Fraction
    origin_pts: int

    def seek_targets(self):
        """Midpoints of four equal windows, relative to presentation origin."""
        return tuple(self.duration * Fraction(2 * i + 1, 8) for i in range(DEFAULT_FRAMES))


def validate_probe(document, *, byte_count):
    """Validate bounded ffprobe JSON; metadata tags are intentionally ignored."""
    count = integer(byte_count)
    if count <= 0:
        raise invalid("video file is empty")
    if count > MAX_VIDEO_BYTES:
        raise BridgeError("MEDIA_LIMIT_EXCEEDED", "video byte limit exceeded", subcode="VIDEO_BYTE_LIMIT")
    if not isinstance(document, dict):
        raise invalid("probe must be an object")
    container = document.get("format")
    streams = document.get("streams")
    if not isinstance(container, dict) or not isinstance(streams, list) or len(streams) > 64:
        raise invalid("missing or excessive stream metadata")
    if not {"mov", "mp4"}.intersection(str(container.get("format_name", "")).split(",")):
        raise invalid("only MP4/MOV containers are supported", "VIDEO_CONTAINER_UNSUPPORTED")
    videos = []
    for stream in streams:
        if not isinstance(stream, dict):
            raise invalid("stream metadata must be an object")
        disposition = stream.get("disposition", {})
        if not isinstance(disposition, dict):
            raise invalid("stream disposition must be an object")
        if stream.get("codec_type") == "video" and not disposition.get("attached_pic", 0):
            videos.append(stream)
    if len(videos) != 1:
        raise invalid("exactly one video stream is required")
    stream = videos[0]
    width, height = integer(stream.get("width")), integer(stream.get("height"))
    if width <= 0 or height <= 0:
        raise invalid("invalid source dimensions")
    if width * height > MAX_SOURCE_PIXELS:
        raise BridgeError("MEDIA_LIMIT_EXCEEDED", "source frame pixel limit exceeded", subcode="VIDEO_PIXEL_LIMIT")
    durations = [rational(v) for v in (container.get("duration"), stream.get("duration")) if v is not None]
    if not durations or any(d <= 0 for d in durations):
        raise invalid("positive duration is required")
    duration = max(durations)
    if duration > MAX_VIDEO_SECONDS:
        raise BridgeError("MEDIA_LIMIT_EXCEEDED", "video duration limit exceeded", subcode="VIDEO_DURATION_LIMIT")
    time_base = rational(stream.get("time_base"))
    if time_base <= 0:
        raise invalid("positive time base required")
    origin_pts = integer(stream.get("start_pts"))
    stream_index = integer(stream.get("index"))
    if stream_index < 0:
        raise invalid("invalid stream index")
    return VideoProbe(stream_index, width, height, duration, time_base, origin_pts)


def frame_manifest(probe, decoded_frames):
    """Bind one to four unique source timestamps to normalized image bytes.

    decoded_frames contains (PTS, width, height, normalized_image_bytes).
    Duplicate/nonmonotonic timestamps fail rather than claiming temporal proof.
    """
    if not 1 <= len(decoded_frames) <= DEFAULT_FRAMES:
        raise invalid("one to four decoded frames required", "VIDEO_FRAME_COUNT_INVALID")
    result = []
    previous = None
    for index, (pts_value, width_value, height_value, image) in enumerate(decoded_frames):
        pts = integer(pts_value)
        width, height = integer(width_value), integer(height_value)
        seconds = (pts - probe.origin_pts) * probe.time_base
        if seconds < 0 or seconds > probe.duration or (previous is not None and pts <= previous):
            raise invalid("decoded timestamps are outside the timeline or not increasing", "VIDEO_PTS_INVALID")
        if min(width, height) <= 0 or max(width, height) > VIDEO_LONG_EDGE:
            raise BridgeError("MEDIA_LIMIT_EXCEEDED", "normalized video frame dimension limit exceeded", subcode="VIDEO_FRAME_DIMENSION_LIMIT")
        if not isinstance(image, bytes) or not image:
            raise invalid("normalized frame bytes are missing")
        result.append({"index": index, "pts": pts, "time_base_num": probe.time_base.numerator,
                       "time_base_den": probe.time_base.denominator,
                       "time_seconds": float(seconds), "sha256": sha256(image).hexdigest()})
        previous = pts
    return result
