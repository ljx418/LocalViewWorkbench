"""Run deterministic JS worker/protocol checks; no Playwright or browser starts."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]


class BrowserWorkerTests(unittest.TestCase):
    def test_original_browser_export_and_real_semantic_negative_cases(self):
        result=subprocess.run(['node','tools/v0_s2_browser_oracle_test.cjs'],cwd=ROOT,capture_output=True,timeout=30)
        self.assertEqual(0,result.returncode,result.stderr.decode('utf-8','replace'))
        self.assertIn(b'Original browser export semantics',result.stdout)

    def test_native_host_readiness_rejects_early_or_pending_graph_setup(self):
        result=subprocess.run(['node','tools/v0_s2_browser_readiness_test.cjs'],cwd=ROOT,capture_output=True,timeout=30)
        self.assertEqual(0,result.returncode,result.stderr.decode('utf-8','replace'))
        self.assertIn(b'Native host readiness boundaries passed',result.stdout)

    def test_real_policy_and_stdio_protocol_refuse_bad_authority_without_browser(self):
        result=subprocess.run(['node','tools/v0_s2_browser_policy_test.cjs'],cwd=ROOT,capture_output=True,timeout=30)
        self.assertEqual(0,result.returncode,result.stderr.decode('utf-8','replace'))
        data=json.loads(result.stdout)
        self.assertEqual('OFFLINE_BROWSER_POLICY_NOT_BROWSER_ACCEPTANCE',data['kind'])
        self.assertEqual(11,data['passed']);self.assertEqual(0,data['failed']);self.assertEqual(0,data['browser_starts'])
        self.assertEqual(11,len({c['name'] for c in data['checks']}));self.assertTrue(all(c['passed'] is True for c in data['checks']))


if __name__=='__main__':unittest.main()
