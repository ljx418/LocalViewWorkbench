"""ComfyUI node owners for the LVW V0 loopback bridge."""

from .core import BridgeOwner, DEFAULT_MODEL, MAX_TIMEOUT_SECONDS


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
