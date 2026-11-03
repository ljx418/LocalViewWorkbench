"""Default-path native evidence with synthetic HTTP/GPU; no live claims."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import core,video_evidence
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_evidence import NativeAudit,validate_binding
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_request import VideoRequestOwner
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_transport import InterruptibleOllamaTransport
from LVW_V0_RuntimePatch.tests.test_s2_video_request import Decoder
from LVW_V0_RuntimePatch.tests.test_s2_video_cancel import Transport
from LVW_V0_RuntimePatch.tests.test_s2_video_transport import Connection


def binding():return {'candidate_sha':'a'*40,'authorization_sha256':'b'*64,'model_digest':'c'*64,
    'program_authorization_id':'AUTH-PROGRAM-V1-LOCAL-01','scope':'V0_S2_NATIVE_CHECKPOINT',
    'ollama_pid':10,'ollama_start_ticks':100,'max_runs':2,'issued_at':900,'expires_at':1100}


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(core._RESOURCE_RELEASE_PENDING.clear)
        self.addCleanup(setattr,video_evidence,'_AUDIT',None)
    def audit(self,events,**kwargs):
        return NativeAudit(binding(),sink=events.append,check_root=lambda:{'synthetic':True},wall=lambda:1000,**kwargs)

    def test_default_off_does_not_read_configuration_and_modes_cannot_overlap(self):
        with patch.dict(os.environ,{'LVW_NATIVE_CHECKPOINT':''}),patch('pathlib.Path.read_bytes') as read:
            self.assertIsNone(video_evidence.configured_native_audit())
        read.assert_not_called()
        for flag in ('invalid','run-owned-v1'):
            with patch.dict(os.environ,{'LVW_NATIVE_CHECKPOINT':flag,'LVW_WARM_BENCHMARK':'run-owned-v1'}),self.assertRaises(core.BridgeError):
                video_evidence.configured_native_audit()

    def test_binding_budget_expiry_replay_header_and_cleanup_after_expiry(self):
        events=[];wall=[1000]
        audit=NativeAudit({**binding(),'max_runs':1},sink=events.append,check_root=lambda:{},wall=lambda:wall[0])
        audit.start('run1')
        with self.assertRaises(core.BridgeError):audit.event('run1','forged',candidate_sha='d'*40)
        wall[0]=1100
        with self.assertRaises(core.BridgeError):audit.before_provider('run1',{'model':core.DEFAULT_MODEL},5)
        audit.before_control('run1') # Cleanup remains authorized.
        audit.finish('run1',status='failed',resource_state='released',error_code='SCOPE_FORBIDDEN',cancel_epoch=0,cancel_accepted_at=None,release={})
        wall[0]=1000
        for token in ('run1','run2'):
            with self.assertRaises(core.BridgeError):audit.start(token)
        self.assertNotIn('forged',[event['event'] for event in events])

    def test_explicit_file_binding_is_fresh_bounded_and_mutation_refuses_new_work(self):
        with tempfile.TemporaryDirectory() as temp:
            directory=Path(temp);path=directory/'lvw-native-profile.json';now=__import__('time').time()
            path.write_text(json.dumps({**binding(),'issued_at':now-1,'expires_at':now+600}))
            with patch.dict(os.environ,{'LVW_NATIVE_CHECKPOINT':'run-owned-v1','LVW_WARM_BENCHMARK':''}), \
                 patch.dict('sys.modules',{'folder_paths':SimpleNamespace(get_temp_directory=lambda:temp)}):
                audit=video_evidence.configured_native_audit();audit.start('file-run')
                path.write_text(path.read_text()+' ')
                with self.assertRaises(core.BridgeError):audit.ensure()
                lines=[json.loads(line) for line in (directory/'lvw-native-events.jsonl').read_text().splitlines()]
                self.assertEqual(['run_started'],[line['event'] for line in lines])

    def test_root_replacement_blocks_unload_before_any_http_to_foreign_service(self):
        audit=NativeAudit(binding(),sink=lambda value:None,check_root=lambda:(_ for _ in ()).throw(core.BridgeError('SCOPE_FORBIDDEN','changed',subcode='ROOT_CHANGED')),wall=lambda:1000)
        audit.start('owner-run');transport=InterruptibleOllamaTransport();transport.bind_audit(audit,'owner-run')
        with patch('http.client.HTTPConnection') as http,self.assertRaises(core.BridgeError):transport.cleanup(core.DEFAULT_MODEL,120)
        http.assert_not_called();self.assertEqual('unproven',transport.release_evidence['state'])

    def test_root_replacement_during_connect_cannot_send_to_new_owner(self):
        events=[];checks=[0]
        def root():
            checks[0]+=1
            if checks[0]>1:raise core.BridgeError('SCOPE_FORBIDDEN','replaced',subcode='ROOT_CHANGED')
            return {}
        audit=NativeAudit(binding(),sink=events.append,check_root=root,wall=lambda:1000);audit.start('connect')
        transport=InterruptibleOllamaTransport();transport.bind_audit(audit,'connect');connection=Connection()
        with patch('http.client.HTTPConnection',return_value=connection),self.assertRaises(core.BridgeError):
            transport.chat({'model':core.DEFAULT_MODEL},120)
        self.assertEqual([],connection.sent);self.assertTrue(connection.closed)
        self.assertNotIn('provider_request_sent',[e['event'] for e in events])

    def test_slow_ownership_check_is_charged_and_cannot_restart_timeout(self):
        events=[];clock=[0]
        def root():clock[0]=6;return {}
        audit=NativeAudit(binding(),sink=events.append,check_root=root,clock=lambda:clock[0],wall=lambda:1000);audit.start('slow')
        transport=InterruptibleOllamaTransport();transport.bind_audit(audit,'slow')
        with patch('time.monotonic',side_effect=lambda:clock[0]),patch('http.client.HTTPConnection') as http,self.assertRaises(core.BridgeError) as error:
            transport.chat({'model':core.DEFAULT_MODEL},5)
        self.assertEqual('MODEL_TIMEOUT',error.exception.code);http.assert_not_called()

    def test_real_owner_cancel_during_prepare_has_terminal_without_gpu_or_publication(self):
        events=[];entered=threading.Event();finish=threading.Event();transport=InterruptibleOllamaTransport()
        class BlockingDecoder(Decoder):
            def decode(self,*args,**kwargs):entered.set();finish.wait(2);return super().decode(*args,**kwargs)
        owner=VideoRequestOwner(BlockingDecoder(),bridge=core.BridgeOwner(transport=transport,encoder=lambda f:'fixture'),
            tensor_builder=lambda f:f,host_preflight=lambda:{},preflight=lambda:(_ for _ in ()).throw(AssertionError('must not admit GPU')),audit=self.audit(events))
        errors=[]
        def work():
            try:owner.run('prepare-cancel','clip.mp4',model=core.DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120)
            except BaseException as error:errors.append(error)
        thread=threading.Thread(target=work);thread.start()
        try:
            self.assertTrue(entered.wait(1));owner.cancel('prepare-cancel');owner.cancel('prepare-cancel')
        finally:finish.set();thread.join(3)
        self.assertFalse(thread.is_alive());self.assertEqual('JOB_CANCELLED',errors[0].code)
        names=[e['event'] for e in events];self.assertNotIn('gpu_admission_started',names);self.assertNotIn('provider_attempt',names)
        self.assertEqual(1,names.count('cancel_accepted'));self.assertEqual('cancelled',events[-1]['status'])
        self.assertFalse(events[-1]['result_published']);self.assertEqual('not_requested',events[-1]['resource_release']['state'])
        with self.assertRaises(core.BridgeError):owner.completed_result('prepare-cancel')

    def test_real_transport_provider_cancel_records_unload_empty_inventory_and_three_gpu_points(self):
        events=[];clock=[0.0];entered=threading.Event();connection=Connection()
        class Response:
            status=200
            def read1(self,count):
                entered.set()
                if not connection.sock.stopped.wait(2):raise AssertionError('cancel missing')
                raise OSError('owned cancel')
            def close(self):pass
        connection.response=Response()
        transport=InterruptibleOllamaTransport(require_gpu_release=True,gpu_probe=lambda deadline:100)
        audit=self.audit(events,clock=lambda:clock[0])
        owner=VideoRequestOwner(Decoder(),bridge=core.BridgeOwner(transport=transport,encoder=lambda f:'fixture',clock=lambda:clock[0]),
            tensor_builder=lambda f:f,host_preflight=lambda:{},preflight=lambda:{'gpu_used_mib':100},audit=audit,clock=lambda:clock[0])
        errors=[]
        def work():
            try:owner.run('provider-cancel','clip.mp4',model=core.DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120)
            except BaseException as error:errors.append(error)
        def control(method,path,payload,timeout):
            audit.before_control('provider-cancel')
            return {'done':True} if method=='POST' else {'models':[]}
        with patch('http.client.HTTPConnection',return_value=connection),patch.object(transport,'_control_request',side_effect=control), \
             patch('time.monotonic',side_effect=lambda:clock[0]),patch('time.sleep',side_effect=lambda seconds:clock.__setitem__(0,clock[0]+seconds)):
            thread=threading.Thread(target=work);thread.start()
            try:self.assertTrue(entered.wait(1));owner.cancel('provider-cancel')
            finally:connection.sock.stopped.set();thread.join(3)
        self.assertFalse(thread.is_alive());self.assertEqual('JOB_CANCELLED',errors[0].code)
        names=[e['event'] for e in events]
        for name in ('provider_request_sent','provider_connection_closed','unload_acknowledged','model_inventory_empty','physical_release','cancel_accepted','run_finished'):
            self.assertIn(name,names)
        self.assertLess(names.index('provider_connection_closed'),names.index('model_inventory_empty'))
        self.assertLess(names.index('model_inventory_empty'),names.index('physical_release'))
        terminal=events[-1];self.assertEqual('released',terminal['resource_state']);self.assertEqual(1,terminal['provider_attempts'])
        self.assertEqual(3,len(terminal['resource_release']['gpu_samples']));self.assertEqual(0,terminal['resource_release']['model_inventory_empty_monotonic'])
        self.assertEqual(2,terminal['resource_release']['elapsed_seconds']);self.assertFalse(terminal['result_published'])
        self.assertNotIn('fixture',json.dumps(events));self.assertNotIn('clip.mp4',json.dumps(events))

    def test_terminal_sink_failure_revokes_completed_result_and_quarantines_slot(self):
        events=[]
        def sink(value):
            if value['event']=='run_finished':
                self.assertEqual('releasing',owner.current_status()['resource_state'])
                with self.assertRaises(core.BridgeError):owner.completed_result('disk')
                raise OSError('disk failure')
            events.append(value)
        audit=NativeAudit(binding(),sink=sink,check_root=lambda:{},wall=lambda:1000)
        class Auditable(Transport):
            def bind_audit(self,audit,token):self.audit=audit;self.token=token;self.release_evidence={'state':'released'}
            def chat(self,payload,timeout_seconds):
                self.audit.before_provider(self.token,payload,timeout_seconds)
                return super().chat(payload,timeout_seconds)
        owner=VideoRequestOwner(Decoder(),bridge=core.BridgeOwner(transport=Auditable(threading.Event()),encoder=lambda f:'fixture'),
            tensor_builder=lambda f:f,host_preflight=lambda:{},preflight=lambda:{},audit=audit)
        with self.assertRaises(core.BridgeError):owner.run('disk','clip.mp4',model=core.DEFAULT_MODEL,user_instruction='',mode='realistic',timeout_seconds=120)
        self.assertEqual('unknown',owner.current_status()['resource_state']);self.assertTrue(core._RESOURCE_RELEASE_PENDING.is_set())
        with self.assertRaises(core.BridgeError):owner.completed_result('disk')


if __name__=='__main__':unittest.main()
