"""Synthetic artifacts/API transport only, with real phase and evidence oracles."""
import copy
import json
import os
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.v0_s2_fault_evidence import fault_trace
from tools.v0_s2_fault_phase import FaultPhase
from tools.v0_s2_http import ControlError
from tools.v0_s2_checkpoint_oracles import EvidenceError
from tools.v0_s2_driver import base
from LVW_V0_RuntimePatch.tests.test_s2_cancel_evidence import facts,prefix
from LVW_V0_RuntimePatch.tests.test_s2_cancel_phase import Driver
from LVW_V0_RuntimePatch.tests import test_s2_cancel_phase as cancel_test
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_workbench import project


def fault_facts(released_at=8):
    original=facts();events=[e for e in original['events'] if e['event'] in ('run_started','source_prepared',
        'gpu_admission_started','gpu_admission_completed','provider_attempt','provider_owner_verified','provider_request_sent',
        'provider_connection_closed','run_finished')]
    events[-1].update(status='failed',resource_state='unknown',error_code='MODEL_UNAVAILABLE',cancel_epoch=0,
        result_published=False,resource_release={'state':'unproven'})
    stop={'port':11434,'owned_listener_pid':10,'lineage_reproven':True,'terminal_absent':True,'unknown_descendants_absent':True,
        'root_stop':{'pid':10,'target_start_ticks':100,'state':'STOPPED','termination_requested':True,'original_absent':True,
            'stop_requested_wall_seconds':1005.1,'exit_confirmed_wall_seconds':1005.15},
        'descendants_before_stop':[{'pid':11,'parent_pid':10,'start_ticks':101,'process_start_ticks':105}],
        'descendant_terminal_states':[{'pid':11,'target_start_ticks':105,'state':'ABSENT','original_absent':True,'termination_requested':False}]}
    samples=[{'monotonic_seconds':t,'gpu_used_mib':1124 if t>=released_at-2 else 2000,'available_ram_mib':4096,
        'private_bytes':{str(os.getpid()):1000}} for t in range(1,int(released_at)+1)]
    if released_at!=int(released_at):
        for row in samples[-3:]:row['monotonic_seconds']+=released_at-int(released_at);row['gpu_used_mib']=1124
    return {'events':events,'binding':original['binding'],'owner_pid':os.getpid(),'token':'run','before':prefix(10),'after':prefix(10),
        'stop':stop,'clocks':{'before':{'monotonic_seconds':5,'wall_seconds':1005},'after':{'monotonic_seconds':5.3,'wall_seconds':1005.3}},
        'resource_samples':samples,'baseline_gpu_mib':100}


class FaultDriver(Driver):
    def __init__(self,root,case=None):
        super().__init__(root,case);self._fault_sampler_activated=True;self.data=fault_facts()
        for e in self.data['events']:
            if e['event']=='source_prepared':e['source_sha256']=hashlib.sha256((root/'input/clip.mp4').read_bytes()).hexdigest()
        if case=='wrong-source':next(e for e in self.data['events'] if e['event']=='source_prepared')['source_sha256']='0'*64
        self._resource_worker.scope='COMFY_ONLY_FAULT';self._resource_worker.pids=[os.getpid()]
        self.clock_index=0;self.point_index=0;self.stops=0;self.pids=[]
    def chat_log_snapshot(self):return prefix(10)
    def submit(self,graph):
        self.submissions+=1;self.graph=copy.deepcopy(graph)
        pid=str(self.submissions)*32;self.pids.append(pid)
        if self.submissions==1:
            self.index=0;self.token='run';self.pid=pid;self.write(self.data['events'][:7])
        return pid
    def native_clock(self):
        value=self.data['clocks']['before' if self.clock_index==0 else 'after'];self.clock_index+=1;return copy.deepcopy(value)
    def stop_ollama(self):
        self.stops+=1;self.finished=True
        if self.case=='published':self.data['events'][-1]['result_published']=True
        self.write(self.data['events']);return copy.deepcopy(self.data['stop'])
    def guard_point(self,**kwargs):
        value=copy.deepcopy(self.data['resource_samples'][5+self.point_index]);self.point_index+=1;return value
    def _json_request(self,url,*,payload=None,timeout=2,observer=None):
        observer();self.calls.append((url,payload))
        if url.endswith('/api/ps'):
            return 200,{'models':[] if self.index<0 else [{'model':'gemma4:26b','digest':'c'*64,'size_vram':100}]}
        if url.endswith('/video/status'):
            return 200,{'run_token':'run','status':'failed' if self.finished else 'running','cancel_epoch':0,
                'resource_state':'unknown' if self.finished else 'busy','error_code':'MODEL_UNAVAILABLE' if self.finished else None}
        if '/history/' in url:
            pid=url.rsplit('/',1)[1];quarantine=pid!=self.pid;code='RESOURCE_BUSY' if quarantine else 'MODEL_UNAVAILABLE'
            if self.case=='quarantine-success' and quarantine:code='MODEL_UNAVAILABLE'
            error={'node_id':'1','node_type':'LVWVideoPromptOwner','prompt_id':pid,
                'exception_message':json.dumps({'code':code,'details':{'subcode':'VIDEO_REQUEST_ACTIVE'}})}
            return 200,{pid:{'prompt':[0,pid,self.graph],'status':{'status_str':'error','messages':[['execution_error',error]]},'outputs':{}}}
        if url.endswith('/video/workbench'):
            if payload['action']=='preview':
                value=project(payload)
                if self.case=='changed-draft':value['result']['draft']['natural_zh']='changed'
                return 200,value
            response={'error':{'code':'ATTEMPT_STALE' if self.case!='wrong-adopt-code' else 'RESOURCE_BUSY'}}
            raise ControlError('CONTROL_HTTP_409',http_status=409,response=response,response_raw=json.dumps(response).encode())
        raise AssertionError(url)


