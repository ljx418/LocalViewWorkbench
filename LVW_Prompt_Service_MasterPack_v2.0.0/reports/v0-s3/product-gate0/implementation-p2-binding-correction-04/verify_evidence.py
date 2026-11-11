"""Verify raw trees before lossless archiving; extraction restores identical paths."""
import base64, hashlib, json, tarfile, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
temporary=tempfile.TemporaryDirectory(prefix='lvw-p2b-c04-verify-')
EVIDENCE=Path(temporary.name)
for archive in ROOT.glob('*.tar.gz'):
    with tarfile.open(archive) as tar:
        for item in tar.getmembers():
            assert not item.issym() and not item.islnk()
            assert (EVIDENCE/item.name).resolve().is_relative_to(EVIDENCE.resolve())
        tar.extractall(EVIDENCE,filter='data')
results=[]
for terminal in sorted(EVIDENCE.glob('*raw/public-*/cross-os-lifecycle.json')):
    t=json.loads(terminal.read_bytes());base=terminal.parent
    commands=[];observations=[];actual=0
    for r in t['artifact_refs']:
        p=base/r['path'];data=p.read_bytes()
        assert p.resolve().is_relative_to(base.resolve()) and not p.is_symlink()
        assert len(data)==r['bytes']<=1048576 and hashlib.sha256(data).hexdigest()==r['sha256']
        actual+=len(data)
        if r['kind']=='command':
            c=json.loads(data)
            if 'stdout_base64' in c:
                streams=[base64.b64decode(c[k],validate=True) for k in ('stdout_base64','stderr_base64')]
                assert list(map(len,streams))==c['stream_bytes']
                assert [hashlib.sha256(s).hexdigest() for s in streams]==c['stream_sha256']
                assert all(len(s)<=262144 for s in streams)
                commands.append(dict(bytes=c['stream_bytes'],complete=c.get('raw_complete','EARLIER_DIRECTED_VERSION'),error=c.get('error')))
        if r['kind']=='observer':observations.append(json.loads(data)['sample_count'])
    claim=json.loads((base/'consumed.json').read_bytes())
    assert claim['status']=='EXPIRED' and claim['terminal_sha256']==hashlib.sha256(terminal.read_bytes()).hexdigest()
    assert terminal.stat().st_size<=16384 and actual<=t['counters']['output_bytes']<=16777216
    results.append(dict(terminal=str(terminal.relative_to(EVIDENCE)),status=t['status'],terminal_bytes=terminal.stat().st_size,
        artifact_bytes=actual,charged_output=t['counters']['output_bytes'],refs=len(t['artifact_refs']),
        observer_samples=observations,commands=commands,synthetic_debits=t['synthetic_debits']))
(ROOT/'verification.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps({'verified_terminals':len(results),'max_terminal_bytes':max(r['terminal_bytes'] for r in results)}))

temporary.cleanup()
assert not EVIDENCE.exists()
