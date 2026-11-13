import sys,os,json
sys.dont_write_bytecode=True
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
blocked=[]
def guard(event,args):
 if event in {'subprocess.Popen','os.system','os.posix_spawn','os.fork','os.forkpty','socket.__new__','socket.connect','socket.getaddrinfo'}:
  blocked.append(event)
  raise RuntimeError('COLLECTION_ONLY_GUARD_BLOCKED:'+event)
sys.addaudithook(guard)
sys.path.insert(0,os.getcwd())
import pytest
nodes=json.loads(sys.argv[1]); collected=[]
class Plugin:
 def pytest_collection_finish(self, session): collected.extend(x.nodeid for x in session.items)
code=int(pytest.main(nodes+['--collect-only','-q','-p','no:cacheprovider'],plugins=[Plugin()]))
print('COLLECTION_RECEIPT='+json.dumps({'exit_code':code,'collected':collected,'exact_match':collected==nodes,'blocked_events':blocked,'tests_executed':0}))
raise SystemExit(0 if code==0 and collected==nodes and not blocked else 2)
