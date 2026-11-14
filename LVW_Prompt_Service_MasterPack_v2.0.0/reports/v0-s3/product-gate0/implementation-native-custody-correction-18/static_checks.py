"""The static checks of the correction 18 of the native custody.

The script is a **static** checker: it reads the sources as text, it
parses them with the standard ``ast`` and ``symtable`` modules and it
never imports, collects, executes or runs anything.  It never touches a
native library, an operating system process, a model, a GPU, a service,
a network, a medium, a database, a ledger or a counter.

The checks of the residual defects of the independent review of the
correction 17 inspect the **actual** exception boundaries and the
**actual** finalisation ordering of the candidate:

* the 189 frozen node identities and their order are unchanged and the
  four other modules are byte identical to their pins;
* the fourteen nodes of this module keep their names, their order,
  their signatures and their decorators and **no** assertion was
  removed;
* M3 1: the start of the controlled round and its ``RUNNING``
  assertion are in the **body** of the ``Try`` whose ``finally`` owns
  the drain of the owners - the nesting is read from the syntax tree
  and never from a comment;
* M3 2: the constructor seam reads the real ``_target`` of the stdlib
  thread and it targets the **exact** custody-owned channel;
* M3 3: the generic sentinel is never raised for the cleanup-only
  ``CLOSE_FAILURE`` checkpoint;
* M3 4: every non-close controlled subcase requires its **own** empty
  list of the close failures;
* M3 5: the drain reads the generation before the enumeration, after
  the enumeration and after the joined producers, and it takes a final
  exact-owner resnapshot;
* M3 6: the interruption objects and the diagnostic of a failed
  classification are retained and the stop of the round fails the
  proof;
* M3 7: every cleanup call site is guarded and every cleanup error is
  a **list**;
* M2 1/2: the phase is attempted before its construction and the
  attempt of the coordination happens before the operation;
* M2 3: the seam attempts the barrier, it persists the document before
  it publishes the completion and the phase consumes the error of that
  write;
* M2 4: the result of the phase is written **after** the cleanup and it
  carries the original failure;
* M2 5: the join and the query of the worker are guarded.

Usage::

    python3 -I static_checks.py <package-root> <baseline-blob>
"""
import ast
import builtins
import hashlib
import json
import sys
from pathlib import Path

MODULES = (
    ('tools/test_v0_s3_native_custody.py', 117),
    ('tools/test_v0_s3_native_custody_regressions.py', 16),
    ('tools/test_v0_s3_native_custody_correction05.py', 24),
    ('tools/test_v0_s3_native_custody_correction07.py', 18),
    ('tools/test_v0_s3_native_custody_correction10.py', 14),
)

PINS = {
    'tools/v0_s3_native_broker.py':
        '06cfc9518ccb782d456b930f627ca99e0774f82e81d214115277cef3be79bb83',
    'tools/v0_s3_native_custody.py':
        '7f26e9276a1c7507b0ad716fc31d8f5a4b17e5b670625a6982c52fbb93494581',
    'tools/test_v0_s3_native_custody.py':
        'fe96d2ffd353d3f3f6df4da2b023dd6cfaf58fe730ab6655afbca723ed507d32',
    'tools/test_v0_s3_native_custody_regressions.py':
        '03250ea0ac64519c57edfbe1be965eb2827b46fc7f2d80b47146e4a5e6e7cb93',
    'tools/test_v0_s3_native_custody_correction05.py':
        '8563989f078fcd45d44c496a0bea16c1ecf5005513543f6f4e00792e4ed7e130',
    'tools/test_v0_s3_native_custody_correction07.py':
        'dc74cf7f92e8be6cc2b69c602b9fc0b3fdd765ec8b9b48c4f061dde7bdcd6cdf',
}

#: The occurrences that the independent reviews of the correction 16
#: and of the correction 17 found removed.  Every one of them must be
#: absent **and** it must have a replacement that is equal or stronger.
REMOVED = (
    ("controlled['sentinel'] == '_R07Sentinel'",
     "failure['class'] is _R07Sentinel"),
    ("zero_session.state == 'RUNNING'",
     "zero_start_return['state'] == 'UNKNOWN_RETAINED'"),
    ('zero_attached_pump is not None',
     'zero_pump is zero_session._pump'),
    ('zero_attached_pump.is_alive()',
     "facts['zero_pump_finished'] is True"),
    ("item['alive'] is False",
     "_assert_salvage_proved(controlled['salvage']"),
    ('zero_held.wait(15.0)',
     "zero_premise['pump_at_admission'] is True"),
    ("controlled['failure'] is not None",
     "close_failures[0]['detail'] == 'controlled_close_failure'"),
)

