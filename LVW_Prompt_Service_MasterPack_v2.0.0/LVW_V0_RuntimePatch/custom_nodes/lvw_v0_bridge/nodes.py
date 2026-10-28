"""ComfyUI node owners for the LVW V0 loopback bridge."""

import json

from .core import BridgeOwner, DEFAULT_MODEL, MAX_TIMEOUT_SECONDS
from .manual import MANUAL_ACTIONS, ManualDraftOwner


class _NodeBase:
    CATEGORY = "LVW/V0"
    OUTPUT_NODE = True
    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("raw_response", "suggestion")
    FUNCTION = "analyze"

    def __init__(self, transport=None, encoder=None):
        self._owner = BridgeOwner(transport=transport, encoder=encoder)

    @staticmethod
    def _common_inputs():
        return {
            "model": ([DEFAULT_MODEL], {"default": DEFAULT_MODEL}),
            "user_instruction": ("STRING", {"default": "", "multiline": True}),
            "mode": (["documentary", "realistic", "scifi", "science", "cinematic", "stylized"], {"default": "realistic"}),
            "timeout_seconds": ("INT", {"default": MAX_TIMEOUT_SECONDS, "min": 1, "max": MAX_TIMEOUT_SECONDS, "step": 1}),
        }


class LVWImagePromptBridge(_NodeBase):
    """One bounded image -> raw local-model response plus machine suggestion."""

    @classmethod
    def INPUT_TYPES(cls):
        required = {"image": ("IMAGE",)}
        required.update(cls._common_inputs())
        return {"required": required}

    def analyze(self, image, model=DEFAULT_MODEL, user_instruction="", mode="realistic", timeout_seconds=MAX_TIMEOUT_SECONDS):
        raw, suggestion = self._owner.analyze_image(image, model=model, user_instruction=user_instruction,
                                                    mode=mode, timeout_seconds=timeout_seconds)
        return {"ui": {"text": [raw, suggestion]}, "result": (raw, suggestion)}


class LVWVideoFramesPromptBridge(_NodeBase):
    """One-to-four ordered, already-bounded frames; one model call per frame."""

    @classmethod
    def INPUT_TYPES(cls):
        required = {"frames": ("IMAGE",)}
        required.update(cls._common_inputs())
        return {"required": required}

    def analyze(self, frames, model=DEFAULT_MODEL, user_instruction="", mode="realistic", timeout_seconds=MAX_TIMEOUT_SECONDS):
        raw, suggestion = self._owner.analyze_video(frames, model=model, user_instruction=user_instruction,
                                                    mode=mode, timeout_seconds=timeout_seconds)
        return {"ui": {"text": [raw, suggestion]}, "result": (raw, suggestion)}


class LVWManualPromptOwner:
    """Standalone pure-CPU manual draft, copy, and export output node."""

    CATEGORY = "LVW/V0"
    OUTPUT_NODE = True
    RETURN_TYPES = ("STRING",) * 9
    RETURN_NAMES = ("natural_zh", "natural_en", "image_prompt", "video_prompt", "tags_json",
                    "negative", "edit_instruction", "payload", "status")
    FUNCTION = "process"

    def __init__(self, owner=None):
        self._owner = owner or ManualDraftOwner()

    @classmethod
    def INPUT_TYPES(cls):
        multiline = {"default": "", "multiline": True}
        return {"required": {
            "natural_zh": ("STRING", multiline),
            "natural_en": ("STRING", multiline),
            "image_prompt": ("STRING", multiline),
            "video_prompt": ("STRING", multiline),
            "tags": ("STRING", {"default": "", "multiline": True}),
            "negative": ("STRING", multiline),
            "edit_instruction": ("STRING", multiline),
            "action": (list(MANUAL_ACTIONS), {"default": "preview_json"}),
            "filename": ("STRING", {"default": "lvw-manual"}),
        }}

    def process(self, natural_zh="", natural_en="", image_prompt="", video_prompt="",
                tags="", negative="", edit_instruction="", action="preview_json",
                filename="lvw-manual"):
        draft, payload, status = self._owner.execute(
            action=action, filename=filename, natural_zh=natural_zh, natural_en=natural_en,
            image_prompt=image_prompt, video_prompt=video_prompt, tags=tags,
            negative=negative, edit_instruction=edit_instruction,
        )
        outputs = draft.outputs()
        result = (outputs["natural_zh"], outputs["natural_en"], outputs["image_prompt"],
                  outputs["video_prompt"], json.dumps(outputs["tags"], ensure_ascii=False),
                  outputs["negative"], outputs["edit_instruction"], payload, status)
        return {"ui": {"text": [status, payload]}, "result": result}
