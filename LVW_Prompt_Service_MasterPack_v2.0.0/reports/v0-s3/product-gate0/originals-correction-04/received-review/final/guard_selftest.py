import sys,os,json,socket,subprocess,sqlite3
from pathlib import Path
O=Path(__file__).resolve().parent
cases={
 'popen':lambda:subprocess.Popen([sys.executable,'-c','pass']),
 'socket':lambda:socket.socket(),
 'fork':lambda:os.fork(),
 'exec':lambda:os.execv('/bin/true',['true']),
 'system':lambda:os.system('true'),
 'counter':lambda:open('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json'),
 'ledger':lambda:open('/tmp/protected-ledger.sqlite'),
 'sqlite_direct':lambda:sqlite3.connect('/tmp/protected-ledger.sqlite'),
}
results={}
for name,fn in cases.items():
 try:fn()
 except RuntimeError as e:results[name]=str(e)
 else:raise AssertionError('guard allowed '+name)
(O/'guard-selftest.json').write_text(json.dumps(results,indent=2))
print(json.dumps(results))
