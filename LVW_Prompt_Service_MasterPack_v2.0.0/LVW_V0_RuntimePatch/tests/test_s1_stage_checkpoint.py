import argparse
import copy
import importlib.util
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.core import BridgeError
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraftOwner
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.nodes import LVWManualPromptOwner, LVWDraftStateOwner


PACK_ROOT = Path(__file__).resolve().parents[2]
HARNESS = PACK_ROOT / "reports/v0-s1/stage-checkpoint-phase-a/checkpoint.py"
SPEC = importlib.util.spec_from_file_location("s1_stage_checkpoint", HARNESS)
checkpoint = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checkpoint)


class Clipboard:
    def __init__(self): self.values = []
    def write(self, value): self.values.append(value)


def prompt_spec():
    return {"schema_version":"lvw.prompt/1","mode":"realistic",
            "domains":{"observation":["visible subject"],"inference":[],"user_evidence":[],
                       "creative_intent":[],"unknowns":[]},
            "technical":{},"locked_fields":[],"text_zh":"可见主体","text_en":"visible subject",
            "tags":["visible"],"negative":"","template_id":"default","template_version":"1"}


class FakeDriver:
    def __init__(self, lifecycle, args, _evidence):
        self.lifecycle, self.args = lifecycle, args
        self.submissions = 0; self.records = {}; self.counter = 0
        self.listener_terminal_states = {}
        self.base = next(Path(args.temp_parent).glob("lvw-s1-checkpoint-*"))
        self.manual = LVWManualPromptOwner(owner=ManualDraftOwner(
            export_root=self.base/"output/lvw_manual", export_parent=self.base/"output",
            clipboard=Clipboard(), clock=lambda:"2026-10-28T00:00:00Z"))
        self.state = LVWDraftStateOwner()
    def target_hashes(self): return {"main.py":"same","prompt_assistant_state":{"exists":False,"file_count":0,"tree_sha256":None}}
    def preflight(self): return {"gpu_count":1,"max_used_mib":1,"process_match_count":0,"target_listener_count":0}
    def start_ollama(self, _): pass
    def no_cloud_remote_gate(self): return {"ollama_no_cloud":True,"duration_seconds_min":10,
        "samples":[{"connection_count":0,"nonloopback_count":0} for _ in range(5)]}
    def start_comfy(self, *_): pass
    def ownership_summary(self): return {"11434":{"lineage_proven":True},"8191":{"lineage_proven":True}}
    def registry(self): return {name:{} for name in self.lifecycle.REQUIRED_NODES}
    def verify_model(self): return {"model":"gemma4:26b","local_exact_match_count":1,
                                    "digest":checkpoint.AUTHORIZED_MODEL_DIGEST}
    def unload(self): return {"cleanup_http_status":200,"terminal_api_ps_model_count":0}
    def stop_ollama(self):
        self.listener_terminal_states["11434"]={"lineage_reproven":True,"stop_requested":True,
                                                "terminal_absent":True}
    def runtime_guard(self): return {"max_gpu_used_mib":2,"nonloopback_count":0}
    def submit(self, graph):
        self.submissions += 1; self.counter += 1; prompt_id=f"prompt-{self.counter}"
        outputs={}
        try:
            if "2" in graph and graph["2"]["class_type"]=="LVWImagePromptBridge":
                raw=json.dumps({"model":"gemma4:26b","done":True})
                suggestion=json.dumps(prompt_spec(),ensure_ascii=False,separators=(",",":"))
                outputs["2"]={"text":[raw,suggestion]}
                metadata={"source_sha256":checkpoint.AUTHORIZED_SAMPLE_SHA256,"output_dimensions":[1024,768],
                          "resize_strategy":"lanczos_long_edge_1024"}
                response=self.manual.process(natural_zh=json.dumps(metadata),natural_en="",image_prompt="",
                    video_prompt="",tags="",negative="",edit_instruction="",action="preview_json",filename="metadata")
                outputs["3"]={"text":response["ui"]["text"]}
            else:
                node=graph["1"]
                if node["class_type"]=="LVWManualPromptOwner": response=self.manual.process(**node["inputs"])
                else: response=self.state.process(**node["inputs"])
                outputs["1"]={"text":response["ui"]["text"]}
            record={"status":{"status_str":"success","messages":[]},"outputs":outputs}
        except BridgeError as exc:
            record={"status":{"status_str":"error","messages":[["execution_error",{
                "node_id":"1","node_type":graph["1"]["class_type"],"exception_message":str(exc)}]]},"outputs":{}}
        self.records[prompt_id]={prompt_id:record}
        return prompt_id
    def history(self,prompt_id): return self.records[prompt_id]
    def cleanup(self): return {"owned_count":2,"failures":[],"final_target_listener_count":0,
        "owned_listener_terminal_states":[{"port":11434,"terminal_absent":True},{"port":8191,"terminal_absent":True}],
        "owned_wrapper_terminal_states":[{"owner":"ollama","exited":True},{"owner":"comfy","exited":True}],
        "proven":True}
    def post_cleanup_snapshot(self,_): return {"target_listener_count":0,"target_process_match_count":0,"run_temp_absent":True}


