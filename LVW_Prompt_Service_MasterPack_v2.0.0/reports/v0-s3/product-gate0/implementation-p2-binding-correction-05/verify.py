"""Read only final combined synthetic artifacts; never touches recorded runtime paths."""
import base64, hashlib, json
from pathlib import Path
OUT=Path(__file__).resolve().parent
raw=OUT/'combined-raw'
rows=[]
for observation in sorted(raw.glob('finalization-*.jsonl')):
    value=json.loads(observation.read_text())
    name=observation.stem.removeprefix('finalization-')
    root=raw/('public-'+name)
    terminal=root/'cross-os-lifecycle.json'
    refs=0;streams=[];detail_bytes=0
    if terminal.exists():
        data=terminal.read_bytes();index=json.loads(data)
        assert index==value['terminal']
        assert hashlib.sha256(data).hexdigest()==value['terminal_sha256']
        assert not (index['status']=='READY_FOR_REVIEW' and value['returned_status']=='BLOCKED')
        if index['status']=='READY_FOR_REVIEW':
            assert value['finalization_proven'] and index['finalization_proven']
            for claim in (value['claim'],value['consumed']):
                assert claim['status']=='EXPIRED' and claim['result']=='TERMINAL_REFERENCE_NOT_DECISION'
                assert claim['terminal_sha256']==hashlib.sha256(data).hexdigest()
                assert all(claim[k]==index[k] for k in ('candidate','child_id','child_sha256'))
        for ref in index['artifact_refs']:
            path=root/ref['path']
            assert not path.is_symlink() and path.parent==root/'details'
            content=path.read_bytes()
            assert len(content)==ref['bytes'] and hashlib.sha256(content).hexdigest()==ref['sha256']
            detail_bytes+=len(content);refs+=1
        assert detail_bytes==index['detail_actual_bytes']<=index['detail_reserved_bytes']
        assert len(data)<=16384 and index['counters']['output_bytes']<=16777216
    else:
        assert name in ('all-permanent','early-permanent')
        assert value['returned_status']=='BLOCKED' and not value['terminal_index_persisted']
    for path in sorted((root/'details').glob('*-command.raw')):
        command=json.loads(path.read_bytes())
        if 'stream_bytes' not in command:continue
        sizes=[]
        for n,stream in enumerate(('stdout','stderr')):
            content=base64.b64decode(command[stream+'_base64'],validate=True)
            assert len(content)==command['stream_bytes'][n]
            assert hashlib.sha256(content).hexdigest()==command['stream_sha256'][n]
            sizes.append(len(content))
        streams.append(dict(bytes=sizes,complete=command['raw_complete']))
    if name=='None':
        assert len(streams)==3 and all(s==dict(bytes=[262144,256000],complete=True) for s in streams)
    tree_bytes=sum(p.stat().st_size for p in root.rglob('*') if p.is_file())
    factory_bytes=sum(sum(f['bytes'] for f in json.loads(p.read_text())['files']) for p in raw.glob('factory-'+name+'-*.jsonl'))
    assert tree_bytes+factory_bytes<=16777216
    rows.append(dict(tree_bytes=tree_bytes,factory_bytes=factory_bytes,case=name,status=value['returned_status'],disk_status=value['terminal']['status'] if value['terminal'] else None,
        claim_status=value['claim']['status'],local_status=value['consumed']['status'] if value['consumed'] else None,
        index_persisted=value['terminal_index_persisted'],finalization_proven=value['finalization_proven'],
        phases=value['phases'],refs=refs,detail_bytes=detail_bytes,streams=streams))
assert len(rows)==19
old=json.loads((OUT.parent/'independent-p2-binding-correction-04/combined-counts.json').read_text())
new=json.loads((OUT/'combined-counts.json').read_text())
oldids={x['nodeid'] for x in old['results']};newids={x['nodeid'] for x in new['results']}
assert oldids<=newids and len(oldids)==227 and len(newids)==237
assert all(x['outcome']=='passed' for x in new['results'])
cleanup=[json.loads(p.read_text()) for p in raw.glob('public-cleanup-*.jsonl')]
assert len(cleanup)==19 and all(x['absent'] for x in cleanup)
result=dict(cases=rows,previous_nodeids_retained=227,final_passed=237,new_matrix_cases=10,
            cleanup_records=cleanup,verification='synthetic offline only; no runtime paths accessed')
(OUT/'verification.json').write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n')
print(json.dumps(dict(cases=len(rows),old_retained=227,passed=237,cleanup_records=len(cleanup))))
