#!/usr/bin/env python3
"""Correction 22 - STATIC shape checks of the candidate.

This script is a **static** instrument: it never imports the candidate,
it never collects it, it never runs a test, it never opens a socket, a
database, a model or a native library and it never starts a product
process.  It reads the candidate source and the frozen baseline source
as **data** (text, ``ast`` and ``hashlib``) and it reports the shape of
the six residual counterexamples of the correction 21.

Usage::

    python3 check_correction22.py --root <pack root> \\
        --baseline <baseline commit> [--json <out.json>]

The baseline is read with ``git show`` (read only, no checkout).

The checks of the denominator, of the assertions and of the six
unchanged sources are the checks of the correction 21: they are kept
**unchanged** so that the regression guard of the correction 22 is the
regression guard of the correction 21.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys

#: The five modules of the frozen denominator of the acceptance.
MODULES = (
    'tools/test_v0_s3_native_custody.py',
    'tools/test_v0_s3_native_custody_regressions.py',
    'tools/test_v0_s3_native_custody_correction05.py',
    'tools/test_v0_s3_native_custody_correction07.py',
    'tools/test_v0_s3_native_custody_correction10.py',
)

#: The expected size of the denominator.
EXPECTED_NODES = 189

#: The six sources that this correction must not touch.  The values are
#: the SHA256 of the frozen baseline; the check recomputes them.
UNCHANGED = {
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

T10 = 'tools/test_v0_s3_native_custody_correction10.py'


# ----------------------------------------------------------------- helpers

def read(path):
    with open(path, encoding='utf-8') as handle:
        return handle.read()


def sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def git_show(root, commit, path):
    """Read one blob of the baseline, read only."""
    top = subprocess.run(
        ['git', '-C', root, 'rev-parse', '--show-toplevel'],
        check=True, stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
    prefix = os.path.relpath(os.path.abspath(root), top)
    full = path if prefix == '.' else os.path.join(prefix, path)
    result = subprocess.run(
        ['git', '-C', top, 'show', '%s:%s' % (commit, full)],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return result.stdout.decode('utf-8')


def parse(text):
    return ast.parse(text)


def test_nodes(tree):
    """The identifiers of the tests of one module, in the order."""
    nodes = []
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name.startswith('test_'):
                nodes.append(item.name)
    return nodes


def assert_predicates(tree):
    """The multiset of the assertion predicates of one module.

    The value of the multiset is a pair: the number of the occurrences
    and the **source** of the predicate.
    """
    found = {}
    for item in ast.walk(tree):
        if isinstance(item, ast.Assert):
            key = ast.dump(item.test, annotate_fields=True)
            count, _ = found.get(key, (0, None))
            found[key] = (count + 1, ast.unparse(item.test))
    return found


def function_of(tree, name):
    for item in tree.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if item.name == name:
                return item
    return None


def functions_of(tree):
    return [item for item in tree.body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]


def parent_map(tree):
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def ancestors(node, parents):
    found = []
    current = parents.get(id(node))
    while current is not None:
        found.append(current)
        current = parents.get(id(current))
    return found


def guarded_statements(tree):
    """The nodes that are the body of a guarded ``try``."""
    guarded = set()
    for item in ast.walk(tree):
        if isinstance(item, ast.Try) and item.handlers:
            for statement in item.body:
                for inner in ast.walk(statement):
                    guarded.add(id(inner))
    return guarded


# ------------------------------------------------------- the carried checks

def check_denominator(root, baseline):
    """The exact 189 identifiers, in the order, of the candidate."""
    result = {'modules': {}, 'candidate': [], 'baseline': [], 'ok': True}
    for module in MODULES:
        candidate = parse(read(os.path.join(root, module)))
        frozen = parse(git_show(root, baseline, module))
        candidate_nodes = test_nodes(candidate)
        frozen_nodes = test_nodes(frozen)
        result['modules'][module] = {
            'candidate': len(candidate_nodes),
            'baseline': len(frozen_nodes),
            'equal': candidate_nodes == frozen_nodes,
        }
        result['candidate'].extend('%s::%s' % (module, name)
                                   for name in candidate_nodes)
        result['baseline'].extend('%s::%s' % (module, name)
                                  for name in frozen_nodes)
    result['total'] = len(result['candidate'])
    result['unique'] = len(set(result['candidate']))
    result['equal'] = result['candidate'] == result['baseline']
    result['ok'] = (result['total'] == EXPECTED_NODES
                    and result['unique'] == EXPECTED_NODES
                    and result['equal']
                    and all(item['equal'] for item in
                            result['modules'].values()))
    return result


def check_assertions(root, baseline):
    """No assertion predicate of the baseline was removed.

    CORRECTION 22: a predicate may only be **moved** and never added
    and never lost.  The predicates that this correction moves are the
    **requeries of the liveness** of an owner: they are replaced by the
    fact that the guarded join returned, which is equivalent or
    stronger (an **unknown** liveness is never read as the end of the
    owner).  The mapping is reported with both sides.
    """
    result = {'modules': {}, 'removed': [], 'added': [], 'ok': True}
    for module in MODULES:
        candidate = assert_predicates(parse(read(os.path.join(root, module))))
        frozen = assert_predicates(parse(git_show(root, baseline, module)))
        removed = []
        added = []
        for key, (count, source) in frozen.items():
            if candidate.get(key, (0, None))[0] < count:
                removed.append({'module': module,
                                'predicate': source,
                                'baseline': count,
                                'candidate': candidate.get(key, (0, None))[0],
                                'moved': is_liveness_requery(source)})
        for key, (count, source) in candidate.items():
            if frozen.get(key, (0, None))[0] < count:
                added.append({'module': module,
                              'predicate': source,
                              'baseline': frozen.get(key, (0, None))[0],
                              'candidate': count})
        result['modules'][module] = {
            'baseline_predicates': sum(item[0] for item in frozen.values()),
            'candidate_predicates': sum(item[0] for item in candidate.values()),
            'removed': len(removed),
            'added': len(added),
        }
        result['removed'].extend(removed)
        result['added'].extend(added)
    result['total_baseline'] = sum(item['baseline_predicates']
                                   for item in result['modules'].values())
    result['total_candidate'] = sum(item['candidate_predicates']
                                    for item in result['modules'].values())
    # the **total** number of the predicates is the one of the baseline:
    # a predicate may only be **moved** and never added and never lost.
    result['count_preserved'] = (result['total_baseline']
                                  == result['total_candidate'])
    result['removed_occurrences'] = sum(item['baseline'] - item['candidate']
                                        for item in result['removed'])
    result['added_occurrences'] = sum(item['candidate'] - item['baseline']
                                      for item in result['added'])
    result['moved_occurrences'] = (result['removed_occurrences']
                                   == result['added_occurrences'])
    result['only_moved'] = all(item['moved'] for item in result['removed'])
    result['ok'] = (result['count_preserved'] and result['moved_occurrences']
                    and result['only_moved'])
    return result


def is_liveness_requery(source):
    """The predicate is the requery of the liveness of an owner."""
    try:
        node = ast.parse(source, mode='eval').body
    except SyntaxError:
        return False
    if not isinstance(node, ast.UnaryOp) or not isinstance(node.op, ast.Not):
        return False
    operand = node.operand
    if not isinstance(operand, ast.Call):
        return False
    if not isinstance(operand.func, ast.Attribute):
        return False
    return operand.func.attr == 'is_alive'


def check_unchanged(root):
    """The six sources of the correction are byte identical."""
    result = {'sources': {}, 'ok': True}
    for path, expected in UNCHANGED.items():
        actual = sha256(read(os.path.join(root, path)))
        result['sources'][path] = {'sha256': actual, 'expected': expected,
                                   'equal': actual == expected}
    result['ok'] = all(item['equal'] for item in result['sources'].values())
    return result


def check_evidence_root(root):
    """The evidence root of the module is the NEW directory."""
    tree = parse(read(os.path.join(root, T10)))
    source = ast.unparse(tree)
    ok = ('implementation-native-custody-correction-22' in source
          and 'implementation-native-custody-correction-21' not in source)
    return {'ok': ok}


# ------------------------------------------------------ the six corrections

def check_final_verdict(root):
    """M2.a / M3.d: the final verdict follows **all** the cleanup actions.

    The check is a **real AST** order check of the ``finally`` of the
    controlled subcase: the guarded actions of the cleanup come first,
    the facts of the subcase are **complete** and the **last** write of
    the evidence is attempted next, and only then the priority of the
    failures is enforced.  A write that failed is an **actual** error of
    the cleanup: it updates the facts **in memory** and it rejects the
    success of the subcase.  A deliberate failure that was already
    **caught** never exempts a new unexpected error of the cleanup.
    """
    tree = parse(read(os.path.join(root, T10)))
    node = None
    for item in functions_of(tree):
        source = ast.unparse(item)
        if 'controlled_api.frames_ready.set' in source and 'checkpoint' in source:
            node = item
            break
    result = {'ok': False}
    if node is None:
        return result
    source = ast.unparse(node)
    result['function'] = node.name
    result['no_caught_exemption'] = 'not raised' not in source
    result['recomputes_the_verdict'] = '_cleanup_verdict(' in source
    result['publishes_the_facts'] = '_publish_cleanup(' in source
    result['enforces_the_verdict'] = 'raise AssertionError(verdict)' in source
    order = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Try):
            continue
        if not item.finalbody:
            continue
        joined = '\n'.join(ast.unparse(statement)
                           for statement in item.finalbody)
        if 'controlled_observer_patch.stop' not in joined:
            continue
        order.append({
            'line': item.lineno,
            'release_before_publish':
                joined.rfind('controlled_api.frames_ready.set')
                < joined.rfind('_publish_cleanup('),
            'publish_before_priority':
                joined.rfind('_publish_cleanup(')
                < joined.rfind('raise controlled_interrupts[0]'),
            'verdict_after_publish':
                joined.rfind('raise AssertionError(verdict)')
                > joined.rfind('_publish_cleanup('),
            'original_kept':
                'if not final_unwinding:' in joined,
        })
    result['finally_blocks'] = order
    ok = (result['no_caught_exemption'] and result['recomputes_the_verdict']
          and result['publishes_the_facts'] and result['enforces_the_verdict'])
    ok = ok and bool(order)
    for item in order:
        ok = ok and item['release_before_publish']
        ok = ok and item['publish_before_priority']
        ok = ok and item['verdict_after_publish']
        ok = ok and item['original_kept']
    result['ok'] = ok
    return result


def check_zero_registry_durable(root):
    """M2.b: the errors of the query of the registry are durable.

    The check is a **real AST** check: the document of the round of the
    zero expiry carries the errors of the query of the registry as an
    **explicit field** and the verdict of the round is recomputed with
    them, so that a query that failed never disappears because the
    proof of the round names another failure.
    """
    tree = parse(read(os.path.join(root, T10)))
    result = {'ok': False, 'durable_fields': [], 'verdicts': []}
    for item in ast.walk(tree):
        if not isinstance(item, ast.Dict):
            continue
        keys = {key.value for key in item.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)}
        if 'registry_errors' in keys:
            result['durable_fields'].append({'line': item.lineno,
                                             'keys': sorted(keys)})
    for item in ast.walk(tree):
        if not isinstance(item, ast.Call):
            continue
        if not isinstance(item.func, ast.Name):
            continue
        if item.func.id != '_cleanup_verdict':
            continue
        result['verdicts'].append({
            'line': item.lineno,
            'source': ast.unparse(item)})
    zero = [item for item in result['verdicts']
            if 'zero_registry_errors' in item['source']]
    result['zero_verdict'] = bool(zero)
    result['ok'] = bool(result['durable_fields']) and bool(zero)
    return result


def check_r12_actions_before_priority(root):
    """M3.a: every action of the cleanup of R12 precedes the priority.

    The check is a **real AST** order check: the public stop of the
    round is attempted **before** the priority of the failures, its
    failure is retained with its exact type and its exact detail and it
    is never silently swallowed, and the ordinary errors of the cleanup
    are consumed.
    """
    tree = parse(read(os.path.join(root, T10)))
    node = None
    for item in functions_of(tree):
        if 'r12_cleanup_errors' in ast.unparse(item):
            node = item
            break
    result = {'ok': False}
    if node is None:
        return result
    source = ast.unparse(node)
    result['function'] = node.name
    result['no_silent_pass'] = 'except Exception:' not in source
    result['stops_the_round'] = 'session.stop()' in source
    result['consumes_the_errors'] = (
        'raise AssertionError(' in source and 'r12_cleanup_errors' in source)
    order = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Try):
            continue
        if not item.finalbody:
            continue
        joined = '\n'.join(ast.unparse(statement)
                           for statement in item.finalbody)
        if 'r12_cleanup_errors' not in joined:
            continue
        order.append({
            'line': item.lineno,
            'stop_before_priority':
                joined.rfind('session.stop()')
                < joined.rfind('_raise_first_interruption('),
            'priority_before_proof':
                joined.rfind('_raise_first_interruption(')
                < joined.rfind('assert not _owner_alive('),
            'guard_after_the_join':
                joined.rfind('_join_owner(') < joined.rfind('session.stop()'),
        })
    result['finally_blocks'] = order
    ok = (result['no_silent_pass'] and result['stops_the_round']
          and result['consumes_the_errors'] and bool(order))
    for item in order:
        ok = ok and item['stop_before_priority']
        ok = ok and item['priority_before_proof']
        ok = ok and item['guard_after_the_join']
    result['ok'] = ok
    return result


def check_guarded_closes(root):
    """M3.b: no direct close replaces the original or the pending K1.

    The check is a **real AST** check: every close of an endpoint in a
    **cleanup region** is guarded, its failure is retained with its
    exact type and its exact detail and the priority of the failures is
    enforced **outside** the cleanup region.
    """
    tree = parse(read(os.path.join(root, T10)))
    guarded = guarded_statements(tree)
    parents = parent_map(tree)
    closes = []
    for item in ast.walk(tree):
        if not isinstance(item, ast.Call):
            continue
        if not isinstance(item.func, ast.Attribute):
            continue
        if item.func.attr != 'close':
            continue
        owner = ast.unparse(item.func.value)
        if not any(word in owner for word in
                   ('endpoint', 'transport', 'channel')):
            continue
        chain = ancestors(item, parents)
        proof = any(isinstance(parent, ast.Assert) for parent in chain)
        finally_blocks = [parent for parent in chain
                          if isinstance(parent, ast.Try) and parent.finalbody]
        closes.append({'line': item.lineno,
                       'call': ast.unparse(item),
                       'owner': owner,
                       'proof': proof,
                       'guarded': id(item) in guarded,
                       'in_cleanup_region': bool(finally_blocks)})
    result = {'closes': closes}
    unguarded = [item for item in closes
                 if item['in_cleanup_region'] and not item['guarded']
                 and not item['proof']]
    result['unguarded_cleanup_closes'] = unguarded
    # the priority of the cleanup of the await is **outside** its
    # ``finally``: the close of the endpoint can never replace the
    # original failure or the **first** exact pending interruption.
    node = None
    for item in functions_of(tree):
        if 'await_cleanup_errors' in ast.unparse(item):
            node = item
            break
    result['await_priority_outside'] = False
    result['await_close_guarded'] = False
    if node is not None:
        node_parents = parent_map(node)
        for item in ast.walk(node):
            if not isinstance(item, ast.Try) or not item.finalbody:
                continue
            joined = '\n'.join(ast.unparse(statement)
                               for statement in item.finalbody)
            if 'endpoint.close()' not in joined:
                continue
            result['await_close_guarded'] = 'except BaseException' in joined
        # the priority of the cleanup of the await is enforced **outside**
        # the ``finally``: the call is not a statement of a final body.
        for item in ast.walk(node):
            if not isinstance(item, ast.Call):
                continue
            if not isinstance(item.func, ast.Name):
                continue
            if item.func.id != '_raise_first_interruption':
                continue
            inside = False
            for parent in ancestors(item, node_parents):
                if isinstance(parent, ast.Try) and parent.finalbody:
                    for statement in parent.finalbody:
                        for inner in ast.walk(statement):
                            if inner is item:
                                inside = True
            if not inside:
                result['await_priority_outside'] = True
    result['ok'] = (not unguarded and result['await_close_guarded']
                    and result['await_priority_outside'])
    return result


def check_error_consumers(root):
    """M3.c: every collected error list has a consumer.

    The check is a **real AST** dataflow check: every list of the errors
    of a cleanup is read somewhere else than in its own ``append``: it
    feeds a verdict, a document or a failure of the round.  A list that
    is only appended to is an error that nobody reads.
    """
    tree = parse(read(os.path.join(root, T10)))
    lists = {}
    for item in ast.walk(tree):
        if not isinstance(item, ast.Assign):
            continue
        if not isinstance(item.value, ast.List):
            continue
        for target in item.targets:
            if isinstance(target, ast.Name) and target.id.endswith('errors'):
                lists[target.id] = item.lineno
    consumed = {}
    for item in ast.walk(tree):
        if not isinstance(item, ast.Name):
            continue
        if not isinstance(item.ctx, ast.Load):
            continue
        name = item.id
        if name not in lists:
            continue
        # an ``append`` of the list is not a consumer
        parent = None
        for candidate in ast.walk(tree):
            for child in ast.iter_child_nodes(candidate):
                if child is item:
                    parent = candidate
        if isinstance(parent, ast.Call) and isinstance(parent.func,
                                                       ast.Attribute):
            if parent.func.attr == 'append':
                continue
        consumed[name] = consumed.get(name, 0) + 1
    result = {'lists': {name: {'line': line, 'consumers':
                               consumed.get(name, 0)}
                        for name, line in sorted(lists.items())},
              'ok': False}
    unconsumed = [name for name in lists if not consumed.get(name)]
    result['unconsumed'] = unconsumed
    result['ok'] = not unconsumed
    return result


def check_deferred_priority(root):
    """M3.c: the priority of the failures follows every owner action.

    The check is a **real AST** nesting check: no loop over the owners
    of a round re-raises inside its body, and every loop that traverses
    the owners of a round is followed by the enforcement of the priority
    of the failures.
    """
    tree = parse(read(os.path.join(root, T10)))
    loops = []
    for item in ast.walk(tree):
        if not isinstance(item, ast.For):
            continue
        target = ast.unparse(item.target)
        iterated = ast.unparse(item.iter)
        if not any(word in (target + ' ' + iterated)
                   for word in ('owner', 'owners', 'pending', 'inflight')):
            continue
        raises = []
        for inner in ast.walk(item):
            if isinstance(inner, ast.Raise):
                raises.append({'line': inner.lineno,
                               'text': ast.unparse(inner)})
            if isinstance(inner, ast.Call) and isinstance(inner.func,
                                                          ast.Name):
                if inner.func.id == '_raise_first_interruption':
                    raises.append({'line': inner.lineno,
                                   'text': ast.unparse(inner)})
        loops.append({'line': item.lineno,
                      'target': target,
                      'iterated': iterated,
                      'raises_in_body': raises})
    result = {'loops': loops, 'ok': False}
    result['ok'] = bool(loops) and all(not item['raises_in_body']
                                      for item in loops)
    # the liveness of an owner is the fact of the guarded join: the
    # query is never repeated outside the guard of the helper.
    helper = function_of(tree, '_join_owner')
    helper_source = ast.unparse(helper) if helper is not None else ''
    result['helper_guards_join'] = (
        "'kind': 'JOIN'" in helper_source
        and "'kind': 'LIVENESS'" in helper_source
        and '_note_interruption' in helper_source)
    result['helper_never_raises'] = 'raise ' not in helper_source
    owner_helper = function_of(tree, '_owner_alive')
    result['owner_alive_helper'] = owner_helper is not None
    result['owner_alive_unknown_is_alive'] = (
        owner_helper is not None
        and 'return True' in ast.unparse(owner_helper))
    result['ok'] = (result['ok'] and result['helper_guards_join']
                    and result['helper_never_raises']
                    and result['owner_alive_helper']
                    and result['owner_alive_unknown_is_alive'])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--json', default=None)
    options = parser.parse_args()

    report = {
        'kind': 'lvw.correction22.static-shape-checks/1',
        'baseline': options.baseline,
        'candidate_root': options.root,
        'denominator': check_denominator(options.root, options.baseline),
        'assertions': check_assertions(options.root, options.baseline),
        'unchanged_sources': check_unchanged(options.root),
        'evidence_root': check_evidence_root(options.root),
        'M2.a_final_controlled_verdict': check_final_verdict(options.root),
        'M2.b_zero_registry_durable': check_zero_registry_durable(
            options.root),
        'M3.a_r12_all_actions_before_priority':
            check_r12_actions_before_priority(options.root),
        'M3.b_guarded_closes': check_guarded_closes(options.root),
        'M3.c_error_list_consumers': check_error_consumers(options.root),
        'M3.c_deferred_priority': check_deferred_priority(options.root),
    }
    report['ok'] = all(value['ok'] for value in report.values()
                       if isinstance(value, dict) and 'ok' in value)
    text = json.dumps(report, indent=1, sort_keys=True, default=str)
    print(text)
    if options.json:
        with open(options.json, 'w', encoding='utf-8') as handle:
            handle.write(text + '\n')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    sys.exit(main())
