#!/usr/bin/env python3
"""Correction 21 - STATIC shape checks of the candidate.

This script is a **static** instrument: it never imports the candidate,
it never collects it, it never runs a test, it never opens a socket, a
database, a model or a native library and it never starts a product
process.  It reads the candidate source and the frozen baseline source
as **data** (text, ``ast`` and ``hashlib``) and it reports the shape
of the five residual counterexamples of the correction 21.

Usage::

    python3 check_correction21.py --root <pack root> \\
        --baseline <baseline commit> [--json <out.json>]

The baseline is read with ``git show`` (read only, no checkout).

The checks of the denominator, of the assertions and of the six
unchanged sources are the checks of the correction 20: they are kept
**unchanged** so that the regression guard of the correction 21 is the
regression guard of the correction 20.
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
R10 = 'test_n10_r10_the_outcome_of_the_generation_wins_over_the_cancellation'

#: The keys of the complete bundle of the facts of a drain.
DRAIN_KEYS = ('drain_salvage', 'drain_all_salvage', 'drain_owner_errors',
              'drain_attempts', 'drain_errors', 'drain_quiescent',
              'drain_proof')

#: The helpers that own a guarded join by construction.
JOIN_HELPERS = ('_join_owner', '_salvage_threads')


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
    """The multiset of the assertion predicates of one module."""
    found = {}
    for item in ast.walk(tree):
        if isinstance(item, ast.Assert):
            key = ast.dump(item.test, annotate_fields=True)
            found[key] = found.get(key, 0) + 1
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


def calls_of(node, callee):
    """Every call of ``callee`` inside ``node``."""
    found = []
    for item in ast.walk(node):
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
            if item.func.id == callee:
                found.append(item)
    return found


def dict_keys(node):
    """The keys of every dictionary literal inside ``node``."""
    found = []
    for item in ast.walk(node):
        if not isinstance(item, ast.Dict):
            continue
        keys = sorted(key.value for key in item.keys
                      if isinstance(key, ast.Constant)
                      and isinstance(key.value, str))
        if keys:
            found.append({'line': item.lineno, 'keys': keys})
    return found


def unpacked_calls(tree, callee):
    """The calls of ``callee`` that are unpacked into a mapping.

    The unpack is either a ``**`` of a dictionary literal or a ``**`` of
    a call - the two forms that the module uses to merge the bundle of
    the facts of a drain into the document of a round.
    """
    found = []
    for item in ast.walk(tree):
        values = []
        if isinstance(item, ast.Dict):
            values = [value for key, value in zip(item.keys, item.values)
                      if key is None]
        elif isinstance(item, ast.Call):
            values = [keyword.value for keyword in item.keywords
                      if keyword.arg is None]
        else:
            continue
        for value in values:
            if isinstance(value, ast.Call) \
                    and isinstance(value.func, ast.Name) \
                    and value.func.id == callee:
                found.append({'line': value.lineno,
                              'argument': ast.unparse(value.args[0])
                              if value.args else None})
    return found


def is_proof(node, parents):
    """The call is the query of the **ordinary proof** of a round."""
    return any(isinstance(parent, ast.Assert) for parent in parents)


def parent_map(tree):
    """The parent of every node of ``tree``."""
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def ancestors(node, parents):
    """The ancestors of ``node``, from the closest to the farthest."""
    found = []
    current = parents.get(id(node))
    while current is not None:
        found.append(current)
        current = parents.get(id(current))
    return found


def guarded_ids(tree):
    """The nodes that are the body of a guarded ``try``."""
    guarded = set()
    helper_actions = set()
    for item in ast.walk(tree):
        if isinstance(item, ast.Try) and item.handlers:
            for statement in item.body:
                for inner in ast.walk(statement):
                    guarded.add(id(inner))
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
            if item.func.id != '_join_owner':
                continue
            for argument in item.args + [kw.value for kw in item.keywords]:
                for inner in ast.walk(argument):
                    helper_actions.add(id(inner))
    return guarded | helper_actions


def guarded_calls(tree, attributes, owners):
    """The direct calls of an owner in a **cleanup region**.

    A call is **guarded** when it is the body of a ``try`` that has a
    handler or when it is the action of the guarded helper of the
    join: the failure of the call is then retained by the module and it
    never skips the action that follows it.  A call that is the query
    of the **ordinary proof** of a round is classified apart: the proof
    runs after every cleanup action and it skips nothing.
    """
    parents = parent_map(tree)
    guarded = guarded_ids(tree)
    found = []
    for item in ast.walk(tree):
        if not isinstance(item, ast.Call):
            continue
        if not isinstance(item.func, ast.Attribute):
            continue
        if item.func.attr not in attributes:
            continue
        owner = ast.unparse(item.func.value)
        if owner not in owners:
            continue
        chain = ancestors(item, parents)
        proof = any(isinstance(parent, ast.Assert) for parent in chain)
        found.append({'line': item.lineno,
                      'call': ast.unparse(item),
                      'owner': owner,
                      'proof': proof,
                      'guarded': id(item) in guarded})
    return found


def owner_loops(tree, guarded_ids=None):
    """Every loop of the module that traverses the owners of a round."""
    guarded_ids = guarded_ids or set()
    found = []
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
        actions = []
        for inner in ast.walk(item):
            if not isinstance(inner, ast.Call):
                continue
            if not isinstance(inner.func, ast.Attribute):
                continue
            if inner.func.attr not in ('join', 'join_bounded', 'is_alive',
                                       'settle', 'stop_accepting'):
                continue
            actions.append(inner)
        source = ast.unparse(item)
        unguarded = [ast.unparse(action) for action in actions
                     if id(action) not in guarded_ids
                     and not _inside_assert(action, tree)]
        found.append({'line': item.lineno,
                      'target': target,
                      'iterated': iterated,
                      'raises_in_body': raises,
                      'guarded_join': '_join_owner' in source,
                      'owner_actions': len(actions),
                      'unguarded_actions': unguarded})
    return found


def _inside_assert(node, tree):
    """The node is the query of the **ordinary proof** of a round."""
    parents = parent_map(tree)
    for parent in ancestors(node, parents):
        if isinstance(parent, ast.Assert):
            return True
    return False


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
    """No assertion predicate of the baseline was removed."""
    result = {'modules': {}, 'removed': [], 'ok': True}
    for module in MODULES:
        candidate = assert_predicates(parse(read(os.path.join(root, module))))
        frozen = assert_predicates(parse(git_show(root, baseline, module)))
        removed = []
        for key, count in frozen.items():
            if candidate.get(key, 0) < count:
                removed.append({'module': module,
                                'predicate': ast.unparse(
                                    ast.parse(key, mode='eval').body),
                                'baseline': count,
                                'candidate': candidate.get(key, 0)})
        result['modules'][module] = {
            'baseline_predicates': sum(frozen.values()),
            'candidate_predicates': sum(candidate.values()),
            'removed': len(removed),
        }
        result['removed'].extend(removed)
    result['ok'] = not result['removed']
    return result


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
    ok = ('implementation-native-custody-correction-21' in source
          and 'implementation-native-custody-correction-20/evidence'
          not in source)
    return {'ok': ok}


# ----------------------------------------------------- the five corrections

def check_drain_facts(root):
    """M2.a: the durable evidence keeps the **whole** history of a drain.

    The check is a **dataflow** check on the real AST: the final
    document of every phase, the final verdict of the earlier work and
    the evidence of the coordination must carry the complete bundle of
    the facts of the drain - the final salvage, the salvage of every
    iteration, the per owner errors of every iteration, the attempts,
    the complete error list, the quiescence and the proof.
    """
    tree = parse(read(os.path.join(root, T10)))
    helper = function_of(tree, '_drain_facts')
    result = {'helper_keys': [], 'callers': [], 'ok': False}
    if helper is None:
        return result
    for item in dict_keys(helper):
        result['helper_keys'] = item['keys']
        break
    result['callers'] = unpacked_calls(tree, '_drain_facts')
    wanted = set(DRAIN_KEYS)
    ok = wanted.issubset(set(result['helper_keys']))
    ok = ok and len(result['callers']) >= 8
    # the drain of the round keeps the per owner errors of every
    # iteration and returns them: the errors are never reduced to the
    # proof string of the first owner that failed.
    drain = function_of(tree, '_drain_owners')
    drain_source = ast.unparse(drain) if drain is not None else ''
    result['drain_keeps_owner_errors'] = 'owner_errors' in drain_source
    ok = ok and result['drain_keeps_owner_errors']
    # the shared store of the group and the outer recovery read the
    # **same** facts: the recovery reuses the store and never writes a
    # generic FAIL over an empty document.
    node = function_of(tree, R10)
    recovery = []
    for item in ast.walk(node):
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == 'recovered':
                    recovery.append(ast.unparse(item.value))
    result['recovery_documents'] = recovery
    ok = ok and any('r10_raw.get' in text for text in recovery)
    result['ok'] = ok
    return result


def check_barrier_persistence(root):
    """M2.b: the terminal barrier document keeps the persistence facts.

    The check is a **real AST** check of the document of the incomplete
    barrier branch: it must name the **actual** persistence of the
    barrier, the **actual** error of its persistence and the
    **observed** snapshot of the barrier - and it must not relabel the
    executed failure as a phase that never ran.
    """
    tree = parse(read(os.path.join(root, T10)))
    phase = function_of(tree, '_m09_timeout_phase')
    result = {'branches': [], 'ok': False}
    if phase is None:
        return result
    for item in ast.walk(phase):
        if not isinstance(item, ast.Call):
            continue
        if not isinstance(item.func, ast.Name) or item.func.id != 'dict':
            continue
        keywords = {kw.arg: kw.value for kw in item.keywords
                    if kw.arg is not None}
        if 'premise' not in keywords:
            continue
        source = ast.unparse(item)
        keys = set(keywords)
        branch = {'line': item.lineno,
                  'premise': 'BARRIER_NOT_COMPLETED' in source,
                  'status_fail': 'status' in keys and "'FAIL'" in source,
                  'executed': 'executed' in keys and 'True' in source,
                  'persisted': 'barrier_persisted' in keys,
                  'write_error': 'barrier_write_error' in keys,
                  'observed': 'barrier_observed' in keys,
                  'observed_generation':
                      'barrier_observed_generation' in keys,
                  'snapshot_present': 'barrier_snapshot_present' in keys,
                  'not_run': 'NOT_RUN' in source}
        result['branches'].append(branch)
    incomplete = [item for item in result['branches'] if item['premise']]
    result['incomplete_branches'] = len(incomplete)
    ok = bool(incomplete)
    for branch in incomplete:
        ok = ok and branch['persisted'] and branch['write_error']
        ok = ok and branch['observed'] and branch['observed_generation']
        ok = ok and branch['snapshot_present'] and branch['status_fail']
        ok = ok and branch['executed'] and not branch['not_run']
    result['ok'] = ok
    return result


def check_late_release(root):
    """M3.a: no controlled release happens after the last verdict.

    The check is a **real AST** check of the ``finally`` of the
    controlled subcase: the **last** release of the gate of the round
    and the restore of the observer happen **before** the final facts,
    the final evidence and the final priority, and the priority is
    applied **after** them - a pending interruption is never added
    after the last check and ignored.
    """
    tree = parse(read(os.path.join(root, T10)))
    node = None
    for item in functions_of(tree):
        source = ast.unparse(item)
        if 'checkpoint' in source and 'controlled_api.frames_ready.set' \
                in source:
            node = item
            break
    result = {'ok': False}
    if node is None:
        return result
    source = ast.unparse(node)
    result['function'] = node.name
    result['has_final_release'] = 'controlled_api.frames_ready.set' in source
    result['has_final_update'] = "facts['cleanup_errors']" in source
    result['has_final_write'] = 'write_facts()' in source
    result['has_priority'] = 'raise controlled_interrupts[0]' in source
    result['preserves_original'] = 'not raised' in source
    # the **last** release of the gate of the round and the priority of
    # the failures are in the same ``finally``: the release comes first
    # and the priority comes last.
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
        order.append({'line': item.lineno,
                      'release_after_disarm':
                          joined.rfind('controlled_api.frames_ready.set')
                          > joined.rfind('controlled_observer.disarm'),
                      'priority_after_release':
                          joined.rfind('raise controlled_interrupts[0]')
                          > joined.rfind('controlled_api.frames_ready.set'),
                      'final_write_before_priority':
                          joined.rfind('write_facts()')
                          < joined.rfind('raise controlled_interrupts[0]')})
    result['finally_blocks'] = order
    ok = (result['has_final_release'] and result['has_final_update']
          and result['has_final_write'] and result['has_priority'])
    ok = ok and bool(order)
    for item in order:
        ok = ok and item['priority_after_release']
        ok = ok and item['final_write_before_priority']
    result['ok'] = ok
    return result


def check_owner_loops(root):
    """M3.b: every owner of a round is attempted before the rethrow.

    The check is a **real AST nesting** check: no loop over the owners
    of a round may re-raise inside its body, every such loop must use
    the guarded join of an owner, and the priority of the failures must
    be applied **after** the whole traversal.
    """
    tree = parse(read(os.path.join(root, T10)))
    guarded = guarded_ids(tree)
    loops = owner_loops(tree, guarded)
    result = {'loops': loops, 'ok': False}
    result['ok'] = bool(loops) and all(
        not item['raises_in_body'] and not item['unguarded_actions']
        for item in loops)
    # the guarded join of an owner records the failure and the exact
    # object of a cancellation: the helper itself never raises.
    helper = function_of(tree, '_join_owner')
    helper_source = ast.unparse(helper) if helper is not None else ''
    result['helper_guards_join'] = (
        "'kind': 'JOIN'" in helper_source
        and "'kind': 'LIVENESS'" in helper_source
        and '_note_interruption' in helper_source)
    result['helper_never_raises'] = 'raise ' not in helper_source
    result['ok'] = (result['ok'] and result['helper_guards_join']
                    and result['helper_never_raises'])
    # every direct join, query or stop of an owner in a **cleanup
    # region** is guarded: a failure of it never skips the action that
    # follows it.
    direct = []
    for item in functions_of(tree):
        if item.name in JOIN_HELPERS:
            continue
        for call in guarded_calls(item, ('join', 'join_bounded', 'is_alive',
                                         'stop_accepting', 'settle'),
                                  ('thread', 'worker', 'reader', 'creator',
                                   'tightener', 'reader_thread', 'pending',
                                   'owner._thread')):
            inside_finally = False
            for statement in ast.walk(item):
                if not isinstance(statement, ast.Try):
                    continue
                for body in statement.finalbody:
                    if call['line'] in [
                            inner.lineno for inner in ast.walk(body)
                            if getattr(inner, 'lineno', None) is not None]:
                        inside_finally = True
            call['function'] = item.name
            call['in_cleanup_region'] = inside_finally
            direct.append(call)
    result['direct_owner_calls'] = direct
    unguarded = [item for item in direct
                 if item['in_cleanup_region'] and not item['guarded']
                 and not item['proof']]
    result['unguarded_cleanup_calls'] = unguarded
    result['ok'] = result['ok'] and not unguarded
    return result


def check_registry_queries(root):
    """M3.c: every query of the facts of a registry is guarded.

    The check is a **real AST** check: the only place of the module
    that calls ``facts()`` of a registry is the guarded helper, and the
    helper retains the actual error and the exact object of a
    cancellation and it never fabricates an empty registry.
    """
    tree = parse(read(os.path.join(root, T10)))
    helper = function_of(tree, '_registry_snapshot')
    helper_source = ast.unparse(helper) if helper is not None else ''
    direct = []
    for item in functions_of(tree):
        if item is helper:
            continue
        for call in ast.walk(item):
            if not isinstance(call, ast.Call):
                continue
            if not isinstance(call.func, ast.Attribute):
                continue
            if call.func.attr != 'facts':
                continue
            direct.append({'function': item.name, 'line': call.lineno,
                           'call': ast.unparse(call)})
    result = {
        'helper_guards': ('_note_interruption' in helper_source
                          and 'return None' in helper_source),
        'helper_never_raises': 'raise ' not in helper_source,
        'direct_facts_calls': direct,
    }
    result['ok'] = (result['helper_guards']
                    and result['helper_never_raises']
                    and not direct)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--json', default=None)
    options = parser.parse_args()

    report = {
        'kind': 'lvw.correction21.static-shape-checks/1',
        'baseline': options.baseline,
        'candidate_root': options.root,
        'denominator': check_denominator(options.root, options.baseline),
        'assertions': check_assertions(options.root, options.baseline),
        'unchanged_sources': check_unchanged(options.root),
        'evidence_root': check_evidence_root(options.root),
        'M2.a_full_drain_facts': check_drain_facts(options.root),
        'M2.b_incomplete_barrier_persistence': check_barrier_persistence(
            options.root),
        'M3.a_no_late_controlled_release': check_late_release(options.root),
        'M3.b_every_owner_attempted': check_owner_loops(options.root),
        'M3.c_guarded_registry_queries': check_registry_queries(options.root),
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
