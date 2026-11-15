"""The frozen regressions of the N1 correction 10 of the native custody.

This module carries the **14 frozen oracle groups** of the root package
``reports/v0-s3/product-gate0/native-custody-correction-10`` (the file
``regression-obligations.json``).  The obligations are frozen by the
root and they are not written by the implementer: every group below is
mapped to the production owner that has to carry it and to the test
that drives it.

The rules of this module are the rules of the whole N1 package.

* It is **offline**.  It never starts a process, it never opens a
  socket, it never touches a database and it never reads the original
  budget ledger or the original shared counter.  The Windows primitives
  are driven through an **in-process** table of primitives that is
  injected into the production façade: the production code that is
  checked here is the code of a real run, only the native library is
  missing.  The only seam that is injected is the **lowest** one: the
  primitive table of the façade of the Windows API, the file objects
  of the ends of the channel and the frame of the peer.  The public
  production owners - the core, the loop, the channel, the endpoints,
  the workers, the session, the launcher and the custody of the
  launcher - are the real ones.

* Every case drives the **actual production method**: the production
  ``WindowsApi`` with an injected primitive table, the production
  ``BrokerCore``, ``BrokerLoop``, ``BrokerProcess``, ``StreamChannel``,
  ``_WindowsPipeWorker``, ``_WindowsPipeEndpoint``, ``_StartupOwner``,
  ``_LauncherCustody``, ``_LaunchAggregate`` and the production
  ``NativeCustodySession``.  A façade that only returns the right story
  would not prove anything and it is not used for the failure paths.

* Every case records the state of the resources **at the moment the
  product returned**, before any salvage of the test owner.  The
  cleanup of the test owner is explicit and it is never used to
  declare that the product returned cleanly: a product that could not
  release a resource stays unknown and keeps its original reference.
  Every thread that the test itself started is joined by the test with
  a **bounded** wait, in every case and unconditionally.

* The native claims of this package stay ``NOT_PROVEN``.  The module
  proves the behaviour of the Python owners and it never claims that a
  Windows API, a job object, a GPU, a port or a service was executed.

The six Majors of the read only pre review stay **OPEN**: this module
is a regression set and it never signs a Major.  The closure of a
Major belongs to a new independent review and to the gate owner.

The boundary of the process is not installed here: the guard of the
batch lives in the report directory of the batch and the runner of the
batch is its only authorised entry.
"""
import ast
import hashlib
import json
import os
import queue
import subprocess
import sys
import threading
import time
import unittest.mock
from pathlib import Path

import pytest

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

import tools.v0_s3_native_broker as broker_module  # noqa: E402 - the path is set above
from tools.v0_s3_native_broker import (  # noqa: E402 - the path is set above
    BrokerCore, BrokerError, BrokerLoop, BrokerProcess, StreamChannel,
    WindowsApi, _ChannelCancel, _LauncherCustody, _LaunchAggregate,
    _RoundContext, _StartupOwner, _WindowsPipeEndpoint, _WindowsPipeWorker,
    _adopt_broker_process, _launcher_custody_items, release_retained_launches)
import tools.v0_s3_native_custody as custody_module  # noqa: E402 - the path is set above
from tools.v0_s3_native_custody import (  # noqa: E402 - the path is set above
    CHANNEL_POLL_SECONDS, CHANNEL_SCHEMA, CustodyError, NativeCustodySession,
    validate_launch_plan)
from tools.test_v0_s3_native_custody_correction07 import (  # noqa: E402
    _FakeFile, _F5Api, _F5ExternalCancelOwner, _f5_build_chain, _reply_bytes)
from tools.test_v0_s3_native_custody_regressions import (  # noqa: E402
    ManualClock, RecordingWin32, SyntheticKernel32, m07a_interrupted_launch,
    plan_document, sealed_plan, structure_of, synthetic_table)


#: The directory in which the bounded facts of this module are written.
#: Every document is written **before** the assertions of its phase and
#: every value of it is a value that the production returned.
#:
#: CORRECTION 11: the diagnostics of this module are written in the NEW
#: directory of the correction 11.  The real documents of the failed
#: batch of the correction 10 stay in the directory of the correction
#: 10: they are never overwritten, never deleted and never replaced by
#: a summary.
#: CORRECTION 12: the diagnostics of this module are written in the NEW
#: directory of the correction 12.  The real documents of the failed
#: batch of the correction 11 stay in the directory of the correction
#: 11: they are never overwritten, never deleted and never replaced by
#: a summary.
#: CORRECTION 13: the diagnostics of this module are written in the NEW
#: directory of the correction 13.  The real documents of the failed
#: batch of the correction 12 stay in the directory of the correction
#: 12: they are never overwritten, never deleted and never replaced by
#: a summary.
#: CORRECTION 14: the diagnostics of this module are written in the NEW
#: directory of the correction 14.  The real documents of the failed
#: batch of the correction 13 stay in the directory of the correction
#: 13: they are never overwritten, never deleted and never replaced by
#: a summary.
#: CORRECTION 15: the diagnostics of this module are written in the NEW
#: directory of the correction 15.  The real documents of the batch of
#: the correction 14 stay in the directory of the correction 14: they
#: are never overwritten, never deleted and never replaced by a
#: summary.
#: CORRECTION 16: the diagnostics of this module are written in the NEW
#: directory of the correction 16.  The real documents of the batch of
#: the correction 15 stay in the directory of the correction 15: they
#: are never overwritten, never deleted and never replaced by a
#: summary.
#: CORRECTION 17: the diagnostics of this module are written in the NEW
#: directory of the correction 17.  The real documents of the batch of the
#: correction 16 stay in the directory of the correction 16: they are
#: never overwritten, never deleted and never replaced by a summary.
#: CORRECTION 18: the diagnostics of this module are written in the NEW
#: directory of the correction 18.  The real documents of the batch of the
#: correction 17 stay in the directory of the correction 17: they are
#: never overwritten, never deleted and never replaced by a summary.
#: CORRECTION 19: the diagnostics of this module are written in the NEW
#: directory of the correction 19.  The real documents of the batch of the
#: correction 18 stay in the directory of the correction 18: they are
#: never overwritten, never deleted and never replaced by a summary.
#: CORRECTION 20: the diagnostics of this module are written in the NEW
#: directory of the correction 20.  The real documents of the batch of the
#: correction 19 stay in the directory of the correction 19: they are
#: never overwritten, never deleted and never replaced by a summary.
#: CORRECTION 22: the diagnostics of this module are written in the NEW
#: directory of the correction 22.  The real documents of the batch of the
#: correction 21 stay in the directory of the correction 21: they are
#: never overwritten, never deleted and never replaced by a summary.
#: CORRECTION 23: the diagnostics of this module are written in the NEW
#: directory of the correction 23.  The real documents of the batch of the
#: correction 22 stay in the directory of the correction 22: they are
#: never overwritten, never deleted and never replaced by a summary.
#: OPT-B: the evidence root of this module is **bound to the run** by the
#: environment of the root-frozen plan.  The module never writes into a
#: spent evidence root any more and it **fails closed** when the
#: environment does not name a fresh one: one immutable source candidate
#: can be verified in an isolated targeted run and later in the full
#: checkpoint without an edit of the source that only moves the output.
_EVIDENCE_DIR_ENV = 'LVW_N1_T10_EVIDENCE_DIR'
_EVIDENCE_DIR_VALUE = os.environ.get(_EVIDENCE_DIR_ENV, '').strip()
if not _EVIDENCE_DIR_VALUE:
    raise RuntimeError(
        'the evidence root of this module is bound to the run: the '
        'environment %s does not name a fresh evidence root'
        % (_EVIDENCE_DIR_ENV,))
EVIDENCE_DIR = Path(_EVIDENCE_DIR_VALUE).expanduser()

#: The nonce of the private channel of the probes of this module.  It
#: is a closed form of 32 hexadecimal characters and it is the nonce of
#: the round of the probe: the frames of the probe carry it.
NONCE = '0' * 32

#: The two codes that the production may name for the cancellation of
#: the channel.  The code depends on the layer that observed the flag:
#: the read endpoint of the channel raises ``BROKER_PIPE_CANCELLED`` and
#: the wait of the channel between two reads raises
#: ``BROKER_CHANNEL_CANCELLED``.  A negative case that is about the
#: **origin** of the cancellation accepts the code that the real
#: observation layer produced and it never widens the set to hide any
#: other error.
CANCELLATION_CODES = ('BROKER_PIPE_CANCELLED', 'BROKER_CHANNEL_CANCELLED')

#: The bounded wait of the gate of the admission of the round of the zero
#: expiry and the bounded wait for the admission itself.  Every wait of
#: the fixture is bounded and every gate of the fixture is released
#: unconditionally: a gate that timed out is a **fact** that the group
#: records and it is never a silent success.
ZERO_GATE_SECONDS = 30.0
#: OPT-B-07 (F06-M1): the bound of the hold of the **producer** of the
#: round of the zero expiry.  It is a bound of the **fixture** and never
#: a deadline of the product: the deadline of the round is never
#: extended and no threshold of the production is changed.
ZERO_PRODUCER_SECONDS = 30.0
ZERO_ADMISSION_SECONDS = 15.0


def write_phase(phase, document):
    """Write the bounded facts of one phase of this module."""
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / ('n10-%s.json' % phase)
    path.write_text(json.dumps(document, indent=1, sort_keys=True,
                                default=repr), encoding='utf-8')
    return str(path)


def _live_plan_document():
    """A plan document whose lease is valid for the clock of the host."""
    return plan_document(lease_expires_at=time.time() + 3600.0)


def _chain(api, document, plan, tmp_path, *, clock=None):
    """Build the **real** chain of one round.

    The chain is the one of the production launcher: the frames of the
    round are published first, then the endpoints, then the channel and
    then the handle of the broker.  Nothing of the chain is replaced by
    a stand-in and the facts of the close are the facts of the
    production.

    The clock of the chain may be a clock that only moves when the
    owner of the test moves it: the deadline of the round is then a
    fact of the test and not a fact of the wall of the host.
    """
    return _f5_build_chain(api, document, plan, clock or time.monotonic,
                           time.time, tmp_path)


def write_phase_not_run(phase, reason):
    """Mark one phase that was **not** executed.

    A phase that did not run is never written as if it had run: the
    document names the reason of the failure and it carries **no** fact
    of the phase.  A document of a phase that never ran is never a
    fabricated expectation of the phase.
    """
    return write_phase(phase, {'status': 'NOT_RUN', 'reason': reason})


class _R07Sentinel(Exception):
    """The deliberate failure of the fixture of one round.

    It is a **test** sentinel and nothing else: it is raised on purpose
    at a checkpoint of the fixture of the round and it is caught again
    by the owner of the test.  It is never a broad ``Exception``, it
    never hides a real failure of the production and it is never used
    to swallow one.
    """


class _R07OrdinaryAssertion(AssertionError):
    """The deliberate **ordinary** assertion of the fixture of one round.

    It is a real ``AssertionError`` - the base of this class is the
    ``AssertionError`` of the test - and it carries a **token** that no
    other failure of the group carries.  The assertion of the group is
    really raised and really fails; the token is normalised so that the
    exact token of the failure survives the rewriting of the assertions
    of the test runner.  It is caught by **its own type** and never by a
    broad ``Exception``: an ordinary failure of the group that is not
    this one is never taken for it.
    """

    TOKEN = 'N10-R07-CONTROLLED-ORDINARY-ASSERTION'


class _R07ConstructorFailure(Exception):
    """The deliberate failure of the **construction** of a transport.

    It is raised by the seam of the fixture **after** the drain thread
    of the transport was really started: the local variable of the
    transport stays empty and the owner of the drain thread is the
    registry of the fixture.  It is a **test** exception and nothing
    else: it is never a broad ``Exception`` and it never hides a real
    failure of the production.
    """


class _OwnerRegistry:
    """The registry of the owners that the fixture of this module starts.

    The registry is **immediate**: an owner is registered at the moment
    of its construction or of its start and it is never discovered
    later from a product that may have dropped it.  A channel whose
    construction failed half way, a drain thread whose start took
    effect and a worker that the product retained are all in the
    registry, and the salvage of the fixture joins every one of them
    with an explicitly bounded wait.

    The registry owns **nothing**: it only remembers.  The product
    keeps its own owners and its own returned state, and the registry
    never claims that the product released a resource.

    CORRECTION 17 (M3): the registry also holds the **provenance** of
    every start that the observer of this module saw.  The provenance
    is the proof of the start of an owner: an owner whose start was
    never invoked is ``NEVER_STARTED``, an owner whose start did not
    return is ``UNKNOWN`` and an owner whose start returned is
    ``STARTED``.  The provenance is keyed by the **exact** thread
    object and it is never inferred from a name.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._entries = []
        self._sequence = 0
        self._threads = {}

    def register(self, name, owner, *, kind, seam):
        """Register one owner **immediately** and return its entry."""
        with self._lock:
            self._sequence += 1
            entry = {'name': name, 'owner': owner, 'kind': kind,
                     'seam': seam, 'order': self._sequence,
                     'registered_at': time.monotonic(),
                     'start_state': None, 'start_error': None}
            self._entries.append(entry)
            return entry

    def mark_starting(self, thread):
        """Register the **exact** thread object before its start.

        The registration happens **before** the original start is
        called: a thread whose start does not return is an owner of the
        round from that moment on and it is never forgotten.
        """
        with self._lock:
            self._sequence += 1
            entry = {'name': 'thread:%s#%d' % (thread.name, id(thread)),
                     'owner': thread, 'kind': 'thread',
                     'seam': 'thread.start', 'order': self._sequence,
                     'registered_at': time.monotonic(),
                     'start_state': 'STARTING', 'start_error': None}
            self._entries.append(entry)
            self._threads[id(thread)] = entry
            return entry

    def mark_started(self, thread):
        """The start of the thread returned: the owner really started."""
        with self._lock:
            entry = self._threads.get(id(thread))
            if entry is not None:
                entry['start_state'] = 'STARTED'
            return entry

    def mark_failed(self, thread, error):
        """The start of the thread did not return: the owner is unknown."""
        with self._lock:
            entry = self._threads.get(id(thread))
            if entry is not None:
                entry['start_state'] = 'FAILED'
                entry['start_error'] = {'type': type(error).__name__,
                                        'detail': str(error)}
            return entry

    def pending_starts(self):
        """The starts that did not return yet."""
        with self._lock:
            return sum(1 for item in self._entries
                       if item['kind'] == 'thread'
                       and item['start_state'] == 'STARTING')

    def start_provenance(self):
        """The proven provenance of every start that the observer saw."""
        with self._lock:
            return {id(item['owner']): item['start_state']
                    for item in self._entries if item['kind'] == 'thread'}

    def generation(self):
        """The number of the owners that the registry holds.

        The generation is the **witness** of the quiescence of the
        round: a generation that did not change across a final
        resnapshot means that no new owner appeared after it.
        """
        with self._lock:
            return len(self._entries)

    def entries(self):
        """The entries of the registry in the order of their registration."""
        with self._lock:
            return list(self._entries)

    def observed_threads(self):
        """The **exact** thread objects that this registry observed.

        CORRECTION 20 (M3): this view is **independent** of the query
        of ``entries``: a failure of that query never loses these
        references and the fallback of the drain of a round never
        starts from an empty list.
        """
        with self._lock:
            return [(item['name'], item['owner'])
                    for item in self._threads.values()]

    def facts(self):
        """The facts of the registry: an owner is named and never guessed."""
        return [{'name': item['name'], 'kind': item['kind'],
                 'seam': item['seam'], 'order': item['order'],
                 'start_state': item['start_state']}
                for item in self.entries()]


class _StartObserver:
    """The observer of the starts of the threads of one round.

    The observer is installed around the **original**
    ``threading.Thread.start``: it forwards every start and it never
    refuses one, it never blocks one and it never changes a decision of
    the production.  It only **observes** the start and it registers the
    **exact** thread object at the moment of the start, so that a
    thread that the product starts during the stop of the round is an
    owner of the round and it is never forgotten.

    The scope of the observer is the **actual** round that the fixture
    builds: the observer is armed before the round is started and it is
    disarmed only after the salvage of that round has finished.
    """

    def __init__(self, registry):
        self._registry = registry
        self._original = threading.Thread.start
        self.armed = False
        self.observed = []

    def install(self):
        """The context manager that installs the observer."""
        observer = self

        def observed_start(thread, *args, **kwargs):
            if not observer.armed:
                return observer._original(thread, *args, **kwargs)
            observer._registry.mark_starting(thread)
            try:
                result = observer._original(thread, *args, **kwargs)
            except BaseException as error:  # noqa: BLE001 - it stays visible
                observer._registry.mark_failed(thread, error)
                raise
            observer._registry.mark_started(thread)
            observer.observed.append({'id': id(thread), 'name': thread.name})
            return result

        return unittest.mock.patch.object(threading.Thread, 'start',
                                          observed_start)

    def arm(self):
        """The observation of the starts begins."""
        self.armed = True

    def disarm(self):
        """The observation of the starts ends."""
        self.armed = False


class _PhaseLedger:
    """The ledger of the phases that the group of this module runs.

    The ledger remembers what was **entered** and what **ended**.  It
    never decides: a phase that was entered and that failed is a
    ``FAIL`` and only a phase that was never entered is a ``NOT_RUN``.
    The states are ``PLANNED``, ``ATTEMPTED``, ``PASSED``, ``FAIL`` and
    ``NOT_RUN`` and the two last states are terminal.
    """

    STATES = ('PLANNED', 'ATTEMPTED', 'PASSED', 'FAIL', 'NOT_RUN')

    def __init__(self):
        self._lock = threading.Lock()
        self._states = {}
        self._order = []
        self._reasons = {}

    def _plan_locked(self, name):
        if name not in self._states:
            self._states[name] = 'PLANNED'
            self._order.append(name)

    def plan(self, name):
        """Name one phase **before** it runs."""
        with self._lock:
            self._plan_locked(name)
            return name

    def attempt(self, name):
        """Mark that the operation of the phase was **entered**."""
        with self._lock:
            self._plan_locked(name)
            if self._states[name] == 'PLANNED':
                self._states[name] = 'ATTEMPTED'
            return self._states[name]

    def finish(self, name, state, reason=None):
        """Close one phase; a closed phase is never reopened."""
        with self._lock:
            self._plan_locked(name)
            if self._states[name] in ('PASSED', 'FAIL', 'NOT_RUN'):
                return self._states[name]
            self._states[name] = state
            if reason is not None:
                self._reasons[name] = reason
            return state

    def pass_(self, name):
        """The phase held every one of its checks."""
        return self.finish(name, 'PASSED')

    def fail(self, name, reason=None):
        """The phase was executed and it failed."""
        return self.finish(name, 'FAIL', reason)

    def state(self, name):
        """The state of one phase."""
        with self._lock:
            return self._states.get(name, 'PLANNED')

    def names(self):
        """The names of the phases in the order of their planning."""
        with self._lock:
            return list(self._order)

    def reason(self, name):
        """The reason of the failure of one phase."""
        with self._lock:
            return self._reasons.get(name)


class _RegistryCustody:
    """The custody seam of the fixture: it registers what it retains.

    The custody of the launcher is a **supported** seam of the
    production: a channel registers itself with it **before** it builds
    anything.  The seam of the fixture forwards every call to the
    original custody of the round and it registers the retained owner
    in the registry of the fixture at the moment of the retention.

    A channel whose construction failed after its drain thread was
    started is therefore in the registry of the fixture even when the
    constructor never returned the channel to the fixture.
    """

    def __init__(self, registry, name, original=None):
        self._registry = registry
        self._name = name
        self._original = original

    def retain(self, kind, resource, detail=None, launch=None):
        self._registry.register('%s:%s' % (self._name, kind), resource,
                                kind=kind, seam='custody.retain')
        if self._original is None:
            return resource
        # The **original** signature of the custody is honoured: the
        # aggregate of a launch takes three arguments and the table of
        # the launcher takes four.
        return self._original.retain(kind, resource, detail)

    def forget(self, resource):
        if self._original is None:
            return None
        return self._original.forget(resource)


def _owner_start_state(thread, hint=None):
    """The start state of one owner of the round.

    The state is one of ``'STARTED'``, ``'NEVER_STARTED'`` or
    ``'UNKNOWN'``.  ``UNKNOWN`` is the state of an owner whose start
    did not return and of an owner whose liveness could not be asked:
    such an owner may still come up, it is never taken for an owner
    that never started and it **fails the proof** of the cleanup.

    CORRECTION 17 (M3): ``NEVER_STARTED`` is returned **only** when the
    provenance of the start **proves** it: the owner does not exist at
    all, or the registry of the fixture observed that its start was
    never invoked.  An owner without an identity and without a
    provenance is ``UNKNOWN``: it is never guessed to be an owner that
    never started.
    """
    if thread is None:
        return 'NEVER_STARTED'
    # CORRECTION 18 (M3): the query of the identity of the owner is
    # **not** swallowed here any more.  A failure of it is a fact of the
    # cleanup and the guard of the caller records it with its exact type
    # and its exact detail: a silent ``UNKNOWN`` without a diagnostic
    # would hide the failure of the classification and it would let an
    # unknown identity pass for a proved exit.
    ident = getattr(thread, 'ident', None)
    if ident is not None:
        return 'STARTED'
    if hint in ('STARTED', 'NEVER_STARTED', 'UNKNOWN'):
        return hint
    return 'UNKNOWN'


def _salvage_threads(owners, *, seconds=10.0, states=None, total_seconds=30.0,
                     interrupts=None):
    """Join the owners that really started and report their liveness.

    The salvage is the work of the **test** and it is **separate** from
    the returned state of the product: it never renews a deadline of
    the round, it never erases a retained resource of the product and
    it never claims that the product released it.

    Every owner that really started is joined with an explicitly
    bounded wait and its liveness is reported.  An owner that never
    started is reported and **never** joined.  An owner whose start
    state is ``UNKNOWN`` is reported as unknown: it is never joined as
    if it had ended and it fails the proof of the cleanup.

    CORRECTION 17 (M3): **every** owner is attempted.  A failure of the
    classification of an owner, of its join or of its liveness query
    never aborts the iteration: the error is **retained** in a list
    with its kind, its exact type and its detail, and it fails the
    proof of the cleanup.  The wait of an owner is cropped by the
    remaining budget of the salvage, so that the salvage is bounded as
    a whole.

    CORRECTION 18 (M3): the **exact** object of a ``KeyboardInterrupt``
    or of a ``SystemExit`` is retained in the ``interrupts`` list of the
    caller: the identity of the cancellation survives every best effort
    cleanup and it is re-raised by the owner of the cleanup when no
    other failure is unwinding.  The error that is written in the
    document keeps its exact type and its exact detail; the **object**
    itself never enters a document.
    """
    facts = []
    hints = states or {}
    deadline = time.monotonic() + max(0.0, total_seconds)
    for name, thread in owners:
        state = None
        errors = []
        try:
            state = _owner_start_state(thread, hints.get(name))
        except BaseException as error:  # noqa: BLE001 - it stays visible
            errors.append({'kind': 'STATE', 'type': type(error).__name__,
                           'detail': str(error)})
            _note_interruption(interrupts, error)
            state = 'UNKNOWN'
        if state != 'STARTED':
            facts.append({'name': name, 'start_state': state,
                          'started': None if state == 'UNKNOWN' else False,
                          'alive': None, 'joined': None, 'errors': errors})
            continue
        try:
            wait = max(0.0, min(seconds, deadline - time.monotonic()))
            thread.join(wait)
        except BaseException as error:  # noqa: BLE001 - it stays visible
            errors.append({'kind': 'JOIN', 'type': type(error).__name__,
                           'detail': str(error)})
            _note_interruption(interrupts, error)
        alive = None
        try:
            alive = bool(thread.is_alive())
        except BaseException as error:  # noqa: BLE001 - it stays visible
            errors.append({'kind': 'LIVENESS', 'type': type(error).__name__,
                           'detail': str(error)})
            _note_interruption(interrupts, error)
        facts.append({'name': name, 'start_state': state, 'started': True,
                      'alive': alive, 'joined': (alive is False),
                      'errors': errors})
    return facts


def _note_interruption(interrupts, error):
    """Retain the **exact** object of an interruption of the cleanup.

    A ``KeyboardInterrupt`` and a ``SystemExit`` are the identity of the
    cancellation of the round: they are retained as the objects
    themselves and they are re-raised by the owner of the cleanup when
    no other failure is unwinding.
    """
    if interrupts is None:
        return False
    if isinstance(error, (KeyboardInterrupt, SystemExit)):
        interrupts.append(error)
        return True
    return False


def _interruption_facts(interrupts):
    """The **durable** diagnostics of the exact interruptions.

    CORRECTION 19 (M3): the exact object of a cancellation never enters a
    document - only its exact type and its exact detail do.  The
    diagnostics of the cancellations of a cleanup are **kept** in the
    document of the cleanup: they are never reduced to a type and a
    detail of the last error and they are never discarded next to an
    original failure.
    """
    return [{'type': type(item).__name__, 'detail': repr(item)}
            for item in (interrupts or [])]


def _release_gate(action, errors=None, interrupts=None, kind='GATE'):
    """Release **one** gate, guarded.

    CORRECTION 20 (M3): the release of a gate is **one action per
    gate**.  A cancellation of one gate never skips the gate that
    follows it, it never skips the closes, the stop, the joins, the
    proof or the evidence that follow it, and it never replaces the
    failure that is already unwinding.  The **exact** object of the
    cancellation is retained and the owner of the cleanup re-raises the
    **first** one of them when no other failure is unwinding.
    """
    try:
        action()
    except BaseException as error:  # noqa: BLE001 - it stays visible
        if errors is not None:
            errors.append({'kind': kind, 'type': type(error).__name__,
                           'detail': str(error)})
        _note_interruption(interrupts, error)
        return error
    return None


def _raise_first_interruption(interrupts):
    """Re-raise the **first** exact pending interruption of a cleanup.

    CORRECTION 20 (M3): the priority of the failures of a cleanup is
    fixed: the failure that is already unwinding wins, then the
    **first** exact pending interruption of the cleanup and only then an
    ordinary assertion.  A cancellation of the cleanup is never reduced
    to a type and a detail and it is never discarded.
    """
    if interrupts and sys.exc_info()[0] is None:
        raise interrupts[0]


def _cleanup_facts(region, **extra):
    """The **minimal** actual facts of a cleanup region.

    CORRECTION 23 (M3): the facts of a cleanup exist **before** the body
    of the region runs.  A body that fails before its own happy facts
    exist never leaves the cleanup of the region without a document and
    the document never claims a result that was not observed:
    ``executed`` says that the body really ran, ``actions`` names every
    action that was really attempted, ``alive`` carries the **actual**
    liveness that the guarded join returned, ``original`` carries the
    failure that was really unwinding, ``unknown`` names the states that
    were not reached and ``proof_failure`` is the verdict that the
    **complete** history of the cleanup really has.
    """
    facts = {'region': region,
             'executed': False,
             'actions': [],
             'alive': None,
             'original': None,
             'unknown': [],
             'cleanup_errors': [],
             'interrupts': [],
             'proof_failure': None}
    facts.update(extra)
    return facts


def _original_facts():
    """The **exact** original failure that is unwinding, if any.

    CORRECTION 23 (M3): the original failure of a cleanup region is read
    **before** the first action of the cleanup runs - inside the handler
    of a write the state of the frame is the write error itself and the
    original failure would never be seen.  The document of the cleanup
    names it and it is never replaced by a secondary failure.
    """
    kind, value, _ = sys.exc_info()
    if kind is None:
        return None
    return {'type': kind.__name__, 'detail': str(value)}


#: CORRECTION 23 / OPT-B-07 (F06-M4): the narrow fixture observation of
#: the **actual** held references of a round.  It is **default inert**:
#: a round that nobody observes records nothing and it pays nothing.  It
#: is a fixture seam and never a production API: it only remembers the
#: objects that the fixture **really** observed at its real seams, so
#: that a supplemental case can compare a faulted object with the
#: object that the fixture really held **before** the fault.
_HELD_REFERENCES = None


def _observe_reference(kind, reference):
    """Remember one **actual** held reference of a round.

    CORRECTION 23 / OPT-B-07 (F06-M4): the seam is **inactive** by
    default: the map is ``None`` and nothing at all is retained, so a
    round that nobody observes leaves no reference behind.  A case that
    wants the references installs its **own fresh** map for the duration
    of the case and restores the previous one when the case ends.
    """
    if _HELD_REFERENCES is None:
        return reference
    _HELD_REFERENCES[kind] = reference
    return reference


def _cleanup_verdict(errors, base_proof, detail):
    """The **final** verdict of a cleanup region.

    CORRECTION 22 (M2/M3): the verdict of a cleanup is computed from
    the **actual** errors of the cleanup **after** the last action of it
    and it is never frozen before it.  The proof that was already found
    is **preserved** and the errors of the cleanup are **added** to it:
    an error of the cleanup never erases the error that was already
    found and it never disappears because the proof already failed.

    CORRECTION 23 (M2/M3): ``errors`` is the **complete** history of the
    cleanup - never a slice of it - and ``base_proof`` is the **actual**
    physical proof of the region.  An error that was recorded **before**
    the proof was computed is part of the verdict: a cleanup that met an
    unexpected error after its proof was found never keeps the proof it
    found earlier.

    The verdict is a **fact** and never an exception: the priority of
    the failures - the failure that is unwinding, then the **first**
    exact pending interruption, then the ordinary error - is enforced
    by the caller.
    """
    if not errors:
        return base_proof
    text = '%s: %s' % (detail, errors)
    if base_proof is None:
        return text
    return '%s; %s' % (base_proof, text)


def _owner_alive(join_fact):
    """The **actual** liveness of an owner, from the guarded join.

    CORRECTION 22 (M3): the liveness of an owner is the fact that the
    **guarded** join returned: the query is never repeated outside its
    guard and an **unknown** liveness is never read as the end of the
    owner.  An owner that never started has no thread and it is not
    alive.
    """
    if join_fact is None:
        return False
    alive = join_fact.get('alive')
    if alive is None:
        return True
    return bool(alive)


def _publish_cleanup(facts, writer, errors, interrupts, verdict=None):
    """Write the **complete** facts of a cleanup region.

    CORRECTION 22 (M2/M3): the document of a cleanup carries **every**
    actual error and **every** actual interruption of the cleanup and it
    is written **before** the priority of the failures is applied.  A
    write that failed is an **actual** error of the cleanup: it is
    retained with its exact type and its exact detail, the facts are
    updated **in memory** and the durability of the failure is a **best
    effort**.

    CORRECTION 23 (M2/M3): the verdict of the cleanup is recomputed
    **before every attempt to write** and **before the retry** that
    follows a failed write.  ``verdict`` is the callable that recomputes
    it from the **complete** history of the errors of the cleanup and
    from the **actual** physical proof of the region, so the durable
    artifact always carries the verdict that the cleanup **really** has
    and never the proof of a state that is already outdated.  The error
    of a failed write is added to that history **before** the retry: the
    artifact of the retry carries the **failed** proof and never
    ``None``.  When the retry fails as well the facts of the cleanup
    keep the failed verdict **in memory**, the durability of the
    evidence is marked as **not** confirmed and the cleanup never claims
    that the disk persisted it.
    """
    def _refresh():
        facts['cleanup_errors'] = list(errors)
        facts['interrupts'] = _interruption_facts(interrupts)
        if verdict is None:
            return None
        current = verdict() if callable(verdict) else verdict
        facts['proof_failure'] = current
        return current

    _refresh()
    try:
        writer()
        facts['evidence_durable'] = True
    except BaseException as error:  # noqa: BLE001 - it stays visible
        errors.append({'kind': 'EVIDENCE', 'type': type(error).__name__,
                       'detail': str(error)})
        _note_interruption(interrupts, error)
        # the verdict is recomputed **with** the error of the write
        # **before** the retry: the artifact of the retry carries the
        # failed proof of the cleanup and never a proof of ``None``.
        _refresh()
        try:
            writer()
            facts['evidence_durable'] = True
        except BaseException as retry_error:  # noqa: BLE001
            errors.append({'kind': 'EVIDENCE_RETRY',
                           'type': type(retry_error).__name__,
                           'detail': str(retry_error)})
            _note_interruption(interrupts, retry_error)
            _refresh()
            facts['evidence_durable'] = False
    return facts


def _observed_thread_refs(registry, errors=None, interrupts=None):
    """The **exact** thread objects that the registry observed.

    CORRECTION 20 (M3): the fallback of the owners of a round does
    **not** depend on the query of the entries of the registry.  The
    exact thread objects that the registry observed are read from an
    **independent** view and a failure of the query of the entries
    never replaces them with an empty list: the drain always starts
    with the references that are really known.
    """
    if registry is None:
        return []
    refs = []
    try:
        getter = getattr(registry, 'observed_threads', None)
        if getter is not None:
            refs = [(name, thread) for name, thread in getter()]
    except BaseException as error:  # noqa: BLE001 - it stays visible
        if errors is not None:
            errors.append({'kind': 'REGISTRY_OBSERVED',
                           'type': type(error).__name__,
                           'detail': str(error)})
        _note_interruption(interrupts, error)
        refs = []
    if not refs:
        # the **last** independent view of the registry: the exact
        # objects that it holds are read without its own query.
        try:
            held = getattr(registry, '_threads', None)
            if isinstance(held, dict):
                refs = [(item.get('name'), item.get('owner'))
                        for item in held.values()
                        if isinstance(item, dict)]
        except BaseException as error:  # noqa: BLE001 - it stays visible
            if errors is not None:
                errors.append({'kind': 'REGISTRY_THREADS',
                               'type': type(error).__name__,
                               'detail': str(error)})
            _note_interruption(interrupts, error)
            refs = []
    return [(name, thread) for name, thread in refs if thread is not None]


def _assert_salvage_proved(facts, message):
    """The proof that the fixture released every owner that it started.

    An owner with an **unknown** start state fails the proof: it is
    never taken for an owner that never started and it is never taken
    for an owner that ended.  An owner that met an error fails the
    proof as well: a cleanup that met an error is never a success.
    """
    for item in facts:
        assert item['start_state'] != 'UNKNOWN', \
            '%s: the owner %s has an unknown start state' \
            % (message, item['name'])
        errors = item.get('errors') or []
        assert not errors, \
            '%s: the owner %s met %s' % (message, item['name'], errors)
        if item['started']:
            assert item['alive'] is False, \
                '%s: the owner %s was left behind' % (message, item['name'])


def _prove_salvage(facts, message):
    """The proof of the cleanup of a round, as a **fact**.

    The proof is **run** in every case - also while an ordinary failure
    is already unwinding - and it returns the failure of the proof
    instead of raising it: a failure of the proof never replaces the
    failure that is already unwinding and it is never discarded.
    """
    for item in facts:
        errors = item.get('errors') or []
        if item['start_state'] == 'UNKNOWN':
            return '%s: the owner %s has an unknown start state%s' \
                % (message, item['name'], _errors_suffix(errors))
        if errors:
            return '%s: the owner %s met %s' \
                % (message, item['name'], errors)
        if item['started'] and item['alive'] is not False:
            return '%s: the owner %s was left behind' % (message, item['name'])
    return None


def _errors_suffix(errors):
    """The diagnostic of the errors of one owner of the round."""
    if not errors:
        return ''
    return ' (%s)' % (errors,)


def _drain_facts(drain):
    """The **complete** structured facts of the drain of one round.

    CORRECTION 21 (M2): the durable evidence of a round keeps the
    **whole** history of its drain and not only its attempts: the final
    salvage, the salvage of **every** iteration, the **per owner**
    errors of every iteration, the attempts, the **complete** error
    list of the drain - the errors of the enumeration, of the releases
    and of the **final resnapshot** - the quiescence and the proof.

    The first proof of a salvage is **never** used as the error list of
    the drain: a second owner error of the same iteration is never
    reduced to the proof string of the first owner and it never leaves
    the durable evidence of the round.
    """
    drain = drain or {}
    return {
        'drain_salvage': list(drain.get('salvage') or []),
        'drain_all_salvage': list(drain.get('all_salvage') or []),
        'drain_owner_errors': list(drain.get('owner_errors') or []),
        'drain_attempts': list(drain.get('attempts') or []),
        'drain_errors': list(drain.get('errors') or []),
        'drain_quiescent': bool(drain.get('quiescent')),
        'drain_proof': drain.get('proof'),
    }


def _registry_snapshot(registry, errors=None, interrupts=None,
                       label='REGISTRY_FACTS'):
    """The snapshot of the facts of a registry, **guarded**.

    CORRECTION 21 (M3): the query of the facts of the registry is a
    **guarded** query: it is the very query of the entries that the
    fallback of the drain of a round tolerates.  A failure of it is a
    fact of the cleanup: it is retained with its exact type and its
    exact detail, the **exact** object of a cancellation is retained and
    it never replaces the failure that is already unwinding and it
    never replaces the **first** exact pending interruption.

    The snapshot of a query that failed is **unknown** (``None``): it
    is never a fabricated empty registry that looks successful and it
    is an explicit diagnostic that fails the proof of the round.
    """
    if registry is None:
        return None
    try:
        return registry.facts()
    except BaseException as error:  # noqa: BLE001 - it stays visible
        if errors is not None:
            errors.append({'kind': label, 'type': type(error).__name__,
                           'detail': str(error)})
        _note_interruption(interrupts, error)
        return None


def _join_owner(label, thread, errors, interrupts, *, seconds=10.0,
                join=None):
    """Join **one** owner of a round and read its liveness, guarded.

    CORRECTION 21 (M3): the join and the liveness query of an owner
    are **guarded**: a failure of them is retained with its exact type
    and its exact detail, the **exact** object of a cancellation is
    retained and it never replaces the failure that is already
    unwinding.  The caller attempts **every** owner of the round and it
    enforces the priority of the failures - the failure that is already
    unwinding, then the **first** exact pending interruption, then the
    ordinary proof - **after** the whole traversal.
    """
    joined = None
    alive = None
    try:
        if join is not None:
            join()
        else:
            thread.join(seconds)
        joined = True
    except BaseException as error:  # noqa: BLE001 - it stays visible
        errors.append({'kind': 'JOIN', 'owner': label,
                       'type': type(error).__name__, 'detail': str(error)})
        _note_interruption(interrupts, error)
    try:
        alive = bool(thread.is_alive())
    except BaseException as error:  # noqa: BLE001 - it stays visible
        errors.append({'kind': 'LIVENESS', 'owner': label,
                       'type': type(error).__name__, 'detail': str(error)})
        _note_interruption(interrupts, error)
    return {'owner': label, 'joined': joined, 'alive': alive,
            'thread': thread}


def _capture_stop(session, original_broker=None, *, interrupts=None):
    """The **returned** state of the public stop of a round.

    The result of the stop is captured **before** the salvage of the
    fixture: the salvage is the work of the test and it never replaces
    the returned state of the product.  An exception of the stop is
    captured and it is never discarded.

    CORRECTION 17 (M3): the live state and the retention of the round
    are read **now**, in the moment of the failure, and the **actual**
    facts of the evidence of the session are kept with their **real**
    keys.  The identities of the retained resource are the live objects
    of the session: the retained broker is compared with the broker of
    the round that was captured **before** the stop, and a broker that
    is gone is ``None`` and never the identity of ``None``.

    CORRECTION 18 (M3): a stop that raised and a snapshot of the
    evidence that failed are **facts of the cleanup** and they never
    certify it: the helper ``_stop_proof_failure`` turns them into the
    failure of the proof.  The **exact** object of an interruption is
    retained in the ``interrupts`` list of the caller.
    """
    captured = {'returned': None, 'exception': None, 'live_state': None,
                'evidence': None, 'evidence_state': None,
                'evidence_broker_retained': None,
                'evidence_failures': None,
                'evidence_background_threads': None,
                'evidence_closer_start_state': None,
                'retained_broker_is_original': None,
                'retained_broker_id': None, 'snapshot_error': None}
    if session is None:
        return captured
    try:
        captured['returned'] = session.stop()
    except BaseException as error:  # noqa: BLE001 - the failure stays visible
        captured['exception'] = {'type': type(error).__name__,
                                 'detail': str(error)}
        _note_interruption(interrupts, error)
    try:
        captured['live_state'] = session.state
        broker = getattr(session, 'broker', None)
        captured['retained_broker_id'] = None if broker is None else id(broker)
        if original_broker is not None:
            captured['retained_broker_is_original'] = \
                (broker is original_broker)
        evidence = session.evidence()
        captured['evidence'] = evidence
        captured['evidence_state'] = evidence['state']
        captured['evidence_broker_retained'] = evidence['broker_retained']
        captured['evidence_failures'] = list(evidence['failures'])
        captured['evidence_background_threads'] = list(
            evidence['background_threads'])
        captured['evidence_closer_start_state'] = evidence['closer_start_state']
    except BaseException as error:  # noqa: BLE001 - the failure stays visible
        captured['snapshot_error'] = {'type': type(error).__name__,
                                      'detail': str(error)}
        _note_interruption(interrupts, error)
    return captured


def _stop_proof_failure(captured, message):
    """The failure of the cleanup that the capture of the stop carries.

    A stop that raised and a snapshot of the evidence that failed are
    **facts** of the cleanup: they are never ignored and they never
    certify that the round was cleaned.  The helper returns ``None``
    when the capture carries no error at all.
    """
    problems = []
    if captured.get('exception') is not None:
        problems.append('the stop of the round met %s'
                        % (captured['exception'],))
    if captured.get('snapshot_error') is not None:
        problems.append('the snapshot of the evidence of the round met %s'
                        % (captured['snapshot_error'],))
    if not problems:
        return None
    return '%s: %s' % (message, '; '.join(problems))


def _join_details(*parts):
    """The detail of a failure: every part that carries a fact.

    CORRECTION 18 (M2): the original failure of the phase and every
    diagnostic of its cleanup are **joined**: neither of them replaces
    the other and none of them is dropped.
    """
    return '; '.join([part for part in parts if part])


def _cleanup_detail(cleanup_errors, write_errors):
    """The diagnostic of the cleanup errors of one phase.

    CORRECTION 18 (M2): the errors of the cleanup are a **list** and
    they are never overwritten: the detail names **every** one of them
    and it names the errors of the writing of the evidence as well.
    """
    parts = []
    for item in cleanup_errors:
        parts.append('%s: %s' % (item.get('kind'), item.get('detail')))
    for item in write_errors:
        parts.append('the writing of the evidence of %s failed: %s'
                     % (item.get('name'), item.get('detail')))
    if not parts:
        return None
    return '; '.join(parts)


def _session_owners(session, prefix='session', hints=None):
    """The owners that the session of the round really started.

    The registry is read from the session itself: the background
    threads of the round and the closer threads that it really built.
    A closer that never started is reported as such and it is never
    joined.  A thread whose start did not return is **UNKNOWN**: it
    keeps its owner in the session and it may still come up.
    """
    owners = []
    if session is None:
        return owners
    records = getattr(session, '_background_threads', None) or {}
    for kind in sorted(records):
        record = records[kind] or {}
        name = '%s:background-%s' % (prefix, str(kind))
        owners.append((name, record.get('thread')))
        if hints is None:
            continue
        state = record.get('state')
        if state == 'STARTING':
            hints[name] = 'UNKNOWN'
        elif state == 'FAILED' and not record.get('started'):
            hints[name] = 'NEVER_STARTED'
    closer_state = getattr(session, '_closer_start_state', None)
    for index, thread in enumerate(getattr(session, '_closer_threads', None)
                                   or []):
        name = '%s:closer-%d' % (prefix, index)
        owners.append((name, thread))
        if hints is not None and closer_state == 'STARTING':
            hints[name] = 'UNKNOWN'
    return owners


def _install_main_pump_observer(session, phase):
    """Observe the ACTUAL pump of the MAIN session of one round.

    The seam is the production ``_start_background_thread`` of the
    session: the pump of the round is the exact object that the
    production really hands to it and the observer captures it
    **before** the original start, so that the capture never depends on
    the mutable reference ``session._pump`` that the production retires
    once it confirmed the join of the pump.

    The observer is **instance local**: it is installed on this one
    session, so every call it forwards is by construction the call of
    this MAIN session, and the kind of the call is kept as it is: only
    the pump of the round is held and every other background thread of
    the round is forwarded untouched.

    The forwarder is **transparent**: the original method is called
    with the original arguments, its result is returned unchanged and
    its error is re-raised unchanged.  The observer never decides
    anything, it never refuses a start and it never changes a deadline
    of the round.

    The **join** of the pump is observed by an instance local forwarder
    of the original ``join_bounded`` of the pump: the real argument,
    the real result and the real error of the join are recorded and
    they are forwarded unchanged.  The phase of every join says whether
    the join happened **before the body boundary** of the region of the
    fixture or **during the salvage** of that region.
    """
    observed = {'pump': None, 'calls': [], 'joins': []}
    original_start = session._start_background_thread

    def install_join_recorder(pump):
        """Observe the join of the pump on the pump itself."""
        original_join = pump.join_bounded

        def recording_join_bounded(seconds):
            record = {'seconds': seconds, 'phase': phase(),
                      'result': None, 'error': None,
                      'at': time.monotonic(),
                      'thread': threading.current_thread().name}
            observed['joins'].append(record)
            try:
                result = original_join(seconds)
            except BaseException as error:  # noqa: BLE001 - it stays visible
                record['error'] = repr(error)
                raise
            record['result'] = result
            return result

        pump.join_bounded = recording_join_bounded

    def observing_start_background_thread(kind, thread):
        """Forward the start of one background thread of the round."""
        record = {'kind': kind, 'thread_id': id(thread),
                  'captured': False, 'start_result': None,
                  'start_error': None, 'at': time.monotonic()}
        observed['calls'].append(record)
        if kind == 'pump' and observed['pump'] is None:
            observed['pump'] = thread
            record['captured'] = True
            install_join_recorder(thread)
        try:
            result = original_start(kind, thread)
        except BaseException as error:  # noqa: BLE001 - it stays visible
            record['start_error'] = repr(error)
            raise
        record['start_result'] = result
        return result

    session._start_background_thread = observing_start_background_thread
    return observed


def _pump_pointer_state(session, held_pump):
    """The state of the **mutable** reference of the pump of the round.

    The reference of the session and the object that the fixture really
    holds are two different things: the production retires the
    reference of the session once it confirmed the join of the pump and
    it never replaces it with another object.  The state of the
    reference is therefore one of

    * ``NOT_STARTED``  the fixture never observed a pump of the round,
    * ``SAME``         the reference is the very object that the
      fixture holds,
    * ``ABSENT``       the reference is ``None`` and the production
      retired it,
    * ``OTHER``        the reference is another object.

    The state is a fact of the fixture and it is never a proof: an
    absent reference proves neither the start of a pump nor its end.
    """
    if held_pump is None:
        return 'NOT_STARTED'
    pointer = getattr(session, '_pump', None)
    if pointer is None:
        return 'ABSENT'
    if pointer is held_pump:
        return 'SAME'
    return 'OTHER'


def _endpoint_owners(prefix, endpoint, hints=None):
    """The owners that one endpoint of the round really started.

    The read worker and the write worker of the endpoint are the
    owners that the endpoint really started.  A worker that the
    endpoint **retained** is a worker whose start did not return: its
    state is **UNKNOWN** and it fails the proof of the cleanup.
    """
    owners = []
    if endpoint is None:
        return owners
    for role, label in (('_reader', 'read'), ('_writer', 'write')):
        worker = getattr(endpoint, role, None)
        if worker is None:
            continue
        owners.append(('%s:%s-worker' % (prefix, label), worker))
    for index, worker in enumerate(getattr(endpoint, '_retained', None)
                                   or []):
        name = '%s:retained-%d' % (prefix, index)
        owners.append((name, worker))
        if hints is not None:
            hints[name] = 'UNKNOWN'
    return owners


def _channel_owners(channel, prefix, hints=None):
    """The owners that the channel of the round really started.

    The drain thread of the channel and the workers of its two
    endpoints are the owners of the round that really started.  A worker
    that was never started is reported as such and it is never joined.
    """
    owners = []
    if channel is None:
        return owners
    owners.append((prefix + ':drain', getattr(channel, '_thread', None)))
    if hints is not None:
        # The drain thread of a channel is started **inside** the
        # constructor of the channel: a channel whose construction
        # failed at the start of its drain owns a drain thread whose
        # start did not return and it may still come up.
        hints[prefix + ':drain'] = 'UNKNOWN'
    reader = getattr(channel, '_reader', None)
    writer = getattr(channel, '_writer', None)
    for endpoint, label in ((reader, 'read'), (writer, 'write')):
        owners.extend(_endpoint_owners('%s:%s' % (prefix, label), endpoint,
                                       hints))
    return owners


def _registry_owners(registry, session=None, channel=None, prefix='round',
                      errors=None, interrupts=None):
    """Every owner of the round: the registered ones and the live ones.

    The registry of the fixture holds the owners that were registered
    **immediately** - a channel that was constructed, an endpoint that
    was built, a session that was created.  The session and the
    channel that are still reachable are added to them, so that a
    thread that the product started after the registration is never
    forgotten.  One owner is never in the list twice: the identity of
    the thread decides and not its name.

    CORRECTION 19 (M3): the traversal is **best effort**.  The query
    of one container never aborts the traversal and it never replaces
    the owners of the round with an empty list: every other owner is
    still attempted.  The **exact** thread objects that the start
    registry observed are retained **first** and they are an
    independent fallback - a failure of the query of a container never
    loses them.  Every failure is retained with its exact type and its
    exact detail and the **exact** object of an interruption is kept.
    """
    owners = []
    hints = {}
    seen = set()
    kinds = set()

    def add(items):
        for name, thread in items:
            key = ('thread', id(thread)) if thread is not None \
                else ('name', name)
            if key in seen:
                continue
            seen.add(key)
            owners.append((name, thread))

    def note(kind, error):
        """Retain one failure of the traversal, never swallow it."""
        if errors is not None:
            errors.append({'kind': kind, 'type': type(error).__name__,
                           'detail': str(error)})
        _note_interruption(interrupts, error)

    # CORRECTION 20 (M3): the **exact** thread objects that the start
    # registry observed are read from an **independent** view **before**
    # the query of the entries: the fallback of the owners of the round
    # never depends on that query and it never starts from an empty
    # list.  The query of the entries may fail and the references that
    # are really known are still there.
    observed = _observed_thread_refs(registry, errors, interrupts)
    try:
        entries = registry.entries()
    except BaseException as error:  # noqa: BLE001 - it stays visible
        note('REGISTRY_ENTRIES', error)
        entries = []
    # CORRECTION 19 (M3): the **exact** thread objects that the start
    # registry observed are retained **first** and they are an
    # independent fallback: a failure of the query of a container never
    # loses them and it never replaces the owners of the round with an
    # empty list.  They are merged into the owners **after** the
    # traversal, so that the name of an owner that a container really
    # knows is never replaced by the name of the registry.
    for entry in entries:
        name = entry.get('name')
        owner = entry.get('owner')
        kind = entry.get('kind')
        if kind == 'thread':
            add([(name, owner)])
            observed.append((name, owner))
            continue
        try:
            if kind == 'channel':
                items = _channel_owners(owner, name, hints)
            elif kind == 'endpoint':
                items = _endpoint_owners(name, owner, hints)
            elif kind == 'session':
                items = _session_owners(owner, name, hints)
            else:
                items = [(name, owner)]
        except BaseException as error:  # noqa: BLE001 - it stays visible
            # the traversal continues: the owners that follow this one
            # are still attempted and the exact thread object of this
            # entry is still an owner of the round.
            note('OWNER_QUERY', error)
            if isinstance(owner, threading.Thread):
                add([(name, owner)])
            continue
        kinds.add(kind)
        add(items)
    try:
        if session is not None and 'session' not in kinds:
            add(_session_owners(session, '%s:session' % prefix, hints))
    except BaseException as error:  # noqa: BLE001 - it stays visible
        note('SESSION_QUERY', error)
    try:
        if channel is not None and 'channel' not in kinds:
            add(_channel_owners(channel, '%s:channel' % prefix, hints))
    except BaseException as error:  # noqa: BLE001 - it stays visible
        note('CHANNEL_QUERY', error)
    # CORRECTION 19 (M3): the fallback of the observed threads: every
    # exact thread object that the start registry saw is an owner of the
    # round.  The merge is **idempotent**: an owner that the traversal
    # already named keeps its name and its hint.
    for name, thread in observed:
        add([(name, thread)])
    # CORRECTION 17 (M3): the provenance of the starts that the
    # observer of the fixture saw is the **proven** provenance of the
    # start of an owner.  It is keyed by the exact thread object and it
    # never replaces the hint of the production: a thread whose start
    # returned is ``STARTED`` and a thread whose start did not return is
    # ``UNKNOWN``.
    try:
        provenance = registry.start_provenance() if registry is not None else {}
    except BaseException as error:  # noqa: BLE001 - it stays visible
        note('PROVENANCE', error)
        provenance = {}
    for name, thread in owners:
        if thread is None:
            continue
        state = provenance.get(id(thread))
        if state == 'STARTED':
            hints[name] = 'STARTED'
        elif state in ('STARTING', 'FAILED'):
            hints[name] = 'UNKNOWN'
    return owners, hints


def _drain_owners(registry, session=None, channel=None, prefix='round', *,
                  seconds=10.0, budget=30.0, release=None, interrupts=None):
    """The bounded drain of the owners of one round.

    CORRECTION 17 (M3): the drain repeats, **boundedly**, until the
    owners of the round are quiescent and really joined.  The bound of
    the drain is **one** overall bound: the wait of an owner is cropped
    by the remaining budget and the budget is never reset - neither
    between the rounds of the drain nor between the rounds of the test.

    The quiescence of the round is asserted **after** the drain and
    never before it: a round that is not quiescent is a failure of the
    cleanup, the gates of the round are still released and **all** the
    registered owners are still attempted.

    CORRECTION 18 (M3): the enumeration of the owners and the reading
    of the generation of the registry are **one** observation.  The
    generation is read **before** the exact owners are enumerated and
    it is read **again** right after the enumeration and once more
    after the joined producer threads of the iteration.  All of these
    readings must agree and the **final** exact-owner resnapshot must
    contain every owner of the enumeration: a thread that was started
    between the enumeration and the reading of the generation is never
    certified as quiescent and it is never left behind.

    Every error of the drain - the enumeration, the release of the
    gates, the classification of an owner, its join and its liveness
    query - is **retained** in a list with its exact type and its exact
    detail and it fails the proof of the cleanup.  **Every** iteration
    is kept: an error of an earlier iteration is never erased by a
    later iteration that really ended the threads.  A failure never
    aborts the iteration and it never skips the final result of the
    round.  The drain never renews a deadline of the product.

    CORRECTION 19 (M3): every read of the drain - the generation, the
    pending starts and the final resnapshot - is **best effort** and it
    never skips the owners that follow it.  The release of the gates is
    **one action per gate**: a failure of one gate never skips the gate
    that follows it.  The traversal of the owners never replaces the
    owners of the round with an empty list and the exact thread objects
    that the start registry observed are always retained.
    """
    deadline = time.monotonic() + max(0.0, budget)
    attempts = []
    errors = []
    # CORRECTION 21 (M2): the **per owner** errors of **every** iteration
    # of the drain are kept one by one: the errors of an owner are never
    # reduced to the proof string of the first owner that failed and
    # they never leave the durable evidence of the round.
    owner_errors = []
    # CORRECTION 20 (M3): the drain starts with the references that are
    # **independently** known: a failure of the very first enumeration
    # never replaces the owners of the round with an empty list and the
    # partial child of the registry is still attempted.
    owners = _observed_thread_refs(registry, errors, interrupts)
    hints = {}
    salvage = []
    all_salvage = []
    quiescent = False

    def read_generation(label):
        """Read the generation of the registry, guarded.

        CORRECTION 19 (M3): the reading of the generation is **best
        effort**: a failure of it is a fact of the cleanup and it never
        skips the owners that follow it.
        """
        try:
            return registry.generation()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            errors.append({'kind': label, 'type': type(error).__name__,
                           'detail': str(error)})
            _note_interruption(interrupts, error)
            return None

    def read_pending(label):
        """Read the pending starts of the registry, guarded."""
        try:
            return registry.pending_starts()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            errors.append({'kind': label, 'type': type(error).__name__,
                           'detail': str(error)})
            _note_interruption(interrupts, error)
            return None

    while True:
        # the generation of the registry is read **before** the exact
        # owners are enumerated
        generation_before = read_generation('GENERATION_BEFORE')
        try:
            owners, hints = _registry_owners(registry, session=session,
                                              channel=channel, prefix=prefix,
                                              errors=errors,
                                              interrupts=interrupts)
        except BaseException as error:  # noqa: BLE001 - it stays visible
            errors.append({'kind': 'ENUMERATION',
                           'type': type(error).__name__,
                           'detail': str(error)})
            _note_interruption(interrupts, error)
            # CORRECTION 19 (M3): the owners of the previous observation
            # are **retained**: a failure of the enumeration never loses
            # them and it never replaces them with an empty list.
        # ... and it is read **again** right after the enumeration: a
        # start that happened between the two readings is a change of
        # the generation and the enumeration is repeated.
        generation_after = read_generation('GENERATION_AFTER')
        snapshot = {'generation_before': generation_before,
                    'generation_after': generation_after,
                    'generation': generation_after,
                    'pending': read_pending('PENDING'),
                    'owners': [name for name, _ in owners],
                    'errors': list(errors)}
        attempts.append(snapshot)
        if release is not None:
            # CORRECTION 19 (M3): the release of the gates is **best
            # effort**: every gate is released on its own and a failure
            # of one gate never skips the gate that follows it.
            actions = (release if isinstance(release, (list, tuple))
                       else [release])
            for action in actions:
                try:
                    action()
                except BaseException as error:  # noqa: BLE001
                    errors.append({'kind': 'RELEASE',
                                   'type': type(error).__name__,
                                   'detail': str(error)})
                    _note_interruption(interrupts, error)
        remaining = max(0.0, deadline - time.monotonic())
        salvage = _salvage_threads(owners, states=hints, seconds=seconds,
                                   total_seconds=remaining,
                                   interrupts=interrupts)
        # CORRECTION 18 (M3): **every** iteration of the drain is kept -
        # the failure of an earlier iteration is never erased by a later
        # iteration that ended the threads.
        all_salvage.extend(salvage)
        # CORRECTION 21 (M2): the errors of the owners of **this**
        # iteration are kept **one by one** and they are named with the
        # iteration that really produced them: the error of a second
        # owner of the same iteration is never lost behind the proof
        # string of the first one.
        for item in salvage:
            for error in (item.get('errors') or []):
                owner_errors.append({
                    'iteration': len(attempts) - 1,
                    'name': item.get('name'),
                    'kind': error.get('kind'),
                    'type': error.get('type'),
                    'detail': error.get('detail')})
        # The **final** exact-owner resnapshot: it is taken after the
        # joined producer threads of this iteration and it must agree
        # with the enumeration of this iteration.
        final_generation = read_generation('FINAL_GENERATION')
        try:
            final_owners, _final_hints = _registry_owners(
                registry, session=session, channel=channel, prefix=prefix,
                errors=errors, interrupts=interrupts)
        except BaseException as error:  # noqa: BLE001 - it stays visible
            errors.append({'kind': 'FINAL_ENUMERATION',
                           'type': type(error).__name__,
                           'detail': str(error)})
            _note_interruption(interrupts, error)
            # CORRECTION 20 (M3): the final resnapshot never starts from
            # an empty list either: the **independently** known
            # references are the owners that the round really knows.
            final_owners = _observed_thread_refs(registry, errors, interrupts)
        # and the generation is read **again** after the final
        # resnapshot: a start that happened during it is a change of the
        # generation and the drain repeats.
        final_generation_after = read_generation('FINAL_GENERATION_AFTER')
        final_names = [name for name, _ in final_owners]
        missing = [name for name in snapshot['owners']
                   if name not in final_names]
        late = [name for name in final_names
                if name not in snapshot['owners']]
        pending = read_pending('FINAL_PENDING')
        stable = (generation_before == generation_after
                  and final_generation == generation_after
                  and final_generation_after == generation_after
                  and not missing and not late)
        quiescent = (pending == 0 and stable
                     and _prove_salvage(salvage, prefix) is None)
        if quiescent or time.monotonic() >= deadline:
            break
        # the drain is **bounded** and it never spins: the next attempt
        # follows a short pause and it happens inside the same budget
        time.sleep(0.01)
    proof = _prove_salvage(all_salvage, prefix)
    if proof is None and errors:
        proof = '%s: the drain met %s' % (prefix, errors)
    # CORRECTION 19 (M2/M3): a round that is **not** quiescent is a
    # failure of the cleanup even when every owner that the salvage saw
    # was really joined: the final resnapshot of the drain found an
    # owner that no join released, and the proof of the cleanup says so.
    if proof is None and not quiescent:
        proof = ('%s: the owners of the round were not quiescent' % prefix)
    return {'owners': owners, 'hints': hints, 'salvage': salvage,
            'all_salvage': all_salvage, 'owner_errors': owner_errors,
            'attempts': attempts, 'proof': proof, 'errors': errors,
            'quiescent': bool(quiescent)}



# -- N10-R01: the control handle of a process ------------------------------

def test_n10_r01_the_control_handle_is_closed_only_after_the_exit(tmp_path):
    """N10-R01 (M03): the last control handle of a process is kept.

    Obligation: a Core that took a process and could not assign it to
    the job of the round - the child is still suspended and it never ran
    - keeps the **original** control handle of that process when the
    termination of the child fails and when the wait does not confirm
    the exit: the record of the round and the pending table of the
    round **both** forbid the close of the handle, the handle stays with
    its owner and the same owner may still terminate the process and
    wait for it inside the original deadline.  The thread handle and
    the pipe handles are independent of the exit and they are released
    on their own.

    Entry: ``BrokerCore._launch_role`` (the assignment of the process),
    ``BrokerCore._terminate_owned``, ``BrokerCore._release_the_records``,
    ``BrokerCore._process_closeable`` and
    ``_PendingResources.close_all``.  Trigger: the assignment of the
    process to the job fails, the termination of the child fails and the
    wait does not confirm the exit.  Oracle: the close of the control
    handle was never attempted, the handle is still reachable and the
    round is not a release.  Negative: a close that would succeed is
    never a proof that the process ended.  Returned state: the record
    and the pending table name the handle and its owner.  Salvage: the
    same owner confirms the exit later and closes the handle exactly
    once.
    """
    class UnconfirmedWin32(RecordingWin32):
        """A façade whose processes never confirm their exit by themselves."""

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self.confirmed = False

        def terminate_job(self, job, exit_code):
            # The termination of the job does **not** mark the processes
            # as exited: only the wait of the round may confirm it.
            self.calls.append(('terminate_job', job, exit_code))

        def wait_process(self, process, timeout_ms):
            self.calls.append(('wait_process', process, timeout_ms))
            for entry in self.created:
                if entry['handle'] == process:
                    entry['exited'] = self.confirmed
                    return entry['exited']
            return True

    win32 = UnconfirmedWin32(fail_at=('assign', 'terminate'))
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    try:
        core.arm()
        # The assignment of the process to the job of the round fails:
        # the child is still suspended and it never ran.
        with pytest.raises(BrokerError) as info:
            core.launch()
        assert info.value.code == 'BROKER_ASSIGN_FAILED'
        assert win32.fired == {'assign', 'terminate'}, \
            'the named failures of the round never happened'
        record = core.records[0]
        target = record['process_handle']
        assert target is not None, 'the child never got a control handle'
        facts = {'assigned': record['assigned'], 'resumed': record['resumed'],
                 'exited': record['exited'],
                 'process_handle_kept': record['process_handle'] is target,
                 'process_handle_closed': record['process_handle_closed'],
                 'thread_handle_closed': record['thread_handle_closed'],
                 'pending': [item['kind'] for item in core._pending.pending()],
                 'live': sorted(win32.live),
                 'state': core.state}
        write_phase('r01-first', facts)
        # The child never ran and its exit was never confirmed.
        assert record['assigned'] is False
        assert record['resumed'] is False
        assert record['exited'] is False
        # The control handle of the child is **still** with its owner.
        assert record['process_handle'] is target, \
            'the control handle was forgotten while the exit was unknown'
        assert record['process_handle_closed'] is False
        assert target in win32.live, \
            'the control handle was closed while the exit was unknown'
        # The pending table forbids the close as well: the eligibility
        # comes from the owner of the handle and not from the name of a
        # state.
        pending = [item for item in core._pending.pending()
                   if item['handle'] == target]
        assert pending, 'the control handle lost its owner'
        assert pending[0]['kind'] == 'process'
        # The thread handle is independent of the exit of the process.
        assert record['thread_handle_closed'] is True
        assert record['thread_handle'] is None
        # The round is not a release.
        assert core.state == 'UNKNOWN_RETAINED'
        assert core._released is False

        # The same owner confirms the exit: the handle is closed once.
        win32.confirmed = True
        core.stop('STOP')
        facts = {'process_handle_closed': record['process_handle_closed'],
                 'closes': win32.closed.count(target),
                 'state': core.state,
                 'pending': [item['kind'] for item in core._pending.pending()]}
        write_phase('r01-second', facts)
        assert record['process_handle_closed'] is True
        assert record['process_handle'] is None
        assert win32.closed.count(target) == 1, \
            'the control handle was closed twice'
        assert target not in win32.live
    finally:
        # The salvage of the owner of the test is bounded and it never
        # hides a resource that the product kept.
        for handle in list(win32.live):
            RecordingWin32.close_handle(win32, handle)


# -- N10-R02: the claim of the recovery and the handover -------------------

def test_n10_r02_the_claim_of_the_recovery_and_the_handover_are_exclusive():
    """N10-R02 (M05): the recovery and the handover are one decision.

    Obligation: the recovery of the API owner **claims** the entry
    under the lock of the table before it touches it and the handover
    of the same entry is **refused** while the claim is alive: a
    handle that was handed over may never be closed by the recovery and
    a handle that the recovery claimed may never be handed over.  The
    blocking primitive of the recovery runs **outside** of the lock of
    the table and the table stays usable while it waits.  An exception
    never leaves an entry without an owner and never leaves two close
    owners.

    Entry: ``WindowsApi.release_retained``, ``WindowsApi.handover`` and
    ``WindowsApi._claim_entry``.  Trigger: the recovery blocks inside
    the close of one end of a pipe while the core hands the other end
    over.  Oracle: the handover of the claimed end is refused and the
    end is never registered with a second owner; the handover of the
    other end succeeds while the recovery waits.  Negative: the table
    lock is never held while the recovery waits.  Returned state: the
    report of the recovery names the entries that it did not own.
    Salvage: the recovery of the API owner releases the ends that it
    owns.

    CORRECTION 11 (M05): the **creation** of a process and the
    recovery of the façade are **one** ownership decision as well.  The
    original entries of the process and of its thread are reserved or
    refused under the lock of the table, the blocking primitives run
    outside of that lock, and a handle that the recovery of the façade
    claimed is never delivered to the core and never closed twice.
    The group drives the race between the birth query of a created
    process and the recovery of the façade and it proves that there is
    exactly one closer of the original handle of the process.
    """
    entered = threading.Event()
    release = threading.Event()
    closed = []

    def create_pipe(kernel32, *args):
        read = kernel32.allocate('pipe_read')
        write = kernel32.allocate('pipe_write')
        args[0]._obj.value = read
        args[1]._obj.value = write
        return 1

    def close_handle(kernel32, *args):
        handle = getattr(args[0], 'value', args[0])
        if handle in kernel32.live and kernel32.live[handle] == 'pipe_read':
            # The close of the read end blocks: the recovery holds its
            # claim while it waits.
            entered.set()
            release.wait(10.0)
        kernel32.live.pop(handle, None)
        closed.append(handle)
        return 1

    kernel32 = SyntheticKernel32(script={'CreatePipe': create_pipe,
                                         'CloseHandle': close_handle})
    api = WindowsApi(table=synthetic_table(kernel32))
    read, write = api.create_pipe('stdout')
    report_holder = {}

    def recover():
        report_holder['report'] = api.release_retained()

    worker = threading.Thread(target=recover, name='lvw-n10-r02-recovery')
    worker.start()
    # CORRECTION 20 (M3): the release of the gate of the recovery is
    # guarded: a cancellation of it never skips the join that follows it
    # and it never replaces the failure that is already unwinding.
    recovery_cleanup_errors = []
    recovery_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this region exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the region without a
    # durable document.
    recovery_cleanup_facts = _cleanup_facts('recovery')
    try:
        recovery_cleanup_facts['executed'] = True
        assert entered.wait(10.0), \
            'the recovery never reached the close of the claimed end'
        # The table is usable while the recovery waits: the lock of the
        # table is not held by the blocking primitive.
        registered = []

        def register(items):
            registered.extend(items)

        # The handover of the **claimed** end is refused.
        with pytest.raises(BrokerError) as info:
            api.handover([(read, 'pipe_read')], owner='CORE', register=register)
        assert info.value.code == 'BROKER_HANDOVER_CLAIMED'
        assert registered == [], \
            'a claimed end was registered with a second owner'
        # The handover of the **other** end succeeds: the table is not
        # held by the recovery that waits.
        api.handover([(write, 'pipe_write')], owner='CORE', register=register)
        assert registered == [(write, 'pipe_write')]
        write_phase('r02-claim', {'claimed': repr(read),
                                   'refused_code': info.value.code,
                                   'registered': [repr(item)
                                                  for item in registered]})
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        recovery_cleanup_facts['original'] = _original_facts()
        # CORRECTION 20 (M3): the release of the gate is guarded and the
        # exact object of a cancellation of it is retained.
        _release_gate(release.set, recovery_cleanup_errors, recovery_interrupts)
        recovery_cleanup_facts['actions'].append('release:gate')
        # CORRECTION 21 (M3): the join of the recovery is **guarded**: a
        # failure of it is retained with its exact type and its exact
        # detail and it never replaces the failure that is already
        # unwinding.
        recovery_join = _join_owner('recovery', worker,
                                    recovery_cleanup_errors,
                                    recovery_interrupts, seconds=15.0)
        recovery_cleanup_facts['actions'].append('join:recovery')
        # CORRECTION 22 (M3): the **actual** liveness of the owner is the
        # fact that the guarded join returned: the query is never
        # repeated outside its guard and an **unknown** liveness is
        # never read as the end of the owner.
        recovery_alive = _owner_alive(recovery_join)
        recovery_cleanup_facts['alive'] = recovery_alive
        recovery_cleanup_facts['report'] = [
            {'kind': item['kind'], 'released': item['released']}
            for item in (report_holder.get('report') or [])]
        recovery_cleanup_facts['closed'] = list(closed)
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures: the
        # diagnostics of the cleanup are durable even when the original
        # failure of the region is unwinding.  The verdict of the
        # cleanup is recomputed from the **complete** history of its
        # errors **before** every attempt to write.
        _publish_cleanup(
            recovery_cleanup_facts,
            lambda: write_phase('r02-report-cleanup',
                                recovery_cleanup_facts),
            recovery_cleanup_errors, recovery_interrupts,
            verdict=lambda: _cleanup_verdict(
                recovery_cleanup_errors, None,
                'the cleanup of the recovery met'))
        # the **exact** cancellation wins over the ordinary assertion of
        # the join that follows it.
        _raise_first_interruption(recovery_interrupts)
        # the ordinary proof of the round: it runs **after** the join and
        # it never replaces the failure that is already unwinding.
        if sys.exc_info()[0] is None:
            assert not recovery_alive, 'the recovery was left behind'
    report = report_holder.get('report') or []
    # CORRECTION 22 (M3): the facts of the cleanup are **durable** before
    # they are enforced: every actual error and every actual
    # interruption of the cleanup is in the document of the phase.
    write_phase('r02-report', {'report': [{'kind': item['kind'],
                                            'released': item['released']}
                                           for item in report],
                               'closed': list(closed),
                               'cleanup_errors': list(recovery_cleanup_errors),
                               'interrupts': _interruption_facts(
                                   recovery_interrupts),
                               'recovery_alive': recovery_alive})
    # the ordinary errors of the cleanup are **consumed**: they fail the
    # round instead of being recorded and forgotten.
    if recovery_cleanup_errors and sys.exc_info()[0] is None:
        raise AssertionError('the cleanup of the recovery met %s'
                             % (recovery_cleanup_errors,))
    # The claimed end was closed by the recovery that owned it and the
    # end that was handed over was never closed by the recovery.
    assert closed.count(getattr(read, 'value', read)) == 1
    assert closed.count(getattr(write, 'value', write)) == 0, \
        'the recovery closed an end that it handed over'

    # The second direction: an end that was handed over is never closed
    # by a recovery that read the entry before the handover.
    kernel32 = SyntheticKernel32(script={'CreatePipe': create_pipe})
    api = WindowsApi(table=synthetic_table(kernel32))
    read, write = api.create_pipe('stderr')
    key = id(read)
    entry = api._retained.get(key)
    assert entry is not None, 'the end was not retained by the facade'
    registered = []
    api.handover([(read, 'pipe_read'), (write, 'pipe_write')], owner='CORE',
                 register=lambda items: registered.extend(items))
    assert registered == [(read, 'pipe_read'), (write, 'pipe_write')]
    # The recovery of the facade finds nothing: the end has an owner.
    report = api.release_retained()
    write_phase('r02-handed-over', {'report': report,
                                     'live': sorted(kernel32.live)})
    assert report == [], 'the recovery closed an end that it handed over'
    assert getattr(read, 'value', read) in kernel32.live

    # -- the third direction (N1 correction 11, M05): the **creation**
    #    of a process and the recovery of the façade are one ownership
    #    decision.  The birth query of the created process blocks, the
    #    recovery of the façade claims the original entries of the
    #    process and of its thread while the creation is in flight,
    #    and the return of the creation may then neither deliver a
    #    stale claimed handle to the core nor forget it.  There is
    #    exactly **one** closer of the original handle of the process.
    blocked = threading.Event()
    resume = threading.Event()
    closed_handles = []

    def get_process_times(kernel32, *args):
        # The birth query of the created process blocks: the recovery
        # of the façade runs while the creation is in flight.
        blocked.set()
        resume.wait(10.0)
        # The production hands the birth query a **reference** to the
        # structure of the creation.  The structure itself is the
        # ``_obj`` of that reference: a field that is written on the
        # reference itself would raise before the race of the group was
        # ever reached.
        creation = structure_of(args[1])
        creation.dwLowDateTime = kernel32.creation_time & 0xFFFFFFFF
        creation.dwHighDateTime = kernel32.creation_time >> 32
        return 1

    def close_handle(kernel32, *args):
        handle = getattr(args[0], 'value', args[0])
        closed_handles.append(handle)
        kernel32.live.pop(handle, None)
        return 1

    kernel32 = SyntheticKernel32(script={'GetProcessTimes': get_process_times,
                                         'CloseHandle': close_handle})
    api = WindowsApi(table=synthetic_table(kernel32))
    outcome = {}

    def create():
        try:
            outcome['created'] = api.create_process_suspended(
                executable='C:/python.exe', arguments=['-I'],
                working_directory='C:/', stdout_handle=0, stderr_handle=0)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            outcome['error'] = error

    creator = threading.Thread(target=create, name='lvw-n10-r02-creation')
    creator.start()
    # CORRECTION 20 (M3): the release of the gate of the creation is
    # guarded: a cancellation of it never skips the join that follows it
    # and it never replaces the failure that is already unwinding.
    creation_cleanup_errors = []
    creation_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this region exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the region without a
    # durable document.
    creation_cleanup_facts = _cleanup_facts('creation')
    try:
        creation_cleanup_facts['executed'] = True
        assert blocked.wait(10.0), \
            'the birth query of the creation never ran'
        # The recovery of the façade claims the original entries of the
        # process and of its thread while the creation is in flight.
        report = api.release_retained()
        assert report, 'the recovery of the façade found nothing to release'
        resume.set()
        creator.join(15.0)
        assert not creator.is_alive(), 'the creation was left behind'
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        creation_cleanup_facts['original'] = _original_facts()
        # CORRECTION 20 (M3): the release of the gate is guarded and the
        # exact object of a cancellation of it is retained.
        _release_gate(resume.set, creation_cleanup_errors, creation_interrupts)
        creation_cleanup_facts['actions'].append('release:gate')
        # CORRECTION 21 (M3): the join of the creator is **guarded**: a
        # failure of it is retained with its exact type and its exact
        # detail and it never replaces the failure that is already
        # unwinding.
        creation_join = _join_owner('creator', creator,
                                    creation_cleanup_errors,
                                    creation_interrupts, seconds=15.0)
        creation_cleanup_facts['actions'].append('join:creator')
        creation_cleanup_facts['alive'] = _owner_alive(creation_join)
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures.
        _publish_cleanup(
            creation_cleanup_facts,
            lambda: write_phase('r02-creation-cleanup',
                                creation_cleanup_facts),
            creation_cleanup_errors, creation_interrupts,
            verdict=lambda: _cleanup_verdict(
                creation_cleanup_errors, None,
                'the cleanup of the creation met'))
        # the **exact** cancellation of the cleanup wins over an ordinary
        # assertion and it is re-raised as **itself**.
        _raise_first_interruption(creation_interrupts)
    facts = {'error': getattr(outcome.get('error'), 'code', None),
             'created': outcome.get('created') is not None,
             'closed': list(closed_handles),
             'report': [{'kind': item['kind'], 'released': item['released']}
                        for item in report],
             # CORRECTION 22 (M3): the facts of the cleanup of the
             # creation are **durable**: every actual error and every
             # actual interruption of it is in the document.
             'cleanup_errors': list(creation_cleanup_errors),
             'interrupts': _interruption_facts(creation_interrupts),
             'creator_alive': _owner_alive(creation_join)}
    write_phase('r02-creation', facts)
    # the ordinary errors of the cleanup are **consumed**: they fail the
    # round instead of being recorded and forgotten.
    if creation_cleanup_errors and sys.exc_info()[0] is None:
        raise AssertionError('the cleanup of the creation met %s'
                             % (creation_cleanup_errors,))
    # A stale claimed handle is never delivered to the core.
    assert outcome.get('created') is None, \
        'a stale claimed handle was delivered to the core'
    error = outcome.get('error')
    assert isinstance(error, BrokerError), \
        'the creation did not refuse the refused handover'
    assert error.code == 'BROKER_PROCESS_HANDOVER_REFUSED'
    # There is exactly **one** closer of the original handle of the
    # process and of its thread: the recovery of the façade and the
    # direct cleanup of the failed creation are one owner.
    assert closed_handles.count(kernel32.process_handle) == 1, \
        'the original handle of the process was closed twice'
    assert closed_handles.count(kernel32.thread_handle) == 1, \
        'the original handle of the thread was closed twice'


# -- N10-R03: one notification for every confirmed close -------------------

def test_n10_r03_every_confirmed_close_notifies_the_owner_of_the_handle(tmp_path):
    """N10-R03 (M06): the notification of a close is one notification.

    Obligation: a reader that really stopped and whose read end could
    not be closed by the first attempt is closed by the pending pass of
    the round, and that confirmed close notifies the **owner** of the
    handle: the reader learns that its handle is gone, the pending
    table and the retained resources of the round agree with it, and
    the next stop of the round never closes the same original handle a
    second time - a handle that the operating system may have reused.

    Entry: ``BrokerCore._close_one_reader``,
    ``BrokerCore._note_closed_handle`` and
    ``_PendingResources.close_all``.  Trigger: the first close of the
    read end of a stopped reader fails and the pending pass succeeds.
    Oracle: the reader holds no handle any more, the pending table does
    not name it and the handle was closed exactly once.  Negative: a
    second stop never closes the handle again.  Returned state: the
    facts of the two stops agree with each other.  Salvage: the owner of
    the test releases the handles that the product kept.
    """
    win32 = RecordingWin32()
    core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path)
    try:
        core.arm()
        core.launch()
        reader = core.readers[0]
        target = reader.handle
        assert target is not None, 'the reader never got a handle'
        state = {'failed': False}
        original_close = win32.close_handle

        def close_handle(handle):
            if handle == target and not state['failed']:
                # The first close of the read end of the reader fails.
                state['failed'] = True
                win32.calls.append(('close_handle', handle))
                raise BrokerError('BROKER_HANDLE_CLOSE_FAILED')
            original_close(handle)

        win32.close_handle = close_handle
        core.stop('STOP')
        first = {'reader_handle': reader.handle,
                 'closed': win32.closed.count(target),
                 'pending': [item['handle'] for item in core._pending.pending()],
                 'retained': [item['handle']
                              for item in core._retained_resources],
                 'state': core.state}
        write_phase('r03-first', first)
        assert state['failed'], 'the targeted close never failed'
        # The confirmed close of the pending pass notified the owner.
        assert reader.handle is None, \
            'the reader still names a handle that was really closed'
        assert target not in [item['handle'] for item in core._pending.pending()]
        assert target not in [item['handle']
                              for item in core._retained_resources]
        assert win32.closed.count(target) == 1

        # The next stop of the round never closes the same handle again.
        core.stop('STOP')
        second = {'reader_handle': reader.handle,
                  'closed': win32.closed.count(target),
                  'state': core.state}
        write_phase('r03-second', second)
        assert win32.closed.count(target) == 1, \
            'the read end was closed a second time'
        assert reader.handle is None
    finally:
        for handle in list(win32.live):
            RecordingWin32.close_handle(win32, handle)


# -- N10-R04: the aggregate finds the partial channel ---------------------

def test_n10_r04_the_launch_aggregate_finds_the_partial_channel():
    """N10-R04 (M07): the partial channel has an owner.

    Obligation: the channel of a launch registers itself with the
    **aggregate** of the launch before it builds anything, so that a
    channel whose reader thread did not start is found by the outer
    owner of the launch and never through a local variable that is
    ``None`` at that moment.  The process helper never closes the
    standard input and the standard output of a process whose channel
    took them: the channel is coordinated first and the files of the
    process are closed by the channel alone.  Facts that are not
    complete keep the original owner.

    Entry: ``StreamChannel.__init__``, ``_LaunchAggregate.retain``,
    ``_LaunchAggregate.release`` and ``_adopt_broker_process``.
    Trigger: the reader thread of the channel really starts and the
    start of the thread does not return, so that the construction of the
    channel fails with the channel already half built.  Oracle: the
    aggregate found the partial channel, the files of the process were
    closed by the channel and never by the process helper.  Negative:
    the process helper never closes the files of a process whose
    channel took them.  Returned state: the facts of the aggregate
    name what it released.  Salvage: the owner of the test releases the
    handles that the product kept.

    RECONCILIATION (N1 correction 12): the **ownership premise** of the
    group is built before the cleanup is expected.  The original
    process is bound to the **same** aggregate and registered with the
    **same** table of the launcher through the production adoption -
    ``_adopt_broker_process`` - and the channel is built by the
    production ``channel_factory`` of that adoption.  The process of the
    launch is therefore coordinated by the aggregate that owns it and
    not by a stand-in: the release of the aggregate coordinates the
    channel **before** the process, the raw files of the process are
    never closed under a live channel endpoint and the incomplete start
    keeps its owner.

    The **recovery** is the same owner: the reader of the channel really
    ends and the second release of the table coordinates the channel
    again.  The confirmed close happens exactly once, the process is
    never terminated or waited for a second time and the table of the
    launcher is empty only when every item of the launch is really
    released.
    """
    order = []
    read_release = threading.Event()
    # The event of the worker that is really inside its read.  It is
    # published **before** the wait of the primitive and it is the
    # barrier of the group: a start that returned does not prove that a
    # read primitive is still active.
    worker_inside = threading.Event()

    class Process:
        pid = 4242
        returncode = None

        def __init__(self):
            self.terminated = 0
            self.waited = 0
            self.closed = []
            self.stdin = type('S', (), {'close': self._close})()
            self.stdout = type('S', (), {'close': self._close})()

        def _close(self):
            self.closed.append('stream')
            order.append('process_stream')

        def terminate(self):
            self.terminated += 1
            order.append('terminate')

        def wait(self, timeout=None):
            self.waited += 1
            order.append('wait')
            return 0

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            return 'REQUESTED'

        def close_handle(self, handle):
            return None

        def read_stream(self, handle, size):
            # The reader of the chain stays inside its read: the
            # channel is partial and its close can never confirm the
            # read end while the reader is alive.
            # The event is published **before** the wait of the
            # primitive: the group waits for it before it injects the
            # interruption of the start.
            worker_inside.set()
            read_release.wait(20.0)
            return b''

        def write_stream(self, handle, data):
            return len(data)

    class CountingFile:
        """A file of the channel that counts its own closes."""

        def __init__(self, name):
            self.name = name
            self.closes = 0

        def close(self):
            self.closes += 1
            order.append('channel-' + self.name)
            return True

    clock = ManualClock(1000.0)
    custody = _LauncherCustody()
    aggregate = _LaunchAggregate(custody=custody)
    process = Process()
    read_file = CountingFile('read')
    write_file = CountingFile('write')
    original_start = threading.Thread.start
    # The ONE context of the round: the bounded join of the reader of
    # the channel is bounded by it and the join never waits longer than
    # the round allows.
    context = _RoundContext(clock=clock)
    context.bind_absolute_deadline(clock.value + 0.2)

    def failing_start(self):
        # The thread of the reader of the channel really starts and its
        # start does not return: the channel is half built and the
        # aggregate is its owner.
        original_start(self)
        if self.name == 'lvw-native-custody-channel':
            # RECONCILIATION (N1 correction 13): the interruption is
            # injected **after** the worker of the read really entered
            # its read primitive.  A start that returned does not prove
            # that a read is still active: the reader of the channel
            # may end before the cleanup of the launch and it may then
            # release the channel correctly.  The group therefore waits
            # for the explicit event of the worker before it injects the
            # interruption.
            assert worker_inside.wait(20.0), \
                'the worker of the read never entered its read primitive'
            raise RuntimeError('thread_start_failed_after_start')

    def channel_factory():
        """Build the **partial** channel of the launch.

        The channel registers itself with the aggregate of the launch
        before it builds anything and the start of its reader thread
        does not return: the channel is half built and the aggregate is
        its owner.
        """
        read_endpoint = _WindowsPipeEndpoint(
            file_object=read_file, name='channel-read', api=Api(),
            clock=clock, handle=900, context=context)
        write_endpoint = _WindowsPipeEndpoint(
            file_object=write_file, name='channel-write', api=Api(),
            clock=clock, handle=901, context=context)
        return StreamChannel(None, None, read_endpoint=read_endpoint,
                             write_endpoint=write_endpoint,
                             custody=aggregate, clock=clock, context=context)

    # CORRECTION 20 (M3): the release of the gate of the reader is
    # guarded: a cancellation of it never skips the join that follows it
    # and it never replaces the failure that is already unwinding.
    launch_cleanup_errors = []
    launch_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this region exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the region without a
    # durable document.
    launch_cleanup_facts = _cleanup_facts('partial-launch')
    try:
        launch_cleanup_facts['executed'] = True
        with unittest.mock.patch.object(threading.Thread, 'start',
                                        failing_start):
            with pytest.raises(RuntimeError):
                # The production adoption binds the **original process**
                # to the aggregate and registers it with the table of
                # the launcher **before** the channel of the launch is
                # built.
                _adopt_broker_process(process, channel_factory=channel_factory,
                                      executable='C:/python.exe',
                                      executable_sha256='a' * 64,
                                      aggregate=aggregate, custody=custody)
        # The partial channel is found **through the aggregate** and not
        # through a local variable of the adoption.
        channel = aggregate.channel
        assert channel is not None, \
            'the partial channel lost its owner'
        facts = {'aggregate_channel': channel is not None,
                 'read_closes': read_file.closes,
                 'write_closes': write_file.closes,
                 'process_closed': list(process.closed),
                 'terminated': process.terminated,
                 'waited': process.waited,
                 'order': list(order),
                 'custody': [(item['kind'], repr(item['resource']))
                             for item in custody.items()]}
        write_phase('r04-partial', facts)
        # The channel of the launch was coordinated **before** the
        # process: the files of the process belong to the channel.
        assert order and order[0] == 'channel-write', \
            'the channel of the launch was not coordinated before the process'
        assert order == ['channel-write', 'terminate', 'wait'], \
            'the release of the launch did not follow the dependency order'
        # The process of the launch was coordinated by the aggregate that
        # owns it: it was terminated and it was waited for.
        assert process.terminated == 1
        assert process.waited == 1
        # The files of the process were not closed by the process
        # helper: the channel owns them.
        assert process.closed == [], \
            'the process helper closed the files of the channel'
        # The read end of the channel is never closed under a live
        # reader: the incomplete start keeps its owner.
        assert read_file.closes == 0, \
            'the read end was closed under a live reader'
        assert write_file.closes == 1
        assert aggregate.channel is channel, \
            'the incomplete start lost its owner'
        assert any(item['kind'] == 'channel' for item in custody.items()), \
            'the incomplete channel lost its owner in the table'

        # The **same** owner coordinates the launch again: the reader of
        # the channel really ends and the second release of the table
        # closes the read end exactly once.
        read_release.set()
        reader_thread = getattr(channel, '_thread', None)
        if reader_thread is not None:
            reader_thread.join(10.0)
            assert not reader_thread.is_alive(), \
                'the reader thread of the channel was left behind'
        report = custody.release()
        facts = {'report': report,
                 'read_closes': read_file.closes,
                 'write_closes': write_file.closes,
                 'process_closed': list(process.closed),
                 'terminated': process.terminated,
                 'waited': process.waited,
                 'order': list(order),
                 'custody': [(item['kind'], repr(item['resource']))
                             for item in custody.items()]}
        write_phase('r04-release', facts)
        assert 'channel' in (report.get('released') or []), \
            'the same owner did not coordinate the channel again'
        assert read_file.closes == 1, \
            'the read end of the channel was not closed by its owner'
        assert write_file.closes == 1, \
            'the write end of the channel was closed a second time'
        # The process was never terminated or waited for a second time.
        assert process.terminated == 1, \
            'the recovery terminated the process of the launch a second time'
        assert process.waited == 1, \
            'the recovery waited for the process of the launch a second time'
        assert process.closed == []
        # The table of the launcher is empty only when every item of the
        # launch is really released.
        assert custody.items() == [], \
            'the table of the launcher kept an item of a released launch'
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        launch_cleanup_facts['original'] = _original_facts()
        # The salvage of the owner of the test: the thread that the
        # channel really started is joined with a bounded wait.
        #
        # CORRECTION 20 (M3): the release of the gate is guarded and the
        # exact object of a cancellation of it is retained.
        _release_gate(read_release.set, launch_cleanup_errors,
                      launch_interrupts)
        launch_cleanup_facts['actions'].append('release:gate')
        partial = aggregate.channel
        # CORRECTION 22 (M3): the lookup of the thread of the owner is
        # guarded: a failure of it is retained with its exact type and
        # its exact detail and it never skips the priority that follows.
        thread = None
        try:
            thread = getattr(partial, '_thread', None)
        except BaseException as error:  # noqa: BLE001 - it stays visible
            launch_cleanup_errors.append(
                {'kind': 'OWNER_THREAD', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(launch_interrupts, error)
        launch_join = None
        if thread is not None:
            # CORRECTION 21 (M3): the join of the reader is **guarded**
            # and the priority of the failures is enforced **after** it:
            # a failure of the join never replaces the failure that is
            # already unwinding.
            launch_join = _join_owner('launch-reader', thread,
                                      launch_cleanup_errors,
                                      launch_interrupts, seconds=10.0)
            launch_cleanup_facts['actions'].append('join:launch-reader')
        launch_cleanup_facts['alive'] = _owner_alive(launch_join)
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures.
        _publish_cleanup(
            launch_cleanup_facts,
            lambda: write_phase('r04-partial-cleanup',
                                launch_cleanup_facts),
            launch_cleanup_errors, launch_interrupts,
            verdict=lambda: _cleanup_verdict(
                launch_cleanup_errors, None,
                'the cleanup of the launch met'))
        # CORRECTION 22 (M3): the priority of the failures is enforced
        # **after** every action of the cleanup: a pending interruption
        # is never raised while the owner of the round was left behind.
        _raise_first_interruption(launch_interrupts)
        # the ordinary proof of the round: it runs **after** the join and
        # it never replaces the failure that is already unwinding.
        if sys.exc_info()[0] is None:
            assert not _owner_alive(launch_join), \
                'the reader thread of the channel was left behind'
        # the ordinary errors of the cleanup are **consumed**: they fail
        # the round instead of being recorded and forgotten.
        if launch_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the launch met %s'
                                 % (launch_cleanup_errors,))


# -- N10-R05: an incomplete channel keeps its owner ------------------------

def test_n10_r05_an_incomplete_channel_keeps_its_owner_and_the_cancel(tmp_path):
    """N10-R05 (M07): a close that returned is not a release.

    Obligation: the close of the channel of a launch is a release only
    when **every** fact of it is closed - the reader, the two ends, the
    workers of the endpoints and the original handles of their threads.
    A close that returned incomplete facts keeps the channel with its
    original reference and its owner, and the same launch coordinates
    the channel **before** the process.  The safe steps of the release
    run before the original cancellation of the launch propagates: the
    original object is the one that leaves, the cancellation of the
    recovery stays reachable next to it and the recovery of the launcher
    cancels in the same way.

    Entry: ``_LaunchAggregate.release``, ``_adopt_broker_process`` and
    ``_LauncherCustody.release``.  Trigger: the close of the channel
    returns without a confirmed end and it is cancelled by the
    recovery.  Oracle: the process was terminated and waited **after**
    the channel was coordinated, the channel kept its owner, the
    original failure object is the one that propagated and the
    cancellation of the recovery is reachable next to it.  Negative: a
    returned close is never taken for a release.  Returned state: the
    facts of the aggregate name what it kept.  Salvage: the recovery of
    the launcher releases what it may.

    CORRECTION 12 (M07-A): the retry of an unresolved **original raw
    stream** of a launch is cancelled: the original cancellation is the
    error that leaves and the stream keeps its owner.  A cancelled
    retry never forgets a stream and it never replaces the failure that
    it could not confirm.
    """
    order = []

    class Process:
        pid = 4242
        returncode = None

        def __init__(self):
            self.terminated = 0
            self.waited = 0

        def terminate(self):
            self.terminated += 1
            order.append('terminate')

        def wait(self, timeout=None):
            self.waited += 1
            order.append('wait')
            return 0

    class CancellingChannel:
        """A channel whose close returns without a confirmed end and
        whose close is cancelled by the recovery."""

        reader_finished = True

        def __init__(self):
            self.closes = 0

        def close(self):
            self.closes += 1
            order.append('channel')
            raise KeyboardInterrupt('channel_close_cancelled')

    class FailingBrokerProcess:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('broker_process_construction_failed')

    process = Process()
    channel = CancellingChannel()
    custody = _LauncherCustody()
    aggregate = _LaunchAggregate(custody=custody)
    original = broker_module.BrokerProcess
    broker_module.BrokerProcess = FailingBrokerProcess
    try:
        with pytest.raises(RuntimeError) as info:
            _adopt_broker_process(process, channel_factory=lambda: channel,
                                  executable='C:/python.exe',
                                  executable_sha256='a' * 64,
                                  aggregate=aggregate, custody=custody)
    finally:
        broker_module.BrokerProcess = original
    facts = {'channel_closes': channel.closes,
             'terminated': process.terminated,
             'waited': process.waited,
             'order': list(order),
             'aggregate_channel': aggregate.channel is channel,
             'custody': [(item['kind'], repr(item['resource']))
                         for item in custody.items()],
             'error_type': type(info.value).__name__,
             'error_detail': getattr(info.value, 'detail', None)}
    write_phase('r05-adoption', facts)
    # The original failure object is the one that propagated.
    assert str(info.value) == 'broker_process_construction_failed'
    # The safe steps of the release ran before the failure left: the
    # channel was coordinated **before** the process.
    assert channel.closes == 1
    assert order == ['channel', 'terminate', 'wait'], \
        'the channel of the launch was not coordinated before the process'
    assert process.terminated == 1
    assert process.waited == 1
    # The cancellation of the recovery is reachable next to the original
    # failure: the primary failure and the cancellation coexist.
    cancellation = getattr(info.value, 'lvw_cancelled', None)
    assert isinstance(cancellation, KeyboardInterrupt), \
        'the cancellation of the recovery was swallowed'
    assert str(cancellation) == 'channel_close_cancelled'
    # The incomplete facts kept the channel with its owner.
    assert aggregate.channel is channel, \
        'an incomplete channel lost its owner'
    assert any(item['kind'] == 'channel' for item in custody.items())

    # The recovery of the launcher cancels in the same way: the safe
    # steps run first and the cancellation of the recovery is the error
    # that leaves.  The recovery runs on a **fresh** launch and on a
    # fresh table of the launcher, so that the order that is observed
    # belongs to that launch alone.
    order[:] = []
    process2 = Process()
    channel2 = CancellingChannel()
    custody2 = _LauncherCustody()

    class FailingBrokerProcess2:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('broker_process_construction_failed')

    original = broker_module.BrokerProcess
    broker_module.BrokerProcess = FailingBrokerProcess2
    try:
        with pytest.raises(RuntimeError):
            _adopt_broker_process(process2, channel_factory=lambda: channel2,
                                  executable='C:/python.exe',
                                  executable_sha256='a' * 64,
                                  custody=custody2)
    finally:
        broker_module.BrokerProcess = original
    order[:] = []
    with pytest.raises(KeyboardInterrupt) as recovery:
        custody2.release()
    facts = {'order': list(order),
             'terminated': process2.terminated,
             'waited': process2.waited,
             'error_type': type(recovery.value).__name__,
             'custody': [(item['kind'], repr(item['resource']))
                         for item in custody2.items()]}
    write_phase('r05-recovery', facts)
    assert str(recovery.value) == 'channel_close_cancelled'
    # RECONCILIATION (N1 correction 11): the process of this launch was
    # **already** released by the adoption phase: its exit was really
    # confirmed and its original handle was released with it.  The
    # recovery of the launcher therefore coordinates the channel only
    # and it never repeats the termination and the wait of a process
    # that was already proved released.  The old expectation that the
    # recovery repeats them contradicted the ownership of the process
    # and it is replaced by the boundary that really holds.
    assert order == ['channel'], \
        'the recovery of the launcher did not coordinate the channel only'
    assert process2.terminated == 1, \
        'the recovery terminated the process of the launch a second time'
    assert process2.waited == 1, \
        'the recovery waited for the process of the launch a second time'
    # The channel that could not be released keeps its owner.
    assert any(item['kind'] == 'channel' for item in custody2.items())

    # -- PHASE THREE: a launch whose **original handle** was still
    #    retained is coordinated **again** by the recovery of the
    #    launcher.  The recovery retries the incomplete parts and it
    #    never opens a budget of its own.
    order[:] = []

    class RetainedProcess:
        """A process whose first wait failed: it keeps its owner."""

        pid = 4243
        returncode = None

        def __init__(self):
            self.terminated = 0
            self.waited = 0

        def terminate(self):
            self.terminated += 1
            order.append('terminate')

        def wait(self, timeout=None):
            self.waited += 1
            order.append('wait')
            if self.waited == 1:
                raise RuntimeError('wait_failed')
            return 0

    class FailingBrokerProcess3:
        def __init__(self, *args, **kwargs):
            raise RuntimeError('broker_process_construction_failed')

    process3 = RetainedProcess()
    channel3 = CancellingChannel()
    custody3 = _LauncherCustody()

    original = broker_module.BrokerProcess
    broker_module.BrokerProcess = FailingBrokerProcess3
    try:
        with pytest.raises(RuntimeError):
            _adopt_broker_process(process3, channel_factory=lambda: channel3,
                                  executable='C:/python.exe',
                                  executable_sha256='a' * 64,
                                  custody=custody3)
    finally:
        broker_module.BrokerProcess = original
    # The adoption could not release the process: it keeps its owner.
    assert process3.waited == 1
    kept = [item for item in custody3.items() if item['kind'] == 'process']
    assert kept, 'the process that could not be released lost its owner'
    order[:] = []
    with pytest.raises(KeyboardInterrupt):
        custody3.release()
    facts = {'order': list(order),
             'terminated': process3.terminated,
             'waited': process3.waited,
             'custody': [(item['kind'], repr(item['resource']))
                         for item in custody3.items()]}
    write_phase('r05-retained-recovery', facts)
    # The channel is coordinated first and the **retained** process is
    # coordinated again: the recovery really retries the incomplete
    # part and it never releases the channel alone.
    assert order == ['channel', 'terminate', 'wait'], \
        'the recovery did not coordinate the retained process again'
    assert process3.terminated == 2
    assert process3.waited == 2

    # -- N1 correction 12 (M07-A): a **cancelled** retry of an
    #    unresolved original raw stream keeps the owner of the stream
    #    and the original cancellation is the error that leaves.
    #    RECONCILIATION (N1 correction 13): the phase runs on a
    #    **scoped** table of the launcher.  The table of the launcher
    #    of this package is shared by the whole batch and the context
    #    that another check of the batch bound to it is **not** the
    #    context of this launch: the bound of another round would
    #    refuse the retry of the raw stream before it starts and the
    #    cancellation would never be observed at all.  The production
    #    table is used and it is never emptied by hand.
    scoped = _LauncherCustody()
    with unittest.mock.patch.object(broker_module, '_LAUNCHER_CUSTODY',
                                    scoped):
        holder = m07a_interrupted_launch(tmp_path, sealed_plan(),
                                         failures=1, cancel=True)
        stdout = holder['stdout']
        aggregate = holder['aggregate'][0] if holder['aggregate'] else None
        assert aggregate is not None, 'the interrupted launch lost its owner'
        release_retained_launches()
        assert stdout.attempts == 1, \
            'the raw stream was not closed by the first release'
        assert stdout.confirmed == 0
        with pytest.raises(KeyboardInterrupt):
            release_retained_launches()
        assert stdout.attempts == 2, \
            'the same owner did not retry the raw stream of the launch'
        assert stdout.confirmed == 0, \
            'the cancelled retry of the raw stream was read as a close'
        owned = [item for item in _launcher_custody_items()
                 if item['kind'] == 'stdout' and item['resource'] is stdout]
        assert owned, 'the cancelled retry forgot the owner of the raw stream'
        assert [item['name'] for item in aggregate.raw_streams] == ['stdout'], \
            'the launch forgot a raw stream that was never closed'
        # The **final** recovery of the **same** owner after the test
        # released its fault seam: the stream is really closed, the
        # owner of it is released and the table of the launcher is
        # empty again.  The recovery is the same owner and it never
        # opens a budget of its own.
        stdout.cancel = False
        release_retained_launches()
        facts = {'attempts': stdout.attempts, 'confirmed': stdout.confirmed,
                 'owned': len([item for item in _launcher_custody_items()
                               if item['kind'] == 'stdout'
                               and item['resource'] is stdout]),
                 'raw_streams': [item['name']
                                 for item in aggregate.raw_streams],
                 'table': [(item['kind'], repr(item['resource']))
                           for item in _launcher_custody_items()]}
        write_phase('r05-final-recovery', facts)
        assert stdout.confirmed == 1, \
            'the final recovery did not close the raw stream of the launch'
        assert stdout.closed is True
        assert not [item for item in _launcher_custody_items()
                    if item['kind'] == 'stdout'
                    and item['resource'] is stdout], \
            'the table of the launcher kept the closed raw stream'
        assert aggregate.raw_streams == [], \
            'the launch still owns a raw stream that was really closed'

    # -- N1 correction 13 (M07-A.3): the **current** minimum of the
    #    original round is read again before **each** initial raw close.
    #    A context that was tightened by the wait of the process or by a
    #    previous close of an original refuses the next close: the
    #    original keeps its owner and its identity, no new close is
    #    started and no fresh cleanup lease is opened.
    class BoundStream:
        """One original raw file that counts its own closes.

        The file carries two named seams: an **ordinary** failure that
        happens once and a callback that the group uses to tighten the
        original round between two closes.  The ordinary failure is the
        fault seam of the group: it is released by its own first
        attempt and the second attempt of the **same** owner really
        closes the original.
        """

        def __init__(self, name, on_close=None, failure=None):
            self.name = name
            self.attempts = 0
            self.closed = False
            self.on_close = on_close
            self._failure = failure
            # The **original** fault object of the seam: it is kept so
            # that the identity of the failure is a fact and not a
            # label.
            self.fault = None

        def close(self):
            self.attempts += 1
            if self._failure is not None:
                error = self._failure
                self._failure = None
                self.fault = error
                raise error
            if self.on_close is not None:
                callback = self.on_close
                self.on_close = None
                callback()
            self.closed = True
            return True

    class BoundProcess:
        """A process whose wait may tighten the original round."""

        pid = 4246
        returncode = 0

        def __init__(self, *, stdin, stdout, on_wait=None):
            self.stdin = stdin
            self.stdout = stdout
            self.terminated = 0
            self.waited = 0
            self.on_wait = on_wait

        def terminate(self):
            self.terminated += 1

        def wait(self, timeout=None):
            self.waited += 1
            if self.on_wait is not None:
                callback = self.on_wait
                self.on_wait = None
                callback()
            return 0

    def bound_launch(context, process):
        """One no-channel launch that the owner of the table coordinates."""
        custody = _LauncherCustody()
        aggregate = _LaunchAggregate(custody=custody, context=context)
        aggregate.bind_process(process)
        custody.retain('aggregate', aggregate, 'launch')
        custody.retain('process', process, 'popened', launch=aggregate)
        return custody, aggregate

    # -- the case one: the round is tightened **during the wait** of the
    #    process.  The initial raw closes are refused and the originals
    #    keep their identity.
    clock_one = ManualClock(1000.0)
    context_one = _RoundContext(clock=clock_one)
    context_one.bind_absolute_deadline(clock_one.value + 10.0)
    stdin_one = BoundStream('stdin')
    stdout_one = BoundStream('stdout')
    process_one = BoundProcess(
        stdin=stdin_one, stdout=stdout_one,
        on_wait=lambda: context_one.bind_absolute_deadline(clock_one.value - 1.0))
    custody_one, aggregate_one = bound_launch(context_one, process_one)
    report_one = custody_one.release()
    facts = {'report': report_one,
             'stdin_attempts': stdin_one.attempts,
             'stdout_attempts': stdout_one.attempts,
             'raw_streams': [item['name']
                             for item in aggregate_one.raw_streams],
             'owned': [(item['kind'], repr(item['resource']))
                       for item in custody_one.items()],
             'terminated': process_one.terminated,
             'waited': process_one.waited}
    write_phase('r05-bound-during-wait', facts)
    assert stdin_one.attempts == 0, \
        'the input was closed although the round had expired'
    assert stdout_one.attempts == 0, \
        'the output was closed although the round had expired'
    assert [item['name'] for item in aggregate_one.raw_streams] == \
        ['stdin', 'stdout'], \
        'the launch lost an original that it may not close any more'
    owned_one = [item for item in custody_one.items()
                 if item['kind'] in ('stdin', 'stdout')]
    assert len(owned_one) == 2, \
        'the table of the launcher lost the identity of an original'

    # -- the case two: the round is tightened **between** two initial
    #    raw closes.  The close that follows the tightening is refused.
    clock_two = ManualClock(1000.0)
    context_two = _RoundContext(clock=clock_two)
    context_two.bind_absolute_deadline(clock_two.value + 10.0)
    stdin_two = BoundStream(
        'stdin',
        on_close=lambda: context_two.bind_absolute_deadline(
            clock_two.value - 1.0))
    stdout_two = BoundStream('stdout')
    process_two = BoundProcess(stdin=stdin_two, stdout=stdout_two)
    custody_two, aggregate_two = bound_launch(context_two, process_two)
    report_two = custody_two.release()
    facts = {'report': report_two,
             'stdin_attempts': stdin_two.attempts,
             'stdout_attempts': stdout_two.attempts,
             'raw_streams': [item['name']
                             for item in aggregate_two.raw_streams],
             'owned': [(item['kind'], repr(item['resource']))
                       for item in custody_two.items()]}
    write_phase('r05-bound-between-closes', facts)
    assert stdin_two.attempts == 1, \
        'the input was not closed although the round was still positive'
    assert stdin_two.closed is True
    assert stdout_two.attempts == 0, \
        'the output was closed although the round had expired'
    assert [item['name'] for item in aggregate_two.raw_streams] == ['stdout'], \
        'the launch owns an original whose close was confirmed'

    # -- the case three: the positive case.  Every initial close of a
    #    launch with a positive remaining is really attempted.
    clock_three = ManualClock(1000.0)
    context_three = _RoundContext(clock=clock_three)
    context_three.bind_absolute_deadline(clock_three.value + 10.0)
    stdin_three = BoundStream('stdin')
    stdout_three = BoundStream('stdout')
    process_three = BoundProcess(stdin=stdin_three, stdout=stdout_three)
    custody_three, aggregate_three = bound_launch(context_three, process_three)
    report_three = custody_three.release()
    facts = {'report': report_three,
             'stdin_attempts': stdin_three.attempts,
             'stdout_attempts': stdout_three.attempts,
             'raw_streams': [item['name']
                             for item in aggregate_three.raw_streams]}
    write_phase('r05-bound-positive', facts)
    assert stdin_three.attempts == 1
    assert stdout_three.attempts == 1
    assert aggregate_three.raw_streams == [], \
        'the launch owns an original whose close was confirmed'

    # -- the round of the first case is **expired** and the deadline of
    #    a round is **one way**: it may only be shortened.  A repeated
    #    release of the **same** owner therefore starts **no** new close,
    #    the exact originals keep their owner and the current bound of
    #    the round is the expired one.  The group never renews a lease,
    #    it never replaces the context of the round and it never rewinds
    #    a clock.
    repeated_one = custody_one.release()
    facts = {'repeated': repeated_one,
             'stdin_attempts': stdin_one.attempts,
             'stdout_attempts': stdout_one.attempts,
             'stdin_closed': stdin_one.closed,
             'stdout_closed': stdout_one.closed,
             'raw_streams': [item['name']
                             for item in aggregate_one.raw_streams],
             'owned': [(item['kind'], repr(item['resource']))
                       for item in custody_one.items()],
             'absolute_deadline': context_one.absolute_deadline}
    write_phase('r05-bound-expired-repeat', facts)
    assert stdin_one.attempts == 0, \
        'the expired round started a new close of the input'
    assert stdout_one.attempts == 0, \
        'the expired round started a new close of the output'
    assert stdin_one.closed is False
    assert stdout_one.closed is False
    assert [item['name'] for item in aggregate_one.raw_streams] == \
        ['stdin', 'stdout'], \
        'the expired round lost the identity of an original'
    assert context_one.absolute_deadline == clock_one.value - 1.0, \
        'the expired round renewed its own deadline'

    # -- the successful unresolved-only retry: it happens in a
    #    **separate** original round that is still **positive** and it
    #    uses the **same** owner, the **same** original context and the
    #    **same** original deadline for both attempts.  The ordinary
    #    failure of the close is the fault seam of the group: the first
    #    attempt retains the original with its identity and the second
    #    attempt of the same owner really closes it.
    clock_four = ManualClock(1000.0)
    context_four = _RoundContext(clock=clock_four)
    context_four.bind_absolute_deadline(clock_four.value + 10.0)
    stdin_four = BoundStream('stdin')
    stdout_four = BoundStream(
        'stdout', failure=RuntimeError('stdout_close_failed'))
    process_four = BoundProcess(stdin=stdin_four, stdout=stdout_four)
    custody_four, aggregate_four = bound_launch(context_four, process_four)
    report_four = custody_four.release()
    facts = {'report': report_four,
             'stdin_attempts': stdin_four.attempts,
             'stdout_attempts': stdout_four.attempts,
             'stdout_closed': stdout_four.closed,
             'raw_streams': [item['name']
                             for item in aggregate_four.raw_streams],
             'owned': [(item['kind'], repr(item['resource']))
                       for item in custody_four.items()],
             'absolute_deadline': context_four.absolute_deadline}
    write_phase('r05-owned-retry', facts)
    assert stdout_four.attempts == 1, \
        'the output of the launch was not closed by the first release'
    assert stdout_four.closed is False, \
        'the failed close of the output was read as a close'
    # The **original** fault object of the seam is the failure that the
    # product names and the identity of it is kept.
    assert stdout_four.fault is not None, \
        'the ordinary failure of the close never happened'
    assert aggregate_four.facts.get('failures', {}).get('stdout') \
        == 'RuntimeError', \
        'the ordinary failure of the close was not named by the product'
    assert [item['name'] for item in aggregate_four.raw_streams] == \
        ['stdout'], \
        'the launch lost the unresolved original of its round'
    owned_four = [item for item in custody_four.items()
                  if item['kind'] == 'stdout']
    assert owned_four, \
        'the unresolved original of the round lost its owner'
    # The fault seam of the group is released by its own first attempt:
    # the **same** owner retries the unresolved original under the
    # **same** original context and the **same** original deadline.
    recovered_four = custody_four.release()
    facts = {'recovered': recovered_four,
             'stdin_attempts': stdin_four.attempts,
             'stdout_attempts': stdout_four.attempts,
             'stdout_closed': stdout_four.closed,
             'raw_streams': [item['name']
                             for item in aggregate_four.raw_streams],
             'owned': [(item['kind'], repr(item['resource']))
                       for item in custody_four.items()],
             'absolute_deadline': context_four.absolute_deadline}
    write_phase('r05-owned-retry-recovery', facts)
    assert stdout_four.attempts == 2, \
        'the same owner did not retry the unresolved original'
    assert stdout_four.closed is True, \
        'the same owner did not really close the unresolved original'
    assert aggregate_four.raw_streams == [], \
        'the launch still owns an original that was really closed'
    assert custody_four.items() == [], \
        'the table of the launcher kept an item of the launch'
    # The deadline of the round was never renewed and the context of
    # the round is the one of the first attempt.
    assert context_four.absolute_deadline == clock_four.value + 10.0, \
        'the round renewed its own deadline'


# -- N10-R06: the admission of a generation -------------------------------

def test_n10_r06_an_expired_or_cancelled_call_performs_no_primitive_call():
    """N10-R06 (M08): the admission comes before the side effect.

    Obligation: a read or a write of an endpoint that enters when the
    round is already expired or already cancelled is refused **before**
    the worker of the endpoint is started, before the request is
    submitted and before the primitive is called: the number of the
    real primitive calls of such a call is zero.  The check and the
    admission of the generation are one atomic step and a cancellation
    is never a remedy that is applied after the submission.

    Entry: ``_WindowsPipeEndpoint.read``,
    ``_WindowsPipeEndpoint.write`` and
    ``_WindowsPipeEndpoint._admission``.  Trigger: the call enters with
    an expired deadline and with a cancel flag that is already set, for
    the read and for the write.  Oracle: the refusal is named and no
    worker was started.  Negative: the endpoint never starts a worker
    for a refused call.  Returned state: the facts of the endpoint name
    no worker.  Salvage: the owner of the test closes the endpoint at
    the end.
    """
    clock = ManualClock(1000.0)
    calls = []

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            calls.append('cancel')
            return 'REQUESTED'

        def close_handle(self, handle):
            calls.append('close_handle')
            return None

        def read_stream(self, handle, size):
            calls.append('read')
            return b''

        def write_stream(self, handle, data):
            calls.append('write')
            return len(data)

    endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('read'),
                                    name='inprocess', api=Api(), clock=clock,
                                    handle=702)
    # CORRECTION 22 (M3): the errors of the closes of the endpoints of
    # this round are **retained**: a close that failed never replaces the
    # failure that is already unwinding.
    r06_cleanup_errors = []
    r06_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this region exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the region without a
    # durable document.
    r06_cleanup_facts = _cleanup_facts('r06-close')
    try:
        r06_cleanup_facts['executed'] = True
        with pytest.raises(BrokerError) as info:
            endpoint.read(clock.value - 1.0, None)
        assert info.value.code == 'BROKER_PIPE_TIMEOUT'
        assert calls == [], 'a primitive was called by a refused read'
        assert endpoint._reader is None, \
            'the refused read started a worker of the endpoint'
        assert endpoint.facts.get('retained_workers', 0) == 0

        cancel = _ChannelCancel()
        cancel.set()
        with pytest.raises(BrokerError) as info:
            endpoint.read(None, cancel)
        assert info.value.code == 'BROKER_PIPE_CANCELLED'
        assert calls == [], 'a primitive was called by a refused read'
        assert endpoint._reader is None, \
            'the refused read started a worker of the endpoint'

        with pytest.raises(BrokerError) as info:
            endpoint.write(b'abc', clock.value - 1.0, None)
        assert info.value.code == 'BROKER_PIPE_TIMEOUT'
        assert calls == [], 'a primitive was called by a refused write'
        assert endpoint._writer is None, \
            'the refused write started a worker of the endpoint'

        with pytest.raises(BrokerError) as info:
            endpoint.write(b'abc', None, cancel)
        assert info.value.code == 'BROKER_PIPE_CANCELLED'
        assert calls == [], 'a primitive was called by a refused write'
        assert endpoint._writer is None, \
            'the refused write started a worker of the endpoint'
        write_phase('r06-admission', {'calls': list(calls),
                                      'reader': endpoint._reader is not None,
                                      'writer': endpoint._writer is not None})

        # -- the linearization point of the admission (N1 correction
        #    11, M08): the request is admitted **before** the worker of
        #    the endpoint is started and it is admitted **again** after
        #    the worker is ready and immediately before the request is
        #    submitted.  A cancellation or an expiry that is published
        #    **before** that final admission causes **zero** primitive
        #    calls: the request never reaches the worker.
        endpoint2 = _WindowsPipeEndpoint(file_object=_FakeFile('read2'),
                                         name='inprocess-2', api=Api(),
                                         clock=clock, handle=703)
        try:
            cancel2 = _ChannelCancel()
            # The initial admission of the generation succeeds: the
            # round is neither expired nor cancelled.
            endpoint2._admission(None, None)
            worker = endpoint2._start('read', endpoint2._read_block, None)
            assert worker.ready.is_set(), 'the worker was never ready'
            # The cancellation is published after the readiness of the
            # worker and before the dispatch of the request.
            cancel2.set()
            with pytest.raises(BrokerError) as info:
                endpoint2._await(worker, None, None, cancel2)
            assert info.value.code == 'BROKER_PIPE_CANCELLED'
            assert calls == [], \
                'a primitive was called by a request that was not admitted'
            assert worker._submitted == 0, \
                'the request was submitted although the admission was refused'
            write_phase('r06-linearization', {
                'calls': list(calls),
                'submitted': worker._submitted,
                'code': info.value.code})
        finally:
            # CORRECTION 22 (M3): the close of the endpoint is
            # **guarded**: it never replaces the failure that is already
            # unwinding and it never replaces the **first** exact pending
            # interruption of the cleanup.
            try:
                endpoint2.close()
            except BaseException as error:  # noqa: BLE001 - it stays visible
                r06_cleanup_errors.append(
                    {'kind': 'CLOSE', 'owner': 'r06:endpoint2',
                     'type': type(error).__name__,
                     'detail': str(error)})
                _note_interruption(r06_interrupts, error)

        # The same boundary with an **expiry**: the deadline of the
        # round arrives after the readiness of the worker and before the
        # dispatch of the request.
        endpoint3 = _WindowsPipeEndpoint(file_object=_FakeFile('read3'),
                                         name='inprocess-3', api=Api(),
                                         clock=clock, handle=704)
        try:
            before = list(calls)
            endpoint3._admission(None, None)
            worker3 = endpoint3._start('read', endpoint3._read_block, None)
            assert worker3.ready.is_set(), 'the worker was never ready'
            # The deadline of the round arrives before the dispatch.
            clock.value += 1000.0
            with pytest.raises(BrokerError) as info:
                endpoint3._await(worker3, None, clock.value - 1.0, None)
            assert info.value.code == 'BROKER_PIPE_TIMEOUT'
            assert calls == before, \
                'a primitive was called by a request that was not admitted'
            assert worker3._submitted == 0, \
                'the request was submitted although the admission was refused'
            write_phase('r06-expiry', {
                'calls': list(calls),
                'submitted': worker3._submitted,
                'code': info.value.code})
        finally:
            # CORRECTION 22 (M3): the close of the endpoint is
            # **guarded**: it never replaces the failure that is already
            # unwinding and it never replaces the **first** exact pending
            # interruption of the cleanup.
            try:
                endpoint3.close()
            except BaseException as error:  # noqa: BLE001 - it stays visible
                r06_cleanup_errors.append(
                    {'kind': 'CLOSE', 'owner': 'r06:endpoint3',
                     'type': type(error).__name__,
                     'detail': str(error)})
                _note_interruption(r06_interrupts, error)
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        r06_cleanup_facts['original'] = _original_facts()
        # CORRECTION 22 (M3): the close of the last endpoint is
        # **guarded** and the priority of the failures of the cleanup is
        # enforced **after** it: the failure that is already unwinding
        # wins, then the **first** exact pending interruption and only
        # then the ordinary error of the cleanup.
        try:
            endpoint.close()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            r06_cleanup_errors.append(
                {'kind': 'CLOSE', 'owner': 'r06:endpoint',
                 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(r06_interrupts, error)
        r06_cleanup_facts['actions'].append('close:r06:endpoint')
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures: the
        # diagnostics of the cleanup are durable even when the original
        # failure of the region is unwinding.
        _publish_cleanup(
            r06_cleanup_facts,
            lambda: write_phase('r06-close-cleanup', r06_cleanup_facts),
            r06_cleanup_errors, r06_interrupts,
            verdict=lambda: _cleanup_verdict(
                r06_cleanup_errors, None,
                'the cleanup of the endpoints met'))
        _raise_first_interruption(r06_interrupts)
        if r06_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the endpoints met %s'
                                 % (r06_cleanup_errors,))


# -- N10-R07: the context reaches every layer -----------------------------

def test_n10_r07_the_context_of_the_round_reaches_every_layer(tmp_path):
    """N10-R07 (M08): the context of the round is one context.

    Obligation: the parent hands the **one** context of the round to
    the launcher of the broker and the launcher holds it **before** the
    first side effect of the launch - the creation of the process, the
    reading of the executable, the channel and its endpoints.  The
    channel, the endpoints, the workers of the endpoints and the API of
    the primitives read the **same** context.  In the child the STOP of
    the round publishes the ONE cleanup deadline and the transport of
    the round - the write of the terminal reply, the partial write and
    the join of the reader - uses the earlier of the lease and the
    cleanup: there is no unbound window and no new budget of its own.

    The group drives the **production** launcher of the round: the
    default launcher of the session calls the production ``launch_broker``
    and the only seam that is replaced is the creation of the process:
    an in-process fake of ``subprocess.Popen`` that never calls the
    original and that never starts an operating system process.  The
    executable that is hashed is a **bound synthetic fixture** of the
    round and the endpoints of the channel are the production Windows
    endpoints with the synthetic primitives of the round.

    Entry: ``NativeCustodySession._call_launcher``,
    ``NativeCustodySession.start``, ``_default_launcher``,
    ``launch_broker``, ``_LaunchAggregate``, ``StreamChannel``,
    ``_WindowsPipeEndpoint``, ``_WindowsPipeWorker``,
    ``WindowsApi.bind_context``, ``BrokerCore.__init__`` and
    ``BrokerLoop._stop``.  Trigger: the round publishes its cleanup
    deadline and the terminal reply is written.  Oracle: the context of
    the session was already the context of the round when the process
    was created, when the executable was hashed and when the channel and
    its endpoints were built; every layer of the child reads the
    published cleanup deadline.  Negative: no layer keeps a deadline of
    its own.  Returned state: the evidence of the session names the
    propagation of the context.  Salvage: the owner of the test closes
    the round in every case.

    RECONCILIATION (N1 correction 14, F3): the group drove the parent
    of the round with the clock of the session while the channel of the
    round and its two endpoints kept the **default** clock of the host
    (``time.monotonic``).  A deadline of the round was then compared
    with a clock of **another** domain: the admission of the read of
    the endpoint refused the round, the reader of the channel failed,
    the pump of the parent ended at the end of the stream and the
    group observed **no** admission at all (the phase document of the
    failed batch of the correction 13 recorded two empty lists).

    The group now builds the channel of the round with the clock of
    the round - the production class is used unchanged and only its
    supported clock argument is bound - so that the channel, its two
    endpoints, their workers, the pump of the parent, the context of
    the round and the aggregate of the launch read every deadline of
    the round in ONE domain.  The group then proves the **liveness** of
    the pump of the parent before it tightens the bound (the next real
    read of the broker is held at a transparent seam), publishes the
    **original** cleanup deadline of the round and releases the
    admission: the original queue method really executes and the
    recorded argument is the argument that the production really passed
    to it.  The reply of the parent is bounded by the **published**
    cleanup deadline of the original context and not by the timeout of
    the call.  The positive admission and the zero expiry stay two
    distinct real owner schedules with the identity of the original
    context, the production is not changed and no assertion of the
    group is skipped.

    RECONCILIATION (N1 correction 15, M1): the oracle of the **zero
    expiry** was a helper that the group built itself: an **unstarted**
    and **unattached** ``_ChannelPump`` that was called directly after
    the pump of the round had already ended.  That proved the helper
    and not the public chain of the parent.

    The oracle of the zero expiry is now a **public** chain: a round
    that is really started through the PRODUCTION default launcher,
    with the ORIGINAL context of **that** round, with ONE clock domain
    and with the **attached** pump of that round - the pump that the
    production session really started and really owns.  The admission
    of the pump is held at a transparent gate, the **zero expiry** is
    published on the ORIGINAL context **before** the next current bound
    of the round is calculated, the reply of the parent is really
    waited for with a zero timeout and the attached pump really asks
    the queue of the round for nothing.  The pump is held while the
    reply is waited for, so its end of stream and its error can never
    preempt the reply that the round owes.  The direct helper of the
    group stays a **supplement** of the public chain and it is never
    the oracle of the zero expiry.  The production is not changed, no
    permissive fallback is added to it and no assertion of the group is
    skipped.

    RECONCILIATION (N1 correction 15, M3): the owners that the round
    really starts are registered **immediately** and they are released
    **unconditionally**.  The close of the transport of the child runs
    in an inner ``finally`` and it runs also when an assertion of the
    group failed.  The stop of the product keeps its own deadline and
    its own returned state; the salvage of the test owner is
    **separate** from it: it joins every owner that really started with
    an explicitly bounded wait, it renews no deadline of the round, it
    erases no retained resource of the product and it never claims that
    the product released it.  Two subcases fail **on purpose** at an
    established checkpoint of a round - after the parent admission and
    after the start of the transport of the child - and they catch the
    **test sentinel** of the group again: they are the proof of the
    negative path of the fixture.

    RECONCILIATION (N1 correction 16, M1): the oracle of the zero
    expiry is the **public** start of the round itself and it is no
    longer a second private read after a completed start.  The round is
    really started through the PRODUCTION default launcher and the
    reply admission of that very start is the admission that observes
    the zero expiry: the **attached** pump of the round is held at a
    transparent gate that calls the original read of the broker, the
    ORIGINAL context of the round is tightened **before** the current
    bound of the round is calculated by the admission, the reply of the
    parent is really waited for with a zero timeout and the attached
    pump really asks the queue of the round for nothing.  The expected
    error cause, the returned state and the retention of the round are
    read from the **returned** evidence of the public start and they
    are never inferred from a previous successful start or from the
    identity of the context.  The direct helper of the group stays a
    **supplement** and it is never the oracle.

    RECONCILIATION (N1 correction 16, M3): the fixture owns a
    **registry** of the owners that it really starts and every owner is
    registered **immediately**: a channel that registers itself with
    its custody before it builds anything, an endpoint that is built
    and a session that is created.  A drain thread whose start took
    effect and then failed is therefore an owner that the fixture
    joins.  The start state of an owner is one of ``STARTED``,
    ``NEVER_STARTED`` or ``UNKNOWN`` and an **unknown** owner fails the
    proof of the cleanup: it is never taken for an owner that never
    started.  Every gate of the fixture - the primitive of the round
    included - is released in the **outermost** ``finally``, the close
    of the transport of the child never prevents the cleanup of the
    other endpoint, every bounded salvage join and every liveness check
    **runs while an ordinary failure is unwinding** and the returned
    state of the public stop of the round is captured **before** the
    salvage.  Five subcases fail on purpose: the **test sentinel**, an
    **ordinary** assertion, a close of the transport of the child that
    fails and a construction of the transport of the child that fails
    **after** its drain thread was really started.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    clock = ManualClock(1000.0)
    observations = {'events': []}

    class Api:
        """The synthetic primitives of the round."""

        def __init__(self):
            self.lock = threading.Lock()
            self.frames = []
            self.thread_handles = []
            self.next_handle = 900
            # The explicit notification that the round published a
            # frame: the reader of the round waits for it and it never
            # ends the stream on a timeout.
            self.frames_ready = threading.Event()
            self.final = b''

        def duplicate_current_thread_handle(self):
            with self.lock:
                self.next_handle += 1
                self.thread_handles.append(self.next_handle)
                return self.next_handle

        def cancel_synchronous_io(self, handle):
            # RECONCILIATION (N1 correction 14, F3): the round is really
            # alive now and the reader of the channel is really inside
            # its read when the round is closed.  The cancellation
            # releases that read: the reader really ends and no thread
            # of the round is left behind after the test.
            self.frames_ready.set()
            return 'REQUESTED'

        def close_handle(self, handle):
            return None

        def read_stream(self, handle, size):
            with self.lock:
                if self.frames:
                    return self.frames.pop(0)
            # The reader of the round waits for the explicit frame of
            # the round; the wait is bounded and it never decides the
            # end of the stream.
            self.frames_ready.wait(30.0)
            with self.lock:
                if self.frames:
                    return self.frames.pop(0)
            return b''

        def write_stream(self, handle, data):
            # The terminal frame of the round is published by the write
            # of the stop and by nothing else.
            with self.lock:
                final = self.final
                self.final = b''
            if final:
                with self.lock:
                    self.frames.append(final)
                self.frames_ready.set()
            return len(data)

    api = Api()
    api.frames = [_reply_bytes('READY', 'ARMED', {}, plan, NONCE, 1),
                  _reply_bytes('STATUS', 'RUNNING', {}, plan, NONCE, 2)]
    api.final = _reply_bytes('STOPPED', 'RELEASED', {}, plan, NONCE, 3)

    class FakeFile:
        """A file of the round that counts its own closes."""

        def __init__(self, name):
            self.name = name
            self.closes = 0

        def close(self):
            self.closes += 1
            return True

    class FakeHandle:
        """The original handle of the process of the round."""

        def __init__(self):
            self.closed = 0

        def Close(self):
            self.closed += 1
            return True

    class FakeProcess:
        """The process of the round: it is never an operating system one."""

        pid = 4242
        returncode = 0

        def __init__(self):
            self.stdin = FakeFile('stdin')
            self.stdout = FakeFile('stdout')
            self.stderr = FakeFile('stderr')
            self._handle = FakeHandle()
            self.terminated = 0
            self.waited = 0

        def wait(self, timeout=None):
            self.waited += 1
            return 0

        def terminate(self):
            self.terminated += 1
            return None

    # The bound synthetic executable of the round: a local file whose
    # bytes are the bytes that the launcher hashes.  No arbitrary path
    # and no network is ever read.
    synthetic_executable = tmp_path / 'synthetic-python.exe'
    synthetic_executable.write_bytes(b'# the synthetic executable of the round\n')
    synthetic_digest = hashlib.sha256(
        synthetic_executable.read_bytes()).hexdigest()

    def fake_popen(command, **kwargs):
        """The in-process seam of the creation of the process.

        The fake never calls the original ``Popen`` and it never
        starts an operating system process.  It observes the state of
        the launch **at the moment of the creation of the process**: the
        aggregate of the launch is already with its owner and the
        context of the launch is already the context of the session.
        """
        observations['events'].append('popen')
        observations['command'] = list(command)
        aggregates = [item['resource'] for item in _launcher_custody_items()
                      if item['kind'] == 'aggregate']
        observations['aggregate_at_popen'] = aggregates[-1] if aggregates else None
        observations['context_at_popen'] = (aggregates[-1].context
                                           if aggregates else None)
        return FakeProcess()

    class _OsView:
        """A view of the module os that reports the platform of the round.

        The view is bound to the **module of the broker** and it never
        changes the module os of the host: the guard of the batch and
        every other owner of the host keep the real platform.
        """

        name = 'nt'

        def __getattr__(self, item):
            return getattr(os, item)

    class _SubprocessView:
        """A view of the module subprocess whose Popen is the fake."""

        def Popen(self, command, **kwargs):
            return fake_popen(command, **kwargs)

        def __getattr__(self, item):
            return getattr(subprocess, item)

    class _SysView:
        """A view of the module sys that names the synthetic executable."""

        executable = str(synthetic_executable)

        def __getattr__(self, item):
            return getattr(sys, item)

    handles = {'next': 900}

    def fake_make_endpoint(file_object, name, *, api=None, clock=None,
                           context=None):
        """The endpoints of the round: the production ones.

        The endpoint is the production Windows endpoint and the only
        thing that is injected is the **synthetic primitive table** of
        the round: no native library is loaded and no operating system
        call is made.

        N1 correction 16 (M3): the endpoint is registered in the
        registry of the fixture **immediately**: the workers of the
        endpoint are started later and the product may drop its
        reference to them when it closes the endpoint.
        """
        handles['next'] += 1
        endpoint = _WindowsPipeEndpoint(
            file_object=file_object, name=name,
            api=api if api is not None else api_table['value'],
            clock=clock,
            handle=handles['next'], context=context)
        registry = round_registry['value']
        if registry is not None:
            registry.register('endpoint:%s' % name, endpoint,
                              kind='endpoint', seam='make_endpoint')
        return endpoint

    # The table of the primitives of the round that is **started now**.
    # It is a holder and not a plain name: every round of the group has
    # its own table and the launcher of a round really reads the table
    # of **that** round.
    api_table = {'value': api}
    # RECONCILIATION (N1 correction 14, F3): the ONE clock domain of
    # the round.  The channel of the round and its two endpoints are
    # built by the **production** launcher and they keep the default
    # clock of the host (time.monotonic) when the launcher does not
    # name one, while the context of the round carries the deadlines of
    # the round in the domain of the clock of the session.  A deadline
    # of the round was then compared with a clock of **another** domain:
    # the admission of the read of the endpoint refused the round (the
    # deadline of the round was in the past for the clock of the host),
    # the reader of the channel failed, the pump of the parent ended at
    # the end of the stream and **no** admission was observed at all.
    #
    # The channel of the round is therefore built with the clock of the
    # round: the production class is used unchanged and only its
    # **supported** clock argument is bound.  The channel, its two
    # endpoints, the pump of the parent, the context of the round and
    # the aggregate of the launch then read every deadline of the
    # round in ONE domain.  The production is not changed.
    real_stream_channel = broker_module.StreamChannel
    # The clock of the round that is **started now**.  The channel of
    # the round and its two endpoints read the ONE domain of that
    # round: the wrapper below binds it and it never decides a deadline
    # of its own.
    round_clock = {'value': clock}
    # N1 correction 16 (M3): the registry of the owners that the
    # fixture really starts.  The registry of the round that is
    # **started now** is the one that the seams below write into: an
    # owner is registered **immediately** and it is never discovered
    # later from a product that may have dropped it.
    round_registry = {'value': None}
    # The recorder of the queue of the round that is **started now**.
    # It is armed only for the round that observes the zero expiry and
    # it is installed on the queue of the round at the moment of the
    # construction of its channel.
    round_queue_recorder = {'value': None}

    def clocked_stream_channel(*args, **kwargs):
        """The production channel of the round with the clock of the round.

        The wrapper calls the **original** production constructor and it
        only binds the clock of the round: it never replaces a method,
        never decides a deadline and never changes the wiring of the
        launch.

        N1 correction 16 (M3): the custody of the launch is the
        **supported** seam of the production and the wrapper replaces it
        with the custody seam of the fixture: a channel registers itself
        with its custody **before** it builds anything, so the registry
        of the fixture holds the channel even when its construction
        failed after its drain thread was started.  The original
        custody of the round receives every call unchanged.
        """
        kwargs.setdefault('clock', round_clock['value'])
        registry = round_registry['value']
        if registry is not None and kwargs.get('custody') is not None:
            kwargs['custody'] = _RegistryCustody(registry, 'launch',
                                                 kwargs['custody'])
        channel = real_stream_channel(*args, **kwargs)
        recorder = round_queue_recorder['value']
        if recorder is not None:
            recorder(channel)
        return channel

    def start_round(round_session, round_api, round_clock_value, registry):
        """Start one round through the PRODUCTION default launcher.

        The round is started by the **production** session, with the
        **production** default launcher and with the **production**
        ``launch_broker``.  The only seams are the creation of the
        process, the table of the primitives of the round and the clock
        of the round: the launcher of the round itself is never
        replaced by a stand-in.

        N1 correction 16 (M3): the session of the round is registered
        in the registry of the fixture **immediately**: the background
        threads and the closer threads of the round are the owners that
        the session really started and the product may drop its
        reference to them.

        N1 correction 17 (M1): the **returned** state of the public
        start is the value that this helper returns.  The public
        ``NativeCustodySession.start`` returns the evidence of the round
        and never raises for an ordinary failure: the caller reads the
        value that the public operation really returned and it never
        reads a later evidence object instead of it.
        """
        previous_api_table = api_table['value']
        previous_clock = round_clock['value']
        previous_registry = round_registry['value']
        api_table['value'] = round_api
        round_clock['value'] = round_clock_value
        round_registry['value'] = registry
        registry.register('session', round_session, kind='session',
                          seam='fixture')
        try:
            with unittest.mock.patch.object(broker_module, 'os', _OsView()), \
                 unittest.mock.patch.object(broker_module, 'subprocess',
                                            _SubprocessView()), \
                 unittest.mock.patch.object(broker_module, 'sys', _SysView()), \
                 unittest.mock.patch.object(broker_module, '_make_endpoint',
                                            fake_make_endpoint), \
                 unittest.mock.patch.object(broker_module, 'StreamChannel',
                                            clocked_stream_channel):
                start_return = round_session.start()
        finally:
            api_table['value'] = previous_api_table
            round_clock['value'] = previous_clock
            round_registry['value'] = previous_registry
        return start_return

    session = NativeCustodySession(plan=document, run_root=tmp_path,
                                   parent_child_remaining_seconds=21600,
                                   launcher=None, clock=clock,
                                   wall=time.time, nonce=NONCE)
    # OPT-B-09 (T07-M1): the pump of the **MAIN** session is observed at
    # the seam where the production really starts it.  The observer is
    # **instance local** and **transparent**: it is installed on this one
    # session, it forwards every call to the original bound method of
    # the class and it holds only the pump of the round.  The mutable
    # reference ``session._pump`` is retired by the production once it
    # confirmed the join of the pump, so the pump of the round is
    # **held** from here on and it is never read through that reference
    # again.
    #
    # The phase of the observation says where the round is: a join of
    # the pump that happened **before the body boundary** of this region
    # is a join of the production and a join that happened **during the
    # salvage** of this region is a join of the fixture.
    main_pump_phase = {'value': 'before-body-boundary', 'at': None}
    main_pump_observed = _install_main_pump_observer(
        session, lambda: main_pump_phase['value'])
    main_pump = None
    parent_salvage = []
    child_transport = None
    # N1 correction 16 (M3): the registry of the owners that the
    # fixture really starts.  Every owner of the parent and of the
    # child is registered **immediately**.
    parent_registry = _OwnerRegistry()
    # CORRECTION 17 (M3): the observer of the starts of the threads of
    # the round of the parent.  It is armed before the round is started
    # and it is disarmed only after the salvage of that round: a thread
    # that the product starts during the stop is an owner of the round.
    parent_observer = _StartObserver(parent_registry)
    parent_observer_patch = parent_observer.install()
    parent_observer_patch.start()
    parent_observer.arm()
    # The failures of the close of the transport of the child and of
    # its two endpoints: they are **recorded** and never discarded.
    child_close_failures = []
    # CORRECTION 18 (M3): the **exact** objects of the interruptions
    # that the cleanup of the round of the parent met.
    parent_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this region exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the region without a
    # durable document.
    parent_cleanup_facts = _cleanup_facts('parent-salvage')
    try:
        parent_cleanup_facts['executed'] = True
        # -- the parent: the PRODUCTION default launcher and the
        #    PRODUCTION launch_broker, with the creation of the process
        #    replaced by the in-process fake -------------------------
        parent_start_return = start_round(session, api, clock,
                                          parent_registry)
        # OPT-B-09 (T07-M1): the pump of the MAIN session that the
        # production really started is **held** from here on: it is the
        # exact object that the observer of the start really saw, it is
        # the object that the production kept in its own table of the
        # background threads of the round and it is the object that the
        # facts of this region describe.
        main_pump = main_pump_observed.get('pump')
        facts = {'context_at_popen':
                 observations['context_at_popen'] is session._context,
                 'command': observations.get('command'),
                 'executable_sha256': getattr(session.broker,
                                              'executable_sha256', None),
                 'channel_context':
                 session.broker._channel._context is session._context,
                 'reader_context':
                 session.broker._channel._reader._context is session._context,
                 'writer_context':
                 session.broker._channel._writer._context is session._context,
                 'broker_context':
                 session.broker._context is session._context,
                 'events': list(observations['events'])}
        write_phase('r07-launcher', facts)
        # The context of the round was **already** the context of the
        # session when the process of the round was created.
        assert observations.get('context_at_popen') is session._context, \
            'the launcher did not hold the context of the session before ' \
            'the creation of the process'
        # The executable that was hashed is the bound synthetic fixture
        # of the round and the hash is the one that the round carries.
        assert observations.get('command', [None])[0] \
            == str(synthetic_executable), \
            'the launcher did not use the bound synthetic executable'
        assert session.broker.executable_sha256 == synthetic_digest, \
            'the launcher did not hash the bound synthetic executable'
        # The channel of the launch and its endpoints carry the same
        # context.
        assert session.broker._channel._context is session._context
        assert session.broker._channel._reader._context is session._context
        assert session.broker._channel._writer._context is session._context
        assert session.broker._context is session._context
        assert session.evidence()['launcher_context_propagated'] is True

        # -- N1 correction 13 (PF13-03) and N1 correction 14 (F3): the
        #    **real** parent pump reads the channel of the round through
        #    the BrokerProcess and the queue of the channel, and the
        #    parent waits for its replies on the event of the round.
        #    The recorders are transparent: they call the original owner
        #    of the wait and they record the **actual** argument of it.
        #    The original context of the round is tightened before the
        #    next admission and the next requested argument is the
        #    **current** minimum; the zero expiry is included.
        #
        #    RECONCILIATION (F3): the previous fixture of the group
        #    installed the recorder on a pump that was **already dead**:
        #    the reader of the channel had failed at the admission of
        #    its read (the deadline of the round was in the domain of
        #    the facade and the clock of the endpoint was the clock of
        #    the host), the channel was at the end of its stream and
        #    **no** admission of the parent was observed at all.  The
        #    group now proves the **liveness** of the owner of the read
        #    before it tightens the bound: the next real read of the
        #    broker is **held** at the seam of the BrokerProcess, the
        #    transparent recorder is installed, the ORIGINAL cleanup
        #    deadline of the round is published and the admission is
        #    released.  The original queue method really executes and
        #    the recorded argument is the argument that the production
        #    really passed to it.
        queue_waits = []
        original_get = session.broker._channel._queue.get

        def recording_get(block=True, timeout=None):
            queue_waits.append(timeout)
            return original_get(block=block, timeout=timeout)

        session.broker._channel._queue.get = recording_get
        reply_waits = []
        original_waiter = custody_module._ReplyWaiter

        class RecordingWaiter(original_waiter):
            """A waiter of a reply that records its actual wait."""

            def __init__(self, kinds):
                super().__init__(kinds)
                event = self.event
                original_wait = event.wait

                def recording_wait(timeout=None):
                    reply_waits.append(timeout)
                    return original_wait(timeout)

                event.wait = recording_wait

        # The gate of the admission: the next real read of the broker
        # is held **before** the bound of the round is published.  The
        # gate calls the original read of the broker: it never decides
        # a deadline, it never replaces the decision of the production
        # and it never fabricates an admission.
        admission_gate = threading.Event()
        admission_held = threading.Event()
        original_broker_read = session.broker.read

        def gated_broker_read(timeout):
            admission_held.set()
            admission_gate.wait(15.0)
            return original_broker_read(timeout)

        session.broker.read = gated_broker_read
        # CORRECTION 20 (M3): the release of the gate of the admission is
        # guarded: a cancellation of it never replaces the failure that
        # is already unwinding and the **exact** object of the
        # cancellation is retained.
        admission_cleanup_errors = []
        admission_interrupts = []
        # CORRECTION 23 (M3): the facts of the cleanup of this region
        # exist **before** its body runs: a body that fails before its
        # own happy facts exist never leaves the cleanup of the region
        # without a durable document.
        admission_cleanup_facts = _cleanup_facts('admission')
        try:
            admission_cleanup_facts['executed'] = True
            # -- the pump of the parent is really alive and it reaches
            #    its next admission: the liveness of the owner of the
            #    read is a **fact** of the round and not an assumption.
            assert admission_held.wait(15.0), \
                'the parent pump never reached its next admission'
            queue_waits[:] = []
            reply_waits[:] = []
            # The **published** cleanup deadline of the round shortens
            # the next read of the parent: the round is not over yet.
            session._context.publish_cleanup_deadline(clock.value + 0.05)
            # The admission is released: the production reads the
            # **current** minimum of the ORIGINAL context.
            admission_gate.set()
            deadline = time.monotonic() + 15.0
            while time.monotonic() < deadline:
                if any(value is not None and 0.0 < value <= 0.05 + 1e-9
                       for value in queue_waits):
                    break
                time.sleep(0.005)
            # The reply of the parent is bounded by the **published**
            # cleanup deadline of the ORIGINAL context: the timeout of
            # the call is longer and it may not shorten it.
            with unittest.mock.patch.object(custody_module, '_ReplyWaiter',
                                            RecordingWaiter):
                with pytest.raises(CustodyError):
                    session._read_reply(('READY',), timeout=10.0)
            # The **actual** remaining of the round at the admission: it
            # is read from the ORIGINAL context and from the clock of
            # the round and it is never a nominal number.
            remaining = session._context.effective_deadline() - clock()
            facts = {'queue_waits': list(queue_waits),
                     'reply_waits': list(reply_waits),
                     'cleanup': clock.value + 0.05,
                     'remaining_at_admission': remaining,
                     # OPT-B-09 (T07-M1): the **held** pump of the MAIN
                     # session is read here and not the mutable reference
                     # of the session: an absent reference used to be
                     # reported as a pump that is not alive and that
                     # carries no error, and that conflated a retired
                     # reference with a pump that really ended.  The
                     # state of the reference is a separate fact and it
                     # is never a proof.
                     'pump_alive': bool(main_pump is not None
                                        and not main_pump.finished),
                     'pump_error': (repr(main_pump.error)
                                    if main_pump is not None else None),
                     'pump_pointer_state': _pump_pointer_state(
                         session, main_pump),
                     'session_state': session.state}
            write_phase('r07-pump-current-minimum', facts)
            assert queue_waits, \
                'the parent pump never waited for a frame of the round'
            assert 0.0 < queue_waits[-1] <= 0.05 + 1e-9, \
                'the read of the parent pump ignored the current minimum'
            assert queue_waits[-1] == pytest.approx(remaining), \
                'the read of the parent pump did not use the actual remaining'
            assert reply_waits, \
                'the parent never waited for a reply of the round'
            assert 0.0 < reply_waits[-1] <= 0.05 + 1e-9, \
                'the reply event of the parent ignored the current minimum'
            assert reply_waits[-1] == pytest.approx(remaining), \
                'the reply event of the parent did not use the actual remaining'
        finally:
            # CORRECTION 23 (M3): the **exact** original failure that is
            # unwinding is read **before** the first action of the
            # cleanup runs: it is the priority that follows the
            # publication.
            admission_cleanup_facts['original'] = _original_facts()
            # The gate of the owner of the test is released
            # **unconditionally**: no admission of the parent stays
            # blocked behind the test and no thread of the test is left
            # behind.
            #
            # CORRECTION 20 (M3): the release is guarded and the exact
            # object of a cancellation of it is retained: it never
            # replaces the failure that is already unwinding.
            _release_gate(admission_gate.set, admission_cleanup_errors,
                          admission_interrupts)
            admission_cleanup_facts['actions'].append('release:admission')
            # CORRECTION 23 (M3): the publication of the cleanup is
            # **unconditional** and it happens **after** every action of
            # the cleanup and **before** the priority of the failures.
            _publish_cleanup(
                admission_cleanup_facts,
                lambda: write_phase('r07-admission-cleanup',
                                    admission_cleanup_facts),
                admission_cleanup_errors, admission_interrupts,
                verdict=lambda: _cleanup_verdict(
                    admission_cleanup_errors, None,
                    'the cleanup of the admission met'))
        # CORRECTION 20 (M3): the priority of the failures of this round
        # is fixed: the failure that is already unwinding wins, then the
        # **exact** interruption of the cleanup and only then an ordinary
        # assertion.
        _raise_first_interruption(admission_interrupts)
        # CORRECTION 22 (M3): the ordinary errors of the cleanup are
        # **consumed**: they fail the round instead of being recorded
        # and forgotten.
        if admission_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the admission met %s'
                                 % (admission_cleanup_errors,))
        # -- N1 correction 16 (M1): the zero expiry on a **public**
        #    operation that is really in flight.
        #
        #    The oracle of the zero expiry is **not** a helper that the
        #    group builds itself and it is **not** a second private read
        #    after a completed start.  It is the **public** start of the
        #    round itself: the round is really started through the
        #    PRODUCTION default launcher and the reply admission of that
        #    very start is the admission that observes the zero expiry.
        #
        #    The schedule of the round is bounded at every step:
        #
        #      1. the round is really started through the PRODUCTION
        #         default launcher with the ORIGINAL context of **that**
        #         round and with ONE clock domain;
        #      2. the **attached** pump of the round - the pump that the
        #         production session really started and really owns -
        #         reaches its next admission and the admission is
        #         **held** at a transparent gate that calls the original
        #         read of the broker;
        #      3. the reply admission of the **public** start tightens
        #         the ORIGINAL context of the round **before** the
        #         current bound of the round is calculated by the
        #         admission;
        #      4. the reply of the parent is really waited for and it
        #         asks for **nothing**: the event of the reply is
        #         really waited for with a zero timeout;
        #      5. the admission is released and the **attached** pump
        #         really performs its next read: the queue of the round
        #         is really asked for **nothing**.
        #
        #    The pump of the round is held at the gate while the reply
        #    is waited for: the end of the stream of the pump and its
        #    error can therefore never preempt the reply that the round
        #    owes.  The gate is released only **after** the wait of the
        #    admission returned.
        zero_api = Api()
        zero_clock = ManualClock(2000.0)
        zero_document = plan_document(lease_expires_at=time.time() + 120.0)
        zero_plan = validate_launch_plan(zero_document, now=time.time())
        zero_api.frames = [
            _reply_bytes('READY', 'ARMED', {}, zero_plan, NONCE, 1),
            _reply_bytes('STATUS', 'RUNNING', {}, zero_plan, NONCE, 2)]
        zero_api.final = _reply_bytes('STOPPED', 'RELEASED', {}, zero_plan,
                                      NONCE, 3)
        zero_session = NativeCustodySession(
            plan=zero_document, run_root=tmp_path / 'zero-round',
            parent_child_remaining_seconds=21600, launcher=None,
            clock=zero_clock, wall=time.time, nonce=NONCE)
        zero_registry = _OwnerRegistry()
        zero_observer = _StartObserver(zero_registry)
        # CORRECTION 18 (M3): the **exact** objects of the interruptions
        # that the cleanup of the round of zero met.
        zero_interrupts = []
        # CORRECTION 21 (M3): the errors of the **guarded** queries of
        # the registry of the round of zero: a query that failed is a
        # fact of the cleanup, it is never a fabricated empty registry
        # and it never replaces the failure that is unwinding.
        zero_registry_errors = []
        # CORRECTION 23 (M3): the facts of the cleanup of this region
        # exist **before** its body runs: a body that fails before its
        # own happy facts exist never leaves the cleanup of the region
        # without a durable document.
        zero_cleanup_facts = _cleanup_facts('zero-salvage')
        zero_queue_waits = []
        zero_reply_waits = []
        zero_gate = threading.Event()
        zero_held = threading.Event()
        # OPT-B-07 (F06-M1): the **producer** of the round - the reader
        # thread of the channel that publishes the frames - is held
        # between its **original** check of the wait and the publication
        # of the frame.  The producer is released only after the real
        # read of the pump really completed its empty queue and error
        # check, so the order of the queue and the error publication of
        # the round is decided by the **real** producer and never by the
        # fixture.
        zero_producer_gate = threading.Event()
        zero_producer_held = threading.Event()
        zero_producer_facts = []
        zero_channel_ref = {'value': None}
        zero_gate_facts = []
        zero_premise = {}
        # OPT-B (R07 observed owner): the **actual** attached pump of the
        # round is held here, **independently** of the mutable reference
        # of the session.  The production retires that reference once it
        # confirmed the join of the pump, so the reference is **not** the
        # evidence that the pump of the round really ended.
        zero_observed = {}
        zero_salvage = []
        zero_returned = {}
        zero_channel = None
        zero_broker = None
        zero_pump = None
        zero_start_return = {}
        zero_trace = []
        zero_original_broker_read = broker_module.BrokerProcess.read
        zero_original_waiter = custody_module._ReplyWaiter

        def zero_record(event, **facts):
            """Record one event of the order of the zero round."""
            item = {'event': event, 'at': time.monotonic()}
            item.update(facts)
            zero_trace.append(item)
            return item

        def zero_install_queue_recorder(channel):
            """The recorder of the queue of the round of the zero expiry.

            The recorder is installed on the queue of the round at the
            moment of the construction of the channel - **before** the
            pump of the round is started - and it calls the **original**
            method of the queue: it records the **actual** argument
            that the production really passed to it.
            """
            zero_channel_ref['value'] = channel
            # OPT-B-07 (F06-M4): the **actual** pipe worker of the read
            # end of the round is observed at the construction of the
            # **real** channel of the production: it is the worker that
            # the final query of the cleanup really asks about and it is
            # a different resource from the reply pump of the custody.
            zero_read_endpoint = getattr(channel, '_reader', None)
            zero_read_worker = (
                getattr(zero_read_endpoint, '_reader', None)
                if zero_read_endpoint is not None else None)
            _observe_reference('zero:read-worker', zero_read_worker)
            original_get = channel._queue.get

            def zero_recording_get(block=True, timeout=None):
                zero_queue_waits.append(timeout)
                zero_record('QUEUE_GET_ENTERED', timeout=timeout)
                return original_get(block=block, timeout=timeout)

            channel._queue.get = zero_recording_get
            # OPT-B-07 (F06-M1): the ACTUAL publication of the frame is
            # observed truthfully: the recorder of the queue reports the
            # real result of the real put and the real error of it, and
            # the state of the channel is read **after** the put really
            # happened.  The producer is held inside the check of the
            # channel, so the reader of the round cannot publish before
            # this recorder is installed.
            original_put = channel._queue.put

            def zero_recording_put(item, block=True, timeout=None):
                try:
                    result = original_put(item, block=block, timeout=timeout)
                except BaseException as error:  # noqa: BLE001 - it stays visible
                    zero_record('QUEUE_PUT_ERROR',
                                type=type(error).__name__,
                                detail=str(error))
                    raise
                zero_record('QUEUE_PUT_RETURNED', result=repr(result))
                zero_record('CHANNEL_STATE_AFTER_PUBLICATION',
                            queue_size=channel._queue.qsize(),
                            channel_error=getattr(channel, '_error', None))
                return result

            channel._queue.put = zero_recording_put

        zero_original_check_wait = broker_module.StreamChannel._check_wait

        def zero_producer_check_wait(self):
            """Hold the producer of the round between its check and its
            publication.

            CORRECTION 23 / OPT-B-07 (F06-M1): the seam is a scoped
            **class** patch that is installed **before** the channel of
            the round is constructed, so the very first check of the
            real reader of the round already runs through it.  The
            original check runs first and its result and its exception
            are forwarded unchanged, and only the channel of the **exact**
            zero context is held.
            """
            if getattr(self, '_context', None) is not zero_session._context:
                return zero_original_check_wait(self)
            result = zero_original_check_wait(self)
            zero_producer_held.set()
            released = zero_producer_gate.wait(ZERO_PRODUCER_SECONDS)
            zero_producer_facts.append(
                {'released': bool(released),
                 'timeout': ZERO_PRODUCER_SECONDS})
            zero_record('PRODUCER_RELEASED', released=bool(released))
            return result

        def zero_gated_broker_read(self, timeout):
            """The read of the broker of the round, held at the gate.

            The gate belongs to the round of the zero expiry only: the
            context of the handle decides that.  It forwards the
            original signature and the original result and it decides
            only the schedule.
            """
            if getattr(self, '_context', None) is not zero_session._context:
                return zero_original_broker_read(self, timeout)
            zero_record('PUMP_READ_ENTERED', timeout=timeout)
            zero_held.set()
            released = zero_gate.wait(ZERO_GATE_SECONDS)
            zero_gate_facts.append({'released': bool(released),
                                    'timeout': ZERO_GATE_SECONDS})
            zero_record('GATE_RELEASED', released=bool(released),
                        timeout=ZERO_GATE_SECONDS)
            try:
                result = zero_original_broker_read(self, timeout)
            except BaseException as error:  # noqa: BLE001 - it stays visible
                zero_record('PUMP_READ_ERROR', type=type(error).__name__,
                            detail=str(error))
                raise
            zero_record('PUMP_READ_RETURNED', result=repr(result))
            # OPT-B-09 (T07-M1): the error of the channel is read from
            # the **already held** reference of the real channel and not
            # from a second private read of the broker of the session:
            # an absent reference of the broker reported no error at all
            # and that is not a proof of anything.  The field stays a
            # diagnostic of the trace and it is never promoted into a
            # proof of the absence of an error.
            zero_record('CHANNEL_ERROR_SEEN_BY_THE_PUMP',
                        channel_error=getattr(zero_channel_ref['value'],
                                             '_error', None))
            # OPT-B-07 (F06-M1): the producer is released only **after**
            # the real read of the pump really completed its empty queue
            # and error check: the real producer decides the order of the
            # publication and the fixture never hides it.
            zero_producer_gate.set()
            return result

        class ZeroTighteningWaiter(zero_original_waiter):
            """The waiter of the reply that tightens the ORIGINAL context.

            The waiter of the reply is built by the admission of the
            **public** start of the round and it is built **before**
            the admission calculates the current bound of the round.
            The waiter tightens the ORIGINAL context of the round at
            that exact moment and it records the actual wait of the
            reply.  It forwards the original signature and the original
            result and it decides only the schedule.
            """

            def __init__(self, kinds):
                super().__init__(kinds)
                # The premise of the schedule: the attached pump of the
                # round is really inside its read and it is really held
                # there.  A schedule that did not reach the admission
                # fails the premise of the test.
                zero_premise['pump_at_admission'] = bool(
                    zero_held.wait(ZERO_ADMISSION_SECONDS))
                pump = zero_session._pump
                zero_premise['pump_attached'] = pump is not None
                # OPT-B-07 (F06-M4): the **actual** reply pump of the
                # custody that the public admission really saw is
                # remembered under its **own** name: it is the pump of
                # the custody and it is **not** the pipe worker of the
                # channel, which is a different resource and is observed
                # separately at the construction of the real channel.
                _observe_reference('zero:parent-pump', pump)
                # OPT-B (R07 observed owner): the **exact** object of the
                # attached pump is held **here**, at the public admission
                # and **before** the deadline of the round is tightened.
                # The public start may retire the reference of the session
                # when it confirms the join of the pump; the object that
                # this admission really saw is the evidence of the round.
                zero_observed['pump'] = pump
                zero_premise['pump_eof_at_admission'] = bool(
                    pump is not None and pump._eof)
                # CORRECTION 17 (M1): the **actual** error of the pump
                # and its display form are two different facts: the
                # premise asserts the actual value and the display form
                # is never an oracle.
                error = pump.error if pump is not None else None
                zero_premise['pump_error_is_none'] = error is None
                zero_premise['pump_error_type'] = (
                    type(error).__name__ if error is not None else None)
                zero_premise['pump_error_repr'] = (
                    repr(error) if error is not None else None)
                # OPT-B-07 (F06-M1): the deadline of the round is
                # tightened only after the **real** producer of the round
                # and the **real** pump of the round are both held: the
                # original check of the producer already ran against the
                # valid deadline of the round and its result was
                # forwarded unchanged, and the real empty queue and error
                # check of the pump runs after the tightening and before
                # the producer is released.  The original check and the
                # original error semantics are unchanged and a timeout
                # that the production really publishes stays a failure.
                producer_ready = zero_producer_held.wait(
                    ZERO_ADMISSION_SECONDS)
                pump_ready = zero_held.wait(ZERO_ADMISSION_SECONDS)
                zero_record('BOTH_HELD', producer=bool(producer_ready),
                            pump=bool(pump_ready))
                # CORRECTION 23 / OPT-B-07 (F06-M1): the deadline of the
                # round is tightened only when the real producer and the
                # real pump are both really held, and the premise is
                # **asserted**: a round that did not reach both holds
                # fails instead of tightening the deadline anyway.
                assert producer_ready, (
                    'the producer of the zero round was never held')
                assert pump_ready, (
                    'the pump of the zero round was never held')
                zero_record('PRE_TIGHTENING_QUEUE_STATE',
                            queue_size=(
                                zero_channel_ref['value']._queue.qsize()
                                if zero_channel_ref['value'] is not None
                                else None),
                            channel_error=(
                                getattr(zero_channel_ref['value'], '_error',
                                        None)
                                if zero_channel_ref['value'] is not None
                                else None))
                # The ORIGINAL context of the round is tightened
                # **before** the admission calculates the current bound
                # of the round.
                zero_session._context.bind_absolute_deadline(
                    zero_clock.value)
                zero_premise['tightened_at'] = time.monotonic()
                zero_premise['effective_at_admission'] = \
                    zero_session._context.effective_deadline()
                event = self.event
                original_wait = event.wait

                def recording_wait(timeout=None):
                    zero_reply_waits.append(timeout)
                    zero_record('REPLY_WAIT_ENTERED', timeout=timeout)
                    result = original_wait(timeout)
                    zero_record('REPLY_WAIT_RETURNED', timeout=timeout,
                                result=bool(result))
                    # The pump is released **after** the wait of the
                    # admission returned: the end of the stream of the
                    # pump and its error can never preempt the reply
                    # that the round owes.
                    zero_gate.set()
                    return result

                event.wait = recording_wait

        with zero_observer.install():
            zero_observer.arm()
            try:
                zero_cleanup_facts['executed'] = True
                with unittest.mock.patch.object(
                        broker_module.BrokerProcess, 'read',
                        zero_gated_broker_read), \
                     unittest.mock.patch.object(
                         broker_module.StreamChannel, '_check_wait',
                         zero_producer_check_wait), \
                     unittest.mock.patch.object(custody_module, '_ReplyWaiter',
                                                ZeroTighteningWaiter):
                    round_queue_recorder['value'] = zero_install_queue_recorder
                    try:
                        zero_record('START_CALLED')
                        # CORRECTION 17 (M1): the **returned** state of
                        # the public start is the value that the public
                        # operation really returned.
                        zero_start_return = start_round(zero_session, zero_api,
                                                       zero_clock,
                                                       zero_registry)
                    finally:
                        round_queue_recorder['value'] = None
                # The **returned** state of the public start of the
                # round is the value that the public start returned: it
                # is read before the salvage of the fixture and the
                # salvage never replaces it.
                zero_returned = zero_start_return
                # OPT-B (R07 observed owner): the pump that the facts of
                # the round describe is the **observed** object and never
                # the mutable reference of the session: the production
                # clears that reference once it confirmed the join of the
                # pump, and a completion is never inferred from an absent
                # reference.
                zero_pump = zero_observed.get('pump')
                zero_session_pump = getattr(zero_session, '_pump', None)
                zero_broker = getattr(zero_session, 'broker', None)
                # The **production** keeps the actual object of the pump in
                # its own table of the background threads of the round and
                # the **observer** of the starts keeps the actual objects
                # that it really saw: the identity of the observed pump is
                # checked against both of them.
                zero_background_pump = None
                for owner_name, owner_thread in _session_owners(
                        zero_session, 'zero:session'):
                    if owner_name.endswith(':background-pump'):
                        zero_background_pump = owner_thread
                        break
                zero_observed_threads = [owner_thread for _owner_name,
                                         owner_thread
                                         in zero_registry.observed_threads()]
                zero_start_provenance = zero_registry.start_provenance()
                zero_channel = getattr(zero_broker, '_channel', None)
                # The **attached** pump of the round really performed its
                # read after the gate was released: the queue of the round
                # was really asked for nothing.
                deadline = time.monotonic() + 15.0
                while time.monotonic() < deadline:
                    if zero_pump is not None and zero_pump.finished:
                        break
                    time.sleep(0.005)
                if zero_pump is not None and zero_pump.finished:
                    zero_record('PUMP_ENDED')
                zero_pump_error = zero_pump.error if zero_pump is not None else None
                # CORRECTION 21 (M3): the query of the facts of the
                # registry is **guarded**: it is the very query of the
                # entries that the fallback of the drain tolerates.  A
                # failure of it is retained with its exact type and its
                # exact detail, the **exact** object of a cancellation is
                # retained and it never replaces the failure that is
                # already unwinding and it never replaces the **first**
                # exact pending interruption of the cleanup.
                zero_registry_snapshot = _registry_snapshot(
                    zero_registry, zero_registry_errors, zero_interrupts,
                    label='ZERO_REGISTRY_FACTS')
                facts = {'zero_queue_waits': list(zero_queue_waits),
                         'zero_reply_waits': list(zero_reply_waits),
                         'zero_pump_finished': bool(zero_pump is not None
                                                    and zero_pump.finished),
                         'zero_pump_error_is_none': zero_pump_error is None,
                         'zero_pump_error_type': (
                             type(zero_pump_error).__name__
                             if zero_pump_error is not None else None),
                         'zero_pump_error_repr': (
                             repr(zero_pump_error)
                             if zero_pump_error is not None else None),
                         'zero_pump_frames': zero_pump.frames
                         if zero_pump is not None else None,
                         # OPT-B (R07 observed owner): the facts of the
                         # **observed** pump of the round and of the
                         # mutable reference of the session are two
                         # different things and they are both named.
                         'zero_pump_observed': zero_pump is not None,
                         'zero_pump_is_the_observed_pump':
                             zero_pump is not None
                             and zero_pump is zero_observed.get('pump'),
                         'zero_pump_alive': bool(zero_pump is not None
                                                and zero_pump.alive),
                         'zero_pump_broker_is_the_round_broker':
                             zero_pump is not None
                             and getattr(zero_pump, '_broker', None)
                             is zero_broker,
                         'zero_pump_is_the_production_background_pump':
                             zero_pump is not None
                             and zero_background_pump is not None
                             and zero_pump is zero_background_pump,
                         'zero_pump_is_an_observed_start':
                             zero_pump is not None
                             and any(zero_pump is item
                                     for item in zero_observed_threads),
                         'zero_pump_start_provenance':
                             zero_start_provenance.get(id(zero_pump))
                             if zero_pump is not None else None,
                         'zero_session_pump_state': (
                             'ABSENT_AFTER_CONFIRMED_JOIN'
                             if zero_session_pump is None
                             else ('THE_OBSERVED_PUMP'
                                   if zero_session_pump is zero_pump
                                   else 'ANOTHER_OBJECT')),
                         'zero_state': zero_returned.get('state'),
                         'zero_failures': list(zero_returned.get('failures')
                                               or []),
                         'zero_broker_retained': zero_returned.get(
                             'broker_retained'),
                         'zero_broker_identity': zero_returned.get('broker'),
                         'zero_premise': dict(zero_premise),
                         'zero_gate_facts': list(zero_gate_facts),
                         'zero_registry': zero_registry_snapshot,
                         'zero_trace': list(zero_trace),
                         'zero_pump_context_is_the_session_context':
                             zero_pump is not None
                             and zero_pump._context is zero_session._context,
                         'zero_channel_context_is_the_session_context':
                             zero_channel is not None
                             and zero_channel._context is zero_session._context}
                write_phase('r07-zero-public-chain', facts)
                # The premise of the schedule: the attached pump of the
                # round was really inside its read and it was really held
                # there, and the end of its stream never preempted the
                # reply that the round owes.
                assert zero_premise['pump_at_admission'] is True, \
                    'the attached pump of the zero round never reached its admission'
                assert zero_premise['pump_eof_at_admission'] is False, \
                    'the attached pump of the zero round was at the end of its ' \
                    'stream before the admission of the reply'
                assert zero_premise['pump_error_is_none'] is True, \
                    'the attached pump of the zero round failed before the ' \
                    'admission of the reply'
                assert zero_premise['pump_error_repr'] is None, \
                    'the attached pump of the zero round failed before the ' \
                    'admission of the reply'
                # The gate was **released** and it never timed out.
                assert zero_gate_facts, \
                    'the admission of the zero round never reached the gate'
                assert zero_gate_facts[0]['released'] is True, \
                    'the gate of the admission of the zero round timed out'
                assert zero_gate_facts[0]['timeout'] == ZERO_GATE_SECONDS, \
                    'the gate of the admission of the zero round was not bounded'
                # The public start of the round really observed the zero
                # expiry: the reply of the parent asked for **nothing**.
                assert zero_reply_waits, \
                    'the public start of the zero round never waited for a reply'
                assert zero_reply_waits[-1] == 0.0, \
                    'the reply event of the zero round asked for a wait ' \
                    'after the expiry'
                # The **attached** pump of the round really asked the queue
                # of the round for **nothing**.
                assert zero_queue_waits, \
                    'the attached pump of the zero round never waited for a frame'
                assert zero_queue_waits[-1] == 0.0, \
                    'the attached pump of the zero round asked for a wait ' \
                    'after the expiry'
                assert facts['zero_pump_finished'] is True, \
                    'the attached pump of the zero round did not end'
                assert facts['zero_pump_context_is_the_session_context'] is True, \
                    'the attached pump of the zero round has another context'
                assert facts['zero_channel_context_is_the_session_context'] is True, \
                    'the channel of the zero round has another context'
                # ORACLE MAPPING (OPT-B-R07-OBSERVED-OWNER-01): the **old**
                # oracle read the pump of the round **after** the public
                # start returned and it demanded that a **finished** pump
                # was still retained in the mutable reference of the
                # session.  The production retires that reference **on
                # purpose** once it confirmed the join of the pump ("a
                # thread that really stopped is not kept any more"), so
                # the old oracle could only fail a round that behaved
                # correctly and it read the state of a reference that the
                # production had already released.
                #
                # The **new** oracle keeps the identity obligation and it
                # moves it to the object that the public admission really
                # observed: that object is the one that is checked, it
                # really finished, it is not alive any more, it carries no
                # error, it carries the ORIGINAL context of the round and
                # it really served the broker of the round, and its
                # identity is confirmed against the production table of
                # the background threads and against the actual objects
                # that the observer of the starts saw.  The reference of
                # the session is either that very object or it is absent,
                # and its absence is only accepted on the **specific**
                # path on which the production confirmed the join: an
                # absent reference is never a proof and never a PASS.
                assert facts['zero_pump_observed'] is True, \
                    'the public admission of the zero round never observed ' \
                    'an attached pump'
                assert facts['zero_pump_is_the_observed_pump'] is True, \
                    'the pump of the zero round is not the pump that its ' \
                    'admission observed'
                assert facts['zero_pump_alive'] is False, \
                    'the observed pump of the zero round is still alive ' \
                    'after the public start returned'
                assert facts['zero_pump_error_is_none'] is True, \
                    'the observed pump of the zero round failed: %s' \
                    % (facts['zero_pump_error_repr'],)
                assert facts['zero_pump_broker_is_the_round_broker'] is True, \
                    'the observed pump of the zero round did not serve the ' \
                    'broker of the round'
                assert facts['zero_pump_is_the_production_background_pump'] \
                    is True, \
                    'the observed pump of the zero round is not the pump ' \
                    'that the production kept in its background table'
                assert facts['zero_pump_is_an_observed_start'] is True, \
                    'the observer of the starts never saw the pump of the ' \
                    'zero round start'
                assert facts['zero_pump_start_provenance'] == 'STARTED', \
                    'the start of the pump of the zero round was not ' \
                    'proven: %s' % (facts['zero_pump_start_provenance'],)
                assert facts['zero_session_pump_state'] in (
                    'THE_OBSERVED_PUMP', 'ABSENT_AFTER_CONFIRMED_JOIN'), \
                    'the session of the zero round kept a pump that its ' \
                    'admission never observed: %s' \
                    % (facts['zero_session_pump_state'],)
                if facts['zero_session_pump_state'] == \
                        'ABSENT_AFTER_CONFIRMED_JOIN':
                    # the **specific** path on which the production
                    # confirmed the join of the pump and cleared its
                    # reference: the pump really started, it really ended
                    # and the production named no failure for it.
                    assert 'CUSTODY_PUMP_NOT_STOPPED' \
                        not in facts['zero_failures'], \
                        'the production did not confirm the join of the ' \
                        'pump of the zero round: %s' \
                        % (facts['zero_failures'],)
                    assert 'CUSTODY_PUMP_NOT_STARTED' \
                        not in facts['zero_failures'], \
                        'the pump of the zero round never started: %s' \
                        % (facts['zero_failures'],)
                # The **expected error cause** of the public start: the
                # admission of the reply of the round really timed out and
                # the round latched its unknown state.
                assert 'CUSTODY_CHANNEL_TIMEOUT' in facts['zero_failures'], \
                    'the public start of the zero round did not name the ' \
                    'timeout of the admission: %s' % (facts['zero_failures'],)
                assert 'CUSTODY_CHANNEL_EOF' not in facts['zero_failures'], \
                    'the round of the zero expiry ended at the end of its ' \
                    'stream instead of the timeout of the admission'
                assert facts['zero_state'] == 'UNKNOWN_RETAINED', \
                    'the public start of the zero round did not latch its state'
                # CORRECTION 17 (M1): the **retention** of the round is
                # the returned fact of the product: the **value** of the
                # retention, the **identity** of the retained resource
                # and the source of the identity of the broker are the
                # oracle - the presence of a key is not.
                assert facts['zero_broker_retained'] is True, \
                    'the public start of the zero round did not retain its broker'
                assert zero_broker is not None, \
                    'the round of the zero expiry has no broker'
                assert zero_session.broker is zero_broker, \
                    'the retained original resource is not the object of the round'
                assert facts['zero_broker_identity'] is not None, \
                    'the returned state of the public start names no identity'
                assert facts['zero_broker_identity']['identity_source'] \
                    == 'PARENT_ORIGINAL_HANDLE', \
                    'the identity of the broker of the zero round is a claim ' \
                    'and not the original handle'
                assert facts['zero_broker_identity']['pid'] == zero_broker.pid, \
                    'the identity of the broker of the zero round names ' \
                    'another process'
                assert zero_returned['pump_error'] is None, \
                    'the pump of the zero round failed before the admission'
                # CORRECTION 17 (M1): the **order** of the start, of the
                # pump, of the reply, of the gate and of the queue is the
                # recorded order and it is the required one.
                def zero_index(event):
                    for position, item in enumerate(zero_trace):
                        if item['event'] == event:
                            return position
                    return None

                order = [zero_index(name) for name in
                         ('START_CALLED', 'PUMP_READ_ENTERED',
                          'REPLY_WAIT_ENTERED', 'REPLY_WAIT_RETURNED',
                          'GATE_RELEASED', 'QUEUE_GET_ENTERED', 'PUMP_ENDED')]
                assert all(item is not None for item in order), \
                    'the order of the zero round was not completely observed: ' \
                    '%s' % (zero_trace,)
                assert order == sorted(order), \
                    'the order of the start, of the pump, of the reply, of ' \
                    'the gate and of the queue of the zero round was not ' \
                    'the required one: %s' % (zero_trace,)
            finally:
                # The fixture of the zero round is released and the owners
                # that it really started are joined with a bounded wait.
                # The gate of the test and the primitive of the round are
                # released **unconditionally**.
                #
                # CORRECTION 20 (M3): every **initial** release of a gate
                # is guarded **on its own**: a cancellation of the first
                # gate never skips the second one and it never skips the
                # stop, the drain, the proof and the evidence that follow
                # it.  It never replaces the failure that is already
                # unwinding either: the **exact** object of the
                # cancellation is retained and it is re-raised with the
                # priority of the cleanup.
                zero_cleanup_errors = []
                # CORRECTION 23 (M3): the **exact** original failure that
                # is unwinding is read **before** the first action of the
                # cleanup runs: it is the priority that follows the
                # publication.
                zero_cleanup_facts['original'] = _original_facts()
                _release_gate(zero_gate.set, zero_cleanup_errors,
                              zero_interrupts)
                _release_gate(zero_api.frames_ready.set, zero_cleanup_errors,
                              zero_interrupts)
                # OPT-B-07 (F06-M1): **every** failure and cleanup path
                # releases the producer as well: a producer that stayed
                # held would keep the round waiting for a frame that the
                # fixture itself holds back.
                _release_gate(zero_producer_gate.set, zero_cleanup_errors,
                              zero_interrupts)
                zero_cleanup_facts['actions'].extend(
                    ['release:gate', 'release:frames_ready',
                     'release:producer'])
                # The **returned** state of the product is captured
                # **before** the salvage: the salvage of the test is
                # separate from it and it never discards it.
                zero_stop = _capture_stop(zero_session,
                                           original_broker=zero_broker,
                                           interrupts=zero_interrupts)
                # CORRECTION 17 (M3): the owners of the round are drained
                # **boundedly**: the drain repeats until the owners are
                # quiescent and really joined, the quiescence is
                # asserted **after** the drain and the budget of the
                # drain is one overall bound.
                #
                # CORRECTION 18 (M3): the drain and the writing of the
                # evidence are guarded: one exception never skips the
                # owners that follow it and it never certifies the
                # cleanup.
                #
                # OPT-B (R07 fixture shutdown): the drain of the round
                # only **enumerates** the owners of the round and joins
                # them; it never asks one of them to end.  The worker of
                # the read end that the product really kept therefore went
                # on waiting for a request that never came.  The fixture
                # drives the shutdown of the **actual** owners of the
                # round itself:
                #
                #  * the workers of the two endpoints of the zero channel
                #    are asked to stop and to cancel their in-flight
                #    operation, **bounded**, with the production methods of
                #    the worker itself;
                #  * the **repeatable** production close of the channel is
                #    repeated by the drain, so the production closes the
                #    read end itself and releases the handle of the thread
                #    of its worker - and it closes the read end only after
                #    the reader of the channel really ended: the read end
                #    is never closed under a live reader.
                #
                # The returned state of the product and its stop facts are
                # already sealed above: this shutdown never relabels them
                # and it never renews a deadline of the product.  The
                # budget of the fixture - the overall bound of the drain
                # and the bound of every owner - is the one that is
                # already in use.
                # CORRECTION 23 (M3) / OPT-B-03: a query of the **final**
                # state of the round can fail.  A failure of it is an
                # **actual** error of the cleanup: it is retained with
                # its exact type and its exact detail, an exact
                # cancellation is retained as a pending interruption of
                # the cleanup and the state is recorded as **unknown** -
                # it is never read as a fact.  The query never replaces
                # the failure that is already unwinding, it never skips
                # the other owners of the round and it never skips the
                # publication of the evidence: the priority of the
                # failures - the original, then the **first** exact
                # pending interruption, then the ordinary verdict - is
                # enforced after the publication.
                zero_unknown = []

                def zero_guarded_query(label, call, default=None):
                    """Read one fact of the final state of the round.

                    CORRECTION 23 (M3) / OPT-B-03: the read is guarded.
                    A failure of it is an actual error of the cleanup, the
                    exact cancellation is retained as a pending
                    interruption and the state is **unknown**: it is
                    never read as a fact and it never replaces the
                    failure that is already unwinding.
                    """
                    try:
                        return call()
                    except BaseException as error:  # noqa: BLE001
                        zero_cleanup_errors.append(
                            {'kind': 'FINAL_QUERY',
                             'type': type(error).__name__,
                             'detail': str(error), 'query': label})
                        _note_interruption(zero_interrupts, error)
                        zero_unknown.append(label)
                        return default

                zero_shutdown = []
                zero_shutdown_workers = []
                zero_endpoints = []
                # CORRECTION 23 / OPT-B-04 (M1): the endpoints of the
                # channel of the production are its ``_reader`` and its
                # ``_writer``: the names of the endpoints are the
                # attributes of the **real** channel and nothing else.
                # A missing endpoint is a missing owner and it is never
                # read as an endpoint that does not exist.
                for endpoint_label, endpoint_attribute in (
                        ('read', '_reader'), ('write', '_writer')):
                    endpoint = zero_guarded_query(
                        'channel:%s-endpoint' % endpoint_label,
                        lambda attribute=endpoint_attribute: getattr(
                            zero_channel, attribute, None))
                    if endpoint is None:
                        continue
                    zero_endpoints.append((endpoint_label, endpoint))
                for endpoint_label, endpoint in zero_endpoints:
                    for role, label in (('_reader', 'read'),
                                        ('_writer', 'write')):
                        worker = zero_guarded_query(
                            'endpoint:%s:%s-worker'
                            % (endpoint_label, label),
                            lambda role=role, endpoint=endpoint: getattr(
                                endpoint, role, None))
                        if worker is None:
                            continue
                        entry = {'endpoint': endpoint_label, 'role': role,
                                 'thread': zero_guarded_query(
                                     'worker:%s:%s:name'
                                     % (endpoint_label, label),
                                     lambda worker=worker: getattr(
                                         worker, 'name', None))}
                        # CORRECTION 23 / OPT-B-04 (M1): the **real**
                        # methods of the worker are really called: the
                        # lambda calls them and it forwards their result.
                        # The earlier form only took the bound method and
                        # never asked the worker to end.
                        for action, call in (
                                ('stop_accepting',
                                 lambda worker=worker: worker.stop_accepting()),
                                ('request_cancel',
                                 lambda worker=worker: worker.request_cancel())):
                            try:
                                entry[action] = repr(call())
                            except BaseException as error:  # noqa: BLE001
                                zero_cleanup_errors.append(
                                    {'kind': 'FIXTURE_SHUTDOWN',
                                     'type': type(error).__name__,
                                     'detail': str(error)})
                                _note_interruption(zero_interrupts, error)
                                entry[action] = 'FAILED'
                        zero_shutdown.append(entry)
                        zero_shutdown_workers.append(worker)
                zero_cleanup_facts['actions'].append(
                    'stop:zero-endpoint-workers')
                zero_channel_close = {}

                def zero_close_facts(channel):
                    """The compact actual facts of one production close.

                    The close of the channel is **repeatable** by the
                    production itself: a close that did not confirm its
                    ends may try them again.  Only the facts that say
                    whether the reader really ended, whether the read end
                    was really closed and whether the handle of the
                    thread of its worker was really released are kept.
                    """
                    facts = channel.close()
                    return {name: facts.get(name) for name in (
                        'reader_finished', 'reader_alive',
                        'read_end_closed', 'read_retained_workers',
                        'read_worker_thread_handle_released',
                        'write_end_closed', 'write_retained_workers',
                        'write_worker_thread_handle_released',
                        'worker_thread_handle_released',
                        'channel_retained_workers')}

                def zero_close_channel():
                    """Repeat the production close of the zero channel.

                    The close of the channel is **repeatable** by the
                    production itself: a close that did not confirm its
                    ends may try them again.  It is repeated here after the
                    drain released the gates of the round, so that the
                    production closes the read end itself once the reader
                    of the channel really ended.
                    """
                    if zero_channel is None:
                        return
                    zero_channel_close.update(zero_close_facts(zero_channel))

                zero_drain = {'salvage': [], 'attempts': [], 'proof': None,
                              'quiescent': False, 'errors': [],
                              'all_salvage': [], 'owner_errors': []}
                try:
                    zero_drain = _drain_owners(
                        zero_registry, session=zero_session,
                        channel=zero_channel,
                        prefix='zero',
                        release=(lambda: zero_gate.set(),
                                 lambda: zero_api.frames_ready.set(),
                                 zero_close_channel),
                        interrupts=zero_interrupts)
                except BaseException as error:  # noqa: BLE001
                    zero_cleanup_errors.append(
                        {'kind': 'DRAIN', 'type': type(error).__name__,
                         'detail': str(error)})
                    _note_interruption(zero_interrupts, error)
                # OPT-B (R07 fixture shutdown): the production close of
                # the channel is repeated **after** the drain and it is
                # **bounded**.  The close that the drain carried may
                # still have found a worker that was alive, and it kept
                # the handle of the thread of that worker; a worker that
                # the drain really joined afterwards would still carry
                # that handle.  The repeat is the **same repeatable**
                # production close: the production releases the handle of
                # the thread of a worker that really ended, and it closes
                # the read end only after the reader of the channel
                # really ended.  The errors of the repeat are retained
                # with their exact type and their exact detail and the
                # original exception keeps the priority.
                zero_close_after = {}
                if zero_channel is not None:
                    try:
                        zero_close_after = zero_close_facts(zero_channel)
                    except BaseException as error:  # noqa: BLE001
                        zero_cleanup_errors.append(
                            {'kind': 'FIXTURE_SHUTDOWN_CLOSE',
                             'type': type(error).__name__,
                             'detail': str(error)})
                        _note_interruption(zero_interrupts, error)
                zero_channel_close.update(zero_close_after)
                # The **hard** verdict of the release of the handles: the
                # thread of every worker that the round really registered
                # really ended, its handle was really released and no
                # endpoint of the round kept a worker that it retained.
                # The state is **read**, never inferred, and the verdict
                # is part of the proof of the cleanup: it is not a
                # displayed fact and an unknown or a missing result fails
                # the round.
                zero_handle_proof = None
                zero_retained = 0
                for endpoint_label, endpoint in zero_endpoints:
                    retained = zero_guarded_query(
                        'endpoint:%s:retained' % endpoint_label,
                        lambda endpoint=endpoint: getattr(
                            endpoint, '_retained', None) or [])
                    if retained is None:
                        continue
                    zero_retained += len(retained)
                for entry, worker in zip(zero_shutdown,
                                         zero_shutdown_workers):
                    label = 'worker:%s:%s' % (entry.get('endpoint'),
                                              entry.get('role'))
                    released = zero_guarded_query(
                        '%s:thread-handle-released' % label,
                        lambda worker=worker: getattr(
                            worker, 'thread_handle_released', None))
                    alive = zero_guarded_query(
                        '%s:alive' % label,
                        lambda worker=worker: worker.is_alive())
                    entry['alive_after'] = alive
                    entry['joined_after'] = zero_guarded_query(
                        '%s:joined' % label,
                        lambda worker=worker: getattr(worker, 'joined', None))
                    entry['thread_handle_released'] = released
                    if alive is None or released is None:
                        zero_handle_proof = (
                            'the final state of the %s worker of the zero '
                            'round is unknown' % (entry.get('role'),))
                    elif alive:
                        zero_handle_proof = (
                            'the %s worker of the zero round is still alive'
                            % (entry.get('role'),))
                    elif not released:
                        zero_handle_proof = (
                            'the handle of the thread of the %s worker of '
                            'the zero round was not released'
                            % (entry.get('role'),))
                    if zero_handle_proof is not None:
                        break
                if zero_handle_proof is None and zero_unknown:
                    zero_handle_proof = (
                        'the final state of the round of zero is unknown: %s'
                        % (zero_unknown,))
                if zero_handle_proof is None and zero_retained:
                    zero_handle_proof = (
                        'the round of zero retained %d worker(s) after the '
                        'close of its endpoints' % (zero_retained,))
                if zero_handle_proof is None and zero_close_after.get(
                        'channel_retained_workers'):
                    zero_handle_proof = (
                        'the close of the channel of the zero round kept %s '
                        'worker(s)' % (zero_close_after.get(
                            'channel_retained_workers'),))
                zero_salvage = zero_drain['salvage']
                zero_proof = zero_drain['proof']
                # CORRECTION 18 (M3): a stop that raised and a snapshot
                # of the evidence that failed are facts of the cleanup.
                zero_stop_proof = _stop_proof_failure(zero_stop,
                                                      'the round of zero')
                if zero_proof is None and zero_stop_proof is not None:
                    zero_proof = zero_stop_proof
                # CORRECTION 19 (M3): the **quiescence** of the round of
                # zero is part of its proof: an owner that the final
                # resnapshot of the drain found and that no join
                # released fails the round of zero and it fails the test
                # with it.
                if zero_proof is None and zero_drain['quiescent'] is not True:
                    zero_proof = 'the round of zero was not quiescent'
                # OPT-B (R07 fixture shutdown): the release of the handles
                # of the threads of the workers is part of the proof of
                # the cleanup: a handle that was not released and a
                # worker that was retained fail the round with it.
                if zero_handle_proof is not None:
                    zero_proof = _cleanup_verdict(
                        [zero_handle_proof], zero_proof,
                        'the release of the handles of the round of zero')
                # CORRECTION 21 (M3): the query of the facts of the
                # registry that builds the **cleanup** evidence is
                # guarded as well: an unknown snapshot is an explicit
                # diagnostic and it fails the proof of the round - it is
                # never a fabricated empty registry that looks
                # successful.
                zero_registry_snapshot = _registry_snapshot(
                    zero_registry, zero_registry_errors, zero_interrupts,
                    label='ZERO_REGISTRY_FACTS')

                def zero_current_verdict():
                    """The **current** verdict of the cleanup of the round.

                    CORRECTION 23 (M2/M3): the verdict is derived from the
                    **complete** history of the errors of the cleanup - the
                    errors of its actions **and** the errors of the
                    guarded query of the registry - and from the **actual**
                    physical proof of the round.  A proof that the drain
                    found never hides an error that the cleanup met and
                    the verdict is recomputed **before every attempt to
                    write** and **before the retry** of a failed write.
                    """
                    history = (list(zero_cleanup_errors)
                               + list(zero_registry_errors))
                    return _cleanup_verdict(
                        history, zero_proof,
                        'the cleanup of the round of zero met')

                facts = dict(zero_cleanup_facts)
                facts.update({'salvage': zero_salvage,
                              'all_salvage': zero_drain.get('all_salvage', []),
                              'stop': zero_stop,
                              'fixture_shutdown': list(zero_shutdown),
                              'fixture_channel_close': dict(zero_channel_close),
                              'fixture_handle_proof': zero_handle_proof,
                              'fixture_retained_workers': zero_retained,
                              'fixture_unknown_queries': list(zero_unknown),
                              'drain': zero_drain['attempts'],
                              'quiescent': zero_drain['quiescent'],
                              'proof_failure': zero_current_verdict(),
                              'stop_proof_failure': zero_stop_proof,
                              'cleanup_errors': list(zero_cleanup_errors),
                              'interrupts': _interruption_facts(
                                  zero_interrupts),
                              'registry': zero_registry_snapshot,
                              'registry_errors': list(zero_registry_errors),
                              **_drain_facts(zero_drain)})
                zero_cleanup_facts['alive'] = bool(zero_drain['quiescent'])
                # the state of the unwinding is read **before** the
                # write: inside the handler of the write the state of the
                # frame is the write error itself and the original
                # failure would never be seen.  The write itself is
                # guarded by the helper of the cleanup and the priority
                # that follows it reads the state of the frame again.
                try:
                    # CORRECTION 23 (M2/M3): the publication of the
                    # cleanup is **unconditional**, it happens **after**
                    # every action of the cleanup and **before** the
                    # priority of the failures, and the verdict of the
                    # cleanup is recomputed **before** every attempt to
                    # write and **before** the retry of a failed write: a
                    # write that failed is an **actual** error of the
                    # cleanup and the artifact of the retry carries the
                    # **failed** proof.
                    _publish_cleanup(
                        facts,
                        lambda: write_phase('r07-zero-salvage', facts),
                        zero_cleanup_errors, zero_interrupts,
                        verdict=zero_current_verdict)
                finally:
                    zero_observer.disarm()
                # CORRECTION 19 (M3): the priority of the failures is
                # fixed: the failure that is already unwinding wins, then
                # the **exact** interruption of the cleanup and only then
                # the ordinary assertion of the proof.
                if zero_interrupts and sys.exc_info()[0] is None:
                    raise zero_interrupts[0]
                zero_verdict = zero_current_verdict()
                if zero_verdict is not None and sys.exc_info()[0] is None:
                    raise AssertionError(zero_verdict)
                # CORRECTION 17 (M1): the proof of the cleanup of the
                # round of the zero expiry is **hard**: no owner of the
                # round may have an unknown start state, no owner may
                # have met an error and every owner that really started
                # was really joined and is not alive any more.
                if sys.exc_info()[0] is None:
                    _assert_salvage_proved(zero_salvage, 'the round of zero')
        # -- N1 correction 15 (M1): the **SUPPLEMENT** of the zero
        #    expiry.  The direct helper of the group is kept as a
        #    supplement of the public chain above and it is never the
        #    oracle of the zero expiry: the acceptance oracle is the
        #    attached pump of the round that the production really
        #    started.
        # The **zero expiry**: the absolute deadline of the round is
        # shortened and every next wait of the parent asks for nothing.
        # The pump of the round ends when the bound of the round
        # arrived: it never spins on a round that is over.  The queue
        # wait of the **same** production chain - the BrokerProcess and
        # the channel of the round - is therefore observed through the
        # handle of the broker.
        # OPT-B-09 (T07-M1): the state of the **held** pump of the MAIN
        # session is read **before** the fallible sequence of the expiry:
        # a round that is about to expire has to have a pump that is
        # still alive, and the fact of the owner is recorded either way.
        main_pump_alive_before_expiry = bool(main_pump is not None
                                             and main_pump.alive)
        main_pump_finished_before_expiry = bool(main_pump is not None
                                                and main_pump.finished)
        session._context.bind_absolute_deadline(clock.value)
        queue_waits[:] = []
        reply_waits[:] = []
        session.broker.read(CHANNEL_POLL_SECONDS)
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            # OPT-B-09 (T07-M1): the **held** pump of the MAIN session is
            # polled here and not the mutable reference of the session.
            # The bound of the region is unchanged: it is the same
            # fifteen seconds and the same sleep.
            if main_pump is not None and main_pump.finished:
                break
            time.sleep(0.005)
        # The reply event of the parent is observed on a **fresh** pump
        # of the same production owner with the same original context:
        # the pump of the round is over and it never waits again.
        zero_pump = custody_module._ChannelPump(
            session.broker, decode=session._decode_reply, clock=clock,
            context=session._context)
        try:
            with unittest.mock.patch.object(custody_module, '_ReplyWaiter',
                                            RecordingWaiter):
                with pytest.raises(CustodyError):
                    zero_pump.take(('READY',), clock.value + 0.05)
        finally:
            zero_pump.stop()
        # OPT-B-09 (T07-M1): the **production** keeps the actual object of
        # the pump in its own table of the background threads of the round
        # and the observer of the starts keeps the actual objects that it
        # really saw: the identity of the held pump is checked against
        # both of them and against the record of the production itself.
        main_background_pump = None
        main_background_record = None
        for owner_name, owner_thread in _session_owners(
                session, 'parent:session'):
            if owner_name.endswith(':background-pump'):
                main_background_pump = owner_thread
                break
        for record_kind, record_value in (
                getattr(session, '_background_threads', None) or {}).items():
            if record_kind == 'pump':
                main_background_record = record_value
                break
        main_observed_threads = [
            owner_thread for _owner_name, owner_thread
            in parent_registry.observed_threads()]
        main_start_provenance = parent_registry.start_provenance()
        # The **joins** of the held pump that were confirmed **before the
        # salvage** of this region: only those prove that the production
        # really ended the pump of the round and really retired its
        # reference.
        # The **joins** of the held pump that really happened **before the
        # salvage** of this region began: the boundary is the exact
        # moment at which the salvage of the fixture started and it does
        # not depend on the thread that made the join, so a join of the
        # production that races the boundary is still named correctly.
        main_salvage_started_at = main_pump_phase.get('at')
        main_joins_before_salvage = [
            item for item in main_pump_observed['joins']
            if main_salvage_started_at is None
            or item.get('at', 0.0) < main_salvage_started_at]
        main_pump_error = (main_pump.error
                           if main_pump is not None else None)
        facts = {'queue_waits': list(queue_waits),
                 'reply_waits': list(reply_waits),
                 'pump_finished': bool(main_pump is not None
                                       and main_pump.finished),
                 # OPT-B-09 (T07-M1): the facts of the **held** pump of
                 # the MAIN session and the state of the **mutable**
                 # reference of the session are two different things and
                 # they are both named.
                 'pump_observed': main_pump is not None,
                 'pump_alive': bool(main_pump is not None
                                    and main_pump.alive),
                 'pump_error_is_none': (main_pump_error is None
                                        if main_pump is not None
                                        else None),
                 'pump_error_type': (type(main_pump_error).__name__
                                     if main_pump_error is not None
                                     else None),
                 'pump_error_repr': (repr(main_pump_error)
                                     if main_pump_error is not None
                                     else None),
                 'pump_frames': (main_pump.frames
                                 if main_pump is not None else None),
                 'pump_context_is_the_session_context': (
                     main_pump is not None
                     and main_pump._context is session._context),
                 'pump_broker_is_the_round_broker': (
                     main_pump is not None
                     and getattr(main_pump, '_broker', None)
                     is getattr(session, 'broker', None)),
                 'pump_is_the_production_background_pump': (
                     main_pump is not None
                     and main_background_pump is not None
                     and main_pump is main_background_pump),
                 'pump_background_record_state': (
                     (main_background_record or {}).get('state')),
                 'pump_background_record_started': (
                     (main_background_record or {}).get('started')),
                 'pump_background_record_error': repr(
                     (main_background_record or {}).get('error')),
                 'pump_is_an_observed_start': (
                     main_pump is not None
                     and any(main_pump is item
                             for item in main_observed_threads)),
                 'pump_start_provenance': (
                     main_start_provenance.get(id(main_pump))
                     if main_pump is not None else None),
                 'pump_pointer_state': _pump_pointer_state(session, main_pump),
                 'pump_joins': list(main_pump_observed['joins']),
                 'pump_joins_before_salvage': main_joins_before_salvage,
                 'pump_salvage_started_at': main_salvage_started_at,
                 'pump_join_confirmed_before_salvage': bool(
                     any(item.get('result') is True
                         for item in main_joins_before_salvage)),
                 'pump_start_calls': list(main_pump_observed['calls']),
                 'pump_phase': main_pump_phase['value'],
                 'pump_alive_before_expiry': main_pump_alive_before_expiry,
                 'pump_finished_before_expiry':
                     main_pump_finished_before_expiry}
        write_phase('r07-pump-zero-expiry', facts)
        assert queue_waits, \
            'the parent never waited for a frame of the round'
        assert queue_waits[-1] == 0.0, \
            'the read of the parent asked for a wait after the expiry'
        assert reply_waits, \
            'the parent never waited for a reply of the round'
        assert reply_waits[-1] == 0.0, \
            'the reply event of the parent asked for a wait after the expiry'
        assert facts['pump_finished'] is True, \
            'the pump of the round did not end after the bound arrived'
        # OPT-B-09 (T07-M1) - ORACLE MAPPING: the **old** oracle read the
        # pump of the round through the **mutable** reference of the
        # session and it collapsed an absent reference and an unfinished
        # pump into one single ``False``.  The production retires that
        # reference on purpose once it confirmed the join of the pump
        # ("a thread that really stopped is not kept any more"), so the
        # old oracle could only report the state of a reference that the
        # production had already released and it could never see the
        # failure of a pump that really ended with an error.
        #
        # The **new** oracle keeps the identity obligation and it moves it
        # to the object that the production really started: that object
        # is the one that is read, it really finished, it is not alive any
        # more, it carries no error, it carries the ORIGINAL context of
        # the round and it really served the broker of the round, and its
        # identity is confirmed against the production table of the
        # background threads and against the actual objects that the
        # observer of the starts saw.  The reference of the session is
        # either that very object or it is absent, and its absence is
        # only accepted on the **specific** path on which the production
        # confirmed the join **before the salvage** of this region.
        assert facts['pump_observed'] is True, \
            'the round never started a pump that the fixture observed'
        assert facts['pump_alive'] is False, \
            'the pump of the round is still alive after the bound arrived'
        assert facts['pump_error_is_none'] is True, \
            'the pump of the round failed: %s' % (facts['pump_error_repr'],)
        assert facts['pump_context_is_the_session_context'] is True, \
            'the pump of the round has another context'
        assert facts['pump_broker_is_the_round_broker'] is True, \
            'the pump of the round did not serve the broker of the round'
        assert facts['pump_is_the_production_background_pump'] is True, \
            'the pump of the round is not the pump that the production ' \
            'kept in its background table'
        assert facts['pump_is_an_observed_start'] is True, \
            'the observer of the starts never saw the pump of the round ' \
            'start'
        assert facts['pump_start_provenance'] == 'STARTED', \
            'the start of the pump of the round was not proven: %s' \
            % (facts['pump_start_provenance'],)
        assert facts['pump_pointer_state'] in ('SAME', 'ABSENT'), \
            'the session of the round kept a pump that the fixture never ' \
            'observed: %s' % (facts['pump_pointer_state'],)
        if facts['pump_pointer_state'] == 'ABSENT':
            # The **specific** path on which the production retired the
            # reference of the pump: the pump really started, it really
            # ended and the production really joined it **before the
            # salvage** of this region.  An absent reference is never a
            # proof on its own.
            assert facts['pump_join_confirmed_before_salvage'] is True, \
                'the reference of the pump of the round was retired ' \
                'without a confirmed join before the salvage: %s' \
                % (facts['pump_joins'],)

        # -- the child: the core, the loop and the transport share one
        #    context and the cleanup deadline of the round -----------
        # N1 correction 15 (M3): every owner that the child really
        # starts is registered **immediately** and it is released
        # **unconditionally**.  The close of the transport of the child
        # runs in an inner ``finally`` and it runs also when an
        # assertion of the group failed: a failed assertion of the
        # group may never leave the drain thread of the transport of the
        # child or the workers of its two endpoints behind.
        child = None
        windows = None
        child_read_endpoint = None
        child_write_endpoint = None
        transport = None
        try:
            # CORRECTION 18 (M3): the construction of the child is
            # **inside** the guard of the round: a construction that
            # failed half way still owns its teardown and its proof.
            kernel32 = SyntheticKernel32()
            windows = WindowsApi(table=synthetic_table(kernel32))
            child = BrokerCore(win32=windows, plan=sealed_plan(),
                               run_root=tmp_path, clock=clock)
            assert windows._context is child.context, \
                'the facade of the primitives has no context of the round'
            child.bind_absolute_deadline(2000.0)
            # N1 correction 16 (M3): the endpoints and the transport of
            # the child are registered **immediately**.  A construction
            # that failed half way still owns its endpoints and its
            # drain thread, and the product may drop its reference to
            # them when it closes them.
            child_read_endpoint = _WindowsPipeEndpoint(
                file_object=_FakeFile('read'), name='transport-read',
                api=api, clock=clock, handle=920, context=child.context)
            parent_registry.register('child:read-endpoint',
                                     child_read_endpoint,
                                     kind='endpoint', seam='fixture')
            child_write_endpoint = _WindowsPipeEndpoint(
                file_object=_FakeFile('write'), name='transport-write',
                api=api, clock=clock, handle=921, context=child.context)
            parent_registry.register('child:write-endpoint',
                                     child_write_endpoint,
                                     kind='endpoint', seam='fixture')
            transport = StreamChannel(
                None, None,
                read_endpoint=child_read_endpoint,
                write_endpoint=child_write_endpoint,
                clock=clock, context=child.context,
                custody=_RegistryCustody(parent_registry, 'child'))
            child_transport = transport
            transport.bind_deadline(2000.0)
            loop = BrokerLoop(core=child, transport=transport, plan=child.plan,
                              nonce=NONCE, clock=clock, wall=time.time)
            loop._deadline_mono = 2000.0
            # The STOP of the round: the core publishes the ONE cleanup
            # deadline and the terminal reply is written under it.
            loop._stop('STOP_COMMAND', 0)
            cleanup = child.context.cleanup_deadline_value()
            facts = {'cleanup': cleanup,
                     'transport': transport._effective_deadline(),
                     'write_endpoint': transport._writer._effective_deadline(),
                     'write_deadline': transport._writer._write_deadline,
                     'read_endpoint': transport._reader._effective_deadline(),
                     'api': windows._effective_deadline()}
            write_phase('r07-child', facts)
            assert cleanup is not None, 'the round published no cleanup deadline'
            assert transport._effective_deadline() == cleanup, \
                'the transport kept the long lease of the round'
            assert transport._writer._effective_deadline() == cleanup, \
                'the endpoint of the transport kept the long lease'
            assert transport._writer._write_deadline == cleanup, \
                'the partial write of the transport kept the long lease'
            assert transport._reader._effective_deadline() == cleanup, \
                'the join of the reader kept the long lease'
            assert windows._effective_deadline() == cleanup, \
                'the facade of the primitives kept the long lease'
        finally:
            # The close of the transport of the child is
            # **unconditional**: it runs also when an assertion of the
            # group failed.  It is the close of the **product** of the
            # child and it is not the salvage of the test owner.
            #
            # N1 correction 16 (M3): a close that failed never
            # prevents the cleanup of the **other** endpoint: every
            # close of the fixture runs in its own ``finally`` and every
            # failure of a close is **recorded** and never discarded.
            #
            # CORRECTION 19 (M3): the close of the transport and the
            # close of **each** endpoint are ``BaseException`` aware: a
            # cancellation of the first close never skips the close of
            # the second endpoint.  The **exact** object of the
            # cancellation is retained and it is re-raised by the final
            # salvage of the parent.
            if transport is not None:
                try:
                    transport.close()
                except BaseException as error:  # noqa: BLE001
                    child_close_failures.append(
                        {'owner': 'child:transport',
                         'type': type(error).__name__,
                         'detail': str(error)})
                    _note_interruption(parent_interrupts, error)
                finally:
                    # A **partial** construction of the transport of the
                    # child still owns its two endpoints: they are closed
                    # here and they are never forgotten.
                    for endpoint in (child_read_endpoint, child_write_endpoint):
                        if endpoint is None:
                            continue
                        try:
                            endpoint.close()
                        except BaseException as error:  # noqa: BLE001
                            child_close_failures.append(
                                {'owner': getattr(endpoint, '_name', 'endpoint'),
                                 'type': type(error).__name__,
                                 'detail': str(error)})
                            _note_interruption(parent_interrupts, error)
            else:
                # A **partial** construction of the transport of the
                # child still owns its two endpoints: they are closed
                # here and they are never forgotten.
                for endpoint in (child_read_endpoint, child_write_endpoint):
                    if endpoint is None:
                        continue
                    try:
                        endpoint.close()
                    except BaseException as error:  # noqa: BLE001
                        child_close_failures.append(
                            {'owner': getattr(endpoint, '_name', 'endpoint'),
                             'type': type(error).__name__,
                             'detail': str(error)})
                        _note_interruption(parent_interrupts, error)
    finally:
        # N1 correction 16 (M3): the fixture of the test releases
        # **every** gate of the test - the primitive of the round
        # included - and joins **every** owner that really started.
        # The stop of the product keeps its own deadline and its own
        # returned state; the salvage of the test is **separate** from
        # it: it renews no deadline of the round, it erases no retained
        # resource of the product and it never claims that the product
        # released it.
        #
        # The **returned** state of the product is captured **before**
        # the salvage, and the proof of the cleanup is **run** while an
        # ordinary failure is already unwinding: it never replaces the
        # failure that is unwinding and it is never discarded.
        # CORRECTION 20 (M3): the **initial** release of the gate of the
        # parent is guarded **on its own**: a cancellation of it never
        # skips the stop, the drain, the proof and the evidence that
        # follow it and it never replaces the failure that is already
        # unwinding.
        parent_cleanup_errors = []
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        parent_cleanup_facts['original'] = _original_facts()
        # CORRECTION 21 (M3): the errors of the **guarded** query of the
        # facts of the registry of the parent: a query that failed is a
        # fact of the cleanup and it never replaces the failure that is
        # unwinding.
        parent_registry_errors = []
        _release_gate(api.frames_ready.set, parent_cleanup_errors,
                      parent_interrupts)
        parent_broker = getattr(session, 'broker', None)
        # OPT-B-09 (T07-M1): the salvage of this region begins here: a
        # join of the pump of the MAIN session that is observed from now
        # on is a join of the **fixture** and it is named as such.  A
        # join that was observed before this point is a join of the
        # **production**.
        main_pump_phase['value'] = 'fixture-salvage'
        main_pump_phase['at'] = time.monotonic()
        parent_stop = _capture_stop(session, original_broker=parent_broker,
                                    interrupts=parent_interrupts)
        parent_channel = getattr(parent_broker, '_channel', None)
        # CORRECTION 17 (M3): the owners of the round of the parent are
        # drained **boundedly**: the drain repeats until the owners are
        # quiescent and really joined, the quiescence is asserted
        # **after** the drain and the budget of the drain is one overall
        # bound that is never reset.
        #
        # CORRECTION 18 (M3): the drain is guarded: one exception never
        # skips the owners that follow it and it never skips the
        # evidence of the cleanup.
        parent_drain = {'salvage': [], 'attempts': [], 'proof': None,
                        'quiescent': False, 'errors': [], 'all_salvage': [], 'owner_errors': []}
        try:
            parent_drain = _drain_owners(
                parent_registry, session=session, channel=parent_channel,
                prefix='parent', release=lambda: api.frames_ready.set(),
                interrupts=parent_interrupts)
        except BaseException as error:  # noqa: BLE001
            parent_cleanup_errors.append(
                {'kind': 'DRAIN', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(parent_interrupts, error)
        parent_salvage = parent_drain['salvage']
        parent_proof = parent_drain['proof']
        # CORRECTION 18 (M3): a stop that raised and a snapshot of the
        # evidence that failed are facts of the cleanup: they never
        # certify it.
        parent_stop_proof = _stop_proof_failure(parent_stop,
                                                'the round of the parent')
        if parent_proof is None and parent_stop_proof is not None:
            parent_proof = parent_stop_proof
        if parent_proof is None and parent_stop_proof is not None:
            parent_proof = parent_stop_proof
        # CORRECTION 19 (M3): the **quiescence** of the round of the
        # parent is part of its proof: an owner that the final
        # resnapshot of the drain found and that no join released fails
        # the round of the parent and it fails the test with it.
        if parent_proof is None and parent_drain['quiescent'] is not True:
            parent_proof = ('the round of the parent was not quiescent')
        # CORRECTION 21 (M3): the query of the facts of the registry is
        # **guarded** and it happens **before** the writer: the evidence
        # of the cleanup is never lost because the query of the registry
        # failed and an unknown snapshot is an explicit diagnostic that
        # fails the proof of the round.
        parent_registry_snapshot = _registry_snapshot(
            parent_registry, parent_registry_errors, parent_interrupts,
            label='PARENT_REGISTRY_FACTS')

        def parent_current_verdict():
            """The **current** verdict of the cleanup of the parent.

            CORRECTION 23 (M2/M3): the verdict is derived from the
            **complete** history of the errors of the cleanup - the errors
            of its actions **and** the errors of the guarded query of the
            registry - and from the **actual** physical proof of the
            round.  A proof that the drain found never hides an error
            that the cleanup met and the verdict is recomputed **before
            every attempt to write** and **before the retry** of a failed
            write.
            """
            history = (list(parent_cleanup_errors)
                       + list(parent_registry_errors))
            return _cleanup_verdict(
                history, parent_proof,
                'the cleanup of the round of the parent met')

        parent_document = dict(parent_cleanup_facts)
        parent_document.update(
            {'salvage': parent_salvage,
             'all_salvage': parent_drain.get('all_salvage', []),
             'stop': parent_stop,
             'drain': parent_drain['attempts'],
             'quiescent': parent_drain['quiescent'],
             'proof_failure': parent_current_verdict(),
             'stop_proof_failure': parent_stop_proof,
             'cleanup_errors': list(parent_cleanup_errors),
             'child_close_failures': child_close_failures,
             'interrupts': _interruption_facts(parent_interrupts),
             'registry': parent_registry_snapshot,
             'registry_errors': list(parent_registry_errors),
             # OPT-B-09 (T07-M1): the facts of the **held** pump of the
             # MAIN session and the state of its **mutable** reference
             # are recorded beside the facts of the salvage: they are two
             # different things and neither of them replaces the other.
             'main_pump_observed': main_pump is not None,
             'main_pump_pointer_state': _pump_pointer_state(session,
                                                            main_pump),
             'main_pump_joins': list(main_pump_observed['joins']),
             'main_pump_start_calls': list(main_pump_observed['calls']),
             **_drain_facts(parent_drain)})
        parent_cleanup_facts['alive'] = bool(parent_drain['quiescent'])
        # the state of the unwinding is read **before** the write: inside
        # the handler of the write the state of the frame is the write
        # error itself and the original failure would never be seen.  The
        # write itself is guarded by the helper of the cleanup and the
        # priority that follows it reads the state of the frame again.
        try:
            # CORRECTION 23 (M2/M3): the publication of the cleanup is
            # **unconditional**, it happens **after** every action of the
            # cleanup and **before** the priority of the failures, and
            # the verdict of the cleanup is recomputed **before** every
            # attempt to write and **before** the retry of a failed
            # write: a write that failed is an **actual** error of the
            # cleanup and the artifact of the retry carries the **failed**
            # proof.
            _publish_cleanup(
                parent_document,
                lambda: write_phase('r07-parent-salvage', parent_document),
                parent_cleanup_errors, parent_interrupts,
                verdict=parent_current_verdict)
        finally:
            parent_observer.disarm()
            parent_observer_patch.stop()
        # CORRECTION 19 (M3): the priority of the failures is fixed: the
        # failure that is already unwinding wins, then the **exact**
        # interruption of the cleanup and only then the ordinary
        # assertion of the proof.
        if parent_interrupts and sys.exc_info()[0] is None:
            raise parent_interrupts[0]
        parent_verdict = parent_current_verdict()
        if parent_verdict is not None and sys.exc_info()[0] is None:
            raise AssertionError(parent_verdict)
    # CORRECTION 17 (M3): no unrelated failure of a close of the child
    # is tolerated next to the intended ones: every failure of a close
    # of the child fails the round of the parent.
    assert child_close_failures == [], \
        'the close of the transport of the child met %s' \
        % (child_close_failures,)

    # -- N1 correction 12 (M08-A): the admission of a generation is
    #    decided at the **dispatch** of the worker and it consults the
    #    **current** original context of the round.  The captured
    #    request of the call is never the authority of the decision.
    class DispatchApi:
        """The primitives of a worker whose dispatch is observed."""

        def __init__(self):
            self.calls = []

        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            self.calls.append('cancel')
            return 'REQUESTED'

        def close_handle(self, handle):
            return None

        def read_stream(self, handle, size):
            # The primitive of the round: it is never called when the
            # admission of the generation was refused.
            self.calls.append('read')
            return b''

    class PausedQueue:
        """The queue of a worker whose dispatch the owner pauses.

        The worker takes the request of the round **after** the owner
        of the test released it: the admission of the generation is
        therefore decided after the cancellation or the expiry of the
        original context was published.
        """

        def __init__(self, real):
            self._real = real
            self.release = threading.Event()

        def put(self, item, timeout=None):
            return self._real.put(item, timeout=timeout)

        def get(self, timeout=None):
            while not self.release.is_set():
                time.sleep(0.005)
            return self._real.get(timeout=timeout)

    for mode in ('cancel', 'expire'):
        api = DispatchApi()
        context = _RoundContext()
        context.bind_absolute_deadline(time.monotonic() + 60.0)
        worker = _WindowsPipeWorker(api, 702, kind='read',
                                    action=lambda request: b'',
                                    name='lvw-n10-r07-dispatch',
                                    context=context)
        paused = PausedQueue(worker._requests)
        worker._requests = paused
        worker.start()
        # CORRECTION 20 (M3): the release of the paused queue of the
        # teardown is guarded: a cancellation of it never replaces the
        # failure that is already unwinding and the **exact** object of
        # the cancellation is retained.
        dispatch_cleanup_errors = []
        dispatch_interrupts = []
        # CORRECTION 23 (M3): the facts of the cleanup of this region
        # exist **before** its body runs: a body that fails before its
        # own happy facts exist never leaves the cleanup of the region
        # without a durable document.
        dispatch_facts = _cleanup_facts('dispatch-%s' % mode)
        try:
            dispatch_facts['executed'] = True
            assert worker.wait_ready(5.0), 'the worker never came up'
            # The request is really submitted and the dispatch of the
            # worker is paused: the flag of the call and the flag of
            # the channel are **not** set.
            generation = worker.submit(None)
            # The original context of the round is cancelled or it
            # expires **before** the decision of the dispatch.
            if mode == 'cancel':
                context.request_cancel()
            else:
                context.cleanup_deadline(time.monotonic() - 1.0)
            paused.release.set()
            assert worker.wait_done(generation, 10.0), \
                'the refused generation never completed'
            outcome = worker.outcome(generation)
            assert outcome is not None, 'the outcome of the generation is gone'
            dispatch_facts.update({'mode': mode, 'generation': generation,
                                   'error': outcome['error'],
                                   'calls': list(api.calls)})
            write_phase('r07-dispatch-%s' % mode, dispatch_facts)
            # The primitive of the round was never called: the
            # admission of the generation was refused before it.
            assert api.calls == [], \
                'the primitive of the round ran after a refused admission'
            if mode == 'cancel':
                assert outcome['error'] == 'BROKER_PIPE_CANCELLED'
            else:
                assert outcome['error'] == 'BROKER_PIPE_TIMEOUT'
            assert outcome['generation'] == generation, \
                'the outcome of another generation was read'
        finally:
            # CORRECTION 23 (M3): the **exact** original failure that is
            # unwinding is read **before** the first action of the cleanup
            # runs: it is the priority that follows the publication.
            dispatch_facts['original'] = _original_facts()
            # CORRECTION 20 (M3): the release of the paused queue is
            # guarded and the exact object of a cancellation of it is
            # retained: it never replaces the failure that is already
            # unwinding.
            _release_gate(paused.release.set, dispatch_cleanup_errors,
                          dispatch_interrupts)
            dispatch_facts['actions'].append('release:paused-queue')
            # CORRECTION 21 (M3): the stop and the join of the worker are
            # **guarded**: a failure of them is retained with its exact
            # type and its exact detail, the **exact** object of a
            # cancellation is retained and it never replaces the failure
            # that is already unwinding.
            try:
                worker.stop_accepting()
            except BaseException as error:  # noqa: BLE001
                dispatch_cleanup_errors.append(
                    {'kind': 'STOP_ACCEPTING',
                     'type': type(error).__name__,
                     'detail': str(error)})
                _note_interruption(dispatch_interrupts, error)
            dispatch_join = _join_owner(
                'dispatch-worker', worker, dispatch_cleanup_errors,
                dispatch_interrupts, seconds=10.0,
                join=lambda: worker.join_bounded(10.0))
            # CORRECTION 22 (M3): the **actual** liveness of the owner is
            # the fact that the guarded join returned: the query is
            # never repeated outside its guard.
            dispatch_alive = _owner_alive(dispatch_join)
            dispatch_facts['actions'].append('join:dispatch-worker')
            dispatch_facts['alive'] = dispatch_alive
            dispatch_facts['worker_alive'] = dispatch_alive
            # CORRECTION 22 (M3): the facts of the cleanup are
            # **complete** and they are **durable** before the priority
            # is applied.
            # CORRECTION 23 (M3): the publication is **unconditional** -
            # it never waits for the happy facts of the body - and the
            # verdict of the cleanup is recomputed **before** every
            # attempt to write and **before** the retry of a failed write.
            _publish_cleanup(
                dispatch_facts,
                lambda: write_phase('r07-dispatch-%s' % mode,
                                    dispatch_facts),
                dispatch_cleanup_errors, dispatch_interrupts,
                verdict=lambda: _cleanup_verdict(
                    dispatch_cleanup_errors, None,
                    'the cleanup of the dispatch met'))
            # the **exact** cancellation wins over the ordinary assertion
            # of the join that follows it.
            _raise_first_interruption(dispatch_interrupts)
            # the ordinary proof of the round: it runs **after** the join
            # and it never replaces the failure that is already
            # unwinding.
            if sys.exc_info()[0] is None:
                assert not dispatch_alive, 'the worker was left behind'
            # the ordinary errors of the cleanup are **consumed**: they
            # fail the round instead of being recorded and forgotten.
            if dispatch_cleanup_errors and sys.exc_info()[0] is None:
                raise AssertionError('the cleanup of the dispatch met %s'
                                     % (dispatch_cleanup_errors,))
        # CORRECTION 20 (M3): the priority of the failures of this
        # round is fixed: the failure that is already unwinding wins,
        # then the **exact** interruption of the cleanup.
        _raise_first_interruption(dispatch_interrupts)

    # -- N1 correction 12 (M08-A): the await of the endpoint notices
    #    the cancellation of the **original** context of the round and
    #    not only the flag of the call.
    released = threading.Event()

    class AwaitApi:
        """The primitives of an endpoint whose read is released."""

        def __init__(self):
            self.calls = []

        def duplicate_current_thread_handle(self):
            return 703

        def cancel_synchronous_io(self, handle):
            self.calls.append('cancel')
            released.set()
            return 'REQUESTED'

        def close_handle(self, handle):
            return None

        def read_stream(self, handle, size):
            self.calls.append('read')
            released.wait(10.0)
            return b''

    await_context = _RoundContext()
    await_context.bind_absolute_deadline(time.monotonic() + 60.0)
    endpoint = _WindowsPipeEndpoint(file_object=_FakeFile('await'),
                                    name='await', api=AwaitApi(),
                                    clock=time.monotonic, handle=704,
                                    context=await_context)
    holder = {}

    def run_read():
        try:
            endpoint.read(None, None)
        except BaseException as error:  # noqa: BLE001 - the failure stays visible
            holder['error'] = error

    reader = threading.Thread(target=run_read)
    reader.start()
    # CORRECTION 20 (M3): the release of the gate of the await is
    # guarded: a cancellation of it never skips the join and the close
    # that follow it and it never replaces the failure that is already
    # unwinding.
    await_cleanup_errors = []
    await_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this region exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the region without a
    # durable document.
    await_facts = _cleanup_facts('await-context')
    try:
        await_facts['executed'] = True
        deadline = time.monotonic() + 10.0
        while endpoint._reader is None and time.monotonic() < deadline:
            time.sleep(0.005)
        assert endpoint._reader is not None, 'the worker never started'
        # The original context of the round is cancelled while the read
        # is really in flight.
        await_context.request_cancel()
        reader.join(10.0)
        assert not reader.is_alive(), 'the read of the round was left behind'
        error = holder.get('error')
        await_facts.update({'error': type(error).__name__,
                            'code': getattr(error, 'code', None),
                            'calls': endpoint._api.calls})
        write_phase('r07-await-context', await_facts)
        assert isinstance(error, BrokerError), \
            'the await of the endpoint did not name the cancellation'
        assert error.code == 'BROKER_PIPE_CANCELLED', \
            'the await of the endpoint did not notice the original context'
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        await_facts['original'] = _original_facts()
        # CORRECTION 20 (M3): the release of the gate is guarded and the
        # exact object of a cancellation of it is retained.
        _release_gate(released.set, await_cleanup_errors, await_interrupts)
        await_facts['actions'].append('release:gate')
        # CORRECTION 21 (M3): the join of the reader is **guarded**: a
        # failure of it is retained with its exact type and its exact
        # detail and it never skips the close of the endpoint that
        # follows it.
        await_join = _join_owner('await-reader', reader,
                                  await_cleanup_errors, await_interrupts,
                                  seconds=10.0)
        # CORRECTION 22 (M3): the close of the endpoint is **guarded**:
        # a failure of it is retained with its exact type and its exact
        # detail, it never replaces the failure that is already
        # unwinding and it never replaces the **first** exact pending
        # interruption of the cleanup.
        try:
            endpoint.close()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            await_cleanup_errors.append(
                {'kind': 'CLOSE', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(await_interrupts, error)
        # CORRECTION 22 (M3): the facts of the cleanup are **complete**
        # and they are **durable** before the priority is applied.
        # CORRECTION 23 (M3): the publication is **unconditional** - it
        # never waits for the happy facts of the body - and the verdict
        # of the cleanup is recomputed **before** every attempt to write
        # and **before** the retry of a failed write.
        await_facts['actions'].append('join:await-reader')
        await_facts['alive'] = _owner_alive(await_join)
        await_facts['reader_alive'] = _owner_alive(await_join)
        _publish_cleanup(
            await_facts,
            lambda: write_phase('r07-await-context', await_facts),
            await_cleanup_errors, await_interrupts,
            verdict=lambda: _cleanup_verdict(
                await_cleanup_errors, None,
                'the cleanup of the await met'))
    # the **exact** cancellation of the cleanup wins over an ordinary
    # assertion and it is re-raised as **itself**.
    _raise_first_interruption(await_interrupts)
    # the ordinary errors of the cleanup are **consumed**: they fail the
    # round instead of being recorded and forgotten.
    if await_cleanup_errors and sys.exc_info()[0] is None:
        raise AssertionError('the cleanup of the await met %s'
                             % (await_cleanup_errors,))

    # -- N1 correction 15 (M3): the fixture of the group releases
    # -- N1 correction 16 (M3): the fixture of the group releases
    #    **every** gate of the test and joins **every** owner that
    #    really started - also when an assertion of the group fails.
    #    The subcases below fail **on purpose** at a meaningful
    #    checkpoint of a round and they catch **their own** exception
    #    again: the distinctive sentinel of the group, an **ordinary**
    #    assertion of the group, a close of the transport of the child
    #    that fails and a construction of the transport of the child
    #    that fails **after** its drain thread was really started.
    #    They are the proof of the negative path of the fixture: a
    #    failed assertion of the group may never leave a gate of the
    #    test blocked and it may never leave an owner of the round
    #    behind.  A receipt of the happy path alone cannot prove the
    #    negative path.
    def controlled_failure(checkpoint):
        """Fail one round of the fixture on purpose at a checkpoint.

        The round is really started through the PRODUCTION default
        launcher and the failure of the fixture of the test is raised
        at the requested checkpoint of the round.  The ``finally`` of
        the subcase releases every gate of the test, closes the
        transport of the child where it was constructed, stops the
        round, joins every owner that really started and **runs the
        proof of the cleanup** - also while the failure of the subcase
        is already unwinding.

        Every failure of the subcase is caught by **its own type**: it
        is never a broad ``Exception`` and it never swallows a real
        failure of the production.

        N1 correction 16 (M3): the owners of the round are registered
        **immediately** in the registry of the fixture, so the drain
        thread of a transport whose construction failed is still an
        owner that the fixture joins.

        N1 correction 17 (M3): the cleanup region is moved **outward**
        by one level: it encloses the start of the round **and** the
        assertion of the state of the round, so a failure of either is
        cleaned up, joined and proved.  The deliberate failure is
        **raised inside** the cleanup region and it is **caught outside**
        of it: the cleanup demonstrably runs while the failure is
        unwinding and that fact is recorded.  The ``CLOSE_FAILURE``
        checkpoint is the one case whose failure is produced **by the
        cleanup itself**: it is recorded with its exact type and its
        exact message and it never propagates.
        """
        controlled_api = Api()
        controlled_clock = ManualClock(3000.0)
        controlled_document = plan_document(lease_expires_at=time.time()
                                            + 120.0)
        controlled_plan = validate_launch_plan(controlled_document,
                                                now=time.time())
        controlled_api.frames = [
            _reply_bytes('READY', 'ARMED', {}, controlled_plan, NONCE, 1),
            _reply_bytes('STATUS', 'RUNNING', {}, controlled_plan, NONCE, 2)]
        controlled_api.final = _reply_bytes('STOPPED', 'RELEASED', {},
                                            controlled_plan, NONCE, 3)
        controlled_session = NativeCustodySession(
            plan=controlled_document,
            run_root=tmp_path / ('controlled-' + checkpoint.lower()),
            parent_child_remaining_seconds=21600, launcher=None,
            clock=controlled_clock, wall=time.time, nonce=NONCE)
        controlled_registry = _OwnerRegistry()
        # CORRECTION 17 (M3): the observer of the starts of the round of
        # the subcase.  It is armed before the round is started and it
        # is disarmed only after the salvage of that round.
        controlled_observer = _StartObserver(controlled_registry)
        gate = threading.Event()
        held = threading.Event()
        transport = None
        read_endpoint = None
        write_endpoint = None
        raised = []
        close_failures = []
        injected_starts = []
        facts = {}
        controlled_original_broker = None
        # CORRECTION 18 (M3): the errors of the cleanup of this subcase
        # are **lists** and they are never overwritten: one exception
        # never skips the owners that follow it.
        controlled_cleanup_errors = []
        # CORRECTION 18 (M3): the **exact** objects of the interruptions
        # that the cleanup of this subcase met.
        controlled_interrupts = []
        # CORRECTION 23 (M3): the facts of the cleanup of this subcase
        # exist **before** its body runs: a body that fails before its
        # own happy facts exist never leaves the cleanup of the subcase
        # without a durable document.
        facts = _cleanup_facts('controlled-%s' % checkpoint.lower(),
                               checkpoint=checkpoint)
        facts['executed'] = True
        # CORRECTION 23 (M2/M3): the **base proof** of the cleanup and the
        # detail of its verdict are fixed **before** the body runs: the
        # verdict is recomputed from them and from the **complete**
        # history of the errors of the cleanup.
        controlled_base_proof = None
        controlled_detail = ('the cleanup of the controlled failure of %s met'
                             % checkpoint)

        def controlled_current_verdict():
            """The **current** verdict of the cleanup of the subcase.

            CORRECTION 23 (M2/M3): the verdict is derived from the
            **complete** history of the errors of the cleanup - never a
            slice of it - and from the **actual** physical proof of the
            subcase.  An error of an inner writer that was recorded
            **after** the proof was computed is part of the verdict and
            the verdict is recomputed **before every attempt to write**
            and **before the retry** that follows a failed write.
            """
            return _cleanup_verdict(controlled_cleanup_errors,
                                     controlled_base_proof,
                                     controlled_detail)

        def write_facts():
            """Write the facts of the subcase of the group."""
            write_phase('r07-controlled-failure-%s' % checkpoint.lower(),
                        facts)

        controlled_observer_patch = controlled_observer.install()
        controlled_observer_patch.start()
        controlled_observer.arm()
        try:
            # (A) The OUTER region: the deliberate failures are caught
            #     **here**, outside of the entire cleanup region.
            try:
                # (B) The cleanup region: the start of the round and the
                #     assertion of its state are **inside** it.
                controlled_start_return = start_round(
                    controlled_session, controlled_api, controlled_clock,
                    controlled_registry)
                controlled_original_broker = getattr(controlled_session,
                                                      'broker', None)
                assert controlled_start_return['state'] == 'RUNNING', \
                    'the round of the controlled failure did not really start'
                controlled_original_read = controlled_session.broker.read

                def controlled_gated_read(timeout):
                    held.set()
                    gate.wait(30.0)
                    return controlled_original_read(timeout)

                controlled_session.broker.read = controlled_gated_read
                # The **established checkpoint** of the parent: the
                # attached pump of the round really reached its next
                # admission and the admission is really held.
                assert held.wait(15.0), \
                    'the parent of the controlled failure never reached its admission'
                if checkpoint in ('CHILD_TRANSPORT', 'CLOSE_FAILURE',
                                  'CONSTRUCTOR_FAILURE'):
                    controlled_kernel32 = SyntheticKernel32()
                    controlled_windows = WindowsApi(
                        table=synthetic_table(controlled_kernel32))
                    controlled_core = BrokerCore(
                        win32=controlled_windows, plan=sealed_plan(),
                        run_root=tmp_path, clock=controlled_clock)
                    controlled_core.bind_absolute_deadline(4000.0)
                    read_endpoint = _WindowsPipeEndpoint(
                        file_object=_FakeFile('controlled-read'),
                        name='controlled-read', api=controlled_api,
                        clock=controlled_clock, handle=930,
                        context=controlled_core.context)
                    controlled_registry.register(
                        'controlled:read-endpoint', read_endpoint,
                        kind='endpoint', seam='fixture')
                    write_endpoint = _WindowsPipeEndpoint(
                        file_object=_FakeFile('controlled-write'),
                        name='controlled-write', api=controlled_api,
                        clock=controlled_clock, handle=931,
                        context=controlled_core.context)
                    controlled_registry.register(
                        'controlled:write-endpoint', write_endpoint,
                        kind='endpoint', seam='fixture')
                    if checkpoint == 'CONSTRUCTOR_FAILURE':
                        # CORRECTION 17 (M3): the construction of the
                        # transport of the child fails **inside** the
                        # constructor: the ORIGINAL ``Thread.start``
                        # really takes effect and the exception is
                        # raised after it.  The seam targets the
                        # **exact** drain object of this child - the
                        # thread whose target is the drain of the
                        # channel of the **context of the child** -
                        # and it never touches a thread of the parent
                        # that carries the same name.
                        original_thread_start = threading.Thread.start
                        # CORRECTION 19 (M3): the channel of the **parent**
                        # is captured **before** the child is constructed:
                        # the lookup of the child never returns it and the
                        # identity of the child is proved against it.  The
                        # parent is the channel that the launch of the
                        # round already registered as ``launch:channel``.
                        controlled_parent_channel = None
                        for entry in controlled_registry.entries():
                            if entry.get('kind') == 'channel' \
                                    and entry.get('name') == 'launch:channel':
                                controlled_parent_channel = entry.get('owner')
                                break
                        if controlled_parent_channel is None:
                            controlled_parent_channel = getattr(
                                getattr(controlled_session, 'broker', None),
                                '_channel', None)

                        def controlled_custody_channel():
                            """The **exact** child channel of the custody.

                            CORRECTION 19 (M3): the lookup selects the
                            channel that the **controlled** custody of the
                            fixture really retained - the newly registered
                            child - and **never** the channel of the
                            parent that the launch already registered as
                            ``launch:channel``.  The identity of the child
                            is proved against the parent and a name that
                            is similar never claims the ownership.
                            """
                            children = [entry['owner']
                                        for entry
                                        in controlled_registry.entries()
                                        if entry['kind'] == 'channel'
                                        and entry['name'] == 'controlled:channel']
                            if not children:
                                # the fallback is the **newly retained**
                                # owner: the channel of the parent that
                                # the launch already registered is never
                                # the child.
                                children = [entry['owner']
                                            for entry
                                            in controlled_registry.entries()
                                            if entry['kind'] == 'channel'
                                            and entry['owner'] is not
                                            controlled_parent_channel]
                            assert len(children) == 1, \
                                'the controlled custody did not retain ' \
                                'exactly one child channel: %s' % (children,)
                            child = children[0]
                            assert child is not controlled_parent_channel, \
                                'the child channel of the controlled ' \
                                'custody is the channel of the parent'
                            return child

                        def controlled_start_then_raise(thread, *args,
                                                         **kwargs):
                            # CORRECTION 18 (M3): the actual attribute of
                            # the stdlib thread is ``_target`` - a plain
                            # ``threading.Thread`` has **no** ``target``
                            # attribute at all and the bound method of
                            # the target carries its owner in
                            # ``__self__``.
                            target = getattr(thread, '_target', None)
                            owner = getattr(target, '__self__', None)
                            if not isinstance(owner,
                                              broker_module.StreamChannel):
                                return original_thread_start(thread, *args,
                                                            **kwargs)
                            if getattr(owner, '_context', None) \
                                    is not controlled_core.context:
                                return original_thread_start(thread, *args,
                                                            **kwargs)
                            # the **exact** custody-owned child: only the
                            # channel that the custody of the fixture
                            # really registered is injected into and
                            # never a thread of the parent that carries
                            # the same name.
                            child = controlled_custody_channel()
                            if owner is not child:
                                return original_thread_start(thread, *args,
                                                            **kwargs)
                            injected_starts.append(
                                {'id': id(thread), 'name': thread.name,
                                 'owner_id': id(owner),
                                 'child_id': id(child),
                                 'target_name': getattr(target, '__name__',
                                                       None),
                                 'target_owner_is_custody_channel': True,
                                 'target_owner_is_parent':
                                     owner is
                                     controlled_parent_channel})
                            # the ORIGINAL start really takes effect and
                            # the exact failure of the fixture is raised
                            # **inside** the constructor of the child.
                            original_thread_start(thread, *args, **kwargs)
                            raise _R07ConstructorFailure(checkpoint)

                        with unittest.mock.patch.object(
                                threading.Thread, 'start',
                                controlled_start_then_raise):
                            transport = broker_module.StreamChannel(
                                None, None, read_endpoint=read_endpoint,
                                write_endpoint=write_endpoint,
                                clock=controlled_clock,
                                context=controlled_core.context,
                                custody=_RegistryCustody(
                                    controlled_registry, 'controlled'))
                    else:
                        transport = StreamChannel(
                            None, None, read_endpoint=read_endpoint,
                            write_endpoint=write_endpoint,
                            clock=controlled_clock,
                            context=controlled_core.context,
                            custody=_RegistryCustody(
                                controlled_registry, 'controlled'))
                        transport.bind_deadline(4000.0)
                        if checkpoint == 'CLOSE_FAILURE':
                            # The close of the transport of the child
                            # fails: the cleanup of the **other**
                            # endpoint may never be skipped because of
                            # it and the failure of the close is
                            # **recorded** with its exact type and its
                            # exact message.
                            def controlled_failing_close():
                                raise RuntimeError(
                                    'controlled_close_failure')

                            transport.close = controlled_failing_close
                # The deliberate failure of the fixture of the test is
                # **raised** here: it propagates through the cleanup
                # region and it is caught **outside** of it.
                if checkpoint == 'ORDINARY_ASSERTION':
                    # An **ordinary** assertion of the group: it is a
                    # real ``AssertionError`` of the test and it is
                    # caught by its own type - never by a broad
                    # ``Exception``.
                    try:
                        assert controlled_session.state == 'NOT_A_STATE', \
                            _R07OrdinaryAssertion.TOKEN
                    except AssertionError as error:
                        # The token of the deliberate assertion is
                        # normalised: the exact token of the failure
                        # survives the rewriting of the assertions of
                        # the test runner.
                        raise _R07OrdinaryAssertion(
                            _R07OrdinaryAssertion.TOKEN) from error
                elif checkpoint not in ('CONSTRUCTOR_FAILURE',
                                        'CLOSE_FAILURE'):
                    # CORRECTION 18 (M3): the ``CLOSE_FAILURE``
                    # checkpoint is a **cleanup only** case: its failure
                    # is produced by the cleanup itself and it never
                    # raises the generic sentinel of the group.
                    raise _R07Sentinel(checkpoint)
            finally:
                # (C) The cleanup region: every gate of the test is
                #     released and every owner of the round is
                #     released with it, **while** the deliberate
                #     failure is unwinding.
                #
                # CORRECTION 18 (M3): every step of the cleanup is
                # guarded and every error is **retained**: an
                # interruption of the first close never skips the close
                # of the second endpoint and it never skips the owners
                # of the round.
                #
                # CORRECTION 20 (M3): every **initial** release of a gate
                # is guarded **on its own**: a cancellation of the first
                # gate never skips the second one, never skips the
                # closes, the stop, the drain, the proof and the evidence
                # that follow it and it never replaces the failure that
                # is already unwinding.
                _release_gate(gate.set, controlled_cleanup_errors,
                              controlled_interrupts)
                _release_gate(controlled_api.frames_ready.set,
                              controlled_cleanup_errors,
                              controlled_interrupts)
                try:
                    # The close of the transport of the child runs in
                    # its own ``finally``: a close that failed never
                    # prevents the cleanup of the **other** endpoint
                    # and every failure of a close is **recorded**.
                    if transport is not None:
                        try:
                            transport.close()
                        except BaseException as error:  # noqa: BLE001
                            close_failures.append(
                                {'owner': 'controlled:transport',
                                 'type': type(error).__name__,
                                 'detail': str(error)})
                            _note_interruption(controlled_interrupts, error)
                    for endpoint in (read_endpoint, write_endpoint):
                        if endpoint is None:
                            continue
                        try:
                            endpoint.close()
                        except BaseException as error:  # noqa: BLE001
                            close_failures.append(
                                {'owner': getattr(endpoint, '_name',
                                                  'endpoint'),
                                 'type': type(error).__name__,
                                 'detail': str(error)})
                            _note_interruption(controlled_interrupts, error)
                finally:
                    # The **returned** state of the product is captured
                    # **before** the salvage of the fixture and the
                    # proof of the cleanup is **run** while the failure
                    # of the subcase is already unwinding.
                    controlled_stop = _capture_stop(
                        controlled_session,
                        original_broker=controlled_original_broker,
                        interrupts=controlled_interrupts)
                    # CORRECTION 20 (M3): this release is guarded as
                    # well: a cancellation of it never skips the drain,
                    # the proof and the evidence that follow it.
                    _release_gate(controlled_api.frames_ready.set,
                                  controlled_cleanup_errors,
                                  controlled_interrupts)
                    controlled_broker = getattr(controlled_session,
                                                'broker', None)
                    controlled_channel = getattr(controlled_broker,
                                                 '_channel', None)
                    # CORRECTION 17 (M3): the owners of the round are
                    # drained **boundedly** and the quiescence is
                    # asserted **after** the drain.
                    drain = {'salvage': [], 'attempts': [], 'proof': None,
                             'quiescent': False, 'errors': [],
                             'all_salvage': [], 'owner_errors': []}
                    try:
                        drain = _drain_owners(
                            controlled_registry,
                            session=controlled_session,
                            channel=controlled_channel, prefix='controlled',
                            release=(lambda: gate.set(),
                                     lambda: controlled_api.frames_ready.set()),
                            interrupts=controlled_interrupts)
                    except BaseException as error:  # noqa: BLE001
                        controlled_cleanup_errors.append(
                            {'kind': 'DRAIN',
                             'type': type(error).__name__,
                             'detail': str(error)})
                        _note_interruption(controlled_interrupts, error)
                    # CORRECTION 18 (M3): a stop that raised and a
                    # snapshot of the evidence that failed are facts of
                    # the cleanup: they never certify it.
                    stop_proof = _stop_proof_failure(
                        controlled_stop,
                        'the controlled failure of %s' % checkpoint)
                    salvage = drain['salvage']
                    # CORRECTION 23 (M2/M3): the **base proof** of the
                    # cleanup is the **actual** physical proof of the
                    # subcase and the **complete** history of the errors of
                    # the cleanup is added to it by the verdict.  An error
                    # that the cleanup met is never hidden by a proof that
                    # the drain already found.
                    controlled_base_proof = drain['proof']
                    if (controlled_base_proof is None
                            and stop_proof is not None):
                        controlled_base_proof = stop_proof
                    # CORRECTION 19 (M3): the **quiescence** of the round
                    # of the controlled failure is part of its proof: an
                    # owner that the final resnapshot of the drain found
                    # and that no join released fails the subcase with it.
                    if (controlled_base_proof is None
                            and drain['quiescent'] is not True):
                        controlled_base_proof = (
                            'the owners of the controlled failure of %s '
                            'were not quiescent' % checkpoint)
                    # CORRECTION 21 (M3): the query of the facts of the
                    # registry is **guarded**: it is the very query of
                    # the entries that the fallback of the drain
                    # tolerates.  A failure of it never replaces the
                    # failure that is already unwinding and it never
                    # replaces the **first** exact pending interruption
                    # of the cleanup: it is retained as a fact of the
                    # cleanup and it fails the proof of the subcase.
                    controlled_registry_snapshot = _registry_snapshot(
                        controlled_registry, controlled_cleanup_errors,
                        controlled_interrupts,
                        label='CONTROLLED_REGISTRY_FACTS')
                    if (controlled_base_proof is None
                            and controlled_registry_snapshot is None):
                        controlled_base_proof = (
                            'the registry of the controlled failure of '
                            '%s could not be read: %s'
                            % (checkpoint, controlled_cleanup_errors))
                    facts.update({'checkpoint': checkpoint,
                                  'failure': raised[0] if raised else None,
                                  'gate_released': bool(gate.is_set()),
                                  'stop': controlled_stop,
                                  'close_failures': list(close_failures),
                                  'cleanup_errors':
                                      list(controlled_cleanup_errors),
                                  'cleanup_ran_while_unwinding':
                                      sys.exc_info()[0] is not None,
                                  'salvage': salvage,
                                  'all_salvage': drain.get('all_salvage', []),
                                  'drain': drain['attempts'],
                                  'quiescent': drain['quiescent'],
                                  'proof_failure': controlled_base_proof,
                                  'stop_proof_failure': stop_proof,
                                  'interrupts': _interruption_facts(
                                      controlled_interrupts),
                                  'injected_starts': list(injected_starts),
                                  'registry': controlled_registry_snapshot,
                                  **_drain_facts(drain)})
                    unwinding = sys.exc_info()[0] is not None
                    # CORRECTION 23 (M2/M3): the write of the evidence is
                    # an action of the cleanup and it is **guarded**: a
                    # write that failed is an **actual** error of the
                    # cleanup, the verdict is recomputed **with** it
                    # **before** the retry and the artifact of the retry
                    # carries the **failed** proof and never a proof of
                    # ``None``.  The write never replaces the failure that
                    # is already unwinding.
                    _publish_cleanup(facts, write_facts,
                                     controlled_cleanup_errors,
                                     controlled_interrupts,
                                     verdict=controlled_current_verdict)
                    # CORRECTION 19 (M3): the priority of the failures is
                    # fixed: the failure that is already unwinding wins,
                    # then the **exact** interruption of the cleanup and
                    # only then the ordinary assertion of the proof.  A
                    # proof assertion never renders the rethrow of the
                    # exact interruption unreachable.
                    if controlled_interrupts and not unwinding:
                        raise controlled_interrupts[0]
                    inner_verdict = controlled_current_verdict()
                    if inner_verdict is not None and not unwinding:
                        raise AssertionError(inner_verdict)
        except _R07Sentinel as error:
            raised.append({'class': _R07Sentinel,
                           'type': type(error).__name__,
                           'token': str(error),
                           'detail': str(error)})
            facts['failure'] = raised[0]
            _publish_cleanup(facts, write_facts,
                             controlled_cleanup_errors,
                             controlled_interrupts,
                             verdict=controlled_current_verdict)
        except _R07ConstructorFailure as error:
            raised.append({'class': _R07ConstructorFailure,
                           'type': type(error).__name__,
                           'token': str(error),
                           'detail': str(error)})
            facts['failure'] = raised[0]
            _publish_cleanup(facts, write_facts,
                             controlled_cleanup_errors,
                             controlled_interrupts,
                             verdict=controlled_current_verdict)
        except _R07OrdinaryAssertion as error:
            raised.append({'class': _R07OrdinaryAssertion,
                           'type': type(error).__name__,
                           'token': str(error),
                           'detail': str(error),
                           'is_assertion_error': isinstance(
                               error, AssertionError)})
            facts['failure'] = raised[0]
            _publish_cleanup(facts, write_facts,
                             controlled_cleanup_errors,
                             controlled_interrupts,
                             verdict=controlled_current_verdict)
        finally:
            # CORRECTION 22 (M2/M3): the state of the unwinding is read
            # **before** the last actions of the cleanup run: the failure
            # that is already unwinding wins over every other failure of
            # the cleanup and it is never replaced by one of them.
            final_unwinding = sys.exc_info()[0] is not None
            # CORRECTION 23 (M2/M3): the **complete** history of the
            # errors of the cleanup is the history of the verdict: the
            # errors of the **inner** region of the subcase are **not**
            # sliced away and an error of an inner writer that was
            # recorded after the physical proof was computed fails the
            # subcase with the whole history of the cleanup.
            facts['original'] = _original_facts()
            # CORRECTION 21 (M3): the observer of the starts and the patch
            # of the round are restored **unconditionally** - they are
            # never skipped - and a failure of them is **recorded** with
            # its exact type and its exact detail: it never replaces the
            # failure that is already unwinding.
            try:
                controlled_observer.disarm()
            except BaseException as error:  # noqa: BLE001
                controlled_cleanup_errors.append(
                    {'kind': 'DISARM', 'type': type(error).__name__,
                     'detail': str(error)})
                _note_interruption(controlled_interrupts, error)
            try:
                controlled_observer_patch.stop()
            except BaseException as error:  # noqa: BLE001
                controlled_cleanup_errors.append(
                    {'kind': 'PATCH_STOP', 'type': type(error).__name__,
                     'detail': str(error)})
                _note_interruption(controlled_interrupts, error)
            # CORRECTION 21 (M3): the **last** release of the gate of the
            # round is a cleanup side effect and it happens at the **end**
            # of the cleanup: a cancellation of it is recorded in the
            # durable facts and it is re-raised as **itself** when no
            # original failure of the subcase is unwinding.  It is never
            # added after the last check and ignored.
            _release_gate(controlled_api.frames_ready.set,
                          controlled_cleanup_errors, controlled_interrupts)
            facts['actions'].extend(['disarm:observer',
                                     'stop:observer-patch',
                                     'release:frames_ready'])
            # CORRECTION 22 (M2/M3): the facts of the subcase are
            # **complete** before the **last** write of the evidence:
            # every actual error and every actual interruption of the
            # cleanup is in them and the verdict of the subcase is
            # recomputed with them.  A late ordinary error of the
            # release, of the disarm or of the stop of the patch fails
            # the subcase even when the physical salvage passed.
            #
            # CORRECTION 23 (M2/M3): the publication is **unconditional**
            # and it happens **after** every action of the cleanup and
            # **before** the priority of the failures; the verdict of the
            # subcase is recomputed **before** every attempt to write and
            # **before** the retry that follows a failed write, so the
            # durable artifact carries the verdict that the cleanup
            # really has.
            _publish_cleanup(facts, write_facts,
                             controlled_cleanup_errors,
                             controlled_interrupts,
                             verdict=controlled_current_verdict)
            # the write of the evidence is an action of the cleanup as
            # well: a write that failed is an **actual** error of it, it
            # updates the facts **in memory** and it rejects the success
            # of the subcase.
            verdict = controlled_current_verdict()
            facts['proof_failure'] = verdict
            # CORRECTION 22 (M3): the priority of the failures is
            # enforced **after** the last action of the cleanup and
            # **after** the last write of the evidence: the failure that
            # is already unwinding wins, then the **first** exact
            # pending interruption of the cleanup and only then the
            # ordinary verdict of the subcase.  A deliberate failure
            # that was already **caught** is not a failure that is
            # unwinding: it never exempts a **new** unexpected error of
            # the cleanup from failing the subcase.
            if not final_unwinding:
                if controlled_interrupts:
                    raise controlled_interrupts[0]
                if verdict is not None:
                    raise AssertionError(verdict)
        return facts

    controlled_results = {}
    for checkpoint in ('PARENT_ADMISSION', 'CHILD_TRANSPORT',
                       'ORDINARY_ASSERTION', 'CLOSE_FAILURE',
                       'CONSTRUCTOR_FAILURE'):
        controlled = controlled_failure(checkpoint)
        controlled_results[checkpoint] = controlled
        if checkpoint == 'CLOSE_FAILURE':
            # CORRECTION 17 (M3): this checkpoint is a **cleanup only**
            # case: the deliberate failure is produced by the cleanup
            # itself, it is **recorded**, it never propagates and it is
            # the **only** failure that may be recorded.  The physical
            # cleanup of the round is proved by the joins and the
            # liveness of the owners and not by the injected failure.
            assert controlled['failure'] is None, \
                'the close failure of %s was not a cleanup-only failure' \
                % checkpoint
            assert controlled['cleanup_ran_while_unwinding'] is False, \
                'the close failure of %s was claimed to unwind' % checkpoint
            close_failures = controlled['close_failures']
            assert len(close_failures) == 1, \
                'the close failure of %s was not the only failure: %s' \
                % (checkpoint, close_failures)
            assert close_failures[0]['owner'] == 'controlled:transport', \
                'the close failure of %s was not the failure of the ' \
                'transport of the child: %s' % (checkpoint, close_failures)
            assert close_failures[0]['type'] == 'RuntimeError', \
                'the close failure of %s was not the exact type: %s' \
                % (checkpoint, close_failures)
            assert close_failures[0]['detail'] == 'controlled_close_failure', \
                'the close failure of %s was not the exact message: %s' \
                % (checkpoint, close_failures)
            assert [item for item in close_failures
                    if item['owner'] != 'controlled:transport'] == [], \
                'the close failure of %s was accompanied by another owner: %s' \
                % (checkpoint, close_failures)
            assert [item for item in close_failures
                    if item['type'] != 'RuntimeError'] == [], \
                'the close failure of %s was accompanied by another type: %s' \
                % (checkpoint, close_failures)
        else:
            failure = controlled['failure']
            assert failure is not None, \
                'the controlled failure of %s did not raise its failure' \
                % checkpoint
            # CORRECTION 17 (M3): the **exact** type and the **exact**
            # token of the deliberate failure - never a name of a type
            # and never a non-``None`` check.
            if checkpoint == 'ORDINARY_ASSERTION':
                assert failure['class'] is _R07OrdinaryAssertion, \
                    'the controlled failure of %s was not the ordinary ' \
                    'assertion of the group: %s' % (checkpoint, failure)
                assert failure['is_assertion_error'] is True, \
                    'the controlled failure of %s was not an ' \
                    'AssertionError: %s' % (checkpoint, failure)
                assert failure['token'] == _R07OrdinaryAssertion.TOKEN, \
                    'the controlled failure of %s was not the exact token: %s' \
                    % (checkpoint, failure)
            elif checkpoint == 'CONSTRUCTOR_FAILURE':
                assert failure['class'] is _R07ConstructorFailure, \
                    'the controlled failure of %s was not the failure of ' \
                    'the constructor: %s' % (checkpoint, failure)
                assert failure['token'] == 'CONSTRUCTOR_FAILURE', \
                    'the controlled failure of %s was not the exact token: %s' \
                    % (checkpoint, failure)
                # the seam really took effect on the **exact** drain of
                # the child and on nothing else
                assert len(controlled['injected_starts']) == 1, \
                    'the constructor failure of %s did not take effect on ' \
                    'exactly one drain: %s' \
                    % (checkpoint, controlled['injected_starts'])
                assert controlled['injected_starts'][0]['name'] \
                    == 'lvw-native-custody-channel', \
                    'the constructor failure of %s did not take effect on ' \
                    'the drain of the child: %s' \
                    % (checkpoint, controlled['injected_starts'])
                # CORRECTION 19 (M3): the injection really took effect on
                # the **child** and never on the channel of the parent
                # that the launch already registered.
                assert controlled['injected_starts'][0][
                    'target_owner_is_parent'] is False, \
                    'the constructor failure of %s was injected into the ' \
                    'channel of the parent: %s' \
                    % (checkpoint, controlled['injected_starts'])
            else:
                assert failure['class'] is _R07Sentinel, \
                    'the controlled failure of %s was not the sentinel of ' \
                    'the group: %s' % (checkpoint, failure)
                assert failure['type'] == '_R07Sentinel', \
                    'the controlled failure of %s was not the exact type: %s' \
                    % (checkpoint, failure)
                assert failure['token'] == checkpoint, \
                    'the controlled failure of %s was not the exact token: %s' \
                    % (checkpoint, failure)
            # CORRECTION 18 (M3): **every** non-close controlled
            # subcase requires its **own** list of the close failures to
            # be empty: an unrelated failure of a close of an endpoint
            # fails the subcase instead of being tolerated next to the
            # intended failure.  The list of the main round is a
            # different list and it supplies no coverage here.
            assert controlled['close_failures'] == [], \
                'the controlled failure of %s met an unrelated close ' \
                'failure: %s' % (checkpoint, controlled['close_failures'])
            # the cleanup really ran **while** the deliberate failure was
            # unwinding: that is the proof of the negative path
            assert controlled['cleanup_ran_while_unwinding'] is True, \
                'the cleanup of the controlled failure of %s did not run ' \
                'while the failure was unwinding' % checkpoint
        assert controlled['gate_released'] is True, \
            'the gate of the controlled failure of %s stayed blocked' \
            % checkpoint
        assert controlled['proof_failure'] is None, \
            'the cleanup of the controlled failure of %s was not proved: %s' \
            % (checkpoint, controlled['proof_failure'])
        assert controlled['quiescent'] is True, \
            'the owners of the controlled failure of %s were not quiescent' \
            % checkpoint
        _assert_salvage_proved(controlled['salvage'],
                               'the controlled failure of %s' % checkpoint)

# -- N10-R08: the retry of a cancellation re-reads the context ------------

def test_n10_r08_the_retry_of_a_cancellation_re_reads_the_context():
    """N10-R08 (M08): the retry of a cancellation tightens itself.

    Obligation: every round of the retry of a cancellation reads the
    **latest** effective context: a cleanup deadline that the round
    published while the retry was running shortens the retry and the
    pause of the retry is cropped to the time that is really left.  A
    retry never waits longer than the context allows and it never falls
    back to a fresh budget of its own.

    Entry: ``_WindowsPipeWorker.request_cancel`` and
    ``_WindowsPipeWorker._effective_deadline``.  Trigger: the
    cancellation reports ``NOT_FOUND`` and the round publishes a
    shorter cleanup deadline while the retry runs.  Oracle: the retry
    stopped at the shorter deadline and it really repeated.  Negative:
    the retry never follows the old absolute deadline beyond the
    cleanup.  Returned state: the number of the attempts is named.
    Salvage: the owner of the test releases the worker at the end.
    """
    context = _RoundContext()
    context.bind_absolute_deadline(time.monotonic() + 30.0)
    release = threading.Event()
    attempts = []

    class Api:
        def duplicate_current_thread_handle(self):
            return 701

        def cancel_synchronous_io(self, handle):
            attempts.append(time.monotonic())
            if len(attempts) == 1:
                # The round publishes a **shorter** cleanup deadline
                # while the retry of the cancellation is running.
                context.cleanup_deadline(time.monotonic() + 0.05)
            return 'NOT_FOUND'

        def close_handle(self, handle):
            return None

    worker = _WindowsPipeWorker(Api(), 702, kind='read',
                                action=lambda request: release.wait(10.0),
                                name='lvw-n10-r08', context=context)
    worker.start()
    # CORRECTION 20 (M3): the release of the gate of the retry is
    # guarded: a cancellation of it never skips the join that follows it
    # and it never replaces the failure that is already unwinding.
    retry_cleanup_errors = []
    retry_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this region exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the region without a
    # durable document.
    retry_facts = _cleanup_facts('retry')
    try:
        retry_facts['executed'] = True
        assert worker.wait_ready(5.0), 'the worker never came up'
        worker.submit(None)
        assert worker.inside.wait(5.0), 'the worker never entered its read'
        started = time.monotonic()
        state = worker.request_cancel(None)
        elapsed = time.monotonic() - started
        retry_facts.update({'state': state, 'attempts': len(attempts),
                            'elapsed': elapsed,
                            'cleanup': context.cleanup_deadline_value()})
        write_phase('r08-retry', retry_facts)
        assert len(attempts) >= 2, \
            'the cancellation was not really repeated'
        assert elapsed < 2.0, \
            'the retry ignored the cleanup deadline of the round'
        assert context.cleanup_deadline_value() is not None
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        retry_facts['original'] = _original_facts()
        # CORRECTION 20 (M3): the release of the gate is guarded and the
        # exact object of a cancellation of it is retained.
        _release_gate(release.set, retry_cleanup_errors, retry_interrupts)
        retry_facts['actions'].append('release:gate')
        # CORRECTION 21 (M3): the join of the worker is **guarded** and
        # the priority of the failures is enforced **after** it.
        retry_join = _join_owner('retry-worker', worker,
                                 retry_cleanup_errors, retry_interrupts,
                                 seconds=10.0)
        # CORRECTION 22 (M3): the **actual** liveness of the owner is the
        # fact that the guarded join returned: the query is never
        # repeated outside its guard.
        retry_alive = _owner_alive(retry_join)
        retry_facts['actions'].append('join:retry-worker')
        retry_facts['alive'] = retry_alive
        # CORRECTION 22 (M3): the facts of the cleanup are **complete**
        # and they are **durable** before the priority is applied.
        # CORRECTION 23 (M3): the publication is **unconditional** - it
        # never waits for the happy facts of the body - and the verdict of
        # the cleanup is recomputed **before** every attempt to write and
        # **before** the retry of a failed write.
        retry_facts['worker_alive'] = retry_alive
        _publish_cleanup(
            retry_facts, lambda: write_phase('r08-retry', retry_facts),
            retry_cleanup_errors, retry_interrupts,
            verdict=lambda: _cleanup_verdict(
                retry_cleanup_errors, None,
                'the cleanup of the retry met'))
        # the **exact** cancellation wins over the ordinary assertion of
        # the join that follows it.
        _raise_first_interruption(retry_interrupts)
        # the ordinary proof of the round: it runs **after** the join and
        # it never replaces the failure that is already unwinding.
        if sys.exc_info()[0] is None:
            assert not retry_alive, 'the worker was left behind'
        # the ordinary errors of the cleanup are **consumed**: they fail
        # the round instead of being recorded and forgotten.
        if retry_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the retry met %s'
                                 % (retry_cleanup_errors,))


# -- N10-R09: every exit of the startup owner joins its thread ------------

def test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread(tmp_path):
    """N10-R09 (M08): the owner of a startup step joins its thread.

    Obligation: **every** exit of a startup step - the success, the
    timeout, the ordinary failure, the cancellation and the
    ``SystemExit`` - waits for the **real** exit of the thread of the
    step in a ``finally``, bounded by the deadline of the round.  A
    thread that did not exit keeps its owner: it stays in the owners
    that are in flight and the round keeps the fact.  The original
    exception object is the one that leaves and the wait never
    publishes the cleanup deadline of the round before the round
    failed.

    Entry: ``BrokerLoop._run_startup`` and ``_StartupOwner.settle``.
    Trigger: the result of the step is published while the **real**
    thread of the step is still alive, and the result is an ordinary
    error, a cancellation and a ``SystemExit``.  Oracle: the owner was
    not released before the real exit of its thread, the bounded join
    ran and the original exception object is the one that propagated.
    Negative: the publication of the result is never a proof that the
    thread ended.  Returned state: the owners that are in flight are
    named.  Salvage: the owner of the test releases the threads that
    the product started.

    RECONCILIATION (N1 correction 11): the three phases of the group
    shared **one** deadline of the loop, so the second phase inherited
    the budget that the first phase had already consumed and it was
    refused by the deadline of the round before its result was read.
    Every phase is now an **independent bounded scenario** with its own
    core, its own loop and its own deadline: no phase borrows the
    expired budget of a previous phase, the real result is published
    while the real thread of the step is still alive, the join of every
    thread is **unconditional** and no sleep ever proves the exit of a
    thread.

    RECONCILIATION (N1 correction 14, F4): the **unconditional** join
    of the group was also applied to the thread of the step that
    **never started**: the seam of that subcase raised before the
    original start of the thread and the join of the fixture raised
    ``RuntimeError: cannot join thread before it is started``.  The
    facts of the start decide now: the start did not return, the
    thread has **no identity** and it is not alive, so the fixture
    skips **only** that impossible join.  The unconditional bounded
    join stays for every thread that really started, an object without
    an identity is never read as a physical exit of a thread and the
    causal negative of the group (an unproved start is never released)
    is unchanged.
    """
    clock = time.monotonic
    release = threading.Event()
    owners = []
    # CORRECTION 20 (M3): the release of the gate of the startup owner is
    # guarded: a cancellation of it never skips the joins that follow it
    # and it never replaces the failure that is already unwinding.
    startup_cleanup_errors = []
    startup_interrupts = []
    startup_documents = []
    # CORRECTION 23 (M3): the facts of the cleanup of this region exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the region without a
    # durable document.  The documents of the phases of the body are
    # **kept** and they never replace the document of the cleanup.
    startup_cleanup_facts = _cleanup_facts('startup')
    try:
        startup_cleanup_facts['executed'] = True
        for error in (BrokerError('BROKER_STARTUP_ORDINARY'),
                      KeyboardInterrupt('startup_cancelled'),
                      SystemExit(3)):
            published = threading.Event()
            # RECONCILIATION (N1 correction 11): every phase of the
            # group is an **independent bounded scenario**.  It has its
            # own core, its own loop and its own deadline: no phase
            # borrows the expired budget of a previous phase and no
            # sleep ever proves the exit of a thread.
            win32 = RecordingWin32()
            core = BrokerCore(win32=win32, plan=sealed_plan(), run_root=tmp_path,
                              clock=clock)
            core.bind_absolute_deadline(clock() + 60.0)
            transport = type('T', (), {'bind_deadline': lambda self, value: value,
                                       'write': lambda self, raw: None})()
            loop = BrokerLoop(core=core, transport=transport, plan=core.plan,
                              nonce=NONCE, clock=clock, wall=time.time)
            loop._deadline_mono = clock() + 2.0

            def action(error=error, published=published, loop=loop):
                # The result of the step is published and the **real**
                # thread of the step stays alive: the publication of the
                # result is never a proof that the thread ended.
                owner = loop._startup_owner
                owner._results.put_nowait(('error', error))
                published.set()
                release.wait(15.0)

            published.clear()
            with pytest.raises(type(error)) as info:
                loop._run_startup('ARM', action)
            assert published.is_set(), \
                'the result of the step was never published'
            # The original exception object is the one that propagated.
            assert info.value is error, \
                'the original exception object was replaced'
            owner = loop._startup_owner
            owners.append(owner)
            # The real thread of the step is still alive: the owner was
            # not released before the real exit of its thread.
            assert owner.in_flight, \
                'the thread of the step ended while the owner was released'
            assert loop._startup_in_flight is owner, \
                'the owner of a step that did not end was released'
            assert owner in core.context.inflight(), \
                'the owner of a step that did not end left the flight'
            facts = {'error_type': type(error).__name__,
                     'in_flight': len(core.context.inflight()),
                     'retained': loop._startup_in_flight is owner}
            startup_documents.append(
                ('r09-%s' % type(error).__name__.lower(), facts))
            write_phase('r09-%s' % type(error).__name__.lower(), facts)
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        startup_cleanup_facts['original'] = _original_facts()
        # The salvage of the owner of the test: the threads that the
        # product started are released and joined with a bounded wait.
        # The join is **unconditional**: no phase leaves a thread of the
        # round behind.
        _release_gate(release.set, startup_cleanup_errors,
                      startup_interrupts)
        startup_cleanup_facts['actions'].append('release:gate')
        # CORRECTION 21 (M3): **every** owner of the round is attempted
        # and **every** join and **every** liveness query of it is
        # **guarded**: a failure of the join of the first owner never
        # skips the owners that follow it, it never replaces the failure
        # that is already unwinding and it never replaces the **first**
        # exact pending interruption of the cleanup.
        startup_joins = []
        for owner in owners:
            try:
                thread = owner._thread
            except BaseException as error:  # noqa: BLE001
                startup_cleanup_errors.append(
                    {'kind': 'OWNER_THREAD', 'type': type(error).__name__,
                     'detail': str(error)})
                _note_interruption(startup_interrupts, error)
                continue
            if thread is None:
                continue
            startup_joins.append(
                _join_owner('startup-owner', thread, startup_cleanup_errors,
                            startup_interrupts, seconds=10.0))
        startup_cleanup_facts['actions'].append('join:startup-owners')
        # CORRECTION 23 (M3): the **actual** liveness of every owner that
        # the traversal joined is a **durable** list of the cleanup: it
        # never waits for the documents of the phases of the body.
        startup_cleanup_facts['joins'] = [
            {'owner': item.get('owner'), 'joined': item.get('joined'),
             'alive': item.get('alive')} for item in startup_joins]
        startup_cleanup_facts['alive'] = any(
            _owner_alive(item) for item in startup_joins)
        # CORRECTION 22 (M3): the facts of the cleanup are **complete**
        # and they are **durable** before the priority is applied: every
        # actual error and every actual interruption of the cleanup is in
        # the document of the phase.
        for phase, document in startup_documents:
            _publish_cleanup(
                document,
                lambda p=phase, d=document: write_phase(p, d),
                startup_cleanup_errors, startup_interrupts)
        # CORRECTION 23 (M3): the document of the cleanup itself is
        # **unconditional** - the documents of the phases of the body are
        # never its only failure-evidence path - and the verdict of the
        # cleanup is recomputed **before** every attempt to write and
        # **before** the retry of a failed write.
        _publish_cleanup(
            startup_cleanup_facts,
            lambda: write_phase('r09-startup-cleanup',
                                startup_cleanup_facts),
            startup_cleanup_errors, startup_interrupts,
            verdict=lambda: _cleanup_verdict(
                startup_cleanup_errors, None,
                'the cleanup of the startup met'))
        # CORRECTION 21 (M3): the priority of the failures is enforced
        # **after** the whole traversal of the owners: the failure that
        # is already unwinding wins, then the **first** exact pending
        # interruption of the cleanup and only then the ordinary proof
        # of the round.
        _raise_first_interruption(startup_interrupts)
        # the ordinary proof of the round: it runs **after** the whole
        # traversal, so a failure of it never skips an owner of the
        # round, and it never replaces the failure that is already
        # unwinding.  The **actual** liveness of every owner is the fact
        # that the guarded join returned: the query is never repeated
        # outside its guard and an **unknown** liveness is never read as
        # the end of an owner.
        if sys.exc_info()[0] is None:
            for item in startup_joins:
                assert not _owner_alive(item), \
                    'the thread of a startup step was left behind'
        # the ordinary errors of the cleanup are **consumed**: they fail
        # the round instead of being recorded and forgotten.
        if startup_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the startup met %s'
                                 % (startup_cleanup_errors,))

    # -- N1 correction 12 (M08-C): the wait of the owner of a startup
    #    step is cropped to the time that is really left until the
    #    **current** effective deadline of the round.  The owner holds
    #    the original context and it never keeps a copy of a number.
    #    RECONCILIATION (N1 correction 13): the recorder of the queue
    #    implements the **whole** signature of ``queue.get``: the owner
    #    observes the result that is already published with a non
    #    blocking ``get_nowait`` and that observation is **not** a wait.
    #    The two are recorded apart and the recorder forwards the
    #    arguments of the original call.  The schedule of the group
    #    tightens the deadline of the round **between** two waits and
    #    the next wait receives the time that is really left.
    clock = ManualClock(1000.0)
    context = _RoundContext(clock=clock)
    context.bind_absolute_deadline(clock.value + 0.5)
    owner = _StartupOwner(name='inventory', clock=clock,
                          deadline=clock.value + 0.5, context=context)
    observed = []
    requested = []
    first_wait = threading.Event()
    original_get = owner._results.get

    def recording_get(block=True, timeout=None):
        if block is False:
            # The observation of the owner asks for the result that is
            # already published and it never waits for one.
            observed.append(timeout)
            return original_get(block=False)
        requested.append(timeout)
        if len(requested) == 1:
            first_wait.set()
        return original_get(block=True, timeout=timeout)

    owner._results.get = recording_get

    def tighten():
        # The deadline of the round is tightened **between** two waits
        # of the owner: the next wait receives the time that is really
        # left and it is cropped to it.  The last step expires the
        # round even when the barrier was never reached: the owner
        # never waits forever.
        first_wait.wait(10.0)
        clock.advance(0.49)
        time.sleep(0.2)
        clock.advance(0.02)
        clock.advance(10.0)

    tightener = threading.Thread(target=tighten, daemon=True,
                                  name='lvw-n10-r09-tightener')
    tightener.start()
    # CORRECTION 23 (M3): the facts of the cleanup of this region exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the region without a
    # durable document.
    tightener_errors = []
    tightener_interrupts = []
    tightener_cleanup_facts = _cleanup_facts('tightener')
    try:
        tightener_cleanup_facts['executed'] = True
        with pytest.raises(BrokerError) as info:
            owner.await_result()
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        tightener_cleanup_facts['original'] = _original_facts()
        # CORRECTION 21 (M3): the join of the tightener is **guarded**:
        # a failure of it is retained with its exact type and its exact
        # detail and it never replaces the failure that is already
        # unwinding.
        tightener_join = _join_owner('tightener', tightener,
                                     tightener_errors, tightener_interrupts,
                                     seconds=10.0)
        tightener_cleanup_facts['actions'].append('join:tightener')
        # CORRECTION 22 (M3): the **actual** liveness of the owner is the
        # fact that the guarded join returned: the query is never
        # repeated outside its guard.
        tightener_alive = _owner_alive(tightener_join)
        tightener_cleanup_facts['alive'] = tightener_alive
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures: the
        # diagnostics of the cleanup are durable even when the original
        # failure of the region is unwinding.
        _publish_cleanup(
            tightener_cleanup_facts,
            lambda: write_phase('r09-await-wait-cleanup',
                                tightener_cleanup_facts),
            tightener_errors, tightener_interrupts,
            verdict=lambda: _cleanup_verdict(
                tightener_errors, None,
                'the cleanup of the tightener met'))
        # the **exact** cancellation wins over the ordinary assertion of
        # the join that follows it.
        _raise_first_interruption(tightener_interrupts)
        # the ordinary proof of the round: it runs **after** the join and
        # it never replaces the failure that is already unwinding.
        if sys.exc_info()[0] is None:
            assert not tightener_alive, \
                'the thread that tightens the deadline was left behind'
    facts = {'observed': list(observed), 'requested': list(requested),
             'code': info.value.code,
             # CORRECTION 22 (M3): the facts of the cleanup of the
             # tightener are **durable**: every actual error and every
             # actual interruption of it is in the document.
             'cleanup_errors': list(tightener_errors),
             'interrupts': _interruption_facts(tightener_interrupts),
             'tightener_alive': tightener_alive}
    write_phase('r09-await-wait', facts)
    # the ordinary errors of the cleanup are **consumed**: they fail the
    # round instead of being recorded and forgotten.
    if tightener_errors and sys.exc_info()[0] is None:
        raise AssertionError('the cleanup of the tightener met %s'
                             % (tightener_errors,))
    assert info.value.code == 'BROKER_STARTUP_DEADLINE_EXCEEDED', \
        'the owner of the step did not refuse the expired round'
    assert observed, 'the owner of the step never observed its result'
    assert requested, 'the owner of the step never waited for its result'
    assert requested[0] <= 0.05 + 1e-9, \
        'the wait of the owner exceeded the poll cap of the package'
    assert max(requested) <= 0.5 + 1e-9, \
        'the wait of the owner exceeded the remaining of the round'
    # The wait that followed the tightening received the time that was
    # really left and it was cropped to it.
    assert min(requested[1:]) <= 0.01 + 1e-9, \
        'the wait of the owner was not cropped to the tightened remaining'

    # -- N1 correction 12 (M08-D): a start that raised **after** the
    #    thread of the step really came up is not a release.  The owner
    #    joins the thread that it really has, it keeps its owner while
    #    the thread is alive and a later settle of the **same** owner
    #    converges after the real exit of the thread.
    tail_release = threading.Event()
    original_start = threading.Thread.start

    def failing_start(self):
        original_start(self)
        if self.name.startswith('lvw-native-custody-startup-'):
            raise KeyboardInterrupt('start_interrupted')

    clock = time.monotonic
    core = BrokerCore(win32=RecordingWin32(), plan=sealed_plan(),
                      run_root=tmp_path, clock=clock)
    core.bind_absolute_deadline(clock() + 60.0)
    transport = type('T', (), {'bind_deadline': lambda self, value: value,
                               'write': lambda self, raw: None})()
    loop = BrokerLoop(core=core, transport=transport, plan=core.plan,
                      nonce=NONCE, clock=clock, wall=time.time)
    loop._deadline_mono = clock() + 30.0
    # CORRECTION 20 (M3): the release of the gate of the interrupted
    # start is guarded: a cancellation of it never skips the settle and
    # the join that follow it and it never replaces the failure that is
    # already unwinding.
    interrupted_cleanup_errors = []
    interrupted_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this region exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the region without a
    # durable document.
    interrupted_facts = _cleanup_facts('interrupted-start')
    # CORRECTION 23 (M3): the **observed** owner of the interrupted start
    # and its **exact** thread are held **independently** of the query of
    # the owners that are in flight.  A failure of that query never loses
    # the owner that the body really observed and it never replaces the
    # settle and the join of it.
    interrupted_observed_owner = None
    interrupted_observed_thread = None
    interrupted_owner_observed = False
    try:
        interrupted_facts['executed'] = True
        with unittest.mock.patch.object(threading.Thread, 'start',
                                        failing_start):
            with pytest.raises(KeyboardInterrupt):
                loop._run_startup('ARM', lambda: tail_release.wait(15.0))
        owner = loop._startup_owner
        assert owner is not None, 'the owner of the step was never built'
        # CORRECTION 23 (M3): the owner and its thread are recorded
        # **before** any fallible container query of the cleanup runs.
        interrupted_observed_owner = owner
        interrupted_owner_observed = True
        # OPT-B-07 (F06-M4): the **actual** owner and the **actual**
        # thread that the fixture really held are remembered for the
        # supplemental cases: they are the objects that a fault of the
        # cleanup must be compared with, and they are captured **before**
        # the fault.
        _observe_reference('r09:owner', owner)
        try:
            interrupted_observed_thread = getattr(owner, '_thread', None)
            # OPT-B-07 (F06-M4): the **actual** thread of the owner that
            # the fixture really held is observed **here**, in the body and
            # **before** any fault of the cleanup.
            _observe_reference('r09:thread', interrupted_observed_thread)
        except BaseException as error:  # noqa: BLE001 - it stays visible
            interrupted_cleanup_errors.append(
                {'kind': 'OWNER_THREAD', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(interrupted_interrupts, error)
        interrupted_facts.update({'started': owner._started,
                                  'in_flight': owner.in_flight,
                                  'retained': loop._startup_in_flight is owner})
        write_phase('r09-interrupted-start', interrupted_facts)
        # The facts of the thread decided: the thread of the step really
        # came up and the owner does not release it.
        assert owner._started is True, \
            'the facts of the thread of the step were not consulted'
        assert loop._startup_in_flight is owner, \
            'the owner of an interrupted start was released'
        assert owner.in_flight is True
        assert owner in core.context.inflight()
        # The thread of the step is really alive: the owner is still
        # the owner of it.
        tail_release.set()
        assert owner.settle(10.0) is True, \
            'the later settle of the owner did not converge'
        assert owner.in_flight is False
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        interrupted_facts['original'] = _original_facts()
        # CORRECTION 20 (M3): the release of the gate is guarded and the
        # exact object of a cancellation of it is retained.
        _release_gate(tail_release.set, interrupted_cleanup_errors,
                      interrupted_interrupts)
        interrupted_facts['actions'].append('release:gate')
        # CORRECTION 21 (M3): every owner that is still in flight is
        # attempted and every settle of it is **guarded**: a failure of
        # one settle never skips the owners that follow it and it never
        # replaces the failure that is already unwinding.
        # CORRECTION 22 (M3): the query of the owners that are in flight
        # is guarded: a failure of it is retained with its exact type and
        # its exact detail and it never skips the owner that is really
        # known.
        pending_owners = []
        try:
            pending_owners = list(loop.context.inflight())
        except BaseException as error:  # noqa: BLE001 - it stays visible
            interrupted_cleanup_errors.append(
                {'kind': 'INFLIGHT', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(interrupted_interrupts, error)
        # CORRECTION 23 (M3): the owners that the query returned are
        # **merged** with the owner that the body really observed: the
        # identity of an owner is never counted twice and the fallback
        # never loses a known owner.  A failure of the query of the owners
        # that are in flight never cancels the settle of the owner that
        # was really observed.
        merged_owners = []
        for candidate in list(pending_owners) + [interrupted_observed_owner]:
            if candidate is None:
                continue
            if any(candidate is item for item in merged_owners):
                continue
            merged_owners.append(candidate)
        interrupted_facts['actions'].append('settle:startup-owners')
        interrupted_facts['owners_attempted'] = len(merged_owners)
        for pending in merged_owners:
            try:
                pending.settle(5.0)
            except BaseException as error:  # noqa: BLE001
                interrupted_cleanup_errors.append(
                    {'kind': 'SETTLE', 'type': type(error).__name__,
                     'detail': str(error)})
                _note_interruption(interrupted_interrupts, error)
        # CORRECTION 22 (M3): the lookup of the thread of the owner is
        # guarded as well: a failure of it never skips the priority that
        # follows it.
        thread = None
        try:
            thread = getattr(loop._startup_owner, '_thread', None)
        except BaseException as error:  # noqa: BLE001 - it stays visible
            interrupted_cleanup_errors.append(
                {'kind': 'OWNER_THREAD', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(interrupted_interrupts, error)
        # CORRECTION 23 (M3): the **known** thread of the observed owner
        # is the fallback of the lookup: a failure of the lookup never
        # cancels the join of a thread that the body really observed.
        if thread is None:
            thread = interrupted_observed_thread
        interrupted_facts['actions'].append('join:interrupted-start')
        interrupted_join = None
        if thread is not None:
            interrupted_join = _join_owner(
                'interrupted-start', thread, interrupted_cleanup_errors,
                interrupted_interrupts, seconds=10.0)
        # CORRECTION 23 (M3): the liveness of a **known** owner is never
        # read from an unknown join: an owner whose thread could not be
        # determined is recorded as **unknown** and the round fails with
        # it - it is never a synthetic cleanup success.
        interrupted_liveness_known = True
        if interrupted_owner_observed and thread is None:
            interrupted_liveness_known = False
            interrupted_facts['unknown'].append('owner_thread')
            interrupted_cleanup_errors.append(
                {'kind': 'OWNER_LIVENESS_UNKNOWN', 'type': 'RuntimeError',
                 'detail': 'the thread of the observed owner of the '
                           'interrupted start could not be determined'})
        interrupted_facts['liveness_known'] = interrupted_liveness_known
        # CORRECTION 22 (M3): the facts of the cleanup are **complete**
        # and they are **durable** before the priority is applied.
        # CORRECTION 23 (M3): the publication is **unconditional** - it
        # never waits for the happy facts of the body - and the verdict of
        # the cleanup is recomputed **before** every attempt to write and
        # **before** the retry of a failed write.
        interrupted_facts['owner_alive'] = _owner_alive(interrupted_join)
        interrupted_facts['alive'] = interrupted_facts['owner_alive']
        _publish_cleanup(
            interrupted_facts,
            lambda: write_phase('r09-interrupted-start',
                                interrupted_facts),
            interrupted_cleanup_errors, interrupted_interrupts,
            verdict=lambda: _cleanup_verdict(
                interrupted_cleanup_errors, None,
                'the cleanup of the interrupted start met'))
        # the **exact** cancellation wins over the ordinary assertion of
        # the join that follows it - and it wins **after** every action
        # of the cleanup was attempted.
        _raise_first_interruption(interrupted_interrupts)
        # the ordinary proof of the round: it runs **after** every action
        # of the cleanup and it never replaces the failure that is already
        # unwinding.
        if sys.exc_info()[0] is None:
            if not interrupted_liveness_known:
                raise AssertionError(
                    'the liveness of the owner of the interrupted start is '
                    'unknown: %s' % (interrupted_cleanup_errors,))
            assert not _owner_alive(interrupted_join), \
                'the thread of a startup step was left behind'
        # the ordinary errors of the cleanup are **consumed**: they fail
        # the round instead of being recorded and forgotten.
        if interrupted_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the interrupted start met %s'
                                 % (interrupted_cleanup_errors,))

    # -- N1 correction 12 (M08-D): a start that never came up stays
    #    **unknown**: the owner is never released and no join of a
    #    thread that never started is attempted.
    #
    #    RECONCILIATION (N1 correction 14, F4): the group joined the
    #    thread of the step **unconditionally** and the thread of this
    #    subcase never started at all: the seam of the group raised
    #    **before** the original start of the thread, so the join of
    #    the fixture raised ``RuntimeError: cannot join thread before
    #    it is started``.  The facts of the start decide now: the start
    #    did not return, the thread has **no identity** and it is not
    #    alive, so the fixture skips **only** that impossible join.
    #    The unconditional bounded join stays for every thread that
    #    really started (the two phases above), an object without an
    #    identity is never read as a physical exit of a thread and the
    #    causal negative of the group - an unproved start is never
    #    released - is unchanged.
    owner = _StartupOwner(name='never', clock=time.monotonic,
                          deadline=time.monotonic() + 10.0)

    def never_started(self):
        raise RuntimeError('start_failed_before_the_thread')

    with unittest.mock.patch.object(threading.Thread, 'start',
                                    never_started):
        with pytest.raises(RuntimeError):
            owner.start(lambda: None)
    assert owner.settle(5.0) is False, \
        'an unproved start of a step was released'
    assert owner.in_flight is False
    thread = getattr(owner, '_thread', None)
    assert thread is not None, \
        'the owner of the step did not keep the thread of the step'
    # The **facts** of the start of the thread of the step.
    start_facts = {'owner_started': owner._started,
                   'ident': getattr(thread, 'ident', None),
                   'alive': bool(thread.is_alive()),
                   'settle': owner.settle(5.0),
                   'in_flight': owner.in_flight}
    write_phase('r09-never-started', start_facts)
    assert owner._started is False, \
        'the owner of the step claims that the start of its thread returned'
    assert thread.ident is None, \
        'the thread of the step really started'
    assert thread.is_alive() is False, \
        'the thread of the step is alive although it never started'
    if thread.ident is not None or thread.is_alive():
        # A thread that really started is joined **unconditionally** and
        # with a bounded wait.
        thread.join(5.0)
        assert not thread.is_alive(), \
            'the thread of a startup step was left behind'


# -- N10-R10: the outcome of the generation wins --------------------------

class _BarrierRefusal(Exception):
    """The refusal of the publication barrier of the test.

    It is a **premise** of the test and not a failure of the
    production: the production catches the ordinary exceptions of the
    seam of the round, and the outer test asserts that the premise
    failed and that the barrier never reported a success.  An exception
    that the production swallowed is never a test oracle.
    """

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class _M09TimeoutApi:
    """The primitives of a chain whose fault is published by the owner.

    The chain of the phase is the **real** chain of the round: the
    session, the handle of the broker, the channel of the round and the
    worker of its read endpoint.  The façade is the only seam and it
    does two things and nothing else:

    * it publishes the ordinary failure of the read of the **current**
      generation, and it publishes it at the moment of the coordination
      of the round - the moment at which the effective timeout of the
      round is decided;
    * it decides whether the coordination of the round **succeeds**: a
      coordination whose worker really ended is a confirmed one and a
      coordination whose worker is still alive is a failed one.

    The seam never replaces the selection of the outcome, the history
    of the error, the public stop of the round or a fact of the round:
    every one of them is the production.
    """

    def __init__(self, *, worker_holder=None, confirm_the_worker=False,
                 hold_the_worker=False):
        self.lock = threading.Lock()
        self.frames = []
        self.final = b''
        self._outcomes = queue.Queue()
        self.read_waiting = threading.Event()
        self.fault_observed = threading.Event()
        self.eof_observed = threading.Event()
        self.closed = []
        self.close_ledger = []
        self.thread_handles = []
        self.next_handle = 700
        # The ordinary failure of the read and the object of it: the
        # owner of the test keeps the **original** error object and it
        # compares it with the object that the production really kept.
        self.fault = None
        self.fault_object = None
        self.worker_holder = worker_holder if worker_holder is not None else {}
        # Whether the coordination of the round waits for the real exit
        # of the worker.  A coordination that waits is a **confirmed**
        # one and a coordination that does not wait is a **failed** one
        # while the worker is still alive.
        self.confirm_the_worker = confirm_the_worker
        # The event that holds the worker inside its own release, so
        # that the failure of the coordination is deterministic.
        self.hold_the_worker = hold_the_worker
        self.release_the_worker = threading.Event()
        self.cancel_calls = 0
        # The **checked** barrier of the publication of the outcome of
        # the generation.  The barrier is a **premise** of the test and
        # not a fact of the production: it observes the immutable
        # outcome of the **named** generation and it refuses the premise
        # when the outcome is absent, when it belongs to another
        # generation, when it does not carry the expected kind of the
        # ordinary failure or when it does not keep the **exact**
        # original error object.  A refused premise is never a passed
        # barrier and the primitive of the round never returns
        # ``REQUESTED`` as if the barrier had passed.
        self.barrier_probe = 'EXACT'
        self.barrier = {
            'probe': 'EXACT',
            'expected_generation': None,
            'probe_generation': None,
            'observed': False,
            'observed_generation': None,
            'observed_error': None,
            'observed_object': None,
            'failure': None,
            'refused': None,
            'passed': False,
            'returned': None,
            'entered_at': None,
            'observed_at': None,
            'left_at': None,
            'return_state': None,
            'generation': None,
        }
        # CORRECTION 17 (M2): the completion of the barrier is published
        # by the seam itself and the facts of the barrier are **durable**:
        # the snapshot is persisted as a real phase document when the
        # barrier is finalised, on the successful path **and** on the
        # refused path.  A shallow in-memory dictionary alone is not
        # execution evidence.
        self.barrier_completed = threading.Event()
        self.barrier_snapshot = None
        self.barrier_document = None
        self.barrier_expectation = None
        self.barrier_write_error = None
        # CORRECTION 18 (M2): the **ledger** of the phase and the name of
        # the barrier of this phase.  The attempt of the barrier is
        # marked **in the seam itself**: an assertion of the phase that
        # fails after the seam ran may never relabel the barrier as
        # ``NOT_RUN``.
        self.barrier_ledger = None
        self.barrier_name = None
        # CORRECTION 18 (M2): the durable document of the barrier is
        # written **before** the completion is published and the fact of
        # that write is recorded.
        self.barrier_persisted = False
        # CORRECTION 19 (M3): the **exact** objects of the interruptions
        # that the seam of the round met: the owner of the phase re-raises
        # the first one of them when no other failure is unwinding.
        self.interrupts = []
        # CORRECTION 20 (M3): the **exact** object of a cancellation that
        # the durable write of the barrier met: it is never reduced to a
        # type and a detail and it is never converted into an ordinary
        # assertion of the phase.
        self.barrier_interruption = None

    # -- the explicit outcomes of the reader ------------------------------
    def publish_read_fault(self):
        """Publish the ordinary failure of the read, explicitly."""
        with self.lock:
            error = self.fault
            self.fault = None
        if error is not None:
            self.publish_outcome('FAULT', error)
        return error

    def publish_outcome(self, kind, payload=None):
        self._outcomes.put((kind, payload))
        return payload

    # -- the primitives ----------------------------------------------------
    def duplicate_current_thread_handle(self):
        with self.lock:
            self.next_handle += 1
            self.thread_handles.append(self.next_handle)
            return self.next_handle

    def cancel_synchronous_io(self, handle):
        self.cancel_calls += 1
        # The coordination of the round publishes the ordinary failure
        # of the read of the current generation: the fault is really
        # published **before** the endpoint consumes the outcome.
        self.publish_read_fault()
        worker = self.worker_holder.get('worker')
        if worker is not None and not self.confirm_the_worker:
            # RECONCILIATION (N1 correction 14, F5): the cancel
            # primitive of the round enqueued the fault and returned
            # **immediately**.  The coordination of the round could then
            # reach its selection point **before** the worker had
            # published the immutable outcome of its generation: the
            # selection point had no published fault and the parallel
            # fact of the timeout could not be inferred from a later
            # observation of the fault.
            #
            # The primitive now waits, bounded, for the **immutable
            # outcome of that specific generation** before it returns.
            # The selection point of the production then really sees the
            # published fault of the round.  The wait is bounded, it
            # never decides the outcome of the generation and it never
            # replaces the error of the round.  The worker of the round
            # is held inside its own final close and release tail, so
            # the real bounded join of the coordination still FAILS.
            #
            # N1 correction 15 (M2): the wait is a **checked** barrier
            # and it **fails closed**.  The barrier demands the immutable
            # outcome of the **exact** generation, the expected kind of
            # the ordinary failure and the **exact** original error
            # object, and it demands them **before** the cancel
            # primitive returns.  A missing outcome, an outcome of
            # another generation, another kind of failure and another
            # error object are an **explicit refusal** of the premise of
            # the test: the primitive never returns ``REQUESTED`` as if
            # the barrier had passed and the record of the barrier
            # names the refusal.
            generation = self.worker_holder.get('generation')
            if generation is None:
                generation = worker._submitted
            barrier = self.barrier
            expected_generation = generation
            probe_generation = generation
            if self.barrier_probe == 'ABSENT':
                # The negative subcase: the barrier waits for the
                # outcome of a generation that was never published.
                probe_generation = generation + 1000000
            elif self.barrier_probe == 'WRONG_GENERATION':
                # The negative subcase: the premise demands the outcome
                # of another generation than the one that the round
                # really published.
                expected_generation = generation + 1
            barrier['probe'] = self.barrier_probe
            barrier['expected_generation'] = expected_generation
            barrier['probe_generation'] = probe_generation
            barrier['entered_at'] = time.monotonic()
            failure = None
            outcome = None
            # CORRECTION 18 (M2): the attempt of the barrier is marked
            # **here**, in the actual seam of the round and not in the
            # phase that waits for it: an assertion of the phase that
            # fails after this point may never relabel the barrier as
            # ``NOT_RUN`` and it may never overwrite the executed
            # barrier with a synthetic one.
            if self.barrier_ledger is not None and self.barrier_name:
                self.barrier_ledger.attempt(self.barrier_name)
            # CORRECTION 17 (M2): the barrier is **finalised** on the
            # successful path **and** on the refused path: the failure,
            # the return state and the generation and object facts are
            # recorded, the snapshot is persisted and the completion is
            # published - always, and never before the facts are there.
            try:
                if self.barrier_probe == 'ABSENT':
                    outcome = _wait_for_missing_outcome(worker,
                                                         probe_generation,
                                                         1.0)
                else:
                    outcome = _wait_for_outcome(worker, probe_generation, 15.0)
                barrier['observed_at'] = time.monotonic()
                barrier['observed'] = outcome is not None
                barrier['observed_generation'] = (
                    outcome.get('generation')
                    if outcome is not None else None)
                barrier['observed_error'] = (outcome.get('error')
                                             if outcome is not None else None)
                barrier['observed_object'] = (outcome.get('error_object')
                                             if outcome is not None else None)
                if outcome is None:
                    failure = 'BARRIER_OUTCOME_MISSING'
                elif outcome.get('generation') != expected_generation:
                    failure = 'BARRIER_GENERATION_MISMATCH'
                elif outcome.get('error') != 'RuntimeError':
                    failure = 'BARRIER_ERROR_KIND'
                elif outcome.get('error_object') is not self.fault_object:
                    failure = 'BARRIER_ERROR_OBJECT'
                barrier['failure'] = failure
                self.worker_holder['published_outcome'] = outcome
                if failure is not None:
                    # The barrier **fails closed**: the primitive of the
                    # round does not return and the premise of the test is
                    # refused explicitly.
                    barrier['refused'] = failure
                    raise _BarrierRefusal(failure)
                barrier['passed'] = True
                barrier['returned'] = 'REQUESTED'
            finally:
                # the facts of the barrier are finalised **always**: the
                # return state names the path that was taken, the
                # generation is the one that was demanded, the snapshot
                # is persisted as a real document and the completion is
                # published.
                barrier['left_at'] = time.monotonic()
                barrier['return_state'] = ('REFUSED' if failure is not None
                                           else 'PASSED')
                barrier['generation'] = expected_generation
                self.barrier_snapshot = dict(self.barrier)
                # CORRECTION 18 (M2): the durable document of the
                # barrier is written **before** the completion is
                # published: a phase that waits for the completion and
                # that reads the persisted document never reads a
                # snapshot that was not written.
                self._persist_barrier()
                # CORRECTION 20 (M3): the publication of the completion is
                # guarded: a cancellation of it never replaces the
                # original failure and the **exact** object of the
                # cancellation is retained by the owner of the phase.
                _release_gate(self.barrier_completed.set, None, self.interrupts)
        if self.confirm_the_worker:
            # The coordination waits for the real exit of the worker:
            # the bounded join of the coordination is then a confirmed
            # one.
            if worker is not None:
                worker.join(10.0)
        return 'REQUESTED'

    def _persist_barrier(self):
        """The **durable** facts of the barrier of this round.

        The facts of the barrier are written as a real phase document:
        the identity of the observed object is a **boolean** and the
        type and the detail of the failure are readable.  A shallow
        in-memory dictionary alone is not execution evidence.

        The failure of the write never replaces the fact of the barrier:
        it is recorded and it is visible to the owner of the test.
        """
        if not self.barrier_document:
            return None
        snapshot = self.barrier_snapshot or dict(self.barrier)
        observed = snapshot.get('observed_object')
        document = {
            'status': 'EXECUTED',
            'barrier': {key: value for key, value in snapshot.items()
                        if key != 'observed_object'},
            'barrier_observed_object_is_original':
                observed is self.fault_object,
            'barrier_observed_object_type': (type(observed).__name__
                                             if observed is not None else None),
            'barrier_observed_object_detail': (repr(observed)
                                               if observed is not None else None),
            'barrier_expectation': self.barrier_expectation,
            'barrier_probe': self.barrier_probe,
            'confirm_the_worker': bool(self.confirm_the_worker),
            'hold_the_worker': bool(self.hold_the_worker),
            'cancel_calls': self.cancel_calls,
            'expected_generation': self.worker_holder.get('generation'),
            'published_outcome': bool(
                self.worker_holder.get('published_outcome')),
            'barrier_persisted': True,
            'state': None,
        }
        try:
            path = write_phase(self.barrier_document, document)
        except BaseException as error:  # noqa: BLE001 - it stays visible
            self.barrier_write_error = {'type': type(error).__name__,
                                        'detail': str(error)}
            # CORRECTION 20 (M3): the **exact** object of a cancellation
            # that the durable write met is retained: the owner of the
            # phase re-raises **it** and it is never converted into an
            # ordinary assertion of the evidence.
            if isinstance(error, (KeyboardInterrupt, SystemExit)):
                self.barrier_interruption = error
            # CORRECTION 19 (M3): the **exact** object of a cancellation
            # that the durable write met is retained: it is re-raised by
            # the owner of the phase and it is never reduced to a type
            # and a detail.
            _note_interruption(getattr(self, 'interrupts', None), error)
            return None
        # CORRECTION 18 (M2): the fact of the durable write is recorded
        # and it is **consumed** by the phase: a barrier whose document
        # was not written never certifies the barrier.
        self.barrier_persisted = True
        return path

    def close_handle(self, handle):
        with self.lock:
            self.close_ledger.append(handle)
            self.closed.append(handle)
        if self.hold_the_worker:
            # The worker is held inside its own release: it is really
            # alive and the bounded join of the coordination fails.
            self.release_the_worker.wait(20.0)

    def read_stream(self, handle, size):
        with self.lock:
            if self.frames:
                return self.frames.pop(0)
        self.read_waiting.set()
        try:
            kind, payload = self._outcomes.get(timeout=30.0)
        except queue.Empty:
            self.eof_observed.set()
            return b''
        if kind == 'FRAME':
            return payload
        if kind == 'FAULT':
            self.fault_observed.set()
            raise payload
        self.eof_observed.set()
        return b''

    def write_stream(self, handle, data):
        with self.lock:
            final = self.final
            self.final = b''
        if final:
            self.publish_outcome('FRAME', final)
        return len(data)


def _m09_timeout_phase(document, plan, tmp_path, *, phase, confirm_the_worker,
                        hold_the_worker, barrier_probe='EXACT',
                        expect_barrier='PASSED', inventory=None, ledger=None,
                        store=None):
    """The dynamic schedule of the M09 obligation of this group.

    The schedule is the **production** one: a real ordinary fault is
    published for the current generation of the read of the real chain,
    the effective timeout of the round arrives **before** the endpoint
    consumes the outcome, and the coordination of the round - a
    confirmed one or a failed one - preserves the exact original error
    object and its code.  The timeout and the failure of the
    coordination are **parallel** facts: they never replace the failure
    that was really published.

    Every fact of the phase is the fact that the production returned.

    RECONCILIATION (N1 correction 14, F5): the schedule of the **failed**
    coordination reached the selection point of the production without a
    published fault: the cancel primitive of the round enqueued the
    fault of the read and returned immediately, so the coordination
    could finish before the worker had published the immutable outcome
    of its generation.  The parallel fact of the timeout could then not
    be read at all.  The seam of the failed coordination now publishes
    the real primitive fault and waits, bounded, for the **immutable
    outcome of that specific generation** before the cancel primitive
    returns, while the worker of the round is held inside its own
    final close and release tail: the real bounded join of the
    coordination still FAILS and the coordination error stays a
    **parallel** fact of the original error of the round.  The
    confirmed coordination and the required order of the schedule
    (fault published before the timeout, consumed after it) stay
    separate and unchanged.

    N1 correction 15 (M2): the wait of the seam for the outcome of the
    generation is a **checked** barrier and it **fails closed**.  The
    barrier demands the immutable outcome of the **exact** generation,
    the expected kind of the ordinary failure and the **exact** original
    error object **before** the cancel primitive returns, and it stores
    the checked order of the three facts.  A missing outcome, an outcome
    of another generation, another kind of failure and another error
    object are an **explicit refusal** of the premise of the test: the
    primitive never returns ``REQUESTED`` as if the barrier had passed.
    The production catches the ordinary exceptions of the seam, so the
    outer test reads the premise from the record of the barrier itself
    and it captures that record **before** the main assertions of the
    phase.

    The two negative subcases of the barrier (``ABSENT`` and
    ``WRONG_GENERATION``) drive the **same** failed coordination with a
    bounded transparent seam that forces an absent outcome and an
    outcome of another generation.  Their premise is **refused** and
    they are never counted as a successful failed coordination.

    The **confirmed** coordination does not use the barrier at all: it
    waits for the real exit of the worker and the record of the barrier
    says that it never ran.  The expectation of the phase names the
    three cases: ``PASSED`` for the failed coordination, ``REFUSED`` for
    the two negative subcases and ``NOT_APPLICABLE`` for the confirmed
    coordination.

    N1 correction 17 (M2): the construction of the chain is **inside**
    the guard of the phase, the barrier of the publication is waited
    for **after** the cause of the coordination - never before it - and
    the facts of the barrier are read from the **persisted** snapshot of
    the seam.  A phase that was **executed** and that failed is a
    **FAIL** with its raw facts; only a phase that was never entered is
    a ``NOT_RUN``.  The result of the phase is written **last**, after
    the two real stops and after the cleanup of the phase.
    """
    clock = ManualClock(1000.0)
    api = _M09TimeoutApi(confirm_the_worker=confirm_the_worker,
                          hold_the_worker=hold_the_worker)
    api.barrier_probe = barrier_probe
    api.barrier_document = phase + '-barrier'
    api.barrier_expectation = expect_barrier
    # CORRECTION 18 (M2): the seam of the round knows the ledger of the
    # phase and the name of the barrier of this phase: the attempt of
    # the barrier is marked **in the seam** and never only in the phase
    # that waits for it.
    api.barrier_ledger = ledger
    api.barrier_name = phase + '-barrier'
    # CORRECTION 17 (M3): the owners of the round of this phase are
    # registered by the observer of the starts: the observation is armed
    # for the **whole** phase, the construction of the chain included,
    # and it is disarmed only after the salvage of the phase.
    registry = _OwnerRegistry()
    observer = _StartObserver(registry)
    fault = RuntimeError('read_fault')
    api.fault = fault
    api.fault_object = fault
    session = None
    holder = None
    channel_closes = None
    channel_facts = None
    worker = None
    generation = None
    written = set()
    # CORRECTION 20 (M2): the **shared** fact store of the group: it
    # holds the **last actual** facts of every document and it is the
    # store that the outer recovery reads.  A phase that could not
    # persist its own terminal document never loses its facts.
    raw = store if store is not None else {}
    # CORRECTION 18 (M2/M3): the errors of this phase are **lists** and
    # they are never overwritten: a cleanup error is never replaced by a
    # later one and the first error is never the only one.
    cleanup_errors = []
    write_errors = []
    # CORRECTION 18 (M3): the **exact** objects of the interruptions
    # that the cleanup of this phase met.
    interrupts = []
    # CORRECTION 19 (M3): the seam of the round retains the **exact**
    # object of an interruption that its durable write met: the
    # cancellation of the cleanup of the phase is never reduced to a
    # type and a detail.
    api.interrupts = interrupts
    # CORRECTION 18 (M2): the **original** failure of this phase.
    original_failure = {'type': None, 'detail': None}
    names = (phase, phase + '-construction', phase + '-barrier',
             phase + '-first', phase + '-second')

    def record(name, facts):
        """Write one document of the phase and mark it as **written**.

        CORRECTION 17 (M2): the document is **persisted first** and it
        is marked only after the persistence succeeded: a document that
        the inventory of the outer test names really exists on the disk.
        """
        path = write_phase(name, facts)
        written.add(name)
        if inventory is not None:
            inventory.add(name)
        if ledger is not None:
            ledger.attempt(name)
        return path

    def record_guarded(name, facts):
        """Write one document and **never** replace an original failure.

        CORRECTION 18 (M2): the writing of the evidence of a phase that
        is already failing must never replace the original failure: the
        error of the write is retained in ``write_errors`` and the phase
        fails **closed**.
        """
        try:
            return record(name, facts)
        except BaseException as error:  # noqa: BLE001 - it stays visible
            write_errors.append({'name': name,
                                 'type': type(error).__name__,
                                 'detail': str(error)})
            _note_interruption(interrupts, error)
            return None

    def barrier_identity():
        """The durable identity facts of the barrier of this phase.

        CORRECTION 18 (M2): every rewrite of the barrier document keeps
        the **boolean** of the identity of the original error object: the
        repr of an object never carries its identity.
        """
        snapshot = api.barrier_snapshot or {}
        observed = snapshot.get('observed_object')
        return {
            'barrier_observed_object_is_original':
                observed is api.fault_object,
            'barrier_observed_object_type': (type(observed).__name__
                                             if observed is not None else None),
            'barrier_observed_object_detail': (repr(observed)
                                               if observed is not None else None),
        }

    if ledger is not None:
        for name in names:
            ledger.plan(name)
        ledger.attempt(phase + '-construction')
        # CORRECTION 18 (M2): the overall phase is attempted **before**
        # the construction of the chain: a construction that failed half
        # way is an attempted construction **and** an attempted phase -
        # the phase is never ``NOT_RUN`` when its construction ran.
        ledger.attempt(phase)
    observer_patch = observer.install()
    observer_patch.start()
    observer.arm()
    try:
        try:
            # CORRECTION 17 (M2): the construction of the chain is
            # **inside** the guard: a construction that failed half way
            # is an attempted construction with a durable document.
            session, holder, channel_closes, channel_facts = _chain(
                api, document, plan, tmp_path, clock=clock)
            # CORRECTION 18 (M2): a **successful** construction has its
            # own terminal document: the facts are written first and the
            # ``PASSED`` document is written only after them and the
            # ledger of the phase is updated only after that.
            construction_facts = {'construction': 'COMPLETED',
                                  'session_created': session is not None,
                                  'holder_keys': sorted(holder),
                                  'state': getattr(session, 'state', None)}
            raw[phase + '-construction'] = dict(construction_facts)
            record(phase + '-construction',
                   dict(construction_facts, status='EXECUTED'))
            record(phase + '-construction',
                   dict(construction_facts, status='PASSED'))
            if ledger is not None:
                ledger.pass_(phase + '-construction')
            session.start()
            # The reader of the chain is really inside its read and the
            # generation of that read is the fact of the worker itself: it
            # is never a number that the group hard codes.
            assert api.read_waiting.wait(15.0), \
                'the reader of the chain was never inside its read'
            worker = holder['read_endpoint']._reader
            assert worker is not None, 'the reader of the chain never started'
            api.worker_holder['worker'] = worker
            generation = worker._submitted
            assert generation >= 1, 'the reader of the chain never submitted'
            # The **specific** generation of the read that is in flight is
            # given to the seam of the primitive: the outcome that the
            # coordination waits for is the outcome of **that** generation
            # and never a generic event of the worker.
            api.worker_holder['generation'] = generation
            # The effective timeout of the round is tightened while the
            # read is really in flight: the absolute lease of the round
            # stays in the future and only the bound of the channel
            # expires.  **This** is the cause of the coordination of the
            # round and therefore of the barrier of the publication.
            holder['channel'].bind_deadline(clock.value + 0.5)
            clock.advance(1.0)
            # The fault of the read is published by the coordination of the
            # round and the endpoint finds it before it consumes it.
            assert api.fault_observed.wait(15.0), \
                'the ordinary failure of the read never happened'
            assert worker.outcome_published.wait(15.0), \
                'the outcome of the read was never published'
            outcome = worker.outcome(generation)
            assert outcome is not None, 'the outcome of the generation is gone'
            assert outcome['generation'] == generation, \
                'the outcome of another generation was read'
            assert outcome['error'] == 'RuntimeError', \
                'the published failure of the round is not the ordinary one'
            assert outcome['error_object'] is fault, \
                'the outcome of the generation does not keep the original error'
            # The publication of the outcome of the worker is **not** the
            # consumption of it by the endpoint: the endpoint attaches the
            # timeout to the original error object when it raises that
            # object, and the publication happens before it.  The group
            # waits for the **real** termination of the reader of the
            # channel: that is the barrier of the consumption and it is
            # never a sleep that proves it.
            reader_thread = getattr(holder['channel'], '_thread', None)
            assert reader_thread is not None, \
                'the reader thread of the channel does not exist'
            reader_thread.join(15.0)
            assert not reader_thread.is_alive(), \
                'the reader of the channel did not consume the outcome'
            # N1 correction 17 (M2): the barrier of the publication is
            # **completed** by the seam at its finalization, and the
            # finalization happened **after** the cause above.  The
            # phase waits for the completion - a bounded wait that never
            # precedes its cause - and it reads the **persisted** snapshot
            # of the seam.  The seam wrote the document durably at its
            # finalization, on the successful path and on the refused
            # path.
            # The phase attempts the barrier as well: the **seam** is the
            # authority of the attempt and this call is idempotent.
            if ledger is not None:
                ledger.attempt(phase + '-barrier')
            if expect_barrier in ('PASSED', 'REFUSED'):
                if not api.barrier_completed.wait(15.0):
                    # CORRECTION 21 (M2): the **actual** facts of the
                    # persistence of the barrier are in this terminal
                    # document: the fact of the persistence, the error of
                    # the persistence and the **observed** snapshot of the
                    # barrier - even when it is absent or incomplete.
                    # An unknown snapshot is an explicit diagnostic and it
                    # is never a fabricated expectation and never a
                    # synthetic fact.
                    observed_barrier = dict(api.barrier_snapshot or {})
                    barrier_failed_facts = dict(
                        barrier_identity(),
                        status='FAIL',
                        executed=True,
                        premise='BARRIER_NOT_COMPLETED',
                        timeout_seconds=15.0,
                        barrier_completed=False,
                        barrier_expectation=expect_barrier,
                        barrier_probe=barrier_probe,
                        barrier_persisted=bool(api.barrier_persisted),
                        barrier_write_error=api.barrier_write_error,
                        barrier_snapshot_present=bool(api.barrier_snapshot),
                        barrier_observed=observed_barrier.get('observed'),
                        barrier_observed_generation=observed_barrier.get(
                            'observed_generation'),
                        barrier_observed_error=observed_barrier.get(
                            'observed_error'),
                        barrier_return_state=observed_barrier.get(
                            'return_state'),
                        state=session.state)
                    # CORRECTION 20 (M2): the **full intended** facts of
                    # the barrier are stored **before** the terminal write
                    # is attempted: a write that fails never erases them.
                    raw[phase + '-barrier'] = dict(barrier_failed_facts)
                    written_result = record_guarded(phase + '-barrier',
                                                    barrier_failed_facts)
                    # CORRECTION 19 (M2): the terminal state of the ledger
                    # follows the **successful** terminal write: a failed
                    # write leaves the barrier ATTEMPTED and the outer
                    # inventory recovers it, best effort and bounded.
                    if ledger is not None and written_result is not None:
                        ledger.fail(phase + '-barrier', 'BARRIER_NOT_COMPLETED')
                    # CORRECTION 20 (M3): the **first** exact pending
                    # interruption of the round wins over the ordinary
                    # assertion of the evidence.
                    if interrupts:
                        raise interrupts[0]
                    raise AssertionError(
                        'the publication barrier of the round never completed')
                # CORRECTION 18 (M2): the error of the durable write of
                # the barrier is **consumed** here: a barrier whose
                # document was not written never certifies the barrier
                # and it never leaves the evidence of the phase as if it
                # had passed.
                if api.barrier_write_error is not None:
                    barrier_failed_facts = dict(
                        barrier_identity(),
                        status='FAIL',
                        executed=True,
                        premise='BARRIER_DOCUMENT_NOT_WRITTEN',
                        barrier_write_error=api.barrier_write_error,
                        barrier_persisted=bool(api.barrier_persisted),
                        barrier_completed=True,
                        barrier_expectation=expect_barrier,
                        barrier_probe=barrier_probe,
                        state=session.state)
                    # CORRECTION 20 (M2): the **full intended** facts of
                    # the barrier are stored **before** the terminal write
                    # is attempted: a write that fails never erases them
                    # and the outer recovery reuses them.
                    raw[phase + '-barrier'] = dict(barrier_failed_facts)
                    written_result = record_guarded(phase + '-barrier',
                                                    barrier_failed_facts)
                    # CORRECTION 19 (M2): the terminal state of the ledger
                    # follows the **successful** terminal write.
                    if ledger is not None and written_result is not None:
                        ledger.fail(phase + '-barrier',
                                    'BARRIER_DOCUMENT_NOT_WRITTEN')
                    # CORRECTION 20 (M3): the **exact** cancellation of
                    # the durable write of the barrier is never converted
                    # into an ordinary assertion: it is raised as
                    # **itself**, so that the priority of the phase gives
                    # it the place of the **first** exact pending
                    # interruption of the cleanup and it is never
                    # suppressed by a synthesised assertion.
                    if api.barrier_interruption is not None:
                        raise api.barrier_interruption
                    raise AssertionError(
                        'the durable barrier document of the round was not '
                        'written: %s' % (api.barrier_write_error,))
                barrier = dict(api.barrier_snapshot or {})
                raw[phase + '-barrier'] = dict(
                    barrier_identity(),
                    barrier=barrier,
                    barrier_expectation=expect_barrier,
                    barrier_probe=barrier_probe,
                    barrier_completed=True,
                    barrier_persisted=bool(api.barrier_persisted),
                    barrier_return_state=barrier.get('return_state'),
                    confirm_the_worker=bool(confirm_the_worker),
                    hold_the_worker=bool(hold_the_worker),
                    cancel_calls=api.cancel_calls,
                    expected_generation=api.worker_holder.get('generation'),
                    published_outcome=bool(
                        api.worker_holder.get('published_outcome')),
                    state=session.state)
            else:
                # The confirmed coordination does not use the barrier: the
                # document is written immediately with the empty snapshot
                # and **no wait** is performed.
                barrier = dict(api.barrier)
                raw[phase + '-barrier'] = dict(
                    barrier_identity(),
                    barrier=barrier,
                    barrier_expectation=expect_barrier,
                    barrier_probe=barrier_probe,
                    barrier_completed=False,
                    barrier_persisted=bool(api.barrier_persisted),
                    barrier_return_state=barrier.get('return_state'),
                    confirm_the_worker=bool(confirm_the_worker),
                    hold_the_worker=bool(hold_the_worker),
                    cancel_calls=api.cancel_calls,
                    expected_generation=api.worker_holder.get('generation'),
                    published_outcome=bool(
                        api.worker_holder.get('published_outcome')),
                    state=session.state)
                record(phase + '-barrier',
                       dict(raw[phase + '-barrier'], status='EXECUTED'))
            if expect_barrier == 'PASSED':
                assert barrier['failure'] is None, \
                    'the publication barrier of the round failed: %s' \
                    % barrier['failure']
                assert barrier['passed'] is True, \
                    'the publication barrier of the round did not pass'
                assert barrier['returned'] == 'REQUESTED', \
                    'the cancel primitive did not return after the barrier'
                assert barrier['observed_generation'] == generation, \
                    'the barrier observed the outcome of another generation'
                assert barrier['observed_error'] == 'RuntimeError', \
                    'the barrier did not observe the ordinary failure'
                assert barrier['observed_object'] is fault, \
                    'the barrier did not observe the original error object'
                # CORRECTION 18 (M2): the **durable** document of the
                # barrier keeps the identity of the original error object
                # as a **boolean**: the repr of an object never carries
                # its identity.
                assert raw[phase + '-barrier'][
                    'barrier_observed_object_is_original'] is True, \
                    'the durable document of the barrier does not keep the ' \
                    'identity of the original error object'
                assert barrier['entered_at'] <= barrier['observed_at'] \
                    <= barrier['left_at'], \
                    'the order of the barrier of the publication was not checked'
                assert barrier['return_state'] == 'PASSED', \
                    'the barrier of the publication did not finalise its state'
            elif expect_barrier == 'REFUSED':
                # The negative subcase: the barrier **failed closed** and
                # the premise of the test is refused explicitly.  It is
                # never counted as a successful failed coordination.
                assert barrier['failure'] is not None, \
                    'the publication barrier of the round did not fail closed'
                assert barrier['passed'] is False, \
                    'the publication barrier of the round reported a success'
                assert barrier['returned'] is None, \
                    'the cancel primitive returned as if the barrier had passed'
                assert barrier['refused'] == barrier['failure'], \
                    'the refusal of the barrier of the publication was not recorded'
                assert barrier['return_state'] == 'REFUSED', \
                    'the refused barrier of the publication did not finalise ' \
                    'its state'
            else:
                # The **confirmed** coordination: the coordination of the
                # round waits for the real exit of the worker and the
                # barrier of the publication is **not** used by it.  The
                # record of the barrier says so and it is never read as a
                # premise that the schedule did not establish.
                assert barrier['entered_at'] is None, \
                    'the barrier of the publication ran in a schedule that ' \
                    'does not use it'
                assert barrier['passed'] is False, \
                    'the barrier of the publication reported a success in a ' \
                    'schedule that does not use it'
            # CORRECTION 18 (M2): the durable document of the barrier is
            # written **before** the terminal state of the ledger is
            # updated.
            record(phase + '-barrier',
                   dict(raw[phase + '-barrier'], status='PASSED'))
            if ledger is not None:
                ledger.pass_(phase + '-barrier')
            # The endpoint raised the **original** error object and the
            # timeout is a **parallel** fact of it.
            raised = outcome['error_object']
            parallel = getattr(raised, 'lvw_parallel_timeout', None)
            assert isinstance(parallel, dict), \
                'the timeout did not stay a parallel fact of the failure'
            assert parallel.get('code') == 'BROKER_PIPE_TIMEOUT'
            assert parallel.get('generation') == generation
            coordination = parallel.get('coordination_error')
            if confirm_the_worker:
                # The coordination of the round **succeeded**: the worker
                # really ended and the failure of the coordination is not
                # a fact of the round.
                assert coordination is None, \
                    'a confirmed coordination was named as a failed one'
            else:
                # The coordination of the round **failed** and the failure
                # is a parallel fact: the original error of the round is
                # still the error that leaves.
                assert coordination == 'BrokerError', \
                    'the failed coordination was not named as a parallel fact'
            raw[phase] = {'generation': generation,
                          'outcome_error': outcome['error'],
                          'outcome_object': type(outcome['error_object']).__name__,
                          'parallel_timeout': parallel,
                          'cancel_calls': api.cancel_calls,
                          'published_before_cancel_return': bool(
                              api.worker_holder.get('published_outcome')),
                          'barrier': barrier,
                          'barrier_expectation': expect_barrier,
                          'state': session.state}
            record(phase, dict(raw[phase], status='EXECUTED'))
            # The error of the reader of the channel is the error of the
            # round: the history of the round keeps it and the two public
            # stops of the round keep it.
            if ledger is not None:
                ledger.attempt(phase + '-first')
            first = session.stop()
            first_facts = first['broker_close_facts'] or {}
            raw[phase + '-first'] = {
                'reader_error': first_facts.get('channel_reader_error'),
                'state': first['state'],
                'retained': first['broker_retained']}
            record(phase + '-first',
                   dict(raw[phase + '-first'], status='EXECUTED'))
            assert first_facts.get('channel_reader_error') == 'RuntimeError', \
                'the real fault of the round was replaced by a cancellation'
            assert first['broker_retained'] is True
            assert first['state'] == 'UNKNOWN_RETAINED'
            # CORRECTION 18 (M2): the durable document is written
            # **before** the terminal state of the ledger is updated.
            record(phase + '-first',
                   dict(raw[phase + '-first'], status='PASSED'))
            if ledger is not None:
                ledger.pass_(phase + '-first')
            if ledger is not None:
                ledger.attempt(phase + '-second')
            second = session.stop()
            second_facts = second['broker_close_facts'] or {}
            raw[phase + '-second'] = {
                'reader_error': second_facts.get('channel_reader_error'),
                'source': second_facts.get('channel_reader_error_source'),
                'state': second['state']}
            record(phase + '-second',
                   dict(raw[phase + '-second'], status='EXECUTED'))
            assert second_facts.get('channel_reader_error') == 'RuntimeError', \
                'the second attempt lost the error of the reader'
            assert second_facts.get('channel_reader_error_source') \
                == 'REPEATED_CLOSE'
            assert second['state'] == 'UNKNOWN_RETAINED'
            # CORRECTION 18 (M2): the durable document is written
            # **before** the terminal state of the ledger is updated.
            record(phase + '-second',
                   dict(raw[phase + '-second'], status='PASSED'))
            if ledger is not None:
                ledger.pass_(phase + '-second')
        except BaseException as error:
            # N1 correction 17 (M2): a phase that was **executed** and
            # that failed is a **FAIL** with the facts that it really
            # observed.  Only a phase that was **never entered** is left
            # to the inventory of the outer test, which writes it as
            # ``NOT_RUN`` without a fact of the phase.
            #
            # CORRECTION 18 (M2): the **original** failure is retained
            # and it is the one that leaves the phase.  The result
            # document of the phase is written **after** the cleanup and
            # it carries the original failure **and** the diagnostics of
            # the cleanup.  The writing of the evidence never replaces
            # the original failure: it is recorded and the phase fails
            # **closed**.
            original_failure['type'] = type(error).__name__
            original_failure['detail'] = str(error)
            for name in names:
                if name == phase:
                    # the result of the phase is written after the
                    # cleanup of the phase
                    continue
                if ledger is not None:
                    state = ledger.state(name)
                else:
                    state = 'ATTEMPTED' if name in written else 'PLANNED'
                if state != 'ATTEMPTED':
                    continue
                # the facts that the phase really observed are kept: the
                # barrier of the publication stays in the document of the
                # phase that failed
                observed = dict(raw.get(name, {}))
                if name == phase + '-construction':
                    observed.setdefault('construction', 'FAILED')
                if name.endswith('-barrier'):
                    if api.barrier_snapshot:
                        observed.setdefault('barrier',
                                            dict(api.barrier_snapshot))
                    observed.update(barrier_identity())
                    # CORRECTION 19 (M2): the rewrite of the barrier
                    # document keeps the **durable** facts of the
                    # barrier: the fact of its persistence and the error
                    # of its persistence.  An assertion of the phase that
                    # fails after the seam ran never loses the very
                    # evidence fault that the contract requires.
                    observed['barrier_persisted'] = bool(api.barrier_persisted)
                    observed['barrier_write_error'] = api.barrier_write_error
                failed_facts = dict(observed,
                                    status='FAIL',
                                    executed=True,
                                    reason=type(error).__name__,
                                    detail=str(error))
                # CORRECTION 20 (M2): the **full intended** facts of the
                # document are stored **before** the terminal write is
                # attempted: a write that fails leaves the name
                # ATTEMPTED and the outer recovery reuses these facts
                # instead of a generic ``FAIL``.
                raw[name] = dict(failed_facts)
                written_result = record_guarded(name, failed_facts)
                # CORRECTION 19 (M2): the terminal state of the ledger
                # follows the **successful** terminal write: a failed
                # write leaves the phase ATTEMPTED and the outer
                # inventory recovers it, best effort and bounded.
                if ledger is not None and written_result is not None:
                    ledger.fail(name, type(error).__name__)
            raise
        finally:
            # The teardown of the owner of the test is bounded and it is
            # unconditional: the gate is released, the read of the round
            # is ended, the production wait of the worker is restored and
            # the worker is stopped and joined.
            #
            # CORRECTION 18 (M2/M3): every step of the teardown is
            # guarded and every error is **retained** in a list: one
            # exception never skips the owners that follow it and it
            # never skips the result document of the phase.  The join and
            # the query of the worker happen **before** the drain and
            # they are guarded themselves.
            # CORRECTION 20 (M3): the **initial** release of the round is
            # guarded **on its own**: a cancellation of it never skips the
            # stop, the join, the drain, the proof and the evidence that
            # follow it and it never replaces the failure that is already
            # unwinding.
            _release_gate(api.release_the_worker.set, cleanup_errors,
                          interrupts)
            # CORRECTION 21 (M2): the **actual** returned state of the
            # public stop of the phase is kept: it is a fact of the
            # cleanup and it belongs to the durable document of the
            # phase next to the facts of the drain.
            phase_stop = None
            if session is not None:
                try:
                    phase_stop = session.stop()
                except BaseException as error:  # noqa: BLE001
                    cleanup_errors.append({'kind': 'STOP',
                                           'type': type(error).__name__,
                                           'detail': str(error)})
                    _note_interruption(interrupts, error)
            if worker is not None:
                try:
                    worker.join_bounded(10.0)
                except BaseException as error:  # noqa: BLE001
                    cleanup_errors.append({'kind': 'WORKER_JOIN',
                                           'type': type(error).__name__,
                                           'detail': str(error)})
                    _note_interruption(interrupts, error)
                try:
                    if worker.is_alive():
                        cleanup_errors.append(
                            {'kind': 'WORKER', 'type': 'AssertionError',
                             'detail': 'the worker of the read was left '
                                       'behind'})
                except BaseException as error:  # noqa: BLE001
                    cleanup_errors.append({'kind': 'WORKER_LIVENESS',
                                           'type': type(error).__name__,
                                           'detail': str(error)})
                    _note_interruption(interrupts, error)
            # CORRECTION 17 (M3): the owners of the round are drained
            # **boundedly** and the quiescence is asserted **after** the
            # drain: an owner that is still alive fails the proof of the
            # phase and every owner is still attempted.
            drain = {'salvage': [], 'attempts': [], 'proof': None,
                     'quiescent': False, 'errors': [], 'all_salvage': [], 'owner_errors': []}
            try:
                drain = _drain_owners(
                    registry, session=session,
                    channel=(holder or {}).get('channel'), prefix=phase,
                    release=lambda: api.release_the_worker.set(),
                    interrupts=interrupts)
            except BaseException as error:  # noqa: BLE001 - it stays visible
                cleanup_errors.append({'kind': 'DRAIN',
                                       'type': type(error).__name__,
                                       'detail': str(error)})
                _note_interruption(interrupts, error)
            # CORRECTION 18 (M2): the result of the phase is written
            # **after** the cleanup and it carries the original failure
            # **and** every diagnostic of the cleanup.  The phase is
            # ``PASSED`` only when the proof held, the round was
            # quiescent and no unexpected cleanup or evidence error
            # happened.
            cleanup_detail = _cleanup_detail(cleanup_errors, write_errors)
            # CORRECTION 19 (M2): the result of the phase is decided
            # **after** the cleanup and it is written **before** the
            # terminal state of the ledger is advanced.
            clean = (original_failure['type'] is None
                     and cleanup_detail is None
                     and drain['proof'] is None
                     and drain['quiescent'] is True)
            phase_failure_detail = None
            # CORRECTION 19 (M2): the durable facts of the barrier are
            # part of **every** final document of the phase: the
            # snapshot, the rewrite and the final phase keep the fact of
            # the persistence of the barrier, the error of its
            # persistence and the identity of the original object.
            barrier_facts = dict(barrier_identity())
            barrier_facts['barrier_persisted'] = bool(api.barrier_persisted)
            barrier_facts['barrier_write_error'] = api.barrier_write_error
            if clean:
                final_facts = dict(raw.get(phase, {}), status='PASSED',
                                   cleanup_errors=[],
                                   evidence_write_errors=[],
                                   proof_failure=None,
                                   quiescent=True,
                                   drain=drain['attempts'],
                                   stop=phase_stop,
                                   original_failure=dict(original_failure),
                                   interrupts=_interruption_facts(interrupts),
                                   **barrier_facts,
                                   **_drain_facts(drain))
                # CORRECTION 20 (M2): the **full intended** facts of the
                # phase are stored **before** the terminal persistence is
                # attempted: a write that fails leaves the phase
                # ATTEMPTED and the outer recovery reuses these facts.
                raw[phase] = dict(final_facts)
                written_result = record_guarded(phase, final_facts)
                if written_result is None:
                    # the evidence of the phase could not be written:
                    # the phase fails **closed** and it is never
                    # reported as a success.  Its terminal state of the
                    # ledger is **not** advanced: the outer inventory
                    # recovers it, best effort and bounded.
                    phase_failure_detail = (
                        'the result document of the phase could not be '
                        'written: %s' % (write_errors,))
                    # CORRECTION 20 (M2): the store keeps the diagnostic
                    # of the failed persistence: the retry of the outer
                    # recovery carries it and it is never reduced to a
                    # generic ``FAIL``.
                    raw[phase] = dict(final_facts,
                                      status='FAIL',
                                      evidence_write_errors=list(
                                          write_errors),
                                      detail=_join_details(
                                          final_facts.get('detail'),
                                          phase_failure_detail))
                elif ledger is not None:
                    ledger.pass_(phase)
            else:
                reason = (original_failure['type'] or 'CleanupError')
                detail = _join_details(original_failure['detail'],
                                       cleanup_detail, drain['proof'])
                if drain['quiescent'] is not True:
                    detail = _join_details(
                        detail, 'the owners of the phase were not quiescent')
                    if original_failure['type'] is None:
                        reason = 'NOT_QUIESCENT'
                failed_phase_facts = dict(raw.get(phase, {}),
                                          status='FAIL',
                                          executed=True,
                                          reason=reason,
                                          detail=detail,
                                          original_failure=dict(
                                              original_failure),
                                          cleanup_errors=list(cleanup_errors),
                                          evidence_write_errors=list(
                                              write_errors),
                                          proof_failure=drain['proof'],
                                          quiescent=drain['quiescent'],
                                          drain=drain['attempts'],
                                          stop=phase_stop,
                                          interrupts=_interruption_facts(
                                              interrupts),
                                          **barrier_facts,
                                          **_drain_facts(drain))
                # CORRECTION 20 (M2): the **full intended** facts of the
                # phase are stored **before** the terminal persistence is
                # attempted.
                raw[phase] = dict(failed_phase_facts)
                written_result = record_guarded(phase, failed_phase_facts)
                # CORRECTION 19 (M2): the terminal state of the ledger
                # follows the **successful** terminal write: a failed
                # write leaves the phase ATTEMPTED and the outer
                # inventory recovers it, best effort and bounded.
                if written_result is not None:
                    if ledger is not None:
                        ledger.fail(phase, reason)
                else:
                    phase_failure_detail = (
                        'the durable FAIL of the phase was not written: %s'
                        % (write_errors,))
                    cleanup_detail = _join_details(cleanup_detail,
                                                   phase_failure_detail)
                    # CORRECTION 20 (M2): the store keeps the diagnostic
                    # of the failed persistence of the ``FAIL``.
                    raw[phase] = dict(failed_phase_facts,
                                      evidence_write_errors=list(write_errors),
                                      detail=_join_details(
                                          failed_phase_facts.get('detail'),
                                          phase_failure_detail))
                if original_failure['type'] is None:
                    # CORRECTION 19 (M2): the diagnostic of a failed
                    # write is **joined** with the diagnostic of the
                    # phase: neither of them replaces the other.
                    phase_failure_detail = _join_details(
                        phase_failure_detail,
                        'the phase %s failed: %s' % (phase, detail))
            # CORRECTION 19 (M2/M3): the priority of the failures is
            # fixed: the failure that is already unwinding wins, then
            # the **exact** interruption of the cleanup and only then the
            # ordinary assertion of the proof or of the evidence.  An
            # exact interruption is never replaced by a proof assertion
            # and the rethrow of it is never unreachable.
            if interrupts and sys.exc_info()[0] is None:
                raise interrupts[0]
            # CORRECTION 19 (M2): a durable FAIL of the phase never
            # returns a successful test: the phase fails **with** its
            # own document.
            if phase_failure_detail is not None \
                    and sys.exc_info()[0] is None:
                raise AssertionError(phase_failure_detail)
            if cleanup_detail is not None and sys.exc_info()[0] is None:
                raise AssertionError(cleanup_detail)
            if drain['proof'] is not None and sys.exc_info()[0] is None:
                # the owners of the round were not released: the proof of
                # the cleanup fails truthfully and the phase fails with it
                raise AssertionError(drain['proof'])
    finally:
        observer.disarm()
        observer_patch.stop()
class _M09Gate:
    """The transparent gate of the wait of the worker.

    The gate is a **wrapper** of the production wait of the worker: it
    calls the **original** wait and it holds the endpoint **after** that
    wait returned and **before** the endpoint rechecks or consumes the
    outcome of its own generation.

    The gate never decides the outcome, never rewrites the history of
    the error, never touches the selection of the error of the endpoint
    and never returns a fact of its own: it only decides **when** the
    endpoint continues.  Every value that the node asserts afterwards is
    a value that the production returned.

    The gate holds **one named worker** and it holds it only while the
    read of the round is really in flight: the frames of the start of
    the round are never held and the write of the round is never held.
    """

    def __init__(self, api):
        self.api = api
        self.entered = threading.Event()
        self.release = threading.Event()
        self.calls = []
        self.target = None
        self.armed = True

    def install(self, worker_class):
        """Wrap the production wait of the worker class."""
        original = worker_class.wait_done
        gate = self

        def gated_wait_done(worker, generation, timeout):
            result = original(worker, generation, timeout)
            gate.calls.append({'generation': generation,
                               'timeout': timeout,
                               'result': bool(result)})
            if (gate.armed and not result and worker is gate.target
                    and gate.api.read_waiting.is_set()):
                # The endpoint is held **after** the production wait and
                # **before** it rechecks its generation.
                gate.entered.set()
                gate.release.wait(30.0)
            return result

        worker_class.wait_done = gated_wait_done
        return original


def _wait_for_outcome(worker, generation, seconds):
    """The immutable outcome of **that** generation of the worker.

    The generic event of the worker may be stale: the event is only a
    wake up and the **outcome of the named generation** is the fact that
    the wait is really about.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        outcome = worker.outcome(generation)
        if outcome is not None and outcome.get('error') is not None:
            return outcome
        worker.outcome_published.wait(0.05)
    return None


def _wait_for_missing_outcome(worker, generation, seconds):
    """Wait, bounded, for the outcome of a generation that never existed.

    The wait is the **negative** of the barrier of the publication: the
    outcome of that generation is never published, the wait ends with
    ``None`` and it never decides an outcome, never writes one and
    never replaces the error of the round.
    """
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        outcome = worker.outcome(generation)
        if outcome is not None:
            return outcome
        time.sleep(0.005)
    return None


def _m09_published_fault_phase(document, plan, tmp_path, *, phase,
                               inventory=None, ledger=None, store=None):
    """The schedule that the contract requires: the fault comes first.

    The ordinary failure of the read is published **before** the
    effective timeout of the round arrives and the endpoint consumes the
    outcome of its generation only **after** the timeout was decided.

    The order that is driven and recorded is therefore

        the publication of the fault -> the immutable outcome of that
        generation exists -> the effective timeout arrives -> the
        endpoint consumes the outcome.

    The gate of the schedule is a transparent wrapper of the production
    wait of the worker: it calls the original wait and it holds the
    endpoint between the wait and the recheck of its generation.  The
    fault is published **independently** of the timeout, the outcome of
    the **named** generation is waited for (the generic event of the
    worker may be stale) and the timeout of the round is advanced only
    after the outcome really exists.

    The error of the round is the **exact original error object** and
    the timeout is a **parallel** fact of it.  The history of the error
    keeps it across the channel, the handle of the broker and the two
    public stops of the round.

    N1 correction 17 (M2): the construction of the chain is **inside**
    the guard of the phase, a phase that was **executed** and that
    failed is a **FAIL** with the facts that it really observed, and
    the result of the phase is written **last**, after the two real
    stops and after the cleanup of the phase.  Only a phase that was
    never entered is left to the inventory of the outer test.
    """
    clock = ManualClock(1000.0)
    api = _M09TimeoutApi()
    fault = RuntimeError('read_fault')
    api.fault = fault
    api.fault_object = fault
    gate = _M09Gate(api)
    registry = _OwnerRegistry()
    observer = _StartObserver(registry)
    session = None
    holder = None
    channel_closes = None
    channel_facts = None
    worker = None
    generation = None
    trace = []
    written = set()
    # CORRECTION 20 (M2): the **shared** fact store of the group: it
    # holds the **last actual** facts of every document and it is the
    # store that the outer recovery reads.
    raw = store if store is not None else {}
    # CORRECTION 18 (M2/M3): the errors of this phase are **lists** and
    # they are never overwritten: a cleanup error is never replaced by a
    # later one and the first error is never the only one.
    cleanup_errors = []
    write_errors = []
    # CORRECTION 18 (M3): the **exact** objects of the interruptions
    # that the cleanup of this phase met.
    interrupts = []
    # CORRECTION 19 (M3): the seam of the round retains the **exact**
    # object of an interruption that its durable write met.
    api.interrupts = interrupts
    # CORRECTION 18 (M2): the **original** failure of this phase.
    original_failure = {'type': None, 'detail': None}
    names = (phase, phase + '-construction', phase + '-first',
             phase + '-second')

    def record(name, facts):
        """Write one document of the phase and mark it as **written**.

        CORRECTION 17 (M2): the document is **persisted first** and it
        is marked only after the persistence succeeded.
        """
        path = write_phase(name, facts)
        written.add(name)
        if inventory is not None:
            inventory.add(name)
        if ledger is not None:
            ledger.attempt(name)
        return path

    def record_guarded(name, facts):
        """Write one document and **never** replace an original failure.

        CORRECTION 18 (M2): the writing of the evidence of a phase that
        is already failing must never replace the original failure: the
        error of the write is retained in ``write_errors`` and the phase
        fails **closed**.
        """
        try:
            return record(name, facts)
        except BaseException as error:  # noqa: BLE001 - it stays visible
            write_errors.append({'name': name,
                                 'type': type(error).__name__,
                                 'detail': str(error)})
            _note_interruption(interrupts, error)
            return None

    if ledger is not None:
        for name in names:
            ledger.plan(name)
        ledger.attempt(phase + '-construction')
        # CORRECTION 18 (M2): the overall phase is attempted **before**
        # the construction of the chain: a construction that failed half
        # way is an attempted construction **and** an attempted phase.
        ledger.attempt(phase)
    original_wait_done = gate.install(_WindowsPipeWorker)
    observer_patch = observer.install()
    observer_patch.start()
    observer.arm()
    try:
        try:
            # CORRECTION 17 (M2): the construction of the chain is
            # **inside** the guard of the phase.
            session, holder, channel_closes, channel_facts = _chain(
                api, document, plan, tmp_path, clock=clock)
            # CORRECTION 18 (M2): a **successful** construction has its
            # own terminal document: the facts are written first and the
            # ``PASSED`` document is written only after them.
            construction_facts = {'construction': 'COMPLETED',
                                  'session_created': session is not None,
                                  'holder_keys': sorted(holder),
                                  'state': getattr(session, 'state', None)}
            raw[phase + '-construction'] = dict(construction_facts)
            record(phase + '-construction',
                   dict(construction_facts, status='EXECUTED'))
            record(phase + '-construction',
                   dict(construction_facts, status='PASSED'))
            if ledger is not None:
                ledger.pass_(phase + '-construction')
            session.start()
            # The reader of the chain is really inside its read and the
            # generation of that read is the fact of the worker itself: it
            # is never a number that the group hard codes.
            assert api.read_waiting.wait(15.0), \
                'the reader of the chain was never inside its read'
            worker = holder['read_endpoint']._reader
            assert worker is not None, 'the reader of the chain never started'
            gate.target = worker
            generation = worker._submitted
            assert generation >= 1, 'the reader of the chain never submitted'
            # The bound of the round is a real deadline: the timeout that
            # arrives later is the expiry of **this** bound and the absolute
            # lease of the round stays in the future.
            holder['channel'].bind_deadline(clock.value + 0.5)
            # The endpoint is held after its production wait and before it
            # rechecks its generation.
            assert gate.entered.wait(15.0), \
                'the endpoint was never held at the wait of its generation'
            trace.append({'step': 'GATE_ENTERED', 'generation': generation,
                          'clock': clock.value})
            # The ordinary failure of the read is published
            # **independently** of the timeout of the round.
            api.publish_read_fault()
            assert api.fault_observed.wait(15.0), \
                'the ordinary failure of the read never happened'
            # The **specific** outcome of that generation is waited for: the
            # generic event of the worker may be stale.
            outcome = _wait_for_outcome(worker, generation, 15.0)
            assert outcome is not None, \
                'the outcome of the generation was never published'
            trace.append({'step': 'FAULT_PUBLISHED', 'generation': generation,
                          'sequence': outcome['sequence'],
                          'error': outcome['error'],
                          'clock': clock.value})
            assert outcome['generation'] == generation, \
                'the outcome of another generation was read'
            assert outcome['error'] == 'RuntimeError', \
                'the published failure of the round is not the ordinary one'
            assert outcome['error_object'] is fault, \
                'the outcome of the generation does not keep the original error'
            # The effective timeout of the round arrives **now**: the fault
            # is already published and the endpoint has not consumed it.
            clock.advance(1.0)
            trace.append({'step': 'TIMEOUT_ARRIVED', 'generation': generation,
                          'clock': clock.value,
                          'effective': holder['channel']._effective_deadline()})
            # The endpoint continues: it rechecks the timeout and it finds
            # the published outcome of its own generation.
            gate.release.set()
            trace.append({'step': 'RELEASED', 'generation': generation,
                          'clock': clock.value})
            # The endpoint consumed the outcome: the original error object
            # carries the timeout as a **parallel** fact.
            deadline = time.monotonic() + 15.0
            parallel = None
            while time.monotonic() < deadline:
                parallel = getattr(fault, 'lvw_parallel_timeout', None)
                if parallel is not None:
                    break
                time.sleep(0.005)
            assert isinstance(parallel, dict), \
                'the endpoint did not consume the published outcome'
            trace.append({'step': 'OUTCOME_CONSUMED', 'generation': generation,
                          'clock': clock.value, 'parallel': parallel})
            assert parallel.get('code') == 'BROKER_PIPE_TIMEOUT', \
                'the timeout did not stay a parallel fact of the failure'
            assert parallel.get('generation') == generation, \
                'the parallel fact names another generation'
            # The order of the three facts is the order of the contract:
            # the publication of the fault, the arrival of the timeout and
            # the consumption of the outcome.
            steps = [item['step'] for item in trace]
            assert steps.index('FAULT_PUBLISHED') < steps.index('TIMEOUT_ARRIVED'), \
                'the timeout of the round arrived before the fault was published'
            assert steps.index('TIMEOUT_ARRIVED') < steps.index('OUTCOME_CONSUMED'), \
                'the outcome was consumed before the timeout of the round arrived'
            raw[phase] = {'generation': generation, 'trace': trace,
                          'outcome_error': outcome['error'],
                          'outcome_object': type(outcome['error_object']).__name__,
                          'parallel_timeout': parallel,
                          'gate_calls': gate.calls,
                          'state': session.state}
            record(phase, dict(raw[phase], status='EXECUTED'))
            # The error of the reader of the channel is the error of the
            # round: the history of the round keeps it and the two public
            # stops of the round keep it.
            if ledger is not None:
                ledger.attempt(phase + '-first')
            first = session.stop()
            first_facts = first['broker_close_facts'] or {}
            raw[phase + '-first'] = {
                'reader_error': first_facts.get('channel_reader_error'),
                'state': first['state'],
                'retained': first['broker_retained']}
            record(phase + '-first',
                   dict(raw[phase + '-first'], status='EXECUTED'))
            assert first_facts.get('channel_reader_error') == 'RuntimeError', \
                'the real fault of the round was replaced by a cancellation'
            assert first['broker_retained'] is True
            assert first['state'] == 'UNKNOWN_RETAINED'
            # CORRECTION 18 (M2): the durable document is written
            # **before** the terminal state of the ledger is updated.
            record(phase + '-first',
                   dict(raw[phase + '-first'], status='PASSED'))
            if ledger is not None:
                ledger.pass_(phase + '-first')
            if ledger is not None:
                ledger.attempt(phase + '-second')
            second = session.stop()
            second_facts = second['broker_close_facts'] or {}
            raw[phase + '-second'] = {
                'reader_error': second_facts.get('channel_reader_error'),
                'source': second_facts.get('channel_reader_error_source'),
                'state': second['state']}
            record(phase + '-second',
                   dict(raw[phase + '-second'], status='EXECUTED'))
            assert second_facts.get('channel_reader_error') == 'RuntimeError', \
                'the second attempt lost the error of the reader'
            assert second_facts.get('channel_reader_error_source') \
                == 'REPEATED_CLOSE'
            assert second['state'] == 'UNKNOWN_RETAINED'
            # CORRECTION 18 (M2): the durable document is written
            # **before** the terminal state of the ledger is updated.
            record(phase + '-second',
                   dict(raw[phase + '-second'], status='PASSED'))
            if ledger is not None:
                ledger.pass_(phase + '-second')
        except BaseException as error:
            # N1 correction 17 (M2): a phase that was **executed** and
            # that failed is a **FAIL** with the facts that it really
            # observed.  Only a phase that was **never entered** is left
            # to the inventory of the outer test.
            #
            # CORRECTION 18 (M2): the **original** failure is retained
            # and it is the one that leaves the phase; the result
            # document of the phase is written **after** the cleanup and
            # it carries the original failure **and** the diagnostics of
            # the cleanup.  The writing of the evidence never replaces
            # the original failure.
            original_failure['type'] = type(error).__name__
            original_failure['detail'] = str(error)
            for name in names:
                if name == phase:
                    # the result of the phase is written after the
                    # cleanup of the phase
                    continue
                if ledger is not None:
                    state = ledger.state(name)
                else:
                    state = 'ATTEMPTED' if name in written else 'PLANNED'
                if state != 'ATTEMPTED':
                    continue
                failed_facts = dict(raw.get(name, {}),
                                    status='FAIL',
                                    executed=True,
                                    reason=type(error).__name__,
                                    detail=str(error),
                                    trace=list(trace),
                                    gate_calls=list(gate.calls),
                                    cancel_calls=api.cancel_calls)
                # CORRECTION 20 (M2): the **full intended** facts of the
                # document are stored **before** the terminal write is
                # attempted: the outer recovery reuses them.
                raw[name] = dict(failed_facts)
                written_result = record_guarded(name, failed_facts)
                # CORRECTION 19 (M2): the terminal state of the ledger
                # follows the **successful** terminal write: a failed
                # write leaves the phase ATTEMPTED and the outer
                # inventory recovers it, best effort and bounded.
                if ledger is not None and written_result is not None:
                    ledger.fail(name, type(error).__name__)
            raise
        finally:
            # The teardown of the owner of the test is bounded and it is
            # unconditional: the gate is released, the read of the round is
            # ended, the production wait of the worker is restored and the
            # worker is stopped and joined.
            #
            # CORRECTION 18 (M2/M3): every step of the teardown is
            # guarded and every error is **retained** in a list: one
            # exception never skips the owners that follow it and it
            # never skips the result document of the phase.
            # CORRECTION 20 (M3): every **initial** release of a gate is
            # guarded **on its own**: a cancellation of the first gate
            # never skips the second one, never skips the stop, the
            # joins, the drain, the proof and the evidence that follow it
            # and it never replaces the failure that is already
            # unwinding.
            _release_gate(gate.release.set, cleanup_errors, interrupts)
            _release_gate(api.release_the_worker.set, cleanup_errors,
                          interrupts)
            _release_gate(lambda: api.publish_outcome('EOF'), cleanup_errors,
                          interrupts)
            _WindowsPipeWorker.wait_done = original_wait_done
            # CORRECTION 21 (M2): the **actual** returned state of the
            # public stop of the phase is kept: it is a fact of the
            # cleanup and it belongs to the durable document of the
            # phase next to the facts of the drain.
            phase_stop = None
            if session is not None:
                try:
                    phase_stop = session.stop()
                except BaseException as error:  # noqa: BLE001
                    cleanup_errors.append({'kind': 'STOP',
                                           'type': type(error).__name__,
                                           'detail': str(error)})
                    _note_interruption(interrupts, error)
            if worker is not None:
                # The worker is stopped explicitly: the coordination of the
                # round was never reached in this schedule and the worker of
                # the read would otherwise wait for a request that never
                # comes.
                try:
                    worker.stop_accepting()
                except BaseException as error:  # noqa: BLE001
                    cleanup_errors.append({'kind': 'WORKER_STOP',
                                           'type': type(error).__name__,
                                           'detail': str(error)})
                    _note_interruption(interrupts, error)
                try:
                    worker.join_bounded(10.0)
                except BaseException as error:  # noqa: BLE001
                    cleanup_errors.append({'kind': 'WORKER_JOIN',
                                           'type': type(error).__name__,
                                           'detail': str(error)})
                    _note_interruption(interrupts, error)
                try:
                    if worker.is_alive():
                        cleanup_errors.append(
                            {'kind': 'WORKER', 'type': 'AssertionError',
                             'detail': 'the worker of the read was left '
                                       'behind'})
                except BaseException as error:  # noqa: BLE001
                    cleanup_errors.append({'kind': 'WORKER_LIVENESS',
                                           'type': type(error).__name__,
                                           'detail': str(error)})
                    _note_interruption(interrupts, error)
            drain = {'salvage': [], 'attempts': [], 'proof': None,
                     'quiescent': False, 'errors': [], 'all_salvage': [], 'owner_errors': []}
            try:
                drain = _drain_owners(
                    registry, session=session,
                    channel=(holder or {}).get('channel'), prefix=phase,
                    release=(lambda: gate.release.set(),
                             lambda: api.release_the_worker.set()),
                    interrupts=interrupts)
            except BaseException as error:  # noqa: BLE001 - it stays visible
                cleanup_errors.append({'kind': 'DRAIN',
                                       'type': type(error).__name__,
                                       'detail': str(error)})
                _note_interruption(interrupts, error)
            # CORRECTION 18 (M2): the result of the phase is written
            # **after** the cleanup and it carries the original failure
            # **and** every diagnostic of the cleanup.  The phase is
            # ``PASSED`` only when the proof held, the round was
            # quiescent and no unexpected cleanup or evidence error
            # happened.
            cleanup_detail = _cleanup_detail(cleanup_errors, write_errors)
            # CORRECTION 19 (M2): the result of the phase is decided
            # **after** the cleanup and it is written **before** the
            # terminal state of the ledger is advanced.
            clean = (original_failure['type'] is None
                     and cleanup_detail is None
                     and drain['proof'] is None
                     and drain['quiescent'] is True)
            phase_failure_detail = None
            if clean:
                final_facts = dict(raw.get(phase, {}), status='PASSED',
                                   cleanup_errors=[],
                                   evidence_write_errors=[],
                                   proof_failure=None,
                                   quiescent=True,
                                   drain=drain['attempts'],
                                   stop=phase_stop,
                                   original_failure=dict(original_failure),
                                   interrupts=_interruption_facts(interrupts),
                                   **_drain_facts(drain))
                # CORRECTION 20 (M2): the **full intended** facts of the
                # phase are stored **before** the terminal persistence is
                # attempted.
                raw[phase] = dict(final_facts)
                written_result = record_guarded(phase, final_facts)
                if written_result is None:
                    # the evidence of the phase could not be written:
                    # the phase fails **closed** and it is never
                    # reported as a success.  Its terminal state of the
                    # ledger is **not** advanced: the outer inventory
                    # recovers it, best effort and bounded.
                    phase_failure_detail = (
                        'the result document of the phase could not be '
                        'written: %s' % (write_errors,))
                    # CORRECTION 20 (M2): the store keeps the diagnostic
                    # of the failed persistence: the retry of the outer
                    # recovery carries it and it is never reduced to a
                    # generic ``FAIL``.
                    raw[phase] = dict(final_facts,
                                      status='FAIL',
                                      evidence_write_errors=list(
                                          write_errors),
                                      detail=_join_details(
                                          final_facts.get('detail'),
                                          phase_failure_detail))
                elif ledger is not None:
                    ledger.pass_(phase)
            else:
                reason = (original_failure['type'] or 'CleanupError')
                detail = _join_details(original_failure['detail'],
                                       cleanup_detail, drain['proof'])
                if drain['quiescent'] is not True:
                    detail = _join_details(
                        detail, 'the owners of the phase were not quiescent')
                    if original_failure['type'] is None:
                        reason = 'NOT_QUIESCENT'
                failed_phase_facts = dict(raw.get(phase, {}),
                                          status='FAIL',
                                          executed=True,
                                          reason=reason,
                                          detail=detail,
                                          original_failure=dict(
                                              original_failure),
                                          cleanup_errors=list(cleanup_errors),
                                          evidence_write_errors=list(
                                              write_errors),
                                          proof_failure=drain['proof'],
                                          quiescent=drain['quiescent'],
                                          drain=drain['attempts'],
                                          stop=phase_stop,
                                          interrupts=_interruption_facts(
                                              interrupts),
                                          **_drain_facts(drain))
                # CORRECTION 20 (M2): the **full intended** facts of the
                # phase are stored **before** the terminal persistence is
                # attempted.
                raw[phase] = dict(failed_phase_facts)
                written_result = record_guarded(phase, failed_phase_facts)
                # CORRECTION 19 (M2): the terminal state of the ledger
                # follows the **successful** terminal write: a failed
                # write leaves the phase ATTEMPTED and the outer
                # inventory recovers it, best effort and bounded.
                if written_result is not None:
                    if ledger is not None:
                        ledger.fail(phase, reason)
                else:
                    phase_failure_detail = (
                        'the durable FAIL of the phase was not written: %s'
                        % (write_errors,))
                    cleanup_detail = _join_details(cleanup_detail,
                                                   phase_failure_detail)
                    # CORRECTION 20 (M2): the store keeps the diagnostic
                    # of the failed persistence of the ``FAIL``.
                    raw[phase] = dict(failed_phase_facts,
                                      evidence_write_errors=list(write_errors),
                                      detail=_join_details(
                                          failed_phase_facts.get('detail'),
                                          phase_failure_detail))
                if original_failure['type'] is None:
                    # CORRECTION 19 (M2): the diagnostic of a failed
                    # write is **joined** with the diagnostic of the
                    # phase: neither of them replaces the other.
                    phase_failure_detail = _join_details(
                        phase_failure_detail,
                        'the phase %s failed: %s' % (phase, detail))
            # CORRECTION 19 (M2/M3): the priority of the failures is
            # fixed: the failure that is already unwinding wins, then
            # the **exact** interruption of the cleanup and only then the
            # ordinary assertion of the proof or of the evidence.  An
            # exact interruption is never replaced by a proof assertion
            # and the rethrow of it is never unreachable.
            if interrupts and sys.exc_info()[0] is None:
                raise interrupts[0]
            # CORRECTION 19 (M2): a durable FAIL of the phase never
            # returns a successful test: the phase fails **with** its
            # own document.
            if phase_failure_detail is not None \
                    and sys.exc_info()[0] is None:
                raise AssertionError(phase_failure_detail)
            if cleanup_detail is not None and sys.exc_info()[0] is None:
                raise AssertionError(cleanup_detail)
            if drain['proof'] is not None and sys.exc_info()[0] is None:
                # the owners of the round were not released: the proof of
                # the cleanup fails truthfully and the phase fails with it
                raise AssertionError(drain['proof'])
    finally:
        observer.disarm()
        observer_patch.stop()
def test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation(tmp_path):
    """N10-R10 (M09): a real fault of the round is never a benign cancel.

    Obligation: the worker of an endpoint keeps the **outcome** of
    every generation it runs: the result, the error, the original error
    object and the order of the completion.  A failure that was really
    published **before** the cancellation of the round is the first
    error of the round: a close that sets the cancel flag afterwards
    may not replace it and it may not turn it into a benign
    cancellation.  The identity of the token of the cancel is not a
    proof: the order of the two facts is the proof.  The error of the
    reader is a **history**: two real stops of the round keep it and
    the round stays unknown.

    Entry: ``_WindowsPipeWorker.outcome``,
    ``_WindowsPipeWorker.published_before_cancel``,
    ``_WindowsPipeEndpoint._raise_cancellation``,
    ``BrokerProcess._keep_reader_error_history`` and
    ``NativeCustodySession.stop``.  Trigger: the read of the
    generation fails with an ordinary error, the outcome of the
    generation is really published and the close of the round asks for
    the cancellation of the same generation.  Oracle: the original
    error object is the one that leaves, the code of the error is the
    code of the real fault and the two stops of the round keep it.
    Negative: a cancellation may never rewrite a published failure.
    Returned state: the outcome of the generation is named with its
    order and its error object.  Salvage: the owner of the test stops
    the round in every case.

    CORRECTION 11 (M09): the outcome of the **same** generation is
    inspected **again** after the coordination of the cancellation, and
    it is inspected **before** a new timeout is decided.  The published
    failure of the generation remains the primary error of the round and
    the failure of the coordination and a new timeout are **parallel**
    facts: they never replace it and they never hide it.  The group
    drives the coordination of a cancellation whose fault of the round
    is published while the coordination runs, and it proves the order
    of the two facts with the auxiliary static proof of the group.

    CORRECTION 12 (M09): the auxiliary static proof is **replaced** by
    the dynamic schedule of the obligation.  The real chain of the round
    publishes a real ordinary fault for the **current** generation of
    its read, the effective timeout of the round arrives **before** the
    endpoint consumes the outcome, and both a **confirmed** and a
    **failed** coordination of the round preserve the exact original
    error object and its code: the timeout and the failure of the
    coordination are parallel facts and they never replace the failure
    that was really published.  The history of the error keeps it
    across the channel, the handle of the broker and the two public
    stops of the round, and the round stays unknown.  The generation of
    the blocked read is the fact of the worker itself and it is never a
    number that the group hard codes.

    CORRECTION 12 (root preflight PF12-01): the **required order** is
    driven as well and it is driven **distinctly** from the two
    coordination subcases above.  The ordinary failure of the read is
    published **first** and the immutable outcome of **that** generation
    really exists before the effective timeout of the round arrives;
    the endpoint consumes the outcome only after the timeout was
    decided.  The gate of that schedule is a transparent wrapper of the
    production wait of the worker: it calls the original wait and it
    holds the endpoint between that wait and the recheck of its
    generation.  The publication, the timeout and the consumption are
    recorded in their order and the current generation is named with
    them.  The coordination subcases above remain: they are the ones
    that drive a **confirmed** and a **failed** coordination of the
    round, and the failure of the coordination is a parallel fact there.

    RECONCILIATION (N1 correction 14, F5): the schedule of the **failed**
    coordination reached the selection point of the production without a
    published fault.  The cancel primitive of the round enqueued the
    fault of the read and returned immediately, so the coordination
    could finish before the worker had published the immutable outcome
    of its generation, and the parallel fact of the timeout could not
    be read at all (the phase document of the failed batch of the
    correction 13 stopped there).

    The seam of the failed coordination now publishes the **real**
    primitive fault and waits, bounded, for the **immutable outcome of
    that specific generation** before the cancel primitive returns,
    while the worker of the round is held inside its own final close
    and release tail: the real bounded join of the coordination still
    FAILS and the coordination error stays a **parallel** fact of the
    original error of the round.  The confirmed coordination, the
    required order of the schedule (fault published before the timeout,
    consumed after it) and the two public stops of the round stay
    separate and unchanged, no outcome, no history, no selection and
    no public stop of the production is patched, and no assertion of
    the group is relaxed.

    N1 correction 15 (M2): the wait of the seam for the outcome is a
    **checked** barrier and it **fails closed**.  The barrier demands
    the immutable outcome of the **exact** generation, the expected kind
    of the ordinary failure and the **exact** original error object
    **before** the cancel primitive returns, and it stores the checked
    monotonic order of the three facts.  A missing outcome, an outcome
    of another generation, another kind of failure and another error
    object are an **explicit refusal** of the premise of the test: the
    primitive never returns ``REQUESTED`` as if the barrier had passed.
    The production catches the ordinary exceptions of the seam, so the
    outer test reads the premise from the record of the barrier itself
    and it captures that record **before** the main assertions of the
    phase.

    The two negative subcases of the barrier drive the **same** failed
    coordination with a bounded transparent seam that forces an absent
    outcome and an outcome of another generation.  Their premise is
    **refused** and they are never counted as a successful failed
    coordination.  The confirmed coordination, the required order of the
    schedule and the two public stops of the round stay separate and
    unchanged.

    N1 correction 16 (M2): the facts of the barrier are written
    **before** the main assertions of the phase, so a barrier that
    failed closed keeps its failure, its order and its object even when
    the main assertions of the phase fail afterwards.  A phase that was
    **executed** and that failed is a **FAIL** and it keeps the facts
    that it really observed; only the documents that were genuinely
    not reached are ``NOT_RUN``.  The **outer** inventory of the group
    names every main schedule and both negative subcases before they
    run: the failure of an earlier schedule may never leave the
    evidence of a later one ambiguous.
    """
    # -- N1 correction 17 (M2): the **outer** inventory of the phases of
    #    this group is installed **before** any setup and before any
    #    assertion of the group, and it is **complete**: every name that
    #    a schedule really writes is named here and every name that is
    #    never entered is written as ``NOT_RUN`` without a fact.
    #
    #    The arithmetic of the inventory is derived from the operations
    #    that are really instrumented:
    #
    #    * four timeout schedules with five names each - the result of
    #      the phase, the construction of the chain, the barrier of the
    #      publication, the first stop and the second stop - that is 20;
    #    * the published-before-timeout schedule with four names - the
    #      result of the phase, the construction of the chain, the first
    #      stop and the second stop - because its construction is
    #      instrumented like the construction of the other schedules;
    #    * the three documents of the earlier work of the group - the
    #      first stop, the second stop and the coordination;
    #    * the final verdict of the earlier work of the group - the
    #      salvage of that round - because its terminal document is
    #      written **after** its cleanup, exactly like the terminal
    #      document of every later schedule;
    #
    #    that is 28 names, and every one of them is unique.
    ledger = _PhaseLedger()
    r10_documents = []
    for r10_name in ('r10-timeout-confirmed', 'r10-timeout-failed',
                      'r10-barrier-absent', 'r10-barrier-wrong-generation'):
        r10_documents.extend([r10_name, r10_name + '-construction',
                               r10_name + '-barrier', r10_name + '-first',
                               r10_name + '-second'])
    r10_documents.extend(['r10-published-before-timeout',
                           'r10-published-before-timeout-construction',
                           'r10-published-before-timeout-first',
                           'r10-published-before-timeout-second'])
    r10_documents.extend(['r10-first', 'r10-second', 'r10-coordination',
                           'r10-early-salvage'])
    assert len(r10_documents) == len(set(r10_documents)), \
        'the inventory of the group names a document twice'
    for r10_name in r10_documents:
        ledger.plan(r10_name)
    r10_inventory = set()
    r10_raw = {}
    first_failure = {'type': None}
    # CORRECTION 19 (M3): the **exact** objects of the interruptions
    # that the inventory of the group met.
    outer_interrupts = []
    # CORRECTION 17 (M3): the observer of the starts of the round of the
    # earlier work of the group.
    early_registry = _OwnerRegistry()
    early_observer = _StartObserver(early_registry)
    try:
        document = _live_plan_document()
        plan = validate_launch_plan(document, now=time.time())
        api = _F5Api(read_fault=RuntimeError('read_fault'))
        # the observation of the starts covers **only** the round of the
        # earlier work: it is armed before the chain is built and it is
        # disarmed after the salvage of that round.
        early_observer_patch = early_observer.install()
        early_observer_patch.start()
        early_observer.arm()
        try:
            # CORRECTION 18 (M3): the construction of the chain is
            # **inside** the guard of the round: a construction that
            # failed half way still owns its teardown and its proof.
            session = None
            holder = None
            channel_closes = None
            channel_facts = None
            early_cleanup_errors = []
            # CORRECTION 19 (M3): the **exact** objects of the
            # interruptions that the cleanup of the earlier work met.
            early_interrupts = []
            # CORRECTION 19 (M2): the **original** failure of the earlier
            # work: it is durable and it never disappears behind a
            # diagnostic of the cleanup.
            early_original = {'type': None, 'detail': None}
            # CORRECTION 19 (M2): the attempt of the final verdict of the
            # earlier work is marked **before** the round is built.
            ledger.attempt('r10-early-salvage')
            try:
                session, holder, channel_closes, channel_facts = _chain(
                    api, document, plan, tmp_path)
                session.start()
                reader = holder['read_endpoint']._reader
                assert reader is not None, 'the reader of the chain never started'
                # The owner of the test publishes the ordinary failure of the
                # read and waits for the reader to be really inside its read.
                assert api.read_waiting.wait(15.0), \
                    'the reader of the chain was never inside its read'
                # The generation of the read that is really in flight is the
                # fact of the worker itself: the two frames of the round were
                # read before it and the generation of the blocked read is
                # never a number that the group hard codes.
                generation = reader._submitted
                assert generation >= 1, 'the reader of the chain never submitted'
                api.publish_read_fault()
                assert api.fault_observed.wait(15.0), \
                    'the ordinary failure of the read never happened'
                # The barrier: the outcome of the generation is really published
                # and it carries the **original** error object.
                assert reader.outcome_published.wait(15.0), \
                    'the outcome of the read was never published'
                outcome = reader.outcome(generation)
                assert outcome is not None, 'the outcome of the generation is gone'
                assert outcome['generation'] == generation, \
                    'the outcome of another generation was read'
                assert outcome['error'] == 'RuntimeError'
                assert isinstance(outcome['error_object'], RuntimeError)
                # The close of the round asks for the cancellation of the same
                # generation **after** the failure was published.
                holder['channel']._cancel.set()
                ledger.attempt('r10-first')
                first = session.stop()
                first_facts = first['broker_close_facts'] or {}
                r10_raw['r10-first'] = {
                    'generation': generation,
                    'outcome_error': outcome['error'],
                    'outcome_object':
                    type(outcome['error_object']).__name__,
                    'sequence': outcome['sequence'],
                    'reader_error':
                    first_facts.get('channel_reader_error'),
                    'state': first['state']}
                write_phase('r10-first', dict(r10_raw['r10-first'],
                                              status='EXECUTED'))
                r10_inventory.add('r10-first')
                assert first_facts.get('channel_reader_error') == 'RuntimeError', \
                    'the real fault of the round was replaced by a cancellation'
                assert first_facts.get('close_cancellation') is None
                assert first['broker_retained'] is True
                assert first['state'] == 'UNKNOWN_RETAINED'
                # CORRECTION 18 (M2): the durable document is written
                # **before** the terminal state of the ledger is updated.
                write_phase('r10-first', dict(r10_raw['r10-first'],
                                              status='PASSED'))
                ledger.pass_('r10-first')

                # The second public stop of the round: the error of the reader is
                # a history and it is never lost.
                ledger.attempt('r10-second')
                second = session.stop()
                second_facts = second['broker_close_facts'] or {}
                r10_raw['r10-second'] = {
                    'reader_error': second_facts.get('channel_reader_error'),
                    'source': second_facts.get('channel_reader_error_source'),
                    'state': second['state']}
                write_phase('r10-second', dict(r10_raw['r10-second'],
                                               status='EXECUTED'))
                r10_inventory.add('r10-second')
                assert second_facts.get('channel_reader_error') == 'RuntimeError', \
                    'the second attempt lost the error of the reader'
                assert second_facts.get('channel_reader_error_source') \
                    == 'REPEATED_CLOSE'
                assert second['broker_retained'] is True
                assert second['state'] == 'UNKNOWN_RETAINED'
                write_phase('r10-second', dict(r10_raw['r10-second'],
                                               status='PASSED'))
                ledger.pass_('r10-second')
            except BaseException as error:  # noqa: BLE001 - it stays visible
                # CORRECTION 19 (M2): the **original** failure of the
                # earlier work is retained and it is durable: the final
                # verdict of the cleanup carries it next to the errors of
                # the cleanup.
                early_original['type'] = type(error).__name__
                early_original['detail'] = str(error)
                raise
            finally:
                # CORRECTION 18 (M3): every step of the teardown is
                # guarded and every error is **retained** in a list: one
                # exception never skips the drain of the owners and it
                # never skips the proof of the cleanup.
                #
                # CORRECTION 19 (M3): the **exact** object of a
                # cancellation of the cleanup is retained and it is
                # re-raised by the owner of the earlier work.
                if session is not None:
                    try:
                        session.stop()
                    except BaseException as error:  # noqa: BLE001
                        early_cleanup_errors.append(
                            {'kind': 'STOP',
                             'type': type(error).__name__,
                             'detail': str(error)})
                        _note_interruption(early_interrupts, error)
                # CORRECTION 17 (M3): the owners of the round of the earlier
                # work are drained **boundedly** and the quiescence is
                # asserted **after** the drain.
                early_drain = {'salvage': [], 'attempts': [], 'proof': None,
                               'quiescent': False, 'errors': [],
                               'all_salvage': [], 'owner_errors': []}
                try:
                    early_drain = _drain_owners(
                        early_registry, session=session,
                        channel=(holder or {}).get('channel'),
                        prefix='r10-early',
                        interrupts=early_interrupts)
                except BaseException as error:  # noqa: BLE001
                    early_cleanup_errors.append(
                        {'kind': 'DRAIN',
                         'type': type(error).__name__,
                         'detail': str(error)})
                    _note_interruption(early_interrupts, error)
                # CORRECTION 19 (M2): the **final verdict** of the
                # earlier work is computed **after** the cleanup and it
                # is written **before** the terminal state of the ledger
                # is advanced.  The passed subchecks keep their own
                # documents and they are never rewritten by it.
                early_failure = None
                if early_original['type'] is not None:
                    # CORRECTION 20 (M2): the **final verdict** of the
                    # earlier work is a **FAIL** when its **original**
                    # failure is not None: a cleanup that is clean never
                    # certifies a round that really failed and the
                    # verdict of the operation is never the verdict of
                    # its subchecks.
                    early_failure = ('the earlier work of the group failed: '
                                     '%s: %s' % (early_original['type'],
                                                 early_original['detail']))
                elif early_drain['proof'] is not None:
                    early_failure = early_drain['proof']
                elif early_drain['quiescent'] is not True:
                    early_failure = ('the owners of the earlier work of the '
                                     'group were not quiescent')
                elif early_cleanup_errors:
                    early_failure = ('the cleanup of the earlier work of the '
                                     'group met %s'
                                     % (early_cleanup_errors,))
                early_document = {
                    'salvage': early_drain['salvage'],
                    'all_salvage': early_drain.get('all_salvage', []),
                    'drain': early_drain['attempts'],
                    'quiescent': early_drain['quiescent'],
                    'proof_failure': early_drain['proof'],
                    'cleanup_errors': list(early_cleanup_errors),
                    'original_failure': dict(early_original),
                    'interrupts': _interruption_facts(early_interrupts),
                    'status': ('PASSED' if early_failure is None else 'FAIL'),
                    **_drain_facts(early_drain)}
                if early_failure is not None:
                    early_document['executed'] = True
                    early_document['reason'] = (early_original['type']
                                                or 'EarlyCleanup')
                    early_document['detail'] = (early_failure
                                                or early_original['detail'])
                # CORRECTION 20 (M2): the **full intended** facts of the
                # final verdict are stored **before** the terminal write is
                # attempted and they are the facts that the outer
                # recovery reuses.
                r10_raw['r10-early-salvage'] = dict(early_document)
                early_write_failure = None
                try:
                    write_phase('r10-early-salvage', early_document)
                except BaseException as write_error:  # noqa: BLE001
                    early_cleanup_errors.append(
                        {'kind': 'EVIDENCE',
                         'type': type(write_error).__name__,
                         'detail': str(write_error)})
                    _note_interruption(early_interrupts, write_error)
                    # CORRECTION 20 (M2): the evidence of the final
                    # verdict **failed closed**: the diagnostic of the
                    # failure of the write is retained next to the
                    # original failure and the store keeps it.
                    early_write_failure = (
                        'the evidence of the final verdict of the earlier '
                        'work could not be written: %s' % (write_error,))
                    r10_raw['r10-early-salvage'] = dict(
                        early_document,
                        status='FAIL',
                        evidence_write_errors=list(early_cleanup_errors),
                        detail=_join_details(early_document.get('detail'),
                                             early_write_failure))
                else:
                    r10_inventory.add('r10-early-salvage')
                    # CORRECTION 19 (M2): the terminal state of the ledger
                    # follows the **successful** terminal write.
                    if early_failure is None:
                        ledger.pass_('r10-early-salvage')
                    else:
                        ledger.fail('r10-early-salvage', 'EarlyCleanup')
                # CORRECTION 19 (M3): the priority of the failures is
                # fixed: the failure that is already unwinding wins, then
                # the **exact** interruption of the cleanup and only then
                # the ordinary assertion of the cleanup.
                if early_interrupts and sys.exc_info()[0] is None:
                    raise early_interrupts[0]
                if early_write_failure is not None \
                        and sys.exc_info()[0] is None:
                    # CORRECTION 20 (M2): the evidence of the final
                    # verdict is **closed** after the cleanup: the failure
                    # of the write is a real failure of the group and it
                    # is never reduced to a late incomplete ledger.
                    raise AssertionError(early_write_failure)
                if early_failure is not None and sys.exc_info()[0] is None:
                    raise AssertionError(early_failure)
        finally:
            early_observer.disarm()
            early_observer_patch.stop()

        # -- the coordination of the cancellation (N1 correction 11, M09):
        #    the outcome of the **same** generation is inspected **again**
        #    after the coordination of the cancellation.  The original error
        #    object of the generation remains the error that leaves and the
        #    failure of the coordination is a **parallel** fact: it never
        #    replaces the published failure and it never hides it.
        gate = threading.Event()
        entered = threading.Event()

        class CoordinationApi:
            """The primitives of a read whose fault is published late."""

            def duplicate_current_thread_handle(self):
                return 705

            def cancel_synchronous_io(self, handle):
                # The request of the cancellation releases the fault of the
                # round: the original error of the generation is really
                # published **while** the coordination of the cancellation
                # runs.
                gate.set()
                return 'NOT_FOUND'

            def close_handle(self, handle):
                return None

            def read_stream(self, handle, size):
                entered.set()
                gate.wait(5.0)
                raise RuntimeError('read_fault')

        # CORRECTION 18 (M2): the attempt of the coordination is marked
        # **before** the endpoint is created, before the reader is started
        # and before the first assertion of the coordination: an
        # operation that really ran is never inventoried as ``NOT_RUN``.
        ledger.attempt('r10-coordination')
        # CORRECTION 18 (M3): the coordination round has its **own**
        # observer and its **own** registry: the reader that it starts is
        # an owner of that round and it is joined with a bounded wait.
        coord_registry = _OwnerRegistry()
        coord_observer = _StartObserver(coord_registry)
        coord_observer_patch = coord_observer.install()
        coord_observer_patch.start()
        coord_observer.arm()
        endpoint = None
        reader = None
        coord_cleanup_errors = []
        coord_interrupts = []
        coord_original = {'type': None, 'detail': None}
        coord_passed = False
        try:
            # CORRECTION 19 (M3): the **cleanup owning** try starts
            # **before** the endpoint is constructed and **before** the
            # reader is started.  A start that took effect and that then
            # raised still obtains the release of the gates, the close of
            # the endpoint, the join of the observed threads and the
            # proof of the round: a comment is not a boundary.
            try:
                endpoint = _WindowsPipeEndpoint(
                    file_object=_FakeFile('coordination'),
                    name='coordination',
                    api=CoordinationApi(),
                    clock=time.monotonic, handle=706)
                cancel = _ChannelCancel()
                holder = {}

                def run_read():
                    try:
                        endpoint.read(None, cancel)
                    except BaseException as error:  # noqa: BLE001
                        holder['error'] = error

                reader = threading.Thread(target=run_read)
                reader.start()
                assert entered.wait(5.0), \
                    'the read never entered the operation'
                # The cancellation of the round is published while the read is
                # really inside its operation.
                cancel.set()
                reader.join(10.0)
                assert not reader.is_alive(), \
                    'the read of the round was left behind'
                error = holder.get('error')
                assert isinstance(error, RuntimeError), \
                    'the original error object of the generation was replaced'
                assert str(error) == 'read_fault'
                outcome = endpoint._reader.outcome(
                    endpoint._reader._submitted)
                assert outcome is not None, \
                    'the outcome of the generation is gone'
                assert outcome['error'] == 'RuntimeError'
                assert isinstance(outcome['error_object'], RuntimeError)
                r10_raw['r10-coordination'] = {
                    'error': type(error).__name__,
                    'detail': str(error),
                    'outcome': outcome['error'],
                    'parallel': getattr(
                        error, 'lvw_parallel_cancellation', None) is not None}
                write_phase('r10-coordination',
                            dict(r10_raw['r10-coordination'],
                                 status='EXECUTED'))
                r10_inventory.add('r10-coordination')
                coord_passed = True
            except BaseException as error:  # noqa: BLE001 - it stays visible
                coord_original['type'] = type(error).__name__
                coord_original['detail'] = str(error)
                raise
            finally:
                # CORRECTION 18 (M3): every step of the cleanup is
                # guarded: one exception never skips the close of the
                # endpoint and it never skips the owners of the round.
                #
                # CORRECTION 19 (M3): the **exact** object of a
                # cancellation of the cleanup is retained and it is
                # re-raised by the owner of the coordination.
                # CORRECTION 20 (M3): the **initial** release of the gate
                # of the coordination is guarded **on its own**: a
                # cancellation of it never skips the join of the reader,
                # the close of the endpoint, the drain, the proof and the
                # evidence that follow it and it never replaces the
                # failure that is already unwinding.
                _release_gate(gate.set, coord_cleanup_errors, coord_interrupts)
                if reader is not None:
                    try:
                        reader.join(10.0)
                    except BaseException as error:  # noqa: BLE001
                        coord_cleanup_errors.append(
                            {'kind': 'READER_JOIN',
                             'type': type(error).__name__,
                             'detail': str(error)})
                        _note_interruption(coord_interrupts, error)
                if endpoint is not None:
                    try:
                        endpoint.close()
                    except BaseException as error:  # noqa: BLE001
                        coord_cleanup_errors.append(
                            {'kind': 'ENDPOINT_CLOSE',
                             'type': type(error).__name__,
                             'detail': str(error)})
                        _note_interruption(coord_interrupts, error)
                coord_drain = {'salvage': [], 'attempts': [], 'proof': None,
                               'quiescent': False, 'errors': [],
                               'all_salvage': [], 'owner_errors': []}
                try:
                    coord_drain = _drain_owners(
                        coord_registry, prefix='r10-coordination',
                        interrupts=coord_interrupts)
                except BaseException as error:  # noqa: BLE001
                    coord_cleanup_errors.append(
                        {'kind': 'DRAIN',
                         'type': type(error).__name__,
                         'detail': str(error)})
                    _note_interruption(coord_interrupts, error)
                # CORRECTION 19 (M2): the **final** result of the
                # coordination is computed **after** the cleanup and it
                # is written **before** the terminal state of the ledger
                # is advanced.  There is no terminal PASS **before** the
                # cleanup.
                coord_failure = None
                if coord_drain['proof'] is not None:
                    coord_failure = coord_drain['proof']
                elif coord_drain['quiescent'] is not True:
                    coord_failure = ('the owners of the coordination of the '
                                     'round were not quiescent')
                elif coord_cleanup_errors:
                    coord_failure = ('the cleanup of the coordination of the '
                                     'round met %s'
                                     % (coord_cleanup_errors,))
                # the diagnostics of the cleanup are **durable** and they
                # stay in the raw facts of the coordination: a retry of
                # the outer inventory carries them too.
                r10_raw.setdefault('r10-coordination', {})
                r10_raw['r10-coordination']['cleanup_errors'] = \
                    list(coord_cleanup_errors)
                r10_raw['r10-coordination']['quiescent'] = \
                    coord_drain['quiescent']
                r10_raw['r10-coordination']['proof_failure'] = \
                    coord_drain['proof']
                # CORRECTION 20 (M2): the evidence of the coordination has
                # its **own** name: the **original launch document** of
                # the group keeps its own binding and it reaches every
                # real schedule unchanged.  The coordination never
                # replaces the plan of the round with its own evidence.
                coord_document = dict(r10_raw['r10-coordination'],
                                      original_failure=dict(coord_original),
                                      interrupts=_interruption_facts(
                                          coord_interrupts),
                                      drain=coord_drain['attempts'],
                                      **_drain_facts(coord_drain))
                if coord_failure is None and coord_passed \
                        and coord_original['type'] is None:
                    coord_document['status'] = 'PASSED'
                else:
                    coord_document['status'] = 'FAIL'
                    coord_document['executed'] = True
                    coord_document['reason'] = (coord_original['type']
                                                or 'CoordinationCleanup')
                    coord_document['detail'] = (coord_failure
                                                or coord_original['detail'])
                # CORRECTION 20 (M2): the **full intended** facts of the
                # coordination are stored **before** the terminal write is
                # attempted.
                r10_raw['r10-coordination'] = dict(coord_document)
                coord_write_failure = None
                try:
                    write_phase('r10-coordination', coord_document)
                except BaseException as write_error:  # noqa: BLE001
                    coord_cleanup_errors.append(
                        {'kind': 'EVIDENCE',
                         'type': type(write_error).__name__,
                         'detail': str(write_error)})
                    _note_interruption(coord_interrupts, write_error)
                    # CORRECTION 20 (M2): the evidence of the coordination
                    # **failed closed** and the store keeps the
                    # diagnostic of the failure of the write next to the
                    # original failure.
                    coord_write_failure = (
                        'the evidence of the coordination could not be '
                        'written: %s' % (write_error,))
                    r10_raw['r10-coordination'] = dict(
                        coord_document,
                        status='FAIL',
                        evidence_write_errors=list(coord_cleanup_errors),
                        detail=_join_details(coord_document.get('detail'),
                                             coord_write_failure))
                else:
                    r10_inventory.add('r10-coordination')
                    # CORRECTION 19 (M2): the terminal state of the ledger
                    # follows the **successful** terminal write.
                    if coord_document['status'] == 'PASSED':
                        ledger.pass_('r10-coordination')
                    else:
                        ledger.fail('r10-coordination', coord_document['reason'])
                # CORRECTION 19 (M3): the priority of the failures is
                # fixed: the failure that is already unwinding wins, then
                # the **exact** interruption of the cleanup and only then
                # the ordinary assertion of the cleanup.
                if coord_interrupts and sys.exc_info()[0] is None:
                    raise coord_interrupts[0]
                if coord_write_failure is not None \
                        and sys.exc_info()[0] is None:
                    # CORRECTION 20 (M2): the evidence of the coordination
                    # is **closed** after the cleanup: the failure of the
                    # write is a real failure of the group and it is never
                    # reduced to a late incomplete ledger.
                    raise AssertionError(coord_write_failure)
                if coord_failure is not None and sys.exc_info()[0] is None:
                    raise AssertionError(coord_failure)
        finally:
            coord_observer.disarm()
            coord_observer_patch.stop()

        # -- THE DYNAMIC SCHEDULE OF THE M09 OBLIGATION (N1 correction 12):
        #    a real ordinary fault is published for the current generation
        #    of the real chain, the effective timeout of the round arrives
        #    **before** the endpoint consumes the outcome and the original
        #    error object survives both a **confirmed** and a **failed**
        #    coordination of the round.
        #
        #    N1 correction 16 (M2): the **outer** inventory of the phases of
        #    this group.  Every main schedule and both negative barrier
        #    subcases are named **before** they run and every document that
        #    a schedule really wrote is marked in the inventory.  A schedule
        #    that was never reached is ``NOT_RUN`` and it is never
        #    ambiguous: the failure of an earlier schedule may never leave
        #    the evidence of a later one undefined.
        #
        #    N1 correction 17 (M2): every schedule of this group writes its
        #    documents through the ledger of the group: a schedule that was
        #    executed and that failed is a ``FAIL`` and the schedules that
        #    were never entered are ``NOT_RUN``.
        _m09_timeout_phase(document, plan, tmp_path,
                            phase='r10-timeout-confirmed',
                            confirm_the_worker=True, hold_the_worker=False,
                            expect_barrier='NOT_APPLICABLE',
                            inventory=r10_inventory, ledger=ledger,
                            store=r10_raw)
        _m09_timeout_phase(document, plan, tmp_path,
                            phase='r10-timeout-failed',
                            confirm_the_worker=False, hold_the_worker=True,
                            expect_barrier='PASSED',
                            inventory=r10_inventory, ledger=ledger,
                            store=r10_raw)
        # -- N1 correction 15 (M2): the barrier of the publication is
        #    **checked** and it **fails closed**.  The two negative
        #    subcases below drive the **same** failed coordination of the
        #    round with a bounded transparent seam that forces an
        #    **absent** outcome and an outcome of **another generation**.
        #    The premise of the test is then **refused** explicitly and
        #    the subcase is never counted as a successful failed
        #    coordination: the cancel primitive of the round never
        #    returns ``REQUESTED`` as if the barrier had passed.
        _m09_timeout_phase(document, plan, tmp_path,
                            phase='r10-barrier-absent',
                            confirm_the_worker=False, hold_the_worker=True,
                            barrier_probe='ABSENT', expect_barrier='REFUSED',
                            inventory=r10_inventory, ledger=ledger,
                            store=r10_raw)
        _m09_timeout_phase(document, plan, tmp_path,
                            phase='r10-barrier-wrong-generation',
                            confirm_the_worker=False, hold_the_worker=True,
                            barrier_probe='WRONG_GENERATION',
                            expect_barrier='REFUSED',
                            inventory=r10_inventory, ledger=ledger,
                            store=r10_raw)

        # -- THE REQUIRED ORDER (N1 correction 12, root preflight
        #    PF12-01): the ordinary failure of the read is published
        #    **before** the effective timeout of the round arrives and
        #    the endpoint consumes the outcome of its own generation
        #    only **after** the timeout was decided.  The gate is a
        #    transparent wrapper of the production wait of the worker:
        #    it calls the original wait and it holds the endpoint
        #    between that wait and the recheck of its generation.
        _m09_published_fault_phase(document, plan, tmp_path,
                                   phase='r10-published-before-timeout',
                                   inventory=r10_inventory, ledger=ledger,
                                   store=r10_raw)
    except BaseException as error:
        # CORRECTION 17 (M2): a document of a schedule that was entered
        # and that failed is a ``FAIL`` with the facts that it really
        # observed; the schedules that were never entered are ``NOT_RUN``
        # and they carry no fact.
        #
        # CORRECTION 18 (M2): the writing of the evidence **never**
        # replaces the original failure: the error of the write is
        # retained and the original failure is the one that leaves.
        #
        # CORRECTION 19 (M2): the recovery of the terminal documents that
        # a failed write left ATTEMPTED is **bounded and best effort**:
        # one attempt per name, no retry, no success on a missing
        # evidence and the terminal state of the ledger follows the
        # **successful** terminal write.
        first_failure['type'] = type(error).__name__
        first_failure['detail'] = str(error)
        for r10_name in r10_documents:
            if ledger.state(r10_name) != 'ATTEMPTED':
                continue
            # CORRECTION 20 (M2): the recovery reuses the **shared fact
            # store** of the group: the retry carries the **full facts**
            # that the phase really observed - the barrier identity, the
            # persistence of the barrier, the error of its persistence,
            # the original failure, every diagnostic of the cleanup, the
            # quiescence and the attempts of the drain - and it is never
            # a generic ``FAIL`` over an empty document.
            recovered = dict(r10_raw.get(r10_name, {}))
            recovered['status'] = 'FAIL'
            recovered['executed'] = True
            recovered['reason'] = type(error).__name__
            recovered['detail'] = _join_details(recovered.get('detail'),
                                                str(error))
            recovered['recovered_from'] = 'ATTEMPTED'
            try:
                write_phase(r10_name, recovered)
            except BaseException as write_error:  # noqa: BLE001
                first_failure.setdefault('write_errors', []).append(
                    {'name': r10_name,
                     'type': type(write_error).__name__,
                     'detail': str(write_error)})
                _note_interruption(outer_interrupts, write_error)
                continue
            r10_inventory.add(r10_name)
            ledger.fail(r10_name, type(error).__name__)
        raise
    finally:
        # The schedules that were **not** reached are ``NOT_RUN``: they
        # carry no fact of a schedule that was not established and they
        # are never ambiguous.  A document that a schedule really wrote
        # is never overwritten here.
        #
        # CORRECTION 18 (M2): a write that fails here never replaces the
        # original failure of the group: it is retained and it is
        # reported in the reason of the group.
        #
        # CORRECTION 19 (M2): a name is finalised as ``NOT_RUN`` **only
        # after** its durable write succeeded and the terminal state of
        # the ledger follows that write: a failed write leaves the name
        # PLANNED and it is reported as a persistence diagnostic.
        # the state of the unwinding is read **before** the writes: inside
        # the handler of a write the state of the frame is the write
        # error itself and the original failure would never be seen.
        outer_unwinding = sys.exc_info()[0] is not None
        for r10_name in r10_documents:
            if ledger.state(r10_name) != 'PLANNED':
                continue
            try:
                write_phase(r10_name, {'status': 'NOT_RUN',
                                       'reason': first_failure['type']})
            except BaseException as write_error:  # noqa: BLE001
                first_failure.setdefault('write_errors', []).append(
                    {'name': r10_name,
                     'type': type(write_error).__name__,
                     'detail': str(write_error)})
                _note_interruption(outer_interrupts, write_error)
                # CORRECTION 20 (M3): an **exact** cancellation of the
                # write of the inventory is **never** raised in the middle
                # of the inventory: it is retained and it is re-raised
                # **after** the durable summary of the group, as the
                # **first** exact pending interruption of the group.
                continue
            r10_inventory.add(r10_name)
            ledger.finish(r10_name, 'NOT_RUN', first_failure['type'])
        # CORRECTION 20 (M2): the **final accounting** of the group is
        # **durable**.  It is written **once** and **after** every action
        # of the inventory: it carries the intended state of every name,
        # the names that were not persisted, the full facts of every
        # document, the original failure of the group and **every**
        # additional error of a write.  The summary never replaces the
        # original failure and the group never claims that the failure
        # log is durable when its own write failed.
        summary_states = {name: ledger.state(name) for name in r10_documents}
        summary_incomplete = [name for name in r10_documents
                              if summary_states[name]
                              not in ('PASSED', 'FAIL', 'NOT_RUN')
                              or name not in r10_inventory]
        summary = {
            'status': ('FAIL' if (first_failure['type']
                                  or first_failure.get('write_errors')
                                  or summary_incomplete)
                       else 'PASSED'),
            'original_failure': dict(first_failure),
            'write_errors': list(first_failure.get('write_errors', [])),
            'states': summary_states,
            'written': sorted(r10_inventory),
            'not_persisted': [item['name']
                              for item in first_failure.get('write_errors', [])
                              if item.get('name') in r10_documents],
            'incomplete': summary_incomplete,
            'facts': {name: r10_raw.get(name, {}) for name in r10_documents},
            'interrupts': _interruption_facts(outer_interrupts),
            'inventory_size': len(r10_documents),
            'unwinding': bool(outer_unwinding),
        }
        try:
            write_phase('r10-final-summary', summary)
        except BaseException as write_error:  # noqa: BLE001
            first_failure.setdefault('write_errors', []).append(
                {'name': 'r10-final-summary',
                 'type': type(write_error).__name__,
                 'detail': str(write_error)})
            _note_interruption(outer_interrupts, write_error)
    # CORRECTION 19 (M3): the **exact** object of a cancellation that the
    # inventory of the group met is re-raised by the owner of the group:
    # the priority is the failure that is already unwinding, then the
    # exact interruption and only then the ordinary assertion.
    if outer_interrupts:
        raise outer_interrupts[0]
    # CORRECTION 19 (M2): the terminal accounting of the group is
    # **complete** and it is checked **only** when the group really
    # passed: every name of the inventory has a terminal state of the
    # ledger and a document that was really written, and a passing test
    # carries **no** persistence diagnostic at all.
    assert first_failure['type'] is None, \
        'the group of the M09 obligation failed: %s' % (first_failure,)
    assert not first_failure.get('write_errors'), \
        'the evidence of the group carried a persistence diagnostic: %s' \
        % (first_failure.get('write_errors'),)
    for r10_name in r10_documents:
        assert ledger.state(r10_name) in ('PASSED', 'FAIL', 'NOT_RUN'), \
            'the terminal state of %s is %s' \
            % (r10_name, ledger.state(r10_name))
        assert r10_name in r10_inventory, \
            'the document of %s was never written' % (r10_name,)

# -- N10-R11: the overflow of the channel is a named failure -------------

def test_n10_r11_the_overflow_of_the_channel_is_a_named_failure(tmp_path):
    """N10-R11 (M09): the overflow of the channel is named where it is.

    Obligation: a complete frame with a newline that is too long and a
    frame that is one byte beyond the limit are recorded at the place
    where they really happen, as a **named** sticky error of the
    channel with the original facts of the overflow.  A close that
    happens before the read consumes the frame carries that error: the
    channel that overflowed is never a channel that ended normally and
    the broker is never released as if there were no error.  The limits
    of the package do not move: the exact frame fits and the frame that
    is one byte longer does not.

    Entry: ``StreamChannel._drain``, ``StreamChannel._record_overflow``,
    ``StreamChannel.close``, ``BrokerProcess._close_channel`` and
    ``NativeCustodySession.stop``.  Trigger: the channel of the round
    reads a frame that does not fit and the round is stopped twice.
    Oracle: the error of the reader is the named overflow, the facts of
    the overflow travel with the close and the broker is kept.  Negative:
    the exact frame still fits and the one byte beyond the limit does
    not.  Returned state: the facts of the two stops name the overflow.
    Salvage: the owner of the test stops the round in every case.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    limit = 32 * 1024
    # The exact frame and the frame that is one byte longer are strictly
    # adjacent and the limit of the package does not move.
    exact = b'y' * (limit - 1) + b'\n'
    one_over = b'x' * limit + b'\n'
    assert len(exact) == limit
    assert len(one_over) == limit + 1

    # CORRECTION 22 (M3): the errors of the cleanup of this round are
    # **retained**: a failure of the stop of the round is never silently
    # passed and it never replaces the failure that is already
    # unwinding.
    r11_cleanup_errors = []
    r11_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this round exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the round without a
    # durable document.
    r11_cleanup_facts = _cleanup_facts('r11')
    api = _F5Api()
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    try:
        r11_cleanup_facts['executed'] = True
        session.start()
        # The owner of the test publishes the frame that does not fit
        # into the channel of the round: the frame is a **complete**
        # frame with a newline that is one byte beyond the limit.
        assert api.read_waiting.wait(15.0), \
            'the reader of the chain was never inside its read'
        api.publish_outcome('FRAME', one_over)
        # The channel of the round reads the frame that does not fit.
        deadline = time.monotonic() + 15.0
        while holder['channel']._error is None and time.monotonic() < deadline:
            time.sleep(0.02)
        channel = holder['channel']
        facts = {'error': channel._error, 'overflow': channel.overflow,
                 'overflow_facts': channel._overflow_facts}
        write_phase('r11-oversize', facts)
        assert channel.overflow is True
        assert channel._error == 'BROKER_CHANNEL_OVERFLOW', \
            'the overflow was not recorded as a named failure'
        assert channel._overflow_facts.get('reason') == 'FRAME_TOO_LARGE'
        # The two real stops of the round carry the named error.
        first = session.stop()
        first_facts = first['broker_close_facts'] or {}
        write_phase('r11-first', {'reader_error':
                                  first_facts.get('channel_reader_error'),
                                  'overflow': first_facts.get('channel_overflow'),
                                  'state': first['state']})
        assert first_facts.get('channel_reader_error') \
            == 'BROKER_CHANNEL_OVERFLOW', \
            'the close of the round lost the overflow'
        assert first_facts.get('channel_overflow') is True
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
        second = session.stop()
        second_facts = second['broker_close_facts'] or {}
        write_phase('r11-second', {'reader_error':
                                    second_facts.get('channel_reader_error'),
                                    'source':
                                    second_facts.get('channel_reader_error_source'),
                                    'state': second['state']})
        assert second_facts.get('channel_reader_error') \
            == 'BROKER_CHANNEL_OVERFLOW', \
            'the second attempt lost the overflow'
        assert second['broker_retained'] is True
        assert second['state'] == 'UNKNOWN_RETAINED'
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        r11_cleanup_facts['original'] = _original_facts()
        # CORRECTION 22 (M3): the **stop** of the round is guarded and it
        # is never silently passed: its failure is retained with its
        # exact type and its exact detail and the priority of the
        # failures of the cleanup is enforced **after** it.
        try:
            session.stop()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            r11_cleanup_errors.append(
                {'kind': 'STOP', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(r11_interrupts, error)
        r11_cleanup_facts['actions'].append('stop:round')
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures.
        _publish_cleanup(
            r11_cleanup_facts,
            lambda: write_phase('r11-round-cleanup', r11_cleanup_facts),
            r11_cleanup_errors, r11_interrupts,
            verdict=lambda: _cleanup_verdict(
                r11_cleanup_errors, None,
                'the cleanup of the round of R11 met'))
        _raise_first_interruption(r11_interrupts)
        if r11_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the round of R11 met %s'
                                 % (r11_cleanup_errors,))

    # The exact frame still fits: the limits of the package did not move.
    # CORRECTION 22 (M3): the errors of the closes of the channels of
    # this round are **retained**: a close that failed never replaces the
    # failure that is already unwinding.
    blocks = [exact]
    channel = StreamChannel(None, None, read_endpoint=_BlockReader(blocks),
                            write_endpoint=_BlockWriter(), clock=time.monotonic)
    try:
        deadline = time.monotonic() + 15.0
        while channel._count == 0 and time.monotonic() < deadline:
            time.sleep(0.02)
        write_phase('r11-exact', {'count': channel._count,
                                  'overflow': channel.overflow,
                                  'error': channel._error})
        assert channel._count == 1, \
            'the exact frame did not fit into the channel'
        assert channel.overflow is False
        assert channel._error is None
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        r11_cleanup_facts['original'] = _original_facts()
        # CORRECTION 22 (M3): the close of the channel is **guarded**: it
        # never replaces the failure that is already unwinding and it
        # never replaces the **first** exact pending interruption of the
        # cleanup.
        try:
            channel.close()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            r11_cleanup_errors.append(
                {'kind': 'CLOSE', 'owner': 'r11:exact',
                 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(r11_interrupts, error)
        r11_cleanup_facts['actions'].append('close:r11:exact')
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures.
        _publish_cleanup(
            r11_cleanup_facts,
            lambda: write_phase('r11-exact-cleanup', r11_cleanup_facts),
            r11_cleanup_errors, r11_interrupts,
            verdict=lambda: _cleanup_verdict(
                r11_cleanup_errors, None,
                'the cleanup of the round of R11 met'))

    # The frame count of the channel: the frame that is one beyond the
    # number of the frames of the package is refused with the same named
    # error.  The parent of the round may never deliver that many
    # frames - its own budget is smaller - and the channel alone is the
    # owner that may prove it.
    blocks = [b'z\n'] * 1025
    channel = StreamChannel(None, None, read_endpoint=_BlockReader(blocks),
                            write_endpoint=_BlockWriter(), clock=time.monotonic)
    try:
        deadline = time.monotonic() + 15.0
        while channel._error is None and time.monotonic() < deadline:
            time.sleep(0.02)
        write_phase('r11-frames', {'error': channel._error,
                                   'overflow': channel.overflow,
                                   'overflow_facts': channel._overflow_facts,
                                   'frames': channel.frames})
        assert channel.overflow is True
        assert channel._error == 'BROKER_CHANNEL_OVERFLOW'
        assert channel._overflow_facts.get('reason') == 'TOO_MANY_FRAMES'
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        r11_cleanup_facts['original'] = _original_facts()
        # CORRECTION 22 (M3): the close of the channel is **guarded** and
        # the priority of the failures of the cleanup is enforced
        # **after** it: the failure that is already unwinding wins, then
        # the **first** exact pending interruption and only then the
        # ordinary error of the cleanup.
        try:
            channel.close()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            r11_cleanup_errors.append(
                {'kind': 'CLOSE', 'owner': 'r11:frames',
                 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(r11_interrupts, error)
        r11_cleanup_facts['actions'].append('close:r11:frames')
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures.
        _publish_cleanup(
            r11_cleanup_facts,
            lambda: write_phase('r11-frames-cleanup', r11_cleanup_facts),
            r11_cleanup_errors, r11_interrupts,
            verdict=lambda: _cleanup_verdict(
                r11_cleanup_errors, None,
                'the cleanup of the round of R11 met'))
        _raise_first_interruption(r11_interrupts)
        if r11_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the channels met %s'
                                 % (r11_cleanup_errors,))


class _BlockReader:
    """A read end of the channel that returns the blocks it was given."""

    def __init__(self, blocks):
        self.blocks = list(blocks)

    def read(self, deadline=None, cancel=None):
        if self.blocks:
            return self.blocks.pop(0)
        return b''

    def close(self):
        return {'closed': True, 'retained_workers': 0,
                'worker_thread_handle_released': True}


class _BlockWriter:
    """A write end of the channel that counts its own closes."""

    def __init__(self):
        self.closes = 0

    def write(self, raw, deadline=None, cancel=None):
        return len(raw)

    def close(self):
        self.closes += 1
        return {'closed': True, 'retained_workers': 0,
                'worker_thread_handle_released': True}


# -- N10-R12: the causal order of the reader ------------------------------

def test_n10_r12_the_reader_publishes_its_wait_before_it_waits(tmp_path):
    """N10-R12 (test causality): the reader publishes its real state.

    Obligation: the reader of the chain publishes the event that it is
    really inside its read **before** it waits, so that the owner of
    the test never waits for an event that the reader publishes only
    after a timeout.  The external owner waits for that event, it sets
    the **same** cancel flag of the **same** channel without naming an
    owner and it publishes an explicit confirmation; the public stop of
    the round is driven only after that confirmation.  The code of the
    cancellation is the one that the **real** observation layer raised
    - the read endpoint of the channel or the wait of the channel
    between two reads - and the origin of the cancellation stays
    unknown: the close of the channel may never be taken for the owner
    of this cancellation.

    Entry: ``_F5Api.read_stream`` and
    ``_F5ExternalCancelOwner.run``.  Trigger: the round is started and
    the reader of the chain enters its read.  Oracle: the event of the
    reader was published before the owner set the flag, the origin of
    the cancellation is really unknown and the reader of the chain
    keeps the error of the cancellation of the other owner.  Negative:
    the owner never sets the flag before the reader is really inside
    its read.  Returned state: the confirmation of the owner is
    published and the facts of the close name the error of the reader.
    Salvage: the exact thread of the owner is joined by the owner of
    the test, in every case and with a bounded wait.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    api = _F5Api()
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    owner = _F5ExternalCancelOwner(api, holder)
    thread = threading.Thread(target=owner.run, name='lvw-n10-r12-owner')
    thread.start()
    # CORRECTION 23 (M3): the facts of the cleanup of this round exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the round without a
    # durable document.
    r12_facts = _cleanup_facts('r12-stop')
    r12_cleanup_errors = []
    r12_interrupts = []
    try:
        r12_facts['executed'] = True
        session.start()
        # The confirmation of the external owner is published in every
        # case and the failure of the owner is the failure of the test.
        assert owner.published.wait(30.0), \
            'the external owner never confirmed its cancellation'
        if owner.error is not None:
            raise owner.error
        channel = holder['channel']
        facts = {'read_waiting': bool(api.read_waiting.is_set()),
                 'flag_set': owner.flag_set,
                 'flag_owner': owner.flag_owner,
                 'frames': len(api.frames)}
        write_phase('r12-owner', facts)
        # The reader of the chain published its wait before it waited.
        assert api.read_waiting.is_set()
        # The flag of the cancel is really set and its origin is really
        # unknown: the close of the channel may never be taken for the
        # owner of this cancellation.
        assert owner.flag_set is True
        assert channel._cancel.is_set()
        assert channel._cancel.owner() is None
        assert owner.flag_owner is None
        # The public stop of the round is driven only after the
        # confirmation of the owner.
        first = session.stop()
        close_facts = first['broker_close_facts'] or {}
        r12_facts.update({'state': first['state'],
                          'reader_error':
                          close_facts.get('channel_reader_error'),
                          'retained': first['broker_retained']})
        write_phase('r12-stop', r12_facts)
        # The code of the cancellation is the one that the real
        # observation layer raised and it is one of the two codes that
        # the production names for the cancellation of the channel.
        assert close_facts.get('channel_reader_error') in CANCELLATION_CODES, \
            'the cancellation of the other owner was not classified'
        # It is **not** the cancellation of the close of the channel.
        assert close_facts.get('close_cancellation') is None, \
            'the cancellation of another owner was taken for the close'
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
    finally:
        # The exact thread of the owner of the test is joined in every
        # case and with a bounded wait.
        #
        # CORRECTION 21 (M3): the join is **guarded**: a failure of it
        # never skips the stop of the round that follows it and it never
        # replaces the failure that is already unwinding.
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        r12_facts['original'] = _original_facts()
        r12_join = _join_owner('owner-of-the-round', thread,
                               r12_cleanup_errors, r12_interrupts,
                               seconds=30.0)
        # CORRECTION 22 (M3): the **stop** of the round is a cleanup
        # action of its own: it is attempted **before** the priority of
        # the failures, a failure of it is retained with its exact type
        # and its exact detail and it is never silently swallowed.
        r12_stop = None
        try:
            r12_stop = session.stop()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            r12_cleanup_errors.append(
                {'kind': 'STOP', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(r12_interrupts, error)
        r12_facts['actions'].extend(['join:owner-of-the-round',
                                     'stop:round'])
        # CORRECTION 22 (M3): the facts of the cleanup are **complete**
        # and they are **durable** before the priority is applied.
        # CORRECTION 23 (M3): the publication is **unconditional** - it
        # never waits for the happy facts of the body - and the verdict of
        # the cleanup is recomputed **before** every attempt to write and
        # **before** the retry of a failed write.
        r12_facts['owner_alive'] = _owner_alive(r12_join)
        r12_facts['alive'] = r12_facts['owner_alive']
        r12_facts['cleanup_stop_state'] = (
            r12_stop.get('state') if isinstance(r12_stop, dict) else None)
        _publish_cleanup(
            r12_facts, lambda: write_phase('r12-stop', r12_facts),
            r12_cleanup_errors, r12_interrupts,
            verdict=lambda: _cleanup_verdict(
                r12_cleanup_errors, None,
                'the cleanup of the round of R12 met'))
        # the **exact** cancellation wins over the ordinary assertion of
        # the join that follows it - and it wins **after** every action
        # of the cleanup was attempted.
        _raise_first_interruption(r12_interrupts)
        # the ordinary proof of the round: it runs **after** every action
        # of the cleanup and it never replaces the failure that is
        # already unwinding.
        if sys.exc_info()[0] is None:
            assert not _owner_alive(r12_join), \
                'the owner of the round was left behind'
        # the ordinary errors of the cleanup are **consumed**: they fail
        # the round instead of being recorded and forgotten.
        if r12_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the round of R12 met %s'
                                 % (r12_cleanup_errors,))


# -- N10-R13: the fault is unlocked by the owner of the test ---------------

def test_n10_r13_the_fault_is_unlocked_by_the_owner_and_observed_first(tmp_path):
    """N10-R13 (M09): the fault of the read is observed before the stop.

    Obligation: the ordinary failure of the read, the frame that never
    ends and the end of the stream are published by the **owner of the
    test** and they are never unlocked by the write of the stop: the
    owner waits for the real outcome - the error, the frame or the end
    of the stream - and it observes it **before** it drives the public
    stop of the round.  Every phase of the round writes its bounded
    document and every value of it is a value that the production
    returned.

    Entry: ``_F5Api.publish_read_fault``,
    ``_F5Api.publish_partial_frame`` and
    ``NativeCustodySession.stop``.  Trigger: the ordinary failure of
    the read of the chain, the frame that never ends and the end of the
    stream.  Oracle: the failure was really published before the stop,
    the error of the reader is the error of the round and the partial
    frame keeps its own name.  Negative: the write of the stop never
    unlocks a failure that should have happened first.  Returned state:
    the phase documents are on the disk.  Salvage: the owner of the test
    stops the round in every case.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())

    # CORRECTION 22 (M3): the errors of the cleanup of the phases of
    # this round are **retained**: a failure of the stop of the round is
    # never silently passed and it never replaces the failure that is
    # already unwinding.
    r13_cleanup_errors = []
    r13_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this round exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the round without a
    # durable document.
    r13_cleanup_facts = _cleanup_facts('r13')
    # -- PHASE ONE: the ordinary failure of the read --------------------
    api = _F5Api(read_fault=RuntimeError('read_fault'))
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    try:
        r13_cleanup_facts['executed'] = True
        session.start()
        assert api.read_waiting.wait(15.0), \
            'the reader of the chain was never inside its read'
        api.publish_read_fault()
        assert api.fault_observed.wait(15.0), \
            'the ordinary failure of the read never happened'
        reader = holder['read_endpoint']._reader
        assert reader is not None
        assert reader.outcome_published.wait(15.0), \
            'the outcome of the read was never published'
        first = session.stop()
        facts = first['broker_close_facts'] or {}
        write_phase('r13-fault', {'reader_error':
                                   facts.get('channel_reader_error'),
                                   'state': first['state'],
                                   'retained': first['broker_retained']})
        assert facts.get('channel_reader_error') == 'RuntimeError', \
            'the failure of the read was swallowed by the stop'
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        r13_cleanup_facts['original'] = _original_facts()
        # CORRECTION 22 (M3): the **stop** of the round is guarded and it
        # is never silently passed: its failure is retained with its
        # exact type and its exact detail and the priority of the
        # failures of the cleanup is enforced **after** it.
        try:
            session.stop()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            r13_cleanup_errors.append(
                {'kind': 'STOP', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(r13_interrupts, error)
        r13_cleanup_facts['actions'].append('stop:round')
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures.
        _publish_cleanup(
            r13_cleanup_facts,
            lambda: write_phase('r13-fault-cleanup', r13_cleanup_facts),
            r13_cleanup_errors, r13_interrupts,
            verdict=lambda: _cleanup_verdict(
                r13_cleanup_errors, None,
                'the cleanup of the round of R13 met'))
        _raise_first_interruption(r13_interrupts)
        if r13_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the round of R13 met %s'
                                 % (r13_cleanup_errors,))

    # -- PHASE TWO: the frame that never ends and the end of the stream --
    api = _F5Api(partial_frame=b'{"schema": "lvw.s3-native-custody-channel/1"')
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    try:
        session.start()
        assert api.read_waiting.wait(15.0), \
            'the reader of the chain was never inside its read'
        api.publish_partial_frame()
        assert api.eof_observed.wait(15.0), \
            'the end of the stream was never observed'
        channel = holder['channel']
        deadline = time.monotonic() + 15.0
        while channel._error is None and time.monotonic() < deadline:
            time.sleep(0.02)
        first = session.stop()
        facts = first['broker_close_facts'] or {}
        write_phase('r13-partial', {'reader_error':
                                    facts.get('channel_reader_error'),
                                    'state': first['state'],
                                    'retained': first['broker_retained']})
        assert facts.get('channel_reader_error') \
            == 'BROKER_CHANNEL_PARTIAL_FRAME', \
            'the partial frame was dropped as a normal end'
        assert first['broker_retained'] is True
        assert first['state'] == 'UNKNOWN_RETAINED'
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        r13_cleanup_facts['original'] = _original_facts()
        # CORRECTION 22 (M3): the **stop** of the round is guarded and it
        # is never silently passed: its failure is retained with its
        # exact type and its exact detail and the priority of the
        # failures of the cleanup is enforced **after** it.
        try:
            session.stop()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            r13_cleanup_errors.append(
                {'kind': 'STOP', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(r13_interrupts, error)
        r13_cleanup_facts['actions'].append('stop:round')
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures.
        _publish_cleanup(
            r13_cleanup_facts,
            lambda: write_phase('r13-partial-cleanup', r13_cleanup_facts),
            r13_cleanup_errors, r13_interrupts,
            verdict=lambda: _cleanup_verdict(
                r13_cleanup_errors, None,
                'the cleanup of the round of R13 met'))
        _raise_first_interruption(r13_interrupts)
        if r13_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the round of R13 met %s'
                                 % (r13_cleanup_errors,))


# -- N10-R14: the compatibility of the new candidate ----------------------

def test_n10_r14_the_closed_obligations_of_the_package_do_not_regress(tmp_path):
    """N10-R14 (compatibility): the closed obligations stay closed.

    Obligation: the candidate of this correction keeps every closed
    obligation of the package: the unknown state is latched under one
    lock, the budget of the parent and of the child is one budget in
    both directions, the reservation of the terminal exchange is
    consumed by the terminal frame itself, a cancellation of a normal
    close keeps its source and a first error survives a retry.  The
    identity and the order of the 175 frozen nodes are untouched: the
    new groups are **appended** and they never replace an old one.

    Entry: ``NativeCustodySession._latch_unknown_state``,
    ``NativeCustodySession._check_frame_budget``,
    ``NativeCustodySession._send`` and ``_ChannelCancel``.  Trigger: a
    round that is stopped and a round whose reader failed.  Oracle: the
    latches and the budgets keep their facts.  Negative: a later frame
    never borrows the reservation of the terminal one.  Returned state:
    the facts of the round are named.  Salvage: the owner of the test
    stops the round in every case.
    """
    document = _live_plan_document()
    plan = validate_launch_plan(document, now=time.time())
    clock = ManualClock(1000.0)
    # CORRECTION 22 (M3): the errors of the cleanup of this round are
    # **retained**: a failure of the stop of the round is never silently
    # passed and it never replaces the failure that is already
    # unwinding.
    r14_cleanup_errors = []
    r14_interrupts = []
    # CORRECTION 23 (M3): the facts of the cleanup of this round exist
    # **before** its body runs: a body that fails before its own happy
    # facts exist never leaves the cleanup of the round without a
    # durable document.
    r14_cleanup_facts = _cleanup_facts('r14')
    api = _F5Api()
    session, holder, channel_closes, channel_facts = _chain(
        api, document, plan, tmp_path)
    try:
        r14_cleanup_facts['executed'] = True
        session.start()
        # The unknown state is latched under one lock and it is never
        # cleared.  The latch is checked on a **separate** session, so
        # that the round that is stopped below keeps its own state.
        probe = NativeCustodySession(
            plan=document, run_root=tmp_path,
            parent_child_remaining_seconds=60,
            launcher=lambda *args, **kwargs: None, clock=clock,
            wall=time.time, nonce=NONCE)
        assert probe._latch_unknown_state() is True
        assert probe._latch_unknown_state() is False
        assert probe._context.is_unknown() is True
        # The reservation of the terminal exchange is consumed by the
        # terminal frame itself and a normal frame never borrows it.
        session._check_frame_budget(terminal=False)
        session._check_frame_budget(terminal=True)
        # The cancel flag of a normal close keeps its source.
        cancel = _ChannelCancel()
        source = broker_module._CloseSource(1)
        cancel.set(source)
        assert cancel.owner() is source
        assert cancel.owner() is not broker_module._CloseSource(1)
        facts = {'unknown': probe._context.is_unknown(),
                 'frames_sent': session._frames_sent,
                 'frames_received': session._frames_received,
                 'cancel_owner': cancel.owner().owner}
        write_phase('r14-compatibility', facts)
        first = session.stop()
        assert first['state'] in ('UNKNOWN_RETAINED', 'RELEASED')
    finally:
        # CORRECTION 23 (M3): the **exact** original failure that is
        # unwinding is read **before** the first action of the cleanup
        # runs: it is the priority that follows the publication.
        r14_cleanup_facts['original'] = _original_facts()
        # CORRECTION 22 (M3): the **stop** of the round is guarded and it
        # is never silently passed: its failure is retained with its
        # exact type and its exact detail and the priority of the
        # failures of the cleanup is enforced **after** it.
        try:
            session.stop()
        except BaseException as error:  # noqa: BLE001 - it stays visible
            r14_cleanup_errors.append(
                {'kind': 'STOP', 'type': type(error).__name__,
                 'detail': str(error)})
            _note_interruption(r14_interrupts, error)
        r14_cleanup_facts['actions'].append('stop:round')
        # CORRECTION 23 (M3): the publication of the cleanup is
        # **unconditional** and it happens **after** every action of the
        # cleanup and **before** the priority of the failures.
        _publish_cleanup(
            r14_cleanup_facts,
            lambda: write_phase('r14-cleanup', r14_cleanup_facts),
            r14_cleanup_errors, r14_interrupts,
            verdict=lambda: _cleanup_verdict(
                r14_cleanup_errors, None,
                'the cleanup of the round of R14 met'))
        _raise_first_interruption(r14_interrupts)
        if r14_cleanup_errors and sys.exc_info()[0] is None:
            raise AssertionError('the cleanup of the round of R14 met %s'
                                 % (r14_cleanup_errors,))
