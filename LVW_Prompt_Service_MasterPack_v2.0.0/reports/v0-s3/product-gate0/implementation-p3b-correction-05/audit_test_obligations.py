#!/usr/bin/env python3
"""The static obligation audit of the correction-05 batch.

The audit compares the *text* of the frozen correction-04 candidate test
module with the text of the correction-05 candidate test module.  It parses
both files with ``ast`` and compares every test function definition, its
decorators and its body, so a weakened or deleted original obligation is
visible.  It imports no product module and executes no product code.

Usage::

    python3 -B reports/v0-s3/product-gate0/implementation-p3b-correction-05/audit_test_obligations.py \
        --baseline 5de09478a4af6e3dd91410d4dde90c9020a77bfd \
        --candidate HEAD \
        --out reports/v0-s3/product-gate0/implementation-p3b-correction-05/obligation-audit.json
"""

import argparse
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parents[4]
TEST_RELATIVE = "LVW_Prompt_Service_MasterPack_v2.0.0/tools/test_v0_s3_quality_phase.py"


def git_show(revision, relative):
    raw = subprocess.run(["git", "-C", str(PACK_ROOT.parent), "show", revision + ":" + relative],
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


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
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

    payload = {
        "kind": "S3_P3B_CORRECTION_05_TEST_OBLIGATION_AUDIT",
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
        "no_original_obligation_deleted": not missing,
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
        "adapted_definitions", "deleted_definitions", "added_definitions")},
        indent=2, sort_keys=True))
    return 0 if not missing else 1


if __name__ == "__main__":
    sys.exit(main())
