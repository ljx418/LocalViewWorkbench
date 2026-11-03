"""Kernel ownership checks on an owned Python fixture; not a browser test."""
import copy
import os
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from tools.v0_s2_browser_owner import birth, executable, profile_baseline, verify_owner, cleanup_witness, verify_driver_listener
from tools.v0_s2_checkpoint_oracles import EvidenceError


class BrowserOwnerTests(unittest.TestCase):
    def test_driver_port_is_owned_literal_loopback_and_bound_to_original_worker(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); listener.listen(1); port = listener.getsockname()[1]
            original = birth(os.getpid()); value = verify_driver_listener(original, port)
            self.assertEqual(port, value['port']); self.assertTrue(value['proven_before_connect'])
            with self.assertRaises(EvidenceError): verify_driver_listener({**original, 'start_ticks': '0'}, port)
        with self.assertRaises(EvidenceError): verify_driver_listener(original, port)

    def test_driver_wildcard_or_other_process_listener_is_not_a_loopback_worker_proof(self):
        with socket.socket() as listener:
            listener.bind(('0.0.0.0', 0)); listener.listen(1)
            with self.assertRaises(EvidenceError): verify_driver_listener(birth(os.getpid()), listener.getsockname()[1])
        with self.assertRaises(EvidenceError): verify_driver_listener(birth(os.getpid()), 11434)
        with tempfile.TemporaryDirectory() as temporary, socket.socket() as listener:
            process, _, _, _ = self.fixture(Path(temporary))
            listener.bind(('127.0.0.1', 0)); listener.listen(1)
            with self.assertRaises(EvidenceError): verify_driver_listener(birth(process.pid), listener.getsockname()[1])
    def fixture(self, root):
        before = profile_baseline(root)
        profile = root/'playwright_chromiumdev_profile-synthetic'; profile.mkdir()
        process = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(20)', '--user-data-dir='+str(profile)],
            start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(self.stop, process)
        until = time.monotonic()+2
        target = Path(sys.executable).resolve(strict=True)
        while Path(f'/proc/{process.pid}/exe').resolve(strict=True) != target:
            if time.monotonic() >= until: self.fail('fixture exec not observed')
            time.sleep(.001)
        claim = birth(process.pid); info = profile.lstat(); digest = executable(target)['sha256']
        claim.update(executable_sha256=digest, profile_relative_name=profile.name,
            profile_inode=info.st_ino, profile_device=info.st_dev)
        return process, profile, claim, {'worker_birth': birth(os.getpid()), 'browser_executable': target,
            'expected_sha256': digest, 'temporary_root': root, 'before_profiles': before}

    @staticmethod
    def stop(process):
        if process.poll() is None: process.terminate()
        process.wait(timeout=3)

    def test_independent_original_child_executable_profile_and_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            process, profile, claim, params = self.fixture(Path(directory))
            owner = verify_owner(claim, **params)
            self.assertFalse(owner['stage_pass_claim'])
            self.assertEqual('NO_GO', cleanup_witness(owner, temporary_root=Path(directory))['decision'])
            self.stop(process)
            self.assertFalse(cleanup_witness(owner, temporary_root=Path(directory))['profile_absent'])
            profile.rmdir()
            self.assertEqual('BROWSER_CLEANUP_PROVEN', cleanup_witness(owner, temporary_root=Path(directory))['decision'])

    def test_wrong_birth_parent_hash_and_profile_inode_rejected_without_touching_process(self):
        with tempfile.TemporaryDirectory() as directory:
            process, profile, claim, params = self.fixture(Path(directory))
            for key, value in [('start_ticks', '0'), ('parent', process.pid), ('group', 1),
                    ('profile_inode', claim['profile_inode']+1), ('executable_sha256', 'f'*64)]:
                bad = copy.deepcopy(claim); bad[key] = value
                with self.subTest(key=key), self.assertRaises(EvidenceError): verify_owner(bad, **params)
                self.assertIsNone(process.poll()); self.assertTrue(profile.is_dir())

    def test_existing_unbound_or_symlink_profile_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); process, profile, claim, params = self.fixture(root)
            bad = dict(params, before_profiles={profile.name: {}})
            with self.assertRaises(EvidenceError): verify_owner(claim, **bad)
            other = root/'playwright_chromiumdev_profile-unbound'; other.mkdir()
            info = other.lstat(); changed = dict(claim, profile_relative_name=other.name,
                profile_inode=info.st_ino, profile_device=info.st_dev)
            with self.assertRaises(EvidenceError): verify_owner(changed, **params)
            other.rmdir(); other.symlink_to(profile, target_is_directory=True)
            with self.assertRaises(EvidenceError): verify_owner(changed, **params)
            self.assertIsNone(process.poll())


if __name__ == '__main__': unittest.main()
