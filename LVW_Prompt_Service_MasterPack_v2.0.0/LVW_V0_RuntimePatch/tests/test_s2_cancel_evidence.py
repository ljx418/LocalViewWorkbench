"""Native audit producer -> cancellation oracle with controlled synthetic facts."""
import copy
import hashlib
import os
import unittest

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.video_evidence import NativeAudit
from tools.v0_s2_cancel_evidence import cancellation_trace
from tools.v0_s2_checkpoint_oracles import EvidenceError
from LVW_V0_RuntimePatch.tests.test_s2_native_evidence import binding


def prefix(count):
    raw=('[GIN] 200 POST "/api/chat"\n'*count).encode()
    return {'raw_log':raw.decode(),'source_log_bytes':len(raw),'source_log_sha256':hashlib.sha256(raw).hexdigest(),'chat_calls':count}


def facts(kind='provider',release_at=7.5):
    b=binding();events=[];clock=[0]
    proof={'verified_compute_pids':[],'snapshot':{'listener_pid':10,'listener_address':'127.0.0.1','listener_port':11434,
        'processes':[{'pid':10,'parent_pid':1,'start_ticks':100,'name':'ollama.exe'}]}}
    audit=NativeAudit(b,sink=events.append,check_root=lambda:copy.deepcopy(proof),clock=lambda:clock[0],wall=lambda:1000+clock[0])
    token='run';audit.start(token)
    release={'state':'not_requested'}
    if kind=='provider':
        clock[0]=1;audit.event(token,'source_prepared',source_sha256='d'*64,frames=[])
        clock[0]=2;audit.event(token,'gpu_admission_started')
        clock[0]=3;audit.event(token,'gpu_admission_completed',snapshot={'gpu_used_mib':100})
        clock[0]=4;audit.before_provider(token,{'model':'gemma4:26b'},120)
        clock[0]=4.1;audit.verify_provider_owner(token)
        clock[0]=4.2;audit.event(token,'provider_request_sent',call_index=0)
        clock[0]=5.2;audit.event(token,'provider_connection_closed',call_index=0)
        clock[0]=5.3;audit.before_control(token)
        clock[0]=5.4;audit.event(token,'unload_acknowledged',call_index=0,response={'done':True})
        clock[0]=5.5;audit.event(token,'model_inventory_empty',call_index=0,observed_monotonic_seconds=5.5,api_ps={'models':[]})
        elapsed=release_at-5.25
        release={'state':'released','checks':1,'loaded_models':0,'model_inventory_empty_monotonic':5.5,
            'baseline_gpu_mib':100,'started_monotonic_seconds':5.25,'elapsed_seconds':elapsed,
            'gpu_samples':[{'elapsed_seconds':elapsed-2+i,'gpu_used_mib':1124} for i in range(3)]}
        clock[0]=release_at;audit.event(token,'physical_release',call_index=0,release=copy.deepcopy(release))
    clock[0]=release_at+1
    audit.finish(token,status='cancelled',resource_state='released',error_code='JOB_CANCELLED',cancel_epoch=1,
        cancel_accepted_at=5 if kind=='provider' else .1,release=copy.deepcopy(release))
    return {'events':events,'binding':b,'token':token,'owner_pid':os.getpid(),'kind':kind,
        'ack':{'elapsed_seconds':1,'http_status':200,'response':{'run_token':token,'cancel_epoch':1,'status':'cancelling','resource_state':'releasing'}},
        'before':prefix(10),'after':prefix(11 if kind=='provider' else 10),
        'resource_samples':[{'monotonic_seconds':release_at-1.5+i,'gpu_used_mib':1124} for i in range(2)]}


