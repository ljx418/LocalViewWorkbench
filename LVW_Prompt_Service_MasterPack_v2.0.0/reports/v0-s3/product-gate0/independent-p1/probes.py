"""Independent bounded counterexamples. All databases/processes are owned synthetic fixtures."""
import concurrent.futures,json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path.cwd();sys.path.insert(0,str(ROOT))
from tools.test_v0_s3_budget_authority import Fixture
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import core,program_budget as b
OUT=ROOT/'reports/v0-s3/product-gate0/independent-p1'
results=[]
def record(name,**facts):
    value=dict(probe=name,**facts);results.append(value);print(json.dumps(value),flush=True)
with tempfile.TemporaryDirectory(prefix='lvw-p1-independent-probes-') as owned:
    f=Fixture(Path(owned)/'authority',cap=32)
    env={'LVW_S3_BUDGET_REQUIRED':'1','LVW_S3_BUDGET_BINDING':str(f.binding),'LVW_S3_BUDGET_BINDING_SHA256':f.ref['sha256']}
    t=core.OllamaLoopbackTransport();sends=[]
    def failing_send(request,**kw):
        sends.append({'calls_visible_before_send':f.row()['calls']});raise TimeoutError('synthetic final network boundary')
    with patch.dict(os.environ,env),patch.object(t._opener,'open',side_effect=failing_send):
        for key in ('action_kind','payload_sha256','run_id','child_sha256','authority_sha256','binding_sha256','model'):
            before=f.row()['calls'];exchange=b._exchange;actual=[]
            def corrupt(*args):
                raw,proc=exchange(*args);actual.append(proc);value=json.loads(raw);value[key]='wrong';return json.dumps(value).encode(),proc
            with patch.object(b,'_exchange',side_effect=corrupt):
                try:t.chat({'model':'gemma4:26b','messages':[]},10);raise AssertionError('send accepted bad echo')
                except core.BridgeError as e:assert e.details['subcode']=='S3_BRIDGE_RECEIPT_INVALID'
            assert sends==[] and f.row()['calls']==before+1 and f.row()['active']==1
            record('echo_'+key,send_count=0,delta=1,reservation_active=1,process=actual[0])
        # Produce a real exit-0 process with a real reader exception after valid stdout.
        popen=b.subprocess.Popen;exchange=b._exchange;seen=[]
        class ReaderErrorAtEOF:
            def __init__(self,stream):self.stream=stream
            def read(self,*a):
                value=self.stream.read(*a)
                if not value:raise OSError('owned injected reader fault after stdout')
                return value
            def __getattr__(self,key):return getattr(self.stream,key)
        def launch(*a,**kw):
            p=popen(*a,**kw);p.stdout=ReaderErrorAtEOF(p.stdout);return p
        def observed(*a):
            raw,proc=exchange(*a);seen.append(dict(proc,valid_debited_stdout=json.loads(raw)['status']=='DEBITED'));return raw,proc
        before=f.row()['calls']
        with patch.object(b.subprocess,'Popen',side_effect=launch),patch.object(b,'_exchange',side_effect=observed):
            try:t.chat({'model':'gemma4:26b','messages':[]},10);raise AssertionError('reader error accepted')
            except core.BridgeError as e:assert e.details['subcode']=='S3_BRIDGE_PROCESS_FAILED'
        assert seen[0]['exit_code']==0 and seen[0]['error']=='PIPE_ERROR' and seen[0]['valid_debited_stdout']
        assert seen[0]['reaped'] and seen[0]['readers_joined'] and sends==[] and f.row()['calls']==before+1
        record('real_exit0_reader_error',send_count=0,delta=1,process=seen[0])
        before=f.row()['calls']
        try:t.chat({'model':'gemma4:26b','messages':[]},10);raise AssertionError('timeout accepted')
        except core.BridgeError as e:assert e.details['subcode']=='OLLAMA_TIMEOUT'
        assert sends==[{'calls_visible_before_send':before+1}] and f.row()['calls']==before+1
        record('failed_send_not_refunded',send_count=1,delta=1,observed=sends)
    # Actual cleanup entry, only the final network boundary substituted.
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*a):pass
        def read(self):return b'{}'
    before=f.row()['calls']
    with patch.dict(os.environ,env),patch.object(t._opener,'open',return_value=Response()) as send:
        t.cleanup('gemma4:26b',10)
        assert send.call_count==1 and json.loads(send.call_args.args[0].data)['keep_alive']==0
    assert f.row()['calls']==before
    record('production_cleanup_zero_debit',control_sends=1,delta=0)
    # Independent real transaction cap race: six requests compete for remaining two.
    g=Fixture(Path(owned)/'concurrent',cap=2)
    def debit(_):
        try:g.shim.debit(g.request());return 'DEBITED'
        except ValueError:return 'REFUSED'
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:outcomes=list(pool.map(debit,range(6)))
    assert outcomes.count('DEBITED')==2 and g.row()['calls']==2
    record('concurrent_exact_cap',outcomes=outcomes,calls=g.row()['calls'])
    f.authority.close_retaining_reservation('synthetic',ledger=f.ledger)
    assert f.row()['active']==2 and f.row()['calls']==9
    record('unknown_cleanup_retains_reservation',active=f.row()['active'],calls=f.row()['calls'],cap=f.row()['cap'])
assert not Path(owned).exists()
record('temporary_directory_cleanup',owned_root=owned,exists=False)
(OUT/'probes.json').write_text(json.dumps(results,indent=2)+'\n')
