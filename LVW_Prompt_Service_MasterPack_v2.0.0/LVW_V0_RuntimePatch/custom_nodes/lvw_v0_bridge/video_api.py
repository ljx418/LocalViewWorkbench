"""Comfy-local integrated video node and scoped control routes."""
import json
import threading
import uuid
from urllib.parse import urlsplit

from .core import BridgeError
from .nodes import _NodeBase
from .video_node import default_video_decoder
from .video_request import VideoRequestOwner

_OWNER = None
_OWNER_GUARD = threading.Lock()


def get_owner():
    global _OWNER
    with _OWNER_GUARD:
        if _OWNER is None:
            _OWNER = VideoRequestOwner(default_video_decoder())
        return _OWNER


def authorize_control(*, peer, host, origin, control):
    """Literal loopback plus matching Origin defeats cross-site/local DNS calls."""
    try:
        local = urlsplit("http://" + host)
        caller = urlsplit(origin)
        valid = (peer in {"127.0.0.1", "::1"} and local.hostname in {"127.0.0.1", "::1"}
                 and local.username is None and local.password is None
                 and caller.scheme == "http" and caller.netloc == local.netloc
                 and caller.path in {"", "/"} and not caller.query and not caller.fragment
                 and control == "local-ui")
    except (ValueError, TypeError):
        valid = False
    if not valid:
        raise BridgeError("ORIGIN_FORBIDDEN", "local same-origin control required", subcode="VIDEO_CONTROL_FORBIDDEN")


class LVWVideoPromptOwner(_NodeBase):
    RETURN_TYPES = ("STRING", "STRING", "STRING")
    RETURN_NAMES = ("raw_response", "suggestion", "metadata")

    def __init__(self, owner=None):
        self.owner = owner

    @classmethod
    def INPUT_TYPES(cls):
        required = {"video_reference":("STRING", {"default":""})}
        required.update(cls._common_inputs())
        return {"required":required}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Requeue means a new run, never a cached model result from an old token.
        return float("nan")

    def analyze(self, video_reference, model="gemma4:26b", user_instruction="", mode="realistic", timeout_seconds=120):
        owner = self.owner or get_owner()
        result = owner.run(uuid.uuid4().hex, video_reference, model=model,
                           user_instruction=user_instruction, mode=mode, timeout_seconds=timeout_seconds)
        metadata = json.dumps({key:value for key,value in result.items() if key not in {"raw_response","suggestion"}},
                              ensure_ascii=False, sort_keys=True)
        raw, suggestion = result["raw_response"], result["suggestion"]
        return {"ui":{"text":[raw,suggestion,metadata]}, "result":(raw,suggestion,metadata)}


def register_control_routes():
    try:
        from server import PromptServer
    except ImportError:
        return False  # Offline module import does not create a server.
    server = getattr(PromptServer, "instance", None)
    if server is None:
        return False
    from aiohttp import web

    def check(request, *, read_only=False):
        origin = request.headers.get("Origin", "")
        if read_only and not origin and request.headers.get("Sec-Fetch-Site") == "same-origin":
            origin = "http://" + request.host
        authorize_control(peer=request.remote, host=request.host,
                          origin=origin, control=request.headers.get("X-LVW-Control", ""))

    def failure(error):
        return web.json_response({"error":{"code":error.code,"message":error.message}},
                                 status=403 if error.code == "ORIGIN_FORBIDDEN" else 409)

    @server.routes.get("/lvw/v0/video/status")
    async def status(request):
        try:
            check(request, read_only=True)
            with _OWNER_GUARD:
                owner = _OWNER
            return web.json_response(owner.current_status() if owner else {"status":"idle","run_token":None,"resource_state":"released"})
        except BridgeError as error:
            return failure(error)

    @server.routes.post("/lvw/v0/video/cancel")
    async def cancel(request):
        try:
            check(request)
            raw = bytearray()
            while len(raw) <= 4096:
                chunk = await request.content.read(4097 - len(raw))
                if not chunk:
                    break
                raw.extend(chunk)
            if len(raw) > 4096:
                raise ValueError("oversized request")
            body = json.loads(raw)
            if (not isinstance(body, dict) or set(body) != {"run_token"}
                    or not isinstance(body["run_token"], str) or not 0 < len(body["run_token"]) <= 128):
                raise ValueError("invalid token")
            with _OWNER_GUARD:
                owner = _OWNER
            if owner is None:
                raise BridgeError("ATTEMPT_STALE", "no video run", subcode="VIDEO_RUN_STALE")
            return web.json_response(owner.cancel(body["run_token"]))
        except BridgeError as error:
            return failure(error)
        except (ValueError, UnicodeError):
            return web.json_response({"error":{"code":"CONTRACT_UNSUPPORTED","message":"bounded run token required"}}, status=400)
    return True
