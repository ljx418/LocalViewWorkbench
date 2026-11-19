"""Read-only review audit. Argument is the extracted candidate pack directory."""
import ast
import hashlib
import json
import math
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

repo = Path('/mnt/c/workspace/videoworkline/localviewworkbench')
pack = Path(sys.argv[1]).resolve()
work = repo / pack.name
out = Path(__file__).resolve().parent
src = 'a066fe19c1700255cc0268aded3ee5948e90fcf2'
ev = 'b2fb6472d4d9e82d5d381f385216fb6f0daaf243'
corr = Path('reports/resource-cleanup/correction-03')
def git(*args):
    return subprocess.check_output(['git','-C',str(repo),*map(str,args)])
def obj(rev, path):
    return git('show', f'{rev}:{pack.name}/{path}')
def sha(b):
    return hashlib.sha256(b).hexdigest()
def read(p):
    return json.loads(p.read_bytes())
def assert_same(*values):
    assert all(v == values[0] for v in values), values
    return values[0]

report = {}
ack = read(pack/corr/'root-ack.json')
report['ack_sha256'] = {k: assert_same(v,sha((pack/k).read_bytes()),sha(obj(src,k)),
                                       sha(obj('16d6ed99',k))) for k,v in ack['source_hashes'].items()}
report['controller_pyproject_sha256'] = {k:assert_same(sha((pack/k).read_bytes()),sha(obj(src,k)))
                                       for k in [ack['controller'],'lvw/pyproject.toml']}
report['evidence_object_sha256'] = {}
for p in (work/corr).rglob('*'):
    if p.is_file() and '__pycache__' not in p.parts:
        k = p.relative_to(work)
        report['evidence_object_sha256'][str(k)] = assert_same(sha(p.read_bytes()),sha(obj(ev,k)))
