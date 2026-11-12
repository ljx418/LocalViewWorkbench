"""Bounded independent resource observations; executed only by preimport guarded runner."""
import errno, hashlib, json, os, shutil, stat, tempfile
from pathlib import Path
from tools import test_v0_s3_quality_phase as t
from tools import v0_s3_quality_phase as q
OUT = Path(__file__).resolve().parent
ROOT = Path(tempfile.mkdtemp(prefix='lvw-independent-c08-'))
RESULTS = []
VIOLATIONS = []
def fdcount(): return len(os.listdir('/proc/self/fd'))
def alive(fd):
    try: os.fstat(fd); return True
    except OSError: return False
def check(name, result, conditions):
    bad = [k for k,v in conditions.items() if not v]
    RESULTS.append({'name':name, **result, 'checks': conditions, 'violations':bad})
    VIOLATIONS.extend(name+':'+k for k in bad)
class RejectDict(dict):
    def __setitem__(self,k,v): raise OSError(errno.EIO,'independent insertion refusal')
class RejectList(list):
    def append(self,v): raise OSError(errno.EIO,'independent transfer refusal')
class Hooks:
    def __init__(self, target, fault):
        self.target, self.fault = target, fault
        self.orig = {n:getattr(os,n) for n in ('open','fstat','stat','close')}
        self.fd = None; self.fired = 0; self.opened = []; self.closed = []; self.high = fdcount()
    def fire(self): self.fired += 1; raise OSError(errno.EIO,'independent '+self.fault)
    def open(self,path,flags,*a,**kw):
        match = self.target(path, len(self.opened)+1)
        if match and self.fault == 'open' and not self.fired: self.fire()
        fd = self.orig['open'](path,flags,*a,**kw)
        self.opened.append({'fd':fd,'path':str(path)})
        self.high = max(self.high,fdcount())
        if match and self.fd is None: self.fd=fd
        return fd
    def fstat(self,fd):
        if fd == self.fd and self.fault == 'fstat' and not self.fired: self.fire()
        return self.orig['fstat'](fd)
    def stat(self,path,*a,**kw):
        if self.fd is not None and self.target(path,0) and not self.fired:
            if self.fault == 'stat': self.fire()
            info=self.orig['stat'](path,*a,**kw)
            if self.fault in ('type','identity'):
                self.fired += 1; fields=list(info)
                if self.fault == 'type': fields[0] = stat.S_IFLNK | 0o777
                else: fields[1] += 1
                return os.stat_result(fields)
        return self.orig['stat'](path,*a,**kw)
    def close(self,fd):
        self.closed.append(fd)
        return self.orig['close'](fd)
    def __enter__(self):
        for n in self.orig: setattr(os,n,getattr(self,n))
        return self
    def __exit__(self,*args):
        for n,v in self.orig.items(): setattr(os,n,v)
