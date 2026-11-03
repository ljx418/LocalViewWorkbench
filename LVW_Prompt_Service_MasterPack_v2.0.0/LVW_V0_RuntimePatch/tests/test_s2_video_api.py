import asyncio
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import NODE_CLASS_MAPPINGS, video_api
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError


class Routes:
    def __init__(self): self.handlers = {}
    def get(self, path): return self.route("GET", path)
    def post(self, path): return self.route("POST", path)
    def route(self, method, path):
        def register(function): self.handlers[(method,path)] = function; return function
        return register


class Owner:
    def __init__(self): self.cancelled = []; self.runs = []
    def current_status(self): return {"run_token":"current", "status":"running"}
    def cancel(self, token):
        if token != "current": raise BridgeError("ATTEMPT_STALE", "stale", subcode="TEST_STALE")
        self.cancelled.append(token); return {"status":"cancelling","resource_state":"releasing"}
    def run(self, token, reference, **kwargs):
        self.runs.append((token,reference,kwargs))
        return {"raw_response":"raw", "suggestion":"{}", "run_token":token,"frames":[],"cancel_epoch":0}


class ApiTests(unittest.TestCase):
    def test_origin_dns_remote_peer_and_header_fail_closed(self):
        good = dict(peer="127.0.0.1",host="127.0.0.1:8188",origin="http://127.0.0.1:8188",control="local-ui")
        video_api.authorize_control(**good)
        for key,value in [("peer","192.168.1.2"),("host","localhost:8188"),("origin","http://other.example"),
                          ("origin",""),("control",""),("origin","http://127.0.0.1:8188/extra")]:
            with self.subTest(key=key,value=value), self.assertRaises(BridgeError):
                video_api.authorize_control(**{**good,key:value})

    def test_registered_integrated_node_uses_one_request_owner_and_fresh_tokens(self):
        owner = Owner(); node = NODE_CLASS_MAPPINGS["LVWVideoPromptOwner"](owner=owner)
        for _ in range(2):
            output = node.analyze("clip.mp4")
            self.assertEqual(("raw", "{}"), output["result"][:2])
        self.assertEqual(2, len({run[0] for run in owner.runs}))
        self.assertTrue(all(run[1] == "clip.mp4" for run in owner.runs))

    def test_registered_routes_drive_current_owner_and_reject_invalid_requests(self):
        routes = Routes(); owner = Owner()
        fake_server = SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(routes=routes)))
        web = SimpleNamespace(json_response=lambda body,status=200: (status,body))
        class Content:
            def __init__(self, raw): self.raw = raw
            async def read(self, count):
                value, self.raw = self.raw[:count], self.raw[count:]; return value
        def request(body=b'', origin="http://127.0.0.1:8188"):
            return SimpleNamespace(remote="127.0.0.1",host="127.0.0.1:8188",
                headers={"Origin":origin,"X-LVW-Control":"local-ui"},content=Content(body))
        with patch.dict("sys.modules", {"server":fake_server,"aiohttp":SimpleNamespace(web=web)}), patch.object(video_api,"_OWNER",owner):
            self.assertTrue(video_api.register_control_routes())
            cancel = routes.handlers[("POST","/lvw/v0/video/cancel")]
            status = routes.handlers[("GET","/lvw/v0/video/status")]
            self.assertEqual("current", asyncio.run(status(request()))[1]["run_token"])
            self.assertEqual(403, asyncio.run(cancel(request(b'{}',origin="http://other.example")))[0])
            self.assertEqual(400, asyncio.run(cancel(request(b'x'*4097)))[0])
            self.assertEqual(400, asyncio.run(cancel(request(b'{"run_token":"current","path":"/bad"}')))[0])
            self.assertEqual(409, asyncio.run(cancel(request(b'{"run_token":"old"}')))[0])
            self.assertEqual(200, asyncio.run(cancel(request(b'{"run_token":"current"}')))[0])
        self.assertEqual(["current"], owner.cancelled)

    def test_started_and_preview_events_are_session_only_pngs(self):
        events = []
        class PreviewOwner(Owner):
            def run(self, token, reference, **kwargs):
                kwargs["state_hook"](token)
                ppm = b"P6\n1 1\n255\n" + b"abc"
                kwargs["preview_hook"](token, SimpleNamespace(frames=[ppm]*4,
                    manifest=[{"index":i,"time_seconds":i} for i in range(4)]))
                return super().run(token, reference, **kwargs)
        server = SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(
            send_sync=lambda event,value: events.append((event,value)))))
        with patch.dict("sys.modules", {"server":server}):
            NODE_CLASS_MAPPINGS["LVWVideoPromptOwner"](owner=PreviewOwner()).analyze("clip.mp4", unique_id="42")
        self.assertEqual(["lvw.video.started","lvw.video.preview"], [e[0] for e in events])
        self.assertEqual(events[0][1]["run_token"],events[1][1]["run_token"])
        self.assertEqual("42",events[1][1]["node_id"])
        self.assertEqual(4,len(events[1][1]["images"]))
        self.assertTrue(all(image.startswith("data:image/png;base64,iVBOR") for image in events[1][1]["images"]))


if __name__ == "__main__": unittest.main()
