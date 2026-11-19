"""Verify Git objects, raw root evidence, and this review's independent extraction."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

repo = Path("/mnt/c/workspace/videoworkline/localviewworkbench")
s = "cfca7fe72525c600d4086b98428836c33b437b31"
e = "c2857f4eb32f1de2e7e11393741631613ce4a537"
p = "LVW_Prompt_Service_MasterPack_v2.0.0"
d = "reports/resource-cleanup/correction-04/"
here = Path(__file__).resolve().parent
request = json.loads((here / "request.json").read_bytes())
pack = Path(request["cwd"])
def git(*args):
    return subprocess.check_output(["git", "-C", repo, *args])
def blob(commit, path):
    return git("show", f"{commit}:{p}/{path}")
def read(commit, path):
    return json.loads(blob(commit, path))
def sha(data):
    return hashlib.sha256(data).hexdigest()
def dots(data):
    return sum(len(m) for m in re.findall(rb"^(\.+) +\[ *\d+%\]", data, re.M))

plan = read(e, d + "independent-review-plan.json")
ack = read(s, d + "root-ack-recheck.json")
assert git("rev-parse", e+"^").decode().strip() == plan["candidate_sha"] == s
verified = {}
for path, expected in ack["source_hashes"].items():
    digest = sha(blob(s, path))
    assert digest == expected == sha((pack/path).read_bytes()) == sha(blob(e, path)), path
    verified[path] = digest
include = ["lvw", "templates", "tools", "config", "LVW_V0_RuntimePatch/custom_nodes",
           d+"live_harness_v5.py", plan["controller"]]
entries = git("ls-tree","-rz",s,"--",*[p+"/"+a for a in include]).split(b"\0")
count = 0
archive_eol = []
for entry in filter(None, entries):
    header, name = entry.split(b"\t",1)
    mode, kind, oid = header.split()
    assert kind == b"blob"
    f = pack.parent/os.fsdecode(name)
    data = os.fsencode(os.readlink(f)) if mode == b"120000" else f.read_bytes()
    if hashlib.sha1(b"blob "+str(len(data)).encode()+b"\0"+data).hexdigest().encode() != oid:
        original = git("cat-file", "blob", oid.decode())
        assert f.suffix.lower() in (".cmd", ".bat", ".ps1") and data == original.replace(b"\n",b"\r\n")
        archive_eol.append(os.fsdecode(name))
    count += 1
assert not list(pack.rglob("*.pyc")) and not list(pack.rglob(".pytest_cache"))
assert len(list(Path(request["environment"]["TMPDIR"]).rglob("*.pyc"))) == 1
trees = {k:git("rev-parse", k+":"+p+"/lvw/frontend/dist").decode().strip()
         for k in ["a066fe19", "65d93c67", s, e]}
assert len(set(trees.values())) == 1
for asset in (pack/"lvw/frontend/dist").rglob("*"):
    if asset.is_file():
        relative = asset.relative_to(pack)
        assert asset.read_bytes() == (repo/p/relative).read_bytes() == blob(s, str(relative))
root_checks = []
for i, cmd in enumerate(ack["commands"], 1):
    base = d+f"cpu/check-{i:02}/"
    n = f"{i:02}"
    assert cmd == read(e,d+"cpu/request-"+n+".json") == read(e,base+"intent.json")
    receipt = read(e,base+"receipt.json")
    child = read(e,base+"child.json")
    assert all(receipt[k] == cmd[k] for k in ["argv","cwd","environment"])
    assert all(receipt[k] == v for k,v in child.items())
    assert receipt["reaped"] and not receipt["timed_out"] and not receipt["errors"]
    assert receipt["status"] == ("EXITED_NONZERO" if i<=2 else "EXITED_ZERO")
    assert receipt["returncode"] == (1 if i<=2 else 0)
    stdout = blob(e,base+"stdout.log")
    outcome = {"success_markers":dots(stdout)} if i in (5,6) else {}
    if i in (5,6): assert dots(stdout) == {5:90,6:244}[i]
    if i in (1,2):
        outcome["failures"] = re.findall(r"^FAILED (.+)$",stdout.decode(),re.M)
        assert len(outcome["failures"]) == i
    if i == 3: assert b"# pass 12" in stdout and b"# fail 0" in stdout
    if i == 4: assert b"tsc -b && vite build" in stdout and b"built in" in stdout
    outcome.update({k:receipt[k] for k in ["status","pid","birth","elapsed_seconds","returncode","reaped"]})
    outcome["git_evidence"] = base
    outcome["sha256"] = {f:sha(blob(e,base+f)) for f in ("intent.json","child.json","receipt.json","stdout.log","stderr.log")}
    root_checks.append(outcome)
ticks = os.sysconf("SC_CLK_TCK")
start = [int(c["birth"])/ticks for c in root_checks]
assert start[1] < start[3] < start[1]+root_checks[1]["elapsed_seconds"]
assert start[3]+root_checks[3]["elapsed_seconds"] < start[4]
assert start[4]+root_checks[4]["elapsed_seconds"] < start[5]
assert read(e,d+"implementation-receipt.json")["candidate_sha"] == s
raw = here/"cpu"
own = json.loads((raw/"receipt.json").read_bytes())
assert json.loads((raw/"intent.json").read_bytes()) == request
assert all(own[k]==v for k,v in json.loads((raw/"child.json").read_bytes()).items())
assert request["argv"] == plan["allowed_command"] and request["wall_seconds"] == 90
assert dots((raw/"stdout.log").read_bytes()) == 90 and own["reaped"] and own["returncode"] == 0
assert not (raw/"stderr.log").read_bytes() and (here/"controller-exit.txt").read_text().strip()=="0"
out = dict(candidate=s,candidate_tree=git("rev-parse",s+"^{tree}").decode().strip(),evidence_commit=e,
           controller_sha256=sha(blob(s,plan["controller"])),request_sha256=sha((here/"request.json").read_bytes()),
           ack_sha256=sha(blob(s,d+"root-ack-recheck.json")),verified_ack_sha256=verified,
           verified_extracted_entries=count,archive_crlf_conversion=archive_eol,extraction_pathspecs=include,dist_git_trees=trees,
           dist_sha256={str(f.relative_to(pack)):sha(f.read_bytes()) for f in sorted((pack/"lvw/frontend/dist").rglob("*")) if f.is_file()},
           kernel_ticks_per_second=ticks,root_checks=root_checks,
           root_archive_times_ns={a:(repo/p/a).stat().st_mtime_ns for a in [d+"root-ack-recheck.json"]+
            [d+f"cpu/check-{i:02}/{f}.json" for i in range(1,7) for f in ("intent","receipt")]},
           independent_success_markers=90,independent_controller=own)
print(json.dumps(out,indent=2))
