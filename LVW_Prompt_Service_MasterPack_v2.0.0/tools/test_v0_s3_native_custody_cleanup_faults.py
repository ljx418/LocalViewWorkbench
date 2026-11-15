"""The supplemental negative cases of the cleanup of the native custody rounds.

CORRECTION 23 / OPT-B-03.  The five cases of this module are a
**separate supplemental denominator**: they are **not** a substitute for
the fixed 189 nodes and they are **not** the product 29 cases.

Every case drives the **actual** existing R07 or R09 function of
``tools/test_v0_s3_native_custody_correction10.py`` - the real public
production start, the real owners, the real lowest synthetic OS seams
and the real fixture cleanup - and it injects **one** fault at a fixture
observation or at the phase writer.  Nothing is copied from R07 or R09
and no simplified substitute lifecycle is written here.

Every recorder is **transparent**: it calls the **original** real method
and it forwards its result.  A recorder never replaces a production
method with a stand-in and it never writes a fake state where the real
one belongs.

The outcome of a case is read from the **real** artifacts of the run: the
document of the phase is read back from the disk and the facts of the
cleanup are read from it.  A case that passes means that the **callee**
failed in exactly the way that the contract of the case names; the case
itself is a negative test and its success is **not** a success of the
product.
"""

import contextlib
import json
import sys
import types
import unittest.mock
from pathlib import Path

import pytest

PACK_ROOT = Path(__file__).resolve().parents[1]
if str(PACK_ROOT) not in sys.path:
    sys.path.insert(0, str(PACK_ROOT))

import tools.v0_s3_native_broker as broker_module  # noqa: E402 - the path is set above
import tools.test_v0_s3_native_custody_correction10 as t10  # noqa: E402


#: The exact tokens of the injected faults.  They are the identity of the
#: faults and every case asserts the **exact** identity of the error
#: that it injected.
O_TOKEN = 'sup-01-original-failure'
E_TOKEN = 'sup-01-final-query-error'
K1_TOKEN = 'sup-02-first-interruption'
K2_TOKEN = 'sup-02-final-query-interruption'
INNER_WRITER_E_TOKEN = 'sup-03-inner-writer-error'
FINAL_WRITER_E_TOKEN = 'sup-04-final-writer-error'
R09_O_TOKEN = 'sup-05-original-failure'
INFLIGHT_E_TOKEN = 'sup-05-inflight-query-error'
LOOKUP_K_TOKEN = 'sup-05-thread-lookup-interruption'


def _final_query_code():
    """The code object of the guarded final query of the R07 fixture.

    The supplemental cases inject their fault **into** the real query of
    the real worker and they recognise that query by the code object of
    the fixture helper that performs it.  No other place of the round
    asks the worker that way, so the injected fault is really the fault
    of the final query and of nothing else.
    """
    function = t10.test_n10_r07_the_context_of_the_round_reaches_every_layer
    for const in function.__code__.co_consts:
        if (isinstance(const, types.CodeType)
                and const.co_name == 'zero_guarded_query'):
            return const
    return None


FINAL_QUERY_CODE = _final_query_code()


def _from_final_query(depth=3):
    """True when the call really comes from the final query of R07.

    CORRECTION 23 / OPT-B-04 (M2): the frames between the recorder and
    the guarded query of the fixture are three: the recorder of the
    liveness query, the **helper** of the fixture that performs the
    query, the lambda of the fixture and the guarded query itself.  The
    helper is therefore at depth 3 and the earlier depth of 2 stopped at
    the lambda of the fixture - the fault was then never injected.
    """
    try:
        return sys._getframe(depth).f_code is FINAL_QUERY_CODE
    except ValueError:  # pragma: no cover - the stack is always deep enough
        return False


@contextlib.contextmanager
def _case_evidence_root(name):
    """Give the case its own child evidence root below the run root.

    The route of the module is restored when the case ends: the normal
    R07 and R09 documents, the documents of the other rounds and the
    documents of the earlier rounds are never overwritten.
    """
    original = t10.EVIDENCE_DIR
    root = Path(original) / 'negative' / name
    t10.EVIDENCE_DIR = root
    try:
        yield root
    finally:
        t10.EVIDENCE_DIR = original


