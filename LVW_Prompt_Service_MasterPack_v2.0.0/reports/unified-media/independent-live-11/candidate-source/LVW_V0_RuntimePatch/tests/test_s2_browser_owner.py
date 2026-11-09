"""Kernel ownership checks on an owned Python fixture; not a browser test."""
import copy
import json
import os
import socket
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.v0_s2_browser_owner import birth, executable, profile_baseline, verify_owner, cleanup_witness, verify_driver_listener, wire_identity
from tools.v0_s2_checkpoint_oracles import EvidenceError


class BrowserOwnerTests(unittest.TestCase):
    def test_actual_node_bigint_file_identity_matches_python_without_number_roundtrip(self):
        target = Path(__file__).resolve().parents[2]/'tools/v0_s2_browser_acceptance.cjs'
        script = "const s=require('fs').lstatSync(process.argv[1],{bigint:true});console.log(JSON.stringify({inode:s.ino.toString(),device:s.dev.toString(),oneOver:(2n**53n+1n).toString(),maximum:(2n**64n-1n).toString()}));"
        process = subprocess.run(['node', '-e', script, str(target)], capture_output=True, timeout=10, check=True)
        value = json.loads(process.stdout)
        self.assertEqual(target.stat().st_ino, wire_identity(value['inode']))
        self.assertEqual(target.stat().st_dev, wire_identity(value['device']))
        self.assertEqual(2**53+1, wire_identity(value['oneOver'])); self.assertEqual(2**64-1, wire_identity(value['maximum']))

    def test_profile_wire_identity_is_lossless_at_js_boundary_and_uint64_limit(self):
        for value in (2**53-1, 2**53, 2**53+1, 13792273863143970, 2**64-1):
            self.assertEqual(value, wire_identity(str(value)))
        for value in (str(2**64), True, 1.0, '01', '-1', '1e16', '1.0'):
            with self.subTest(value=value), self.assertRaises(EvidenceError): wire_identity(value)
        with tempfile.TemporaryDirectory() as temporary:
            process, profile, claim, params = self.fixture(Path(temporary))
            claim.update(profile_inode=str(claim['profile_inode']), profile_device=str(claim['profile_device']))
            self.assertEqual(profile.stat().st_ino, verify_owner(claim, **params)['profile_inode'])

    def test_driver_port_is_owned_literal_loopback_and_bound_to_original_worker(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); listener.listen(1); port = listener.getsockname()[1]
            original = birth(os.getpid()); value = verify_driver_listener(original, port)
            self.assertEqual(port, value['port']); self.assertTrue(value['proven_before_connect'])
            with self.assertRaises(EvidenceError): verify_driver_listener({**original, 'start_ticks': '0'}, port)
        with self.assertRaises(EvidenceError): verify_driver_listener(original, port)

    def test_driver_wildcard_or_other_process_listener_is_not_a_loopback_worker_proof(self):
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0)); listener.listen(1); port = listener.getsockname()[1]
            original = Path.read_bytes
            def wildcard_row(path):
                raw = original(path)
                if path == Path(f'/proc/{os.getpid()}/net/tcp'):
                    raw = raw.replace(f'0100007F:{port:04X}'.encode(), f'00000000:{port:04X}'.encode())
                return raw
            # The negative uses a synthetic address row; fixture listeners
            # themselves remain literal loopback and never need a client.
            with patch.object(Path, 'read_bytes', wildcard_row), self.assertRaises(EvidenceError):
                verify_driver_listener(birth(os.getpid()), port)
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
