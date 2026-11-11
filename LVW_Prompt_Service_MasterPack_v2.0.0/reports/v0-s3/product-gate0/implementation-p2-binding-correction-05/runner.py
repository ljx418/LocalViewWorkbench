"""Forward-only offline pytest boundary; final phase permits exactly one sealed parser test."""
import base64, hashlib, inspect, json, os, re, selectors, shutil, subprocess, sys, tempfile, time
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
os.chdir(ROOT);sys.path.insert(0,str(ROOT))
phase=sys.argv[1]
assert phase in ('directed','directed2','directed3','directed4','combined')
allow=json.loads((OUT.parent/'offline-parser-allowance-05.json').read_text())
assert hashlib.sha256((ROOT/allow['test_file']).read_bytes()).hexdigest()==allow['test_file_sha256']
records=[];parser=[];denied=[]
def store(name,value):
    (OUT/(phase+'-'+name+'.json')).write_text(json.dumps(value,indent=2,ensure_ascii=False,default=str)+'\n')
def audit(event,args):
    if event=='open' and isinstance(args[0],(str,bytes)):
        path=os.fsdecode(args[0])
        if path.startswith('/mnt/') or re.match(r'^[A-Za-z]:',path):
            denied.append(dict(event=event,path=path));store('denied',denied)
            raise RuntimeError('offline host file read forbidden')
    if event=='subprocess.Popen':
        exe,argv,cwd,env=args
        exe=os.fsdecode(exe)
        host=exe.lower().endswith('.exe') or exe.startswith('/mnt/') or bool(re.match(r'^[A-Za-z]:',exe))
        if host:
            if not parser or parser[-1].get('started') or argv!=parser[-1]['argv']:
                denied.append(dict(event=event,argv=argv));store('denied',denied)
                raise RuntimeError('offline host process forbidden')
            parser[-1]['started']=True;store('parser',parser)
        records.append(dict(executable=exe,argv=[os.fsdecode(x) for x in argv],cwd=str(cwd) if cwd is not None else None))
sys.addaudithook(audit)
real_popen=subprocess.Popen
class GuardedPopen(real_popen):
    def __init__(self,args,*pos,**kwargs):
        exe=os.fsdecode(args[0]) if isinstance(args,(list,tuple)) else str(args)
        host=exe.lower().endswith('.exe') or exe.startswith('/mnt/') or bool(re.match(r'^[A-Za-z]:',exe))
        self.parser_record=None
        if host:
            assert phase=='combined' and not parser,'parser quota or phase'
            assert exe.lower()=='/mnt/c/windows/system32/windowspowershell/v1.0/powershell.exe','only system parser'
            assert args[1:4]==['-NoProfile','-NonInteractive','-Command'] and len(args)==5
            prefix="$tokens=$null;$errors=$null;[void][System.Management.Automation.Language.Parser]::ParseInput([System.Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
            suffix="')),[ref]$tokens,[ref]$errors);if($errors.Count){Write-Output ('PARSE_ERRORS='+$errors.Count);exit 1};Write-Output 'PARSE_ERRORS=0'"
            command=args[4];assert command.startswith(prefix) and command.endswith(suffix)
            encoded=command[len(prefix):-len(suffix)];base64.b64decode(encoded,validate=True)
            assert any(f.function==allow['test_name'] and Path(f.filename).resolve()==ROOT/allow['test_file'] for f in inspect.stack())
            assert sum(len(x.encode()) for x in args)<=65536 and not kwargs.get('shell')
            self.parser_record=dict(argv=list(args),started=False,exit=None,stdout=None,stderr=None)
            parser.append(self.parser_record);store('parser',parser)
        super().__init__(args,*pos,**kwargs)
    def communicate(self,input=None,timeout=None):
        if self.parser_record is not None:assert timeout is not None and timeout<=30
        try:
            if self.parser_record is None:
                out,err=super().communicate(input,timeout)
            else:
                assert input is None
                chunks=[bytearray(),bytearray()];start=time.monotonic()
                with selectors.DefaultSelector() as selector:
                    selector.register(self.stdout,selectors.EVENT_READ,0)
                    selector.register(self.stderr,selectors.EVENT_READ,1)
                    try:
                        while selector.get_map():
                            remaining=timeout-(time.monotonic()-start)
                            if remaining<=0:raise TimeoutError('parser 30s limit')
                            for key,_ in selector.select(min(remaining,.1)):
                                room=65536-sum(map(len,chunks))
                                block=os.read(key.fileobj.fileno(),min(4096,room+1))
                                if not block:selector.unregister(key.fileobj);continue
                                chunks[key.data].extend(block[:room])
                                if len(block)>room:raise RuntimeError('parser capture cap')
                        self.wait(timeout=max(.001,timeout-(time.monotonic()-start)))
                    finally:
                        if self.poll() is None:self.kill();self.wait(timeout=1)
                        self.stdout.close();self.stderr.close()
                        self.parser_record.update(exit=self.returncode,stdout=chunks[0].decode(errors='replace'),stderr=chunks[1].decode(errors='replace'),elapsed=time.monotonic()-start)
                out,err=map(bytes,chunks)
            if self.parser_record is not None:
                self.parser_record.update(exit=self.returncode,stdout_base64=base64.b64encode(out).decode('ascii'),stderr_base64=base64.b64encode(err).decode('ascii'))
                assert len(out)+len(err)<=65536
            return out,err
        finally:
            if self.parser_record is not None:store('parser',parser)