def _phase_writer(original, plan):
    """A transparent recorder of the phase writer of the fixture.

    The recorder calls the **original** writer of the fixture for every
    phase and it forwards its result.  The plan of the case decides what
    happens at one phase; the recorder counts the writes of every phase
    so that a case can inject its fault into one **exact** write and so
    that it can prove that the real writer really ran.
    """
    counts = {}
    calls = []
    injected = []

    def writer(phase, document):
        counts[phase] = counts.get(phase, 0) + 1
        calls.append((phase, counts[phase]))
        action = plan(phase, document, counts[phase])
        if action is None:
            return original(phase, document)
        mode, error = action
        if mode == 'after':
            # the real document is really written and the fault follows it
            original(phase, document)
        injected.append((phase, counts[phase], error))
        raise error

    writer.calls = calls
    writer.injected = injected
    return writer


def _liveness_recorder(original, error, state):
    """A transparent recorder of the liveness query of a real worker.

    The recorder calls the **original** query of the real worker and it
    forwards its result.  Only the one call that really comes from the
    final query of the R07 fixture carries the injected fault.
    """
    def is_alive(self):
        state['calls'] += 1
        if _from_final_query(3):
            state['injected'] += 1
            state['faulted'] = self
            state['faulted_name'] = getattr(self, 'name', None)
            raise error
        return original(self)

    is_alive.state = state
    return is_alive


def _read_document(root, phase):
    """Read one phase document back from the disk of the run."""
    path = Path(root) / ('n10-%s.json' % phase)
    assert path.exists(), 'the phase document %s was never written' % phase
    return json.loads(path.read_text(encoding='utf-8'))


def test_n1_sup_01_final_query_preserves_original(tmp_path):
    """N1-SUP-01: a failing final query never replaces the original.

    The zero body of R07 raises an exact original failure after its raw
    facts were really written, and the final query of the actual worker
    raises an ordinary error once.  The round must leave with the
    **exact** original, the publication must retain both the original
    and the error of the query, and the owners of the round must really
    end with their handles really released.

    The callee is expected to FAIL: the success of this negative case is
    the failure of the callee with the exact original.
    """
    injected_o = AssertionError(O_TOKEN)

    def plan(phase, document, index):
        if phase == 'r07-zero-public-chain' and index == 1:
            return ('after', injected_o)
        return None

    with _case_evidence_root('sup-01') as root:
        state = {'calls': 0, 'injected': 0}
        original_is_alive = broker_module._WindowsPipeWorker.is_alive
        writer = _phase_writer(t10.write_phase, plan)
        with unittest.mock.patch.object(t10, 'write_phase', writer), \
                unittest.mock.patch.object(
                    broker_module._WindowsPipeWorker, 'is_alive',
                    _liveness_recorder(original_is_alive,
                                        OSError(E_TOKEN), state)):
            with pytest.raises(AssertionError) as info:
                t10.test_n10_r07_the_context_of_the_round_reaches_every_layer(
                    tmp_path)
        # the **exact** original left the round and not the error of the
        # query of the final state: the identity of the object is checked
        # and not only its type and its token
        assert type(info.value) is AssertionError, (
            'the round left with %s and not with the original failure'
            % (type(info.value).__name__,))
        assert str(info.value) == O_TOKEN, (
            'the round left with a different failure: %s' % (info.value,))
        assert info.value is injected_o, (
            'the round left with another failure of the same type and the '
            'same token: %r' % (info.value,))
        # the fault of the final query really happened and it happened
        # exactly once
        assert state['injected'] == 1, (
            'the fault of the final query was not injected exactly once: %s'
            % (state,))
        assert writer.injected and writer.injected[0][0] == (
            'r07-zero-public-chain'), (
            'the original failure was not injected into the zero body: %s'
            % (writer.injected,))
        # the publication of the cleanup retained the original and the
        # error of the query
        document = _read_document(root, 'r07-zero-salvage')
        assert document['original']['type'] == 'AssertionError', (
            'the publication did not retain the original: %s'
            % (document.get('original'),))
        assert document['original']['detail'] == O_TOKEN, (
            'the publication retained another original: %s'
            % (document.get('original'),))
        assert any(item.get('type') == 'OSError'
                   and E_TOKEN in (item.get('detail') or '')
                   for item in document['cleanup_errors']), (
            'the publication did not retain the error of the final query: %s'
            % (document.get('cleanup_errors'),))
        # the **unknown** of the failed final query is retained: the round
        # failed closed, the unknown was never read as a fact and it was
        # never overwritten by a false one.
        assert document['fixture_unknown_queries'], (
            'the unknown of the failed final query was not retained: %s'
            % (document.get('fixture_unknown_queries'),))
        assert document['fixture_handle_proof'], (
            'the unknown of the final query did not fail the round: %s'
            % (document.get('fixture_handle_proof'),))
        assert document['proof_failure'], (
            'the failed proof of the cleanup was not retained: %s'
            % (document.get('proof_failure'),))
        assert document['fixture_retained_workers'] == 0, (
            'the round retained a worker: %s'
            % (document.get('fixture_retained_workers'),))
        assert document['fixture_shutdown'], (
            'the fixture did not shut any worker down')
        unknown_entries = [entry for entry in document['fixture_shutdown']
                           if entry['alive_after'] is None]
        assert unknown_entries, (
            'the liveness of the worker of the failed query was not '
            'unknown: %s' % (document['fixture_shutdown'],))
        # the **physical** cleanup is proven **independently** of the
        # unknown: the drain of the round really joined every owner and
        # every owner is really dead.  That proof never overwrites the
        # unknown of the final query and it never turns it into a false.
        assert document['salvage'], (
            'the drain of the round proved no owner at all')
        for item in document['salvage']:
            assert item.get('joined') is True, (
                'an owner of the round was not joined: %s' % (item,))
            assert item.get('alive') is False, (
                'an owner of the round is still alive: %s' % (item,))
        # the fault really landed on the worker that the fixture really
        # held: the identity of the worker is checked with its name in
        # the facts of the shutdown.
        faulted = state.get('faulted_name')
        assert faulted, (
            'the fault of the final query did not name its worker: %s'
            % (state,))
        assert faulted in [entry.get('thread')
                           for entry in document['fixture_shutdown']], (
            'the fault of the final query did not land on a worker that the '
            'fixture held: %s' % (state,))


