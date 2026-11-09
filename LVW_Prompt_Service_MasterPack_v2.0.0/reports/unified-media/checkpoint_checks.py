"""Checkpoint oracles; observations from own process/files and public requests only."""
from pathlib import Path
import hashlib
import json
import stat
import time


def residue(root, api_pid):
    root = Path(root)
    files = []
    for name in ('media', 'video-temp'):
        for path in sorted((root/name).rglob('*')):
            files.append({'path':str(path.relative_to(root)), 'kind':'file' if path.is_file() else 'directory',
                          'bytes':path.stat().st_size if path.is_file() else None})
    spools = []
    for fd in (Path('/proc')/str(api_pid)/'fd').iterdir():
        try:
            target = str(fd.readlink())
            info = fd.stat()
            if stat.S_ISREG(info.st_mode) and ('(deleted)' in target or target.startswith(str(root)+'/')):
                # Persistent service audit streams are expected, not multipart spools.
                if target == str(root/'provider.jsonl'): continue
                spools.append({'fd':fd.name,'target':target,'bytes':info.st_size})
        except FileNotFoundError:
            continue
    return {'media_and_temp':files, 'owned_open_files':sorted(spools,key=lambda x:x['fd'])}


def negative_uploads(root, api_pid, cases, api_call, out, repo_root):
    root, out = Path(root), Path(out)
    rows = [dict(case, status='NOT_RUN') for case in cases]
    report = {'kind':'REAL_PUBLIC_NEGATIVE_MATRIX','cases':rows,'decision':'NO_GO'}
    def save(): (out/'negative-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    save()
    for row in rows:
        before = residue(root, api_pid)
        path = Path(row['path'])
        if not path.is_absolute():
            # Caller supplies repo root once; never interpret fixture names relative to cwd.
            path = Path(repo_root)/path
        try:
            with path.open('rb') as stream:
                response = api_call('POST','/api/v1/media',headers={'Idempotency-Key':row['id']},
                    files={'file':(path.name,stream,'video/mp4')},timeout=60)
            row.update(actual_status=response.status_code,before=before)
            raw_path=out/(row['id']+'-response.raw')
            raw_path.write_bytes(response.content)
            row['raw_response_sha256']=hashlib.sha256(response.content).hexdigest()
            body = response.json()
            (out/(row['id']+'-response.json')).write_text(json.dumps(body,ensure_ascii=False,indent=2)+'\n')
            row.update(actual_status=response.status_code,actual_error=body.get('error',{}).get('code'),before=before)
            assert response.status_code == row['expected_status'], 'wrong public HTTP status'
            assert row['actual_error'] == row['expected_error'], 'wrong stable error'
            deadline=time.monotonic()+5
            after=residue(root,api_pid)
            while after!=before and time.monotonic()<deadline:
                time.sleep(.05);after=residue(root,api_pid)
            row['after']=after
            assert after==before, 'media/temp/spooled file residue'
            ledger=root/'provider.jsonl'
            events=[json.loads(line) for line in ledger.read_text().splitlines()] if ledger.exists() else []
            assert not any(e['event']=='provider_call_started' for e in events), 'model started before negative phase ended'
            assert not body.get('data'), 'rejected file published a media reference'
            row.update(status='PASS',model_calls=0,published_media_ref=False,cleanup_proven=True)
        except BaseException as error:
            row.update(status='FAIL',error=type(error).__name__+': '+str(error))
            save();raise
        save()
    report['decision']='ALL_REAL_NEGATIVES_AND_CLEANUP_PASS';save()
    return report


def verify_configs(request_rows, runs):
    from lvw.backend.app.models import AnalyzeRequest
    verified=[]
    for run in runs:
        matching=[row for row in request_rows if row['job_id']==run['job_id']]
        assert len(matching)==1, 'missing or duplicate original public request'
        row=matching[0]
        request=AnalyzeRequest(**row['request'])
        video=bool(run['frames'])
        configuration={**request.model_dump(),'video_num_ctx':4096 if video else None}
        digest=hashlib.sha256(json.dumps(configuration,sort_keys=True).encode()).hexdigest()
        assert digest==run['config_sha256'], 'public request/result configuration mismatch'
        verified.append({'job_id':run['job_id'],'model_run_id':run['id'],'public_request':row['request'],
                         'normalized_configuration':configuration,'computed_sha256':digest,'status':'PASS'})
    return {'kind':'PUBLIC_ANALYSIS_REQUEST_CONFIG_RECOMPUTATION','cases':verified}
