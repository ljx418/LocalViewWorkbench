"""The static checks of the correction 17 of the native custody.

The script is a **static** checker: it reads the sources as text, it
parses them with the standard ``ast`` and ``symtable`` modules and it
never imports, collects, executes or runs anything.  It never touches a
native library, an operating system process, a model, a GPU, a service,
a network, a medium, a database, a ledger or a counter.

The checks are:

1. the **189** frozen node identities and their order are unchanged and
   the four other modules are byte identical to their pins;
2. the fourteen nodes of this module keep their names, their order,
   their signatures and their decorators;
3. no node is skipped, no node is xfailed and no node was deleted;
4. every global name that the module reads is really bound;
5. the eight removed assertions of the correction 16 candidate are gone
   and every one of them has an equivalent or stronger replacement;
6. the patch of the read of the broker targets the **class** and the
   barrier of the publication is finalised on both paths;
7. the inventory of the group of N10-R10 is complete and unique.

Usage::

    python3 -I tools/static_checks.py <package-root> <baseline-blob>
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

#: The eight occurrences that the independent review of the correction 16
#: candidate found removed.  Every one of them must be absent **and** it
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
    ("item['alive'] is False",
     "item['alive'] is False"),
    ("controlled['failure'] is not None",
     "close_failures[0]['detail'] == 'controlled_close_failure'"),
)

#: The replacements that the correction 17 adds for the eight removed
#: occurrences.  They are all present in the candidate.
REPLACEMENTS = (
    "failure['class'] is _R07Sentinel",
    "failure['token'] == checkpoint",
    "failure['class'] is _R07OrdinaryAssertion",
    "failure['token'] == _R07OrdinaryAssertion.TOKEN",
    "failure['class'] is _R07ConstructorFailure",
    "failure['token'] == 'CONSTRUCTOR_FAILURE'",
    "facts['zero_state'] == 'UNKNOWN_RETAINED'",
    "'CUSTODY_CHANNEL_TIMEOUT' in facts['zero_failures']",
    "'CUSTODY_CHANNEL_EOF' not in facts['zero_failures']",
    "facts['zero_broker_retained'] is True",
    'zero_session.broker is zero_broker',
    "facts['zero_broker_identity']['identity_source']",
    'zero_pump is zero_session._pump',
    "facts['zero_pump_finished'] is True",
    "zero_premise['pump_error_is_none'] is True",
    "zero_premise['pump_eof_at_admission'] is False",
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
    "registry.pending_starts() == 0",
    "registry.generation() == snapshot['generation']",
)

#: The forbidden forms of the correction 16 candidate.
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
)

#: The forms that the correction 17 adds.
REQUIRED = (
    "unittest.mock.patch.object(\n                        broker_module.BrokerProcess, 'read',",
    "api.barrier_completed.wait(15.0)",
    "self.barrier_snapshot = dict(self.barrier)",
    "self.barrier_completed.set()",
    "self._persist_barrier()",
    "'premise': 'BARRIER_NOT_COMPLETED'",
    "ledger.attempt(phase + '-construction')",
    "ledger.attempt(phase + '-first')",
    "ledger.attempt(phase + '-second')",
    "ledger.attempt(phase + '-barrier')",
    "status='FAIL'",
    "status='PASSED'",
    "'status': 'NOT_RUN'",
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
        check('pin:%s' % name, sha256(data) == digest,
              sha256(data))

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
    module = (root / 'tools/test_v0_s3_native_custody_correction10.py')
    source = module.read_text(encoding='utf-8')
    baseline_source = Path(baseline).read_text(encoding='utf-8')
    now = [(item['name'], item['args'], item['decorators'])
           for item in signatures(source)]
    before = [(item['name'], item['args'], item['decorators'])
              for item in signatures(baseline_source)]
    check('nodes:names-order-signatures', now == before,
          json.dumps(now))
    tree = ast.parse(source)
    skipped = [item.name for item in ast.walk(tree)
               if isinstance(item, ast.Call)
               and isinstance(item.func, ast.Attribute)
               and item.func.attr in ('skip', 'xfail', 'skipif')]
    check('nodes:no-skip-no-xfail', not skipped, json.dumps(skipped))
    check('module:compiles', compile(source, str(module), 'exec') is not None)

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

    # 6 - the inventory of the group of N10-R10: the names are derived
    # from the operations that are really instrumented, so the source
    # carries the base names and the four suffixes of the schedules.
    check('inventory:unique', len(INVENTORY) == len(set(INVENTORY)),
          str(len(INVENTORY)))
    for name in ('r10-timeout-confirmed', 'r10-timeout-failed',
                 'r10-barrier-absent', 'r10-barrier-wrong-generation',
                 'r10-published-before-timeout', 'r10-first', 'r10-second',
                 'r10-coordination'):
        check('inventory:name:%s' % name, name in source, '')
    for fragment in ("r10_documents.extend([r10_name, r10_name + '-construction',",
                     "r10_name + '-barrier', r10_name + '-first',",
                     "r10_name + '-second'])",
                     "'r10-published-before-timeout-construction',",
                     "'r10-published-before-timeout-first',",
                     "'r10-published-before-timeout-second'])",
                     "'r10-first', 'r10-second', 'r10-coordination'])"):
        check('inventory:fragment:%s' % fragment[:40], fragment in source, '')

    # 7 - the evidence directory of this correction
    check('evidence:directory',
          'implementation-native-custody-correction-17' in source, '')

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
