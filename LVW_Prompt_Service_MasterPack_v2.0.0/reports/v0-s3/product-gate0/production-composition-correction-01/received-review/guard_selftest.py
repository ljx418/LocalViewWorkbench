import os,subprocess,socket,sqlite3
from pathlib import Path
checks=[lambda:subprocess.Popen(['/bin/true']),lambda:socket.socket(),lambda:os.fork(),lambda:os.execv('/bin/true',['true']),lambda:os.system('true'),lambda:sqlite3.connect(':memory:'),lambda:Path('/tmp/lvw-s3-p4-cpu-control-xn4cjn_s/shared-counter.json').read_bytes(),lambda:Path('/tmp/original.sqlite').read_bytes()]
for f in checks:
 try:f()
 except RuntimeError as e:assert 'INDEPENDENT_' in str(e)
 else:raise AssertionError('guard bypass')
print('8 preimport guard denials confirmed; no candidate import')
