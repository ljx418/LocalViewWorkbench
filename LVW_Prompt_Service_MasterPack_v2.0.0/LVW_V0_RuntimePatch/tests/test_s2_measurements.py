"""Synthetic artifact joins, never runtime or semantic-quality acceptance."""
import copy
import hashlib
import json
import unittest

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import prompt_spec
from tools.v0_s2_measurements import hot_record
from tools.v0_s2_checkpoint_oracles import EvidenceError,performance_oracle


def artifacts(kind='video'):
    candidate='a'*40;auth='b'*64;source='e'*64;prompt='p1'
    binding={'candidate_sha':candidate,'authorization_sha256':auth,'model_digest':'d'*64,
             'ollama_pid':10,'ollama_start_ticks':100,'nvidia_smi_sha256':'1'*64,'issued_at':900,'expires_at':1100}
    root={'listener_pid':10,'listener_address':'127.0.0.1','listener_port':11434,
          'processes':[{'pid':10,'parent_pid':1,'start_ticks':100,'name':'ollama.exe'}]}
    lineage=copy.deepcopy(root);lineage['processes'].append({'pid':11,'parent_pid':10,'start_ticks':101,'name':'ollama.exe'})
    count=4 if kind=='video' else 1
    raws=[json.dumps({'model':'gemma4:26b','done':True,'message':{'content':'{"observations":["red shape"]}'},'frame':i}) for i in range(count)]
    spec=json.dumps(prompt_spec(mode='realistic',observations=['red shape'],inferences=[],unknowns=[],creative_prompt='red shape',tags=['red']))
    frames=[{'index':i,'pts':i*2+1,'time_base_num':1,'time_base_den':2,'time_seconds':i+.5,'sha256':str(i)*64} for i in range(4)]
    if kind=='video':
        graph={'1':{'class_type':'LVWVideoPromptOwner','inputs':{}}}
        text=[json.dumps({'frame_raw_responses':raws}),spec,json.dumps({'source_sha256':source,'run_token':'f'*32,'cancel_epoch':0,'frames':frames})]
        outputs={'1':{'text':text}}
    else:
        graph={'1':{'class_type':'LVWControlledImageInput','inputs':{}},
               '2':{'class_type':'LVWImagePromptBridge','inputs':{'image':['1',0]}}}
        outputs={'2':{'text':[raws[0],spec]}}
    history={prompt:{'status':{'status_str':'success'},'prompt':[0,prompt,graph], 'outputs':outputs}}
    def event(name,t,**kw):
        return {'event':name,'candidate_sha':candidate,'authorization_sha256':auth,'request_number':1,
                'monotonic_seconds':t,'elapsed_seconds':t-100.1,'wall_seconds':1000+t-100,**kw}
    root_proof={'verified_compute_pids':[],'snapshot':root}
    events=[event('request_started',100.2,kind=kind,expected_calls=count,root_proof=root_proof)]
    for i in range(count):
        resource={'owner_pid':20,'compute_pids':[11,20],'gpu_total_mib':24564,'gpu_used_mib':20000,
                  'gpu_free_mib':4564,'available_ram_mib':4096,
                  'native_lineage':{'verified_compute_pids':[11,20],'snapshot':lineage}}
        events.extend([event('before_call',100.3+.7*i,call_index=i,request_payload_sha256='2'*64,
                            resource_admission=resource,api_ps={'models':[{'model':'gemma4:26b','digest':'d'*64,'size_vram':1000}]}),
                       event('after_call',100.6+.7*i,call_index=i,provider_raw_sha256=hashlib.sha256(raws[i].encode()).hexdigest())])
    events.append(event('request_finished',103.5,outcome='succeeded',restored_unloaded=True,root_proof=root_proof))
    points=[{'sample_index':i,'monotonic_seconds':100+i,'gpu_used_mib':20000,'available_ram_mib':4096,
             'private_bytes':{'10':1000,'20':2000}} for i in range(5)]
    receipt={'decision':'RESOURCE_TRACE_COLLECTED_NOT_STAGE_ACCEPTANCE','owned_gpu_query_exited':True,'samples':5,
             'nvidia_binary_sha256':'1'*64,'nvidia_binary_sha256_after':'1'*64,'private_process_set':[10,20]}
    return dict(run_id='run',sample_run_id=kind+'-1',candidate_sha=candidate,authorization_sha256=auth,kind=kind,
        binding=binding,history=history,prompt_id=prompt,source_sha256=source,chat_calls_before=0,chat_calls_after=count,
        warm_events=events,resource_samples=points,sampler_receipt=receipt,started=100,finished=104)


class MeasurementTests(unittest.TestCase):
    def test_public_history_warm_and_resource_join_satisfies_fixed_oracle_without_retiming(self):
        records=[]
        for kind in ('image','video'):
            for index in range(10):
                values=artifacts(kind);values['sample_run_id']=kind+'-'+str(index)
                records.append(hot_record(**values))
        result=performance_oracle(records,run_id='run',candidate_sha='a'*40,expected_model_digest='d'*64)
        self.assertEqual(4,result['performance']['video']['p95_seconds'])
        self.assertEqual(0,records[0]['resource_samples'][0]['elapsed_seconds'])
        self.assertAlmostEqual(.3,records[0]['warm_model_snapshots'][0]['elapsed_seconds'])

    def test_cross_run_raw_lineage_restore_and_sampler_corruption_fail_closed(self):
        for case in ('old-auth','wrong-raw','foreign-pid','pid-reused','restoration-omitted','sampler-failed',
                     'changed-binary','omitted-private','source-changed','event-shifted','no-final-sample','invalid-spec','expired-call','bad-prelude'):
            values=artifacts();events=values['warm_events']
            if case=='old-auth':events[1]['authorization_sha256']='0'*64
            if case=='wrong-raw':events[2]['provider_raw_sha256']='0'*64
            if case=='foreign-pid':events[1]['resource_admission']['compute_pids']=[99]
            if case=='pid-reused':events[1]['resource_admission']['native_lineage']['snapshot']['processes'][0]['start_ticks']=99
            if case=='restoration-omitted':events[-1]['restored_unloaded']=False
            if case=='sampler-failed':values['sampler_receipt']['decision']='NO_GO'
            if case=='changed-binary':values['sampler_receipt']['nvidia_binary_sha256_after']='0'*64
            if case=='omitted-private':values['resource_samples'][1]['private_bytes'].pop('10')
            if case=='source-changed':values['source_sha256']='0'*64
            if case=='event-shifted':events[1]['monotonic_seconds']+=.01
            if case=='no-final-sample':values['resource_samples'].pop();values['sampler_receipt']['samples']=4
            if case=='invalid-spec':values['history']['p1']['outputs']['1']['text'][1]='{"schema_version":"lvw.prompt/1"}'
            if case=='expired-call':events[1]['wall_seconds']=1100
            if case=='bad-prelude':
                points=values['resource_samples']
                points.insert(0,{'sample_index':0,'monotonic_seconds':99,'gpu_used_mib':23552,
                                 'available_ram_mib':4096,'private_bytes':{'10':1000,'20':2000}})
                for index,point in enumerate(points):point['sample_index']=index
                values['sampler_receipt']['samples']=6
            with self.subTest(case=case),self.assertRaises(EvidenceError):hot_record(**values)

    def test_image_must_traverse_actual_controlled_input_to_bridge(self):
        values=artifacts('image');values['history']['p1']['prompt'][2]['2']['inputs']['image']=['other',0]
        with self.assertRaises(EvidenceError):hot_record(**values)


if __name__=='__main__':unittest.main()
