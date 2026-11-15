"""The static checks of the correction 19 of the native custody.

The script is a **static** checker: it reads the sources as text, it
parses them with the standard ``ast`` and ``symtable`` modules and it
never imports, collects, executes or runs anything.  It never touches a
native library, an operating system process, a model, a GPU, a service,
a network, a medium, a database, a ledger or a counter.

The checks of the residual defects of the independent review of the
correction 18 inspect the **actual** exception boundaries and the
**actual** finalisation ordering of the candidate:

* the 189 frozen node identities and their order are unchanged and the
  four other modules are byte identical to their pins;
* the fourteen nodes of this module keep their names, their order,
  their signatures and their decorators and **no** assertion predicate of
  the baseline is removed (the multiset of the assertion predicates is
  compared and the difference is reported);
* R1/M3 1: the exact **child** channel of the controlled custody is
  selected and the parent channel is proved different from it;
* R2/M2 1: every terminal transition of the ledger follows a
  **successful** terminal write;
* R3/M3 4: the cleanup owning try of the coordination contains the
  construction of the endpoint and the start of the reader in its body;
* M2 2: the durable facts of the barrier survive every rewrite and the
  final document of the phase;
* M2 3: the terminal document of the earlier work is written after its
  cleanup;
* M2 4: the quiescence is a proof failure and it is enforced by every
  caller;
* M3 2: the traversal of the owners, the reads of the drain and the
  release of the gates are best effort;
* M3 3: the exact cancellation is rethrown before the proof assertion by
  every caller;
* M3 5: the close of every child endpoint is ``BaseException`` aware.

Usage::

    python3 -I static_checks.py <package-root> <baseline-blob>
"""
import ast
import builtins
import collections
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

#: The predicates that the independent reviews of the correction 15, 16
#: and 17 found removed.  Every one of them must be absent **and** it
#: must have a replacement that is equal or stronger.
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

#: The replacements that the corrections 17, 18 and 19 add.
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
    "controlled['close_failures'] == []",
    "api.barrier_write_error",
    "barrier_observed_object_is_original",
    # -- the correction 19
    "child = controlled_custody_channel()",
    "if owner is not child:",
    "child is not controlled_parent_channel",
    "entry['name'] == 'controlled:channel'",
    "written_result is not None",
    "phase_failure_detail",
    "_interruption_facts(",
    "early_failure",
    "coord_failure",
    "'r10-early-salvage'",
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
    "getattr(thread, 'target', None)",
    # -- the correction 19: the first channel of the registry is the
    #    channel of the parent and it is never the child
    "for entry in controlled_registry.entries():\n            if entry['kind'] "
    "== 'channel':\n                return entry['owner']",
    # -- the correction 19: an unconditional ledger transition after a
    #    failed terminal write
    "ledger.fail(name, type(error).__name__)\n                raise",
)

#: The forms that the correction 19 adds.
REQUIRED = (
    "getattr(thread, '_target', None)",
    "ledger.attempt(phase)",
    "ledger.attempt(phase + '-construction')",
    "ledger.attempt('r10-coordination')",
    "ledger.attempt('r10-early-salvage')",
    "self.barrier_ledger.attempt(self.barrier_name)",
    "self._persist_barrier()",
    "self.barrier_completed.set()",
    "api.barrier_write_error is not None",
    "_stop_proof_failure(",
    "_note_interruption(",
    "controlled_interrupts",
    "early_interrupts",
    "coord_interrupts",
    "outer_interrupts",
    "cleanup_errors.append(",
    "all_salvage",
    "release=(lambda: gate.set(),",
    "release=(lambda: zero_gate.set(),",
)

#: The inventory of the group of N10-R10: it is derived from the
#: operations that are really instrumented.  The correction 19 adds the
#: terminal verdict of the earlier work of the group.
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
    'r10-early-salvage',
)

