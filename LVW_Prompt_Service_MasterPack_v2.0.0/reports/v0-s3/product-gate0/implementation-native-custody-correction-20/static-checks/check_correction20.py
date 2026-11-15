#!/usr/bin/env python3
"""Correction 20 - STATIC shape checks of the candidate.

This script is a **static** instrument: it never imports the candidate,
it never collects it, it never runs a test, it never opens a socket, a
database, a model or a native library and it never starts a product
process.  It reads the candidate source and the frozen baseline source
as **data** (text, ``ast`` and ``hashlib``) and it reports the shape
of the seven counterexamples of the correction 20.

Usage::

    python3 check_correction20.py --root <pack root> \\
        --baseline <baseline commit> [--json <out.json>]

The baseline is read with ``git show`` (read only, no checkout).
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


def calls_of(node, callee):
    """Every call of ``callee`` inside ``node``."""
    found = []
    for item in ast.walk(node):
        if isinstance(item, ast.Call) and isinstance(item.func, ast.Name):
            if item.func.id == callee:
                found.append(item)
    return found


def bare_set_in_finally(tree):
    """The releases that are **not** guarded inside a ``finally``."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        for statement in node.finalbody:
            for item in ast.walk(statement):
                if not isinstance(item, ast.Expr):
                    continue
                if not isinstance(item.value, ast.Call):
                    continue
                func = item.value.func
                if isinstance(func, ast.Attribute) and func.attr == 'set':
                    found.append((item.lineno, ast.unparse(item)))
    return found


def names_of(node):
    """The names that are read or written inside ``node``."""
    return {item.id for item in ast.walk(node)
            if isinstance(item, ast.Name)}


# ------------------------------------------------------------- the checks

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


def check_original_plan(root):
    """M2.1: the launch document keeps its own binding."""
    tree = parse(read(os.path.join(root, T10)))
    node = function_of(tree, R10)
    stores = [item.lineno for item in ast.walk(node)
              if isinstance(item, ast.Name) and item.id == 'document'
              and isinstance(item.ctx, ast.Store)]
    schedules = []
    for callee in ('_m09_timeout_phase', '_m09_published_fault_phase'):
        for call in calls_of(node, callee):
            first = call.args[0] if call.args else None
            schedules.append({'callee': callee, 'line': call.lineno,
                              'document': ast.unparse(first)
                              if first is not None else None})
    chain = []
    for call in calls_of(node, '_chain'):
        second = call.args[1] if len(call.args) > 1 else None
        chain.append({'line': call.lineno,
                      'document': ast.unparse(second)
                      if second is not None else None})
    coordination = [item.lineno for item in ast.walk(node)
                    if isinstance(item, ast.Name) and item.id == 'coord_document'
                    and isinstance(item.ctx, ast.Store)]
    ok = (len(stores) == 1
          and all(item['document'] == 'document' for item in schedules)
          and all(item['document'] == 'document' for item in chain)
          and len(schedules) == 5
          and len(coordination) == 1
          and not any(isinstance(item, ast.Name) and item.id == 'document'
                      and isinstance(item.ctx, ast.Store)
                      for item in ast.walk(node)
                      if getattr(item, 'lineno', 0) > stores[0]))
    return {'document_stores': stores, 'schedules': schedules,
            'chains': chain, 'coord_document_stores': coordination,
            'ok': ok}


def check_shared_facts(root):
    """M2.2: the phases share the fact store of the group."""
    tree = parse(read(os.path.join(root, T10)))
    node = function_of(tree, R10)
    result = {'phases': {}, 'ok': True}
    for callee in ('_m09_timeout_phase', '_m09_published_fault_phase'):
        phase = function_of(tree, callee)
        keywords = {kw.arg for kw in phase.args.kw_defaults
                    and [] or []}
        names = [item.arg for item in phase.args.kwonlyargs]
        result['phases'][callee] = {
            'kwonly': names,
            'has_store': 'store' in names,
            'raw_is_the_store': any(
                isinstance(item, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == 'raw'
                        for target in item.targets)
                and 'store' in ast.unparse(item.value)
                for item in ast.walk(phase)),
        }
        del keywords
    stores = []
    for callee in ('_m09_timeout_phase', '_m09_published_fault_phase'):
        for call in calls_of(node, callee):
            stores.append({'callee': callee, 'line': call.lineno,
                           'store': next((ast.unparse(kw.value)
                                          for kw in call.keywords
                                          if kw.arg == 'store'), None)})
    result['calls'] = stores
    # the outer recovery reuses the store and never writes a generic FAIL
    # over an empty document.
    recovery = []
    for item in ast.walk(node):
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == 'recovered':
                    recovery.append(ast.unparse(item.value))
    result['recovery_documents'] = recovery
    result['ok'] = (all(item['has_store'] and item['raw_is_the_store']
                        for item in result['phases'].values())
                    and len(stores) == 5
                    and all(item['store'] == 'r10_raw' for item in stores)
                    and any('r10_raw.get' in text for text in recovery))
    return result


