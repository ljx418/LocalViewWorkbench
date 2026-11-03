import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch

from tools.v0_s2_runtime import NativeRuntime,SamplerWorker,read_jsonl
from tools.v0_s2_driver import base
from tools.v0_s2_http import ControlError


class RuntimeTests(unittest.TestCase):
    def runtime(self,**kwargs):
        return NativeRuntime(SimpleNamespace(max_public_submissions=64,max_loopback_requests=8192,
            run_id='synthetic',powershell='powershell.exe',comfy_python='python',**kwargs),{})

    def test_constructor_has_no_native_or_socket_side_effects(self):
        with patch('subprocess.Popen') as spawn,patch('http.client.HTTPConnection') as socket:
            self.runtime()
        spawn.assert_not_called();socket.assert_not_called()

    def test_native_clock_budget_and_platform_are_checked(self):
        driver=self.runtime(max_native_clock_reads=1)
        clock={'platform':'win32','clock_basis':'native_python_monotonic','monotonic_seconds':123,'wall_seconds':1000}
        with patch.object(driver,'_windows_path',side_effect=lambda value,**kw:value),patch.object(driver,'_powershell',return_value=json.dumps(clock)) as run:
            self.assertEqual(clock,driver.native_clock())
            with self.assertRaises(base.StopProbe):driver.native_clock()
        self.assertEqual(1,run.call_count)
        driver=self.runtime()
        with patch.object(driver,'_windows_path',side_effect=lambda value,**kw:value),patch.object(driver,'_powershell',return_value=json.dumps({**clock,'platform':'linux'})),self.assertRaises(base.StopProbe):
            driver.native_clock()

    def test_binding_is_native_clock_and_ownership_bound_and_never_overwrites(self):
        driver=self.runtime()
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'temp').mkdir()
            with patch.object(driver,'owned_listener_birth',return_value={'pid':10,'start_ticks':100}), \
                 patch.object(driver,'native_clock',return_value={'wall_seconds':1000}):
                value=driver.write_warm_binding(temp,candidate_sha='a'*40,authorization_sha256='b'*64,model_digest='c'*64,nvidia_sha256='d'*64,baseline_gpu_mib=100)
                self.assertEqual(8200,value['expires_at']);self.assertEqual(100,value['ollama_start_ticks'])
                with self.assertRaises(FileExistsError):
                    driver.write_warm_binding(temp,candidate_sha='a'*40,authorization_sha256='b'*64,model_digest='c'*64,nvidia_sha256='d'*64,baseline_gpu_mib=100)
            with patch.object(driver,'owned_listener_birth') as query,self.assertRaises(base.StopProbe):
                driver.write_warm_binding(temp,candidate_sha='bad',authorization_sha256='b'*64,model_digest='c'*64,nvidia_sha256='d'*64,baseline_gpu_mib=100)
            query.assert_not_called()

    def test_preloads_are_separate_bounded_actions_and_failures_consume_budget(self):
        driver=self.runtime()
        with patch.object(driver,'_json_request',side_effect=OSError('fixture')) as request:
            for _ in range(20):
                with self.assertRaises(OSError):driver.preload(base.MODEL)
            with self.assertRaises(base.StopProbe):driver.preload(base.MODEL)
        self.assertEqual(20,request.call_count);self.assertEqual(0,driver.started_model_calls)

    def test_ready_poll_retries_new_client_http_failure_with_finite_deadline(self):
        driver=self.runtime()
        with patch.object(driver,'_json_request',side_effect=[ControlError('CONTROL_HTTP_503'),(200,{})]) as request,patch('time.sleep'):
            self.assertEqual((200,{}),driver.wait_json(base.COMFY_URL+'/object_info'))
        self.assertEqual(2,request.call_count)

    def test_jsonl_ignores_only_incomplete_last_record_and_never_drops_bad_complete_line(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'trace';path.write_bytes(b'{"index":0}\n{"index":')
            self.assertEqual([{'index':0}],read_jsonl(path,limit=100))
            path.write_bytes(b'{"index":0}\nBAD\n')
            with self.assertRaises(ValueError):read_jsonl(path,limit=100)
            with self.assertRaises(base.StopProbe):read_jsonl(path,limit=3)

    def test_worker_rejects_shell_injection_before_any_side_effect(self):
        for seconds,pids,digest in [('1;bad',[10],'a'*64),(10,['10;bad'],'a'*64),(10,[10],"';bad")]:
            with self.subTest(seconds=seconds,pids=pids),patch('subprocess.Popen') as spawn,self.assertRaises(base.StopProbe):
                SamplerWorker(self.runtime(),Path('unused'),'binary',digest,seconds,pids)
            spawn.assert_not_called()

    def test_sampler_refuses_dead_worker_and_resource_limit_before_using_last_point(self):
        for exited,gpu,ram,passed in [(True,100,4096,False),(False,23552,4096,False),
                                      (False,23551,2047,False),(False,23551,2048,True)]:
            worker=SamplerWorker(self.runtime(),Path('unused'),'binary','a'*64,60,[10])
            worker.process=MagicMock();worker.process.poll.return_value=0 if exited else None
            point={'monotonic_seconds':10,'gpu_used_mib':gpu,'available_ram_mib':ram}
            with self.subTest(exited=exited,gpu=gpu,ram=ram),patch.object(worker,'points',return_value=[point]):
                if passed:self.assertEqual(point,worker.wait_point(after=9))
                else:
                    with self.assertRaises(base.StopProbe):worker.wait_point(after=9)

    def test_sampler_stop_waits_for_native_absence_not_wrapper_exit_alone(self):
        driver=self.runtime()
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp);(directory/'resource-sampler.pid').write_text('12')
            (directory/'resource-sampler.receipt.json').write_text(json.dumps({'owned_gpu_query_exited':True}))
            worker=SamplerWorker(driver,directory,'binary','a'*64,60,[10,20]);worker.process=MagicMock()
            worker.process.returncode=0;worker.stream=MagicMock()
            with patch.object(driver,'_powershell',return_value='1'):
                self.assertFalse(worker.stop()['proven'])
            with patch.object(driver,'_powershell',return_value='0'):
                self.assertTrue(worker.stop()['proven'])
            worker.stream.close.assert_called()


if __name__=='__main__':unittest.main()
