import sys,os,json,hashlib,threading,time,errno
from pathlib import Path
D=Path(__file__).parent
P=json.loads((D/'plan.json').read_text())
R=Path(P['report_dir']);ROOT=Path(P['cwd'])
for path,digest in {**P['sourcepins'],**P['toolpins'],**P['dependency_pins']}.items():
    if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=digest:
        raise RuntimeError('PIN_DRIFT:'+path)
# Trusted stdlib preload after hard guard and all pinned files, before candidate/pytest.
for item in P['stdlib_pins'].values():
    if hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()!=item['sha256']:
        raise RuntimeError('STDLIB_PIN_DRIFT:'+item['path'])
if 'ctypes' in sys.modules:raise RuntimeError('CTYPES_ALREADY_IMPORTED_BEFORE_WINDOW')
_control=sys.modules['lvw_root_preload_control']
_control.begin()
try:
    import ctypes
finally:
    _control.finish()

sys.path.append(P['dependency_root']);sys.path.insert(0,str(ROOT))
import pytest

def inventory():
    rows={};filtered=[];unknown=[]
    try:names=os.listdir('/proc/self/fd')
    except OSError as e:return {'available':False,'error':repr(e),'rows':{},'unknown':['enumeration']}
    for name in names:
        if not name.isdigit():continue
        n=int(name)
        try:
            st=os.fstat(n);rows[n]=[st.st_dev,st.st_ino,st.st_mode]
        except OSError as e:
            if e.errno==errno.EBADF:filtered.append(n)
            else:unknown.append({'fd':n,'errno':e.errno})
    return {'available':True,'rows':rows,'filtered':filtered,'unknown':unknown}

class Capture:
    def __init__(self):self.collected=[];self.reports=[]
    def pytest_collection_finish(self,session):
        self.collected=[x.nodeid for x in session.items]
        if self.collected!=P['nodeids']:
            pytest.exit('FROZEN_NODE_ORDER_MISMATCH',returncode=4)
    def pytest_runtest_logreport(self,report):
        if report.when=='call' or report.failed or report.skipped:
            self.reports.append({'nodeid':report.nodeid,'when':report.when,'outcome':report.outcome,'duration':report.duration,'longrepr':str(report.longrepr) if report.failed else None})

before=inventory();threads_before=[t.name for t in threading.enumerate()]
capture=Capture();started=time.time()
code=int(pytest.main(['-q','-s','--tb=short','-p','no:cacheprovider','--basetemp',str(R/'pytest-temp')]+P['nodeids'],plugins=[capture]))
after=inventory();threads_after=[t.name for t in threading.enumerate()]
passed=[x['nodeid'] for x in capture.reports if x['when']=='call' and x['outcome']=='passed']
failures=[x for x in capture.reports if x['outcome']=='failed'];skips=[x for x in capture.reports if x['outcome']=='skipped']
new_or_reused=[n for n,identity in after['rows'].items() if before['rows'].get(n)!=identity]
clean=(before['available'] and after['available'] and bool(before['rows']) and not before['unknown'] and not after['unknown'] and not new_or_reused and threads_after==['MainThread'])
result={'stdlib_preload':{'events':_control.events,'window_closed_before_candidate':True},'kind':'LVW_N1_ROOT_FROZEN_VALIDATION','pytest_exit':code,'duration_seconds':time.time()-started,'selected':P['nodeids'],'collected':capture.collected,'call_count':len([x for x in capture.reports if x['when']=='call']),'pass_count':len(passed),'fail_count':len(failures),'skip_count':len(skips),'reports':capture.reports,'integrity_only_nodes':P['integrity_only_nodes'],'functional_pass_count':len([n for n in passed if n not in P['integrity_only_nodes']]),'fd_before':before,'fd_after':after,'new_or_reused_fds':new_or_reused,'threads_before':threads_before,'threads_after':threads_after,'cleanup_proven_for_batch':clean,'stage_pass_claim':False,'native_proven':False,'dependency_scope':'Previously frozen named dependency files, not full environment distributions/transitive closure'}
(R/'native-custody-correction-02.receipt.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ['pytest_exit','call_count','pass_count','fail_count','skip_count','functional_pass_count','cleanup_proven_for_batch']}))
raise SystemExit(code if code else (0 if clean and len(passed)==len(P['nodeids']) and not skips else 1))
