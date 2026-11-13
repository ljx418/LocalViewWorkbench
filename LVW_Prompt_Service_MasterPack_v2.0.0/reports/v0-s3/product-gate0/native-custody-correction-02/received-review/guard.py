import sys,os,json,runpy,time,signal
from pathlib import Path
D=Path(__file__).parent
attempts=[]
def audit(event,args):
 denied=(event.startswith(('subprocess.','socket.','os.exec','os.spawn','os.posix_spawn')) or event in ('os.system','os.fork','os.forkpty','pty.spawn','sqlite3.connect','ctypes.dlopen','ctypes.dlsym'))
 if event=='open':
  name=str(args[0]).lower()
  denied=denied or 'shared-counter.json' in name or '/.lvw-runtime/' in name or ('original.' in name and name.endswith(('.sqlite','.sqlite3','.db'))) or 'program02.sqlite' in name
 if denied:
  attempts.append({'event':event,'arg':repr(args)[:250]});raise RuntimeError('INDEPENDENT_AUDIT_DENIED:'+event)
sys.addaudithook(audit)
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
signal.alarm(290)
started=time.time()
try:
 # self-check uses audit events only, no real OS operations
 for event in ['subprocess.Popen','socket.__new__','os.fork','os.exec','os.system','sqlite3.connect']:
  try:sys.audit(event,'selftest')
  except RuntimeError:pass
  else:raise RuntimeError('GUARD_SELFTEST_MISSING:'+event)
 selftest=len(attempts);attempts.clear()
 runpy.run_path(sys.argv[1],run_name='__main__')
finally:
 Path(sys.argv[2]).write_text(json.dumps({'guard_precedes_candidate_and_pytest':True,'selftest_denials':selftest,'runtime_denials':attempts,'wall_seconds':time.time()-started},indent=2))
