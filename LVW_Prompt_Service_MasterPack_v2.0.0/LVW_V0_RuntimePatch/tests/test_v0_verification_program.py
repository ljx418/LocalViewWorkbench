import copy
import hashlib
import json
from pathlib import Path
import tempfile
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from tools import v0_verification_authority as auth
from tools import v0_s2_compute_diagnostic as diag
from tools import v0_s2_compute_types as gpu_types
from tools import v0_s2_automatic_verification as automatic
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError


class VerificationProgramTests(unittest.TestCase):
    def program(self):
        return {'status':'ACTIVE','authorization_id':'AUTH-PROGRAM-V0-LOCAL-VERIFICATION-01','granted_by':'project_owner',
                'statement':auth.STATEMENT,'stages':['V0-S2','V0-S3'],'stage_pass_claim':False}

    def issue(self,program=None,**overrides):
        values=dict(stage='V0-S2',run_id='unit-run-01',candidate='a'*40,harness_sha256='b'*64,
                    program_sha256='c'*64,budget={'provider_calls':0,'cloud_calls':0},max_seconds=1800)
        values.update(overrides);return auth.child(program or self.program(),**values)

    def test_child_terminal_does_not_expire_parent_and_allows_new_unique_verification(self):
        program=self.program();before=copy.deepcopy(program);a=self.issue(program)
        terminal=auth.expire(a,'NO_GO','controlled/terminal.json')
        self.assertEqual('EXPIRED_NO_GO',terminal['status']);self.assertEqual(before,program)
        self.assertEqual('ACTIVE_ONE_SHOT',self.issue(program,run_id='unit-run-02')['status'])
        with self.assertRaises(ValueError):auth.expire(terminal,'COMPLETE','other')

    def test_revocation_scope_invalid_bindings_and_unbounded_cost_refused(self):
        revoked=self.program();revoked['status']='REVOKED'
        for kwargs in [dict(program=revoked),dict(stage='V1'),dict(stage='V0-S4'),dict(max_seconds=21601),
                       dict(candidate='main'),dict(budget={'paid_calls':1}),dict(budget={'gpu':-1}),dict(run_id='../escape')]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.issue(**kwargs)

    def test_birth_and_ancestry_classification_never_trusts_pid_alone(self):
        rows=[{'pid':10,'parent_pid':1,'process_start_ticks':100},
              {'pid':11,'parent_pid':10,'process_start_ticks':110},
              {'pid':20,'parent_pid':1,'process_start_ticks':50}]
        roots={'OLLAMA':{'pid':10,'start_ticks':100}}
        labels=diag.classify([10,11,20],rows,roots)
        self.assertEqual(['OLLAMA','OLLAMA_DESCENDANT','UNRESOLVED_OR_UNOWNED'],[v['classification'] for v in labels])
        self.assertEqual('UNRESOLVED_OR_UNOWNED',diag.classify([10],rows,{'OLLAMA':{'pid':10,'start_ticks':99}})[0]['classification'])
        rows[1]['process_start_ticks']=90
        self.assertEqual('UNRESOLVED_OR_UNOWNED',diag.classify([11],rows,roots)[0]['classification'])
        with self.assertRaises(ValueError):diag.classify(list(range(65)),[],{})

    def test_cycles_missing_births_and_unknown_processes_stay_unresolved(self):
        rows=[{'pid':1,'parent_pid':2,'process_start_ticks':1},{'pid':2,'parent_pid':1,'process_start_ticks':1}]
        self.assertTrue(all(v['classification']=='UNRESOLVED_OR_UNOWNED' for v in diag.classify([1,3],rows,{})))
        self.assertEqual([],diag.classify([],[],{}))
        for value in (None,0,-1):
            self.assertEqual('UNRESOLVED_OR_UNOWNED',diag.classify([1],[{'pid':1,'parent_pid':0,'process_start_ticks':value}],{'COMFY':{'pid':1,'start_ticks':value}})[0]['classification'])

    def driver(self):
        value=object.__new__(diag.Driver);value.guard=lambda:None
        value.commands=[];value.cleanup_mode=False;value.wsl_calls=0
        value.command_release_unproven=False;value.launches=[];value.owned=[];value._wrapper_handles={}
        value.child={'command_executables':{}}
        return value

    def test_diagnostic_blocks_all_post_inference_and_unlisted_gets(self):
        driver=self.driver()
        with patch.object(diag.NativeRuntime,'_json_request') as http:
            for url,payload in [(diag.base.OLLAMA_URL+'/api/chat',None),(diag.base.OLLAMA_URL+'/api/generate',{}),
                                (diag.base.COMFY_URL+'/prompt',{}),('http://example.invalid/',None)]:
                with self.subTest(url=url),self.assertRaises(ValueError):driver._json_request(url,payload=payload)
            http.assert_not_called()
        with self.assertRaises(ValueError):driver.submit({})

    def test_actual_command_adapter_records_exits_and_raw_bytes_with_finite_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);binary=root/'fixture.exe';binary.write_bytes(b'explicit synthetic executable')
            driver=self.driver();driver.directory=root
            driver.child['command_executables'][str(binary)]=hashlib.sha256(binary.read_bytes()).hexdigest()
            def execute_result(argv,**kwargs):
                p=SimpleNamespace(returncode=0,stdout=b'example\n',stderr=b'');kwargs['on_result'](p);return p
            with patch.object(diag,'run_bounded',side_effect=execute_result) as execute:
                self.assertEqual('example',driver.command([str(binary)],'wsl'))
                self.assertEqual(b'example\n',(root/'command-001.stdout.log').read_bytes())
                self.assertEqual(0,driver.commands[0]['exit_code'])
                driver.wsl_calls=4
                with self.assertRaises(ValueError):driver.command([str(binary)],'wsl')
                self.assertEqual(1,execute.call_count)
                binary.write_bytes(b'changed')
                with self.assertRaises(ValueError):driver.command([str(binary)],'native')
                self.assertEqual(1,execute.call_count)

    def test_real_cpu_overflow_keeps_bounded_original_output_and_exit_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            driver=self.driver();driver.directory=Path(temp)
            binary=str(Path(sys.executable).resolve())
            driver.child['command_executables'][binary]=hashlib.sha256(Path(binary).read_bytes()).hexdigest()
            with self.assertRaises(BridgeError):
                driver.command([binary,'-c','import sys; sys.stdout.buffer.write(b"x"*1000000)'],'native')
            self.assertLessEqual((driver.directory/'command-001.stdout.log').stat().st_size,262144)
            self.assertIsInstance(driver.commands[0]['exit_code'],int)
            self.assertEqual('MEDIA_LIMIT_EXCEEDED',driver.commands[0]['error_code'])
            self.assertFalse(driver.command_release_unproven)

    def test_pure_windows_path_conversion_and_frozen_legacy_dependency(self):
        driver=self.driver()
        with patch.object(diag.subprocess,'run') as execute:
            self.assertEqual('C:\\folder\\file',driver._windows_path('/mnt/c/folder/file'))
            with self.assertRaises(ValueError):driver._windows_path('/tmp/not-bound')
            with self.assertRaises(ValueError):driver._windows_path('/mnt/c/other',expected='C:/expected')
            execute.assert_not_called()
        self.assertIn('reports/v0-s1/wp-s1-03-phase-a/live_probe.py',diag.PAYLOAD)

    def test_launch_records_exact_bound_argv_wrapper_and_original_handle(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);binary=root/'synthetic.exe';binary.write_bytes(b'explicit synthetic service tool')
            wrapper=root/'fixture.ps1';wrapper.write_bytes(b'explicit synthetic wrapper')
            driver=self.driver();driver.directory=root
            driver.args=SimpleNamespace(powershell=str(binary));driver._windows_path=lambda value:'C:/fixture.ps1'
            driver.child['tool_bindings']={key:{'path':str(binary),'sha256':hashlib.sha256(binary.read_bytes()).hexdigest()}
                for key in ('powershell','comfy_python','comfy_main','ollama_exe','ffmpeg_exe')}
            process=SimpleNamespace(pid=123,poll=lambda:0)
            with patch.object(diag.subprocess,'Popen',return_value=process) as execute,patch.object(diag,'birth',return_value={'pid':123,'start_ticks':'fixture'}):
                driver.launch_owned('comfy',wrapper,root/'service.log')
                self.assertEqual([str(binary),'-NoProfile','-NonInteractive','-File','C:/fixture.ps1'],driver.launches[0]['argv'])
                self.assertTrue((root/'launch-1.started.json').exists())
                driver.owned[0][2].close();binary.write_bytes(b'changed')
                with self.assertRaises(ValueError):driver.launch_owned('other',wrapper,root/'other.log')
                self.assertEqual(1,execute.call_count)

    def test_revoke_and_expire_block_new_commands_but_owned_cleanup_is_reserved(self):
        driver=object.__new__(diag.Driver);driver.cleanup_mode=False;driver.program_hash='a'*64
        driver.child={'expires_at':time.time()+10}
        revoked=self.program();revoked['status']='REVOKED'
        with patch.object(diag.cp,'repository_json',return_value=revoked),self.assertRaises(ValueError):driver.guard()
        with patch.object(diag.cp,'repository_json',return_value=self.program()),patch.object(diag.cp,'file_hash',return_value='a'*64):
            driver.child['expires_at']=time.time()-1
            with self.assertRaises(ValueError):driver.guard()
            driver.cleanup_mode=True;driver.guard()

    def test_xml_types_are_explicit_and_unknown_or_multiple_gpu_fail_closed(self):
        raw=b'<nvidia_smi_log><gpu><processes><process_info><pid>12</pid><type>G</type></process_info><process_info><pid>13</pid><type>C+G</type></process_info></processes></gpu></nvidia_smi_log>'
        self.assertEqual([{'pid':12,'type':'G'},{'pid':13,'type':'C+G'}],gpu_types.process_types(raw))
        for broken in [raw.replace(b'C+G',b'unknown'),raw.replace(b'<pid>13',b'<pid>12'),b'<nvidia_smi_log><gpu/><gpu/></nvidia_smi_log>']:
            with self.assertRaises(ValueError):gpu_types.process_types(broken)

    def test_real_checkpoint_route_uses_finite_child_and_terminal_keeps_parent_active(self):
        from tools import v0_s2_stage_checkpoint as cp
        from tools import v0_s2_supplemental as supplemental
        for mutation in ('valid','budget','expired','revoke','hold','claimed','packet','other-active','missing-lease'):
            with self.subTest(mutation=mutation),tempfile.TemporaryDirectory() as temp:
                root=Path(temp);state=root/'state';state.mkdir()
                def put(ref,value):
                    p=root/ref;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(cp.canonical(value));return p
                program=self.program();program['default_full_s2_run_budget']=cp.BUDGET
                parent=put(auth.PROGRAM,program);control=put('plans/execution-control.json',{'v0_verification_program':auth.PROGRAM,'external_execution_hold':{'active':False}})
                spec=put('.agent-governance/stages/V0-S2/stage-control.json',{'fixture':'unchanged gate'})
                harness=put(cp.HARNESS,{'fixture':'sealed executor'})
                grant=auth.child(program,stage='V0-S2',run_id='full-v0-auto-01',candidate='a'*40,
                    harness_sha256=cp.file_hash(harness),program_sha256=cp.file_hash(parent),budget=cp.BUDGET,max_seconds=21600)
                grant.update(acceptance_hash=cp.ACCEPTANCE,stage_packet_sha256=cp.file_hash(spec))
                if mutation=='budget':grant['budget']['provider_calls']=84
                elif mutation=='expired':grant['expires_at']=time.time()-1
                elif mutation=='revoke':program['status']='REVOKED';put(auth.PROGRAM,program)
                elif mutation=='hold':put('plans/execution-control.json',{'external_execution_hold':{'active':True}})
                elif mutation=='claimed':(state/'full-v0-auto-01').mkdir()
                elif mutation=='packet':put('.agent-governance/stages/V0-S2/stage-control.json',{'changed':'gate'})
                elif mutation=='other-active':
                    other=state/'full-v0-auto-02';other.mkdir();(other/'lease.closed').write_bytes(b'0')
                elif mutation=='missing-lease':(state/'full-v0-auto-02').mkdir()
                put(automatic.approval_path('full-v0-auto-01'),grant)
                with patch.object(cp,'ROOT',root),patch.object(cp,'STATE_ROOT',state):
                    if mutation=='valid':
                        refs=cp.slot_authority('full-v0-auto-01','a'*40)
                        supplemental.expire(refs,decision='NO_GO',terminal='test-only-terminal')
                        self.assertEqual('ACTIVE',json.loads(parent.read_bytes())['status'])
                        with self.assertRaises(ValueError):cp.slot_authority('full-v0-auto-01','a'*40)
                    else:
                        with self.assertRaises(ValueError):cp.slot_authority('full-v0-auto-01','a'*40)

    def test_two_slots_cannot_both_claim_the_same_stage_concurrently(self):
        from tools import v0_s2_stage_checkpoint as cp
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);state=root/'state';barrier=threading.Barrier(2)
            with patch.object(cp,'ROOT',root),patch.object(cp,'STATE_ROOT',state):
                for slot in ['full-v0-auto-01','full-v0-auto-02']:
                    p=cp.child_path(slot);p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(cp.canonical({'slot':slot}))
                def attempt(slot):
                    raw=cp.child_path(slot).read_bytes();barrier.wait(timeout=5)
                    try:cp.claim_run(slot,{'slot':slot},raw);return 'CLAIMED'
                    except (ValueError,BlockingIOError):return 'REFUSED'
                with ThreadPoolExecutor(max_workers=2) as executor:
                    result=list(executor.map(attempt,['full-v0-auto-01','full-v0-auto-02']))
                self.assertEqual(['CLAIMED','REFUSED'],sorted(result))
                self.assertEqual(1,len(list(state.glob('full-*/lease.closed'))))


if __name__=='__main__':unittest.main()
