import copy
import unittest

from tools.v0_s2_native_component import BUDGET,authority,metadata_oracle


class NativeComponentTests(unittest.TestCase):
    def metadata(self):
        return {'source_sha256':'a'*64,'bytes':100,'decoder_backend':'ffmpeg-cli/pyav-probe',
                'duration_seconds':8,'frames':[{'index':i,'pts':1000+2000*i,'time_base_num':1,'time_base_den':1000,
                'time_seconds':1+2*i,'sha256':str(i)*64} for i in range(4)]}

    def test_exact_source_backend_count_and_actual_time_evidence_required(self):
        self.assertEqual(4,metadata_oracle(self.metadata(),sample_sha256='a'*64,sample_bytes=100)['frame_count'])
        for key,value in [('source_sha256','b'*64),('decoder_backend','mock'),('duration_seconds',61),('bytes',101)]:
            bad=self.metadata();bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):metadata_oracle(bad,sample_sha256='a'*64,sample_bytes=100)
        for key,value in [('pts',1000),('time_seconds',0),('time_base_den',0),('sha256','missing')]:
            bad=self.metadata();bad['frames'][1][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):metadata_oracle(bad,sample_sha256='a'*64,sample_bytes=100)

    def test_no_model_browser_or_stage_acceptance_can_be_added_to_component_scope(self):
        program={'status':'ACTIVE','authorization_id':'AUTH-PROGRAM-V1-LOCAL-01','stages':['V0-S2']}
        auth={'status':'ACTIVE_ONE_SHOT','source_program_authorization':program['authorization_id'],'stage_id':'V0-S2',
              'scope':'NATIVE_PUBLIC_DECODER_COMPONENT_ONLY','budget':BUDGET.copy(),'run_id':'native-component-01','ports':[8191,11434]}
        authority(auth,program)
        for field in ('provider_calls','ollama_starts','browser_runs','stage_checkpoints'):
            bad=copy.deepcopy(auth);bad['budget'][field]=1
            with self.subTest(field=field),self.assertRaises(ValueError):authority(bad,program)
        with self.assertRaises(ValueError):authority({**auth,'run_id':'../escape'},program)


if __name__=='__main__':unittest.main()
