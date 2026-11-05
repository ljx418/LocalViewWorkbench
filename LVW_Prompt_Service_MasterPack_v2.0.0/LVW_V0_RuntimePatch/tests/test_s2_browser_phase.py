"""Launch boundary tests: never start Node, Chromium, Comfy or a provider."""
from pathlib import Path
import hashlib
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools.v0_s2_browser_phase import run_browser_phase
from tools.v0_s2_checkpoint_oracles import EvidenceError


class BrowserPhaseTests(unittest.TestCase):
    def arguments(self, root):
        config = {'run_root': str(root), 'candidate_sha': 'a'*40, 'authorization_sha256': 'b'*64}
        proof = {**config, 'owned_run_root': str(root), 'node_sha256': '0'*64}
        return dict(driver=None, config=config, binding={}, fixture={}, node_executable=str(Path(sys.executable).resolve()),
            node_sha256='0'*64, authorize_launch=lambda config: proof, authorize_action=lambda *args: None,
            verify_bindings=lambda *args: {}, run_offline=lambda *args: {})

    def test_authority_denial_precedes_reads_writes_or_process_launch(self):
        with tempfile.TemporaryDirectory() as temporary, patch('subprocess.Popen') as start:
            root = Path(temporary); args = self.arguments(root)
            def deny(*args): raise EvidenceError('synthetic authorization denied')
            args['authorize_launch'] = deny
            with self.assertRaisesRegex(EvidenceError, 'authorization denied'): run_browser_phase(**args)
            self.assertEqual([], list(root.iterdir())); start.assert_not_called()

    def test_wrong_node_bytes_prevent_directory_creation_and_process_launch(self):
        with tempfile.TemporaryDirectory() as temporary, patch('subprocess.Popen') as start:
            root = Path(temporary)
            with self.assertRaisesRegex(EvidenceError, 'Node executable mismatch'): run_browser_phase(**self.arguments(root))
            self.assertEqual([], list(root.iterdir())); start.assert_not_called()

    def test_never_started_worker_cleans_external_scratch_and_records_failure(self):
        from tools.v0_s2_driver import ROOT
        from tools.v0_s2_browser_owner import executable
        for failure in ('authorization','popen'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as temporary:
                root=Path(temporary);(root/'temp').mkdir()
                args=self.arguments(root);config=args['config'];config['run_id']='cpu-never-started'
                for key,name in [('harness_sha256','tools/v0_s2_browser_acceptance.cjs'),
                        ('policy_sha256','tools/v0_s2_browser_policy.cjs'),
                        ('ui_workflow_sha256','LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.ui.json')]:
                    config[key]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
                args['node_sha256']=executable(args['node_executable'])['sha256']
                args['authorize_launch']=lambda value:{**value,'owned_run_root':str(root),'node_sha256':args['node_sha256']}
                def permit(*unused):
                    if failure=='authorization':raise EvidenceError('synthetic authorization denied')
                args['authorize_action']=permit
                with patch('tools.v0_s2_browser_phase.subprocess.Popen',side_effect=OSError('synthetic spawn failure')) as spawn:
                    result=run_browser_phase(**args)
                self.assertEqual(result['decision'],'NO_GO')
                self.assertTrue(result['browser_cleanup_proven'])
                self.assertTrue(result['linux_temp_cleanup']['proven'])
                self.assertFalse(Path(result['linux_temp_lease']['root']).exists())
                self.assertTrue((root/'temp/browser-phase/phase-receipt.json').is_file())
                self.assertEqual(spawn.call_count,int(failure=='popen'))


if __name__ == '__main__': unittest.main()
