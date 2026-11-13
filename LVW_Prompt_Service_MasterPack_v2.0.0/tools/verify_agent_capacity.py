#!/usr/bin/env python3
"""Read-only Orca workspace capacity preflight; never starts or stops agents."""
import argparse
import json
import subprocess


def check(rows, target, additional):
    # Count all terminals conservatively, including unrecognized/idle agents.
    scoped = [r for r in rows if r.get("worktreeId", "").split("::", 1)[0] == target.split("::", 1)[0]]
    counts = {}
    for row in scoped:
        key = row.get("worktreeId")
        counts[key] = counts.get(key, 0) + 1
    projected = counts.get(target, 0) + additional
    return {"allowed": projected <= 1 and sum(counts.values()) + additional <= 3
            and all(n <= 1 for n in counts.values()),
            "counts": counts, "projected_target": projected,
            "projected_project": sum(counts.values()) + additional,
            "unknown_counts_as_occupied": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree")
    parser.add_argument("--additional", type=int, choices=(0, 1), default=1)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        assert check([], "p::a", 1)["allowed"]
        assert not check([{"worktreeId": "p::a"}], "p::a", 1)["allowed"]
        assert check([{"worktreeId": "p::a"}, {"worktreeId": "p::b"}], "p::c", 1)["allowed"]
        assert not check([{"worktreeId": "p::a"}, {"worktreeId": "p::b"}, {"worktreeId": "p::c"}], "p::d", 1)["allowed"]
        print("4 capacity boundary checks passed")
        return 0
    if not args.worktree:
        parser.error("--worktree is required")
    result = subprocess.run(["orca-ide", "terminal", "list", "--json"], capture_output=True, text=True)
    if result.returncode:
        print(json.dumps({"allowed": False, "reason": "ORCA_CENSUS_UNAVAILABLE", "stderr": result.stderr}))
        return 2
    try:
        doc = json.loads(result.stdout)
        rows = doc["result"]["terminals"]
        assert isinstance(rows, list)
        decision = check(rows, args.worktree.removeprefix("id:"), args.additional)
    except (ValueError, KeyError, TypeError, AssertionError):
        print(json.dumps({"allowed": False, "reason": "ORCA_CENSUS_INVALID"}))
        return 2
    print(json.dumps(decision, ensure_ascii=False, indent=2))
    return 0 if decision["allowed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
