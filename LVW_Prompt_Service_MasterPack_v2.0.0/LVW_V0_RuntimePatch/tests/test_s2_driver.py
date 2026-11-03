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

    def test_loopback_failures_consume_budget_without_unlimited_polling(self):
        driver=S2SystemDriver(SimpleNamespace(max_public_submissions=1,max_loopback_requests=1,
            run_id='synthetic',powershell='powershell.exe'),{})
        with patch.object(driver.clients[base.COMFY_URL],'request',side_effect=OSError('synthetic')) as request:
            with self.assertRaises(OSError):driver._json_request(base.COMFY_URL+'/object_info')
            with self.assertRaises(base.StopProbe):driver._json_request(base.COMFY_URL+'/object_info')
        self.assertEqual(1,request.call_count);self.assertEqual(1,len(driver.request_ledger))

    def test_wrapper_decoder_settings_are_process_local_and_quoted(self):
        value=comfy_wrapper('python','main','base','pid',"C:/tool's/ffmpeg.exe",'C:/tools/ffprobe.exe')
        self.assertIn("$env:LVW_FFMPEG_EXE='C:/tool''s/ffmpeg.exe'",value)
        self.assertIn('--listen 127.0.0.1 --port 8191',value)
        self.assertIn('--disable-api-nodes',value)
        self.assertNotIn('SetEnvironmentVariable',value);self.assertNotIn('setx',value)

    def test_pyav_probe_is_explicit_and_never_becomes_a_none_executable_path(self):
        value=comfy_wrapper('python','main','base','pid','existing-ffmpeg',None)
        self.assertIn("$env:LVW_VIDEO_PROBE_BACKEND='pyav'",value)
        self.assertIn('Remove-Item Env:LVW_FFPROBE_EXE',value)
        self.assertNotIn("'None'",value)

    def test_benchmark_mode_is_explicit_and_default_removes_inherited_flag(self):
        normal=comfy_wrapper('python','main','base','pid','ffmpeg',None)
        warm=comfy_wrapper('python','main','base','pid','ffmpeg',None,warm=True)
        self.assertIn('Remove-Item Env:LVW_WARM_BENCHMARK',normal)
        self.assertIn("$env:LVW_WARM_BENCHMARK='run-owned-v1'",warm)
        with self.assertRaises(ValueError):comfy_wrapper('python','main','base','pid','ffmpeg',None,warm='yes')
        with self.assertRaises(base.StopProbe):
            S2SystemDriver(SimpleNamespace(max_public_submissions=1,run_id='fixture',powershell='powershell.exe',warm_benchmark='yes'),{})


if __name__=='__main__':unittest.main()
