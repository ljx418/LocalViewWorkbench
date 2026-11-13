"""Independent zero-process boundary, installed before every candidate import."""
import sys, os, json, runpy
from pathlib import Path
entry, receipt, *rest = sys.argv[1:]
denials=[]
def audit(event,args):
    if event.startswith(('subprocess.', 'socket.', 'os.exec', 'os.spawn', 'os.posix_spawn')) or event in ('os.fork','os.forkpty','os.system','pty.spawn'):
        denials.append(event)
        raise RuntimeError('INDEPENDENT_DENIED:'+event)
    if event == 'sqlite3.connect':
        denials.append('protected-sqlite:'+str(args[0]))
        raise RuntimeError('INDEPENDENT_PROTECTED_SQLITE')
    if event == 'open':
        name=str(args[0])
        if name.endswith('shared-counter.json') or ('ledger' in name.lower() and name.endswith(('.db','.sqlite','.sqlite3','.json','.jsonl','.db-wal','.sqlite-wal','.db-shm','.sqlite-shm'))):
            denials.append('protected-open:'+name)
            raise RuntimeError('INDEPENDENT_PROTECTED_STATE')
sys.addaudithook(audit)
sys.dont_write_bytecode=True
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
sys.path.insert(0,str(Path.cwd()))
sys.argv=[entry]+rest
try:
    runpy.run_path(entry,run_name='__main__')
finally:
    Path(receipt).write_text(json.dumps({'preimport':True,'entry':entry,'args':rest,'denials':denials,'zero_fixture_process_permission':True},indent=2))