class FaultEvidenceTests(unittest.TestCase):
    def test_actual_failure_not_in_process_recovery_and_release_exact_boundary(self):
        result=fault_trace(**fault_facts());self.assertTrue(result['in_process_quarantine']);self.assertFalse(result['stage_pass_claim'])
        self.assertEqual(0,result['completed_provider_log_delta']);self.assertEqual(1,result['provider_sends'])
        self.assertEqual(30,fault_trace(**fault_facts(35))['release_from_stop_bracket_seconds'])
        with self.assertRaises(EvidenceError):fault_trace(**fault_facts(35.0001))

    def test_foreign_stop_weak_cleanup_fake_terminal_and_resource_failures_are_refused(self):
        for case in ('root','birth','unknown-child','child-birth','published','released','wrong-auth','closed-before-stop',
                     'response-finished','two-samples','gpu-one-over','threshold','ram','private','gap','log-counter','unknown-event'):
            data=fault_facts();events=data['events'];samples=data['resource_samples']
            if case=='root':data['stop']['root_stop']['pid']=99
            if case=='birth':data['stop']['root_stop']['target_start_ticks']=110
            if case=='unknown-child':data['stop']['unknown_descendants_absent']=False
            if case=='child-birth':data['stop']['descendant_terminal_states'][0]['target_start_ticks']=106
            if case=='published':events[-1]['result_published']=True
            if case=='released':events[-1]['resource_state']='released'
            if case=='wrong-auth':events[0]['authorization_sha256']='0'*64
            if case=='closed-before-stop':data['stop']['root_stop']['stop_requested_wall_seconds']=1005.25
            if case=='response-finished':events[-2]['event']='provider_response'
            if case=='two-samples':samples.pop()
            if case=='gpu-one-over':samples[-1]['gpu_used_mib']=1125
            if case=='threshold':samples[0]['gpu_used_mib']=23552
            if case=='ram':samples[0]['available_ram_mib']=2047
            if case=='private':samples[-1]['private_bytes']={}
            if case=='gap':samples[-1]['monotonic_seconds']=8.501
            if case=='log-counter':data['after']=prefix(12)
            if case=='unknown-event':events[1]['event']='synthetic_success'
            with self.subTest(case=case),self.assertRaises(EvidenceError):fault_trace(**data)


class FaultPhaseTests(unittest.TestCase):
    def setUp(self):
        class SyntheticPinned:
            def __init__(self,*args):pass
            def pin(self,prove):return prove()
            def close(self):pass
            def reap_pending(self,**kwargs):return 0
        p=patch('tools.v0_s2_fault_phase.PinnedLoopbackClient',SyntheticPinned);p.start();self.addCleanup(p.stop)
    def phase(self,temp,case=None):
        prior,_,_=cancel_test.CancelPhaseTests().phase(temp);driver=FaultDriver(Path(temp),case)
        phase=FaultPhase(driver,temp,run_id='synthetic-fault',binding=prior.binding,fixture=prior.fixture,
            reference=prior.reference,authorize=lambda *args:None,baseline_gpu_mib=100)
        return phase,driver
    def test_public_fault_manual_quarantine_and_adopt_negatives_run_once(self):
        with tempfile.TemporaryDirectory() as temp:
            phase,driver=self.phase(temp);original=driver.clients[base.COMFY_URL]
            with patch('subprocess.Popen') as spawn,patch('http.client.HTTPConnection') as http:result=phase.run()
            spawn.assert_not_called();http.assert_not_called()
            self.assertEqual('FAULT_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE',result['decision'])
            self.assertEqual({'fixed':4,'PASS':4,'FAIL':0,'NOT_RUN':0},result['test_counts'])
            self.assertEqual(1,driver.stops);self.assertEqual(2,driver.submissions);self.assertIs(original,driver.clients[base.COMFY_URL])
            self.assertFalse(result['in_process_recovery_claimed']);self.assertFalse(result['stage_pass_claim'])
            self.assertTrue(result['cases']['manual-offline']['draft_preserved'])
            with self.assertRaises(ValueError):phase.run()
    def test_fault_is_not_hidden_by_manual_or_adopt_success(self):
        for case in ('published','changed-draft','quarantine-success','wrong-adopt-code','wrong-source'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
                phase,driver=self.phase(temp,case);result=phase.run()
                self.assertEqual('NO_GO',result['decision']);self.assertEqual(1,driver.stops)
                self.assertEqual(4,len(result['cases']));self.assertEqual(1,result['test_counts']['FAIL'])
                self.assertTrue((phase.directory/'failure-journal.json').exists())
    def test_unprepared_sampler_or_changed_comfy_prevents_any_fault(self):
        for case in ('sampler','comfy'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
                phase,driver=self.phase(temp)
                if case=='sampler':driver._fault_sampler_activated=False
                else:driver._resource_worker.pids=[99]
                result=phase.run();self.assertEqual('NO_GO',result['decision']);self.assertEqual(0,driver.stops)
                self.assertEqual(0,driver.submissions)


if __name__=='__main__':unittest.main()
