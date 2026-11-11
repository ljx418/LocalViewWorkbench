#!/usr/bin/env python3
"""Byte-level integrity proof for the independent probe trees.

The recheck script's ``frozen_authority_bytes_identical_to_source`` field
compares *all* 29 authority files, including the deliberately mutated
``plans/execution-control.json``; it is therefore ``False`` in every mutated
probe **by construction**.  This follow-up makes the actual claim explicit and
directly measurable, WITHOUT re-running the checker:

  * every frozen authority file OTHER than ``plans/execution-control.json`` is
    byte-identical to the real repository file (28/28);
  * ``plans/execution-control.json`` differs from the real file ONLY inside the
    intended paths -- the ``development_outline`` entry ``V0-S2`` and the
    ``historical_s2_coordinate`` snapshot (or, for the coordinate-advance
    positive, only ``coordinate`` / ``current_blocking_gate`` / ``updated_at``).

No media stat/hash/probe/decode, no inventory CLI, no network.

Run: python3 -B reports/v0-s3/preparation-03/independent-correction-01/check_probe_tree_integrity.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("recheck", HERE / "run_independent_recheck.py")
recheck = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recheck)

REPO = recheck.REPO
EXECUTION_REL = recheck.EXECUTION_REL


def json_diff(left, right, prefix: str = "") -> list:
    """Every JSON path whose value differs between two documents."""
    paths = []
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            child = "%s.%s" % (prefix, key) if prefix else key
            if key not in left or key not in right:
                paths.append(child)
            else:
                paths.extend(json_diff(left[key], right[key], child))
        return paths
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            paths.append(prefix + "[len %d -> %d]" % (len(left), len(right)))
            return paths
        for index, (a, b) in enumerate(zip(left, right)):
            paths.extend(json_diff(a, b, "%s[%d]" % (prefix, index)))
        return paths
    if left != right:
        paths.append(prefix)
    return paths


def main() -> int:
    source_execution = recheck.read_json(REPO / EXECUTION_REL)
    source_hashes = {rel: recheck.sha256_file(REPO / rel) for rel in recheck.AUTHORITY_FILES}
    frozen = [rel for rel in recheck.AUTHORITY_FILES if rel != EXECUTION_REL]

    cases = []
    for name, mutate, expected_id in recheck.NEGATIVES:
        cases.append((name, "NEGATIVE", mutate, expected_id, ("development_outline[", "historical_s2_coordinate")))
    for name, mutate in recheck.POSITIVES:
        if mutate is None:
            cases.append((name, "POSITIVE", None, None, ()))
        else:
            cases.append((name, "POSITIVE", mutate, None, ("coordinate", "current_blocking_gate", "updated_at")))

    results = []
    with tempfile.TemporaryDirectory(prefix="lvw-s3pa-indep-correction-01-integrity-") as _tmp:
        parent = Path(_tmp)
        for name, kind, mutate, expected_id, allowed in cases:
            tree = recheck.build_tree(parent / name)
            execution_file = tree / EXECUTION_REL
            document = recheck.read_json(execution_file)
            if mutate is not None:
                mutate(document)
                recheck.write_json(execution_file, document)
            mutated = recheck.read_json(execution_file)
            changed = json_diff(source_execution, mutated)
            non_frozen_identical = all(
                recheck.sha256_file(tree / rel) == source_hashes[rel] for rel in frozen
            )
            execution_changed = recheck.sha256_file(execution_file) != source_hashes[EXECUTION_REL]
            allowed_ok = all(any(path.startswith(prefix) for prefix in allowed) for path in changed)
            results.append(
                {
                    "probe": name,
                    "kind": kind,
                    "expected_failed_id": expected_id,
                    "frozen_authority_files": len(frozen),
                    "frozen_authority_files_byte_identical_to_source": non_frozen_identical,
                    "execution_control_json_changed": execution_changed,
                    "execution_control_changed_paths": changed,
                    "changed_paths_confined_to_intended_scope": allowed_ok,
                    "verdict": (
                        "OK"
                        if non_frozen_identical and allowed_ok
                        else "PROBLEM"
                    ),
                }
            )
        parent_exists_after = parent.exists()

    report = {
        "kind": "S3P_A_INDEPENDENT_CORRECTION_01_PROBE_TREE_INTEGRITY",
        "note": (
            "the recheck field 'frozen_authority_bytes_identical_to_source' compares all 29 "
            "authority files including the deliberately mutated plans/execution-control.json, so "
            "it is False in every mutated probe by construction; this file is the direct "
            "byte-level proof of the intended claim"
        ),
        "frozen_authority_file_count": len(frozen),
        "mutated_file": EXECUTION_REL,
        "checker_rerun": False,
        "media_access": False,
        "inventory_cli_invoked": False,
        "cases": results,
        "all_cases_ok": all(item["verdict"] == "OK" for item in results),
        "owned_parent_exists_after_context": parent_exists_after,
    }
    out = HERE / "probe-tree-integrity.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    for item in results:
        print(
            "%-8s %-48s frozen_identical=%s confined=%s changed=%s"
            % (
                item["kind"],
                item["probe"],
                item["frozen_authority_files_byte_identical_to_source"],
                item["changed_paths_confined_to_intended_scope"],
                item["execution_control_changed_paths"],
            )
        )
    print("all_cases_ok:", report["all_cases_ok"])
    print("written:", out)
    return 0 if report["all_cases_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
