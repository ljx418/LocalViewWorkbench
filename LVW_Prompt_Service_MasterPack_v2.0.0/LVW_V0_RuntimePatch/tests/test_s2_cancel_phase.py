"""Synthetic native artifacts drive the actual public-phase coordinator offline."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from tools.v0_s2_cancel_phase import CancellationPhase,cancelled_history
from tools.v0_s2_driver import base
from tools.v0_s2_checkpoint_oracles import EvidenceError
from LVW_V0_RuntimePatch.tests.test_s2_cancel_evidence import facts,prefix


class Driver:
    warm_benchmark=False;native_audit=True
    def __init__(self,root,case=None):
        self.root=root;self.case=case;self.index=-1;self.calls=[];self.all_events=[];self.finished=False;self.submissions=0;self.cancels=0
        self.resource_observer=lambda:None
        self.clients={base.COMFY_URL:object()}
        self._resource_worker=SimpleNamespace(points=lambda:self.data['resource_samples'])
    def write(self,events):
        (self.root/'temp/lvw-native-events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in events))
    def owned_listener_birth(self,port):
        return {'pid':os.getpid(),'start_ticks':200} if port==8191 else {'pid':10,'start_ticks':100}
    def chat_log_snapshot(self):return prefix(10+(self.finished and self.index==1))
    def submit(self,graph):
        self.submissions+=1;self.index+=1;self.graph=copy.deepcopy(graph);self.finished=False
        self.data=facts('preparation' if self.index==0 else 'provider');self.token='run'+str(self.index)
        for e in self.data['events']:e['run_token']=self.token;e['run_number']=self.index+1
        self.pid=str(self.index+1)*32
        if self.case=='missed-window' and self.index==0:
            self.write(self.all_events+self.data['events']);return self.pid
        events=self.data['events'][:1] if self.index==0 else self.data['events'][:7]
        if self.case=='wrong-owner':events[0]['owner_pid']+=1
        self.write(self.all_events+events)
        return self.pid
    def status(self):
        return {'run_token':self.token,'cancel_epoch':1 if self.finished else 0,
            'status':'cancelled' if self.finished else ('preparing' if self.index==0 else 'running'),
            'resource_state':'released' if self.finished else 'busy','error_code':'JOB_CANCELLED' if self.finished else None}
    def history(self):
        error={'node_id':'1','node_type':'LVWVideoPromptOwner','prompt_id':self.pid,
            'exception_message':json.dumps({'code':'JOB_CANCELLED'})}
        value={self.pid:{'prompt':[0,self.pid,self.graph],'status':{'status_str':'error','messages':[['execution_error',error]]},'outputs':{}}}
        if self.case=='wrong-history':value[self.pid]['prompt'][2]={}
        return value
    def _json_request(self,url,*,payload=None,timeout=2,observer=None):
        self.calls.append((url,payload));observer()
        if url.endswith('/api/ps'):
            if self.index==1 and not self.finished:
                return 200,{'models':[{'model':'gemma4:26b','digest':('0' if self.case=='wrong-model' else 'c')*64,'size_vram':100}]}
            return 200,{'models':[]}
        if url.endswith('/video/status'):return 200,self.status()
        if '/history/' in url:return 200,self.history()
        if url.endswith('/video/cancel'):
            self.cancels+=1
            self.finished=True
            if self.case=='published':self.data['events'][-1]['result_published']=True
            self.all_events+=self.data['events'];self.write(self.all_events)
            return 200,{'run_token':payload['run_token'],'cancel_epoch':1,'status':'cancelling','resource_state':'releasing'}
        raise AssertionError(url)


class CancelPhaseTests(unittest.TestCase):
    def setUp(self):
        class SyntheticPinned:
            def __init__(self,*args):pass
            def pin(self,prove):return prove()
            def close(self):pass
            def reap_pending(self,**kwargs):return 0
        patcher=patch('tools.v0_s2_cancel_phase.PinnedLoopbackClient',SyntheticPinned)
        patcher.start();self.addCleanup(patcher.stop)

    def phase(self,temp,case=None):
        root=Path(temp);(root/'temp').mkdir();(root/'input').mkdir();source=b'synthetic-nonmedia'
        (root/'input/clip.mp4').write_bytes(source)
        b=facts()['binding'];(root/'temp/lvw-native-profile.json').write_text(json.dumps(b))
        driver=Driver(root,case);actions=[]
        phase=CancellationPhase(driver,root,run_id='synthetic-cancel',binding=b,
            fixture={'bytes':len(source),'sha256':hashlib.sha256(source).hexdigest()},reference='clip.mp4',
            authorize=lambda action,case:actions.append((action,case)))
        return phase,driver,actions

    def test_public_flow_drives_both_cases_once_and_retains_raw_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            phase,driver,actions=self.phase(temp)
            original=driver.clients[base.COMFY_URL]
            with patch('subprocess.Popen') as spawn,patch('http.client.HTTPConnection') as http:
                result=phase.run()
            spawn.assert_not_called();http.assert_not_called()
            self.assertEqual('CANCELLATION_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE',result['decision'])
            self.assertEqual({'fixed':2,'PASS':2,'FAIL':0,'NOT_RUN':0},result['test_counts'])
            self.assertEqual(2,driver.submissions);self.assertEqual(2,driver.cancels);self.assertTrue(result['parent_cleanup_required'])
            self.assertIs(original,driver.clients[base.COMFY_URL])
            self.assertEqual(0,result['cases']['preparation']['oracle']['provider_calls'])
            self.assertEqual(1,result['cases']['provider']['oracle']['provider_calls']);self.assertFalse(result['stage_pass_claim'])
            for artifact in result['artifacts']:
                raw=(phase.directory/artifact['file']).read_bytes()
                self.assertEqual(artifact['sha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(2,sum(a=='public_submit' for a,_ in actions))
            self.assertEqual(2,sum(a=='control:/lvw/v0/video/cancel' for a,_ in actions))
            with self.assertRaises(ValueError):phase.run()

    def test_invalid_evidence_stops_without_retry_and_preserves_remaining_denominator(self):
        for case,submits,cancels in [('missed-window',1,0),('wrong-owner',1,0),('published',1,1),
                                   ('wrong-history',1,1),('wrong-model',2,1)]:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
                phase,driver,_=self.phase(temp,case);result=phase.run()
                self.assertEqual('NO_GO',result['decision']);self.assertEqual(submits,driver.submissions)
                self.assertEqual(cancels,driver.cancels);self.assertEqual(2,len(result['cases']))
                self.assertEqual(1,result['test_counts']['FAIL']);self.assertTrue((phase.directory/'failure-journal.json').exists())
                self.assertFalse(result['stage_pass_claim'])

    def test_lease_source_root_and_authorization_fail_before_submit(self):
        for case in ('lease','source','root','authorization'):
            with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
                phase,driver,_=self.phase(temp)
                if case=='lease':(Path(temp)/'temp/lvw-native-profile.json').write_text('{}')
                if case=='source':(Path(temp)/'input/clip.mp4').write_bytes(b'changed')
                if case=='root':driver.owned_listener_birth=lambda port:{'pid':99,'start_ticks':100}
                if case=='authorization':phase.authorize=lambda *args:(_ for _ in ()).throw(ValueError('denied'))
                result=phase.run();self.assertEqual('NO_GO',result['decision']);self.assertEqual(0,driver.submissions)
                self.assertEqual('NOT_RUN',result['cases']['provider']['status'])

    def test_journal_prefix_replacement_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            phase,driver,_=self.phase(temp);driver.write([{'event':'replaced'}])
            with self.assertRaises(EvidenceError):phase.delta([{'event':'original'}])

    def test_public_cancel_history_requires_owner_error_and_no_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            phase,driver,_=self.phase(temp);driver.submit({'1':{'class_type':'LVWVideoPromptOwner'}})
            valid=driver.history();cancelled_history(valid,driver.pid,driver.graph)
            for case in ('outputs','code','owner','prompt'):
                value=copy.deepcopy(valid);record=value[driver.pid];error=record['status']['messages'][0][1]
                if case=='outputs':record['outputs']={'1':{}}
                if case=='code':error['exception_message']='{"code":"MODEL_UNAVAILABLE"}'
                if case=='owner':error['node_type']='InternalMock'
                if case=='prompt':error['prompt_id']='old'
                with self.subTest(case=case),self.assertRaises(EvidenceError):cancelled_history(value,driver.pid,driver.graph)


if __name__=='__main__':unittest.main()