def test_n1_sup_02_final_query_preserves_first_interruption(tmp_path):
    """N1-SUP-02: the first exact interruption wins over a later one.

    The release of the round records an exact earlier cancellation as a
    pending interruption of the cleanup, and the final query of the
    actual worker raises a **distinct** exact cancellation once.  The
    round must leave with the **first** exact pending interruption and
    not with the later one, both interruption facts must survive in the
    publication and the real cleanup must be proven.

    The injected cancellation is a **controlled pending state** of the
    fixture: it is never called a real user interrupt.

    The callee is expected to FAIL: the success of this negative case is
    the failure of the callee with the exact first interruption.
    """
    def plan(phase, document, index):
        return None

    # CORRECTION 23 / OPT-B-04 (M3/M5): the exact cancellation of the
    # fixture is **pre-created**: it is one object and it is the object
    # that the interruption mechanism of the cleanup records.
    k1_error = KeyboardInterrupt(K1_TOKEN)
    k2_error = KeyboardInterrupt(K2_TOKEN)

    with _case_evidence_root('sup-02') as root:
        state = {'calls': 0, 'injected': 0}
        original_is_alive = broker_module._WindowsPipeWorker.is_alive
        original_drain = t10._drain_owners
        drain_state = {'k1': 0, 'calls': 0}

        def drain_owners(registry, session=None, channel=None,
                         prefix='round', *, seconds=10.0, budget=30.0,
                         release=None, interrupts=None):
            drain_state['calls'] += 1
            if release is not None and len(release) >= 3 \
                    and not drain_state['k1']:
                drain_state['k1'] = 1
                # the **original** third callback of the drain is kept and
                # it is really called: the real close of the channel of
                # the round is never omitted and the first gate is never
                # executed twice.
                original_third = release[2]

                def k1_release():
                    # the original callback is really called and its
                    # result is forwarded; the exact cancellation of the
                    # fixture follows it and it is injected **once**.
                    original_third()
                    raise k1_error

                release = tuple(release[:2]) + (k1_release,) \
                    + tuple(release[3:])
            return original_drain(registry, session=session,
                                  channel=channel, prefix=prefix,
                                  seconds=seconds, budget=budget,
                                  release=release, interrupts=interrupts)

        writer = _phase_writer(t10.write_phase, plan)
        with unittest.mock.patch.object(t10, 'write_phase', writer), \
                unittest.mock.patch.object(t10, '_drain_owners',
                                           drain_owners), \
                unittest.mock.patch.object(
                    broker_module._WindowsPipeWorker, 'is_alive',
                    _liveness_recorder(original_is_alive, k2_error,
                                        state)):
            with pytest.raises(KeyboardInterrupt) as info:
                t10.test_n10_r07_the_context_of_the_round_reaches_every_layer(
                    tmp_path)
        # the **first** exact pending interruption left the round and not
        # the later one: the identity of the object is checked and not
        # only its type and its token
        assert type(info.value) is KeyboardInterrupt, (
            'the round left with %s and not with the interruption'
            % (type(info.value).__name__,))
        assert str(info.value) == K1_TOKEN, (
            'the round left with another interruption: %s' % (info.value,))
        assert info.value is k1_error, (
            'the round left with another interruption of the same type and '
            'the same token: %r' % (info.value,))
        assert k2_error is not k1_error, (
            'the two interruptions of the case are the same object')
        assert drain_state['k1'] == 1, (
            'the first interruption was never recorded by the mechanism of '
            'the cleanup')
        assert state['injected'] == 1, (
            'the fault of the final query was not injected exactly once: %s'
            % (state,))
        # both interruption facts survive in the publication
        document = _read_document(root, 'r07-zero-salvage')
        details = [item.get('detail') or '' for item in
                   document.get('interrupts', [])]
        assert any(K1_TOKEN in detail for detail in details), (
            'the publication lost the first interruption: %s' % (details,))
        assert any(K2_TOKEN in detail for detail in details), (
            'the publication lost the later interruption: %s' % (details,))
        # the **unknown** of the failed final query is retained: the round
        # failed closed and the unknown was never read as a fact.
        assert document['fixture_unknown_queries'], (
            'the unknown of the failed final query was not retained: %s'
            % (document.get('fixture_unknown_queries'),))
        assert document['fixture_handle_proof'], (
            'the unknown of the final query did not fail the round: %s'
            % (document.get('fixture_handle_proof'),))
        assert document['proof_failure'], (
            'the failed proof of the cleanup was not retained: %s'
            % (document.get('proof_failure'),))
        # the **physical** cleanup is proven **independently** of the
        # unknown: the drain of the round really joined every owner and
        # every owner is really dead, and that proof never overwrites the
        # unknown of the final query.
        assert document['quiescent'] is True, (
            'the round of zero was not quiescent: %s' % (document,))
        assert document['salvage'], (
            'the drain of the round proved no owner at all')
        for item in document['salvage']:
            assert item.get('joined') is True, (
                'an owner of the round was not joined: %s' % (item,))
            assert item.get('alive') is False, (
                'an owner of the round is still alive: %s' % (item,))
        assert document['fixture_retained_workers'] == 0, (
            'the round retained a worker: %s'
            % (document.get('fixture_retained_workers'),))