#: The callers that must enforce the quiescence and the exact priority
#: of the cancellation.
CALLERS = (
    'test_n10_r07_the_context_of_the_round_reaches_every_layer',
    'test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation',
    '_m09_timeout_phase',
    '_m09_published_fault_phase',
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


def assertion_predicates(tree):
    """The multiset of the predicates of the assertions of a tree."""
    counter = collections.Counter()
    for item in ast.walk(tree):
        if isinstance(item, ast.Assert):
            counter[ast.unparse(item.test)] += 1
    return counter


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
    """The calls of a dotted name inside the subtree."""
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


def block_chain(node, parents):
    """The enclosing statement lists of the node, innermost first.

    Every item is a pair ``(block, index)``: the list of the statements
    and the place of the node in it.
    """
    chain = []
    current = node
    while True:
        parent = parents.get(current)
        if parent is None:
            break
        found = None
        for field in ('body', 'orelse', 'finalbody'):
            block = getattr(parent, field, None)
            if not isinstance(block, list):
                continue
            for index, item in enumerate(block):
                if item is current:
                    found = (block, index)
                    break
            if found is not None:
                break
        if found is not None:
            chain.append(found)
        current = parent
    return chain


def write_calls(node):
    """The calls of a write of a document inside the subtree."""
    result = []
    for item in ast.walk(node):
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name) \
                and item.func.id in ('write_phase', 'record', 'record_guarded'):
            result.append(item)
    return result


def write_guarded(call, parents):
    """Is the terminal transition guarded by the result of a write?

    Three shapes are accepted and they are the shapes of the candidate:

    * an enclosing ``if`` whose test names the **result** of the write
      (``written_result``, ``document['status']``, ``early_failure``);
    * a preceding statement of the same block that is an **unguarded**
      write of the same name (``record`` or ``write_phase``): such a
      write raises when it fails and the transition is never reached;
    * a preceding ``try`` whose body is the write and whose handler
      leaves the block (``continue``) when the write failed.
    """
    markers = ('written_result', "document[", 'early_failure',
               'coord_failure')
    current = call
    while True:
        parent = parents.get(current)
        if parent is None:
            break
        if isinstance(parent, ast.If):
            test = ast.unparse(parent.test)
            for marker in markers:
                if marker in test:
                    return True, 'guarded by %s' % test
        current = parent
    name = ast.unparse(call.args[0]) if call.args else ''
    for block, index in block_chain(call, parents):
        for item in block[:index]:
            if isinstance(item, ast.Try):
                writes = write_calls(item)
                leaves = [node for handler in item.handlers
                          for node in ast.walk(handler)
                          if isinstance(node, (ast.Continue, ast.Raise))]
                if writes and leaves:
                    return True, 'guarded by the write of the try'
            for other in write_calls(item):
                if other.func.id in ('record', 'write_phase') and other.args:
                    if ast.unparse(other.args[0]) == name:
                        return True, 'guarded by the preceding write'
    return False, 'no guard'


def quiescence_checks(node):
    """The comparisons that require a quiescence that is not ``True``."""
    result = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Compare):
            continue
        if not any(isinstance(op, ast.IsNot) for op in item.ops):
            continue
        text = ast.unparse(item)
        if "'quiescent'" in text and 'True' in text:
            result.append(item)
    return result


def interrupt_raises(node):
    """The raises of the **exact** object of a cancellation."""
    result = []
    for item in ast.walk(node):
        if isinstance(item, ast.Raise) and isinstance(item.exc, ast.Subscript) \
                and isinstance(item.exc.slice, ast.Constant) \
                and item.exc.slice.value == 0:
            result.append(item)
    return result


def shallow_raises(block):
    """The raises of a block and of the single body of its conditions.

    A condition of the form ``if <guard>: raise ...`` is read as the
    raise of the block: the order of the conditions is the order of the
    failures and it is the order that the contract fixes.
    """
    result = []
    for item in block:
        if isinstance(item, ast.Raise):
            result.append(item)
        elif isinstance(item, ast.If) and len(item.body) == 1 \
                and isinstance(item.body[0], ast.Raise):
            result.append(item.body[0])
    result.sort(key=lambda node: node.lineno)
    return result