try:
    run=t._own_run(ROOT, clock=t.FakeClock(step=0.0))
    root=run['artifact_root']
    (root/'probe-file').write_bytes(b'abcd')
    (root/'keep').write_bytes(b'abcd')
    (root/'probe-dir').mkdir(); (root/'probe-dir'/'x').write_bytes(b'abcd')
    # Each fault occurs with an existing entry already retained. No probe closes a product FD.
    for kind in ('leaf','directory'):
        target='probe-file' if kind=='leaf' else 'probe-dir'
        relative=target if kind=='leaf' else target+'/x'
        for fault in ('open','fstat','stat','type','identity','insert','transfer'):
            before=fdcount(); b=q._ArtifactBoundary(root); b.read('keep',4)
            original_entries=b._custody.entries(); during=fdcount()
            if fault=='insert': b._custody._entries=RejectDict(b._custody._entries)
            if fault=='transfer': b._custody._fds=RejectList(b._custody._fds)
            h=Hooks(lambda p,n: str(p)==target, fault)
            with h:
                refused=None
                try: b.read(relative,4)
                except Exception as e: refused=type(e).__name__+':'+str(e)
                after_refusal=fdcount(); target_live=h.fd is not None and alive(h.fd)
                old_ok=b._custody.entries()==original_entries
                reserved=b._custody.reserved(); b.verify()
                target_closes=h.closed.count(h.fd) if h.fd is not None else 0
            # Retry after restoring the fault container confirms capacity rollback and preserved earlier custody.
            b._custody._entries=dict(b._custody._entries); b._custody._fds=list(b._custody._fds)
            retry=b.read(relative,4)==b'abcd'; b.verify()
            with Hooks(lambda p,n:False,'none') as closer: b.close()
            after_close=fdcount()
            # Force a descriptor number reuse after close; idempotent boundary.close must not close it.
            sentinel=os.open(str(root/'keep'),os.O_RDONLY)
            b.close(); sentinel_live=alive(sentinel); os.close(sentinel)
            check(kind+'_'+fault, {'refused':refused,'hook_fired':h.fired,'opened':h.opened,
                'target_fd':h.fd,'target_close_calls_before_retry':target_closes,
                'target_live_after_refusal':target_live,'fds':[before,during,after_refusal,after_close],
                'reserved_after_refusal':reserved, 'final_close_calls':closer.closed},
                {'refused':refused is not None,'fault_reached':h.fired==1 if fault in ('open','fstat','stat','type','identity') else h.fd is not None,
                 'target_closed_once':target_closes==(0 if fault=='open' else 1),
                 'no_live_target_after_refusal':not target_live,'no_fd_growth':after_refusal==during,
                 'prior_entries_preserved':old_ok,'reservation_released':reserved==0,
                 'retry_admitted':retry,'close_baseline':after_close==before,
                 'no_duplicate_final_close':len(closer.closed)==len(set(closer.closed)),
                 'reused_fd_survives_idempotent_close':sentinel_live})
    # Constructor partial acquisition: first open failure and first fstat at each acquired level.
    for fault,ordinal in [('open',1),('open',2),('open',3),('open',4),('fstat',2),('fstat',3),('fstat',4)]:
        before=fdcount(); h=Hooks(lambda p,n:n==ordinal,fault)
        with h:
            refused=None
            try: q._ArtifactBoundary(root)
            except Exception as e: refused=type(e).__name__+':'+str(e)
            after=fdcount(); live=[x['fd'] for x in h.opened if alive(x['fd'])]
        check('constructor_'+fault+'_'+str(ordinal), {'refused':refused,'hook_fired':h.fired,'opened':h.opened,'closed':h.closed,'live_after':live,'fds':[before,after]},
              {'fault_once':h.fired==1,'refused':refused is not None,'baseline':after==before,'no_live_opened':not live,
               'one_close_each':sorted(h.closed)==sorted(x['fd'] for x in h.opened)})
    # Public QS reaches the same exact faults for a canonical leaf and a raw child directory.
    for kind,target in [('leaf',q.CANONICAL_RECEIPT_NAME),('directory',Path(run['receipt']['rows'][0]['raw_artifact']).parts[-2])]:
        before=fdcount(); h=Hooks(lambda p,n:str(p)==target,'fstat')
        with h:
            refused=None; result=None
            try: result=q.recompute_scores(run['receipt'],root,t._own_scores(run),independence=t._independence())
            except Exception as e: refused=type(e).__name__+':'+str(e)
            after=fdcount(); live=[x['fd'] for x in h.opened if alive(x['fd'])]
        check('public_'+kind+'_postopen_fstat',{'refused':refused,'result':result,'target':target,'hook_fired':h.fired,
              'opened':h.opened,'closed':h.closed,'live_after':live,'fds':[before,after]},
              {'exact_fault_once':h.fired==1,'scores_refused':result is None and refused is not None,
               'all_closed_once':sorted(h.closed)==sorted(x['fd'] for x in h.opened),'no_live_fds':not live,'baseline':after==before})
    # Exact internal cap, dedup miss refusal, and all 72 names reused and verified.
    before=fdcount(); b=q._ArtifactBoundary(root)
    names=['independent-cap-%02d'%i for i in range(73)]
    for name in names: (root/name).write_bytes(b'abcd')
    with Hooks(lambda p,n:False,'none') as h:
        for name in names[:72]: assert b.read(name,4)==b'abcd'
        entries=b._custody.entries(); at=fdcount(); opens=len(h.opened); high=h.high
        refused=None
        try: b.read(names[72],4)
        except Exception as e: refused=type(e).__name__+':'+str(e)
        after_excess=fdcount(); excess_opens=len(h.opened)-opens; excess_high=h.high
        for name in names[:72]: assert b.read(name,4)==b'abcd'
        b.verify(); retained=b._custody.entries()==entries; repeats=len(h.opened)-opens
        count=b._custody.count(); reservations=b._custody.reserved(); b.close(); after_close=fdcount()
    check('exact72_excess73_repeat72',{'limit':q._CUSTODY_ENTRY_LIMIT,'count':count,'refused':refused,'opens':opens,
         'extra_opens':excess_opens,'repeat_opens':repeats,'fds':[before,at,after_excess,after_close],
         'high_before_excess':high,'high_after_excess':excess_high},
         {'exact72':count==72 and opens==72,'excess_refused':refused is not None,'zero_extra_open':excess_opens==0,
          'zero_transient_growth':high==excess_high and at==after_excess,'all_prior_retained':retained,
          'repeat_opens_nothing':repeats==0,'no_pending_reservation':reservations==0,'close_baseline':after_close==before})
    # Full genuine 16 evaluation uses 35 distinct entries under 72, including public scoring success.
    before=fdcount(); observed={}; original_close=q._ArtifactBoundary.close
    def observe_close(self):
        observed['entries']=self._custody.count(); observed['reserved']=self._custody.reserved()
        observed['parent_refs_owned']=all(e['parent_fd'] in self._fds+[x['fd'] for x in self._custody.entries()] for e in self._custody.entries())
        observed['fds_at_close']=fdcount(); return original_close(self)
    q._ArtifactBoundary.close=observe_close
    try: result=q.recompute_scores(run['receipt'],root,t._own_scores(run),independence=t._independence())
    finally: q._ArtifactBoundary.close=original_close
    after=fdcount()
    check('genuine_full16_public_success',{'result':result, 'observed':observed,'fds':[before,after]},
          {'aggregates':result['aggregate_pass'] is True,'35_entries':observed['entries']==35,
           'under_internal72':observed['entries']<q._CUSTODY_ENTRY_LIMIT,'no_reservation':observed['reserved']==0,
           'no_stale_parent':observed['parent_refs_owned'],'close_baseline':after==before})
finally:
    shutil.rmtree(ROOT,ignore_errors=True)
payload={'kind':'INDEPENDENT_BOUNDED_RESOURCE_OBSERVATIONS','count':len(RESULTS),'observations':RESULTS,
         'violations':VIOLATIONS,'registered_roots':[str(ROOT)],'owned_root_removed':not ROOT.exists(),
         'probe_fd_remediation':False,'product_tests':False,'stage_pass_claim':False,'product_gate0':False}
(OUT/'targeted-observations.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
print(json.dumps(payload,indent=2,sort_keys=True))
raise SystemExit(1 if VIOLATIONS else 0)
