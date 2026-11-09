"""Provider grammar must express parser bounds; real failed output stays failed."""
import copy
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator,ValidationError

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import core


class ResponseBoundTests(unittest.TestCase):
    def content(self,video):
        value={'observations':['a red square'],'inferences':[],'unknowns':[],'prompt':'a red square','tags':['red']}
        if video:value['change']='baseline frame'
        return value

    def parse(self,value,video):
        raw=json.dumps({'done':True,'done_reason':'stop','message':{'content':json.dumps(value)}})
        return core.parse_response(raw,instruction='analyze this frame',user_instruction='',video=video)

    def test_exact_and_one_over_item_bounds_match_real_parser_for_images_and_video(self):
        for video in (False,True):
            schema=core.VIDEO_FRAME_RESPONSE_SCHEMA if video else core.IMAGE_RESPONSE_SCHEMA
            validator=Draft202012Validator(schema)
            for field,limit in [('observations',400),('inferences',400),('unknowns',400),('tags',100)]:
                with self.subTest(video=video,field=field):
                    value=self.content(video);value[field]=['x'*limit]
                    validator.validate(value);self.parse(value,video)
                    value[field]=['x'*(limit+1)]
                    with self.assertRaises(ValidationError):validator.validate(value)
                    with self.assertRaises(core.BridgeError) as error:self.parse(value,video)
                    self.assertEqual('SCHEMA_ARRAY_LIMIT',error.exception.details['subcode'])

    def test_captured_failed_vfr_output_is_rejected_by_both_grammar_and_parser(self):
        path=Path(__file__).resolve().parents[2]/'reports/v0-s2/response-bounds-correction-01/failed-response.json'
        receipt=json.loads(path.read_bytes());raw=receipt['raw_response'];content=json.loads(json.loads(raw)['message']['content'])
        self.assertGreater(max(receipt['observation_lengths']),400)
        with self.assertRaises(ValidationError):Draft202012Validator(core.VIDEO_FRAME_RESPONSE_SCHEMA).validate(content)
        with self.assertRaises(core.BridgeError):core.parse_response(raw,instruction='test',user_instruction='',video=True)

    def test_outgoing_payload_uses_bounded_schema_without_raising_token_context_or_calls(self):
        instruction=core._request_instruction(video=True,frame_index=0,previous_observations=[],user_instruction='describe colors')
        payload=core.build_chat_payload(model=core.DEFAULT_MODEL,encoded_image='synthetic',instruction=instruction,video=True)
        self.assertEqual(400,payload['format']['properties']['observations']['items']['maxLength'])
        self.assertEqual(100,payload['format']['properties']['tags']['items']['maxLength'])
        self.assertEqual(2048,payload['options']['num_ctx']);self.assertEqual(768,payload['options']['num_predict'])
        self.assertIn('at most 400 characters',instruction);self.assertEqual(1,instruction.count('describe colors'))
        self.assertEqual(0,payload['keep_alive'])


if __name__=='__main__':unittest.main()
