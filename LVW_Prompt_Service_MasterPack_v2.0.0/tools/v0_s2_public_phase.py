"""Public native decoder/category/file-safety phase of a sealed S2 checkpoint.

No CLI, authorization, service startup, sample creation or Stage PASS. The parent
must bind the source/fixture set and own lifecycle, sampling and final cleanup.
"""
import copy
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import time

from tools.v0_s2_driver import ROOT,base
from tools.v0_s2_checkpoint_oracles import public_video_oracle,EvidenceError
from tools.v0_s2_native_component import metadata_oracle
from tools.v0_s2_measurements import spec_validator
from tools.v0_s2_stage_inputs import CATEGORIES

NEGATIVES={
 'over-duration':('MEDIA_LIMIT_EXCEEDED','VIDEO_DURATION_LIMIT'),
 'fake-extension.mp4':('MEDIA_INVALID',None),'corrupt.mp4':('MEDIA_INVALID',None),'truncated.mov':('MEDIA_INVALID',None),
 'traversal':('PATH_FORBIDDEN','VIDEO_REFERENCE_FORBIDDEN'),
 'absolute':('PATH_FORBIDDEN','VIDEO_REFERENCE_FORBIDDEN'),
 'unc':('PATH_FORBIDDEN','VIDEO_REFERENCE_FORBIDDEN'),
 'empty':('MEDIA_INVALID','VIDEO_EMPTY'),'oversize':('MEDIA_LIMIT_EXCEEDED','VIDEO_BYTE_LIMIT'),
 'reparse':('PATH_FORBIDDEN','VIDEO_REFERENCE_FORBIDDEN')}
FIXED_CASES=('native-decoder',)+tuple('negative-'+name for name in NEGATIVES)+tuple('category-'+name for name in CATEGORIES)
PATH_REFERENCES={'traversal':'../blocked.mp4','absolute':'C:/lvw-forbidden/nonexistent.mp4',
                 'unc':'\\\\127.0.0.1\\lvw-forbidden\\nonexistent.mp4','reparse':'redirect/source.mp4'}


def encoded(value):return (json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))+'\n').encode()


def exact_timeline(metadata,fixture):
    try:
        frames=metadata['frames'];basis=Fraction(fixture['oracle']['time_base'])
        if len(frames)!=4:raise ValueError()
        for index,(frame,pts) in enumerate(zip(frames,fixture['expected_sample_pts'])):
            if (frame['index']!=index or type(frame['pts']) is not int or frame['pts']!=pts
                    or Fraction(frame['time_base_num'],frame['time_base_den'])!=basis
                    or abs(frame['time_seconds']-float(pts*basis))>1e-9):raise ValueError()
        if metadata['source_sha256']!=fixture['sha256']:raise ValueError()
        return {'source_sha256':fixture['sha256'],'selected_pts':[f['pts'] for f in frames],'time_base':str(basis)}
    except (KeyError,TypeError,ValueError,ZeroDivisionError) as error:raise EvidenceError('public frame timeline differs from frozen actual PTS') from error


def failure_oracle(history,prompt_id,graph,*,code,subcode,chat_before,chat_after):
    """Require the production owner's actual execution_error, not any failure."""
    try:
        record=history[prompt_id]
        if (record['prompt'][1]!=prompt_id or record['prompt'][2]!=graph
                or record['status']['status_str']!='error' or record.get('outputs')
                or type(chat_before) is not int or type(chat_after) is not int or chat_before!=chat_after):raise ValueError()
        errors=[]
        for name,payload in record['status']['messages']:
            if name!='execution_error':continue
            if (str(payload['node_id'])!='1' or payload['node_type']!='LVWVideoPromptOwner'
                    or payload['prompt_id']!=prompt_id):raise ValueError()
            error=json.loads(payload['exception_message'])
            if error['code']!=code or (subcode is not None and error['details']['subcode']!=subcode):raise ValueError()
            errors.append({'code':error['code'],'subcode':error.get('details',{}).get('subcode')})
        if len(errors)!=1:raise ValueError()
        return {'production_error':errors[0],'provider_calls':0,'stage_pass_claim':False}
    except (KeyError,TypeError,ValueError) as error:raise EvidenceError('file negative lacks exact production failure/zero provider proof') from error


