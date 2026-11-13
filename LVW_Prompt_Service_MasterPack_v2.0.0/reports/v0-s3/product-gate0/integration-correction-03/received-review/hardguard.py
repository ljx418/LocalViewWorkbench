"""Reviewer boundary installed before candidate imports."""
import sys, os, json, runpy
from pathlib import Path
entry, receipt, *args = sys.argv[1:]
blocked=[]
def boundary(event, args):
    if (event.startswith(('subprocess.', 'socket.', 'os.exec', 'os.spawn', 'os.posix_spawn')) or event in ('os.system','os.fork','os.forkpty','pty.spawn')):
        blocked.append(event)
        raise RuntimeError('REVIEW_PREIMPORT_DENIED:'+event)
    if event == 'open':
        name=str(args[0])
        if name.endswith('shared-counter.json') or ('ledger' in name.lower() and name.endswith(('.db','.sqlite','.sqlite3'))):
            blocked.append('protected-open:'+name)
            raise RuntimeError('REVIEW_PROTECTED_STATE_DENIED')
sys.addaudithook(boundary)
sys.dont_write_bytecode=True
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
sys.path.insert(0,str(Path.cwd()))
sys.argv=[entry]+args
try:
    runpy.run_path(entry,run_name='__main__')
finally:
    Path(receipt).write_text(json.dumps({'installed_before_candidate_import':True,'entry':entry,'arguments':args,'observed_denials':blocked,'process_network_denied':True,'original_counter_and_ledger_denied':True},indent=2)+'\n')
