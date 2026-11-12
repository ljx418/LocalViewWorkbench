#!/usr/bin/env python3
"""The static obligation audit of the correction-08 batch.

The audit compares the *text* of the frozen correction-07 candidate test
module with the text of the correction-08 candidate test module.  It parses
both files with ``ast`` and compares every test function definition, its
decorators and its body, so a weakened or deleted original obligation is
visible.  It does the same for the helper and class definitions of the
module, so a rewritten shared helper is visible as well.  It also compares
the collected node ids of the frozen correction-07 acceptance suite with the
node ids that the correction-08 suite collects, so a dropped test case is
visible.

It imports no product module and it executes no product code.  It uses
``git show`` to read the frozen baseline, so it is a *git read operation*
and it is run outside the offline audit guard, which blocks host processes
by design.

Usage::

    python3 -B reports/v0-s3/product-gate0/implementation-p3b-correction-08/audit_test_obligations.py \
        --baseline fd96cbc37574b382f483e757e8d7235ed5d2598c \
        --candidate HEAD \
        --frozen-suite reports/v0-s3/product-gate0/implementation-p3b-correction-07/suite.receipt.json \
        --candidate-suite reports/v0-s3/product-gate0/implementation-p3b-correction-08/suite.receipt.json \
        --out reports/v0-s3/product-gate0/implementation-p3b-correction-08/obligation-audit.json
"""

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
REPO_ROOT = PACK_ROOT.parent
TEST_RELATIVE = "LVW_Prompt_Service_MasterPack_v2.0.0/tools/test_v0_s3_quality_phase.py"
PRODUCT_RELATIVE = "LVW_Prompt_Service_MasterPack_v2.0.0/tools/v0_s3_quality_phase.py"


def git_show(revision, relative):
    raw = subprocess.run(["git", "-C", str(REPO_ROOT), "show", revision + ":" + relative],
                         check=True, stdout=subprocess.PIPE).stdout
    return raw


def definitions(source):
    """The test definitions of one module, keyed by their name."""
    tree = ast.parse(source)
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            found[node.name] = {
                "decorators": [ast.dump(item) for item in node.decorator_list],
                "body": ast.dump(ast.Module(body=node.body, type_ignores=[])),
                "lineno": node.lineno,
            }
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) and child.name.startswith("test_"):
                    found[node.name + "." + child.name] = {
                        "decorators": [ast.dump(item) for item in child.decorator_list],
                        "body": ast.dump(ast.Module(body=child.body, type_ignores=[])),
                        "lineno": child.lineno,
                    }
    return found


def helpers(source):
    """The helper and class definitions of one module, keyed by their name."""
    tree = ast.parse(source)
    found = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("test_"):
            found[node.name] = ast.dump(ast.Module(body=node.body, type_ignores=[]))
        elif isinstance(node, ast.ClassDef):
            found[node.name] = ast.dump(ast.Module(body=node.body, type_ignores=[]))
    return found


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--frozen-suite", required=True,
                        help="the frozen acceptance receipt with the collected node ids")
    parser.add_argument("--candidate-suite", required=True,
                        help="the receipt of the combined candidate suite")
    parser.add_argument("--out", required=True)
    arguments = parser.parse_args(argv)

    baseline_raw = git_show(arguments.baseline, TEST_RELATIVE)
    candidate_raw = git_show(arguments.candidate, TEST_RELATIVE)
    baseline = definitions(baseline_raw.decode("utf-8"))
    candidate = definitions(candidate_raw.decode("utf-8"))

    identical = []
    adapted = []
    missing = []
    for name, entry in sorted(baseline.items()):
        other = candidate.get(name)
        if other is None:
            missing.append(name)
            continue
        if other["body"] == entry["body"] and other["decorators"] == entry["decorators"]:
            identical.append(name)
        else:
            adapted.append(name)
    added = sorted(set(candidate) - set(baseline))

    baseline_helpers = helpers(baseline_raw.decode("utf-8"))
    candidate_helpers = helpers(candidate_raw.decode("utf-8"))
    changed_helpers = sorted(
        name for name, body in baseline_helpers.items()
        if name not in candidate_helpers or candidate_helpers[name] != body)

    frozen = json.loads((PACK_ROOT / arguments.frozen_suite).read_text(encoding="utf-8"))
    frozen_nodeids = set(frozen.get("collected_nodeids") or [])
    suite_receipt = json.loads(
        (PACK_ROOT / arguments.candidate_suite).read_text(encoding="utf-8"))
    candidate_nodeids = set(suite_receipt.get("collected_nodeids") or [])
    missing_nodeids = sorted(frozen_nodeids - candidate_nodeids)
    added_nodeids = sorted(candidate_nodeids - frozen_nodeids)

    product_baseline = git_show(arguments.baseline, PRODUCT_RELATIVE)
    product_candidate = git_show(arguments.candidate, PRODUCT_RELATIVE)

    payload = {
        "kind": "S3_P3B_CORRECTION_08_TEST_OBLIGATION_AUDIT",
        "baseline_revision": arguments.baseline,
        "candidate_revision": arguments.candidate,
        "test_file": TEST_RELATIVE,
        "baseline_sha256": hashlib.sha256(baseline_raw).hexdigest(),
        "candidate_sha256": hashlib.sha256(candidate_raw).hexdigest(),
        "baseline_test_definitions": len(baseline),
        "candidate_test_definitions": len(candidate),
        "identical_definitions": len(identical),
        "adapted_definitions": adapted,
        "deleted_definitions": missing,
        "added_definitions": added,
        "identical_names": identical,
        "changed_old_helpers": changed_helpers,
        "added_helper_definitions": sorted(set(candidate_helpers) - set(baseline_helpers)),
        "baseline_product_sha256": hashlib.sha256(product_baseline).hexdigest(),
        "candidate_product_sha256": hashlib.sha256(product_candidate).hexdigest(),
        "frozen_collected_nodeids": len(frozen_nodeids),
        "candidate_collected_nodeids": len(candidate_nodeids),
        "missing_frozen_nodeids": missing_nodeids,
        "added_nodeids": added_nodeids,
        "no_original_obligation_deleted": not missing,
        "no_frozen_nodeid_lost": not missing_nodeids,
        "no_original_obligation_adapted": not adapted,
        "no_old_helper_changed": not changed_helpers,
        "stage_pass_claim": False,
        "product_gate0": False,
    }
    out = Path(arguments.out)
    if not out.is_absolute():
        out = PACK_ROOT / out
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                   encoding="utf-8")
    print(json.dumps({key: payload[key] for key in (
        "baseline_test_definitions", "candidate_test_definitions", "identical_definitions",
        "adapted_definitions", "deleted_definitions", "added_definitions",
        "changed_old_helpers", "added_helper_definitions",
        "frozen_collected_nodeids", "candidate_collected_nodeids",
        "missing_frozen_nodeids")},
        indent=2, sort_keys=True))
    return 0 if (not missing and not missing_nodeids and not adapted and not changed_helpers) else 1


if __name__ == "__main__":
    sys.exit(main())
