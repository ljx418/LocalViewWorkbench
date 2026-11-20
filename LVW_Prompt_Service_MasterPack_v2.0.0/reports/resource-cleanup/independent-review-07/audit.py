"""Read only named Git, evidence, bound-tool and ledger inputs. Run with python3 -B."""
import ast, hashlib, json, re, sqlite3, subprocess
from pathlib import Path

R=Path(__file__).resolve().parent
M=Path('/mnt/c/workspace/videoworkline/localviewworkbench')
P='LVW_Prompt_Service_MasterPack_v2.0.0'
C='1f55a4687a392c002538e135863ad71ec87b3376'
E='94f695472b496195f19b9a0eec5d2b1b948cee50'
L='reports/resource-cleanup/correction-05'
B=M/P/L
O=B/'runs/real01'
def j(p): return json.loads(p.read_bytes())
def sha(b): return hashlib.sha256(b).hexdigest()
def h(p): return sha(p.read_bytes())
def git(*args): return subprocess.check_output(['git','-C',M,*args])
def blob(path,rev=C): return git('show',f'{rev}:{P}/{path}')
ack=j(B/'root-ack-live.json')
cpuack=j(B/'root-ack-recheck.json')
ch=j(O/'authorization.json')
rec=j(O/'receipt.json')
assert ack['candidate_sha']==ch['candidate_sha']==rec['candidate_sha']==C
assert ch['frozen_files']==ack['source_hashes'] and ch['samples']==ack['samples']
D=Path(j(R/'request.json')['cwd'])
K=j(B/'independent-review-plan.json')['controller']
hashes={}
for path,expect in (list(cpuack['source_hashes'].items())+[(v['path'],v['sha256']) for v in ch['frozen_files']+ch['samples']]+[(K,ack['controller_sha256']),(ch['program'],ch['program_sha256'])]):
    hashes[path]={'sealed':expect,'candidate':sha(blob(path)),'evidence_commit':sha(blob(path,E)),'main':h(M/P/path)}
    if (D/path).is_file(): hashes[path]['extracted']=h(D/path)
    assert set(hashes[path].values())=={expect},path
def childcheck(out,req,rc):
    t=j(out/'receipt.json')
    assert j(out/'intent.json')==req
    assert all(t[k]==req[k] for k in ('argv','cwd','environment'))
    assert all(t[k]==v for k,v in j(out/'child.json').items())
    assert t['returncode']==rc and t['reaped'] and not t['timed_out']
    assert t['elapsed_seconds']<t['deadline_seconds']==req['wall_seconds']
    return [rc,t['pid'],t['birth'],t['elapsed_seconds'],t['deadline_seconds']]
def count(out):return sum(len(m) for m in re.findall(r'^(\.+)\s+\[', (out/'stdout.log').read_text(),re.M))
controllers={}
for i,req in enumerate(j(B/'root-ack-cpu.json')['commands'] + cpuack['commands'],1):
    o=B/f'cpu/check-{i:02}'
    assert j(B/f'cpu/request-{i:02}.json')==req
    controllers[o.name]=childcheck(o,req,0)+[count(o)]
assert [controllers[k][-1] for k in controllers]==[141,295,141]
controllers['independent']=childcheck(R/'cpu',j(R/'request.json'),0)+[count(R/'cpu')]
assert controllers['independent'][-1]==141
F=M/P/'reports/resource-cleanup/correction-04/cpu'
for i in (3,4): controllers[f'frontend{i}']=childcheck(F/f'check-{i:02}',j(F/f'request-{i:02}.json'),0)
assert '# pass 12' in (F/'check-03/stdout.log').read_text()
ft=[git('rev-parse',f'{rev}:{P}/lvw/frontend').decode().strip() for rev in (C,'cfca7fe7',E)]
assert len(set(ft))==1
assert ack['request']==j(O/'request.json') and ack['budget']==ch['budget']
assert ch['harness_sha256']==hashes[L+'/live_harness_v7.py']['candidate']
assert (O/'run.claim').read_text()==ch['run_id']
rows={}; tools={}
with sqlite3.connect(Path(ch['budget_ledger']).as_uri()+'?mode=ro',uri=True) as db:
    db.row_factory=sqlite3.Row
    for name in ('real01','windows-acl-probe01'):
        run=B/'runs'/name
        a=j(run/'authorization.json')
        row=dict(db.execute('select * from children where run=?',(a['run_id'],)).fetchone())
        rows[name]=row
        assert h(run/'authorization.json')==row['child_hash'] and h(run/'tool-bindings.json')==row['bindings_hash']
        controllers[name]=childcheck(run/'controller',j(run/'request.json'),0)
        for k,v in j(run/'tool-bindings.json').items():
            assert h(Path(v['path']))==v['sha256']
            tools[v['path']]=v['sha256']
