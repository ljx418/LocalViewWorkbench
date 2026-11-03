"""Offline lifecycle adapter checks, never create native processes."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.v0_s2_driver import S2SystemDriver, comfy_wrapper, base


class DriverTests(unittest.TestCase):
    def driver(self,budget=2):
        return S2SystemDriver(SimpleNamespace(max_public_submissions=budget,run_id='synthetic',powershell='powershell.exe'),{})

    def test_no_implicit_start_and_budget_is_explicit(self):
        with patch('subprocess.Popen') as start,patch('http.client.HTTPConnection') as connection:
            self.driver()
            for count in (0,65,True):
                with self.subTest(count=count),self.assertRaises(base.StopProbe):self.driver(count)
        start.assert_not_called();connection.assert_not_called()

    def test_failed_submission_consumes_budget_and_cannot_be_retried_forever(self):
        driver=self.driver(1)
        with patch.object(driver,'_json_request',return_value=(200,{})) as request:
            for _ in range(2):
                with self.assertRaises(base.StopProbe):driver.submit({'1':{'class_type':'fixture'}})
        self.assertEqual(1,request.call_count);self.assertEqual(1,driver.submissions)

    def test_scoped_cancel_request_uses_new_client(self):
        driver=self.driver()
        with patch.object(driver.clients[base.COMFY_URL],'request',return_value=(200,{})) as request:
            driver._json_request(base.COMFY_URL+'/lvw/v0/video/cancel',payload={'run_token':'one'})
            request.assert_called_once_with('POST','/lvw/v0/video/cancel',payload={'run_token':'one'},timeout=20)
        with self.assertRaises(base.StopProbe):driver._json_request('http://example.org/api/ps')

    def test_wrapper_decoder_settings_are_process_local_and_quoted(self):
        value=comfy_wrapper('python','main','base','pid',"C:/tool's/ffmpeg.exe",'C:/tools/ffprobe.exe')
        self.assertIn("$env:LVW_FFMPEG_EXE='C:/tool''s/ffmpeg.exe'",value)
        self.assertIn('--listen 127.0.0.1 --port 8191',value)
        self.assertIn('--disable-api-nodes',value)
        self.assertNotIn('SetEnvironmentVariable',value);self.assertNotIn('setx',value)


if __name__=='__main__':unittest.main()
