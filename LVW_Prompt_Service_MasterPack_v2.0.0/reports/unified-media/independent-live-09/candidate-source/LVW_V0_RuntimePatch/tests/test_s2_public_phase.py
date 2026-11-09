"""Public-phase orchestration/oracles with synthetic native responses only."""
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from tools.v0_s2_driver import base
from tools.v0_s2_public_phase import PublicPhase,FIXED_CASES,PATH_REFERENCES
from tools.v0_s2_stage_inputs import ROOT,load_fixture_set
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import prompt_spec

PLAN=json.loads((ROOT/'reports/v0-s2/frozen-structural-inputs-02.json').read_text())


def inputs():return load_fixture_set(**PLAN['binding_inputs'])


class Native:
    def __init__(self,plan,references,root,corrupt=None):
        self.plan=plan;self.references=references;self.root=root;self.corrupt=corrupt
        self.resource_observer=lambda:None;self.warm_benchmark=False;self.calls=0;self.submits=0;self.time=0
    def owned_listener_birth(self,port):
        if self.corrupt=='owner':raise base.StopProbe('LISTENER_PID_REUSED')
        return {'pid':port,'start_ticks':100,'name':'synthetic'}
    def guard_point(self,*,after=None):self.time+=1;return {'monotonic_seconds':self.time}
    def chat_log_snapshot(self):
        raw=('[GIN] 200 POST "/api/chat"\n'*self.calls).encode()
        return {'raw_log':raw.decode(),'source_log_sha256':hashlib.sha256(raw).hexdigest(),
                'source_log_bytes':len(raw),'observed_bytes':len(raw),'chat_calls':self.calls}
    def chat_log_count(self):return self.calls
    def submit(self,graph):
        self.submits+=1;prompt=f'{self.submits:032x}';node=graph['1'];reference=node['inputs']['video_reference']
        name=next(name for name,value in self.references.items() if value==reference)
        status={'status_str':'success','messages':[]};outputs={}
        decoder=node['class_type']=='LVWControlledVideoInput'
        codes={'over-duration':('MEDIA_LIMIT_EXCEEDED','VIDEO_DURATION_LIMIT'),
            'fake-extension.mp4':('MEDIA_INVALID','VIDEO_PROBE_INVALID'),'corrupt.mp4':('MEDIA_INVALID','VIDEO_PROBE_INVALID'),
            'truncated.mov':('MEDIA_INVALID','VIDEO_PROBE_INVALID'),'traversal':('PATH_FORBIDDEN','VIDEO_REFERENCE_FORBIDDEN'),
            'absolute':('PATH_FORBIDDEN','VIDEO_REFERENCE_FORBIDDEN'),'unc':('PATH_FORBIDDEN','VIDEO_REFERENCE_FORBIDDEN'),
            'empty':('MEDIA_INVALID','VIDEO_EMPTY'),'oversize':('MEDIA_LIMIT_EXCEEDED','VIDEO_BYTE_LIMIT'),
            'reparse':('PATH_FORBIDDEN','VIDEO_REFERENCE_FORBIDDEN')}
        if name in codes:
            code,subcode=codes[name]
            if self.corrupt=='wrong-error':code='MODEL_UNAVAILABLE'
            if self.corrupt=='negative-model-call':self.calls+=1
            status={'status_str':'error','messages':[['execution_error',{'node_id':'1','node_type':node['class_type'],
                'prompt_id':prompt,'exception_message':json.dumps({'code':code,'details':{'subcode':subcode}})}]]}
        else:
            fixture=self.plan['categories'][name];basis=Fraction(fixture['oracle']['time_base'])
            frames=[{'index':i,'pts':pts,'time_base_num':basis.numerator,'time_base_den':basis.denominator,
                     'time_seconds':float(pts*basis),'sha256':str(i)*64} for i,pts in enumerate(fixture['expected_sample_pts'])]
            if self.corrupt=='fabricated-target' and name=='vfr':
                for i,frame in enumerate(frames):frame['pts']=(2*i+1)*12288;frame['time_seconds']=2*i+1
            metadata={'source_sha256':fixture['sha256'],'bytes':fixture['bytes'],'duration_seconds':8,
                'decoder_backend':'ffmpeg-cli/pyav-probe','frames':frames,'run_token':f'{self.submits:032x}',
                'cancel_epoch':0,'resource_release':{'state':'released'}}
            if decoder:outputs={'1':{'text':[json.dumps(metadata)]}}
            else:
                self.calls+=0 if self.corrupt=='cached' else 4
                raw=json.dumps({'frame_raw_responses':[json.dumps({'model':base.MODEL,'done':True,'message':{'content':'red shape'}})]*4})
                spec=json.dumps(prompt_spec(mode='realistic',observations=['red shape'],inferences=[],unknowns=[],creative_prompt='red shape',tags=['red']))
                outputs={'1':{'text':[raw,spec,json.dumps(metadata)]}}
                if self.corrupt=='leftover':(self.root/'temp/lvw-video-orphan').mkdir(exist_ok=True)
        self.value={prompt:{'prompt':[0,prompt,copy.deepcopy(graph)],'status':status,'outputs':outputs}}
        return prompt
    def _json_request(self,url,**kwargs):
        if url.endswith('/api/ps'):return 200,{'models':[]}
        return 200,copy.deepcopy(self.value)