def test_n1_sup_03_inner_writer_error_rejects_success(tmp_path):
    """N1-SUP-03: an inner writer error of the controlled subcase fails it.

    Inside the actual controlled subcase CHILD_TRANSPORT of R07 one
    inner write of the phase raises an ordinary error once and the
    later writes really succeed.  The round must **fail** with that
    error in its verdict and it must never return normally; the
    deliberate sentinel of the subcase must stay recorded and the real
    raw and cleanup facts must be retained.

    The callee is expected to FAIL: the success of this negative case is
    the failure of the callee with the observed error.
    """
    def plan(phase, document, index):
        if phase == 'r07-controlled-failure-child_transport' and index == 1:
            return ('before', OSError(INNER_WRITER_E_TOKEN))
        return None

    with _case_evidence_root('sup-03') as root:
        writer = _phase_writer(t10.write_phase, plan)
        with unittest.mock.patch.object(t10, 'write_phase', writer):
            with pytest.raises(AssertionError) as info:
                t10.test_n10_r07_the_context_of_the_round_reaches_every_layer(
                    tmp_path)
        # the round failed and it failed with the observed error
        assert len(writer.injected) == 1, (
            'the error of the inner writer was not injected exactly once: %s'
            % (writer.injected,))
        assert writer.injected[0][0] == (
            'r07-controlled-failure-child_transport'), (
            'the error was not injected into the inner writer: %s'
            % (writer.injected,))
        assert INNER_WRITER_E_TOKEN in str(info.value), (
            'the round did not fail with the observed error: %s' % (info.value,))
        # the deliberate sentinel of the subcase is still recorded and the
        # error of the writer is in the facts of the subcase
        document = _read_document(root, 'r07-controlled-failure-child_transport')
        assert (document.get('failure') or {}).get('type') == '_R07Sentinel', (
            'the deliberate sentinel of the subcase was not recorded: %s'
            % (document.get('failure'),))
        assert any(item.get('type') == 'OSError'
                   and INNER_WRITER_E_TOKEN in (item.get('detail') or '')
                   for item in document.get('cleanup_errors', [])), (
            'the error of the inner writer is not in the facts of the '
            'subcase: %s' % (document.get('cleanup_errors'),))
        assert document.get('quiescent') is True, (
            'the owners of the subcase were not quiescent: %s' % (document,))


