import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools import v0_s2_offline_checkpoint as checkpoint


class OfflineCheckpointTests(unittest.TestCase):
    def execute(self,root,*,failed=False,skipped=False,changed=False):
        good=SimpleNamespace(returncode=0,stdout=str(root).encode(),stderr=b'Ran 194 tests in 1.0s\n\nOK\n')
        bad=SimpleNamespace(returncode=1,stdout=b'',stderr=b'actual failure')
        if skipped:good.stderr=b'Ran 194 tests in 1.0s\n\nOK (skipped=1)\n'
        values=[bad if failed else good]+[good]*4
        seals=[{'bound':'one'},{'bound':'two' if changed else 'one'}]
        with patch.object(checkpoint,'ROOT',root),patch.object(checkpoint,'seal_candidate',side_effect=seals), \
             patch.object(checkpoint,'packet_binding',return_value={'spec_version':'V0-S2/1.0.1','gate_version':'lvw-gate/1',
                 'acceptance_hash':'32a72139e0c12e0e6d040274024b53bb2dba2f2864b68b840aa215cf739a2a7f'}), \
             patch('subprocess.check_output',return_value='a'*40+'\n'),patch('subprocess.run',side_effect=values):
            return checkpoint.execute('offline-checkpoint-01')

    def test_machine_logs_bound_and_product_cases_remain_unrun(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'reports/v0-s2').mkdir(parents=True)
            result=self.execute(root)
            self.assertEqual('OFFLINE_CHECKS_PASSED_NOT_STAGE_ACCEPTANCE',result['decision'])
            self.assertFalse(result['stage_pass_claim']);self.assertEqual({'NOT_RUN'},set(result['product_cases'].values()))
            self.assertEqual(5,result['test_counts']['PASS'])
            log=root/result['check_results'][0]['stdout_artifact']
            self.assertEqual('PACK_ROOT',log.read_text())
            self.assertEqual(result,json.loads((root/'reports/v0-s2/offline-checkpoint-01/receipt.json').read_text()))

    def test_failure_skip_and_changed_source_never_pass(self):
        for option in ('failed','skipped','changed'):
            with self.subTest(option=option),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);(root/'reports/v0-s2').mkdir(parents=True)
                self.assertEqual('NO_GO',self.execute(root,**{option:True})['decision'])

    def test_preflight_failure_preserves_terminal_receipt_without_executing_checks(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'reports/v0-s2').mkdir(parents=True)
            with patch.object(checkpoint,'ROOT',root),patch.object(checkpoint,'seal_candidate',side_effect=ValueError('mismatch')), \
                 patch('subprocess.check_output',return_value='a'*40+'\n'),patch('subprocess.run') as run:
                result=checkpoint.execute('offline-checkpoint-01')
            run.assert_not_called();self.assertEqual('FAIL',result['preflight_status'])
            self.assertEqual(5,result['test_counts']['NOT_RUN'])
            self.assertEqual('NO_GO',result['decision'])
            self.assertTrue((root/'reports/v0-s2/offline-checkpoint-01/receipt.json').is_file())


if __name__=='__main__':unittest.main()