counts = {}
for name in ['test_resource_cleanup','test_cleanup_validation_harness']:
    nodes = ast.parse((pack/'lvw/tests'/f'{name}.py').read_bytes()).body
    counts[name] = sum(math.prod(len(d.args[1].elts) for d in n.decorator_list
                       if isinstance(d,ast.Call) and getattr(d.func,'attr',None)=='parametrize')
                       for n in nodes if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_'))
assert sum(counts.values()) == 88
report['static_case_counts'] = counts
def check_control(req, folder):
    r = read(req)
    assert_same(r, read(folder/'intent.json'))
    receipt,child = read(folder/'receipt.json'),read(folder/'child.json')
    for k in ('argv','environment','cwd'):
        assert_same(r[k], receipt[k])
    for k,v in child.items():
        assert_same(v,receipt[k])
    assert_same(receipt['deadline_seconds'],r['wall_seconds'])
    assert receipt['reaped'] and receipt['returncode']==0 and receipt['status']=='EXITED_ZERO'
    assert not any(receipt[k] for k in ['errors','signals','cancel_signals','timed_out'])
    stdout=(folder/'stdout.log').read_text()
    return dict(request_sha256=sha(req.read_bytes()),**child,elapsed_seconds=receipt['elapsed_seconds'],
                deadline=r['wall_seconds'],exit=0,reaped=True,stdout=stdout,
                stderr=(folder/'stderr.log').read_text(),
                pytest_successes=sum(len(m) for m in re.findall(r'^(\.+) +\[',stdout,re.M)))
report['controller_runs']={}
for key,parent,num in [('root88',corr,1),('root242',corr,2),
                       ('frontend12',corr.parent/'correction-01',3),('build',corr.parent/'correction-01',4)]:
    base=pack/parent/'cpu'
    report['controller_runs'][key]=check_control(base/f'request-0{num}.json',base/f'check-0{num}')
report['controller_runs']['independent88']=check_control(out/'request.json',out/'cpu')
for k,count in [('root88',88),('root242',242),('independent88',88)]:
    assert_same(report['controller_runs'][k]['pytest_successes'],count)
assert '# pass 12' in report['controller_runs']['frontend12']['stdout']
assert 'tsc -b && vite build' in report['controller_runs']['build']['stdout']
report['frontend_tree_oid']=assert_same(*(git('rev-parse',f'{r}:{pack.name}/lvw/frontend').decode().strip()
                                         for r in ['94f92bed','679803cf',src]))
report['live']={}
for run in sorted((work/corr/'runs').iterdir()):
    c=read(run/'authorization.json')
    a=read(run/'receipt.json')
    native=read(run/'native-final.json')
    data=read(run/'cleanup-response.json')['data']
    req=read(run/'request.json')
    t=read(run/'tool-bindings.json')
    ctl=check_control(run/'request.json',run/'controller')
    assert_same(c['candidate_sha'],a['candidate_sha'],src)
    for k in ['LVW_DATA_ROOT','TMPDIR','LVW_AUTHORIZATION_CHILD']:
        assert_same(req['environment'][k],{'LVW_DATA_ROOT':c['data_root'],'TMPDIR':c['private_root'],
                                            'LVW_AUTHORIZATION_CHILD':str(run/'authorization.json')}[k])
    assert_same((run/'run.claim').read_text(),c['run_id'])
    assert_same(c['program_sha256'],sha(obj(src,c['program'])),sha((work/c['program']).read_bytes()))
    source={f['path']:assert_same(f['sha256'],sha(obj(src,f['path'])),sha((work/f['path']).read_bytes()))
            for f in c['frozen_files']}
    assert_same(c['harness_sha256'],source[str(corr/'live_harness_v4.py')])
    envpath=req['environment']['PATH']
    selected={'python':req['argv'][0],'chromium':c['chromium_executable'],'nvidia-smi':shutil.which('nvidia-smi',path=envpath)}
    if not c['fixture']:
        selected.update(wslpath=shutil.which('wslpath',path=envpath),
                        powershell=shutil.which('powershell.exe',path=envpath) or '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',
                        ollama='/mnt/c/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe')
    assert_same(set(t),set(selected))
    for k,v in t.items():
        assert_same(Path(v['path']).resolve(),Path(selected[k]).resolve())
        assert_same(v['sha256'],sha(Path(v['path']).read_bytes()))
    ledger=Path(c['budget_ledger'])
    with sqlite3.connect(ledger.as_uri()+'?mode=ro',uri=True) as db:
        db.row_factory=sqlite3.Row
        row=dict(db.execute('SELECT * FROM children WHERE run=?',(c['run_id'],)).fetchone())
    assert_same(row['calls'],row['active'],a['model_actions'],a['authorization_terminal']['actual_model_actions'],0)
    for k,file in [('child','authorization.json'),('bindings','tool-bindings.json')]:
        assert_same(row[k+'_path'],str(run/file))
        assert_same(row[k+'_hash'],sha((run/file).read_bytes()))
    assert a['known_terminal'] and not a['cleanup_errors']
    assert len(a['checks'])==(9 if c['fixture'] else 8) and all(x['passed'] for x in a['checks'])
    assert data['verified'] and data['status']=='released'
    assert native['matched'] and native['expected']['state']=='listening' and native['proof']['state']=='exited'
    for k in ['nonce','pid','birth_ticks']: assert_same(native['expected'][k],native['proof'][k])
    record=dict(controller=ctl,source_sha256=source,tools=t,program_sha256=c['program_sha256'],
                db_row=row,receipt=a,response=data,native=native)
    if not c['fixture']:
        assert_same(data['inventory_observation'],{'state':'complete','model_count':0})
        assert_same(data['listener_observation'],{'state':'absent','reason':'CONNECTION_REFUSED'})
        assert_same(data['actions'],['stop_original_lvw_model_service'])
        assert_same(data['after']['values']['gpu_free_mib'],20694)
        record['initial_runtime']=read(run/'initial-runtime.json')
        assert_same(record['initial_runtime']['ollama']['pid'],native['proof']['pid'])
        stem=Path(c['data_root'])/'runtime'/native['proof']['nonce']
        assert_same(read(stem.with_suffix('.owner.json')),native['proof'])
        assert_same(stem.with_suffix('.stop').read_text(),native['proof']['nonce'])
        record['access_log']=stem.with_suffix('.stdout.log').read_text()
    report['live'][run.name]=record
print(json.dumps(report,indent=2))