def test_n1_sup_04_recovered_final_write_has_failed_proof(tmp_path):
    """N1-SUP-04: the recovered write of the final evidence is a FAIL.

    Only the **final** write of the evidence of the actual controlled
    subcase CHILD_TRANSPORT raises an ordinary error once and the
    bounded retry of the fixture really succeeds.  The round must fail
    and the **durable** document that the retry wrote must carry the
    error **and** a non-empty failed proof - the proof is never a late
    update that only exists in memory.

    The callee is expected to FAIL: the success of this negative case is
    the failure of the callee and the durable failed proof on the disk.
    """
    def plan(phase, document, index):
        if phase == 'r07-controlled-failure-child_transport' and index == 3:
            return ('before', OSError(FINAL_WRITER_E_TOKEN))
        return None

    with _case_evidence_root('sup-04') as root:
        writer = _phase_writer(t10.write_phase, plan)
        with unittest.mock.patch.object(t10, 'write_phase', writer):
            with pytest.raises(AssertionError) as info:
                t10.test_n10_r07_the_context_of_the_round_reaches_every_layer(
                    tmp_path)
        assert len(writer.injected) == 1, (
            'the error of the final writer was not injected exactly once: %s'
            % (writer.injected,))
        assert writer.injected[0][1] == 3, (
            'the error was not injected into the final write: %s'
            % (writer.injected,))
        assert FINAL_WRITER_E_TOKEN in str(info.value), (
            'the round did not fail with the observed error: %s' % (info.value,))
        # the document that the **retry** wrote carries the error and the
        # failed proof: it is read back from the disk
        document = _read_document(root, 'r07-controlled-failure-child_transport')
        assert any(item.get('type') == 'OSError'
                   and FINAL_WRITER_E_TOKEN in (item.get('detail') or '')
                   for item in document.get('cleanup_errors', [])), (
            'the recovered document does not carry the error of the final '
            'write: %s' % (document.get('cleanup_errors'),))
        assert document.get('proof_failure'), (
            'the recovered document does not carry the failed proof: %s'
            % (document.get('proof_failure'),))
        assert document.get('quiescent') is True, (
            'the owners of the subcase were not quiescent: %s' % (document,))


