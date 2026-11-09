"""Adapt the existing pure CPU video kernel without importing the Comfy plugin.

The namespace points at project-owned source, never at an installed Comfy tree.
Only the decoder's pure module dependency graph executes; no plugin __init__,
PromptServer, folder_paths, torch or synthetic replacement modules are loaded.
"""
from __future__ import annotations

import importlib
import importlib.machinery
import json
from pathlib import Path
import shutil
import sys
import types

from .errors import AppError

SOURCE = Path(__file__).resolve().parents[3] / "LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge"
PACKAGE = "lvw_cpu_video_kernel"
if PACKAGE not in sys.modules:
    package = types.ModuleType(PACKAGE)
    package.__path__ = [str(SOURCE)]
    package.__spec__ = importlib.machinery.ModuleSpec(PACKAGE, loader=None, is_package=True)
    sys.modules[PACKAGE] = package
core = importlib.import_module(PACKAGE + ".core")
decoder_module = importlib.import_module(PACKAGE + ".video_decoder")
input_module = importlib.import_module(PACKAGE + ".video_input")
process_module = importlib.import_module(PACKAGE + ".video_process")


def translate(error):
    return AppError(error.code, error.message, status_code=422 if error.code.startswith("MEDIA")
                    or error.code == "PATH_FORBIDDEN" else 503, details=error.details)


class VideoKernel:
    def __init__(self, media_root: Path, temp_root: Path):
        self.media_root, self.temp_root = media_root, temp_root
        temp_root.mkdir(parents=True, exist_ok=True)
        self.ffmpeg = shutil.which("ffmpeg")
        self.ffprobe = shutil.which("ffprobe")

    def tools(self):
        if not self.ffmpeg or not self.ffprobe:
            raise AppError("MODEL_UNAVAILABLE", "本地FFmpeg/ffprobe未就绪；不会自动下载", status_code=503)

    def probe(self, path: Path, size: int):
        self.tools()
        try:
            raw = process_module.run_bounded([
                self.ffprobe, "-v", "error", "-f", "mov", "-enable_drefs", "0",
                "-protocol_whitelist", "file,pipe", "-show_entries",
                "format=format_name,duration:stream=index,codec_type,width,height,time_base,start_pts,duration:stream_disposition=attached_pic",
                "-of", "json", str(path)], timeout_seconds=15, output_limit=256 * 1024)
            return input_module.validate_probe(json.loads(raw.stdout), byte_count=size)
        except core.BridgeError as error:
            raise translate(error) from error
        except (ValueError, UnicodeError) as error:
            raise AppError("MEDIA_INVALID", "视频元数据无效", status_code=422) from error

    def decode(self, path: Path, cancel):
        self.tools()
        decoder = decoder_module.VideoDecoder(input_root=self.media_root, temp_parent=self.temp_root,
                                               ffmpeg=self.ffmpeg, ffprobe=self.ffprobe)
        try:
            return decoder.decode(path.name, cancel=cancel)
        except core.BridgeError as error:
            raise translate(error) from error