#: The replacements that the correction 17 and the correction 18 add.
#: They are all present in the candidate.
REPLACEMENTS = (
    "failure['class'] is _R07Sentinel",
    "failure['token'] == checkpoint",
    "failure['class'] is _R07OrdinaryAssertion",
    "failure['token'] == _R07OrdinaryAssertion.TOKEN",
    "failure['class'] is _R07ConstructorFailure",
    "failure['token'] == 'CONSTRUCTOR_FAILURE'",
    "facts['zero_state'] == 'UNKNOWN_RETAINED'",
    "'CUSTODY_CHANNEL_TIMEOUT' in facts['zero_failures']",
    "facts['zero_broker_retained'] is True",
    'zero_session.broker is zero_broker',
    'zero_pump is zero_session._pump',
    "facts['zero_pump_finished'] is True",
    "zero_premise['pump_error_is_none'] is True",
    "zero_gate_facts[0]['released'] is True",
    "zero_reply_waits[-1] == 0.0",
    "zero_queue_waits[-1] == 0.0",
    "_assert_salvage_proved(zero_salvage",
    "_assert_salvage_proved(controlled['salvage']",
    "close_failures[0]['owner'] == 'controlled:transport'",
    "close_failures[0]['type'] == 'RuntimeError'",
    "close_failures[0]['detail'] == 'controlled_close_failure'",
    "controlled['cleanup_ran_while_unwinding'] is True",
    "controlled['cleanup_ran_while_unwinding'] is False",
    "controlled['quiescent'] is True",
    # -- the correction 18
    "controlled['close_failures'] == []",
    "api.barrier_write_error",
    "barrier_observed_object_is_original",
)

#: The forbidden forms of the candidate.
FORBIDDEN = (
    "unittest.mock.patch.object(broker_module, 'BrokerProcess',",
    "repr(pump.error) if pump is not None else None",
    "'broker_retained' in zero_returned",
    "controlled['sentinel'] == '_R07Sentinel'",
    "assert controlled['failure'] is not None",
    "any(item['owner'] == 'controlled:transport'",
    "'controlled_close_failure' in detail",
    "add(_session_owners('%s:session' % prefix, session, hints))",
    "add(_channel_owners('%s:channel' % prefix, channel, hints))",
    # -- the correction 18: the real attribute of the stdlib thread
    "getattr(thread, 'target', None)",
)

#: The forms that the correction 18 adds.
REQUIRED = (
    "getattr(thread, '_target', None)",
    "owner is not controlled_custody_channel()",
    "ledger.attempt(phase)",
    "ledger.attempt(phase + '-construction')",
    "ledger.attempt('r10-coordination')",
    "self.barrier_ledger.attempt(self.barrier_name)",
    "self._persist_barrier()",
    "self.barrier_completed.set()",
    "api.barrier_write_error is not None",
    "_stop_proof_failure(",
    "_note_interruption(",
    "controlled_interrupts",
    "cleanup_errors.append(",
    "all_salvage",
)

#: The inventory of the group of N10-R10: it is derived from the
#: operations that are really instrumented.
INVENTORY = (
    'r10-timeout-confirmed', 'r10-timeout-confirmed-construction',
    'r10-timeout-confirmed-barrier', 'r10-timeout-confirmed-first',
    'r10-timeout-confirmed-second',
    'r10-timeout-failed', 'r10-timeout-failed-construction',
    'r10-timeout-failed-barrier', 'r10-timeout-failed-first',
    'r10-timeout-failed-second',
    'r10-barrier-absent', 'r10-barrier-absent-construction',
    'r10-barrier-absent-barrier', 'r10-barrier-absent-first',
    'r10-barrier-absent-second',
    'r10-barrier-wrong-generation',
    'r10-barrier-wrong-generation-construction',
    'r10-barrier-wrong-generation-barrier',
    'r10-barrier-wrong-generation-first',
    'r10-barrier-wrong-generation-second',
    'r10-published-before-timeout',
    'r10-published-before-timeout-construction',
    'r10-published-before-timeout-first',
    'r10-published-before-timeout-second',
    'r10-first', 'r10-second', 'r10-coordination',
)


# -- the helpers of the AST inspection --------------------------------------

def sha256(data):
    return hashlib.sha256(data).hexdigest()


