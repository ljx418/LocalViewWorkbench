"""Independent behavior probes. No fixture, process, network or original ledger."""
from pathlib import Path
import sys
OUT=Path(__file__).resolve().parent
exec(compile((OUT/'outer_boundary.py').read_bytes(),str(OUT/'outer_boundary.py'),'exec'))
PACK=OUT.parents[3]
sys.path.insert(0,str(PACK))
import json,os,importlib.util
spec=importlib.util.spec_from_file_location('review_helpers',PACK/'tools/test_v0_s3_supervisor.py')
T=importlib.util.module_from_spec(spec);spec.loader.exec_module(T)
E=T.EXECUTOR_MODULE; R=T.RUNNER_MODULE
R.install_offline_guard()
RESULTS=[]
class Handle:
 def __init__(self,pid,code=None): self.pid=pid; self.code=code; self.bad=False; self.stops=0
 def poll(self):
  if self.bad: raise OSError('exit unavailable')
  return self.code
 def wait(self,timeout=None): return self.poll()
 def terminate(self): self.stops+=1; self.code=-15
 def kill(self): self.stops+=1; self.code=-9
class Log:
 def flush(self): pass
 def close(self): pass

def setup(name):
 p=OUT/'synthetic-normal-watchdog'/name;p.mkdir(parents=True)
 c=T.fake_root_counter(p);_,digest,_=T.fake_root_binding(p,counter_path=c)
 ex=T.build_test_executor(p,counter_path=c,binding_digest=digest)
 T.context_inside(p)
 return p,c,ex

def admit(ex):
 prefix=T.executor_prefix();return ex.admit((prefix[0],prefix+['clean_terminal'],None,None))
def add(ex,h): admit(ex);return ex.register(h)
def attempt(ex):
 try: admit(ex);return 'ADMITTED'
 except Exception as err:return type(err).__name__+':'+str(err)
def final(p,ex):
 owned=p/'owned';owned.mkdir(exist_ok=True)
 out=R.finalize_session(executor=ex,owned=owned,stdout_handle=Log(),stderr_handle=Log(),saved_out=os.dup(1),saved_err=os.dup(2),source_hasher=lambda:{})
 return {'exit_code':out['exit_code'],'cleanup_proven':out['cleanup_proven'],'root_retained':owned.exists(),'failure_reasons':out['failure_reasons'],'proofs':out['proofs']}
def save(name,data):
 RESULTS.append({'name':name,**data});(OUT/'negative-results.json').write_text(json.dumps(RESULTS,indent=2));print(json.dumps(RESULTS[-1],sort_keys=True),flush=True)
def failure(kind):
 def fail(*a,**kw):
  if kind=='false':return False
  if kind=='gate':raise E.CpuGateError('INJECTED_FINISH')
  raise OSError('INJECTED_FINISH_IO')
 return fail

# Persistence failures at partial and full capacity. Expectations independent
# from test assertions: no new charge after settlement failure in this admit.
for count in [1,2]:
 for kind in ['gate','oserror','false','read_gate','read_oserror','read_only_gate','read_only_oserror']:
  name=f'finish_{kind}_capacity{count}';p,c,ex=setup(name)
  for n in range(count): add(ex,Handle(710000+n))
  for entry in ex.children:entry['process'].code=0
  original_finish=ex.counter.finish
  ex.counter.finish=failure(kind if kind in ['gate','oserror'] else 'false')
  if kind.startswith('read_'):
   def failread(i,kind=kind):
    if kind in ('read_gate','read_only_gate'):raise E.CpuGateError('INJECTED_READ')
    raise OSError('INJECTED_READ_IO')
   ex.counter.charge_state=failread
   if kind.startswith('read_only_'):ex.counter.finish=original_finish
  before=json.loads(c.read_text());result=attempt(ex);after=json.loads(c.read_text())
  assert after['starts_total']==before['starts_total'] and 'CPU_RECONCILIATION_UNSETTLED' in result
  assert all(x['state']=='STARTED' and not x['settled'] for x in after['charges'])
  uncertain=ex.uncertain; ledger=ex.charge_ledger()
  f=final(p,ex)
  assert not f['cleanup_proven'] and f['root_retained'] and f['exit_code']!=0
  save(name,{'expected':'refuse before new charge','actual':result,'starts_before':before['starts_total'],'starts_after':after['starts_total'],'unsafe_new_admission':after['starts_total']>before['starts_total'],'uncertain_after_attempt':uncertain,'ledger_after_attempt':ledger,'final':f})

