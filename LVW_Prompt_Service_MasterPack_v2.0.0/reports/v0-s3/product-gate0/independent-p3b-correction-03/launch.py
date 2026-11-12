"""Independent offline launch: guard precedes pytest/product/test imports."""
import sys, os
EVENTS=[]
BLOCKED=('socket.connect','socket.bind','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr','socket.getnameinfo','subprocess.Popen','os.system','os.exec','os.spawn','os.posix_spawn','os.fork','os.forkpty')
def audit(event,args):
    if event in BLOCKED:
        EVENTS.append(event)
        raise RuntimeError('independent offline boundary: '+event)
sys.addaudithook(audit)
sys.dont_write_bytecode=True
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
os.environ['PYTHONDONTWRITEBYTECODE']='1'
os.environ.pop('PYTHONPYCACHEPREFIX',None)
import json, runpy, tempfile, shutil, hashlib, traceback
from pathlib import Path
OUT=Path(__file__).resolve().parent
PACK=OUT.parents[3]
sys.path.insert(0,str(PACK))
mode=sys.argv[1]
state={'mode':mode,'before_pytest_import':'pytest' not in sys.modules,'before_product_import':not any(k.startswith('tools.') for k in sys.modules),'blocked_events':EVENTS,'owned_roots':[]}
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
owned=Path(tempfile.mkdtemp(prefix='lvw-independent-c03-6e497-'+mode+'-'))
state['owned_roots'].append(str(owned))
(OUT/(mode+'.ownership.json')).write_text(json.dumps(state,indent=2)+'\n')
os.environ['TMPDIR']=str(owned)
tempfile.tempdir=str(owned)
exitcode=0
try:
    if mode=='suite':
        import pytest
        class Collection:
            def pytest_collection_finish(self,session):
                (OUT/'collected-nodeids.json').write_text(json.dumps([i.nodeid for i in session.items],indent=2)+'\n')
        exitcode=int(pytest.main(['tools/test_v0_s3_quality_phase.py','-q','-p','no:cacheprovider','--no-header','-rN','--basetemp',str(owned/'pytest')],plugins=[Collection()]))
    elif mode=='guard':
        # Four audit events, before test module's monkeypatches can obscure them.
        import socket,subprocess
        results={}
        def attempt(name,fn):
            try:fn();results[name]='NOT_BLOCKED'
            except RuntimeError as e:results[name]=str(e)
        def connect():
            with socket.socket() as s:s.connect(('127.0.0.1',9))
        def bind():
            with socket.socket() as s:s.bind(('127.0.0.1',0))
        attempt('connect',connect);attempt('bind',bind)
        attempt('Popen',lambda:subprocess.Popen(['/bin/true']))
        attempt('system',lambda:os.system('true'))
        print(json.dumps(results,indent=2));exitcode=0 if len(EVENTS)==4 else 1
    elif mode=='replay':
        runpy.run_path(str(PACK/'reports/v0-s3/product-gate0/implementation-p3b-correction-03/replay_correction02_probes.py'),run_name='__main__')
    elif mode=='focused':
        runpy.run_path(str(OUT/'focused.py'),run_name='__main__')
    else:raise ValueError(mode)
except BaseException as e:
    traceback.print_exc();exitcode=3
finally:
    # Only this invocation's explicitly registered root, never previous roots.
    shutil.rmtree(owned)
    state.update(exit_code=exitcode,owned_roots_removed=not owned.exists(),blocked_events=EVENTS,launcher_sha256=digest(Path(__file__)),native_or_direct_syscall_immunity_claim=False)
    (OUT/(mode+'.launch-receipt.json')).write_text(json.dumps(state,indent=2)+'\n')
sys.exit(exitcode)