def nodes(source):
    """The names of the test nodes of one module, in their order."""
    tree = ast.parse(source)
    return [item.name for item in tree.body
            if isinstance(item, ast.FunctionDef) and item.name.startswith(
                'test_')]


def signatures(source):
    """The names, the arguments and the decorators of the test nodes."""
    tree = ast.parse(source)
    result = []
    for item in tree.body:
        if isinstance(item, ast.FunctionDef) and item.name.startswith(
                'test_'):
            result.append({
                'name': item.name,
                'args': [arg.arg for arg in item.args.args],
                'decorators': [ast.dump(dec) for dec in item.decorator_list],
                'lineno': item.lineno,
            })
    return result


def unbound_globals(source, path):
    """The global names that the module reads and that it never binds."""
    import symtable
    table = symtable.symtable(source, str(path), 'exec')
    known = set(table.get_identifiers()) | set(dir(builtins))
    problems = []

    def walk(scope):
        for symbol in scope.get_symbols():
            if symbol.is_global() and not symbol.is_assigned():
                if symbol.get_name() not in known:
                    problems.append('%s: %s' % (scope.get_name(),
                                                symbol.get_name()))
        for child in scope.get_children():
            walk(child)

    walk(table)
    return problems


def find_function(tree, name):
    """The function of the tree with the given name."""
    for item in ast.walk(tree):
        if isinstance(item, ast.FunctionDef) and item.name == name:
            return item
        if isinstance(item, ast.AsyncFunctionDef) and item.name == name:
            return item
    return None


def find_class(tree, name):
    """The class of the tree with the given name."""
    for item in ast.walk(tree):
        if isinstance(item, ast.ClassDef) and item.name == name:
            return item
    return None


def parent_map(node):
    """The parent of every node of the subtree."""
    result = {}
    for parent in ast.walk(node):
        for child in ast.iter_child_nodes(parent):
            result[child] = parent
    return result


def calls(node, name):
    """The calls of the given plain name inside the subtree."""
    return [item for item in ast.walk(node)
            if isinstance(item, ast.Call) and isinstance(item.func, ast.Name)
            and item.func.id == name]


def method_calls(node, dotted):
    """The calls of a dotted name inside the subtree.

    ``self.barrier_ledger.attempt`` matches a call whose function is the
    attribute ``attempt`` of the attribute ``barrier_ledger`` of the name
    ``self``.
    """
    parts = dotted.split('.')
    result = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Call):
            continue
        current = item.func
        matched = True
        for part in reversed(parts):
            if isinstance(current, ast.Attribute) and current.attr == part:
                current = current.value
            elif isinstance(current, ast.Name) and current.id == part:
                continue
            else:
                matched = False
                break
        if matched:
            result.append(item)
    return result


def handler_names(handler):
    """The names of the types that an ``except`` clause catches."""
    if handler.type is None:
        return []
    if isinstance(handler.type, ast.Name):
        return [handler.type.id]
    return string_constants(handler.type)


def has_status(node, value):
    """Does the call carry the status ``value`` in its arguments?"""
    for item in ast.walk(node):
        if isinstance(item, ast.Constant) and item.value == value:
            return True
    return False


def enclosing_try(node, parents):
    """The innermost ``Try`` that contains the node."""
    current = parents.get(node)
    while current is not None:
        if isinstance(current, ast.Try):
            return current
        current = parents.get(current)
    return None


def in_finalbody(node, try_node, parents):
    """Is the node inside the ``finally`` of the given ``Try``?"""
    current = node
    while current is not None:
        parent = parents.get(current)
        if parent is None:
            return False
        if parent is try_node:
            return any(item is current for item in try_node.finalbody)
        current = parent
    return False


def string_constants(node):
    """Every string constant of the subtree."""
    return [item.value for item in ast.walk(node)
            if isinstance(item, ast.Constant) and isinstance(item.value, str)]


