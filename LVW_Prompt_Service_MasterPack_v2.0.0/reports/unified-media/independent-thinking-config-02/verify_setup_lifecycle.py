"""No network/process/GPU/ledger: execute frozen harness with fake setup dependencies."""
import asyncio,hashlib,json,sys,types,os
from pathlib import Path
R=Path.cwd();O=R/'reports/unified-media/independent-thinking-config-02';sys.path[:0]=[str(R),str(R/'lvw/backend')]
m=types.ModuleType('review_frozen_probe');m.__file__=str(R/'reports/unified-media/thinking_config_probe.py')
exec(compile((O/'harness-final.py.txt').read_text(),m.__file__,'exec'),m.__dict__)
scenario=os.environ.get('REVIEW_SCENARIO','missing_gpu');fake=O/('fake-terminal-'+scenario);(fake/'reports/unified-media/live-14').mkdir(parents=True,exist_ok=True)
(fake/'reports/unified-media/independent-live-14').mkdir(exist_ok=True)
exe=fake/'ollama.exe';exe.write_bytes(b'fake tool')
binding={name:{'path':str(exe.resolve()),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()} for name in ['native_ollama','powershell']}
(fake/'reports/unified-media/live-14/bindings.json').write_text(json.dumps(binding));(fake/'reports/unified-media/live-14/actual-model-identity.json').write_text('{"digest":"fake"}')
for i in range(4):(fake/f'reports/unified-media/independent-live-14/frame-{i}.ppm').write_bytes(b'synthetic')
for name in ['request.json','approval.json']:(fake/name).write_text('{}')
# Preserve relative __file__ layout without accessing external files.
script=fake/'reports/unified-media/thinking_config_probe.py';script.write_text('frozen synthetic identity')
m.__file__=str(script.resolve());m.ROOT=fake.resolve();m.listening=lambda:False
calls=[]
m.program=types.SimpleNamespace(reserve=lambda *a:calls.append('reserve'),program_paths=lambda:('request.json','approval.json'),bind=lambda *a:calls.append('bind'),bind_execution=lambda *a:calls.append('bind_execution'),close_retaining_reservation=lambda *a:calls.append('close_retaining'),settle=lambda *a:calls.append('settle'),LEDGER='never-used-fake-ledger')
m.subprocess=types.SimpleNamespace(check_output=lambda args,**kw:'fake-head\n' if args[1]=='rev-parse' else '',run=lambda *a,**kw:types.SimpleNamespace(returncode=0))
m.shutil=types.SimpleNamespace(which=lambda _:None)
def reserve(*a):
    calls.append('reserve')
    if scenario=='reserve_failure':raise ValueError('synthetic reserve rejection')
def bind(*a):
    calls.append('bind')
    if scenario=='bind_failure':raise ValueError('synthetic bind rejection')
def settle(*a):
    calls.append('settle');assert a[1]==0
    if scenario=='settle_failure':raise ValueError('synthetic settlement rejection')
    return {'actual_model_actions':0,'mock_only':True}
m.program.reserve=reserve;m.program.bind=bind;m.program.settle=settle
asyncio.run(m.main())
receipt=json.loads((fake/'reports/unified-media/thinking-config-probe-02/receipt.json').read_text())
assert receipt['decision']==('NO_GO_CLEANUP_PENDING' if scenario=='settle_failure' else 'NO_GO') and receipt['cleanup_proven'] is True
terminal=json.loads((fake/'reports/unified-media/thinking-config-probe-02/authorization.terminal.json').read_text())
assert terminal['status']=='EXPIRED_'+receipt['decision']
if scenario=='settle_failure':
    assert calls==['reserve','bind','settle','close_retaining']
elif scenario=='reserve_failure':
    assert calls==['reserve'] and receipt['no_reservation_issued'] is True
else:
    assert calls==['reserve','bind','settle'] and receipt['settlement']['actual_model_actions']==0
print(json.dumps({'scenario':scenario,'calls':calls,'terminal_receipt':True,'cleanup_proven':True,'real_actions':0},indent=2))
