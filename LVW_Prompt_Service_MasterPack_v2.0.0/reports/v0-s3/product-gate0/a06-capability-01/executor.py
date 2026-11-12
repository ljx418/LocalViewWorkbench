import ast, hashlib, json, os, stat, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
CHILD=HERE.parent/'a06-capability-01.child.json'
def rawwrite(name,data):
    with (HERE/name).open('xb') as f: f.write(data)
def save(name,value): rawwrite(name,(json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode())
def main():
    started=time.monotonic(); child=json.loads(CHILD.read_text()); result={'kind':'A06_READ_ONLY_CAPABILITY_FACTS_NOT_GATE0','candidate_sha':child['candidate_sha'],'child_sha256':hashlib.sha256(CHILD.read_bytes()).hexdigest(),'status':'RUNNING','host_processes_started':0,'source_facts':{},'errors':[],'stage_pass_claim':False,'product_gate0':False}
    assert hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==child['executor_sha256']
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT.parent,text=True).strip()==child['candidate_sha']
    approval=ROOT/child['parent_approval']; req=ROOT/child['parent_request']
    assert hashlib.sha256(approval.read_bytes()).hexdigest()==child['parent_approval_sha256']
    assert hashlib.sha256(req.read_bytes()).hexdigest()==json.loads(approval.read_text())['request_sha256']
    assert json.loads(approval.read_text())['decision']=='APPROVED'
    claim=Path(child['claim_path']); claim.parent.mkdir(parents=True,exist_ok=True)
    with claim.open('xb') as f:f.write((json.dumps({'child_sha256':result['child_sha256'],'status':'RUNNING','candidate_sha':child['candidate_sha']})+'\n').encode());f.flush();os.fsync(f.fileno())
    try:
        total=0; trees={}
        for role,name in child['files'].items():
            path=Path(name)
            for ancestor in (path,*path.parents):
                if ancestor.is_symlink():raise RuntimeError('source symlink: '+role)
            before=path.stat();assert stat.S_ISREG(before.st_mode)
            assert 0<before.st_size<=child['budgets']['per_file_bytes'];total+=before.st_size;assert total<=child['budgets']['source_total_bytes']
            with path.open('rb') as f:raw=f.read(child['budgets']['per_file_bytes']+1)
            after=path.stat();assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns)
            assert len(raw)==before.st_size
            result['source_facts'][role]={'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}
            if role!='native_python':trees[role]=ast.parse(raw.decode('utf-8-sig'))
        result['source_bytes_read']=total
        required={'--base-directory','--user-directory','--disable-auto-launch','--disable-api-nodes','--disable-all-custom-nodes','--whitelist-custom-nodes'}
        flags={n.value for n in ast.walk(trees['cli_args']) if isinstance(n,ast.Constant) and isinstance(n.value,str) and n.value in required}
        mapping={}
        for node in ast.walk(trees['nodes']):
            if isinstance(node,(ast.Assign,ast.AnnAssign)):
                targets=node.targets if isinstance(node,ast.Assign) else [node.target]
                if any(isinstance(t,ast.Name) and t.id=='NODE_CLASS_MAPPINGS' for t in targets) and isinstance(node.value,ast.Dict):
                    for k,v in zip(node.value.keys,node.value.values):
                        if isinstance(k,ast.Constant) and k.value in ('LoadImage','SaveImage'):
                            mapping[k.value]=v.id if isinstance(v,ast.Name) else 'NON_LITERAL_UNVERIFIED'
        result['static_declarations']={'builtin_mapping':mapping,'required_flags_found':sorted(flags),'required_flags_missing':sorted(required-flags),'proof_scope':'AST declarations only; actual runtime registration and baseline execution NOT verified'}
        command=child['command']; assert command[0]==child['files']['native_python']
        save('native.command.json',{'argv':command,'timeout_seconds':child['budgets']['native_seconds']})
        result['host_processes_started']=1
        process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            stdout,stderr=process.communicate(timeout=child['budgets']['native_seconds'])
        except subprocess.TimeoutExpired as timeout:
            rawwrite('native.stdout.log',timeout.output or b'');rawwrite('native.stderr.log',timeout.stderr or b'')
            result['native_process_exit_proven']=False
            result['owned_interop_pid']=process.pid
            raise RuntimeError('native timeout; exit unproven, no termination signal and no retry')
        completed=subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
        rawwrite('native.stdout.log',completed.stdout);rawwrite('native.stderr.log',completed.stderr);rawwrite('native.exit.log',(str(completed.returncode)+'\n').encode())
        assert len(completed.stdout)+len(completed.stderr)<=child['budgets']['native_output_bytes']
        assert completed.returncode==0 and not completed.stderr
        value=json.loads(completed.stdout);assert set(value)=={'is_admin','native_pid','platform'} and type(value['is_admin']) is bool and type(value['native_pid']) is int and value['platform']=='win32'
        result['native_token_observation']=value
        result['native_process_exit_proven']=True
        result['status']='FACTS_COLLECTED_NOT_RUNTIME_ACCEPTANCE'
    except BaseException as error:
        result['status']='FAILED_OR_UNPROVEN';result['errors'].append({'type':type(error).__name__,'message':str(error)})
    finally:
        result['wall_seconds']=time.monotonic()-started
        result['effects']={'model_actions':0,'gpu_actions':0,'media_reads':0,'services':0,'network':0,'downloads':0,'system_configuration_writes':0,'production_ledger_reads_or_writes':0,'full_checkpoints':0,'termination_signals':0}
        result['child_expired']=True;save('receipt.json',result)
        tmp=claim.with_suffix('.final.tmp')
        with tmp.open('xb') as f:f.write((json.dumps({'child_sha256':result['child_sha256'],'status':'EXPIRED','result':result['status'],'receipt_sha256':hashlib.sha256((HERE/'receipt.json').read_bytes()).hexdigest()})+'\n').encode());f.flush();os.fsync(f.fileno())
        os.replace(tmp,claim)
    print(json.dumps(result,ensure_ascii=False));return 0 if result['status']=='FACTS_COLLECTED_NOT_RUNTIME_ACCEPTANCE' else 1
if __name__=='__main__':raise SystemExit(main())
