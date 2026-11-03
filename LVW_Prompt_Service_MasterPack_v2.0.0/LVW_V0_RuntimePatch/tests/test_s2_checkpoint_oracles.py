import unittest

from tools.v0_s2_checkpoint_oracles import EvidenceError,performance_oracle,cancellation_oracle


def records():
    return [{"run_id":"one","candidate_sha":"a"*40,"sample_run_id":f"{kind}-{i}","phase":"hot",
             "kind":kind,"duration_seconds":1,"provider_calls":1 if kind=="image" else 4,
             "warm_model_snapshots":[{'call_index':j,'elapsed_seconds':j/4,
                 'api_ps':{'models':[{'model':'gemma4:26b','digest':'a'*64,'size_vram':100}]}}
                 for j in range(1 if kind=='image' else 4)],
             "outcome":"succeeded","oom":False,"resource_samples":[
                 {"elapsed_seconds":t,"gpu_used_mib":23551,"available_ram_mib":2048} for t in (0,1)]}
            for kind in ("image","video") for i in range(10)]


class OracleTests(unittest.TestCase):
    def check(self,values):return performance_oracle(values,run_id="one",candidate_sha="a"*40,expected_model_digest='a'*64)
    def test_fixed_denominator_and_p95_use_all_runs(self):
        self.assertEqual(10,self.check(records())["performance"]["video"]["count"])
        for count in (0,19,21):
            with self.subTest(count=count),self.assertRaises(EvidenceError):self.check((records()*2)[:count])
    def test_identity_skip_duplicate_and_mock_denominator_rejected(self):
        for key,value in [("run_id","old"),("candidate_sha","b"*40),("outcome","skipped"),
                          ("provider_calls",0),("oom",True),("sample_run_id","image-1")]:
            values=records();values[0][key]=value
            with self.subTest(key=key),self.assertRaises(EvidenceError):self.check(values)
    def test_resource_exact_one_over_and_missing_trace(self):
        for key,value in [("gpu_used_mib",23552),("available_ram_mib",2047),("elapsed_seconds",4)]:
            values=records();values[0]["resource_samples"][1][key]=value
            with self.subTest(key=key),self.assertRaises(EvidenceError):self.check(values)
        values=records();values[0]["resource_samples"]=[]
        with self.assertRaises(EvidenceError):self.check(values)
    def test_slow_run_not_hidden_by_average(self):
        values=records();values[0]["duration_seconds"]=181
        values[0]["resource_samples"]=[{"elapsed_seconds":i,"gpu_used_mib":1,"available_ram_mib":4096} for i in range(182)]
        with self.assertRaisesRegex(EvidenceError,"P95"):self.check(values)
    def test_hot_label_cannot_replace_per_call_residency_and_frozen_digest(self):
        values=records();values[0].pop('warm_model_snapshots')
        with self.assertRaises(EvidenceError):self.check(values)
        for mutation in ('unloaded','changed-model','changed-digest','cpu-only','omitted-video-frame','old-observation'):
            values=records();snapshots=values[10]['warm_model_snapshots']
            if mutation=='unloaded':snapshots[1]['api_ps']['models']=[]
            if mutation=='changed-model':snapshots[1]['api_ps']['models'][0]['model']='other'
            if mutation=='changed-digest':snapshots[1]['api_ps']['models'][0]['digest']='b'*64
            if mutation=='cpu-only':snapshots[1]['api_ps']['models'][0]['size_vram']=0
            if mutation=='omitted-video-frame':snapshots.pop()
            if mutation=='old-observation':snapshots[1]['elapsed_seconds']=0
            with self.subTest(mutation=mutation),self.assertRaises(EvidenceError):self.check(values)
        with self.assertRaises(EvidenceError):performance_oracle(records(),run_id='one',candidate_sha='a'*40,expected_model_digest='unknown')
    def test_exact_p95_thresholds_are_accepted(self):
        values=records()
        for index,seconds in ((0,180),(10,300)):
            values[index]["duration_seconds"]=seconds
            values[index]["resource_samples"]=[{"elapsed_seconds":i,"gpu_used_mib":23551,"available_ram_mib":2048} for i in range(seconds+1)]
        result=self.check(values)
        self.assertEqual(180,result["performance"]["image"]["p95_seconds"])
        self.assertEqual(300,result["performance"]["video"]["p95_seconds"])
    def test_cancellation_exact_and_one_over(self):
        value={"ack_seconds":1,"actual_stop_seconds":2,"release_seconds":32,
               "late_result_discarded":True,"draft_unchanged":True,"owned_connection_only":True,
               "ports_and_temp_clean":True,"non_owned_terminations":0}
        self.assertEqual(30,cancellation_oracle(value)["release_after_stop_seconds"])
        for key,bad in [("ack_seconds",1.001),("release_seconds",32.001),("draft_unchanged",False),("non_owned_terminations",1)]:
            with self.subTest(key=key),self.assertRaises(EvidenceError):cancellation_oracle({**value,key:bad})


if __name__=="__main__":unittest.main()
