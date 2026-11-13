"""Independent pre-import boundary; invoke a candidate entry without bindings."""
import sys, os, runpy, json
from pathlib import Path
BLOCKED = ('subprocess.Popen','os.system','os.exec','os.spawn','os.posix_spawn','os.fork','os.forkpty','socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr','socket.getnameinfo')
entry, evidence_path, *args = sys.argv[1:]
events=[]
def guard(event, arguments):
    if event in BLOCKED:
        if len(events)<100: events.append(event)
        registry=sys.modules.get('lvw_s3_offline_guard_registry')
        cls=getattr(registry,'violation_class',RuntimeError)
        raise cls('INDEPENDENT_PREIMPORT_BLOCKED:'+event)
sys.addaudithook(guard)
os.environ['PYTHONDONTWRITEBYTECODE']='1'
sys.dont_write_bytecode=True
sys.path.insert(0,str(Path.cwd()))
sys.argv=[entry]+args
try:
    runpy.run_path(entry,run_name='__main__')
finally:
    Path(evidence_path).write_text(json.dumps({'installed_before_entry':True,'blocked_events':list(BLOCKED),'observed_blocked_events':events,'entry':entry,'entry_args':args,'bindings_allowed':False},indent=2)+'\n')
