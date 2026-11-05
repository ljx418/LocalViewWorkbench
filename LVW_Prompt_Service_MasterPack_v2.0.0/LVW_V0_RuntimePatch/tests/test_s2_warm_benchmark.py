import copy
import base64
import json
import os
import threading
import tempfile
import time
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import core, benchmark
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_resources import validate_snapshot,resource_preflight
from LVW_V0_RuntimePatch.tests.test_s2_video_cancel import Frame,Transport


def binding():
    return {'candidate_sha':'a'*40,'authorization_sha256':'b'*64,'model_digest':'c'*64,
        'program_authorization_id':'AUTH-PROGRAM-V1-LOCAL-01','scope':'V0_S2_WARM_BENCHMARK',
        'baseline_gpu_mib':100,'max_requests':20,'ollama_pid':10,'ollama_start_ticks':100,'issued_at':900,'expires_at':1100}


class WarmTransport(Transport):
    def __init__(self,cancel=None):
        super().__init__(cancel or threading.Event());self.payloads=[];self.baseline=None
        self.ps={'models':[{'model':core.DEFAULT_MODEL,'digest':'c'*64,'size_vram':1000}]}
    def bind_resource_baseline(self,value):self.baseline=value
    def _control_request(self,method,path,payload,timeout):
        self.assert_control=(method,path,payload)
        return copy.deepcopy(self.ps)
    def cleanup(self,model,timeout,*,release_deadline=None):
        self.release_evidence={'state':'released','baseline_gpu_mib':self.baseline}
        self.release_deadline=release_deadline
        return super().cleanup(model,timeout)
    def chat(self,payload,timeout):
        self.payloads.append(copy.deepcopy(payload))
        raw=super().chat(payload,timeout)
        if 'change' not in payload['format']['properties']:
            envelope=json.loads(raw);content=json.loads(envelope['message']['content']);content.pop('change')
            envelope['message']['content']=json.dumps(content);raw=json.dumps(envelope)
        return raw


