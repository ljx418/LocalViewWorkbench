"""LVW V0 bridge ComfyUI registration."""

from .nodes import (LVWControlledImageInput, LVWDraftStateOwner, LVWImagePromptBridge,
                    LVWManualPromptOwner, LVWVideoFramesPromptBridge)
from .video_node import LVWControlledVideoInput

NODE_CLASS_MAPPINGS = {
    "LVWControlledVideoInput": LVWControlledVideoInput,
    "LVWImagePromptBridge": LVWImagePromptBridge,
    "LVWVideoFramesPromptBridge": LVWVideoFramesPromptBridge,
    "LVWManualPromptOwner": LVWManualPromptOwner,
    "LVWControlledImageInput": LVWControlledImageInput,
    "LVWDraftStateOwner": LVWDraftStateOwner,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "LVWControlledVideoInput": "LVW V0 Controlled Video Input",
    "LVWImagePromptBridge": "LVW V0 Image Prompt Bridge",
    "LVWVideoFramesPromptBridge": "LVW V0 Ordered Frames Prompt Bridge",
    "LVWManualPromptOwner": "LVW V0 Manual Prompt Owner",
    "LVWControlledImageInput": "LVW V0 Controlled Image Input",
    "LVWDraftStateOwner": "LVW V0 Draft State Owner",
}

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