def check_final_summary(root):
    """M2.4: the durable final accounting of the group."""
    tree = parse(read(os.path.join(root, T10)))
    node = function_of(tree, R10)
    summary = []
    for call in calls_of(node, 'write_phase'):
        if call.args and isinstance(call.args[0], ast.Constant):
            if call.args[0].value == 'r10-final-summary':
                keys = None
                for item in ast.walk(node):
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) \
                                    and target.id == 'summary':
                                if isinstance(item.value, ast.Dict):
                                    keys = sorted(
                                        key.value for key in item.value.keys
                                        if isinstance(key, ast.Constant))
                summary.append({'line': call.lineno, 'keys': keys})
    # the summary is written **after** the inventory of the NOT_RUN names
    lines = []
    for call in calls_of(node, 'write_phase'):
        if call.args and isinstance(call.args[0], ast.Name) \
                and call.args[0].id == 'r10_name':
            if 'NOT_RUN' in ast.unparse(call):
                lines.append(call.lineno)
    ok = bool(summary) and bool(summary[0]['keys'])
    wanted = ('states', 'written', 'not_persisted', 'facts',
              'original_failure', 'write_errors')
    if summary and summary[0]['keys']:
        ok = ok and all(key in summary[0]['keys'] for key in wanted)
    ok = ok and bool(lines) and summary[0]['line'] > max(lines)
    return {'summary': summary, 'not_run_writes': lines, 'ok': ok}


def check_early_verdict(root):
    """M2.3: the final verdict of the earlier work fails with it."""
    tree = parse(read(os.path.join(root, T10)))
    node = function_of(tree, R10)
    source = ast.unparse(node)
    ok = ('early_original[\'type\'] is not None' in source
          and 'early_write_failure' in source
          and 'coord_write_failure' in source)
    return {'ok': ok}


def check_gate_guards(root):
    """M3.2: every release of a cleanup region is guarded."""
    tree = parse(read(os.path.join(root, T10)))
    bare = bare_set_in_finally(tree)
    guards = []
    for call in ast.walk(tree):
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
            if call.func.id == '_release_gate':
                guards.append(call.lineno)
    named = []
    node = function_of(tree, R10)
    for call in calls_of(node, '_m09_timeout_phase'):
        named.append(call.lineno)
    return {'bare_releases_in_finally': bare,
            'guarded_releases': len(guards),
            'ok': not bare and len(guards) >= 12}


def check_interruption_priority(root):
    """M3.1: the first exact pending interruption wins."""
    tree = parse(read(os.path.join(root, T10)))
    node = function_of(tree, R10)
    module_source = ast.unparse(tree)
    barrier = []
    for call in calls_of(node, '_m09_timeout_phase'):
        barrier.append(call.lineno)
    phase = function_of(tree, '_m09_timeout_phase')
    phase_source = ast.unparse(phase) if phase is not None else ''
    ok = ('raise zero_interrupts[0]' in module_source
          and 'raise parent_interrupts[0]' in module_source
          and 'raise controlled_interrupts[0]' in module_source
          and 'barrier_interruption' in phase_source
          and 'raise api.barrier_interruption' in phase_source)
    # the pending list is always consulted **before** the current
    # cancellation of the write is re-raised.
    order = []
    for name in ('zero_interrupts', 'parent_interrupts',
                 'controlled_interrupts'):
        best = None
        for item in ast.walk(tree):
            if not isinstance(item, ast.If):
                continue
            pending = None
            bare = None
            for position, statement in enumerate(item.body):
                for inner in ast.walk(statement):
                    if not isinstance(inner, ast.Raise):
                        continue
                    if inner.exc is None:
                        if bare is None:
                            bare = position
                        continue
                    text = ast.unparse(inner.exc)
                    if text == '%s[0]' % name and pending is None:
                        pending = position
            if pending is None:
                continue
            if bare is None:
                continue
            if best is None or len(item.body) > len(best[1].body):
                best = (pending, item, bare)
        if best is None:
            order.append({'list': name, 'pending_first': False})
            continue
        order.append({'list': name, 'pending_at': best[0],
                      'bare_raise_at': best[2],
                      'pending_first': best[0] < best[2]})
    ok = ok and len(order) == 3 and all(item['pending_first']
                                        for item in order)
    return {'ok': ok, 'priority_sites': order, 'barrier_calls': barrier}


def check_independent_fallback(root):
    """M3.3: the fallback of the owners does not depend on ``entries``."""
    tree = parse(read(os.path.join(root, T10)))
    owners = function_of(tree, '_registry_owners')
    drain = function_of(tree, '_drain_owners')
    helper = function_of(tree, '_observed_thread_refs')
    owners_source = ast.unparse(owners)
    drain_source = ast.unparse(drain)
    helper_source = ast.unparse(helper)
    ok = ('_observed_thread_refs(registry' in owners_source
          and 'registry.entries()' not in helper_source
          and '_observed_thread_refs(registry' in drain_source
          and 'observed_threads' in ast.unparse(tree))
    return {'ok': ok,
            'helper_uses_entries': 'registry.entries()' in helper_source,
            'drain_seeds_owners': '_observed_thread_refs' in drain_source}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--json', default=None)
    options = parser.parse_args()

    report = {
        'kind': 'lvw.correction20.static-shape-checks/1',
        'baseline': options.baseline,
        'candidate_root': options.root,
        'denominator': check_denominator(options.root, options.baseline),
        'assertions': check_assertions(options.root, options.baseline),
        'unchanged_sources': check_unchanged(options.root),
        'M2.1_original_plan_binding': check_original_plan(options.root),
        'M2.2_shared_recovery_facts': check_shared_facts(options.root),
        'M2.3_early_final_verdict': check_early_verdict(options.root),
        'M2.4_durable_final_inventory': check_final_summary(options.root),
        'M3.1_interruption_priority': check_interruption_priority(options.root),
        'M3.2_every_initial_gate_guarded': check_gate_guards(options.root),
        'M3.3_independent_observed_fallback':
            check_independent_fallback(options.root),
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
