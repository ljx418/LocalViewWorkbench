"""Owned HTTP interruption and native abort controls, with no real sockets/OS queries."""
import json
import base64
import shutil
import subprocess
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock,patch

from tools.v0_s2_http import LoopbackClient,ControlError
from tools.v0_s2_runtime import NativeRuntime,SamplerWorker
from tools.v0_s2_driver import S2SystemDriver,base


class Socket:
    def __init__(self):self.stopped=threading.Event()
    def shutdown(self,how):self.stopped.set()
    def settimeout(self,value):pass


class BlockedConnection:
    def __init__(self,*,late_connect=False):
        self.sock=Socket();self.closed=False;self.sent=[];self.entered=threading.Event();self.late_connect=late_connect
    def connect(self):
        if self.late_connect:self.entered.set();time.sleep(.3)
    def request(self,*args):self.sent.append(args)
    def getresponse(self):
        self.entered.set()
        if not self.sock.stopped.wait(2):raise AssertionError('observer did not interrupt owned socket')
        raise OSError('owned socket interrupted')
    def close(self):self.closed=True


class AbortTests(unittest.TestCase):
    def runtime(self):return NativeRuntime(SimpleNamespace(max_public_submissions=2,run_id='synthetic',
        powershell='powershell.exe',comfy_python=base.AUTHORIZED_COMFY_PYTHON,ollama_exe='C:/owned/ollama.exe'),{})

    def test_resource_refusal_interrupts_only_owned_socket_and_connect_cannot_send_late(self):
        for late in (False,True):
            connection=BlockedConnection(late_connect=late);foreign=Socket();checks=[]
            def observe():
                checks.append(1)
                if len(checks)>1:
                    self.assertTrue(connection.entered.wait(1))
                    raise base.StopProbe('SYNTHETIC_GPU_LIMIT')
            client=LoopbackClient(base.OLLAMA_URL)
            with self.subTest(late=late),patch('http.client.HTTPConnection',return_value=connection),self.assertRaises(base.StopProbe):
                client.request('POST','/api/generate',payload={'model':base.MODEL},observer=observe)
            self.assertTrue(connection.closed);self.assertEqual(0,client.pending_count())
            self.assertFalse(foreign.stopped.is_set())
            self.assertEqual(0 if late else 1,len(connection.sent))

    def test_successful_monitored_request_keeps_detached_socket_and_closes_all_handles(self):
        connection=MagicMock();owned=connection.sock
        response=MagicMock();response.status=200;response.read1.side_effect=[b'{"done":true}',b'']
        def detach():connection.sock=None;return response
        connection.getresponse.side_effect=detach;observer=MagicMock()
        client=LoopbackClient(base.OLLAMA_URL)
        with patch('http.client.HTTPConnection',return_value=connection):
            self.assertEqual((200,{'done':True}),client.request('POST','/api/generate',payload={},observer=observer))
        self.assertGreaterEqual(observer.call_count,2);self.assertGreaterEqual(owned.settimeout.call_count,3)
        response.close.assert_called_once();connection.close.assert_called_once();self.assertEqual(0,client.pending_count())

    def test_invalid_or_initially_refused_work_never_opens_socket(self):
        client=LoopbackClient(base.OLLAMA_URL);observer=MagicMock(side_effect=base.StopProbe('REFUSED'))
        with patch('http.client.HTTPConnection') as factory:
            with self.assertRaises(ControlError):client.request('POST','/interrupt',observer=observer)
            observer.assert_not_called()
            with self.assertRaises(base.StopProbe):client.request('GET','/api/ps',observer=observer)
        factory.assert_not_called()

    def test_aborted_worker_still_alive_quarantines_new_calls_until_joined(self):
        release=threading.Event();entered=threading.Event();checks=[]
        connection=MagicMock();connection.getresponse.side_effect=lambda:(entered.set(),release.wait(4),None)[-1]
        def observer():
            checks.append(1)
            if len(checks)>1:self.assertTrue(entered.wait(1));raise base.StopProbe('REFUSED')
        client=LoopbackClient(base.OLLAMA_URL)
        with patch('http.client.HTTPConnection',return_value=connection):
            try:
                with self.assertRaises(base.StopProbe):client.request('GET','/api/ps',observer=observer)
                self.assertEqual(1,client.pending_count())
                with self.assertRaisesRegex(ControlError,'PREVIOUS_REQUEST_PENDING'):client.request('GET','/api/ps')
            finally:release.set();self.assertEqual(0,client.reap_pending())

    def test_stale_native_sampler_cannot_be_kept_alive_by_repeated_reads(self):
        worker=SamplerWorker(self.runtime(),Path('unused'),'binary','a'*64,60,[10])
        point={'monotonic_seconds':10,'gpu_used_mib':100,'available_ram_mib':4096}
        with patch.object(worker,'wait_point',return_value=point),patch('time.monotonic',side_effect=[0,3,3.001]):
            worker.observe();worker.observe()
            with self.assertRaises(base.StopProbe):worker.observe()

    def test_native_abort_latches_stops_owned_services_and_never_retries_preload(self):
        driver=self.runtime();worker=MagicMock();worker.observe.side_effect=base.StopProbe('SAMPLER_RESOURCE_LIMIT')
        driver._resource_worker=worker;driver.resource_observer=driver.observe_resources
        # The actual observed client refuses before opening a socket, then the
        # runtime takes its emergency owned-cleanup path exactly once.
        with patch.object(driver,'cleanup',return_value={'proven':False}) as cleanup,patch('http.client.HTTPConnection') as socket:
            with self.assertRaises(base.StopProbe):driver.preload(base.MODEL)
            with self.assertRaises(base.StopProbe):driver.preload(base.MODEL)
        socket.assert_not_called();cleanup.assert_called_once()
        self.assertTrue(driver.resource_abort_latched);self.assertEqual(1,driver.preloads)
        self.assertFalse(driver.evidence['resource_abort_cleanup']['proven'])
        with patch.object(driver,'owned_listener_birth') as prove,self.assertRaises(base.StopProbe):
            driver.release_preload({},worker)
        prove.assert_not_called()

    def test_sampling_failure_between_http_calls_also_latches_and_cleans(self):
        driver=self.runtime();worker=MagicMock();worker.wait_point.side_effect=base.StopProbe('SAMPLER_EXITED')
        driver._resource_worker=worker
        with patch.object(driver,'cleanup',return_value={'proven':False}) as cleanup:
            with self.assertRaises(base.StopProbe):driver.guard_point(after=10)
            with self.assertRaises(base.StopProbe):driver.guard_point(after=10)
        self.assertTrue(driver.resource_abort_latched);cleanup.assert_called_once()

    def test_preload_without_sampler_monitor_is_refused(self):
        driver=self.runtime()
        with patch.object(driver,'_json_request') as request,self.assertRaises(base.StopProbe):driver.preload(base.MODEL)
        request.assert_not_called()

    def test_birth_reuse_or_dead_wrapper_refuses_before_any_stop(self):
        driver=self.runtime();handle=MagicMock();handle.poll.return_value=None
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'wrapper.pid';path.write_text('20');driver._wrapper_handles[str(path)]=handle
            proof={'listener_pid':10,'wrapper_pid':20,'listener_start_ticks':100,'wrapper_start_ticks':90,
                'listener_process_start_ticks':105,'wrapper_process_start_ticks':95,'executable':base.AUTHORIZED_COMFY_PYTHON}
            driver.owned_listener_evidence['8191']={}
            with patch.object(base.SystemDriver,'_prove_listener_owned',return_value=10), \
                 patch.object(driver,'_windows_path',side_effect=lambda path:path), \
                 patch.object(driver,'_powershell',side_effect=[json.dumps(proof),json.dumps({**proof,'listener_start_ticks':101})]):
                self.assertEqual(10,driver._prove_listener_owned(8191,path,'python.exe'))
                with self.assertRaises(base.StopProbe):driver._prove_listener_owned(8191,path,'python.exe')
            handle.poll.return_value=0
            with patch.object(base.SystemDriver,'_prove_listener_owned') as parent,self.assertRaises(base.StopProbe):
                driver._prove_listener_owned(8191,path,'python.exe')
            parent.assert_not_called()

    def test_stop_uses_pinned_handle_and_exact_birth_not_blind_pid_kill(self):
        driver=self.runtime()
        value={'pid':10,'target_start_ticks':100,'state':'STOPPED','termination_requested':True,'original_absent':True,
            'stop_requested_wall_seconds':1000,'exit_confirmed_wall_seconds':1001}
        with patch.object(driver,'_powershell',return_value=json.dumps(value)) as execute:driver._kill_bound(10,100)
        command=execute.call_args.args[0]
        self.assertIn('SafeHandle',command);self.assertIn('Ticks -ne 100',command)
        self.assertLess(command.index('Ticks -ne'),command.index('.Kill()'))
        self.assertIn('.Dispose()',command);self.assertNotIn('Stop-Process',command)

    def test_generated_stop_descendant_and_birth_scripts_parse_without_running_queries(self):
        driver=self.runtime();scripts=[]
        value={'pid':10,'target_start_ticks':100,'state':'STOPPED','termination_requested':True,'original_absent':True,
            'stop_requested_wall_seconds':1000,'exit_confirmed_wall_seconds':1001}
        with patch.object(driver,'_powershell',side_effect=lambda text:(scripts.append(text),json.dumps(value) if '.Kill()' in text else '[]')[1]):
            driver._kill_bound(10,100);driver._snapshot_descendants(10,100)
        with patch.object(driver,'_powershell',side_effect=lambda text:(scripts.append(text),'0')[1]):
            driver._assert_no_new_descendants(10,100,[])
        handle=MagicMock();handle.poll.return_value=None
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'wrapper.pid';path.write_text('20');driver._wrapper_handles[str(path)]=handle
            proof={'listener_pid':10,'wrapper_pid':20,'listener_start_ticks':100,'wrapper_start_ticks':90,
                'listener_process_start_ticks':105,'wrapper_process_start_ticks':95,'executable':base.AUTHORIZED_COMFY_PYTHON}
            driver.owned_listener_evidence['8191']={}
            with patch.object(base.SystemDriver,'_prove_listener_owned',return_value=10), \
                 patch.object(driver,'_windows_path',side_effect=lambda text:text), \
                 patch.object(driver,'_powershell',side_effect=lambda text:(scripts.append(text),json.dumps(proof))[1]):
                driver._prove_listener_owned(8191,path,'python.exe')
        executable=shutil.which('powershell.exe');self.assertIsNotNone(executable)
        encoded=base64.b64encode(json.dumps(scripts).encode()).decode()
        command=("$items=ConvertFrom-Json ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"')));"
            "$count=0;foreach($source in $items){$t=$null;$e=$null;"
            "[void][System.Management.Automation.Language.Parser]::ParseInput($source,[ref]$t,[ref]$e);$count+=$e.Count};"
            "Write-Output ('PARSE_ERRORS='+$count);if($count){exit 1}")
        result=subprocess.run([executable,'-NoProfile','-NonInteractive','-Command',command],capture_output=True,timeout=30)
        self.assertEqual(0,result.returncode);self.assertEqual(b'PARSE_ERRORS=0',result.stdout.strip());self.assertEqual(b'',result.stderr)

    def test_stop_script_runs_against_fake_process_objects_without_real_process_queries(self):
        driver=self.runtime();items=[]
        value={'pid':10,'target_start_ticks':100,'state':'STOPPED','termination_requested':True,'original_absent':True,
            'stop_requested_wall_seconds':1000,'exit_confirmed_wall_seconds':1001}
        for kind in ('owned','replaced','absent'):
            def capture(source):items.append({'kind':kind,'source':source});return json.dumps(value)
            with patch.object(driver,'_powershell',side_effect=capture):driver._kill_bound(10,100,allow_absent=kind!='owned')
        encoded=base64.b64encode(json.dumps(items).encode()).decode()
        command=("$ErrorActionPreference='Stop';class LVWStopFixture{[datetime]$StartTime;[int]$SafeHandle=1;[int]$Kills=0;\n"
            "[void]Kill(){$this.Kills++}\n[bool]WaitForExit([int]$milliseconds){return $true}\n[void]Dispose(){}\n};"
            "function Get-Process{[CmdletBinding()]param([int]$Id);return $script:lvwStopFixture};"
            "if((Get-Command Get-Process).CommandType -ne 'Function'){throw 'FAKE_NOT_INSTALLED'};"
            "$items=ConvertFrom-Json ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"')));"
            "$results=@();foreach($item in $items){$script:lvwStopFixture=[LVWStopFixture]::new();"
            "$ticks=if($item.kind -eq 'replaced'){101}else{100};"
            "$script:lvwStopFixture.StartTime=[datetime]::SpecifyKind([datetime]::MinValue.AddTicks($ticks),[DateTimeKind]::Utc);"
            "if($item.kind -eq 'absent'){$script:lvwStopFixture=$null};"
            "$output=& ([scriptblock]::Create($item.source));$receipt=ConvertFrom-Json ($output -join '');"
            "$kills=if($script:lvwStopFixture){$script:lvwStopFixture.Kills}else{0};"
            "$results+=@([ordered]@{kind=$item.kind;receipt=$receipt;kills=$kills})};ConvertTo-Json -InputObject @($results) -Depth 5 -Compress")
        result=subprocess.run([shutil.which('powershell.exe'),'-NoProfile','-NonInteractive','-Command',command],capture_output=True,timeout=30)
        self.assertEqual(0,result.returncode,result.stderr.decode('utf-8','replace'))
        records=json.loads(result.stdout.decode('utf-8-sig'))
        self.assertEqual(['STOPPED','REPLACED','ABSENT'],[v['receipt']['state'] for v in records])
        self.assertEqual([1,0,0],[v['kills'] for v in records]);self.assertTrue(all(v['receipt']['original_absent'] for v in records))

    def test_foreign_or_reused_listener_cannot_reach_any_kill(self):
        driver=self.runtime();driver.listener_proofs[8191]={'wrapper_pid_file':Path('owned'),'executable_name':'python.exe'}
        with patch.object(driver,'_listener_pid_values',return_value=[99]), \
             patch.object(driver,'_prove_listener_owned',side_effect=base.StopProbe('PID_REUSED')), \
             patch.object(driver,'_kill_bound') as kill,patch.object(driver,'_powershell',return_value='1'):
            value=S2SystemDriver.cleanup(driver)
        self.assertFalse(value['proven']);kill.assert_not_called()

    def test_surviving_descendant_stays_failed_across_repeated_cleanup(self):
        driver=self.runtime();driver.listener_proofs[8191]={'wrapper_pid_file':Path('owned'),'executable_name':'python.exe'}
        driver.listener_births[8191]={'listener_process_start_ticks':100}
        with patch.object(driver,'_listener_pid_values',side_effect=[[10],[],[]]), \
             patch.object(driver,'_prove_listener_owned',return_value=10), \
             patch.object(driver,'_snapshot_descendants',return_value=[{'pid':11,'start_ticks':101}]), \
             patch.object(driver,'_kill_bound') as kill, \
             patch.object(driver,'_powershell',side_effect=lambda command:'1' if 'ProcessId = 11' in command else '0'):
            first=S2SystemDriver.cleanup(driver);second=S2SystemDriver.cleanup(driver)
        self.assertFalse(first['proven']);self.assertFalse(second['proven'])
        kill.assert_called_once_with(10,100)
        self.assertEqual([11],second['owned_listener_terminal_states'][0]['descendant_pids_still_present'])


if __name__=='__main__':unittest.main()