assert j(O/'tool-bindings.json')==ack['tool_bindings']
assert [(r['active'],r['calls']) for r in rows.values()]==[(0,2),(0,0)]
assert all(rows['real01'][k]==v for k,v in j(O/'ledger-reconciliation.json').items() if k in rows['real01'])
assert rows['real01']['elapsed']==rec['authorization_terminal']['elapsed_seconds'] and ch['expires_at']-ch['issued_at']==350
scripts={}
probe_dir=B/'runs/windows-acl-probe01'
pa=j(probe_dir/'authorization.json')
ps=probe_dir/'probe.ps1'
assert pa['script_sha256']==h(ps) and pa['request']==j(probe_dir/'request.json')
assert blob('lvw/backend/app/native_private.py',pa['candidate_sha'])==blob('lvw/backend/app/native_private.py')
tree=ast.parse(blob('lvw/backend/app/native_private.py'))
ns={}
exec(compile(ast.Module(body=[tree.body[5]],type_ignores=[]),'<private-preamble>','exec'),ns)
assert ns['windows_acl_preamble'](pa['private_root']) in ps.read_text()
probe=j(probe_dir/'controller/stdout.log')
assert all(probe[k] is True for k in ['protected','owner_matches','file_owner_matches']) and probe['rule_count']==2
scripts['acl']=h(ps)
ids=[]
starts=[j(O/f'generation-{n}-start.json') for n in ('a','b')]
history=j(O/'native-final.json')['generations']
assert len(history)==len(starts)==2
for start,end in zip(starts,history,strict=True):
    early=start['identity']
    assert early['state']=='listening' and early['job_owned'] and early['listener_owned'] and not early['job_empty']
    assert early==end['expected']
    assert end['proof']==dict(early,state='exited',listener_owned=False,job_empty=True)
    assert end['wrapper_returncode']==0 and end['matched']
    ids.append([early['nonce'],early['pid'],early['birth_ticks'],start['wrapper_pid']])
assert all(len(set(seq))==2 for seq in zip(*ids))
assert ids[1][1]==j(O/'restart-response.json')['data']['ollama']['pid']
tags=j(O/'model-tags.json')['models']; resident,=j(O/'loaded-inventory.json')
tag,=[x for x in tags if x['name']==ch['model_tag']]
assert tag['digest']==ch['model_digest']==resident['digest'] and resident['size_vram']>0
assert j(O/'preload-response.json')['done_reason']=='load'
provider=[json.loads(s) for s in (O/'provider.jsonl').read_text().splitlines()]
run=j(O/'model-run.json')['data']; job=j(O/'job-terminal.json')['data']; exp=j(O/'export.json')
call,=[v for v in provider if v['event']=='provider_call_started']
resp,=[v for v in provider if v['event']=='provider_response_received']
end,=[v for v in provider if v['event']=='provider_call_completed']

assert call['call_id']==resp['call_id']==end['call_id'] and end['outcome']=='success'
assert resp['wire_response_sha256']==sha(run['raw_response'].encode())
assert call['payload_image_sha256']==[run['input_sha256']]==[ch['samples'][0]['sha256']]==[exp['source']['input_sha256']]
assert job['result_ref']==run['id']==exp['source']['model_run_id'] and job['id']==run['job_id']==exp['source']['job_id']==call['lease_job_id']
assert job['attempt_id']==run['attempt_id'] and job['resource_state']=='released' and job['status']==run['status']=='succeeded'
assert json.loads(json.loads(run['raw_response'])['message']['content'])['prompt_zh']==run['parsed_spec']['text_zh']==exp['outputs']['natural_zh']
cl=j(O/'cleanup-response.json')['data']
assert cl['status']=='released' and cl['verified'] and cl['inventory_observation']['model_count']==1
assert rec['final_listener']==cl['listener_observation']=={'state':'absent','reason':'CONNECTION_REFUSED'}
mon=j(O/'resource-samples.json')
def extrema(samples): return [len(samples),max(x['gpu_used_mib'] for x in samples),min(x['available_ram_mib'] for x in samples)]
series={'outer':extrema(mon),'provider':extrema([x for x in provider if 'gpu_used_mib' in x]),'final':extrema(rec['final_resource_samples'])}
assert all(mx<23552 and mn>=2048 for n,mx,mn in series.values())
checks=[x['name'] for x in rec['checks'] if x['passed'] is True]
code=ast.parse(blob(L+'/live_harness_v7.py'))
check_sites=sum(isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='check' for n in ast.walk(code))
assert len(rec['checks'])==len(set(checks))==check_sites+2==22
outfiles={}
for base in [B/'runs',B/'cpu',F/'check-03',F/'check-04']:
    for path in sorted(x for x in base.rglob('*') if x.is_file()):
        rel=path.relative_to(M/P).as_posix()
        assert h(path)==sha(blob(rel,E)),rel
        outfiles[rel]=h(path)
