"""Comfy public adapter for the controlled local video decoder."""
from io import BytesIO
import json
import os
import shutil

from .core import BridgeError
from .video_decoder import VideoDecoder


def comfy_frames(images):
    try:
        import numpy as np
        import torch
        from PIL import Image
    except ImportError as exc:
        raise BridgeError("MODEL_UNAVAILABLE", "video tensor dependencies unavailable",
                          subcode="VIDEO_TENSOR_DEPENDENCY_UNAVAILABLE") from exc
    values = []
    for raw in images:
        with Image.open(BytesIO(raw)) as image:
            values.append(np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0)
    try:
        return torch.from_numpy(np.stack(values))
    except ValueError as exc:
        raise BridgeError("MEDIA_INVALID", "sampled video frame dimensions differ",
                          subcode="VIDEO_FRAME_SHAPE_MISMATCH") from exc


class LVWControlledVideoInput:
    CATEGORY = "LVW/V0"
    OUTPUT_NODE = True
    RETURN_TYPES = ("IMAGE", "STRING")
    RETURN_NAMES = ("frames", "metadata")
    FUNCTION = "load"

    def __init__(self, decoder=None, tensor_builder=None):
        self.decoder = decoder
        self.tensor_builder = tensor_builder or comfy_frames

    @classmethod
    def INPUT_TYPES(cls):
        return {"required": {"video_reference": ("STRING", {"default": ""})}}

    def load(self, video_reference):
        decoder = self.decoder
        if decoder is None:
            try:
                import folder_paths
            except ImportError as exc:
                raise BridgeError("MODEL_UNAVAILABLE", "Comfy directories unavailable",
                                  subcode="COMFY_INPUT_ROOT_UNAVAILABLE") from exc
            ffprobe = os.environ.get("LVW_FFPROBE_EXE") or shutil.which("ffprobe")
            ffmpeg = os.environ.get("LVW_FFMPEG_EXE") or shutil.which("ffmpeg")
            if not ffprobe or not ffmpeg:
                raise BridgeError("MODEL_UNAVAILABLE", "local FFmpeg and ffprobe are required",
                                  subcode="VIDEO_DECODER_UNAVAILABLE")
            decoder = VideoDecoder(input_root=folder_paths.get_input_directory(),
                                   temp_parent=folder_paths.get_temp_directory(),
                                   ffprobe=ffprobe, ffmpeg=ffmpeg)
        video = decoder.decode(video_reference)
        frames = self.tensor_builder(video.frames)
        metadata = json.dumps({"source_sha256": video.source_sha256, "bytes": video.byte_count,
                               "width": video.width, "height": video.height,
                               "duration_seconds": video.duration_seconds,
                               "sampling": "four temporal window midpoints; first decoded frame at or after each target",
                               "limitations": "Four samples do not establish events between samples or continuous motion.",
                               "frames": video.manifest}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return {"ui": {"text": [metadata]}, "result": (frames, metadata)}
