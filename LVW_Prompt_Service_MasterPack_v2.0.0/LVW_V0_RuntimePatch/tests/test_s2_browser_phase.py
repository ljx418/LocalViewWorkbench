"""Launch boundary tests: never start Node, Chromium, Comfy or a provider."""
from pathlib import Path
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


if __name__ == '__main__': unittest.main()
