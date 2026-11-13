"""The failure matrix of the sequential slot correction, round two.

Zero process.  No real child, no network, no machine binding, no fixture,
no model, no service and no original ledger: every counter of this probe is
a synthetic file of this directory and every child is a fake handle.

The oracles of this probe are the **converted** oracles of the independent
review of the first round
(``sequential-correction-review-01/received/negative_probes.py`` and
``idempotency_deadline_probes.py``).  The review reproduced the defects of
the candidate and its exit code zero meant "the defect was reproduced",
never "the candidate is correct".  Here the same triggers are kept and
the expectation is inverted:

* a settlement that the counter refuses (``False``), that fails with a
  gate error, that fails with an I/O error, and a terminal state that
  cannot be read, keep the slot of the child, make the current admission
  fail closed and keep the owned root with a non zero exit code.  The
  refusal is the explicit settlement failure; it is never the concurrency
  limit of a full counter that would hide the root cause.
* a persisted exit code, handle or charge index of another run is never
  an idempotent success: the admission fails closed and the root is kept.
* a reconciliation that crosses the fixed admission deadline refuses the
  start before the new charge is taken.
* the normal order of thirteen children, the legitimate repeated
  settlement, the live child and the unprovable child keep their
  behaviour.

The exit code of this probe is zero when every converted oracle held.
"""
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
exec(compile((OUT / 'outer_boundary.py').read_bytes(),
             str(OUT / 'outer_boundary.py'), 'exec'))
PACK = OUT.parents[3]
sys.path.insert(0, str(PACK))
import json  # noqa: E402
import os  # noqa: E402
import importlib.util  # noqa: E402

spec = importlib.util.spec_from_file_location(
    'round_two_helpers', PACK / 'tools/test_v0_s3_supervisor.py')
T = importlib.util.module_from_spec(spec)
spec.loader.exec_module(T)
E = T.EXECUTOR_MODULE
R = T.RUNNER_MODULE
R.install_offline_guard()

RESULTS = []
VIOLATIONS = []
LAST_DETAIL = None


class Handle:
    """A fake child handle: no process, only the calls of a handle."""

    def __init__(self, pid, code=None):
        self.pid = pid
        self.code = code
        self.bad = False
        self.stops = 0

    def poll(self):
        if self.bad:
            raise OSError('exit unavailable')
        return self.code

    def wait(self, timeout=None):
        return self.poll()

    def terminate(self):
        self.stops += 1
        self.code = -15

    def kill(self):
        self.stops += 1
        self.code = -9


class Log:
    def flush(self):
        pass

    def close(self):
        pass


def setup(name):
    """A synthetic counter, a synthetic binding and a real executor."""
    path = OUT / 'synthetic' / name
    path.mkdir(parents=True, exist_ok=True)
    counter = T.fake_root_counter(path)
    _, digest, _ = T.fake_root_binding(path, counter_path=counter)
    executor = T.build_test_executor(path, counter_path=counter, binding_digest=digest)
    T.context_inside(path)
    return path, counter, executor


def admit(executor):
    prefix = T.executor_prefix()
    return executor.admit((prefix[0], prefix + ['clean_terminal'], None, None))


def add(executor, handle):
    admit(executor)
    return executor.register(handle)


def attempt(executor):
    """One admission, observed as a string."""
    global LAST_DETAIL
    try:
        admit(executor)
        LAST_DETAIL = None
        return 'ADMITTED'
    except Exception as error:  # noqa: BLE001 - the refusal is the observation
        LAST_DETAIL = getattr(error, 'detail', None)
        return type(error).__name__ + ':' + str(error)


def final(path, executor):
    """The outer finalizer of the accepted runner on a synthetic root."""
    owned = path / 'owned'
    owned.mkdir(exist_ok=True)
    outcome = R.finalize_session(
        executor=executor, owned=owned, stdout_handle=Log(), stderr_handle=Log(),
        saved_out=os.dup(1), saved_err=os.dup(2), source_hasher=lambda: {})
    return {'exit_code': outcome['exit_code'],
            'cleanup_proven': outcome['cleanup_proven'],
            'root_retained': owned.exists(),
            'failure_reasons': outcome['failure_reasons'],
            'proofs': outcome['proofs']}


