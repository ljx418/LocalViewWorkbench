import sys,os,json,runpy,time,types
from pathlib import Path
attempts=[];preload_events=[];phase='NEW'
def deny(event,args):
    attempts.append({'event':event,'args':repr(args)[:200]})
    raise RuntimeError('ROOT_GUARD_DENIED:'+event)
def audit(event,args):
    if event=='ctypes.dlopen' and phase=='OPEN' and args==(None,):
        if preload_events:deny(event,args)
        preload_events.append({'event':event,'name':None});return
    prohibited=(event.startswith(('subprocess.','socket.','os.exec','os.spawn','os.posix_spawn','ctypes.dlsym')) or event in ('os.system','os.fork','os.forkpty','pty.spawn','sqlite3.connect','ctypes.dlopen','os.dlopen'))
    if event=='open':
        name=str(args[0]).lower()
        prohibited=prohibited or 'shared-counter.json' in name or '/.lvw-runtime/' in name or 'program02.sqlite' in name or ('original.' in name and name.endswith(('.db','.sqlite','.sqlite3')))
    if prohibited:deny(event,args)
def begin():
    global phase
    if phase!='NEW':raise RuntimeError('PRELOAD_WINDOW_CANNOT_REOPEN')
    phase='OPEN'
def finish():
    global phase
    phase='CLOSED'
    if len(preload_events)!=1:raise RuntimeError('PRELOAD_EVENT_COUNT')
sys.addaudithook(audit)
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
control=types.SimpleNamespace(begin=begin,finish=finish,events=preload_events)
sys.modules['lvw_root_preload_control']=control
started=time.time();selftest=[]
try:
    for event in ['subprocess.Popen','socket.__new__','os.fork','os.exec','os.system','sqlite3.connect','ctypes.dlopen','ctypes.dlsym']:
        try:sys.audit(event,'guard_selftest')
        except RuntimeError:selftest.append(event)
        else:raise RuntimeError('GUARD_SELFTEST_MISSING:'+event)
    attempts.clear()
    runpy.run_path(sys.argv[1],run_name='__main__')
finally:
    Path(sys.argv[2]).write_text(json.dumps({'guard_precedes_candidate_and_pytest':True,'selftest_denials':selftest,'runtime_denials':attempts,'preload_events':preload_events,'preload_window_final_state':phase,'wall_seconds':time.time()-started},indent=2)+'\n')
