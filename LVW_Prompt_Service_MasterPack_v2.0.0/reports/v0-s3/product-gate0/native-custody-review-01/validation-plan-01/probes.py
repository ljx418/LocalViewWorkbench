"""Independent in-process owner probes; no author test module is imported."""
import copy,json,threading
from pathlib import Path
from tools import v0_s3_native_custody as c
from tools import v0_s3_native_broker as b

class Facade:
    def __init__(self,fail=None): self.fail=fail;self.next=100;self.live={};self.calls=[]
    def alloc(self,kind):
        self.next+=1; self.live[self.next]=kind;return self.next
    def create_job(self): return self.alloc('job')
    def set_job_kill_on_close(self,h): self.calls.append(['kill_on_close',h])
    def create_pipe(self,name): return self.alloc(name+'_read'),self.alloc(name+'_write')
    def create_process_suspended(self,**kw):
        h=self.alloc('process');t=self.alloc('thread');self.calls.append(['create',h]);return b.CreatedProcess(h,t,4001,123)
    def assign_process_to_job(self,j,h):
        self.calls.append(['assign',j,h])
        if self.fail=='assign': raise b.BrokerError('BROKER_ASSIGN_FAILED')
        if self.fail=='cancel': raise KeyboardInterrupt('synthetic cancellation')
    def resume_thread(self,t):
        self.calls.append(['resume',t])
        if self.fail=='resume':raise b.BrokerError('BROKER_RESUME_FAILED')
        return 1
    def terminate_job(self,j,code):self.calls.append(['terminate_job',j])
    def terminate_process(self,h,code):self.calls.append(['terminate',h])
    def wait_process(self,h,timeout): return True
    def exit_code(self,h):return 1
    def job_process_ids(self,j):return []
    def close_handle(self,h):
        assert h in self.live,('UNKNOWN_HANDLE',h)
        self.calls.append(['close',h]);del self.live[h];return True
    def read_stream(self,h,size):return b''

class Peer:
    pid=123;executable='synthetic';executable_sha256='a'*64;reader_finished=True
    def __init__(self,plan,nonce,mode):self.plan=plan;self.nonce=nonce;self.mode=mode;self.closed=0;self.reads=0
    def read(self,timeout):
        self.reads+=1
        if self.mode=='cancel':raise KeyboardInterrupt('synthetic cancellation')
        return (json.dumps(dict(schema=c.CHANNEL_SCHEMA,kind='REFUSED',run_id=self.plan.run_id,candidate_sha=self.plan.candidate_sha,authorization_sha256=self.plan.authorization_sha256,nonce=self.nonce,sequence=1,state='UNKNOWN_RETAINED',detail={'code':'BROKER_ASSIGN_FAILED'})).encode()+b'\n')
    def close(self):self.closed+=1
    def write(self,raw):pass

def document():return dict(schema=c.PLAN_SCHEMA,run_id='independent',candidate_sha='a'*40,authorization_sha256='b'*64,lease_expires_at=2000,max_runtime_seconds=60,roles=[dict(role='COMFY',tools=[dict(path='C:/tools/python.exe',sha256='c'*64),dict(path='C:/tools/main.py',sha256='d'*64)],data={'user_directory':'user'},log='temp/comfy.log'),dict(role='OLLAMA',tools=[dict(path='C:/tools/ollama.exe',sha256='e'*64)],data={},log='temp/ollama.log')])

def run_case(name,root):
    doc=document()
    if name=='closed_log_boundaries':
        rejected=[]
        for log in ['C:/escape.log','C:escape.log','x.log:ads','../escape.log','/escape.log','x\\y.log']:
            doc['roles'][0]['log']=log
            try:c.validate_launch_plan(doc,now=1000)
            except c.CustodyError:rejected.append(log)
        return len(rejected)==6,{'rejected':rejected}
    if name=='user_directory_escape':
        doc['roles'][0]['data']['user_directory']='safe/../../outside'
        try:p=c.validate_launch_plan(doc,now=1000)
        except c.CustodyError:return True,{'refused':True}
        return False,{'accepted':True,'command':b.role_command(p.roles[0],root,[])['arguments']}
    if name=='sealed_plan_mutation':
        p=c.validate_launch_plan(doc,now=1000);p.sealed['roles'][0]['tools'][0]['path']='C:/foreign.exe'
        actual=b.role_command(p.roles[0],root,[])['executable']
        return actual!='C:/foreign.exe',{'actual_executable':actual}
    if name.startswith('owner_'):
        mode=name.removeprefix('owner_');f=Facade(mode);p=c.validate_launch_plan(doc,now=1000);core=b.BrokerCore(win32=f,plan=p,run_root=root)
        core.arm();caught=None
        try:core.launch()
        except BaseException as e:caught=type(e).__name__
        if mode=='success':core.stop()
        elif mode=='diagnostic':
            def broken():raise RuntimeError('synthetic diagnostic failure')
            core._collect_stream_counts=broken
            try:core.stop()
            except RuntimeError:caught='RuntimeError'
        before=dict(f.live);calls=list(f.calls);state=core.state
        # Record first; then explicitly release ONLY resources allocated by this facade.
        for reader in core.readers:reader.join(1)
        for h in list(f.live):f.close_handle(h)
        return not before,{'caught':caught,'state':state,'retained_owned_fake_handles':before,'calls':calls,'fake_owner_cleanup_after_record':not f.live}
    if name.startswith('parent_'):
        mode=name.removeprefix('parent_');peers=[]
        def launch(p,r,n):peer=Peer(p,n,mode);peers.append(peer);return peer
        s=c.NativeCustodySession(plan=doc,run_root=root,parent_child_remaining_seconds=60,launcher=launch,wall=lambda:1000,nonce='1'*32)
        caught=None
        try:s.start()
        except BaseException as e:caught=type(e).__name__
        closed=peers[0].closed
        peers[0].close() # only our synthetic peer, after evidence
        return closed==1,{'caught':caught,'closed_before_manual_cleanup':closed,'state':s.state}
    if name=='ready_write_failure':
        f=Facade();p=c.validate_launch_plan(doc,now=1000);core=b.BrokerCore(win32=f,plan=p,run_root=root)
        class Broken:
            def write(self,raw):raise BrokenPipeError('synthetic writer failure')
        loop=b.BrokerLoop(core=core,transport=Broken(),plan=p,nonce='1'*32,wall=lambda:1000)
        caught=None
        try:loop.run()
        except BrokenPipeError:caught='BrokenPipeError'
        before=dict(f.live)
        for h in list(f.live):f.close_handle(h)
        return not before,{'caught':caught,'retained_owned_fake_handles':before,'state':core.state}
    raise AssertionError(name)
