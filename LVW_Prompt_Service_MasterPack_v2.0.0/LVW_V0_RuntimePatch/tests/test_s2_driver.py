"""Offline lifecycle adapter checks, never create native processes."""
from types import SimpleNamespace
import json
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

    def test_native_audit_is_process_local_exclusive_and_default_clears_inheritance(self):
        normal=comfy_wrapper('python','main','base','pid','ffmpeg',None)
        audit=comfy_wrapper('python','main','base','pid','ffmpeg',None,audit=True)
        self.assertIn('Remove-Item Env:LVW_NATIVE_CHECKPOINT',normal)
        self.assertIn("$env:LVW_NATIVE_CHECKPOINT='run-owned-v1'",audit)
        self.assertIn('Remove-Item Env:LVW_WARM_BENCHMARK',audit)
        for mode in ({'audit':'yes'},{'audit':True,'warm':True}):
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                comfy_wrapper('python','main','base','pid','ffmpeg',None,**mode)
        with self.assertRaises(base.StopProbe):
            S2SystemDriver(SimpleNamespace(max_public_submissions=1,run_id='fixture',powershell='powershell.exe',
                native_audit=True,warm_benchmark=True),{})

    def test_native_stop_receipt_rejects_unproven_or_inconsistent_exit(self):
        driver=self.driver()
        value={'pid':10,'target_start_ticks':100,'state':'STOPPED','original_absent':True,
            'termination_requested':True,'stop_requested_wall_seconds':1000,'exit_confirmed_wall_seconds':1001}
        with patch.object(driver,'_powershell',return_value=json.dumps(value)):
            self.assertEqual(value,driver._kill_bound(10,100))
        for change in ({'original_absent':False},{'pid':11},{'termination_requested':False},
                       {'exit_confirmed_wall_seconds':999},{'state':'REPLACED','termination_requested':False}):
            with self.subTest(change=change),patch.object(driver,'_powershell',return_value=json.dumps({**value,**change})),self.assertRaises(base.StopProbe):
                driver._kill_bound(10,100)

    def test_descendants_require_native_birth_and_parent_chain_exact_and_one_over(self):
        driver=self.driver();child={'pid':11,'parent_pid':10,'start_ticks':100,'process_start_ticks':109}
        with patch.object(driver,'_powershell',return_value=json.dumps([child])):
            self.assertEqual([child],driver._snapshot_descendants(10,90))
        for row in ({**child,'process_start_ticks':110},{**child,'parent_pid':99},{**child,'pid':10},
                    {k:v for k,v in child.items() if k!='process_start_ticks'}):
            with self.subTest(row=row),patch.object(driver,'_powershell',return_value=json.dumps([row])),self.assertRaises(base.StopProbe):
                driver._snapshot_descendants(10,90)

    def test_snapshot_cleanup_is_deepest_first_and_recycled_child_is_left_untouched(self):
        driver=self.driver();children=[{'pid':11,'process_start_ticks':101},{'pid':12,'process_start_ticks':102}]
        def proof(pid,ticks,**kw):
            return {'pid':pid,'target_start_ticks':ticks,'state':'REPLACED' if pid==11 else 'STOPPED','original_absent':True}
        with patch.object(driver,'_kill_bound',side_effect=proof) as kill:
            result=driver._stop_snapshot_descendants(children)
        self.assertEqual([12,11],[call.args[0] for call in kill.call_args_list])
        self.assertTrue(all(call.kwargs['allow_absent'] is True for call in kill.call_args_list))
        self.assertEqual('REPLACED',result[-1]['state'])
        # Unknown descendants cause refusal; there is no guessed PID kill.
        with patch.object(driver,'_powershell',return_value='1'),patch.object(driver,'_kill_bound') as kill,self.assertRaises(base.StopProbe):
            driver._assert_no_new_descendants(10,100,children)
        kill.assert_not_called()


if __name__=='__main__':unittest.main()
