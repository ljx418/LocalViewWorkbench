"""LVW V0 bridge ComfyUI registration."""

from .nodes import LVWImagePromptBridge, LVWVideoFramesPromptBridge

NODE_CLASS_MAPPINGS = {
    "LVWImagePromptBridge": LVWImagePromptBridge,
    "LVWVideoFramesPromptBridge": LVWVideoFramesPromptBridge,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LVWImagePromptBridge": "LVW V0 Image Prompt Bridge",
    "LVWVideoFramesPromptBridge": "LVW V0 Ordered Frames Prompt Bridge",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