def all_blocks(function):
    """Every statement list of the subtree of the function."""
    result = []
    for node in ast.walk(function):
        for field in ('body', 'orelse', 'finalbody'):
            block = getattr(node, field, None)
            if isinstance(block, list) and block \
                    and all(isinstance(item, ast.stmt) for item in block):
                result.append(block)
    return result


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

    # 3b - the assertion equivalence: no predicate of the baseline is
    #      removed and every added predicate is reported.
    base_asserts = assertion_predicates(base_tree)
    now_asserts = assertion_predicates(tree)
    removed = sorted((base_asserts - now_asserts).elements())
    added = sorted((now_asserts - base_asserts).elements())
    check('assertions:none-removed', not removed, json.dumps(removed))
    check('assertions:none-reduced',
          sum(now_asserts.values()) >= sum(base_asserts.values()),
          '%d now, %d in the baseline' % (sum(now_asserts.values()),
                                         sum(base_asserts.values())))

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
                 'r10-coordination', 'r10-early-salvage'):
        check('inventory:name:%s' % name, name in source, '')

    # 7 - no new import and no new module level definition
    def imports(tree):
        result = []
        for item in ast.walk(tree):
            if isinstance(item, ast.Import):
                result.extend(alias.name for alias in item.names)
            elif isinstance(item, ast.ImportFrom):
                result.append('%s:%s' % (item.module, item.level))
        return sorted(result)
    check('module:no-new-import', imports(tree) == imports(base_tree),
          json.dumps(imports(tree)))

    # 8 - R1 / M3 1: the exact **child** channel is selected and the
    #     parent channel is proved different from it.
    controlled = find_function(tree, 'controlled_failure')
    check('m3-1:controlled-present', controlled is not None, '')
    if controlled is not None:
        custody = [item for item in ast.walk(controlled)
                   if isinstance(item, ast.FunctionDef)
                   and item.name == 'controlled_custody_channel']
        check('m3-1:custody-channel-lookup', len(custody) == 1, '')
        if custody:
            body = ast.unparse(custody[0])
            check('m3-1:the-child-is-named',
                  "'controlled:channel'" in body,
                  'the name of the child is not used')
            check('m3-1:the-parent-is-excluded',
                  'controlled_parent_channel' in body,
                  'the parent channel is not excluded')
            check('m3-1:not-the-first-channel',
                  "entry['kind'] == 'channel'" not in body
                  or "entry['name'] == 'controlled:channel'" in body,
                  'the lookup may still select the first channel')
        # the identity of the child is compared with the exact object of
        # the owner of the target of the thread.
        compares = [item for item in ast.walk(controlled)
                    if isinstance(item, ast.Compare)
                    and isinstance(item.left, ast.Name)
                    and item.left.id == 'owner'
                    and any(isinstance(op, ast.IsNot) for op in item.ops)]
        check('m3-1:exact-owner-identity-check', len(compares) >= 1,
              str([item.lineno for item in compares]))
        child_compares = [item for item in ast.walk(controlled)
                          if isinstance(item, ast.Compare)
                          and isinstance(item.left, ast.Name)
                          and item.left.id == 'child'
                          and any(isinstance(op, ast.IsNot) for op in item.ops)]
        check('m3-1:the-child-differs-from-the-parent',
              len(child_compares) >= 1,
              str([item.lineno for item in child_compares]))
        # the parent channel is captured before the child is constructed
        parents = parent_map(controlled)
        captures = [item for item in ast.walk(controlled)
                    if isinstance(item, ast.Assign)
                    and any(isinstance(target, ast.Name)
                            and target.id == 'controlled_parent_channel'
                            for target in item.targets)]
        constructions = [item for item in ast.walk(controlled)
                         if isinstance(item, ast.Call)
                         and isinstance(item.func, ast.Attribute)
                         and item.func.attr == 'StreamChannel']
        check('m3-1:the-parent-channel-is-captured', len(captures) >= 1, '')
        if captures and constructions:
            check('m3-1:the-parent-is-captured-before-the-child',
                  captures[0].lineno < constructions[0].lineno,
                  '%d < %d' % (captures[0].lineno, constructions[0].lineno))
        # the original start really takes effect and the exact failure is
        # raised **after** it and **inside** the constructor.
        raises = [item for item in ast.walk(controlled)
                  if isinstance(item, ast.Raise)
                  and isinstance(item.exc, ast.Call)
                  and isinstance(item.exc.func, ast.Name)
                  and item.exc.func.id == '_R07ConstructorFailure']
        starts = [item for item in ast.walk(controlled)
                  if isinstance(item, ast.Call)
                  and isinstance(item.func, ast.Name)
                  and item.func.id == 'original_thread_start']
        check('m3-1:the-exact-constructor-failure', len(raises) == 1,
              str(len(raises)))
        if raises and starts:
            before_raise = [item for item in starts
                            if item.lineno < raises[0].lineno]
            check('m3-1:the-original-start-takes-effect',
                  len(before_raise) >= 1,
                  str([item.lineno for item in before_raise]))

    # 9 - R2 / M2 1: every terminal transition of the ledger follows a
    #     successful terminal write.
    transitions = []
    for item in ast.walk(tree):
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute) \
                and item.func.attr in ('fail', 'pass_', 'finish') \
                and isinstance(item.func.value, ast.Name) \
                and item.func.value.id == 'ledger':
            transitions.append(item)
    check('m2-1:the-terminal-transitions-exist', len(transitions) >= 10,
          str(len(transitions)))
    parents = parent_map(tree)
    unguarded = []
    for item in transitions:
        ok, detail = write_guarded(item, parents)
        if not ok:
            unguarded.append('%s@%s (%s)'
                             % (ast.unparse(item), item.lineno, detail))
    check('m2-1:every-terminal-transition-is-write-guarded',
          not unguarded, json.dumps(unguarded))
    # the failed write of a terminal document leaves the name ATTEMPTED
    finishes = [item for item in transitions
                if isinstance(item.func, ast.Attribute)
                and item.func.attr == 'finish']
    check('m2-1:the-not-run-transition-exists', len(finishes) >= 1, '')

    # 10 - R3 / M3 4: the cleanup owning try of the coordination contains
    #      the construction of the endpoint and the start of the reader.
    r10 = find_function(tree,
                        'test_n10_r10_the_outcome_of_the_generation_wins_'
                        'over_the_cancellation')
    check('m3-4:r10-test-present', r10 is not None, '')
    if r10 is not None:
        parents = parent_map(r10)
        endpoints = [item for item in ast.walk(r10)
                     if isinstance(item, ast.Call)
                     and isinstance(item.func, ast.Name)
                     and item.func.id == '_WindowsPipeEndpoint'
                     and 'coordination' in ast.unparse(item)]
        starts = [item for item in ast.walk(r10)
                  if isinstance(item, ast.Call)
                  and isinstance(item.func, ast.Attribute)
                  and item.func.attr == 'Thread']
        check('m3-4:the-coordination-endpoint-found', len(endpoints) == 1,
              str(len(endpoints)))
        check('m3-4:the-reader-thread-found', len(starts) == 1,
              str(len(starts)))
        if endpoints and starts:
            holder_endpoint = enclosing_try(endpoints[0], parents)
            holder_start = enclosing_try(starts[0], parents)
            check('m3-4:the-endpoint-is-inside-the-cleanup-try',
                  holder_endpoint is not None
                  and holder_endpoint is holder_start,
                  'the endpoint is in %s and the start in %s'
                  % (getattr(holder_endpoint, 'lineno', None),
                     getattr(holder_start, 'lineno', None)))
            if holder_endpoint is not None:
                final = ast.Module(body=holder_endpoint.finalbody,
                                   type_ignores=[])
                closes = [item for item in ast.walk(final)
                          if isinstance(item, ast.Call)
                          and isinstance(item.func, ast.Attribute)
                          and item.func.attr == 'close']
                check('m3-4:the-cleanup-try-closes-the-endpoint',
                      len(closes) >= 1, str(len(closes)))
                check('m3-4:the-cleanup-try-drains-the-owners',
                      bool(calls(final, '_drain_owners')), '')

    # 11 - M2 2: the durable facts of the barrier survive every rewrite
    #      and the final document of the phase.
    phase = find_function(tree, '_m09_timeout_phase')
    check('m2-2:the-phase-present', phase is not None, '')
    if phase is not None:
        for key in ('barrier_persisted', 'barrier_write_error'):
            check('m2-2:the-final-document-carries-%s' % key,
                  key in ast.unparse(phase), '')
        check('m2-2:the-final-document-carries-the-identity',
              'barrier_observed_object_is_original' in ast.unparse(phase), '')
        check('m2-2:the-barrier-facts-are-built-once',
              'barrier_facts' in ast.unparse(phase), '')

    # 12 - M2 3: the terminal document of the earlier work is written
    #      after its cleanup.
    if r10 is not None:
        parents = parent_map(r10)
        chains = calls(r10, '_chain')
        check('m2-3:the-early-chain-found', len(chains) == 1, str(len(chains)))
        early_writes = [item for item in ast.walk(r10)
                        if isinstance(item, ast.Call)
                        and isinstance(item.func, ast.Name)
                        and item.func.id == 'write_phase'
                        and 'r10-early-salvage' in ast.unparse(item)]
        check('m2-3:the-early-verdict-is-written', len(early_writes) == 1,
              str(len(early_writes)))
        if chains and early_writes:
            holder = enclosing_try(chains[0], parents)
            check('m2-3:the-early-verdict-is-after-the-cleanup',
                  holder is not None
                  and in_finalbody(early_writes[0], holder, parents),
                  'the try is %s' % (getattr(holder, 'lineno', None),))
        coord_writes = [item for item in ast.walk(r10)
                        if isinstance(item, ast.Call)
                        and isinstance(item.func, ast.Name)
                        and item.func.id == 'write_phase'
                        and "'r10-coordination'" in ast.unparse(item)]
        check('m2-3:the-coordination-documents-exist',
              len(coord_writes) >= 2, str(len(coord_writes)))

    # 13 - M2 4: the quiescence is a proof failure and it is enforced by
    #      every caller.
    drain = find_function(tree, '_drain_owners')
    check('m2-4:the-drain-present', drain is not None, '')
    if drain is not None:
        text = ast.unparse(drain)
        check('m2-4:the-drain-fails-on-a-nonquiescent-round',
              'not quiescent' in text, '')
    enforced = 0
    for label in CALLERS:
        function = find_function(tree, label)
        if function is None:
            check('m2-4:%s-present' % label, False, '')
            continue
        found = quiescence_checks(function)
        check('m2-4:%s-requires-the-quiescence' % label, len(found) >= 1,
              str(len(found)))
        enforced += len(found)
    check('m2-4:the-quiescence-is-enforced-everywhere', enforced >= 6,
          str(enforced))

    # 14 - M3 2: the traversal of the owners, the reads of the drain and
    #      the release of the gates are best effort.
    registry = find_function(tree, '_registry_owners')
    check('m3-2:the-registry-present', registry is not None, '')
    if registry is not None:
        guards = [item for item in ast.walk(registry)
                  if isinstance(item, ast.ExceptHandler)
                  and 'BaseException' in handler_names(item)]
        check('m3-2:the-traversal-is-guarded-per-query', len(guards) >= 5,
              str(len(guards)))
        text = ast.unparse(registry)
        check('m3-2:the-observed-threads-are-retained',
              'observed' in text, '')
        check('m3-2:the-owners-are-never-emptied',
              'owners, hints = [], {}' not in text, '')
    if drain is not None:
        parents = parent_map(drain)
        reads = [item for item in ast.walk(drain)
                 if isinstance(item, ast.Call)
                 and isinstance(item.func, ast.Attribute)
                 and item.func.attr in ('generation', 'pending_starts')]
        readers = calls(drain, 'read_generation') + calls(drain,
                                                           'read_pending')
        check('m3-2:the-reads-of-the-drain-exist',
              len(reads) >= 2 and len(readers) >= 4,
              '%d reads, %d guarded readers' % (len(reads), len(readers)))
        unguarded_reads = [item.lineno for item in reads
                           if enclosing_try(item, parents) is None]
        check('m3-2:the-reads-of-the-drain-are-guarded',
              not unguarded_reads, json.dumps(unguarded_reads))
        releases = [item for item in ast.walk(drain)
                    if isinstance(item, ast.Call)
                    and isinstance(item.func, ast.Name)
                    and item.func.id == 'action']
        check('m3-2:the-release-is-one-action-per-gate',
              len(releases) >= 1, str(len(releases)))

    # 15 - M3 3: the exact cancellation is rethrown before the proof
    #      assertion by every caller.
    for label in CALLERS:
        function = find_function(tree, label)
        if function is None:
            continue
        interrupts = interrupt_raises(function)
        check('m3-3:%s-rethrows-the-exact-cancellation' % label,
              len(interrupts) >= 1, str(len(interrupts)))
        parents = parent_map(function)
        problems = []
        ordered = False
        for block in all_blocks(function):
            direct = shallow_raises(block)
            block_interrupts = [item for item in direct
                                if isinstance(item.exc, ast.Subscript)
                                and isinstance(item.exc.slice, ast.Constant)
                                and item.exc.slice.value == 0]
            block_assertions = [item for item in direct
                                if isinstance(item.exc, ast.Call)
                                and isinstance(item.exc.func, ast.Name)
                                and item.exc.func.id == 'AssertionError']
            if block_interrupts and block_assertions:
                ordered = True
                if block_interrupts[0].lineno > block_assertions[0].lineno:
                    problems.append('the assertion of the block at %s '
                                    'precedes the rethrow'
                                    % (block_assertions[0].lineno,))
        check('m3-3:%s-the-cancellation-wins' % label,
              ordered and not problems, json.dumps(problems))

    # 16 - M3 5: the close of every child endpoint of the round of the
    #      parent is BaseException aware.
    r07 = find_function(tree,
                        'test_n10_r07_the_context_of_the_round_reaches_'
                        'every_layer')
    check('m3-5:the-r07-present', r07 is not None, '')
    guarded_closes = 0
    plain_closes = 0
    if r07 is not None:
        for item in ast.walk(r07):
            if isinstance(item, ast.Try) and item.handlers:
                body = ast.unparse(ast.Module(body=item.body,
                                              type_ignores=[]))
                if '.close()' in body:
                    names = set()
                    for handler in item.handlers:
                        names.update(handler_names(handler))
                    if 'BaseException' in names:
                        guarded_closes += 1
                    elif 'Exception' in names:
                        plain_closes += 1
    check('m3-5:the-closes-are-base-exception-aware', guarded_closes >= 3,
          str(guarded_closes))
    check('m3-5:no-close-is-exception-only', plain_closes == 0,
          str(plain_closes))

    # 17 - the evidence directory of this correction
    check('evidence:directory',
          'implementation-native-custody-correction-19' in source, '')

    report = {
        'kind': 'lvw.s3-native-custody-correction19-static-checks/1',
        'checks': checks, 'failed': failed,
        'ok': not failed,
        'total': len(checks),
        'assertion_equivalence': {
            'baseline_total': sum(base_asserts.values()),
            'candidate_total': sum(now_asserts.values()),
            'removed': removed,
            'added': added,
            'note': 'No predicate of the baseline is removed.  The added '
                    'predicates are the checks of the residual defects of '
                    'the independent review of the correction 18; they '
                    'never replace an oracle of the baseline.',
        },
    }
    print(json.dumps(report, indent=1, sort_keys=True))
    return 0 if not failed else 1


if __name__ == '__main__':
    if len(sys.argv) != 3:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], sys.argv[2]))
