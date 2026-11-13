from pathlib import Path
OUT=Path(__file__).resolve().parent
source=(OUT/'negative_probes.py').read_text()
exec(compile(source.split('# Persistence failures at partial')[0],str(OUT/'negative_probes.py'),'exec'))
# No pending admission can mask final cleanup: the newly admitted charge
# always receives its original stub handle, which subsequently exits.
for mode in ['wrong_exit','wrong_pid_birth','foreign_index','unknown_terminal']:
 p,c,ex=setup('unmasked_'+mode);h=Handle(760001);add(ex,h);h.code=0
 if mode=='foreign_index':
  original=ex.counter.finish
  ex.counter.finish=lambda index,**kw:False if index==0 else original(index,**kw)
  original_read=ex.counter.charge_state
  ex.counter.charge_state=lambda index:{'index':53,'settled':True,'state':'STOPPED','pid':333333,'birth':{'foreign':'session'},'exit_code':77} if index==0 else original_read(index)
 else:
  ex.counter.finish(0,state='UNKNOWN' if mode=='unknown_terminal' else 'STOPPED',exit_code=77 if mode=='wrong_exit' else 0,spent=1,pid=333333 if mode=='wrong_pid_birth' else h.pid,birth={'foreign':'session'} if mode=='wrong_pid_birth' else None)
 before=json.loads(c.read_text())['charges'][0]
 nxt=Handle(760002);a=attempt(ex)
 if a=='ADMITTED':ex.register(nxt);nxt.code=0
 f=final(p,ex);after=json.loads(c.read_text())['charges'][0]
 save('unmasked_'+mode,{'actual_admit':a,'first_charge_before':before,'first_charge_after':after,'finished_wall_unchanged':before['finished_wall']==after['finished_wall'],'final':f})
 if mode!='unknown_terminal':assert f['cleanup_proven'] and f['exit_code']==0 and not f['root_retained']
 else:assert not f['cleanup_proven'] and f['root_retained']

# Finite I/O latency during the newly inserted reconciliation crosses the
# already bound admission deadline. The original check was before this I/O.
p,c,ex=setup('reconciliation_crosses_deadline');h=Handle(770001);add(ex,h);h.code=0
original=ex.counter.finish;deadline=ex.admission_deadline
now=[ex.clock()];ex.clock=lambda:now[0]
def delayed_finish(index,**kw):
 result=original(index,**kw);now[0]=deadline+0.001;return result
ex.counter.finish=delayed_finish
before=json.loads(c.read_text())['starts_total'];a=attempt(ex);after=json.loads(c.read_text())['starts_total']
save('reconciliation_crosses_deadline',{'expected':'refuse after reconciliation crosses fixed deadline','actual':a,'clock':ex.clock(),'admission_deadline':deadline,'starts_before':before,'starts_after':after,'next_attempt':attempt(ex)})
assert a=='ADMITTED' and after==before+1
(OUT/'idempotency-deadline-results.json').write_text(json.dumps(RESULTS,indent=2))
print('SUPPLEMENTAL_CAPTURED',len(RESULTS))