subprocess.Popen=GuardedPopen
files=['tools/test_v0_s3_runtime_binding.py']
if phase=='combined':
    files+=['tools/test_v0_s3_budget_authority.py','LVW_V0_RuntimePatch/tests/test_s3_program_budget.py']
    files+=['LVW_V0_RuntimePatch/tests/'+x for x in ['test_s2_measurements.py','test_s2_lifecycle_authorization.py','test_lvw_v0_bridge.py','test_s2_video_transport.py','test_s2_native_evidence.py','test_s2_warm_benchmark.py','test_s2_runtime.py']]
import pytest
class Counts:
    def __init__(self):self.collected=0;self.results=[]
    def pytest_collection_finish(self,session):self.collected=len(session.items)
    def pytest_runtest_logreport(self,report):
        if report.when=='call' or report.failed:self.results.append(dict(nodeid=report.nodeid,when=report.when,outcome=report.outcome))
counts=Counts()
start=time.monotonic()
with tempfile.TemporaryDirectory(prefix='lvw-implementation-c05-'+phase+'-') as tmp:
    raw=OUT/(phase+'-raw');raw.mkdir()
    os.environ['P2B_RAW_DIR']=str(raw)
    argv=['-q','-s','-p','no:cacheprovider',*files,'--basetemp='+tmp+'/pytest']
    if phase.startswith('directed'):argv+=['-k', 'correction05 and (all-permanent or early-permanent or shared-afterwrite)' if phase=='directed3' else 'correction05 or correction04_public_run_maximum']
    store('command',dict(argv=[sys.executable,'-B',str(Path(__file__)),phase],pytest_argv=argv,cwd=str(ROOT),start=start,source_hashes={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['tools/v0_s3_runtime_binding.py','tools/test_v0_s3_runtime_binding.py']},allowance_sha256=hashlib.sha256((OUT.parent/'offline-parser-allowance-05.json').read_bytes()).hexdigest()))
    result=pytest.main(argv,plugins=[counts])
    store("counts",dict(collected=counts.collected,results=counts.results))
store('receipt',dict(exit=int(result),elapsed=time.monotonic()-start,parser_invocations=sum(bool(x.get('started')) for x in parser),
    host_hash_reads=0,denied=denied,owned_tmp=tmp,removed=not Path(tmp).exists(),actual_child='DRAFT_NOT_AUTHORIZED',processes=records))
raise SystemExit(result)