def save(name, trigger, expected, actual, held, **extra):
    entry = {'name': name, 'trigger': trigger, 'expected': expected,
             'actual': actual, 'oracle': 'HELD' if held else 'VIOLATED'}
    entry.update(extra)
    RESULTS.append(entry)
    if not held:
        VIOLATIONS.append(name)
    print(json.dumps(entry, sort_keys=True), flush=True)


def refusal_of(text):
    """The refusal code of an observed admission, if it is a refusal."""
    return text.split(':', 1)[1] if ':' in text else text


# --------------------------------------------------------------------------
# M1: every documented failure of the settlement of the counter.
#
# The trigger of every case is kept from the review: the child has already
# exited, its original handle proves it, and the settlement of its charge
# fails in one documented way.  One case has one exited child and one free
# slot, the other case has two exited children and a full counter.  The
# refusal of the second case may never be the concurrency limit of the
# full counter: that would hide the root cause behind a false pass.
# --------------------------------------------------------------------------
for count in (1, 2):
    for kind in ('false', 'gate', 'oserror', 'read_gate', 'read_oserror'):
        name = 'settlement_failure_%s_capacity%d' % (kind, count)
        path, counter, executor = setup(name)
        for number in range(count):
            add(executor, Handle(710000 + number))
        for entry in executor.children:
            entry['process'].code = 0
        if kind == 'false':
            executor.counter.finish = lambda index, **keywords: False
        elif kind == 'gate':
            def refuse_gate(index, **keywords):
                raise E.CpuGateError('INJECTED_FINISH')
            executor.counter.finish = refuse_gate
        elif kind == 'oserror':
            def refuse_io(index, **keywords):
                raise OSError('INJECTED_FINISH_IO')
            executor.counter.finish = refuse_io
        else:
            # The settlement is refused and the persisted terminal state
            # cannot be read either.
            executor.counter.finish = lambda index, **keywords: False

            def refuse_read(index, kind=kind):
                if kind == 'read_gate':
                    raise E.CpuGateError('INJECTED_READ')
                raise OSError('INJECTED_READ_IO')
            executor.counter.charge_state = refuse_read
        before = json.loads(counter.read_text())
        actual = attempt(executor)
        after = json.loads(counter.read_text())
        outcome = final(path, executor)
        code = refusal_of(actual)
        held = (actual != 'ADMITTED'
                and after['starts_total'] == before['starts_total']
                and code == 'CPU_RECONCILIATION_UNSETTLED'
                and code != 'CPU_CONCURRENCY_LIMIT'
                and executor.uncertain is True
                and not outcome['cleanup_proven']
                and outcome['root_retained']
                and outcome['exit_code'] != 0)
        save(name,
             trigger='%d exited child(ren), the settlement of the charge fails with %s'
                     % (count, kind),
             expected='no new charge, the explicit settlement failure refuses the '
                      'admission, the slot is kept, the root is kept and the exit '
                      'code is not zero',
             actual=actual, held=held,
             starts_before=before['starts_total'], starts_after=after['starts_total'],
             occupied_after=after and E.SharedCounter._occupied(after),
             refusal_code=code,
             refusal_detail=LAST_DETAIL,
             uncertain_after_attempt=executor.uncertain,
             settlement_error=[record.get('settlement_error')
                               for record in executor.charge_ledger()],
             final=outcome)

