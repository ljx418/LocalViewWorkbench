import subprocess
import tempfile
from pathlib import Path
import unittest

from tools.v0_s2_seal import SealError,seal_candidate


class SealTests(unittest.TestCase):
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
