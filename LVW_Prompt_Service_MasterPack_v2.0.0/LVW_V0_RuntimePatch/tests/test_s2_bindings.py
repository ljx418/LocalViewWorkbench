import copy
import hashlib
from pathlib import Path
import tempfile
import unittest

from tools.v0_s2_bindings import BindingError,sample_inventory,validate_authority


class BindingTests(unittest.TestCase):
    def test_media_aliases_hashes_and_out_of_root_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'source';root.mkdir()
            (root/'name.mp4').write_bytes(b'synthetic')
            values=sample_inventory(root)
            self.assertEqual(hashlib.sha256(b'synthetic').hexdigest(),values[0]['sha256'])
            self.assertNotIn('name',str(values))
            outside=Path(temp)/'outside.mp4';outside.write_bytes(b'outside')
            (root/'redirect.mp4').symlink_to(outside)
            with self.assertRaises(BindingError):sample_inventory(root)

    def test_count_cap_does_not_silently_choose_subset(self):
        with tempfile.TemporaryDirectory() as temp:
            for i in range(25):(Path(temp)/f'{i}.png').write_bytes(b'fixture')
            with self.assertRaisesRegex(BindingError,'COUNT'):sample_inventory(temp)

    def test_exact_budget_and_scope_authority(self):
        program={'status':'ACTIVE','authorization_id':'AUTH-PROGRAM-V1-LOCAL-01','stages':['V0-S2']}
        auth={'status':'ACTIVE_ONE_SHOT','source_program_authorization':program['authorization_id'],
              'stage_id':'V0-S2','scope':'READ_ONLY_BINDING_INVENTORY','candidate_sha':'a'*40,
              'harness_sha256':'b'*64,'run_id':'inventory-01','budget':{'media_hash_files':24,
              'media_hash_bytes':1073741824,'native_path_queries':1,'service_starts':0,'provider_calls':0,
              'gpu_probes':0,'browser_runs':0,'downloads':0,'cloud_calls':0,'stage_checkpoints':0}}
        validate_authority(auth,program,candidate='a'*40,harness_sha='b'*64)
        for key,value in [('status','EXPIRED'),('run_id','../escape'),('scope','FULL_CHECKPOINT'),('candidate_sha','c'*40)]:
            with self.subTest(key=key),self.assertRaises(BindingError):
                validate_authority({**auth,key:value},program,candidate='a'*40,harness_sha='b'*64)
        changed=copy.deepcopy(auth);changed['budget']['provider_calls']=1
        with self.assertRaises(BindingError):validate_authority(changed,program,candidate='a'*40,harness_sha='b'*64)


if __name__=='__main__':unittest.main()
