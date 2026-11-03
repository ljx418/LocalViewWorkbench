import copy
import unittest

from tools.v0_s2_decoder_probe import authority,BUDGET


class CpuProbeAuthorityTests(unittest.TestCase):
    def test_exact_authority_does_not_allow_model_or_service_actions(self):
        program={'status':'ACTIVE','authorization_id':'AUTH-PROGRAM-V1-LOCAL-01','stages':['V0-S2']}
        auth={'status':'ACTIVE_ONE_SHOT','source_program_authorization':program['authorization_id'],
              'stage_id':'V0-S2','scope':'CPU_DECODER_INTEGRATION_ONLY','budget':BUDGET.copy(),
              'run_id':'cpu-decoder-01','sample_sha256':'a'*64}
        authority(auth,program)
        for key,value in [('status','EXPIRED'),('stage_id','V0-S3'),('scope','LIVE_CHECKPOINT'),('run_id','../escape')]:
            with self.subTest(key=key),self.assertRaises(ValueError):authority({**auth,key:value},program)
        for action in ('provider_calls','service_starts','gpu_probes','stage_checkpoints'):
            changed=copy.deepcopy(auth);changed['budget'][action]=1
            with self.subTest(action=action),self.assertRaises(ValueError):authority(changed,program)
        with self.assertRaises(ValueError):authority(auth,{**program,'stages':[]})


if __name__=='__main__':unittest.main()
