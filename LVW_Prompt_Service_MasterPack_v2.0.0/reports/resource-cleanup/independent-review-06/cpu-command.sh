#!/bin/bash
set -eu -o pipefail
M=/mnt/c/workspace/videoworkline/localviewworkbench
P=LVW_Prompt_Service_MasterPack_v2.0.0
L=reports/resource-cleanup/loaded-validation-01
C=1ee7bd2b12199b12e60c59c15bba776952319eb9
R=${1:-$PWD/reports/resource-cleanup-independent-06}
mkdir -p "$R"
R=$(realpath "$R")
if [[ -e "$R/request.json" ]]; then echo "Choose a fresh output directory" >&2; exit 1; fi
D=$(mktemp -d /tmp/lvw-independent06-XXXXXXXX)
K=reports/workflow-rebaseline-2026-11-15/opt-b-14-trusted-stop-cancel/bounded_exec.py
git -C "$M" archive "$C:$P" lvw/pyproject.toml lvw/backend lvw/tests lvw/frontend/dist templates tools config LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge reports/resource-cleanup/correction-04/live_harness_v5.py "$L/live_harness_v6.py" "$K" | tar -x -C "$D"
mkdir -p "$D/tmp/data"
python3 - "$M/$P/$L" "$D" "$R" <<'PY'
import json,sys,pathlib
l,d,r=map(pathlib.Path,sys.argv[1:])
plan=json.loads((l/'independent-review-plan.json').read_text())
q=json.loads((l/'root-ack-job-cpu.json').read_text())['commands'][0]
assert plan['allowed_command']==q['argv'] and plan['wall_seconds']==q['wall_seconds']==90
q.update(cwd=str(d),output_dir=str(r/'cpu'))
q['environment'].update(PYTHONPATH=f'{d}:{d}/lvw/backend',TMPDIR=str(d/'tmp'),LVW_DATA_ROOT=str(d/'tmp/data'))
(r/'request.json').write_text(json.dumps(q,indent=2))
PY
cd "$D"
/usr/bin/python3 -B "$K" "$R/request.json" >"$R/controller.stdout" 2>"$R/controller.stderr" && rc=0 || rc=$?
echo "$rc" > "$R/controller-exit.txt"
exit "$rc"