# --------------------------------------------------------------------------
# M2: the persisted proof of a terminal state.
#
# The trigger is kept from the review and the pending charge of the review
# is removed: the newly admitted charge always receives its own original
# handle, so no pending admission can mask the conflict.  A conflicting
# record is never an idempotent success.
# --------------------------------------------------------------------------
for mode in ('wrong_exit', 'wrong_pid_birth', 'foreign_index', 'unknown_terminal'):
    name = 'idempotency_conflict_%s' % mode
    path, counter, executor = setup(name)
    child = Handle(760001)
    add(executor, child)
    child.code = 0
    if mode == 'foreign_index':
        original_finish = executor.counter.finish
        executor.counter.finish = (lambda index, **keywords:
                                   False if index == 0
                                   else original_finish(index, **keywords))
        original_read = executor.counter.charge_state
        executor.counter.charge_state = (
            lambda index: {'index': 53, 'role': 'implementation',
                           'scenario': 'clean_terminal', 'argv': [], 'settled': True,
                           'state': 'STOPPED', 'exit_code': 77, 'pid': 333333,
                           'birth': {'foreign': 'session'}}
            if index == 0 else original_read(index))
    else:
        executor.counter.finish(
            0, state='UNKNOWN' if mode == 'unknown_terminal' else 'STOPPED',
            exit_code=77 if mode == 'wrong_exit' else 0, spent=1.0,
            pid=333333 if mode == 'wrong_pid_birth' else child.pid,
            birth={'foreign': 'session'} if mode == 'wrong_pid_birth' else None)
    before = json.loads(counter.read_text())['charges'][0]
    following = Handle(760002)
    actual = attempt(executor)
    if actual == 'ADMITTED':
        executor.register(following)
        following.code = 0
    outcome = final(path, executor)
    after = json.loads(counter.read_text())['charges'][0]
    held = (actual != 'ADMITTED'
            and not outcome['cleanup_proven']
            and outcome['root_retained']
            and outcome['exit_code'] != 0)
    save(name,
         trigger='the counter holds a terminal record of the same index that %s'
                 % mode.replace('_', ' '),
         expected='the conflict is not an idempotent success: the admission fails '
                  'closed, the charge stays open and the root is kept',
         actual=actual, held=held,
         refusal_code=refusal_of(actual),
         refusal_detail=LAST_DETAIL,
         first_charge_before=before, first_charge_after=after,
         finished_wall_unchanged=before['finished_wall'] == after['finished_wall'],
         final=outcome)

# --------------------------------------------------------------------------
# M3: the reconciliation crosses the fixed admission deadline.
#
# The trigger is kept from the review: the finite I/O latency of the newly
# inserted reconciliation moves the monotonic clock one millisecond past
# the deadline that was already bound before the reconciliation.
# --------------------------------------------------------------------------
path, counter, executor = setup('reconciliation_crosses_deadline')
child = Handle(770001)
add(executor, child)
child.code = 0
original_finish = executor.counter.finish
deadline = executor.admission_deadline
now = [executor.clock()]
executor.clock = lambda: now[0]


def delayed_finish(index, **keywords):
    result = original_finish(index, **keywords)
    now[0] = deadline + 0.001
    return result


executor.counter.finish = delayed_finish
before = json.loads(counter.read_text())['starts_total']
actual = attempt(executor)
after = json.loads(counter.read_text())['starts_total']
held = (actual != 'ADMITTED' and after == before
        and refusal_of(actual) == 'SESSION_ADMISSION_WINDOW_CLOSED'
        and executor.admission_deadline == deadline)
save('reconciliation_crosses_deadline',
     trigger='the I/O of the reconciliation moves the clock to the deadline + 0.001',
     expected='the start is refused before the new charge and the deadline is '
              'never rebased',
     actual=actual, held=held,
     refusal_code=refusal_of(actual),
     clock=executor.clock(), admission_deadline=deadline,
     starts_before=before, starts_after=after,
     next_attempt=attempt(executor))

# --------------------------------------------------------------------------
# The normal behaviour that must not change.
# --------------------------------------------------------------------------
path, counter, executor = setup('live_children')
first = Handle(720001)
second = Handle(720002)
add(executor, first)
add(executor, second)
third = attempt(executor)
first.code = 0
fourth = attempt(executor)
fifth = attempt(executor)
held = ('CPU_CONCURRENCY_LIMIT' in third and fourth == 'ADMITTED'
        and 'CPU_CONCURRENCY_LIMIT' in fifth)
