"""Synthetic response fixtures test checkpoint rejection oracles, never real acceptance."""
import hashlib
import importlib
import json
from types import SimpleNamespace
import pytest
from app.models import AnalyzeRequest

checks=importlib.import_module('reports.unified-media.checkpoint_checks')

def run_request():
    body={'media_ref_id':'test-media','mode':'realistic','config_profile':'local-default'}
    configuration={**AnalyzeRequest(**body).model_dump(),'video_num_ctx':4096}
    run={'id':'run-test','job_id':'job-test','frames':[{}],
         'config_sha256':hashlib.sha256(json.dumps(configuration,sort_keys=True).encode()).hexdigest()}
    return [{'job_id':'job-test','request':body}],run


def test_request_digest_recomputed_from_original_public_body():
    rows,run=run_request();result=checks.verify_configs(rows,[run]);assert result['cases'][0]['status']=='PASS'

@pytest.mark.parametrize('mutation',['missing','duplicate','old_digest','changed_body','unknown_field'])
def test_config_oracle_rejects_mismatched_evidence(mutation):
    rows,run=run_request()
    if mutation=='missing':rows=[]
    if mutation=='duplicate':rows*=2
    if mutation=='old_digest':run['config_sha256']='0'*64
    if mutation=='changed_body':rows[0]['request']['custom_guidance']='different'
    if mutation=='unknown_field':rows[0]['request']['unknown']='different'
    with pytest.raises((AssertionError,ValueError)):checks.verify_configs(rows,[run])

@pytest.mark.parametrize('fault',['wrong_code','residue','model_send','published_ref','http_200','none'])
def test_negative_oracle_requires_code_cleanup_no_model_no_publish(tmp_path,monkeypatch,fault):
    source=tmp_path/'fixture.mp4';source.write_bytes(b'bad controlled test input')
    output=tmp_path/'evidence';output.mkdir();owned=tmp_path/'owned';owned.mkdir()
    calls=0
    def residue(root,pid):
        nonlocal calls
        calls+=1
        return {'media_and_temp':['leftover'] if fault=='residue' and calls>1 else [],'owned_open_files':[]}
    monkeypatch.setattr(checks,'residue',residue)
    # No real waiting needed for this deterministic fixture; production uses a 5s bounded wait.
    monkeypatch.setattr(checks.time,'monotonic',lambda:0 if calls==1 else 10)
    if fault=='model_send':(owned/'provider.jsonl').write_text(json.dumps({'event':'provider_call_started'})+'\n')
    def api(*args,**kwargs):
        body={'error':{'code':'WRONG' if fault=='wrong_code' else 'MEDIA_INVALID'}}
        if fault=='published_ref':body['data']={'id':'unexpected'}
        return SimpleNamespace(status_code=200 if fault=='http_200' else 422,json=lambda:body,content=json.dumps(body).encode())
    cases=[{'id':'NV-TEST','path':str(source),'expected_status':422,'expected_error':'MEDIA_INVALID'}]
    if fault=='none':
        assert checks.negative_uploads(owned,123,cases,api,output,tmp_path)['cases'][0]['status']=='PASS'
    else:
        with pytest.raises(AssertionError):checks.negative_uploads(owned,123,cases,api,output,tmp_path)
        assert json.loads((output/'negative-results.json').read_text())['cases'][0]['status']=='FAIL'


def test_non_json_negative_retains_original_response_bytes(tmp_path,monkeypatch):
    source=tmp_path/'bad.mp4';source.write_bytes(b'bad')
    output=tmp_path/'evidence';output.mkdir()
    monkeypatch.setattr(checks,'residue',lambda *args:{'media_and_temp':[],'owned_open_files':[]})
    def invalid_json():raise ValueError('non-JSON diagnostic')
    raw=b'<html>controlled-test-diagnostic</html>'
    response=SimpleNamespace(status_code=503,content=raw,json=invalid_json)
    cases=[{'id':'NV-RAW','path':str(source),'expected_status':422,'expected_error':'MEDIA_INVALID'}]
    with pytest.raises(ValueError):checks.negative_uploads(tmp_path,123,cases,lambda *a,**kw:response,output,tmp_path)
    assert (output/'NV-RAW-response.raw').read_bytes()==raw
    row=json.loads((output/'negative-results.json').read_text())['cases'][0]
    assert row['status']=='FAIL' and row['raw_response_sha256']==hashlib.sha256(raw).hexdigest()
    assert row['actual_status']==503
