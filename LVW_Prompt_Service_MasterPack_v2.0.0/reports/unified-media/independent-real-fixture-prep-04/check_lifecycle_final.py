import hashlib,json,os,sys,types
from pathlib import Path
R=Path.cwd();O=R/'reports/unified-media/independent-real-fixture-prep-04';sys.path[:0]=[str(R),str(R/'lvw/backend')]
m=types.ModuleType('review_fixture');m.__file__=str(R/'reports/unified-media/prepare_real_rejections.py')
exec(compile((O/'harness-final.py.txt').read_text(),m.__file__,'exec'),m.__dict__)
scenario=os.environ['REVIEW_SCENARIO'];fake=(O/'mock-fenced'/scenario/'pack').resolve();live=fake/'reports/unified-media/live-14';live.mkdir(parents=True)
exe=fake/'fake-fftool';exe.write_bytes(b'fake ff tool');binding={k:{'path':str(exe),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()} for k in ('ffmpeg','ffprobe')};(live/'bindings.json').write_text(json.dumps(binding))
for p in ['request.json','grant.json']:(fake/p).write_text('{}')
script=fake/'reports/unified-media/prepare_real_rejections.py';script.write_text('fake script')
m.ROOT=fake;m.__file__=str(script)
artifact=fake.parent.parent/'.lvw-runtime/lvw-prompt-service/R1-unified-fixtures/real-rejection-fixtures-04';assert artifact.is_relative_to(O.resolve())
# Distinct scenario names prevent mock roots sharing an actual filesystem destination.
m.ROOT=(O/'mock-fenced'/scenario/'nested'/'pack').resolve();new=m.ROOT
import shutil
shutil.copytree(fake,new)
fake=new;live=fake/'reports/unified-media/live-14';script=fake/'reports/unified-media/prepare_real_rejections.py';m.__file__=str(script)
artifact=fake.parent.parent/'.lvw-runtime/lvw-prompt-service/R1-unified-fixtures/real-rejection-fixtures-04'
if scenario=='collision':artifact.mkdir(parents=True);(artifact/'sentinel').write_text('foreign')
calls=[]
def reserve(*a,**kw):
    assert a[2]=={'model_calls':0,'provider_calls':0,'full_checkpoints':0} and a[3]==120 and kw['cpu_fixture'] is True
    calls.append('reserve')
    if scenario=='reserve_failure':raise ValueError('mock budget rejection')
def settle(*a):assert a[1]==0;calls.append('settle0');return {'actual_model_actions':0}
m.program=types.SimpleNamespace(approved=lambda: {},reserve=reserve,program_paths=lambda:('request.json','grant.json'),bind=lambda *a:calls.append('bind'),settle=settle,close_retaining_reservation=lambda *a:calls.append('retain'))
def output(args,**kw):
    if args[1]=='rev-parse':return 'mock-head\n'
    return ''
m.subprocess=types.SimpleNamespace(check_output=output,run=lambda *a,**kw:types.SimpleNamespace(returncode=0))
def run(argv,**kw):
    calls.append('fftool');assert kw['output_limit']==1024*1024
    if scenario=='missing_callback':raise RuntimeError('mock unproven exit')
    if 'libx264' in argv:
        assert '-frames:v' in argv and argv[argv.index('-frames:v')+1]=='1'
        assert argv[argv.index('-threads')+1]=='1' and '-n' in argv and '-nostdin' in argv
        Path(argv[-1]).write_bytes(b'x');result=types.SimpleNamespace(stdout=b'',stderr=b'fake',returncode=0)
    else:
        assert argv[argv.index('-protocol_whitelist')+1]=='file,pipe'
        result=types.SimpleNamespace(stdout=b'{"streams":[{"codec_type":"video","width":1,"height":1}],"format":{"duration":"1"}}',stderr=b'',returncode=0)
    kw['on_result'](result);return result
m.process_module=types.SimpleNamespace(run_bounded=run)
if scenario=='collision':
    try:m.main()
    except AssertionError:pass
    else:raise AssertionError('collision not rejected')
    assert calls==[] and (artifact/'sentinel').read_text()=='foreign'
    print(json.dumps({'scenario':scenario,'preflight_rejected':True,'calls':calls,'foreign_root_untouched':True,'real_tool_or_ledger_actions':0,'large_allocations':0},indent=2));sys.exit(0)
m.main()
out=fake/'reports/unified-media/real-rejection-fixtures-04';receipt=json.loads((out/'receipt.json').read_text())
assert receipt['artifacts_usable_for_acceptance'] is False
assert (out/'authorization.terminal.json').exists()
if scenario=='missing_callback':assert receipt['decision']=='NO_GO_CLEANUP_PENDING' and calls[-1]=='retain'
else:assert receipt['decision']=='NO_GO' and calls[-1]=='settle0' if scenario!='reserve_failure' else calls==['reserve']
if scenario=='collision':assert (artifact/'sentinel').read_text()=='foreign' and not receipt['owned_artifact_root_claimed']
assert not (artifact/'over-bytes.mp4').exists()
print(json.dumps({'scenario':scenario,'calls':calls,'attempted':receipt['tool_attempts'],'tool_cleanup_proven':receipt['tool_cleanup_proven'],'terminal_receipt':True,'real_tool_or_ledger_actions':0,'large_allocations':0},indent=2))