save('live_children',
     trigger='two live children and then one exited child',
     expected='the two live children keep their slots and exactly one slot is '
              'released',
     actual={'third': third, 'after_one_exit': fourth, 'one_more': fifth},
     held=held, counter=json.loads(counter.read_text()))

path, counter, executor = setup('unprovable_child')
unprovable = Handle(720003)
unprovable.bad = True
add(executor, unprovable)
actual = attempt(executor)
one_more = attempt(executor)
document = json.loads(counter.read_text())
held = (document['charges'][0]['state'] == 'STARTED'
        and document['charges'][0]['settled'] is False
        and 'CPU_CONCURRENCY_LIMIT' in one_more)
save('unprovable_child',
     trigger='the exit of the child can never be observed',
     expected='the slot of the child is kept: the first start still fits into '
              'the free slot of the counter and the next one is refused',
     actual={'next': actual, 'one_more': one_more}, held=held,
     first_charge=document['charges'][0])

path, counter, executor = setup('sequential13')
peak = 0
for number in range(13):
    child = Handle(730000 + number)
    add(executor, child)
    child.code = 0
    peak = max(peak, E.SharedCounter._occupied(json.loads(counter.read_text())))
pre = json.loads(counter.read_text())
outcome = final(path, executor)
post = json.loads(counter.read_text())
held = (post['starts_total'] == 13 and len(post['charges']) == 13 and peak <= 2
        and outcome['cleanup_proven'] is True
        and pre['charges'][0]['finished_wall'] == post['charges'][0]['finished_wall']
        and executor.revoked is True
        and all(child['process'].stops == 0 for child in executor.children))
save('sequential13',
     trigger='thirteen sequential children that exit before the next admission',
     expected='thirteen starts, a peak of one occupied slot, one cleanup at the '
              'end and no rewritten finished_wall',
     actual={'starts': post['starts_total'], 'peak': peak, 'final': outcome,
             'first_finished_wall_unchanged':
                 pre['charges'][0]['finished_wall'] == post['charges'][0]['finished_wall'],
             'reserved': post['reserved_wall_seconds']},
     held=held)

path, counter, executor = setup('legitimate_repeat')
child = Handle(780001)
add(executor, child)
child.code = 0
outcome_of_reconcile = executor.reconcile_exited_children()
before = json.loads(counter.read_text())['charges'][0]
executor.reap()
after = json.loads(counter.read_text())['charges'][0]
document = json.loads(counter.read_text())
held = (outcome_of_reconcile['failures'] == []
        and len(outcome_of_reconcile['released']) == 1
        and before['finished_wall'] == after['finished_wall']
        and before['observed_lifetime_seconds'] == after['observed_lifetime_seconds']
        and after['settled'] is True
        and document['starts_total'] == 1 and len(document['charges']) == 1
        and executor.uncertain is False
        and executor.unsettled_charges() == [])
save('legitimate_repeat',
     trigger='a child that was already reconciled is reaped again',
     expected='the repeated settlement is idempotent: the finished_wall is not '
              'rewritten, the charge is not settled twice, nothing is refunded '
              'and the cleanup stays uncertain free',
     actual={'before': before, 'after': after,
             'reconciliation': outcome_of_reconcile,
             'starts_total': document['starts_total'],
             'charges': len(document['charges']),
             'unsettled': executor.unsettled_charges()},
     held=held)

(OUT / 'sequential-correction-02-negative-results.json').write_text(
    json.dumps(RESULTS, indent=2, sort_keys=True) + '\n')
print('MATRIX_CAPTURED', len(RESULTS), 'VIOLATIONS', len(VIOLATIONS))
if VIOLATIONS:
    print('VIOLATED_ORACLES', json.dumps(VIOLATIONS))
    sys.exit(1)
print('ALL_CONVERTED_ORACLES_HELD')
sys.exit(0)