class PublicPhase:
    def __init__(self,driver,run_root,*,run_id,candidate_sha,authorization_sha256,fixture_plan,references,authorize):
        if (not callable(authorize) or not callable(getattr(driver,'resource_observer',None))
                or getattr(driver,'warm_benchmark',False) is not False):raise ValueError('owned monitored default runtime required')
        if (not re.fullmatch('[0-9a-f]{40}',candidate_sha) or not re.fullmatch('[0-9a-f]{64}',authorization_sha256)
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}',run_id)):raise ValueError('phase identity invalid')
        if (fixture_plan.get('kind')!='FROZEN_STRUCTURAL_INPUT_PLAN_NOT_ACCEPTANCE'
                or fixture_plan.get('vfr_sampling_exercises_rounding') is not True
                or set(fixture_plan['categories'])!=set(CATEGORIES)
                or set(fixture_plan['negatives'])!={'over-duration','fake-extension.mp4','corrupt.mp4','truncated.mov'}):
            raise ValueError('complete frozen preparation02-type input plan required')
        if set(references)!=set(CATEGORIES)|set(NEGATIVES):raise ValueError('complete public reference set required')
        for name,reference in references.items():
            if name in PATH_REFERENCES:
                if reference!=PATH_REFERENCES[name]:raise ValueError('invalid fixed path-negative reference')
            elif not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,95}',reference) or '..' in reference:
                raise ValueError('invalid run-owned reference')
        self.driver=driver;self.root=Path(run_root).resolve(strict=True);self.directory=self.root/'temp/public-phase'
        self.run_id=run_id;self.candidate=candidate_sha;self.auth=authorization_sha256
        self.plan=copy.deepcopy(fixture_plan);self.references=copy.deepcopy(references);self.authorize=authorize
        self.actions=[];self.artifacts=[];self.seen=set();self.executed=False

    def action(self,name,case):
        self.authorize(name,case)
        value={'ordinal':len(self.actions)+1,'action':name,'case_id':case}
        with (self.directory/'actions.jsonl').open('ab') as stream:
            stream.write(encoded(value));stream.flush();os.fsync(stream.fileno())
        self.actions.append(value)

    def artifact(self,name,value):
        raw=encoded(value)
        if len(raw)>8*1024*1024:raise base.StopProbe('PUBLIC_ARTIFACT_LIMIT')
        with (self.directory/name).open('xb') as stream:stream.write(raw)
        item={'file':name,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)};self.artifacts.append(item)
        return item

    def request(self,path,case,*,payload=None):
        self.action('control:'+path,case)
        return self.driver._json_request(base.COMFY_URL+path,payload=payload,timeout=5,
                                        observer=self.driver.resource_observer)[1]

    def history(self,prompt_id,case):
        if not re.fullmatch('[0-9a-fA-F-]{1,80}',prompt_id) or prompt_id in self.seen:raise base.StopProbe('PUBLIC_PROMPT_ID_INVALID_OR_REUSED')
        self.seen.add(prompt_id);deadline=time.monotonic()+480
        point=self.driver.guard_point(after=None)
        while time.monotonic()<deadline:
            point=self.driver.guard_point(after=point['monotonic_seconds'])
            value=self.request('/history/'+prompt_id,case)
            if prompt_id in value:return value
        raise base.StopProbe('PUBLIC_HISTORY_TIMEOUT')

    def chat_count(self,case,position):
        self.action('independent_provider_count',case);snapshot=self.driver.chat_log_snapshot()
        raw=snapshot['raw_log'].encode('utf-8')
        observed=sum('POST' in line and '"/api/chat"' in line for line in snapshot['raw_log'].splitlines())
        if (hashlib.sha256(raw).hexdigest()!=snapshot['source_log_sha256'] or len(raw)!=snapshot['source_log_bytes']
                or type(snapshot['chat_calls']) is not int or snapshot['chat_calls']!=observed):
            raise EvidenceError('independent provider prefix/count mismatch')
        self.artifact(case+'.provider-'+position+'.json',snapshot)
        return observed

    def verify_source(self,name):
        reference=self.references[name]
        if name in ('traversal','absolute','unc'):return
        path=self.root/'input'/reference
        if name=='reparse':
            target=(self.root/'input/redirect').resolve(strict=True);target.relative_to(self.root)
            try:target.relative_to((self.root/'input').resolve(strict=True))
            except ValueError:return
            raise base.StopProbe('REPARSE_FIXTURE_NOT_OUTSIDE_INPUT')
        if path.is_symlink() or not path.is_file():raise base.StopProbe('PUBLIC_STAGED_FIXTURE_INVALID')
        path.resolve(strict=True).relative_to((self.root/'input').resolve(strict=True))
        if name=='empty':
            if path.stat().st_size!=0:raise base.StopProbe('EMPTY_FIXTURE_INVALID')
            return
        if name=='oversize':
            if path.stat().st_size!=256*1024*1024+1:raise base.StopProbe('OVERSIZE_FIXTURE_INVALID')
            return
        row=self.plan['categories'].get(name) or self.plan['negatives'][name]
        if path.stat().st_size!=row['bytes'] or path.stat().st_size>8*1024*1024:raise base.StopProbe('PUBLIC_SOURCE_SIZE_CHANGED')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise base.StopProbe('PUBLIC_SOURCE_HASH_CHANGED')

    def execute_case(self,case):
        name='vfr' if case=='native-decoder' else case.removeprefix('negative-').removeprefix('category-')
        self.verify_source(name)
        self.action('owned_listener_proof_before',case)
        roots={str(port):self.driver.owned_listener_birth(port) for port in (8191,11434)}
        self.action('model_inventory_before',case)
        before_ps=self.driver._json_request(base.OLLAMA_URL+'/api/ps',timeout=5)[1]
        if before_ps.get('models')!=[]:raise base.StopProbe('PUBLIC_PHASE_REQUIRES_UNLOADED_MODEL')
        before=self.chat_count(case,'before')
        graph=json.loads((ROOT/'LVW_V0_RuntimePatch/workflows/video_reverse_prompt_v0.api.json').read_text())
        if case=='native-decoder':graph={'1':{'class_type':'LVWControlledVideoInput','inputs':{}}}
        graph['1']['inputs']['video_reference']=self.references[name]
        self.artifact(case+'.graph.json',graph)
        self.action('public_submit',case);prompt_id=self.driver.submit(graph)
        history=self.history(prompt_id,case);self.artifact(case+'.history.json',history)
        after=self.chat_count(case,'after')
        if case=='native-decoder':
            record=history[prompt_id]
            if record['prompt'][2]!=graph or record['prompt'][1]!=prompt_id:raise EvidenceError('decoder graph mismatch')
            text=base.workflow_oracle(history,prompt_id,'1')
            if len(text)!=1 or after!=before:raise EvidenceError('decoder-only path invoked provider or lacks metadata')
            metadata=json.loads(text[0]);fixture=self.plan['categories']['vfr']
            value=metadata_oracle(metadata,sample_sha256=fixture['sha256'],sample_bytes=fixture['bytes'])
            value['frozen_timeline']=exact_timeline(metadata,fixture)
        elif case.startswith('negative-'):
            code,subcode=NEGATIVES[name]
            value=failure_oracle(history,prompt_id,graph,code=code,subcode=subcode,chat_before=before,chat_after=after)
        else:
            fixture=self.plan['categories'][name]
            if history[prompt_id]['prompt'][2]!=graph:raise EvidenceError('category graph mismatch')
            value=public_video_oracle(history,prompt_id,source_sha256=fixture['sha256'],expected_model=base.MODEL,
                                      chat_calls_before=before,chat_calls_after=after)
            text=history[prompt_id]['outputs']['1']['text'];spec_validator().validate(json.loads(text[1]))
            metadata=json.loads(text[2]);value['frozen_timeline']=exact_timeline(metadata,fixture)
            value['resource_release']=metadata['resource_release']
        self.verify_source(name)
        if list((self.root/'temp').glob('lvw-video-*')):raise EvidenceError('public video snapshot remains after terminal history')
        self.action('owned_listener_proof_after',case)
        observed={str(port):self.driver.owned_listener_birth(port) for port in (8191,11434)}
        if observed!=roots:raise EvidenceError('owned listener identity changed during public case')
        self.action('model_inventory_after',case)
        after_ps=self.driver._json_request(base.OLLAMA_URL+'/api/ps',timeout=5)[1]
        if after_ps.get('models')!=[]:raise EvidenceError('model still loaded after public terminal state')
        return {'oracle':value,'prompt_id':prompt_id,'provider_calls':after-before,'owned_listeners':roots,
                'chat_calls_before':before,'chat_calls_after':after,
                'model_inventory_before':before_ps,'model_inventory_after':after_ps,'video_snapshots_absent':True}

    def run(self):
        if self.executed:raise ValueError('public phase is one-shot')
        self.executed=True;self.directory.mkdir(exist_ok=False)
        result={'run_id':self.run_id,'candidate_sha':self.candidate,'authorization_sha256':self.auth,
            'decision':'NO_GO','stage_pass_claim':False,'cases':{case:{'status':'NOT_RUN'} for case in FIXED_CASES}}
        active=None;interrupted=None
        try:
            for case in FIXED_CASES:
                active=case;row=self.execute_case(case)
                self.artifact(case+'.oracle.json',row);result['cases'][case]={'status':'PASS',**row}
            result['decision']='PUBLIC_PHASE_VERIFIED_NOT_STAGE_ACCEPTANCE'
        except BaseException as error:
            if active is not None:result['cases'][active]={'status':'FAIL','error_type':type(error).__name__}
            result['error_code']=getattr(error,'reason',type(error).__name__)
            if isinstance(error,(KeyboardInterrupt,SystemExit)):interrupted=error
        finally:
            statuses=[row['status'] for row in result['cases'].values()]
            result['test_counts']={'fixed':len(FIXED_CASES),'PASS':statuses.count('PASS'),'FAIL':statuses.count('FAIL'),'NOT_RUN':statuses.count('NOT_RUN')}
            result['actions']=self.actions;result['artifacts']=copy.deepcopy(self.artifacts)
            self.artifact('phase-receipt.json',result)
        if interrupted is not None:raise interrupted
        return result