class PublicPhaseTests(unittest.TestCase):
    def prepare(self,root,corrupt=None,authorize=None):
        root=Path(root);(root/'input').mkdir();(root/'temp').mkdir();plan=inputs();references={}
        for name,row in {**plan['categories'],**plan['negatives']}.items():
            reference=Path(row['path']).name;shutil.copyfile(ROOT/row['path'],root/'input'/reference);references[name]=reference
        (root/'input/empty.mp4').touch();references['empty']='empty.mp4'
        with (root/'input/oversize.mp4').open('xb') as stream:stream.truncate(256*1024*1024+1)
        references['oversize']='oversize.mp4';references.update(PATH_REFERENCES)
        (root/'outside-input').mkdir();(root/'outside-input/source.mp4').write_bytes(b'owned-not-private')
        (root/'input/redirect').symlink_to(root/'outside-input',target_is_directory=True)
        driver=Native(plan,references,root,corrupt)
        phase=PublicPhase(driver,root,run_id='synthetic',candidate_sha='a'*40,authorization_sha256='b'*64,
            fixture_plan=plan,references=references,authorize=authorize or (lambda action,case:None))
        return phase,driver

    def test_fixed_public_decoder_ten_negatives_four_categories_drive_real_oracles(self):
        with tempfile.TemporaryDirectory() as temp:
            phase,driver=self.prepare(temp);result=phase.run()
            self.assertEqual('PUBLIC_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE',result['decision'])
            self.assertFalse(result['stage_pass_claim']);self.assertEqual(15,result['test_counts']['PASS'])
            self.assertEqual(15,driver.submits);self.assertEqual(16,driver.calls)
            self.assertEqual([14336,38912,63488,87040],result['cases']['category-vfr']['oracle']['frozen_timeline']['selected_pts'])
            for case in FIXED_CASES:
                graph=json.loads((phase.directory/(case+'.graph.json')).read_text())
                self.assertEqual('LVWControlledVideoInput' if case=='native-decoder' else 'LVWVideoPromptOwner',graph['1']['class_type'])
            with self.assertRaises(ValueError):phase.run()

    def test_fabricated_pts_cached_calls_wrong_failure_and_residue_never_pass(self):
        for corrupt in ('fabricated-target','cached','wrong-error','negative-model-call','leftover','owner'):
            with self.subTest(corrupt=corrupt),tempfile.TemporaryDirectory() as temp:
                phase,driver=self.prepare(temp,corrupt);result=phase.run()
                self.assertEqual('NO_GO',result['decision']);self.assertEqual(15,len(result['cases']))
                self.assertEqual(1,result['test_counts']['FAIL']);self.assertLess(driver.submits,15)
                self.assertTrue((phase.directory/'phase-receipt.json').exists())

    def test_authorization_denial_or_changed_source_prevents_submission(self):
        for case in ('auth','source'):
            def grant(action,case_id):
                if action=='public_submit':raise base.StopProbe('BUDGET_EXPIRED')
            with self.subTest(case=case),tempfile.TemporaryDirectory() as temp:
                phase,driver=self.prepare(temp,authorize=grant if case=='auth' else None)
                if case=='source':(Path(temp)/'input/vfr.mp4').write_bytes(b'changed')
                result=phase.run();self.assertEqual('NO_GO',result['decision']);self.assertEqual(0,driver.submits)
                self.assertEqual(14,result['test_counts']['NOT_RUN'])


if __name__=='__main__':unittest.main()
