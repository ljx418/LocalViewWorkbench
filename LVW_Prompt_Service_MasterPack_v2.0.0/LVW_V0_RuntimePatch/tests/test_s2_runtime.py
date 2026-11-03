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
        driver=self.runtime();driver.resource_observer=lambda:None
        with patch.object(driver,'_json_request',side_effect=OSError('fixture')) as request:
            for _ in range(20):
                with self.assertRaises(OSError):driver.preload(base.MODEL)
            with self.assertRaises(base.StopProbe):driver.preload(base.MODEL)
        self.assertEqual(20,request.call_count);self.assertEqual(0,driver.started_model_calls)

    def test_fault_sampler_handoff_starts_coverage_before_retiring_old_private_handles(self):
        driver=self.runtime(native_audit=True);previous=MagicMock();previous.scope='COMFY_AND_OLLAMA'
        previous.stop.return_value={'proven':True,'receipt':{'decision':'RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE'}}
        driver._resource_worker=previous;current=MagicMock();current.scope='COMFY_ONLY_FAULT';current.pids=[10];current.proof={'pid':12}
        previous.points.return_value=[{'monotonic_seconds':9.5},{'monotonic_seconds':10.5}]
        current.points.return_value=[{'monotonic_seconds':10},{'monotonic_seconds':11}]
        order=[]
        def start(*args,**kwargs):
            self.assertTrue(kwargs['fault_only']);order.append('new-started');driver._resource_worker=current;return current
        previous.stop.side_effect=lambda:(order.append('old-stopped'),{'proven':True,'receipt':{'decision':'RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE'}})[1]
        with patch.object(driver,'observe_resources'),patch.object(driver,'start_sampler',side_effect=start):
            self.assertIs(current,driver.prepare_fault_sampler('owned',nvidia_exe='pinned',nvidia_sha256='a'*64))
            with self.assertRaises(base.StopProbe):driver.prepare_fault_sampler('owned',nvidia_exe='pinned',nvidia_sha256='a'*64)
        self.assertEqual(['new-started','old-stopped'],order)
        self.assertFalse(driver.evidence['fault_sampler_transition']['ollama_private_bytes_after_stop_claimed'])
        self.assertEqual(0,driver.evidence['fault_sampler_transition']['handoff_gap_seconds'])

    def test_fault_sampler_bad_old_terminal_latches_abort_and_requests_owned_cleanup(self):
        driver=self.runtime(native_audit=True);previous=MagicMock();previous.scope='COMFY_AND_OLLAMA'
        previous.stop.return_value={'proven':False};driver._resource_worker=previous
        with patch.object(driver,'observe_resources'),patch.object(driver,'start_sampler'),patch.object(driver,'_emergency_cleanup') as cleanup,self.assertRaises(base.StopProbe):
            driver.prepare_fault_sampler('owned',nvidia_exe='pinned',nvidia_sha256='a'*64)
        self.assertTrue(driver.resource_abort_latched);cleanup.assert_called_once()

    def test_fault_sampler_handoff_gap_exact_limit_and_one_over(self):
        for gap,passed in ((1.5,True),(1.5001,False)):
            driver=self.runtime(native_audit=True);old=MagicMock();old.scope='COMFY_AND_OLLAMA';driver._resource_worker=old
            old.stop.return_value={'proven':True,'receipt':{'decision':'RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE'}}
            old.points.return_value=[{'monotonic_seconds':9},{'monotonic_seconds':10}]
            new=MagicMock();new.scope='COMFY_ONLY_FAULT';new.pids=[10];new.proof={}
            new.points.return_value=[{'monotonic_seconds':10+gap},{'monotonic_seconds':11+gap}]
            def start(*args,**kwargs):driver._resource_worker=new;return new
            with self.subTest(gap=gap),patch.object(driver,'observe_resources'),patch.object(driver,'start_sampler',side_effect=start),patch.object(driver,'_emergency_cleanup') as cleanup:
                if passed:driver.prepare_fault_sampler('owned',nvidia_exe='pinned',nvidia_sha256='a'*64);cleanup.assert_not_called()
                else:
                    with self.assertRaises(base.StopProbe):driver.prepare_fault_sampler('owned',nvidia_exe='pinned',nvidia_sha256='a'*64)
                    cleanup.assert_called_once()

    def test_fault_private_scope_is_explicit_default_profile_only(self):
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'temp').mkdir();driver=self.runtime(native_audit=True)
            worker=MagicMock()
            with patch.object(driver,'owned_listener_birth',side_effect=lambda port:{'pid':10 if port==8191 else 11}), \
                 patch('tools.v0_s2_runtime.SamplerWorker',return_value=worker) as factory:
                driver.start_sampler(temp,nvidia_exe='pinned',nvidia_sha256='a'*64,fault_only=True)
            self.assertEqual([10],factory.call_args.args[-1]);self.assertEqual('COMFY_ONLY_FAULT',worker.scope)
            worker.start.assert_called_once()
        with patch('pathlib.Path.mkdir') as mkdir,self.assertRaises(base.StopProbe):
            self.runtime().start_sampler('unused',nvidia_exe='pinned',nvidia_sha256='a'*64,fault_only=True)
        mkdir.assert_not_called()

    def test_native_binding_freezes_lease_owner_and_run_budget_without_overwrite(self):
        driver=self.runtime()
        identity=dict(candidate_sha='a'*40,authorization_sha256='b'*64,model_digest='c'*64)
        with tempfile.TemporaryDirectory() as temp:
            (Path(temp)/'temp').mkdir()
            with patch.object(driver,'owned_listener_birth',return_value={'pid':10,'start_ticks':100}) as root, \
                 patch.object(driver,'native_clock',return_value={'wall_seconds':1000}):
                value=driver.write_native_binding(temp,**identity,max_runs=64)
                self.assertEqual(8200,value['expires_at']);self.assertEqual(64,value['max_runs'])
                self.assertEqual('V0_S2_NATIVE_CHECKPOINT',value['scope']);root.assert_called_with(11434)
                self.assertEqual(value,json.loads((Path(temp)/'temp/lvw-native-profile.json').read_text()))
                with self.assertRaises(FileExistsError):driver.write_native_binding(temp,**identity,max_runs=1)
            for budget in (0,65,True):
                with self.subTest(budget=budget),patch.object(driver,'owned_listener_birth') as root,self.assertRaises(base.StopProbe):
                    driver.write_native_binding(temp,**identity,max_runs=budget)
                root.assert_not_called()

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

    def test_provider_snapshot_binds_exact_complete_log_prefix_not_partial_or_other_routes(self):
        import hashlib
        driver=self.runtime()
        with tempfile.TemporaryDirectory() as temp:
            driver.ollama_log=Path(temp)/'owned.log'
            raw=b'[GIN] 200 POST "/api/generate"\n[GIN] 200 POST "/api/chat"\n[GIN] 200 POST "/api/chat"'
            driver.ollama_log.write_bytes(raw);value=driver.chat_log_snapshot()
            self.assertEqual(1,value['chat_calls']);self.assertEqual(raw[:raw.rfind(b'\n')+1].decode(),value['raw_log'])
            self.assertEqual(hashlib.sha256(value['raw_log'].encode()).hexdigest(),value['source_log_sha256'])
            self.assertEqual(len(raw),value['observed_bytes'])
            driver.ollama_log.write_bytes(raw+b'\n');self.assertEqual(2,driver.chat_log_count())

    def test_failed_preload_recovery_reproves_owner_and_waits_for_three_fresh_gpu_points(self):
        driver=self.runtime();binding={'ollama_pid':10,'ollama_start_ticks':100,'baseline_gpu_mib':100}
        worker=MagicMock();worker.wait_point.side_effect=[
            {'monotonic_seconds':11,'gpu_used_mib':1124},
            {'monotonic_seconds':12,'gpu_used_mib':1125},
            {'monotonic_seconds':13,'gpu_used_mib':1124},
            {'monotonic_seconds':14,'gpu_used_mib':1124},
            {'monotonic_seconds':15,'gpu_used_mib':1124}]
        with patch.object(driver,'owned_listener_birth',return_value={'pid':10,'start_ticks':100}), \
             patch.object(driver,'native_clock',return_value={'monotonic_seconds':10}), \
             patch.object(driver,'_json_request',side_effect=[(200,{'done':True}),(200,{'models':[]})]) as control:
            result=driver.release_preload(binding,worker)
        self.assertTrue(result['proven']);self.assertEqual(5,len(result['gpu_samples']))
        self.assertEqual(2,control.call_count)
        self.assertEqual([10,11,12,13,14],[call.kwargs['after'] for call in worker.wait_point.call_args_list])
        with patch.object(driver,'owned_listener_birth',return_value={'pid':10,'start_ticks':101}), \
             patch.object(driver,'_json_request') as control,self.assertRaises(base.StopProbe):
            driver.release_preload(binding,worker)
        control.assert_not_called()

    def test_preload_recovery_root_proof_cannot_consume_a_fresh_unload_budget(self):
        driver=self.runtime();clock=[0]
        def slow(port):clock[0]=31;return {'pid':10,'start_ticks':100}
        with patch('time.monotonic',side_effect=lambda:clock[0]),patch.object(driver,'owned_listener_birth',side_effect=slow), \
             patch.object(driver,'_json_request') as control,self.assertRaises(base.StopProbe):
            driver.release_preload({'ollama_pid':10,'ollama_start_ticks':100,'baseline_gpu_mib':100},MagicMock())
        control.assert_not_called()

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