class StageCheckpointTests(unittest.TestCase):
    def test_offline_prechecks_keep_fixed_denominator_not_run(self):
        result=checkpoint.run_offline_prechecks(PACK_ROOT)
        self.assertEqual({"denominator":5,"pass":0,"fail":0,"blocked":0,"skipped":0,"not_run":5},
                         result["product_test_counts"])
        self.assertTrue(all(item["product_status"]=="NOT_RUN" for item in result["case_prechecks"]))
        self.assertEqual(0,sum(result["external_actions"].values()))

    def test_default_live_denial_and_plan_has_one_shot_budget(self):
        self.assertEqual(2, checkpoint.main(["--execute-live"]))
        self.assertEqual(24, checkpoint.ONE_SHOT_BUDGET["planned_public_submissions"])
        self.assertEqual(26, checkpoint.ONE_SHOT_BUDGET["max_public_submissions"])
        for key in ("browser_runs","downloads","cloud_calls","external_cost"):
            self.assertEqual(0,checkpoint.ONE_SHOT_BUDGET[key])

    def test_authority_binding_rejects_mutated_request_before_driver(self):
        with tempfile.TemporaryDirectory(dir=PACK_ROOT/"reports/v0-s1") as temp:
            temp=Path(temp); request=temp/"request.json"; authorization=temp/"authorization.json"
            fields={"product_candidate":checkpoint.PRODUCT_CANDIDATE,"harness_candidate":"a"*40,
                    "harness_sha256":"b"*64,"run_id":checkpoint.AUTHORIZED_RUN_ID,
                    "lifecycle_relative":checkpoint.LIFECYCLE_RELATIVE,"lifecycle_sha256":"c"*64,
                    "evidence_relative":checkpoint.AUTHORIZED_EVIDENCE_RELATIVE,
                    "sample_sha256":checkpoint.AUTHORIZED_SAMPLE_SHA256,"budget":checkpoint.ONE_SHOT_BUDGET,
                    "acceptance_hash":checkpoint.ACCEPTANCE_HASH,"model_digest":checkpoint.AUTHORIZED_MODEL_DIGEST,
                    "target_bindings":checkpoint.target_bindings()}
            request_doc=dict(fields,schema_version="lvw.authorization-request/1",request_id="REQ-FUTURE",
                status="PENDING_PROJECT_OWNER_APPROVAL",is_authorization=False,does_not_authorize_execution=True,
                project_id="lvw-prompt-service",stage_id=checkpoint.AUTH_STAGE_ID,workpack_id=checkpoint.AUTH_WORKPACK_ID,
                does_not_authorize_stage_pass=True)
            request.write_text(json.dumps(request_doc),encoding="utf-8")
            auth=dict(fields,schema_version="lvw.authorization/1",request_id="REQ-FUTURE",
                      authorization_id="AUTH-FUTURE",status="GRANTED_ONCE",project_id="lvw-prompt-service",
                      stage_id=checkpoint.AUTH_STAGE_ID,workpack_id=checkpoint.AUTH_WORKPACK_ID,
                      expires_when=checkpoint.AUTH_EXPIRY,does_not_authorize_stage_pass=True,
                      request_sha256=sha256(request.read_bytes()).hexdigest())
            authorization.write_text(json.dumps(auth),encoding="utf-8")
            args=argparse.Namespace(request_record=str(request),authorization_record=str(authorization),
                request_sha256=sha256(request.read_bytes()).hexdigest(),authorization_sha256=sha256(authorization.read_bytes()).hexdigest(),
                harness_candidate="a"*40,harness_sha256="b"*64,authorization_id="AUTH-FUTURE",
                lifecycle_sha256="c"*64,authorization_commit="c"*40,
                comfy_main=checkpoint.AUTHORIZED_COMFY_MAIN,comfy_python=checkpoint.AUTHORIZED_COMFY_PYTHON,
                ollama_exe=checkpoint.AUTHORIZED_OLLAMA_EXE,powershell=checkpoint.AUTHORIZED_POWERSHELL,
                temp_parent=checkpoint.AUTHORIZED_TEMP_PARENT,comfy_url=checkpoint.AUTHORIZED_COMFY_URL,
                ollama_url=checkpoint.AUTHORIZED_OLLAMA_URL)
            mutated=json.loads(request.read_text()); mutated["budget"]["model_calls"]=2
            request.write_text(json.dumps(mutated),encoding="utf-8")
            args.request_sha256=sha256(request.read_bytes()).hexdigest()
            with self.assertRaises(checkpoint.CheckpointError) as raised:
                checkpoint.validate_authority(args,PACK_ROOT)
            self.assertEqual("AUTHORITY_BINDING_MISMATCH",raised.exception.code)

    def test_target_argument_drift_is_rejected_without_loading_lifecycle(self):
        values=dict(comfy_main=checkpoint.AUTHORIZED_COMFY_MAIN,comfy_python=checkpoint.AUTHORIZED_COMFY_PYTHON,
            ollama_exe=checkpoint.AUTHORIZED_OLLAMA_EXE,powershell=checkpoint.AUTHORIZED_POWERSHELL,
            temp_parent=checkpoint.AUTHORIZED_TEMP_PARENT,comfy_url=checkpoint.AUTHORIZED_COMFY_URL,
            ollama_url=checkpoint.AUTHORIZED_OLLAMA_URL)
        checkpoint.validate_target_args(argparse.Namespace(**values))
        for key,bad in (("ollama_exe","C:/other/ollama.exe"),("powershell","pwsh.exe"),
                        ("temp_parent","C:/OtherTemp"),("comfy_url","http://127.0.0.1:8192")):
            broken=dict(values); broken[key]=bad
            with self.subTest(key=key),self.assertRaises(checkpoint.CheckpointError) as raised:
                checkpoint.validate_target_args(argparse.Namespace(**broken))
            self.assertEqual("AUTHORIZED_TARGET_ARGUMENT_MISMATCH",raised.exception.code)

    def test_fake_public_lifecycle_generates_all_machine_facts_once(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp); sample=temp/"sample.bin"; sample.write_bytes(b"synthetic")
            args=argparse.Namespace(repo=PACK_ROOT,run_id=checkpoint.AUTHORIZED_RUN_ID,temp_parent=str(temp),
                sample=str(sample),sample_sha256="pending",comfy_main="unused",comfy_python="unused",ollama_exe="unused",
                powershell="unused",product_candidate=checkpoint.PRODUCT_CANDIDATE,harness_candidate="a"*40,
                harness_sha256="b"*64,lifecycle_sha256="c"*64,authorization_id="AUTH-FUTURE",request_record="",authorization_record="",
                request_sha256="",authorization_sha256="",authorization_commit="")
            sample_hash=sha256(sample.read_bytes()).hexdigest()
            args.sample_sha256=sample_hash
            artifacts=checkpoint.bind_candidate(PACK_ROOT)
            with mock.patch.object(checkpoint,"AUTHORIZED_SAMPLE_SHA256",sample_hash), \
                 mock.patch.object(checkpoint,"validate_authority",return_value={"authorization_id":"AUTH-FUTURE"}), \
                 mock.patch.object(checkpoint,"validate_live_identity",return_value={"product_candidate":checkpoint.PRODUCT_CANDIDATE,
                    "product_artifact_sha256":artifacts,"harness_candidate":"a"*40,"harness_sha256":"b"*64}), \
                 mock.patch.object(checkpoint,"validate_live_paths",return_value={"run_id":checkpoint.AUTHORIZED_RUN_ID}):
                code,result=checkpoint.execute_live(args,driver_factory=FakeDriver)
            self.assertEqual(0,code,result.get("failure"))
            self.assertEqual(24,result["observed"]["public_submissions"])
            self.assertEqual(set(checkpoint.CASE_IDS),set(result["case_facts"]))
            self.assertEqual(1,len(result["model_call_ledger"]))
            self.assertTrue(result["cleanup"]["proven"])
            self.assertEqual(0,result["case_facts"]["V0-A05"]["automatic_retry_count"])

    @staticmethod
    def valid_summary():
        raw=json.dumps({"model":"gemma4:26b","done":True})
        suggestion=json.dumps(prompt_spec(),ensure_ascii=False,separators=(",",":"))
        metadata={"source_sha256":checkpoint.AUTHORIZED_SAMPLE_SHA256,"output_dimensions":[1024,768]}
        def manual_payload(text="x"):
            from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraft, result_json
            draft=ManualDraft.from_inputs(natural_zh=text,natural_en="en",image_prompt="ip",video_prompt="vp",
                                          tags="tag",negative="",edit_instruction="")
            return result_json(draft,created_at="2026-10-28T00:00:00Z")
        counter=iter(range(1,100))
        def trace(text, graph_hash="a"*64):
            number=next(counter)
            return {"prompt_id":f"p{number}","submission_sequence":number,"graph_sha256":graph_hash,
                    "class_types":["Owner"],"history_ui_text":text}
        metadata_text=["{}",manual_payload(json.dumps(metadata))]
        first=next(counter)
        image_graph=json.loads((PACK_ROOT/"LVW_V0_RuntimePatch/workflows/image_reverse_prompt_v0.api.json").read_text())
        image_graph["1"]["inputs"]["image_reference"]="authorized-image.jpg"
        image_graph["3"]=checkpoint.manual_public_graph({"natural_zh":["1",1]},"preview_json","metadata")["1"]
        a01={"prompt_id":f"p{first}","submission_sequence":first,"graph_sha256":checkpoint.value_hash(image_graph),
             "history_ui_text":[raw,suggestion],"metadata_history_ui_text":metadata_text,
             "metadata":metadata,"image_oracle":{"raw_sha256":sha256(raw.encode()).hexdigest(),
             "suggestion_sha256":sha256(suggestion.encode()).hexdigest()}}
        suggestion_value=prompt_spec()
        a03_values={"natural_zh":suggestion_value["text_zh"],"natural_en":suggestion_value["text_en"],
                    "image_prompt":suggestion_value["text_en"],"video_prompt":suggestion_value["text_en"],
                    "tags":",".join(suggestion_value["tags"]),"negative":"","edit_instruction":""}
        from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import ManualDraft, result_json
        a03_draft=ManualDraft.from_inputs(**a03_values)
        jp=result_json(a03_draft,created_at="2026-10-28T00:00:00Z")
        from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.manual import result_txt
        txt=result_txt(a03_draft)
        a03_traces=[trace(["{}",jp],checkpoint.value_hash(checkpoint.manual_public_graph(a03_values,action,"a03")))
                    for action,jp in (("preview_json",jp),("export_json",jp),("export_txt",txt))]
        a03={"traces":a03_traces,"model_calls_before":1,"model_calls_after":1,
             "four_output_sha256":{key:sha256(str(json.loads(jp)["draft"][key]).encode()).hexdigest()
                 for key in ("natural_zh","natural_en","image_prompt","video_prompt")},
             "source_raw_sha256":sha256(raw.encode()).hexdigest(),
             "json_sha256":sha256(jp.encode()).hexdigest(),"json_reread_sha256":sha256(jp.encode()).hexdigest(),
             "txt_sha256":sha256(txt.encode()).hexdigest(),"txt_reread_sha256":sha256(txt.encode()).hexdigest()}
        exact_payload=manual_payload("稿"*20000); exact_txt="## Natural Chinese\n"+"稿"*20000
        manual_values=checkpoint._node_inputs(text="稿"*20000)
        a04_actions=("preview_json","copy_json","copy_txt","export_json","export_txt")
        a04_payloads=(exact_payload,exact_payload,exact_txt,exact_payload,exact_txt)
        a04_success=[trace(["{}",payload],checkpoint.value_hash(checkpoint.manual_public_graph(manual_values,action,"a04")))
                     for action,payload in zip(a04_actions,a04_payloads)]
        failure_number=next(counter)
        failure={"prompt_id":f"p{failure_number}","submission_sequence":failure_number,
                 "graph_sha256":checkpoint.value_hash(checkpoint.manual_public_graph(manual_values,"export_json","a04-failure")),
                 "error_facts":[{"event":"execution_error","code":"DISK_FULL","subcode":"MANUAL_ATOMIC_EXPORT_FAILED"}]}
        a04={"success_traces":a04_success,"failure_trace":failure,
             "ollama_stop_fact":{"lineage_reproven":True,"stop_requested":True,"terminal_absent":True},"draft_characters":20000,
             "draft_sha256":sha256(("稿"*20000).encode()).hexdigest(),
             "failure_target_still_directory":True,"owned_temp_file_count":0,
             "exports":{"a04.json":{"sha256":sha256(exact_payload.encode()).hexdigest()},
                        "a04.txt":{"sha256":sha256(exact_txt.encode()).hexdigest()}}}
        from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge.state import transition
        token="fixture-state"; compact=lambda value:json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"))
        draft_payload=compact({"natural_zh":"kept bytes","natural_en":"","image_prompt":"","video_prompt":"",
                               "tags":[],"negative":"","edit_instruction":""})
        started=compact(transition("",action="start_run",run_token=token))
        succeeded=compact(transition(started,action="model_success",run_token=token,raw_response=raw,
                                     suggestion_payload=suggestion))
        adopted=compact(transition(succeeded,action="adopt",run_token=token,draft_payload=draft_payload))
        setup=[
            trace([started,compact(json.loads(started)["draft"])],checkpoint.value_hash(checkpoint.state_public_graph("","start_run",token))),
            trace([succeeded,compact(json.loads(succeeded)["draft"])],checkpoint.value_hash(checkpoint.state_public_graph(started,"model_success",token,raw=raw,suggestion=suggestion))),
            trace([adopted,compact(json.loads(adopted)["draft"])],checkpoint.value_hash(checkpoint.state_public_graph(succeeded,"adopt",token,draft=draft_payload))),
        ]
        baseline=json.loads(adopted); baseline_hash=checkpoint.value_hash(baseline["draft"]); negatives=[]
        specs=(("invalid_json","model_success","","{","PARSE_PARTIAL"),
               ("explicit_refusal","model_failure","MODEL_REFUSAL","",None),
               ("timeout","model_failure","MODEL_TIMEOUT","",None),
               ("oom","model_failure","GPU_OOM","",None),
               ("stale_token","model_success","","{}","ATTEMPT_STALE"))
        for name,action,error,suggestion_payload,expected_error in specs:
            next_token=token+"-next"
            running=compact(transition(adopted,action="start_run",run_token=next_token))
            start_trace=trace([running,compact(json.loads(running)["draft"])],
                checkpoint.value_hash(checkpoint.state_public_graph(adopted,"start_run",next_token)))
            callback_token="stale" if name=="stale_token" else next_token
            callback_graph=checkpoint.state_public_graph(running,action,callback_token,raw="safe raw",
                                                          suggestion=suggestion_payload,error=error)
            if expected_error:
                number=next(counter); callback_trace={"prompt_id":f"p{number}","submission_sequence":number,
                    "graph_sha256":checkpoint.value_hash(callback_graph),
                    "error_facts":[{"event":"execution_error","code":expected_error}]}
                final=json.loads(running)
            else:
                final=transition(running,action=action,run_token=callback_token,raw_response="safe raw",
                                 suggestion_payload=suggestion_payload,error_code=error)
                callback_trace=trace([compact(final),compact(final["draft"])],checkpoint.value_hash(callback_graph))
            negatives.append({"name":name,"start_trace":start_trace,"callback_trace":callback_trace,
                              "draft_sha256":baseline_hash,"draft_epoch":1,"retry_count":0})
        a05={"setup_traces":setup,"negatives":negatives,"baseline_draft_sha256":baseline_hash,
             "baseline_epoch":1,"automatic_retry_count":0}
        empty=manual_payload(""); empty_values={key:"" for key in ("natural_zh","natural_en","image_prompt","video_prompt",
                                                                      "tags","negative","edit_instruction")}
        a08_trace=trace(["{}",empty],checkpoint.value_hash(checkpoint.manual_public_graph(empty_values,"export_json","a08-empty")))
        a08={"trace":a08_trace,"manual_input_keys":["natural_zh","natural_en","image_prompt","video_prompt","tags","negative","edit_instruction"],
             "model_calls_before":1,"model_calls_after":1,"export_sha256":sha256(empty.encode()).hexdigest()}
        harness_hash=sha256(HARNESS.read_bytes()).hexdigest()
        lifecycle_hash=sha256((PACK_ROOT/checkpoint.LIFECYCLE_RELATIVE).read_bytes()).hexdigest()
        common={"product_candidate":checkpoint.PRODUCT_CANDIDATE,"harness_candidate":"a"*40,
            "harness_sha256":harness_hash,"lifecycle_relative":checkpoint.LIFECYCLE_RELATIVE,
            "lifecycle_sha256":lifecycle_hash,"run_id":checkpoint.AUTHORIZED_RUN_ID,
            "evidence_relative":checkpoint.AUTHORIZED_EVIDENCE_RELATIVE,
            "sample_sha256":checkpoint.AUTHORIZED_SAMPLE_SHA256,"model_digest":checkpoint.AUTHORIZED_MODEL_DIGEST,
            "budget":checkpoint.ONE_SHOT_BUDGET,"acceptance_hash":checkpoint.ACCEPTANCE_HASH,
            "target_bindings":checkpoint.target_bindings()}
        request_doc=dict(common,schema_version="lvw.authorization-request/1",request_id="REQ-FUTURE",
            status="PENDING_PROJECT_OWNER_APPROVAL",is_authorization=False,does_not_authorize_execution=True,
            project_id="lvw-prompt-service",stage_id=checkpoint.AUTH_STAGE_ID,workpack_id=checkpoint.AUTH_WORKPACK_ID,
            does_not_authorize_stage_pass=True)
        request_blob=json.dumps(request_doc,sort_keys=True,separators=(",",":")).encode()
        auth_doc=dict(common,schema_version="lvw.authorization/1",request_id="REQ-FUTURE",
            authorization_id="AUTH-FUTURE",status="GRANTED_ONCE",project_id="lvw-prompt-service",
            stage_id=checkpoint.AUTH_STAGE_ID,workpack_id=checkpoint.AUTH_WORKPACK_ID,
            expires_when=checkpoint.AUTH_EXPIRY,does_not_authorize_stage_pass=True,
            request_sha256=sha256(request_blob).hexdigest())
        auth_blob=json.dumps(auth_doc,sort_keys=True,separators=(",",":")).encode()
        return {"schema_version":"lvw.s1-stage-checkpoint-live/1","acceptance_hash":checkpoint.ACCEPTANCE_HASH,
            "run_id":checkpoint.AUTHORIZED_RUN_ID,"bindings":{"run_id":checkpoint.AUTHORIZED_RUN_ID,
            "evidence_relative":checkpoint.AUTHORIZED_EVIDENCE_RELATIVE,
            "target_bindings_sha256":checkpoint.value_hash(checkpoint.target_bindings())},"authorization_status":"EXPIRED_TERMINAL",
            "identity":{"product_candidate":checkpoint.PRODUCT_CANDIDATE,"product_artifact_sha256":{"x":"y"},
                        "harness_candidate":"a"*40,"harness_sha256":harness_hash,
                        "lifecycle_relative":checkpoint.LIFECYCLE_RELATIVE,"lifecycle_sha256":lifecycle_hash},
            "authority":{"authorization_commit":"b"*40,"request_relative":"reports/v0-s1/request.json",
                         "request_sha256":sha256(request_blob).hexdigest(),"authorization_relative":"reports/v0-s1/auth.json",
                         "authorization_sha256":sha256(auth_blob).hexdigest(),"authorization_id":"AUTH-FUTURE"},
            "_fixture_request":request_blob.decode(),"_fixture_authorization":auth_blob.decode(),
            "budget":checkpoint.ONE_SHOT_BUDGET,"observed":{"image_attempts":1,"model_calls":1,"comfy_starts":1,
            "ollama_starts":1,"public_submissions":24},"network_gate":{"ollama_no_cloud":True,
            "samples":[{"nonloopback_count":0} for _ in range(5)]},
            "preflight":{"gpu_count":1,"max_used_mib":1,"process_match_count":0,"target_listener_count":0},
            "model_identity":{"model":"gemma4:26b","local_exact_match_count":1,
                              "digest":checkpoint.AUTHORIZED_MODEL_DIGEST},
            "owned_listener_lineage":{"11434":{"lineage_proven":True},"8191":{"lineage_proven":True}},
            "image_runtime_guard":{"max_gpu_used_mib":2,"nonloopback_count":0},
            "runtime_guard":{"max_gpu_used_mib":2,"nonloopback_count":0},
            "case_facts":{"V0-A01":a01,"V0-A03":a03,
            "V0-A04":a04,"V0-A05":a05,"V0-A08":a08},"model_call_ledger":[{"raw_sha256":sha256(raw.encode()).hexdigest()}],
            "model_http_ledger":{"chat_200":1,"generate_200":2,"ps_200":1},
            "model_cleanup":{"cleanup_http_status":200},"target_integrity":{"pre":{"x":"y"},"post":{"x":"y"},"equal":True},
            "cleanup":{"failures":[],"final_target_listener_count":0,"owned_listener_terminal_states":[{"terminal_absent":True}],
            "owned_wrapper_terminal_states":[{"exited":True}],"run_owned_temp_removed":True},
            "post_cleanup_snapshot":{"target_listener_count":0,"target_process_match_count":0,"run_temp_absent":True}}

    def verify(self, summary):
        summary=copy.deepcopy(summary)
        request_blob=summary.pop("_fixture_request","").encode()
        authorization_blob=summary.pop("_fixture_authorization","").encode()
        def blob(_repo,_commit,relative):
            if relative.endswith("checkpoint.py"): return HARNESS.read_bytes()
            if relative==checkpoint.LIFECYCLE_RELATIVE: return (PACK_ROOT/relative).read_bytes()
            if relative.endswith("request.json"): return request_blob
            if relative.endswith("auth.json"): return authorization_blob
            raise AssertionError(relative)
        with mock.patch.object(checkpoint,"bind_candidate",return_value={"x":"y"}), \
             mock.patch.object(checkpoint,"_commit_blob",side_effect=blob):
            return checkpoint.verify_machine_facts(summary,PACK_ROOT)

    def test_machine_verifier_recomputes_facts_and_rejects_mutations(self):
        valid=self.valid_summary(); result=self.verify(valid)
        self.assertEqual(5,result["test_counts"]["pass"]); self.assertFalse(result["stage_pass_claim"])
        mutations=[
            lambda x:x["identity"].update(product_candidate="0"*40),
            lambda x:x["identity"].update(harness_sha256="0"*64),
            lambda x:x["identity"].update(lifecycle_sha256="0"*64),
            lambda x:x["identity"].update(lifecycle_relative="reports/v0-s1/wrong.py"),
            lambda x:x["authority"].update(request_sha256="0"*64),
            lambda x:x["observed"].update(model_calls=2),
            lambda x:x["bindings"].update(run_id="reused"),
            lambda x:x["preflight"].update(target_listener_count=1),
            lambda x:x["owned_listener_lineage"]["11434"].update(lineage_proven=False),
            lambda x:x["image_runtime_guard"].update(max_gpu_used_mib=23552),
            lambda x:x["network_gate"]["samples"][0].update(nonloopback_count=1),
            lambda x:x["case_facts"]["V0-A01"]["metadata"].update(source_sha256="0"*64),
            lambda x:x["case_facts"]["V0-A01"].update(graph_sha256="0"*64),
            lambda x:x["case_facts"]["V0-A03"].update(model_calls_after=2),
            lambda x:x["case_facts"]["V0-A03"].update(json_reread_sha256="0"*64),
            lambda x:x["case_facts"]["V0-A04"]["failure_trace"].update(error_facts=[]),
            lambda x:x["case_facts"]["V0-A04"]["ollama_stop_fact"].update(terminal_absent=False),
            lambda x:x["case_facts"]["V0-A05"]["negatives"][0].update(retry_count=1),
            lambda x:x["case_facts"]["V0-A05"]["negatives"][0]["callback_trace"].update(error_facts=[]),
            lambda x:x["case_facts"]["V0-A08"].update(manual_input_keys=["approval"]),
            lambda x:x["case_facts"]["V0-A08"].update(export_sha256="0"*64),
            lambda x:x["case_facts"]["V0-A08"]["trace"].update(submission_sequence=1),
            lambda x:x["model_call_ledger"].clear(),
            lambda x:x["model_http_ledger"].update(chat_200=2),
            lambda x:x["target_integrity"].update(post={"x":"drift"}),
            lambda x:x["cleanup"].update(final_target_listener_count=1),
        ]
        for mutate in mutations:
            broken=copy.deepcopy(valid); mutate(broken)
            with self.subTest(mutation=mutate),self.assertRaises(checkpoint.CheckpointError): self.verify(broken)

    def test_committed_authority_semantics_are_recomputed_not_hash_trusted(self):
        def resign(value, mutate_request=None, mutate_authorization=None):
            request=json.loads(value["_fixture_request"]); authorization=json.loads(value["_fixture_authorization"])
            if mutate_request: mutate_request(request)
            request_blob=json.dumps(request,sort_keys=True,separators=(",",":")).encode()
            authorization["request_sha256"]=sha256(request_blob).hexdigest()
            if mutate_authorization: mutate_authorization(authorization)
            authorization_blob=json.dumps(authorization,sort_keys=True,separators=(",",":")).encode()
            value["_fixture_request"]=request_blob.decode(); value["_fixture_authorization"]=authorization_blob.decode()
            value["authority"]["request_sha256"]=sha256(request_blob).hexdigest()
            value["authority"]["authorization_sha256"]=sha256(authorization_blob).hexdigest()
        cases=(
            (lambda r:r.update(status="GRANTED_ONCE"),None),
            (lambda r:r.update(is_authorization=True),None),
            (None,lambda a:a.update(status="AUTHORIZED")),
            (None,lambda a:a.update(expires_when="reusable")),
            (lambda r:r["target_bindings"].update(ollama_exe="C:/other/ollama.exe"),
             lambda a:a["target_bindings"].update(ollama_exe="C:/other/ollama.exe")),
        )
        for request_mutation,authorization_mutation in cases:
            value=self.valid_summary(); resign(value,request_mutation,authorization_mutation)
            with self.subTest(case=(request_mutation,authorization_mutation)),self.assertRaises(checkpoint.CheckpointError):
                self.verify(value)

    def test_summary_only_booleans_and_private_paths_cannot_pass(self):
        with self.assertRaises(checkpoint.CheckpointError): self.verify({"proof":True,"oracle":True})
        value=self.valid_summary(); value["private"]="/"+"mnt/c/private/sample.jpg"
        with self.assertRaises(checkpoint.CheckpointError) as raised: self.verify(value)
        self.assertEqual("CASE_PRIVACY_VIOLATION",raised.exception.code)


if __name__=="__main__": unittest.main()
