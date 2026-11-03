"""Local CPU-only four-frame decoder built on run-owned video snapshots."""
from dataclasses import dataclass
from fractions import Fraction
import json
import math
from pathlib import Path
import re

from .video_files import stage_video
from .video_input import VIDEO_LONG_EDGE, frame_manifest, invalid, validate_probe
from .video_process import run_bounded


@dataclass(frozen=True)
class DecodedVideo:
    source_sha256: str
    byte_count: int
    width: int
    height: int
    duration_seconds: float
    frames: tuple
    manifest: tuple
    decoder_backend: str = 'ffmpeg-cli/ffprobe-cli'


def parse_ppm(data):
    """Accept exactly one bounded RGB PPM; reject trailing frames/data."""
    match = re.match(rb"P6\s+([0-9]{1,5})\s+([0-9]{1,5})\s+255\n", data[:128])
    if not match:
        raise invalid("decoder returned an invalid RGB image", "VIDEO_FRAME_INVALID")
    width, height = map(int, match.groups())
    if not 0 < width <= VIDEO_LONG_EDGE or not 0 < height <= VIDEO_LONG_EDGE:
        raise invalid("decoder frame exceeds normalized dimensions", "VIDEO_FRAME_INVALID")
    if len(data) != match.end() + width * height * 3:
        raise invalid("decoder frame is truncated or has trailing data", "VIDEO_FRAME_INVALID")
    return width, height


def parse_timestamp(stderr, probe):
    text = stderr.decode("utf-8", errors="replace")
    bases = re.findall(r"config in time_base:\s*([0-9]+/[0-9]+)", text)
    rows = re.findall(r"\bn:\s*([0-9]+)\s+pts:\s*(-?[0-9]+)\s+pts_time:", text)
    try:
        matching_base = bool(bases) and all(Fraction(base) == probe.time_base for base in bases)
    except (ValueError, ZeroDivisionError):
        matching_base = False
    if not matching_base or len(rows) != 1:
        raise invalid("decoder timestamp evidence missing or ambiguous", "VIDEO_PTS_INVALID")
    if rows[0][0] != "0":
        raise invalid("decoder frame order mismatch", "VIDEO_PTS_INVALID")
    return int(rows[0][1])


class VideoDecoder:
    def __init__(self, *, input_root, temp_parent, ffprobe, ffmpeg, runner=run_bounded, probe_runner=None):
        self.input_root = Path(input_root)
        self.temp_parent = Path(temp_parent)
        # Executable paths are trusted application configuration; media cannot
        # override argv, filters, protocols, output destinations or executable.
        if ffprobe is None and probe_runner is None:raise ValueError('trusted video probe required')
        if probe_runner is not None and not callable(probe_runner):raise ValueError('invalid video probe')
        self.ffprobe = str(ffprobe) if ffprobe is not None else None
        self.ffmpeg = str(ffmpeg)
        self.runner = runner
        self.probe_runner=probe_runner
        self.backend='ffmpeg-cli/'+(getattr(probe_runner,'backend_name','custom-probe') if probe_runner else 'ffprobe-cli')

    def decode(self, reference, *, cancel=None):
        with stage_video(self.input_root, reference, self.temp_parent) as snapshot:
            metadata = self.probe_runner(snapshot.path,cancel=cancel) if self.probe_runner else self.runner([
                self.ffprobe, "-v", "error", "-f", "mov", "-enable_drefs", "0", "-protocol_whitelist", "file,pipe",
                "-show_entries", "format=format_name,duration:stream=index,codec_type,width,height,time_base,start_pts,duration:stream_disposition=attached_pic",
                "-of", "json", str(snapshot.path),
            ], timeout_seconds=15, output_limit=256 * 1024, cancel=cancel)
            try:
                document = json.loads(metadata.stdout)
            except (ValueError, UnicodeError, RecursionError) as exc:
                raise invalid("decoder probe JSON is invalid") from exc
            probe = validate_probe(document, byte_count=snapshot.byte_count)
            images = []
            decoded = []
            for target in probe.seek_targets():
                # Select against original stream ticks. No fps-derived timing or
                # generated timestamp is allowed to enter the frame manifest.
                threshold = probe.origin_pts + math.ceil(target / probe.time_base)
                filters = (f"select='gte(pts,{threshold})*eq(selected_n,0)',"
                           f"scale={VIDEO_LONG_EDGE}:{VIDEO_LONG_EDGE}:force_original_aspect_ratio=decrease,"
                           "format=rgb24,showinfo")
                image = self.runner([
                    self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "info",
                    "-threads", "1", "-filter_threads", "1", "-copyts",
                    "-f", "mov", "-enable_drefs", "0", "-protocol_whitelist", "file,pipe", "-i", str(snapshot.path),
                    "-map", f"0:{probe.stream_index}", "-an", "-sn", "-dn",
                    "-vf", filters, "-frames:v", "1", "-fps_mode", "passthrough",
                    "-threads", "1", "-c:v", "ppm", "-f", "image2pipe", "pipe:1",
                ], timeout_seconds=30, output_limit=3 * 1024 * 1024, cancel=cancel)
                width, height = parse_ppm(image.stdout)
                pts = parse_timestamp(image.stderr, probe)
                if pts < threshold:
                    raise invalid("decoded frame precedes requested window", "VIDEO_PTS_INVALID")
                images.append(image.stdout)
                decoded.append((pts, width, height, image.stdout))
            manifest = frame_manifest(probe, decoded)
            return DecodedVideo(snapshot.source_sha256, snapshot.byte_count, probe.width,
                                probe.height, float(probe.duration), tuple(images), tuple(manifest),self.backend)