class CancelEvidenceTests(unittest.TestCase):
    def test_distinct_prepare_and_provider_traces_verify_without_claiming_stage_or_kernel_timestamp(self):
        for kind in ('preparation','provider'):
            value=facts(kind);result=cancellation_trace(**value)
            self.assertFalse(result['stage_pass_claim']);self.assertFalse(result['result_published'])
            self.assertEqual(0 if kind=='preparation' else 1,result['provider_calls'])
            self.assertIn('final_owned_process_and_temp_cleanup',result['remaining_obligations'])
            if kind=='provider':self.assertFalse(result['actual_gpu_kernel_stop_timestamp_claimed'])

    def test_feedback_and_release_exact_limits_pass_one_over_fails(self):
        value=facts(release_at=35);result=cancellation_trace(**value)
        self.assertEqual(30,result['release_from_cancel_seconds'])
        for case in ('ack-over','release-over'):
            value=facts(release_at=35.0001 if case=='release-over' else 35)
            if case=='ack-over':value['ack']['elapsed_seconds']=1.0001
            with self.subTest(case=case),self.assertRaises(EvidenceError):cancellation_trace(**value)

    def test_socket_only_old_run_late_publication_and_false_raw_witnesses_fail(self):
        for case in ('socket-only','old-auth','wrong-owner','published','wrong-token','missing-cancel','wrong-root',
                     'nonempty-models','gpu-one-over','two-gpu-samples','sampler-disagrees','wrong-raw-hash',
                     'wrong-counter','missing-close','cancel-outside-call','expired-work','unknown-event',
                     'missing-root','missing-verified','missing-control','duplicate-sampler','incomplete-prefix','wrong-attempt'):
            value=facts();events=value['events']
            def select(name):return next(e for e in events if e['event']==name)
            if case=='socket-only':events[:]=[e for e in events if e['event'] not in ('physical_release','model_inventory_empty')]
            if case=='old-auth':events[0]['authorization_sha256']='0'*64
            if case=='wrong-owner':value['owner_pid']+=1
            if case=='published':events[-1]['result_published']=True
            if case=='wrong-token':value['ack']['response']['run_token']='old'
            if case=='missing-cancel':events[:]=[e for e in events if e['event']!='cancel_accepted']
            if case=='wrong-root':select('provider_owner_verified')['root_proof']['snapshot']['processes'][0]['start_ticks']=99
            if case=='nonempty-models':select('model_inventory_empty')['api_ps']['models']=[{}]
            if case=='gpu-one-over':select('physical_release')['release']['gpu_samples'][-1]['gpu_used_mib']=1125
            if case=='two-gpu-samples':select('physical_release')['release']['gpu_samples'].pop()
            if case=='sampler-disagrees':value['resource_samples'][0]['gpu_used_mib']=20000
            if case=='wrong-raw-hash':value['after']['source_log_sha256']='0'*64
            if case=='wrong-counter':value['after']['chat_calls']=12
            if case=='missing-close':events[:]=[e for e in events if e['event']!='provider_connection_closed']
            if case=='cancel-outside-call':select('cancel_accepted')['observed_monotonic_seconds']=5.3
            if case=='expired-work':select('provider_request_sent')['wall_seconds']=1100
            if case=='unknown-event':select('provider_request_sent')['event']='fake_success'
            if case=='missing-root':select('provider_attempt').pop('root_proof')
            if case=='missing-verified':events[:]=[e for e in events if e['event']!='provider_owner_verified']
            if case=='missing-control':events[:]=[e for e in events if e['event']!='release_owner_verified']
            if case=='duplicate-sampler':value['resource_samples'][1]=copy.deepcopy(value['resource_samples'][0])
            if case=='incomplete-prefix':
                raw=value['after']['raw_log'].rstrip('\n');value['after'].update(raw_log=raw,source_log_bytes=len(raw.encode()),source_log_sha256=hashlib.sha256(raw.encode()).hexdigest())
            if case=='wrong-attempt':select('provider_attempt')['call_index']=1
            with self.subTest(case=case),self.assertRaises(EvidenceError):cancellation_trace(**value)

    def test_preparation_cannot_hide_gpu_admission_or_provider_activity(self):
        for case in ('gpu','provider'):
            value=facts('preparation')
            if case=='gpu':value['events'].insert(1,{**value['events'][0],'event':'gpu_admission_started'})
            else:value['after']=prefix(11)
            with self.subTest(case=case),self.assertRaises(EvidenceError):cancellation_trace(**value)


if __name__=='__main__':unittest.main()