class WarmTests(unittest.TestCase):
    def setUp(self):self.addCleanup(core._RESOURCE_RELEASE_PENDING.clear)
    def setup_owner(self,transport=None,**overrides):
        events=[];kwargs={'check_root':lambda:None,'admission':lambda:{'owned':True},'sink':events.append,'wall':lambda:1000}
        kwargs.update(overrides);profile=benchmark.WarmBenchmark(binding(),**kwargs)
        transport=transport or WarmTransport()
        owner=core.BridgeOwner(transport=transport,encoder=lambda frame:'fixture',benchmark=profile)
        return owner,profile,transport,events
    def video(self,owner,cancel=None):
        return owner.analyze_video([Frame()]*4,model=core.DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120,cancel_event=cancel)
    def image(self,owner):
        return owner.analyze_image([Frame()],model=core.DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120)

    def test_four_public_bridge_calls_stay_resident_and_cleanup_once_before_return(self):
        owner,profile,transport,events=self.setup_owner()
        raw,suggestion=self.video(owner)
        self.assertEqual(4,len(json.loads(raw)['frame_raw_responses']))
        self.assertEqual('lvw.prompt/1',json.loads(suggestion)['schema_version'])
        self.assertEqual((4,1),(transport.calls,transport.cleanups))
        self.assertTrue(all(payload['keep_alive']==300 for payload in transport.payloads))
        self.assertTrue(all(payload['options']=={'num_ctx':2048,'num_predict':768,'temperature':.2} for payload in transport.payloads))
        before=[event for event in events if event['event']=='before_call']
        after=[event for event in events if event['event']=='after_call']
        self.assertEqual(list(range(4)),[event['call_index'] for event in before])
        self.assertEqual(4,len(after))
        self.assertTrue(all(len(event['request_payload_sha256'])==64 for event in before))
        self.assertTrue(all(len(event['provider_raw_sha256'])==64 for event in after))
        self.assertTrue(events[-1]['restored_unloaded']);self.assertFalse(profile.active)
        self.assertNotIn('messages',json.dumps(events));self.assertNotIn('fixture',json.dumps(events))

    def test_default_bridge_keeps_existing_per_frame_unload(self):
        transport=WarmTransport();owner=core.BridgeOwner(transport=transport,encoder=lambda frame:'fixture')
        self.video(owner)
        self.assertEqual((4,4),(transport.calls,transport.cleanups))
        self.assertTrue(all(payload['keep_alive']==0 for payload in transport.payloads))
        with patch.dict(os.environ,{},clear=True),patch.object(benchmark,'native_lineage') as probe:
            self.assertIsNone(benchmark.configured_profile())
        probe.assert_not_called()

    def test_exact_twenty_requests_then_one_over_has_no_provider_side_effect(self):
        owner,profile,transport,events=self.setup_owner()
        for _ in range(10):self.image(owner)
        with self.assertRaises(core.BridgeError):self.image(owner)
        for _ in range(10):self.video(owner)
        with self.assertRaises(core.BridgeError):self.image(owner)
        self.assertEqual((50,20),(transport.calls,transport.cleanups))
        self.assertEqual(20,profile.requests)

    def test_missing_or_changed_residency_refuses_before_chat_and_restores(self):
        for bad in [{'models':[]},{'models':[{'model':'other','digest':'c'*64,'size_vram':1000}]},
                    {'models':[{'model':core.DEFAULT_MODEL,'digest':'d'*64,'size_vram':1000}]},
                    {'models':[{'model':core.DEFAULT_MODEL,'digest':'c'*64,'size_vram':0}]}]:
            owner,profile,transport,events=self.setup_owner();transport.ps=bad
            with self.subTest(bad=bad),self.assertRaises(core.BridgeError):self.video(owner)
            self.assertEqual((0,1),(transport.calls,transport.cleanups))
            self.assertEqual('failed',events[-1]['outcome'])

    def test_cancellation_discards_success_and_restores_one_request(self):
        cancel=threading.Event();transport=WarmTransport(cancel);transport.trigger=True
        owner,profile,transport,events=self.setup_owner(transport)
        with self.assertRaises(core.BridgeError) as error:self.video(owner,cancel)
        self.assertEqual('JOB_CANCELLED',error.exception.code)
        self.assertEqual((1,1),(transport.calls,transport.cleanups))
        self.assertEqual('failed',events[-1]['outcome'])

    def test_expiry_during_last_response_prevents_publication_but_allows_cleanup(self):
        clock=[1000]
        class Expiring(WarmTransport):
            def chat(self,payload,timeout):
                result=super().chat(payload,timeout)
                if self.calls==4:clock[0]=1100
                return result
        owner,profile,transport,events=self.setup_owner(Expiring(),wall=lambda:clock[0])
        with self.assertRaises(core.BridgeError):self.video(owner)
        self.assertEqual((4,1),(transport.calls,transport.cleanups))
        self.assertEqual('failed',events[-1]['outcome'])

    def test_cleanup_failure_or_lost_root_quarantines_default_owners(self):
        class Dirty(WarmTransport):
            def cleanup(self,model,timeout,*,release_deadline=None):raise RuntimeError('fixture cleanup')
        owner,profile,transport,events=self.setup_owner(Dirty())
        with self.assertRaises(core.BridgeError) as error:self.video(owner)
        self.assertEqual('RESOURCE_RELEASE_PENDING',error.exception.code)
        self.assertTrue(core._RESOURCE_RELEASE_PENDING.is_set())
        other=WarmTransport()
        with self.assertRaises(core.BridgeError):self.image(core.BridgeOwner(transport=other,encoder=lambda frame:'fixture'))
        self.assertEqual(0,other.calls)
        core._RESOURCE_RELEASE_PENDING.clear();checks=[]
        def root():
            checks.append(1)
            if len(checks)>1:raise RuntimeError('root PID reused')
        owner,profile,transport,events=self.setup_owner(check_root=root)
        with self.assertRaises(core.BridgeError):self.video(owner)
        self.assertEqual(0,transport.cleanups)
        self.assertTrue(core._RESOURCE_RELEASE_PENDING.is_set())

    def test_lease_bounds_and_process_lineage_fail_closed(self):
        for key,value in [('max_requests',21),('ollama_pid',True),('candidate_sha','short'),
                          ('expires_at',9000),('expires_at',1000),('model_digest','unknown')]:
            value_binding=binding();value_binding[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(core.BridgeError):benchmark.validate_binding(value_binding,1000)
        document={'listener_pid':10,'listener_address':'127.0.0.1','listener_port':11434,'processes':[{'pid':10,'parent_pid':1,'start_ticks':100,'name':'ollama.exe'},
            {'pid':11,'parent_pid':10,'start_ticks':101,'name':'ollama.exe'}]}
        self.assertEqual((11,20),benchmark.validate_lineage(document,binding(),[11,20],20))
        for mutate in ['root-reused','foreign','cycle','port-reassigned','ancestor-newer','remote-listener']:
            bad=copy.deepcopy(document);pids=[11]
            if mutate=='root-reused':bad['processes'][0]['start_ticks']=99
            if mutate=='foreign':pids=[99]
            if mutate=='cycle':bad['processes'][1]['parent_pid']=11
            if mutate=='port-reassigned':bad['listener_pid']=99
            if mutate=='ancestor-newer':bad['processes'][1]['start_ticks']=99
            if mutate=='remote-listener':bad['listener_address']='0.0.0.0'
            with self.subTest(mutate=mutate),self.assertRaises(core.BridgeError):benchmark.validate_lineage(bad,binding(),pids,20)

    def test_interrupted_restoration_keeps_quarantine_and_preserves_interrupt(self):
        class Interrupted(WarmTransport):
            def cleanup(self,model,timeout,*,release_deadline=None):raise KeyboardInterrupt()
        owner,profile,transport,events=self.setup_owner(Interrupted())
        with self.assertRaises(KeyboardInterrupt):self.video(owner)
        self.assertTrue(core._RESOURCE_RELEASE_PENDING.is_set());self.assertFalse(profile.active)
        other=WarmTransport()
        with self.assertRaises(core.BridgeError):self.image(core.BridgeOwner(transport=other,encoder=lambda frame:'fixture'))
        self.assertEqual(0,other.calls)

    def test_warm_resource_threshold_is_strict_and_needs_ownership_checker(self):
        self.assertEqual(23551,validate_snapshot('24564,23551,1013','11',2048,owner_pid=20,
            warm=True,owned_compute_pids=(11,))['gpu_used_mib'])
        for gpu,pids,ram in [('24564,23552,1012','11',2048),('24564,23551,1013','99',2048),
                             ('24564,23551,1013','11',2047)]:
            with self.subTest(gpu=gpu,pids=pids,ram=ram),self.assertRaises(core.BridgeError):
                validate_snapshot(gpu,pids,ram,owner_pid=20,warm=True,owned_compute_pids=(11,))
        with patch('subprocess.Popen') as spawn,self.assertRaises(core.BridgeError):resource_preflight(warm=True)
        spawn.assert_not_called()

    def test_launch_binding_is_cached_and_mutation_refuses_before_native_probe(self):
        with tempfile.TemporaryDirectory() as temp:
            value=binding();value.update(issued_at=time.time()-1,expires_at=time.time()+600)
            path=Path(temp)/'lvw-warm-profile.json';path.write_text(json.dumps(value))
            with patch.dict(os.environ,{'LVW_WARM_BENCHMARK':'run-owned-v1'}), \
                 patch.dict('sys.modules',{'folder_paths':SimpleNamespace(get_temp_directory=lambda:temp)}), \
                 patch.object(benchmark,'_PROFILE',None),patch.object(benchmark,'native_lineage',return_value=()) as probe:
                first=benchmark.configured_profile();self.assertIs(first,benchmark.configured_profile())
                self.assertTrue((Path(temp)/'lvw-warm-events.jsonl').exists())
                first.ensure_current();probe.assert_not_called()
                path.write_text(json.dumps({**value,'model_digest':'d'*64}))
                with self.assertRaises(core.BridgeError):first.ensure_current()
                probe.assert_not_called()
                path.unlink()
                with self.assertRaises(core.BridgeError) as error:first.ensure_current()
                self.assertNotIn(temp,str(error.exception))
                self.assertEqual('BENCHMARK_BINDING_UNAVAILABLE',error.exception.details['subcode'])

    def test_public_nodes_select_profile_only_through_trusted_runtime_factory(self):
        from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.nodes import LVWImagePromptBridge
        from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_request import VideoRequestOwner
        from LVW_V0_RuntimePatch.tests.test_s2_video_request import Decoder
        _,profile,transport,events=self.setup_owner()
        with patch.object(benchmark,'configured_profile',return_value=profile):
            image=LVWImagePromptBridge(encoder=lambda frame:'fixture')
            self.assertIs(profile,image._owner.benchmark)
            video=VideoRequestOwner(Decoder(),tensor_builder=lambda frames:frames,host_preflight=lambda:{})
            self.assertIs(profile,video.bridge.benchmark)
            self.assertIs(profile.admission,video.preflight)
        with patch.object(benchmark,'configured_profile',return_value=None):
            self.assertIsNone(LVWImagePromptBridge()._owner.benchmark)

    def test_profile_limits_fail_before_fifth_or_second_chat(self):
        owner,profile,transport,events=self.setup_owner()
        with profile.request(transport,core.DEFAULT_MODEL,120,1):
            payload=core.build_chat_payload(model=core.DEFAULT_MODEL,encoded_image='fixture',instruction='fixture',video=False)
            payload['keep_alive']=300;profile.before_call(payload);profile.after_call('raw')
            with self.assertRaises(core.BridgeError):profile.before_call(payload)
        self.assertEqual(0,transport.calls)

    def test_generated_lineage_script_parses_in_native_powershell_without_executing_queries(self):
        executable=shutil.which('powershell.exe')
        self.assertIsNotNone(executable,'Windows/WSL target requires native PowerShell for this compatibility check')
        document={'listener_pid':10,'listener_address':'127.0.0.1','listener_port':11434,'processes':[{'pid':10,'parent_pid':1,'start_ticks':100,'name':'ollama.exe'},
            {'pid':11,'parent_pid':10,'start_ticks':101,'name':'ollama.exe'}]}
        with patch.object(benchmark,'os',SimpleNamespace(name='nt',getpid=lambda:20)), \
             patch.object(benchmark,'run_bounded',return_value=SimpleNamespace(stdout=json.dumps(document).encode())) as runner:
            benchmark.native_lineage(binding(),[11,20])
            script=runner.call_args.args[0][-1]
            self.assertEqual(1,script.count('Get-CimInstance Win32_Process'))
            self.assertEqual(10,runner.call_args.kwargs['timeout_seconds'])
            proof=benchmark.native_lineage(binding(),[11,20],with_evidence=True)
            self.assertEqual(document,proof['snapshot'])
            self.assertEqual([11,20],proof['verified_compute_pids'])
        encoded=base64.b64encode(script.encode()).decode()
        command=("$tokens=$null;$errors=$null;[void][System.Management.Automation.Language.Parser]::ParseInput("
            "[System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+encoded+"')),[ref]$tokens,[ref]$errors);"
            "if($errors.Count){Write-Output ('PARSE_ERRORS='+$errors.Count);exit 1};Write-Output 'PARSE_ERRORS=0'")
        parsed=subprocess.run([executable,'-NoProfile','-NonInteractive','-Command',command],capture_output=True,timeout=30)
        self.assertEqual(0,parsed.returncode)
        self.assertEqual(b'PARSE_ERRORS=0',parsed.stdout.strip())
        self.assertEqual(b'',parsed.stderr)


if __name__=='__main__':unittest.main()
