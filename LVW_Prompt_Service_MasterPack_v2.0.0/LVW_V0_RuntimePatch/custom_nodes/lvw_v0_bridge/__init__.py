"""LVW V0 bridge ComfyUI registration."""

from .nodes import LVWImagePromptBridge, LVWManualPromptOwner, LVWVideoFramesPromptBridge

NODE_CLASS_MAPPINGS = {
    "LVWImagePromptBridge": LVWImagePromptBridge,
    "LVWVideoFramesPromptBridge": LVWVideoFramesPromptBridge,
    "LVWManualPromptOwner": LVWManualPromptOwner,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LVWImagePromptBridge": "LVW V0 Image Prompt Bridge",
    "LVWVideoFramesPromptBridge": "LVW V0 Ordered Frames Prompt Bridge",
    "LVWManualPromptOwner": "LVW V0 Manual Prompt Owner",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
