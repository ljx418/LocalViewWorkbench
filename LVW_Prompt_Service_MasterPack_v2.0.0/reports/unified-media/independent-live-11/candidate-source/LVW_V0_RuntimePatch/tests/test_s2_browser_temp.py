import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from tools import v0_s2_browser_temp as owner


class BrowserTempTests(unittest.TestCase):
    def setUp(self):
        self.evidence=tempfile.TemporaryDirectory()
        self.config={'run_id':'cpu-test','candidate_sha':'a'*40,'authorization_sha256':'b'*64}
        self.root,self.lease=owner.create(self.config,self.evidence.name)

    def tearDown(self):
        if self.root.exists():shutil.rmtree(self.root)
        self.evidence.cleanup()

    def remove(self,**overrides):
        options=dict(independent_cleanup={'decision':'BROWSER_CLEANUP_PROVEN'},node_terminal=True,callbacks_pending=0)
        options.update(overrides)
        return owner.remove(self.root,self.lease,**options)

    def test_linux_fresh_lease_and_independent_terminal_cleanup(self):
        self.assertEqual(self.root.parent,Path('/tmp'))
        self.assertEqual(self.root.stat().st_mode&0o777,0o700)
        self.assertEqual(json.loads((Path(self.evidence.name)/'linux-temp-lease.json').read_text()),self.lease)
        outside=Path(self.evidence.name)/'unrelated';outside.mkdir();(outside/'keep').write_text('original')
        (self.root/'link').symlink_to(outside,target_is_directory=True)
        (self.root/'cache').mkdir();(self.root/'cache'/'new').write_text('scratch')
        self.assertTrue(self.remove()['proven'])
        self.assertEqual((outside/'keep').read_text(),'original')

    def test_uncertain_process_or_callback_preserves_root(self):
        for options in [{'node_terminal':False},{'callbacks_pending':1},{'independent_cleanup':{'decision':'UNKNOWN'}}]:
            with self.subTest(options=options),self.assertRaises(ValueError):self.remove(**options)
            self.assertTrue(self.root.is_dir())

    def test_identity_or_permissions_changed_preserves_root(self):
        original=self.lease['inode'];self.lease['inode']='0'
        with self.assertRaises(ValueError):self.remove()
        self.lease['inode']=original;self.root.chmod(0o755)
        with self.assertRaises(ValueError):self.remove()
        self.assertTrue(self.root.is_dir())

    def test_lease_write_failure_removes_unused_fresh_root(self):
        original=owner.tempfile.mkdtemp;created=[]
        def record(**kwargs):
            value=original(**kwargs);created.append(Path(value));return value
        with patch.object(owner.tempfile,'mkdtemp',side_effect=record),patch.object(Path,'open',side_effect=OSError('receipt write failed')):
            with self.assertRaises(OSError):owner.create(self.config,self.evidence.name)
        self.assertEqual(len(created),1)
        self.assertFalse(created[0].exists())
