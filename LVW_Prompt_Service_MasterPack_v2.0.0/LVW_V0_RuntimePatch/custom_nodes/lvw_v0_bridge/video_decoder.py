"""Local CPU-only bounded decoder: up to four unique source timestamps."""
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


def empty_selection(result,probe):
    # Exit zero alone is insufficient. Require the configured timestamp basis,
    # zero showinfo frames and the decoder's explicit empty-output witness.
    # -xerror below makes actual decode failures fail before this branch.
    if result.stdout or result.returncode!=0:return False
    text=result.stderr.decode('utf-8',errors='replace')
    bases=re.findall(r"config in time_base:\s*([0-9]+/[0-9]+)",text)
    try:valid=bool(bases) and all(Fraction(base)==probe.time_base for base in bases)
    except (ValueError,ZeroDivisionError):valid=False
    return valid and not re.search(r"\bn:\s*[0-9]+\s+pts:",text) and 'Output file is empty, nothing was encoded' in text


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
            def window(target):
                # Select against original stream ticks. No fps-derived timing or
                # generated timestamp is allowed to enter the frame manifest.
                threshold = probe.origin_pts + math.ceil(target / probe.time_base)
                filters = (f"select='gte(pts,{threshold})*eq(selected_n,0)',"
                           f"scale={VIDEO_LONG_EDGE}:{VIDEO_LONG_EDGE}:force_original_aspect_ratio=decrease,"
                           "format=rgb24,showinfo")
                image = self.runner([
                    self.ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "info", "-xerror",
                    "-threads", "1", "-filter_threads", "1", "-copyts",
                    "-f", "mov", "-enable_drefs", "0", "-protocol_whitelist", "file,pipe", "-i", str(snapshot.path),
                    "-map", f"0:{probe.stream_index}", "-an", "-sn", "-dn",
                    "-vf", filters, "-frames:v", "1", "-fps_mode", "passthrough",
                    "-threads", "1", "-c:v", "ppm", "-f", "image2pipe", "pipe:1",
                ], timeout_seconds=30, output_limit=3 * 1024 * 1024, cancel=cancel)
                if empty_selection(image,probe):return None
                width, height = parse_ppm(image.stdout)
                pts = parse_timestamp(image.stderr, probe)
                if pts < threshold:
                    raise invalid("decoded frame precedes requested window", "VIDEO_PTS_INVALID")
                return (pts,width,height,image.stdout)
            for target in probe.seek_targets():
                frame=window(target)
                if frame is None:
                    if not decoded:
                        # No frame at/after the earliest midpoint means later
                        # midpoints cannot add samples. Use the actual first
                        # source frame, never a copied frame or invented PTS.
                        first=window(Fraction(0))
                        if first is not None:decoded.append(first);images.append(first[3])
                    break
                if decoded and frame[0]==decoded[-1][0]:
                    if frame[1:]!=decoded[-1][1:]:raise invalid('same PTS produced different image bytes','VIDEO_PTS_INVALID')
                    continue # Two targets selected one actual frame: count it once.
                if decoded and frame[0]<decoded[-1][0]:raise invalid('decoder timestamps moved backward','VIDEO_PTS_INVALID')
                decoded.append(frame);images.append(frame[3])
            manifest = frame_manifest(probe, decoded)
            return DecodedVideo(snapshot.source_sha256, snapshot.byte_count, probe.width,
                                probe.height, float(probe.duration), tuple(images), tuple(manifest),self.backend)
