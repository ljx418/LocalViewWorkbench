"""Comfy-local integrated video node and scoped control routes."""
import json
import base64
from io import BytesIO
import threading
import uuid
import asyncio
from urllib.parse import urlsplit

from .core import BridgeError
from .nodes import _NodeBase
from .video_node import default_video_decoder
from .video_request import VideoRequestOwner
from .video_upload import receive_video
from .video_input import MAX_VIDEO_BYTES

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
        return {"required":required, "hidden":{"unique_id":"UNIQUE_ID"}}

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # Requeue means a new run, never a cached model result from an old token.
        return float("nan")

    def analyze(self, video_reference, model="gemma4:26b", user_instruction="", mode="realistic", timeout_seconds=120, unique_id=None):
        owner = self.owner or get_owner()
        def started(token):
            if unique_id is not None:
                from server import PromptServer
                client=getattr(PromptServer.instance,'client_id',None)
                if client is not None:
                    PromptServer.instance.send_sync("lvw.video.started", {"node_id":str(unique_id),"run_token":token},client)
        def preview(token, decoded):
            if unique_id is None:
                return
            from server import PromptServer
            client=getattr(PromptServer.instance,'client_id',None)
            if client is None:return
            from PIL import Image
            images = []
            for image_bytes in decoded.frames:
                with Image.open(BytesIO(image_bytes)) as image:
                    output = BytesIO()
                    image.save(output, format="PNG")
                    images.append("data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii"))
            PromptServer.instance.send_sync("lvw.video.preview", {"node_id":str(unique_id), "run_token":token,
                "images":images, "frames":list(decoded.manifest),
                "limitation":"仅观察四个采样帧，不能证明未采样片段或连续运动。"},client)
        result = owner.run(uuid.uuid4().hex, video_reference, model=model,
                           user_instruction=user_instruction, mode=mode, timeout_seconds=timeout_seconds,
                           preview_hook=preview, state_hook=started)
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

    @server.routes.post('/lvw/v0/video/upload')
    async def upload(request):
        try:
            check(request)
            if request.content_length is not None and request.content_length>MAX_VIDEO_BYTES:
                raise BridgeError('MEDIA_LIMIT_EXCEEDED','视频不能超过 256 MiB',subcode='VIDEO_BYTE_LIMIT')
            extension=request.headers.get('X-LVW-Video-Extension','')
            import folder_paths
            async with asyncio.timeout(60):
                result=await receive_video(folder_paths.get_input_directory(),extension,
                                           request.content.iter_chunked(256*1024))
            return web.json_response(result,status=201)
        except BridgeError as error:
            status=403 if error.code=='ORIGIN_FORBIDDEN' else 413 if error.code=='MEDIA_LIMIT_EXCEEDED' else 400
            return web.json_response({'error':{'code':error.code,'message':error.message}},status=status)
        except TimeoutError:
            return web.json_response({'error':{'code':'MEDIA_INVALID','message':'视频上传超时，请重新选择文件'}},status=408)
    return True
