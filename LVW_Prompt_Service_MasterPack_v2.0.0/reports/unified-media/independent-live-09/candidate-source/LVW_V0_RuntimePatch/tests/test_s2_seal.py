import subprocess
import tempfile
from pathlib import Path
import unittest

from tools.v0_s2_seal import SealError,seal_candidate


class SealTests(unittest.TestCase):
    def test_cmd_crlf_is_verified_against_frozen_attributes_and_actual_checkout_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
            git('init');git('config','user.name','Synthetic Fixture');git('config','user.email','fixture@example.invalid')
            (root/'.gitattributes').write_bytes(b'*.cmd text eol=crlf\n')
            command=root/'start.cmd';command.write_bytes(b'@echo off\r\nexit /b 0\r\n')
            git('add','.');git('commit','-m','synthetic crlf');candidate=git('rev-parse','HEAD')
            result=seal_candidate(root,candidate,['start.cmd'])
            self.assertEqual('text/eol=crlf',result['checkout_transforms']['start.cmd'])
            self.assertNotEqual(result['git_blob_sha256']['start.cmd'],result['execution_artifact_sha256']['start.cmd'])
            command.write_bytes(b'@echo off\nexit /b 0\n')
            with self.assertRaisesRegex(SealError,'BYTES'):seal_candidate(root,candidate,['start.cmd'])
            command.write_bytes(b'@echo off\r\nexit /b 1\r\n')
            with self.assertRaisesRegex(SealError,'BYTES'):seal_candidate(root,candidate,['start.cmd'])
            (root/'.gitattributes').write_text('*.cmd text eol=lf\n')
            with self.assertRaisesRegex(SealError,'ATTRIBUTES'):seal_candidate(root,candidate,['start.cmd'])

    def test_real_git_payload_identity_includes_javascript_and_added_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL).decode().strip()
            git('init');git('config','user.name','Synthetic Fixture');git('config','user.email','fixture@example.invalid')
            pack=root/'pack';pack.mkdir();payload=pack/'bridge';payload.mkdir()
            (payload/'core.py').write_text('pass\n');(payload/'web.js').write_text('export {};\n')
            git('add','.');git('commit','-m','synthetic');candidate=git('rev-parse','HEAD')
            sealed=seal_candidate(pack,candidate,['bridge'])
            self.assertEqual({'bridge/core.py','bridge/web.js'},set(sealed['execution_artifact_sha256']))
            (payload/'web.js').write_text('changed\n')
            with self.assertRaisesRegex(SealError,'BYTES'):seal_candidate(pack,candidate,['bridge'])
            (payload/'web.js').write_text('export {};\n');(payload/'extra.py').write_text('pass\n')
            with self.assertRaisesRegex(SealError,'INVENTORY'):seal_candidate(pack,candidate,['bridge'])
            (payload/'extra.py').unlink();(payload/'alias.py').symlink_to(payload/'core.py')
            with self.assertRaisesRegex(SealError,'SYMLINK'):seal_candidate(pack,candidate,['bridge'])
            (pack/'linked').symlink_to(payload,target_is_directory=True)
            with self.assertRaisesRegex(SealError,'SYMLINK'):seal_candidate(pack,candidate,['linked/core.py'])
            for path in ['../pack','/tmp','bridge\\core.py']:
                with self.subTest(path=path),self.assertRaises(SealError):seal_candidate(pack,candidate,[path])


if __name__=='__main__':unittest.main()
