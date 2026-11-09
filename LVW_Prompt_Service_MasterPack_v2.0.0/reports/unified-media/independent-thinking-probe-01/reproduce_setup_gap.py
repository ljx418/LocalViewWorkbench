"""No network/process/GPU/ledger: execute frozen harness with fake setup dependencies."""
import asyncio,hashlib,json,sys,types
from pathlib import Path
R=Path.cwd();O=R/'reports/unified-media/independent-thinking-probe-01';sys.path[:0]=[str(R),str(R/'lvw/backend')]
m=types.ModuleType('review_frozen_probe');m.__file__=str(R/'reports/unified-media/thinking_capability_probe.py')
exec(compile((O/'harness-initial.py.txt').read_text(),m.__file__,'exec'),m.__dict__)
fake=O/'fake-pack';(fake/'reports/unified-media/live-14').mkdir(parents=True,exist_ok=True)
(fake/'reports/unified-media/independent-live-14').mkdir(exist_ok=True)
exe=fake/'ollama.exe';exe.write_bytes(b'fake tool')
binding={name:{'path':str(exe.resolve()),'sha256':hashlib.sha256(exe.read_bytes()).hexdigest()} for name in ['native_ollama','powershell']}
(fake/'reports/unified-media/live-14/bindings.json').write_text(json.dumps(binding));(fake/'reports/unified-media/live-14/actual-model-identity.json').write_text('{"digest":"fake"}')
for i in range(4):(fake/f'reports/unified-media/independent-live-14/frame-{i}.ppm').write_bytes(b'synthetic')
for name in ['request.json','approval.json']:(fake/name).write_text('{}')
# Preserve relative __file__ layout without accessing external files.
script=fake/'reports/unified-media/thinking_capability_probe.py';script.write_text('frozen synthetic identity')
m.__file__=str(script.resolve());m.ROOT=fake.resolve();m.listening=lambda:False
calls=[]
m.program=types.SimpleNamespace(reserve=lambda *a:calls.append('reserve'),program_paths=lambda:('request.json','approval.json'),bind=lambda *a:calls.append('bind'),bind_execution=lambda *a:calls.append('bind_execution'),close_retaining_reservation=lambda *a:calls.append('close_retaining'),settle=lambda *a:calls.append('settle'),LEDGER='never-used-fake-ledger')
m.subprocess=types.SimpleNamespace(check_output=lambda args,**kw:'fake-head\n' if args[1]=='rev-parse' else '',run=lambda *a,**kw:types.SimpleNamespace(returncode=0))
m.shutil=types.SimpleNamespace(which=lambda _:None)
try:asyncio.run(m.main())
except AssertionError as e:error=str(e)
else:raise AssertionError('expected missing tool error')
result={'error':error,'calls':calls,'terminal_receipt_exists':(fake/'reports/unified-media/thinking-capability-probe-01/receipt.json').exists(),'real_actions':0}
assert calls==['reserve','bind'] and not result['terminal_receipt_exists']
print(json.dumps(result,indent=2))
