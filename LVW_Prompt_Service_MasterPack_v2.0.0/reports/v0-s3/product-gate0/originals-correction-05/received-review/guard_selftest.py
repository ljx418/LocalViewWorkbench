import sys,os,socket,subprocess,sqlite3,json
from pathlib import Path
assert 'tools.v0_s3_coordinator' not in sys.modules
cases={'subprocess':lambda:subprocess.Popen(['/definitely-no-execute']), 'socket':lambda:socket.socket(),'fork':lambda:os.fork(),'exec':lambda:os.execv('/definitely-no-execute',['guard-test']),'system':lambda:os.system('true'),'sqlite':lambda:sqlite3.connect(':memory:'),'counter':lambda:open('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json'),'ledger':lambda:open('/tmp/original.sqlite'),'ledgerjson':lambda:open('/tmp/global-ledger.json')}
results={}
for name,fn in cases.items():
 try:fn()
 except RuntimeError as ex:
  assert str(ex).startswith('INDEPENDENT_');results[name]=str(ex)
 else:raise AssertionError(name)
Path(__file__).with_name('guard-selftest-results.json').write_text(json.dumps(results,indent=2));print(json.dumps(results))
