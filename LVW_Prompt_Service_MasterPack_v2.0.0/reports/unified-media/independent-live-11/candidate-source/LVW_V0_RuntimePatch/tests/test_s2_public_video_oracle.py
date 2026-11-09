import json
import unittest

from tools.v0_s2_checkpoint_oracles import EvidenceError,public_video_oracle


def history():
    raw={'frame_raw_responses':[json.dumps({'model':'local-model','done':True,'message':{'content':'synthetic'}}) for _ in range(4)]}
    metadata={'source_sha256':'a'*64,'run_token':'b'*32,'cancel_epoch':0,'frames':[
        {'index':i,'pts':1000+2000*i,'time_base_num':1,'time_base_den':1000,'time_seconds':1+2*i,'sha256':str(i)*64}
        for i in range(4)]}
    return {'fresh':{'status':{'status_str':'success'},'prompt':[0,'fresh',{'1':{'class_type':'LVWVideoPromptOwner'}}],
        'outputs':{'1':{'text':[json.dumps(raw),json.dumps({'schema_version':'lvw.prompt/1','domains':{'observation':['synthetic']}}),json.dumps(metadata)]}}}}


class PublicVideoOracleTests(unittest.TestCase):
    def check(self,value,**kwargs):
        args={'source_sha256':'a'*64,'expected_model':'local-model','chat_calls_before':1,'chat_calls_after':5,**kwargs}
        return public_video_oracle(value,'fresh',**args)

    def test_bound_public_owner_and_real_log_delta_both_required(self):
        self.assertEqual(4,self.check(history())['provider_log_calls'])
        for kwargs in ({'chat_calls_after':1},{'chat_calls_after':6},{'chat_calls_before':True},
                       {'expected_model':'wrong'},{'source_sha256':'c'*64}):
            with self.subTest(kwargs=kwargs),self.assertRaises(EvidenceError):self.check(history(),**kwargs)
        wrong=history();wrong['fresh']['prompt'][2]['1']['class_type']='LVWVideoFramesPromptBridge'
        with self.assertRaises(EvidenceError):self.check(wrong)

    def test_wrong_time_hash_denominator_and_failed_history_rejected(self):
        for field,value in [('pts',1000),('time_seconds',99),('time_base_den',0),('sha256','missing'),('index',True)]:
            wrong=history();text=wrong['fresh']['outputs']['1']['text'];meta=json.loads(text[2]);meta['frames'][1][field]=value;text[2]=json.dumps(meta)
            with self.subTest(field=field),self.assertRaises(EvidenceError):self.check(wrong)
        wrong=history();wrong['fresh']['status']['status_str']='error'
        with self.assertRaises(EvidenceError):self.check(wrong)
        for index in range(3):
            wrong=history();wrong['fresh']['outputs']['1']['text'][index]='[]'
            with self.subTest(index=index),self.assertRaises(EvidenceError):self.check(wrong)


if __name__=='__main__':unittest.main()