def test_n1_sup_05_held_startup_owner_survives_query_faults(tmp_path):
    """N1-SUP-05: the held owner and thread survive the failing queries.

    The actual interrupted start of R09 observes its owner and its
    thread, the body raises an exact original failure before the settle
    of the owner, the query of the owners that are in flight raises an
    ordinary error and the lookup of the thread raises an exact
    cancellation.  The **exact** original must win, the real settle of
    the held owner and the real join of the held thread must really
    happen - the recorders prove it - the known liveness must be dead
    and the failure evidence must survive.

    The callee is expected to FAIL: the success of this negative case is
    the failure of the callee with the exact original.
    """
    original_owner = broker_module._StartupOwner

    class _LookupFaultOwner(original_owner):
        """The real owner of a startup step, with a failing lookup.

        The class is the **real** class of the owner: it keeps the whole
        lifecycle of the owner and only the **lookup** of its thread
        fails, and only after the fixture really asked the owner to
        settle.  The real settle and the real join of the fixture run
        against this very owner.
        """

        lookup_fault = None

        @property
        def _thread(self):
            fault = type(self).lookup_fault
            if fault is not None:
                raise fault
            return self._thread_value

        @_thread.setter
        def _thread(self, value):
            self._thread_value = value

    inflight_state = {'armed': 0, 'injected': 0, 'calls': 0}
    # CORRECTION 23 / OPT-B-04 (M5): the exact original of the case is
    # pre-created and the case compares the **object** that left the
    # round with it.
    injected_o = AssertionError(R09_O_TOKEN)

    def plan(phase, document, index):
        if phase == 'r09-interrupted-start' and index == 1:
            inflight_state['armed'] = 1
            return ('after', injected_o)
        return None

    with _case_evidence_root('sup-05') as root:
        lookup_state = {'armed': 0, 'injected': 0}
        settle_calls = []
        join_calls = []
        original_inflight = broker_module._RoundContext.inflight
        original_settle = broker_module._StartupOwner.settle
        original_join_owner = t10._join_owner

        def inflight(self):
            inflight_state['calls'] += 1
            if inflight_state['armed'] and not inflight_state['injected']:
                inflight_state['injected'] = 1
                raise OSError(INFLIGHT_E_TOKEN)
            return original_inflight(self)

        def settle(self, seconds):
            result = original_settle(self, seconds)
            # the **exact** thread of the owner is read **before** the
            # lookup of the thread starts to fail: the case compares the
            # thread that the fixture really joined with it.
            owner_thread = getattr(self, '_thread', None)
            settle_calls.append((self, seconds, owner_thread))
            if seconds == 5.0:
                # the settle of the held owner really happened: the
                # lookup of the thread fails from now on
                lookup_state['armed'] = 1
                _LookupFaultOwner.lookup_fault = KeyboardInterrupt(
                    LOOKUP_K_TOKEN)
            return result

        def join_owner(label, thread, errors, interrupts, *, seconds=10.0,
                       join=None):
            join_calls.append((label, thread))
            return original_join_owner(label, thread, errors, interrupts,
                                       seconds=seconds, join=join)

        writer = _phase_writer(t10.write_phase, plan)
        with unittest.mock.patch.object(t10, 'write_phase', writer), \
                unittest.mock.patch.object(broker_module, '_StartupOwner',
                                           _LookupFaultOwner), \
                unittest.mock.patch.object(broker_module._RoundContext,
                                           'inflight', inflight), \
                unittest.mock.patch.object(broker_module._StartupOwner,
                                           'settle', settle), \
                unittest.mock.patch.object(t10, '_join_owner', join_owner):
            with pytest.raises(AssertionError) as info:
                t10.test_n10_r09_every_exit_of_the_startup_owner_joins_its_thread(
                    tmp_path)
        # the **exact** original won the round
        assert type(info.value) is AssertionError, (
            'the round left with %s and not with the original failure'
            % (type(info.value).__name__,))
        assert str(info.value) == R09_O_TOKEN, (
            'the round left with another failure: %s' % (info.value,))
        assert info.value is injected_o, (
            'the round left with another failure of the same type and the '
            'same token: %r' % (info.value,))
        assert inflight_state['injected'] == 1, (
            'the error of the query of the owners in flight was not injected '
            'exactly once: %s' % (inflight_state,))
        assert lookup_state['armed'] == 1, (
            'the settle of the held owner never happened: %s' % (settle_calls,))
        # the real settle of the held owner really happened: the query of
        # the owners in flight really failed, so the owner that the
        # fixture held is the only owner that it settled.
        held_settles = [item for item in settle_calls if item[1] == 5.0]
        assert held_settles, (
            'the fixture never settled the owner that it held: %s'
            % (settle_calls,))
        # the real join of the held thread really happened
        held_joins = [item for item in join_calls
                      if item[0] == 'interrupted-start']
        assert held_joins, (
            'the fixture never joined the thread that it held: %s'
            % (join_calls,))
        assert held_joins[0][1] is not None, (
            'the join of the held thread had no thread: %s' % (held_joins,))
        # the **identity** of the held owner and of its thread: the join
        # really joined the thread of the owner that the fixture settled,
        # and it is checked with ``is`` and not with a name or a token.
        settled_owner, _settled_seconds, settled_thread = held_settles[0]
        assert settled_thread is not None, (
            'the held owner had no thread of its own: %s' % (held_settles,))
        assert held_joins[0][1] is settled_thread, (
            'the fixture joined another thread than the one of the owner '
            'that it held: %s' % (held_joins,))
        assert settled_owner is not None, (
            'the settle of the held owner had no owner: %s' % (held_settles,))
        # the failure evidence of the cleanup survives and the known
        # liveness is dead
        document = _read_document(root, 'r09-interrupted-start')
        assert (document.get('original') or {}).get('detail') == R09_O_TOKEN, (
            'the publication did not retain the original: %s'
            % (document.get('original'),))
        kinds = [item.get('kind') for item in document.get('cleanup_errors', [])]
        assert 'INFLIGHT' in kinds, (
            'the publication did not retain the error of the query of the '
            'owners in flight: %s' % (document.get('cleanup_errors'),))
        assert 'OWNER_THREAD' in kinds, (
            'the publication did not retain the interruption of the lookup of '
            'the thread: %s' % (document.get('cleanup_errors'),))
        assert document.get('owner_alive') is False, (
            'the known liveness of the held owner was not dead: %s'
            % (document.get('owner_alive'),))
        assert document.get('liveness_known') is True, (
            'the liveness of the held owner was not known: %s' % (document,))
