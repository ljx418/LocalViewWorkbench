#!/usr/bin/env python3
"""Independent comparison of the carried test functions.

The candidate claims "233 passed (165 carried over from 1.1.1 plus 68 new)".
This tool does not trust that arithmetic: it parses the prior (f795694) and
the candidate (eea5663) test modules, compares the *bodies* of every test
function that exists in both, and reports every carried function whose body
changed. A carried negative whose assertion was weakened or deleted is a
finding; a carried function that only changed because the frozen pin moved
is a legitimate version change.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]          # .../LVW_Prompt_Service_MasterPack_v2.0.0/..
REL = "LVW_Prompt_Service_MasterPack_v2.0.0/tools/test_verify_v1_plan.py"


def source_at(revision):
    proc = subprocess.run(["git", "show", "%s:%s" % (revision, REL)],
                          capture_output=True, text=True, cwd=str(REPO))
    if proc.returncode != 0:
        raise SystemExit("cannot read %s: %s" % (revision, proc.stderr.strip()))
    return proc.stdout


def functions(text):
    tree = ast.parse(text)
    lines = text.splitlines()
    found = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
            found[node.name] = "\n".join(lines[node.lineno - 1:node.end_lineno])
    return found


def main():
    prior = functions(source_at("f7956941992a0c467384b5dc9c63133f95152f41"))
    candidate = functions(source_at("eea56636b1870586fd8d6b17005334f1b4c63cd7"))

    carried = sorted(set(prior) & set(candidate))
    removed = sorted(set(prior) - set(candidate))
    added = sorted(set(candidate) - set(prior))

    changed = []
    for name in carried:
        if prior[name] != candidate[name]:
            changed.append({
                "test": name,
                "prior_lines": prior[name].splitlines(),
                "candidate_lines": candidate[name].splitlines(),
            })

    # The one removed function and its replacement.
    replacement = {}
    for name in removed:
        for other in added:
            if (other.replace("112", "111") == name.replace("_112_", "_111_")
                    or name.replace("_111_", "_112_") == other):
                replacement[name] = other

    result = {
        "prior_test_function_count": len(prior),
        "candidate_test_function_count": len(candidate),
        "carried_function_count": len(carried),
        "removed_functions": removed,
        "removed_function_replacements": replacement,
        "added_function_count": len(added),
        "added_functions": added,
        "carried_functions_with_a_changed_body": [item["test"] for item in changed],
        "changed_bodies": changed,
    }
    out = HERE / "test-diff-results.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "changed_bodies"},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
