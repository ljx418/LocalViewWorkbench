"""Fixed-phase orchestration with synthetic native behavior, no live claims."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.v0_s2_warm_phase import WarmPhase
from tools.v0_s2_driver import base
from LVW_V0_RuntimePatch.tests.test_s2_measurements import artifacts


class Sampler:
    def __init__(self):self.now=100;self.stops=0
    def wait_point(self,*,after,timeout=3):
        if after is not None:self.now=max(self.now,int(after)+1)
        return self.points()[self.now-100]
    def points(self):
        return [{'sample_index':i,'monotonic_seconds':100+i,'gpu_used_mib':200,
                 'available_ram_mib':4096,'private_bytes':{'10':1000,'20':2000}}
                for i in range(self.now-99)]
    def stop(self):
        self.stops+=1
        receipt=artifacts()['sampler_receipt'];receipt['samples']=len(self.points())
        return {'proven':True,'receipt':receipt}


class Native:
    def __init__(self,root,sampler,*,failure=None):
        self.root=root;self.worker=sampler;self.calls=0;self.preloads=0;self.submits=0;self.recoveries=0
        self.failure=failure;self.last=None;self.events=[];self.polls=0
    def owned_listener_birth(self,port):return {'pid':10,'start_ticks':100 if self.failure!='owner' else 101}
    def verify_model(self):return {'digest':'d'*64 if self.failure!='model' else '0'*64}
    def preload(self,model):
        self.preloads+=1
        if self.failure=='preload':raise OSError('synthetic preload error')
    def chat_log_count(self):return self.calls
    def submit(self,graph):
        self.submits+=1;kind='image' if '2' in graph else 'video';value=artifacts(kind)
        value['source_sha256']=hashlib.sha256((b'image' if kind=='image' else b'video')).hexdigest()
        prompt_id=f'{self.submits:032x}'
        history=value['history'].pop('p1');history['prompt'][1]=prompt_id;history['prompt'][2]=copy.deepcopy(graph)
        if kind=='video':
            metadata=json.loads(history['outputs']['1']['text'][2]);metadata['source_sha256']=value['source_sha256']
            history['outputs']['1']['text'][2]=json.dumps(metadata)
        offset=self.worker.now-100
        for event in value['warm_events']:
            event['request_number']=self.submits;event['monotonic_seconds']+=offset
            event['wall_seconds']+=offset
            if event['event']=='request_finished':event['resource_release']['started_monotonic_seconds']+=offset
        self.events.extend(value['warm_events'])
        path=self.root/'temp/lvw-warm-events.jsonl'
        path.write_text(''.join(json.dumps(e)+'\n' for e in self.events))
        self.last=(prompt_id,{prompt_id:history})
        self.calls+=1 if kind=='image' else 4
        self.worker.now+=6
        if self.failure=='submit':raise OSError('synthetic submit lost acknowledgement')
        if self.failure=='interrupt':raise KeyboardInterrupt()
        return prompt_id
    def _json_request(self,url,**kwargs):
        self.polls+=1
        if self.failure=='history':raise OSError('synthetic history failure')
        if self.failure=='cached':self.calls=0
        if self.failure=='wrong-graph':self.last[1][self.last[0]]['prompt'][2]={}
        return 200,copy.deepcopy(self.last[1])
    def native_clock(self):return {'monotonic_seconds':self.worker.now+.1,'wall_seconds':1000+self.worker.now}
    def release_preload(self,binding,worker):self.recoveries+=1;return {'proven':True}


class PhaseTests(unittest.TestCase):
    def make(self,directory,*,failure=None,authorize=None):
        root=Path(directory);(root/'input').mkdir();(root/'temp').mkdir()
        samples={}
        for kind,suffix in [('image','.png'),('video','.mp4')]:
            reference='fixed'+suffix;raw=kind.encode();(root/'input'/reference).write_bytes(raw)
            samples[kind]={'reference':reference,'sha256':hashlib.sha256(raw).hexdigest()}
        worker=Sampler();driver=Native(root,worker,failure=failure);binding=artifacts()['binding']
        binding.update(expires_at=8000,program_authorization_id='AUTH-PROGRAM-V1-LOCAL-01',
                       scope='V0_S2_WARM_BENCHMARK',max_requests=20)
        phase=WarmPhase(driver,worker,root,run_id='synthetic-run',binding=binding,samples=samples,
                        authorize=authorize or (lambda action,case:None))
        return phase,driver,worker

    def test_twenty_fresh_public_runs_join_real_oracles_with_fixed_denominator(self):
        with tempfile.TemporaryDirectory() as temp:
            phase,driver,worker=self.make(temp);value=phase.run()
            self.assertEqual('WARM_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE',value['decision'])
            self.assertFalse(value['stage_pass_claim']);self.assertEqual(20,value['test_counts']['PASS'])
            self.assertEqual((20,20,50,0),(driver.preloads,driver.submits,driver.calls,driver.recoveries))
            self.assertEqual(1,worker.stops)
            ledger=[json.loads(line) for line in (phase.directory/'actions.jsonl').read_text().splitlines()]
            for case in value['cases']:
                actions=[entry['action'] for entry in ledger if entry['case_id']==case]
                self.assertLess(actions.index('preload'),actions.index('public_submit'))
                graph=json.loads((phase.directory/(case+'.graph.json')).read_text())
                self.assertEqual('LVWControlledImageInput' if case.startswith('image') else 'LVWVideoPromptOwner',graph['1']['class_type'])
            for item in value['artifacts']:
                raw=(phase.directory/item['name']).read_bytes()
                self.assertEqual(item['sha256'],hashlib.sha256(raw).hexdigest())
            with self.assertRaises(ValueError):phase.run()

    def test_preload_submit_and_history_failure_never_retry_or_shrink_denominator(self):
        for failure in ('preload','submit','history','cached','wrong-graph'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as temp:
                phase,driver,worker=self.make(temp,failure=failure);value=phase.run()
                self.assertEqual('NO_GO',value['decision']);self.assertEqual(20,len(value['cases']))
                self.assertEqual({'fixed':20,'PASS':0,'FAIL':1,'NOT_RUN':19,'COLLECTED_PENDING_ORACLE':0},value['test_counts'])
                self.assertEqual(1,driver.preloads);self.assertLessEqual(driver.submits,1)
                self.assertEqual(1,driver.recoveries);self.assertEqual(1,worker.stops)
                self.assertTrue((phase.directory/'phase-receipt.json').is_file())

    def test_rejected_authorization_or_changed_source_never_preloads(self):
        for cause in ('auth','source'):
            def grant(action,case):
                if cause=='auth' and action=='preload':raise base.StopProbe('SYNTHETIC_AUTH_REFUSED')
            with self.subTest(cause=cause),tempfile.TemporaryDirectory() as temp:
                phase,driver,worker=self.make(temp,authorize=grant)
                if cause=='source':(Path(temp)/'input/fixed.png').write_bytes(b'changed')
                value=phase.run()
                self.assertEqual('NO_GO',value['decision']);self.assertEqual(0,driver.preloads)
                self.assertEqual(0,driver.submits);self.assertEqual(0,driver.recoveries)
                self.assertEqual(1,worker.stops)

    def test_owner_or_model_change_refuses_before_preload_and_never_unloads_foreign_root(self):
        for cause in ('owner','model'):
            with self.subTest(cause=cause),tempfile.TemporaryDirectory() as temp:
                phase,driver,worker=self.make(temp,failure=cause);value=phase.run()
                self.assertEqual('NO_GO',value['decision']);self.assertEqual(0,driver.preloads)
                self.assertEqual(0,driver.submits);self.assertEqual(0,driver.recoveries)
                self.assertEqual(1,worker.stops)

    def test_expiry_refuses_new_work_but_cannot_block_reserved_sampler_cleanup(self):
        def denied(action,case):raise base.StopProbe('SYNTHETIC_EXPIRED')
        with tempfile.TemporaryDirectory() as temp:
            phase,driver,worker=self.make(temp,authorize=denied);value=phase.run()
            self.assertEqual('NO_GO',value['decision']);self.assertEqual(0,driver.preloads)
            self.assertEqual(1,worker.stops)
            self.assertEqual('stop_sampler',value['actions'][-1]['action'])
            self.assertTrue(value['actions'][-1]['reserved_cleanup'])

    def test_interruption_retains_terminal_failure_and_cleanup_before_propagating(self):
        with tempfile.TemporaryDirectory() as temp:
            phase,driver,worker=self.make(temp,failure='interrupt')
            with self.assertRaises(KeyboardInterrupt):phase.run()
            value=json.loads((phase.directory/'phase-receipt.json').read_text())
            self.assertEqual('NO_GO',value['decision']);self.assertEqual(19,value['test_counts']['NOT_RUN'])
            self.assertEqual(1,driver.recoveries);self.assertEqual(1,worker.stops)

    def test_existing_event_stream_cannot_be_spliced_into_fresh_phase(self):
        with tempfile.TemporaryDirectory() as temp:
            phase,driver,worker=self.make(temp)
            (Path(temp)/'temp/lvw-warm-events.jsonl').write_text('{"event":"request_started"}\n')
            value=phase.run()
            self.assertEqual('NO_GO',value['decision']);self.assertEqual(0,driver.preloads)
            self.assertEqual(20,value['test_counts']['NOT_RUN'])


if __name__=='__main__':unittest.main()