# Genuine success / slot occupancy, unknown original handle, and sequential13.
p,c,ex=setup('live_exit');h1=Handle(720001);h2=Handle(720002);add(ex,h1);add(ex,h2)
a=attempt(ex);h1.code=0;b=attempt(ex);d=attempt(ex)
assert 'CPU_CONCURRENCY_LIMIT' in a and b=='ADMITTED' and 'CPU_CONCURRENCY_LIMIT' in d
save('live_exit',{'third_live':a,'after_one_exit':b,'one_more':d,'counter':json.loads(c.read_text())})
p,c,ex=setup('unknown_original');h=Handle(720003);h.bad=True;add(ex,h);a=attempt(ex);b=attempt(ex)
assert json.loads(c.read_text())['charges'][0]['state']=='STARTED'
save('unknown_original',{'next':a,'one_more':b,'first_occupied':True})
p,c,ex=setup('sequential13');peak=0
for i in range(13):
 h=Handle(730000+i);add(ex,h);h.code=0
 peak=max(peak,E.SharedCounter._occupied(json.loads(c.read_text())))
pre=json.loads(c.read_text());f=final(p,ex);post=json.loads(c.read_text())
assert post['starts_total']==13 and peak<=2 and f['cleanup_proven']
assert pre['charges'][0]['finished_wall']==post['charges'][0]['finished_wall']
assert ex.revoked and all(h['process'].stops==0 for h in ex.children)
save('sequential13',{'starts':post['starts_total'],'peak':peak,'final':f,'first_finished_wall_unchanged':True,'reserved':post['reserved_wall_seconds']})

# A terminal record exists for the same integer index but conflicts with
# original handle exit / custody. Use real finish to persist mismatch first.
for mode in ['wrong_exit','wrong_pid_birth','foreign_index','unknown_terminal']:
 p,c,ex=setup('idempotency_'+mode);h=Handle(740001);add(ex,h);h.code=0
 if mode in ['wrong_exit','wrong_pid_birth','unknown_terminal']:
  ex.counter.finish(0,state='UNKNOWN' if mode=='unknown_terminal' else 'STOPPED',exit_code=77 if mode=='wrong_exit' else 0,spent=1,pid=999999 if mode=='wrong_pid_birth' else h.pid,birth={'foreign':'session'} if mode=='wrong_pid_birth' else None)
 else:
  ex.counter.finish=lambda *a,**kw:False
  ex.counter.charge_state=lambda i:{'index':53,'settled':True,'state':'STOPPED','pid':999999,'birth':{'foreign':'session'},'exit_code':77}
 before=c.read_bytes();a=attempt(ex)
 if a=='ADMITTED':
  nxt=Handle(740002,0);ex.register(nxt)
 after=json.loads(c.read_text());f=final(p,ex)
 assert not f['cleanup_proven'] and f['root_retained'] and f['exit_code']!=0
 assert after['starts_total']==1
 save('idempotency_'+mode,{'expected':'conflicting or UNKNOWN terminal must not count as successful persistence','admit':a,'child':{k:v for k,v in ex.children[0].items() if k!='process'},'persisted_charge':after['charges'][0],'final':f,'new_starts':after['starts_total']-1})

# Marker alone skips persisted proof in reaper. Simulate readable evidence
# divergence in synthetic file; this is a robustness probe, not normal usage.
p,c,ex=setup('local_marker_disk_divergence');h=Handle(750001);add(ex,h);h.code=0
ex.reconcile_exited_children();doc=json.loads(c.read_text());doc['charges'][0].update(state='STARTED',settled=False,finished_wall=None);c.write_text(json.dumps(doc))
f=final(p,ex)
assert not f['cleanup_proven'] and f['root_retained']
assert json.loads(c.read_text())['charges'][0]['state']=='STARTED'
save('local_marker_disk_divergence',{'assumption':'synthetic persisted record diverges after local success','counter':json.loads(c.read_text()),'final':f})
# Same original latency trigger expanded to poll, write, read and exact edges.
for operation in ['poll','finish','charge_state']:
 for offset in [-0.001,0,1.0]:
  name=f'deadline_{operation}_{offset}';p,c,ex=setup(name);h=Handle(770001);add(ex,h);h.code=0
  deadline=ex.admission_deadline;now=[ex.clock()];ex.clock=lambda:now[0]
  owner=h if operation=='poll' else ex.counter
  original=getattr(owner,operation)
  def slow(*a,_original=original,**kw):
   result=_original(*a,**kw);now[0]=deadline+offset;return result
  setattr(owner,operation,slow)
  a=attempt(ex);after=json.loads(c.read_text())
  save(name,{'actual':a,'starts':after['starts_total'],'offset':offset,'clock':ex.clock(),'deadline':deadline,'deadline_unchanged':ex.admission_deadline==deadline})
  assert ex.admission_deadline==deadline
  assert (a=='ADMITTED' and after['starts_total']==2) if offset<0 else ('SESSION_ADMISSION_WINDOW_CLOSED' in a and after['starts_total']==1)
  if a=='ADMITTED':ex.register(Handle(770002,0))
  final(p,ex)
