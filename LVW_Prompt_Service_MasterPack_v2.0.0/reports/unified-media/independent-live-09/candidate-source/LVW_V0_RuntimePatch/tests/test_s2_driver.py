"""Offline lifecycle adapter checks, never create native processes."""
from types import SimpleNamespace
import json
import tempfile
from pathlib import Path
import unittest
import subprocess
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

    def test_browser_and_adapter_submissions_share_one_fixed_denominator(self):
        driver=self.driver(2)
        self.assertEqual(1,driver.reserve_public_submission())
        with patch.object(driver,'_json_request',return_value=(200,{})) as request:
            with self.assertRaises(base.StopProbe):driver.submit({'1':{'class_type':'fixture'}})
            with self.assertRaises(base.StopProbe):driver.reserve_public_submission()
            with self.assertRaises(base.StopProbe):driver.submit({'1':{'class_type':'fixture'}})
        self.assertEqual(2,driver.submissions);self.assertEqual(1,request.call_count)

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
        self.assertIn("--user-directory 'base/user'",value)
        self.assertNotIn('SetEnvironmentVariable',value);self.assertNotIn('setx',value)

    def test_pyav_probe_is_explicit_and_never_becomes_a_none_executable_path(self):
        value=comfy_wrapper('python','main','base','pid','existing-ffmpeg',None)
        self.assertIn("$env:LVW_VIDEO_PROBE_BACKEND='pyav'",value)
        self.assertIn('Remove-Item Env:LVW_FFPROBE_EXE',value)
        self.assertNotIn("'None'",value)

    def test_comfy_launch_removes_python_injection_and_uses_owned_offline_cache(self):
        value=comfy_wrapper('python','main',"C:/owned root's run",'pid','ffmpeg',None)
        self.assertIn("'PYTHONPATH','PYTHONHOME'",value)
        self.assertIn("$lvwTemporary='C:/owned root''s run/temp/service-os'",value)
        self.assertIn("$env:HF_HUB_OFFLINE='1'",value)
        self.assertIn('$env:TEMP=$lvwTemporary',value)
        self.assertNotIn('SetEnvironmentVariable',value);self.assertNotIn('setx',value)

    def test_native_junction_metadata_is_exact_and_wrong_target_never_authorizes_removal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();(root/'input').mkdir();(root/'outside-input').mkdir()
            driver=self.driver();driver.evidence['owned_run_root']=str(root)
            proof={'path':str(root/'input/redirect'),'attributes':0x400,'link_type':'Junction','targets':[str(root/'outside-input')]}
            with patch.object(driver,'_windows_path',side_effect=lambda value,**kwargs:value),patch.object(driver,'_powershell',return_value=json.dumps(proof)):
                self.assertTrue(driver.verify_reparse_fixture(root)['proven'])
            for change in ({'attributes':0},{'link_type':'SymbolicLink'},{'targets':[str(root.parent)]},{'targets':[]},{'path':'other'}):
                with self.subTest(change=change),patch.object(driver,'_windows_path',side_effect=lambda value,**kwargs:value), \
                     patch.object(driver,'_powershell',return_value=json.dumps({**proof,**change})) as query,self.assertRaises(base.StopProbe):
                    driver.remove_owned_reparse_fixture(root)
                self.assertEqual(1,query.call_count);self.assertNotIn('Directory]::Delete',query.call_args.args[0])

    def test_native_junction_removal_requires_link_absence_and_preserved_owned_target(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();(root/'input').mkdir();(root/'outside-input').mkdir()
            driver=self.driver();driver.evidence['owned_run_root']=str(root)
            proof={'path':str(root/'input/redirect'),'attributes':0x400,'link_type':'Junction','targets':[str(root/'outside-input')]}
            with patch.object(driver,'_windows_path',side_effect=lambda value,**kwargs:value), \
                 patch.object(driver,'_powershell',side_effect=[json.dumps(proof),json.dumps({'link_absent':True,'target_exists':True})]) as query:
                self.assertTrue(driver.remove_owned_reparse_fixture(root)['proven'])
                self.assertIn(',$false)',query.call_args.args[0])
            with patch.object(driver,'_windows_path',side_effect=lambda value,**kwargs:value), \
                 patch.object(driver,'_powershell',side_effect=[json.dumps(proof),json.dumps({'link_absent':True,'target_exists':False})]),self.assertRaises(base.StopProbe):
                driver.remove_owned_reparse_fixture(root)

    def test_junction_checks_and_delete_preserve_literal_leaf_when_converter_follows_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();(root/'input').mkdir();target=root/'outside-input';target.mkdir()
            link=root/'input/redirect';link.symlink_to(target,target_is_directory=True)
            driver=self.driver();driver.evidence['owned_run_root']=str(root);converted=[]
            def convert(argv,**kwargs):
                source=Path(argv[-1]);converted.append(source)
                relative=source.resolve().relative_to(root)
                return subprocess.CompletedProcess(argv,0,'C:\\fixture'+('\\'+str(relative).replace('/','\\') if str(relative)!='.' else ''),'')
            proof={'path':'C:\\fixture\\input\\redirect','attributes':0x400,'link_type':'Junction',
                'targets':['C:\\fixture\\outside-input']}
            with patch.object(base,'run_local',side_effect=convert),patch.object(driver,'_powershell',
                    side_effect=[json.dumps(proof),json.dumps({'link_absent':True,'target_exists':True})]) as query:
                self.assertTrue(driver.remove_owned_reparse_fixture(root)['proven'])
            self.assertNotIn(link,converted)
            self.assertIn("Get-Item -LiteralPath 'C:\\fixture\\input\\redirect'",query.call_args_list[0].args[0])
            self.assertIn("Directory]::Delete('C:\\fixture\\input\\redirect',$false)",query.call_args_list[1].args[0])
            self.assertTrue(target.is_dir())

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

    def atomic_driver(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        root=Path(temporary.name);(root/'temp').mkdir()
        driver=self.driver();driver.evidence.update(owned_run_root=str(root),candidate_sha='a'*40,authorization_sha256='b'*64)
        driver._windows_path=lambda value,**kwargs:value
        return driver

    def persist_atomic(self,driver,children):
        lease=driver.evidence['owned_pre_stop_snapshot']
        Path(lease['file']).write_text(json.dumps({**lease['identity'],'children':children}))

    def test_atomic_fault_stop_keeps_native_snapshot_and_birth_bound_stop_in_one_command(self):
        driver=self.atomic_driver();stop={'pid':10,'target_start_ticks':100,'state':'STOPPED','original_absent':True,
            'termination_requested':True,'stop_requested_wall_seconds':1000,'exit_confirmed_wall_seconds':1001}
        child={'pid':11,'parent_pid':10,'start_ticks':101,'process_start_ticks':105}
        def reply(command):
            self.persist_atomic(driver,[child]);return json.dumps({'descendants':[child],'root_stop':stop})
        with patch.object(driver,'_powershell',side_effect=reply) as query:
            self.assertEqual(([child],stop),driver._snapshot_descendants(10,100,stop_root=True))
            self.assertEqual(1,query.call_count)
            command=query.call_args.args[0]
            self.assertLess(command.index('$null=$root.SafeHandle'),command.index('$root.Kill()'))
            self.assertLess(command.index('DESCENDANT_DEPTH_LIMIT'),command.index('$root.Kill()'))
        for mutation in ({'pid':99},{'target_start_ticks':101},{'original_absent':False}):
            def bad(command):
                self.persist_atomic(driver,[child]);return json.dumps({'descendants':[child],'root_stop':{**stop,**mutation}})
            with patch.object(driver,'_powershell',side_effect=bad),self.assertRaises(base.StopProbe):
                driver._snapshot_descendants(10,100,stop_root=True)

    def test_atomic_stop_recovers_bound_children_on_timeout_or_corrupt_return(self):
        child={'pid':11,'parent_pid':10,'start_ticks':101,'process_start_ticks':105}
        for failure in ('timeout','json','missing','wrong-auth','bad-child','older-root','older-parent','symlink'):
            with self.subTest(failure=failure):
                driver=self.atomic_driver()
                def fail(command):
                    if failure!='missing':self.persist_atomic(driver,[child])
                    lease=driver.evidence['owned_pre_stop_snapshot'];path=Path(lease['file'])
                    if failure=='wrong-auth':path.write_text(json.dumps({**lease['identity'],'authorization_sha256':'c'*64,'children':[child]}))
                    if failure=='bad-child':path.write_text(json.dumps({**lease['identity'],'children':[{**child,'parent_pid':99}]}))
                    if failure=='older-root':path.write_text(json.dumps({**lease['identity'],'children':[{**child,'start_ticks':90,'process_start_ticks':95}]}))
                    if failure=='older-parent':path.write_text(json.dumps({**lease['identity'],'children':[child,{'pid':12,'parent_pid':11,'start_ticks':99,'process_start_ticks':104}]}))
                    if failure=='symlink':
                        target=path.with_suffix('.target');path.rename(target);path.symlink_to(target)
                    if failure=='timeout':raise subprocess.TimeoutExpired('synthetic command',1)
                    return 'broken JSON'
                with patch.object(driver,'_powershell',side_effect=fail),self.assertRaises(Exception):
                    driver._snapshot_descendants(10,100,stop_root=True)
                if failure in ('timeout','json'):self.assertEqual([child],driver._cleanup_descendants[11434])
                else:self.assertNotIn(11434,driver._cleanup_descendants)

    def test_atomic_fault_stop_refuses_unknown_changed_or_already_consumed_root(self):
        driver=self.driver();birth={'listener_pid':10,'listener_process_start_ticks':100}
        driver.listener_births[11434]=birth.copy();driver.listener_proofs[11434]={'synthetic':True}
        with patch.object(driver,'_snapshot_descendants') as snapshot:
            for value in (None,{}, {**birth,'listener_pid':99}):
                with self.assertRaises(base.StopProbe):driver.stop_ollama_snapshot_bound(value)
            snapshot.assert_not_called()
        driver.listener_terminal_states['11434']={'terminal_absent':True}
        with patch.object(driver,'_snapshot_descendants') as snapshot,self.assertRaises(base.StopProbe):
            driver.stop_ollama_snapshot_bound(birth)
        snapshot.assert_not_called()

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

    def test_stale_comfy_user_directory_cannot_be_reused_or_modified(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'user').mkdir();marker=root/'user/keep';marker.write_text('existing configuration')
            with patch('subprocess.Popen') as spawn,self.assertRaises(FileExistsError):self.driver().start_comfy(root,root/'log')
            spawn.assert_not_called();self.assertEqual('existing configuration',marker.read_text())


if __name__=='__main__':unittest.main()