prepared=j(O/'receipt.prepared.json')
assert prepared['status']=='EVIDENCE_COMPLETE_PENDING_SETTLEMENT' and prepared['operation_status']==rec['status']=='PASS_REAL_LOADED_RESTART_IMAGE'
assert all(prepared[k]==v for k,v in rec.items() if k not in ('status','authorization_terminal'))
assert prepared['settlement_expected']=={'actual_model_actions':2,'run_id':ch['run_id']}
assert j(O/'controller/stdout.log')==dict(status=rec['status'],checks=22,known_terminal=True,model_actions=2)
audit=j(O/'private-root-audit.json')['generation_roots']
for item in audit:
    root=Path(item['path']); nonce=item['nonce']
    end,=[v['proof'] for v in history if v['proof']['nonce']==nonce]
    assert item['mode']=='0o700' and item['uid']==1000 and nonce in root.name
    assert sha(json.dumps(end,separators=(',',':')).encode())==item['owner_sha256']
assert len(set(x['nonce'] for x in audit))==2
assert rec['known_terminal'] and rec['cleanup_errors']==[] and all(rec['cleanup'][k] for k in ['context_closed','browser_closed','driver_closed','api_closed','native_exited','resource_bound_confirmed'])
assert rows['real01']['seconds']==ack['max_seconds']==360
assert rows['windows-acl-probe01']['elapsed']==j(probe_dir/'terminal.json')['elapsed_seconds']
assert j(probe_dir/'terminal.json')['actual_model_actions']==0
assert (O/'restart-response.json').is_file() and j(O/'restart-response.json')['data']['ollama']['managed']
assert rec['cleanup']['native_generations']==2 and call['frame_count']==len(call['payload_image_sha256'])==1
assert j(B/'independent-review-plan.json')['allowed_command']==j(R/'request.json')['argv']
for name in ['decision.md','profile.md','implementation-receipt.json','result.md','root-ack-cpu.json','root-ack-live.json','root-ack-recheck.json','independent-review-plan.json']:
    path=B/name
    rel=str(path.relative_to(M/P))
    assert h(path)==sha(blob(rel,E)); outfiles[rel]=h(path)

expected=set()
for path in git('ls-tree','-r','--name-only',C+':'+P).decode().splitlines():
    q=Path(path)
    if q.parent.as_posix() in ('lvw/backend/app','LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge') and q.suffix=='.py' or q.parent.as_posix()=='templates' and q.suffix=='.txt' or path.startswith('lvw/frontend/dist/'):
        expected.add(path)
assert expected | {K,'tools/local_program_authority.py',L+'/profile.md',L+'/live_harness_v7.py',L+'/seal_real01.py'}=={x['path'] for x in ch['frozen_files']}
old=M/P/'reports/resource-cleanup/loaded-validation-01/runs'
series['historicalReal02outer']=extrema(j(old/'real02/resource-samples.json'))
series['historicalReal02provider']=extrema([v for line in (old/'real02/provider.jsonl').read_text().splitlines() if 'gpu_used_mib' in (v:=json.loads(line))])
with sqlite3.connect(Path(ch['budget_ledger']).as_uri()+'?mode=ro',uri=True) as db:
    for n in ['real01','orphan-probe01']:
        oldrun=j(old/n/'authorization.json')['run_id']
        recorded=db.execute('select active,calls from children where run=?',(oldrun,)).fetchone()
        assert recorded==(2,int(n=='real01'))
        rows[oldrun]=recorded
assert all(s['gpu_used_mib']<=j(O/'preflight.json')['gpu_used_mib']+1024 for s in rec['final_resource_samples'])
early=j(B/'root-ack-cpu.json')['source_hashes']
assert all(sha(blob(path,'26e556c8'))==value for path,value in early.items())
print(json.dumps(dict(candidate=C,evidence_commit=E,hash_comparisons=hashes,frozen_count=len(ch['frozen_files']),tool_bytes=tools,script_hashes=scripts,front_tree=ft[0],controllers=controllers,ledger=rows,native_starts=ids,source_image=run['input_sha256'],response=resp['wire_response_sha256'],model_digest=tag['digest'],resident_vram_bytes=resident['size_vram'],cleanup_gpu=[cl[k]['values']['gpu_used_mib'] for k in ('before','after')],samples_count_peak_gpu_min_ram=series,final_gpu=[s['gpu_used_mib'] for s in rec['final_resource_samples']],check_sites=check_sites,passed_check_names=checks,archived_file_sha256=outfiles),indent=2))