def main(root, baseline):
    root = Path(root)
    checks = []
    failed = []

    def check(name, ok, detail=''):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail})
        if not ok:
            failed.append(name)

    # 1 - the pins of the production and of the other test modules
    for name, digest in sorted(PINS.items()):
        data = (root / name).read_bytes()
        check('pin:%s' % name, sha256(data) == digest, sha256(data))

    # 2 - the 189 frozen node identities and their order
    total = 0
    identities = []
    for name, count in MODULES:
        source = (root / name).read_text(encoding='utf-8')
        found = nodes(source)
        check('node-count:%s' % name, len(found) == count,
              '%d of %d' % (len(found), count))
        total += len(found)
        identities.extend('%s::%s' % (name, item) for item in found)
    check('denominator:189', total == 189, str(total))
    check('denominator:unique', len(set(identities)) == 189,
          str(len(set(identities))))

    # 3 - the nodes of this module against the baseline blob
    module = root / 'tools/test_v0_s3_native_custody_correction10.py'
    source = module.read_text(encoding='utf-8')
    baseline_source = Path(baseline).read_text(encoding='utf-8')
    now = [(item['name'], item['args'], item['decorators'])
           for item in signatures(source)]
    before = [(item['name'], item['args'], item['decorators'])
              for item in signatures(baseline_source)]
    check('nodes:names-order-signatures', now == before, json.dumps(now))
    tree = ast.parse(source)
    base_tree = ast.parse(baseline_source)
    skipped = [item.name for item in ast.walk(tree)
               if isinstance(item, ast.Call)
               and isinstance(item.func, ast.Attribute)
               and item.func.attr in ('skip', 'xfail', 'skipif')]
    check('nodes:no-skip-no-xfail', not skipped, json.dumps(skipped))
    check('module:compiles', compile(source, str(module), 'exec') is not None)
    base_asserts = len([item for item in ast.walk(base_tree)
                        if isinstance(item, ast.Assert)])
    now_asserts = len([item for item in ast.walk(tree)
                        if isinstance(item, ast.Assert)])
    check('module:no-assertion-removed', now_asserts >= base_asserts,
          '%d now, %d in the baseline' % (now_asserts, base_asserts))

    # 4 - every global that the module reads is bound
    problems = unbound_globals(source, module)
    check('module:no-unbound-global', not problems, json.dumps(problems))

    # 5 - the removed assertions and their replacements
    for old, new in REMOVED:
        check('removed:%s' % old, old not in source or new in source,
              'the predicate is %s present'
              % ('still' if old in source else 'not'))
    for item in REPLACEMENTS:
        check('replacement:%s' % item, item in source, '')
    for item in FORBIDDEN:
        check('forbidden:%s' % item, item not in source, '')
    for item in REQUIRED:
        check('required:%s' % item[:48], item in source, '')

    # 6 - the inventory of the group of N10-R10
    check('inventory:unique', len(INVENTORY) == len(set(INVENTORY)),
          str(len(INVENTORY)))
    for name in ('r10-timeout-confirmed', 'r10-timeout-failed',
                 'r10-barrier-absent', 'r10-barrier-wrong-generation',
                 'r10-published-before-timeout', 'r10-first', 'r10-second',
                 'r10-coordination'):
        check('inventory:name:%s' % name, name in source, '')

    # 7 - M3 1: the start of the controlled round and its RUNNING
    #     assertion are in the **body** of the try whose finally owns
    #     the drain of the owners.
    controlled = find_function(tree, 'controlled_failure')
    check('m3-1:controlled-present', controlled is not None, '')
    if controlled is not None:
        parents = parent_map(controlled)
        starts = calls(controlled, 'start_round')
        check('m3-1:start-round-found', len(starts) == 1, str(len(starts)))
        running = [item for item in ast.walk(controlled)
                   if isinstance(item, ast.Assert)
                   and 'RUNNING' in ast.unparse(item.test)
                   and 'controlled_start_return' in ast.unparse(item.test)]
        check('m3-1:running-assert-found', len(running) == 1,
              str(len(running)))
        for label, node in (('start', starts[0] if starts else None),
                            ('running', running[0] if running else None)):
            if node is None:
                check('m3-1:%s-nesting' % label, False, 'the node is missing')
                continue
            holder = enclosing_try(node, parents)
            ok = holder is not None and holder.finalbody
            if ok:
                ok = bool(calls(
                    ast.Module(body=holder.finalbody, type_ignores=[]),
                    '_drain_owners'))
            check('m3-1:%s-inside-the-cleanup-region' % label, ok,
                  'the try is %s' % (getattr(holder, 'lineno', None),))
        # the deliberate failures are caught **outside** of the cleanup
        # region: their handler belongs to a try that is an ancestor of
        # the cleanup region.
        cleanup_region = enclosing_try(starts[0], parents) if starts else None
        handlers = []
        for item in ast.walk(controlled):
            if isinstance(item, ast.ExceptHandler) and item.type is not None:
                names = handler_names(item)
                if any(name in ('_R07Sentinel', '_R07ConstructorFailure',
                                '_R07OrdinaryAssertion') for name in names):
                    handlers.append(item)
        check('m3-1:three-exact-handlers', len(handlers) == 3,
              str(len(handlers)))
        for handler in handlers:
            outer = enclosing_try(handler, parents)
            check('m3-1:handler-outside-the-cleanup-region',
                  outer is not None and outer is not cleanup_region,
                  'the handler is at %s' % (handler.lineno,))

    # 8 - M3 2: the real ``_target`` of the stdlib thread and the exact
    #     custody-owned channel.
    if controlled is not None:
        gets = [item for item in ast.walk(controlled)
                if isinstance(item, ast.Call)
                and isinstance(item.func, ast.Name)
                and item.func.id == 'getattr'
                and len(item.args) in (2, 3)
                and isinstance(item.args[1], ast.Constant)]
        target_reads = [item for item in gets
                        if item.args[1].value == 'target']
        underscore_reads = [item for item in gets
                            if item.args[1].value == '_target']
        check('m3-2:no-plain-target-read', not target_reads,
              str([item.lineno for item in target_reads]))
        check('m3-2:underscore-target-read', len(underscore_reads) == 1,
              str([item.lineno for item in underscore_reads]))
        exact = [item for item in ast.walk(controlled)
                 if isinstance(item, ast.Compare)
                 and isinstance(item.left, ast.Name)
                 and item.left.id == 'owner'
                 and any(isinstance(op, (ast.Is, ast.IsNot))
                         for op in item.ops)]
        check('m3-2:exact-owner-identity-check', len(exact) >= 1,
              str([item.lineno for item in exact]))
        custody = [item for item in ast.walk(controlled)
                   if isinstance(item, ast.FunctionDef)
                   and item.name == 'controlled_custody_channel']
        check('m3-2:custody-channel-lookup', len(custody) == 1, '')

    # 9 - M3 3: the generic sentinel is never raised for the cleanup-only
    #     CLOSE_FAILURE checkpoint.
    sentinel_raises = []
    for item in ast.walk(tree):
        if isinstance(item, ast.Raise) and isinstance(item.exc, ast.Call) \
                and isinstance(item.exc.func, ast.Name) \
                and item.exc.func.id == '_R07Sentinel':
            sentinel_raises.append(item)
    check('m3-3:one-sentinel-raise', len(sentinel_raises) == 1,
          str(len(sentinel_raises)))
    if controlled is not None and sentinel_raises:
        parents = parent_map(controlled)
        guard = enclosing_try(sentinel_raises[0], parents)
        holder = None
        for item in ast.walk(controlled):
            if isinstance(item, ast.If) and item.lineno \
                    <= sentinel_raises[0].lineno <= item.end_lineno:
                if holder is None or (item.end_lineno - item.lineno) < \
                        (holder.end_lineno - holder.lineno):
                    holder = item
        ok = False
        if holder is not None and isinstance(holder.test, ast.Compare):
            comparators = string_constants(holder.test)
            ok = 'CLOSE_FAILURE' in comparators \
                and 'CONSTRUCTOR_FAILURE' in comparators
        check('m3-3:close-failure-excluded-from-the-sentinel', ok,
              ast.unparse(holder.test) if holder is not None else 'no guard')

    # 10 - M3 4: every non-close controlled subcase requires its own
    #     empty list of the close failures.
    close_asserts = []
    for item in ast.walk(tree):
        if isinstance(item, ast.Assert) \
                and "controlled['close_failures'] == []" in ast.unparse(item.test):
            close_asserts.append(item)
    check('m3-4:close-failures-empty-assert', len(close_asserts) == 1,
          str(len(close_asserts)))
    if close_asserts and controlled is not None:
        parents = parent_map(controlled)
        inside = False
        for item in ast.walk(tree):
            if isinstance(item, ast.If) and isinstance(item.test, ast.Compare) \
                    and string_constants(item.test) == ['CLOSE_FAILURE']:
                for stmt in item.orelse:
                    for sub in ast.walk(stmt):
                        if sub is close_asserts[0]:
                            inside = True
        check('m3-4:assert-in-the-non-close-branch', inside, '')

    # 11 - M3 5: the drain reads the generation before the enumeration,
    #     after it and after the joined producers, and it takes a final
    #     exact-owner resnapshot.
    drain = find_function(tree, '_drain_owners')
    check('m3-5:drain-present', drain is not None, '')
    if drain is not None:
        enumerations = calls(drain, '_registry_owners')
        generations = [item for item in ast.walk(drain)
                       if isinstance(item, ast.Call)
                       and isinstance(item.func, ast.Attribute)
                       and item.func.attr == 'generation']
        check('m3-5:two-enumerations', len(enumerations) >= 2,
              str(len(enumerations)))
        check('m3-5:three-generation-readings', len(generations) >= 3,
              str(len(generations)))
        if len(enumerations) >= 2 and len(generations) >= 3:
            first = enumerations[0].lineno
            second = enumerations[1].lineno
            before = [item for item in generations if item.lineno < first]
            middle = [item for item in generations
                      if first < item.lineno < second]
            after = [item for item in generations if item.lineno > second]
            check('m3-5:generation-before-the-enumeration', len(before) >= 1,
                  str([item.lineno for item in before]))
            check('m3-5:generation-after-the-enumeration', len(middle) >= 1,
                  str([item.lineno for item in middle]))
            check('m3-5:generation-after-the-resnapshot', len(after) >= 1,
                  str([item.lineno for item in after]))
        keys = string_constants(drain)
        check('m3-5:generation-before-key', 'generation_before' in keys, '')
        check('m3-5:generation-after-key', 'generation_after' in keys, '')
        check('m3-5:quiescent-key', 'quiescent' in keys, '')

    # 12 - M3 6: the interruption objects, the diagnostic of a failed
    #     classification and the failure of the stop of the round.
    salvage = find_function(tree, '_salvage_threads')
    capture = find_function(tree, '_capture_stop')
    owner_state = find_function(tree, '_owner_start_state')
    check('m3-6:salvage-present', salvage is not None, '')
    check('m3-6:capture-present', capture is not None, '')
    check('m3-6:owner-state-present', owner_state is not None, '')
    if salvage is not None:
        args = ([arg.arg for arg in salvage.args.args]
                + [arg.arg for arg in salvage.args.kwonlyargs])
        check('m3-6:salvage-takes-the-interruptions',
              'interrupts' in args, json.dumps(args))
    if capture is not None:
        args = ([arg.arg for arg in capture.args.args]
                + [arg.arg for arg in capture.args.kwonlyargs])
        check('m3-6:capture-takes-the-interruptions',
              'interrupts' in args, json.dumps(args))
    if owner_state is not None:
        # the classification is **not** swallowed inside the helper: the
        # guard of the caller records the exact diagnostic.
        inner_try = [item for item in ast.walk(owner_state)
                     if isinstance(item, ast.Try)]
        check('m3-6:classification-not-swallowed', not inner_try,
              str([item.lineno for item in inner_try]))
    stop_proof = find_function(tree, '_stop_proof_failure')
    check('m3-6:stop-proof-helper', stop_proof is not None, '')
    if stop_proof is not None:
        users = calls(tree, '_stop_proof_failure')
        check('m3-6:stop-proof-used', len(users) >= 3, str(len(users)))

    # 13 - M3 7: the cleanup call sites are guarded and their errors are
    #     **lists**.
    for label, needle in (('controlled', 'close_failures'),
                           ('m09-timeout', 'cleanup_errors'),
                           ('m09-published', 'cleanup_errors')):
        check('m3-7:%s-errors-are-a-list' % label,
              needle in source, '')
    guarded = 0
    for item in ast.walk(tree):
        if isinstance(item, ast.ExceptHandler):
            if 'BaseException' in handler_names(item):
                guarded += 1
    check('m3-7:base-exception-guards', guarded >= 10, str(guarded))

    # 14 - M2 1 and M2 2: the phase is attempted before its construction
    #     and the attempt of the coordination happens before the
    #     operation.
    for label in ('_m09_timeout_phase', '_m09_published_fault_phase'):
        phase = find_function(tree, label)
        check('m2-1:%s-present' % label, phase is not None, '')
        if phase is None:
            continue
        parents = parent_map(phase)
        attempts = [item for item in ast.walk(phase)
                    if isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Attribute)
                    and item.func.attr == 'attempt'
                    and isinstance(item.func.value, ast.Name)
                    and item.func.value.id == 'ledger'
                    and isinstance(item.args[0], ast.Name)
                    and item.args[0].id == 'phase']
        chains = calls(phase, '_chain')
        check('m2-1:%s-phase-attempted' % label, len(attempts) >= 1,
              str(len(attempts)))
        check('m2-1:%s-chain-found' % label, len(chains) == 1,
              str(len(chains)))
        if attempts and chains:
            check('m2-1:%s-phase-attempted-before-the-construction' % label,
                  attempts[0].lineno < chains[0].lineno,
                  '%d < %d' % (attempts[0].lineno, chains[0].lineno))
        constructions = [item for item in ast.walk(phase)
                         if isinstance(item, ast.Call)
                         and isinstance(item.func, ast.Name)
                         and item.func.id == 'record'
                         and item.args
                         and isinstance(item.args[0], ast.BinOp)
                         and ast.unparse(item.args[0]).endswith(
                             "'-construction'")]
        check('m2-1:%s-construction-document' % label,
              len(constructions) >= 2, str(len(constructions)))
        passed = [item for item in constructions
                  if has_status(item, 'PASSED')]
        check('m2-1:%s-construction-passed-document' % label,
              len(passed) >= 1, str(len(passed)))

    r10 = find_function(tree,
                        'test_n10_r10_the_outcome_of_the_generation_wins_'
                        'over_the_cancellation')
    check('m2-2:r10-test-present', r10 is not None, '')
    if r10 is not None:
        parents = parent_map(r10)
        attempts = [item for item in ast.walk(r10)
                    if isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Attribute)
                    and item.func.attr == 'attempt'
                    and isinstance(item.func.value, ast.Name)
                    and item.func.value.id == 'ledger'
                    and item.args
                    and isinstance(item.args[0], ast.Constant)
                    and item.args[0].value == 'r10-coordination']
        endpoints = [item for item in ast.walk(r10)
                     if isinstance(item, ast.Call)
                     and isinstance(item.func, ast.Name)
                     and item.func.id == '_WindowsPipeEndpoint']
        check('m2-2:coordination-attempt-found', len(attempts) == 1,
              str(len(attempts)))
        check('m2-2:coordination-endpoint-found', len(endpoints) >= 1,
              str(len(endpoints)))
        if attempts and endpoints:
            coordination_endpoint = [item for item in endpoints
                                     if 'coordination' in ast.unparse(item)]
            check('m2-2:attempt-before-the-endpoint',
                  bool(coordination_endpoint)
                  and attempts[0].lineno < coordination_endpoint[0].lineno,
                  '%d < %d' % (attempts[0].lineno,
                               coordination_endpoint[0].lineno
                               if coordination_endpoint else -1))
        chains = calls(r10, '_chain')
        check('m2-2:early-chain-found', len(chains) == 1, str(len(chains)))
        if chains:
            holder = enclosing_try(chains[0], parents)
            ok = holder is not None and holder.finalbody
            if ok:
                ok = bool(calls(
                    ast.Module(body=holder.finalbody, type_ignores=[]),
                    '_drain_owners'))
            check('m2-2:early-chain-inside-its-guard', ok,
                  'the try is %s' % (getattr(holder, 'lineno', None),))

    # 15 - M2 3: the seam attempts the barrier, it persists the document
    #     before it publishes the completion and the phase consumes the
    #     error of that write.
    seam = find_function(tree, 'cancel_synchronous_io')
    check('m2-3:seam-present', seam is not None, '')
    if seam is not None:
        attempts = method_calls(seam, 'self.barrier_ledger.attempt')
        check('m2-3:the-seam-attempts-the-barrier', len(attempts) == 1,
              str(len(attempts)))
        persists = method_calls(seam, 'self._persist_barrier')
        completes = method_calls(seam, 'self.barrier_completed.set')
        check('m2-3:the-seam-persists', len(persists) >= 1,
              str(len(persists)))
        check('m2-3:the-seam-completes', len(completes) >= 1,
              str(len(completes)))
        if persists and completes:
            check('m2-3:persist-before-the-completion',
                  persists[-1].lineno < completes[-1].lineno,
                  '%d < %d' % (persists[-1].lineno, completes[-1].lineno))
        api_class = find_class(tree, '_M09TimeoutApi')
        identity = []
        if api_class is not None:
            identity = [item for item in ast.walk(api_class)
                        if isinstance(item, ast.Constant)
                        and item.value
                        == 'barrier_observed_object_is_original']
        check('m2-3:the-durable-identity-boolean', len(identity) >= 1,
              str(len(identity)))
    phase = find_function(tree, '_m09_timeout_phase')
    if phase is not None:
        readers = [item for item in ast.walk(phase)
                   if isinstance(item, ast.Attribute)
                   and item.attr == 'barrier_write_error']
        check('m2-3:the-phase-consumes-the-write-error',
              len(readers) >= 1, str(len(readers)))

    # 16 - M2 4: the result of the phase is written **after** the
    #     cleanup and it carries the original failure.
    for label in ('_m09_timeout_phase', '_m09_published_fault_phase'):
        phase = find_function(tree, label)
        if phase is None:
            continue
        parents = parent_map(phase)
        results = [item for item in ast.walk(phase)
                   if isinstance(item, ast.Call)
                   and isinstance(item.func, ast.Name)
                   and item.func.id in ('record', 'record_guarded')
                   and item.args and isinstance(item.args[0], ast.Name)
                   and item.args[0].id == 'phase'
                   and has_status(item, 'PASSED')]
        check('m2-4:%s-result-document' % label, len(results) >= 1,
              str(len(results)))
        if results:
            ok = False
            for item in results:
                holder = enclosing_try(item, parents)
                if holder is not None and in_finalbody(item, holder,
                                                        parents):
                    ok = True
            check('m2-4:%s-result-after-the-cleanup' % label, ok, '')
        # the handler of the failure does not write the result of the
        # phase: the result is written after the cleanup.
        skips = [item for item in ast.walk(phase)
                 if isinstance(item, ast.Compare)
                 and isinstance(item.left, ast.Name)
                 and item.left.id == 'name'
                 and any(isinstance(op, ast.Eq) for op in item.ops)]
        check('m2-4:%s-the-handler-skips-the-result' % label,
              len(skips) >= 1, str(len(skips)))
        original = [item for item in ast.walk(phase)
                    if isinstance(item, ast.Subscript)
                    and isinstance(item.value, ast.Name)
                    and item.value.id == 'original_failure']
        check('m2-4:%s-the-original-failure-is-retained' % label,
              len(original) >= 1, str(len(original)))
        quiescent = [item for item in ast.walk(phase)
                     if isinstance(item, ast.Subscript)
                     and isinstance(item.value, ast.Name)
                     and item.value.id == 'drain'
                     and isinstance(item.slice, ast.Constant)
                     and item.slice.value == 'quiescent']
        check('m2-4:%s-the-quiescence-is-required' % label,
              len(quiescent) >= 1, str(len(quiescent)))

    # 17 - M2 5: the join and the query of the worker are guarded.
    for label in ('_m09_timeout_phase', '_m09_published_fault_phase'):
        phase = find_function(tree, label)
        if phase is None:
            continue
        parents = parent_map(phase)
        joins = [item for item in ast.walk(phase)
                 if isinstance(item, ast.Call)
                 and isinstance(item.func, ast.Attribute)
                 and item.func.attr == 'join_bounded']
        check('m2-5:%s-worker-join-found' % label, len(joins) >= 1,
              str(len(joins)))
        guarded = 0
        for item in joins:
            holder = enclosing_try(item, parents)
            if holder is not None and holder.handlers:
                guarded += 1
        check('m2-5:%s-worker-join-guarded' % label, guarded == len(joins),
              '%d of %d' % (guarded, len(joins)))
        alive = [item for item in ast.walk(phase)
                 if isinstance(item, ast.Call)
                 and isinstance(item.func, ast.Attribute)
                 and item.func.attr == 'is_alive']
        check('m2-5:%s-worker-query-found' % label, len(alive) >= 1,
              str(len(alive)))

    # 18 - the finalisation ordering: the durable document is written
    #     before the terminal state of the ledger is updated.
    ordering_ok = True
    ordering_detail = []
    for label in ('_m09_timeout_phase', '_m09_published_fault_phase'):
        phase = find_function(tree, label)
        if phase is None:
            continue
        passes = [item for item in ast.walk(phase)
                  if isinstance(item, ast.Call)
                  and isinstance(item.func, ast.Attribute)
                  and item.func.attr == 'pass_'
                  and isinstance(item.func.value, ast.Name)
                  and item.func.value.id == 'ledger']
        for item in passes:
            argument = ast.unparse(item.args[0])
            writes = [other for other in ast.walk(phase)
                      if isinstance(other, ast.Call)
                      and isinstance(other.func, ast.Name)
                      and other.func.id == 'record'
                      and ast.unparse(other.args[0]) == argument
                      and other.lineno < item.lineno]
            if not writes:
                ordering_ok = False
                ordering_detail.append('%s: %s' % (label, argument))
    check('finalisation:document-before-the-ledger', ordering_ok,
          json.dumps(ordering_detail))

    # 19 - the evidence directory of this correction
    check('evidence:directory',
          'implementation-native-custody-correction-18' in source, '')

    report = {'checks': checks, 'failed': failed,
              'ok': not failed,
              'total': len(checks)}
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0 if not failed else 1


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