# Uncertainty raised by bounded I/O itself is rechecked before charge.
p,c,ex=setup('uncertain_after_reconciliation');h=Handle(780001);add(ex,h);h.code=0
original=ex.counter.finish
def uncertain_finish(*a,**kw):
 result=original(*a,**kw);ex.uncertain=True;return result
ex.counter.finish=uncertain_finish
a=attempt(ex);save('uncertain_after_reconciliation',{'actual':a,'starts':json.loads(c.read_text())['starts_total']})
assert 'SESSION_UNCERTAIN_CUSTODY' in a and json.loads(c.read_text())['starts_total']==1
final(p,ex)
# Strict identity on real read path and each admission identity component.
for mode in ['budget','role','scenario','argv','birth','state']:
 p,c,ex=setup('identity_'+mode);h=Handle(790001);add(ex,h);h.code=0
 ex.counter.finish(0,state='STOPPED',exit_code=0,spent=1,pid=h.pid,birth=None)
 doc=json.loads(c.read_text())
 if mode=='budget':doc['budget_id']='foreign'
 else:doc['charges'][0][mode]={'role':'review','scenario':'foreign','argv':['foreign'],'birth':{'foreign':1},'state':'TIMED_OUT'}[mode]
 c.write_text(json.dumps(doc));a=attempt(ex);f=final(p,ex)
 save('identity_'+mode,{'actual':a,'final':f,'starts':json.loads(c.read_text())['starts_total']})
 assert 'CPU_RECONCILIATION_UNSETTLED' in a and not f['cleanup_proven'] and f['root_retained']
# Existing exact proof must survive even a broken finish interface, without writes.
for mode in ['false','gate','oserror']:
 p,c,ex=setup('exact_terminal_'+mode);h=Handle(800001);add(ex,h);h.code=0
 ex.counter.finish(0,state='STOPPED',exit_code=0,spent=1,pid=h.pid,birth=None)
 pre=json.loads(c.read_text());ex.counter.finish=failure(mode)
 outcome=ex.reconcile_exited_children();f=final(p,ex);post=json.loads(c.read_text())
 save('exact_terminal_'+mode,{'reconciliation':outcome,'final':f,'finished_wall_unchanged':pre['charges'][0]['finished_wall']==post['charges'][0]['finished_wall'],'starts':post['starts_total'],'reserved':post['reserved_wall_seconds']})
 assert f['cleanup_proven'] and pre['charges'][0]==post['charges'][0]
# Already proven local state diverges to UNKNOWN as well as STARTED: no repair.
p,c,ex=setup('local_marker_unknown');h=Handle(810001);add(ex,h);h.code=0
ex.reconcile_exited_children();doc=json.loads(c.read_text());doc['charges'][0].update(state='UNKNOWN',settled=False,finished_wall=None);c.write_text(json.dumps(doc));f=final(p,ex)
save('local_marker_unknown',{'final':f,'charge':json.loads(c.read_text())['charges'][0]})
assert not f['cleanup_proven'] and json.loads(c.read_text())['charges'][0]['state']=='UNKNOWN'
# Finalizer persistence failures, with no pending entry to mask cleanup.
for settled in [False,True]:
 for read_mode in ['gate','oserror']:
  for finish_mode in ['real','false','gate','oserror']:
   p,c,ex=setup(f'final_read_{settled}_{read_mode}_{finish_mode}');h=Handle(820001);add(ex,h);h.code=0
   if settled:ex.counter.finish(0,state='STOPPED',exit_code=0,spent=1,pid=h.pid,birth=None)
   def unreadable(index,_mode=read_mode):
    if _mode=='gate':raise E.CpuGateError('INJECTED_READ')
    raise OSError('INJECTED_READ_IO')
   ex.counter.charge_state=unreadable
   if finish_mode!='real':ex.counter.finish=failure(finish_mode)
   f=final(p,ex)
   save(f'final_read_{settled}_{read_mode}_{finish_mode}',{'final':f,'counter':json.loads(c.read_text())})
print('DIAGNOSTICS_CAPTURED',len(RESULTS))
