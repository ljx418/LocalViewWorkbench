import asyncio
import json
from pathlib import Path
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

import jsonschema

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import core, video_api
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_request import VideoRequestOwner
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_workbench import project, MAX_BODY_BYTES
from LVW_V0_RuntimePatch.tests.test_s2_video_api import Routes
from LVW_V0_RuntimePatch.tests.test_s2_video_cancel import Frame, Transport

ROOT = Path(__file__).resolve().parents[2]


def fields():
    return dict(natural_zh='人工稿', natural_en='', image_prompt='', video_prompt='',
                tags='中文,tag\n另一项', negative='', edit_instruction='')


class WorkbenchTests(unittest.TestCase):
    def validate(self, result):
        jsonschema.Draft202012Validator(json.loads((ROOT/'contracts/v0-result.schema.json').read_text())).validate(result)

    def test_manual_projection_bypasses_busy_gpu_and_keeps_missing_english(self):
        entered=threading.Event(); release=threading.Event()
        def busy():
            with core._INFERENCE_LOCK:
                entered.set(); release.wait(3)
        thread=threading.Thread(target=busy);thread.start()
        try:
            self.assertTrue(entered.wait(1))
            owner=MagicMock()
            with patch('subprocess.Popen') as spawn:
                value=project({'action':'preview','fields':fields()},owner)
            self.validate(value['result'])
            self.assertEqual('人工稿',value['result']['draft']['natural_zh'])
            self.assertEqual('',value['result']['draft']['natural_en'])
            self.assertEqual(['中文','tag','另一项'],value['result']['draft']['tags'])
            self.assertIn('人工稿',value['txt'])
            self.assertIsNone(value['result']['run_id'])
            owner.completed_result.assert_not_called();spawn.assert_not_called()
        finally:release.set();thread.join(4)
        self.assertFalse(thread.is_alive())

    def test_unicode_character_boundary_and_unknown_fields_fail_closed(self):
        exact=fields();exact['natural_zh']='🎨'*20000
        self.assertEqual(exact['natural_zh'],project({'action':'preview','fields':exact})['result']['draft']['natural_zh'])
        exact['natural_zh']+='🎨'
        with self.assertRaises(core.BridgeError) as error:project({'action':'preview','fields':exact})
        self.assertEqual('MEDIA_LIMIT_EXCEEDED',error.exception.code)
        for body in [None,{'action':'export','fields':fields()},
                     {'action':'preview','fields':{**fields(),'path':'outside'}},
                     {'action':'adopt','run_token':'x','fields':fields()}]:
            with self.subTest(body=body),self.assertRaises(ValueError):project(body)

    def test_adoption_reads_production_request_snapshot_without_new_provider_calls(self):
        class Decoder:
            def decode(self,reference,cancel=None):
                return SimpleNamespace(frames=[Frame()]*4,source_sha256='a'*64,byte_count=100,
                    width=1,height=1,duration_seconds=4.0,
                    manifest=[{'index':i,'pts':1000*i+500,'time_base_num':1,'time_base_den':1000,
                               'time_seconds':i+.5,'sha256':str(i)*64} for i in range(4)])
        transport=Transport(threading.Event())
        owner=VideoRequestOwner(Decoder(),bridge=core.BridgeOwner(transport=transport,encoder=lambda frame:'fixture'),
            tensor_builder=lambda frames:frames,host_preflight=lambda:{},preflight=lambda:{})
        run=owner.run('owned-run','clip.mp4',model=core.DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120)
        self.assertEqual(4,transport.calls)
        value=project({'action':'adopt','run_token':'owned-run'},owner)
        self.validate(value['result'])
        self.assertEqual(run['raw_response'],value['result']['raw_response'])
        self.assertEqual(run['source'],value['result']['source'])
        self.assertEqual('decoded_pts',value['result']['source']['frames'][0]['time_basis'])
        self.assertEqual('model_adopted',value['result']['draft_origin'])
        self.assertEqual('',value['result']['draft']['natural_zh'])
        self.assertEqual(4,transport.calls)
        value['result']['source']['sha256']='b'*64
        self.assertEqual('a'*64,owner.completed_result('owned-run')['source']['sha256'])
        for token in ['wrong','']:
            with self.assertRaises((ValueError,core.BridgeError)):project({'action':'adopt','run_token':token},owner)
        owner.host_preflight=lambda:(_ for _ in ()).throw(core.BridgeError('RESOURCE_BUSY','fixture',subcode='TEST_BUSY'))
        with self.assertRaises(core.BridgeError):
            owner.run('new-run','clip.mp4',model=core.DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120)
        with self.assertRaises(core.BridgeError):project({'action':'adopt','run_token':'owned-run'},owner)
        with self.assertRaises(core.BridgeError):project({'action':'adopt','run_token':'new-run'},owner)
        # A previously adopted client snapshot is an independent copy.
        self.assertEqual('owned-run',value['result']['run_id'])

    def test_public_route_auth_body_limits_and_busy_manual_path(self):
        routes=Routes();server=SimpleNamespace(PromptServer=SimpleNamespace(instance=SimpleNamespace(routes=routes)))
        web=SimpleNamespace(json_response=lambda body,status=200:(status,body))
        class Content:
            def __init__(self,raw,timeout=False):self.raw=raw;self.reads=0;self.timeout=timeout
            async def read(self,count):
                self.reads+=1
                if self.timeout:raise TimeoutError()
                value,self.raw=self.raw[:count],self.raw[count:];return value
        def request(raw,origin='http://127.0.0.1:8188',length=None,timeout=False):
            return SimpleNamespace(remote='127.0.0.1',host='127.0.0.1:8188',content_length=length,
                headers={'Origin':origin,'X-LVW-Control':'local-ui'},content=Content(raw,timeout))
        raw=json.dumps({'action':'preview','fields':fields()},ensure_ascii=False).encode()
        with patch.dict('sys.modules',{'server':server,'aiohttp':SimpleNamespace(web=web)}),patch.object(video_api,'_OWNER',MagicMock()) as owner:
            video_api.register_control_routes();handler=routes.handlers[('POST','/lvw/v0/video/workbench')]
            for req,status in [(request(raw,origin='http://bad.example'),403),(request(raw,length=MAX_BODY_BYTES+1),413)]:
                self.assertEqual(status,asyncio.run(handler(req))[0]);self.assertEqual(0,req.content.reads)
            exact=raw+b' '*(MAX_BODY_BYTES-len(raw))
            status,value=asyncio.run(handler(request(exact)))
            self.assertEqual(200,status);self.validate(value['result']);owner.completed_result.assert_not_called()
            self.assertEqual(413,asyncio.run(handler(request(exact+b' ')))[0])
            self.assertEqual(408,asyncio.run(handler(request(raw,timeout=True)))[0])
            self.assertEqual(400,asyncio.run(handler(request(b'{')))[0])
            self.assertEqual(400,asyncio.run(handler(request(b'{"action":"adopt","run_token":"x","extra":0}')))[0])


if __name__=='__main__':unittest.main()
