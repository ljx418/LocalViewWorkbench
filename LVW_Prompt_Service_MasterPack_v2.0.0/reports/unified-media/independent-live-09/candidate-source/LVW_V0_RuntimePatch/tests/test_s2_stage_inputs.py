"""Recompute real generated input provenance offline, without media execution."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import v0_s2_stage_inputs as inputs

RECEIPT='reports/v0-s2/fixture-preparation-01/receipt.json'
AUTH='reports/v0-s2/authorization-fixtures-01.json'


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


class StageInputTests(unittest.TestCase):
    def load(self,root,**changes):
        options={'receipt_path':RECEIPT,'receipt_sha256':digest(root/RECEIPT),
                 'authorization_path':AUTH,'authorization_sha256':digest(root/AUTH),'require_vfr_rounding':False}
        options.update(changes)
        with patch.object(inputs,'ROOT',root):return inputs.load_fixture_set(**options)

    def snapshot(self,root):
        shutil.copytree(inputs.ROOT/Path(RECEIPT).parent,root/Path(RECEIPT).parent)
        (root/AUTH).write_bytes((inputs.ROOT/AUTH).read_bytes())
        offline=json.loads((root/AUTH).read_text())['offline_receipt']
        (root/offline).parent.mkdir(parents=True);(root/offline).write_bytes((inputs.ROOT/offline).read_bytes())

    def test_actual_four_generated_timelines_derive_exact_public_sampling_expectations(self):
        value=self.load(inputs.ROOT)
        self.assertFalse(value['stage_pass_claim']);self.assertEqual(set(inputs.CATEGORIES),set(value['categories']))
        self.assertEqual(4,len(value['negatives']))
        for row in value['categories'].values():self.assertEqual(4,len(set(row['expected_sample_pts'])))
        self.assertEqual([1024,2048],value['categories']['vfr']['oracle']['pts_gaps'])
        self.assertEqual([12288,36864,61440,86016],value['categories']['static']['expected_sample_pts'])

    def test_first_real_vfr_set_cannot_be_used_for_full_stage_rounding_check(self):
        value=self.load(inputs.ROOT)
        self.assertFalse(value['vfr_sampling_exercises_rounding'])
        with self.assertRaisesRegex(ValueError,'DO_NOT_EXERCISE_ROUNDING'):
            self.load(inputs.ROOT,require_vfr_rounding=True)

    def test_frozen_hash_mismatch_rejects_before_using_rewritten_provenance(self):
        with self.assertRaises(ValueError):self.load(inputs.ROOT,receipt_sha256='0'*64)
        with self.assertRaises(ValueError):self.load(inputs.ROOT,authorization_sha256='0'*64)

    def test_corruption_failed_cleanup_and_missing_denominators_cannot_be_inputs(self):
        for case in ('sample-bytes','log-bytes','cleanup','missing-case','missing-command','old-source','failed-command','changed-oracle'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);self.snapshot(root);receipt=json.loads((root/RECEIPT).read_text())
                if case=='sample-bytes':(root/Path(RECEIPT).parent/'fixtures/static.mp4').write_bytes(b'changed')
                if case=='log-bytes':(root/Path(RECEIPT).parent/'static-probe.stdout.log').write_text('{}')
                if case=='cleanup':receipt['cleanup_proven']=False
                if case=='missing-case':receipt['fixtures'].pop('vfr')
                if case=='missing-command':receipt['commands'].pop()
                if case=='old-source':receipt['identity']['execution_artifact_sha256']['tools/v0_s2_fixtures.py']='0'*64
                if case=='failed-command':receipt['commands'][0]['exit_code']=1
                if case=='changed-oracle':receipt['fixtures']['static']['oracle']['frames']=4
                (root/RECEIPT).write_text(json.dumps(receipt))
                with self.assertRaises(ValueError):self.load(root)


if __name__=='__main__':unittest.main()
