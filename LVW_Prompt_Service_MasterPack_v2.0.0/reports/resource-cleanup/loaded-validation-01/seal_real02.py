"""Root-ACKed one-shot correction run. No process/model launch occurs here."""
from pathlib import Path
from types import ModuleType
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[3]
BASE = Path(__file__).resolve().parent
source = (ROOT / 'tools/local_program_authority.py').read_bytes()
assert hashlib.sha256(source).hexdigest() == '677998fa2ab5b51017b5437fecd07d6ca31c26473a7ac0acede4637f6470f787'
a = ModuleType('verified_root_sealer')
a.__file__ = str(ROOT / 'tools/local_program_authority.py')
exec(compile(source, a.__file__, 'exec'), a.__dict__)
a.approved(ROOT)
ack = json.loads((BASE / 'root-ack-job-cpu.json').read_text())
assert all(a.digest(ROOT / k) == v for k, v in ack['source_hashes'].items())
for number in [2, 3]:
    receipt = json.loads((BASE / f'cpu/check-{number:02}/receipt.json').read_text())
    assert receipt['returncode'] == 0 and receipt['reaped'] and not receipt['timed_out']
probe = json.loads((BASE / 'runs/native-job-probe01/controller/stdout.log').read_text(encoding='utf-8-sig'))
assert probe['status'] == 'NATIVE_JOB_KERNEL_PASS' and probe['job_empty'] and probe['original_exited']
sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
run = 'cleanup-loaded01-real02'
out = BASE / 'runs/real02'
out.mkdir()
private = Path(tempfile.mkdtemp(prefix='lvw-cleanup-v4-loaded-'))
data = private / 'data'
data.mkdir(mode=0o700)
marker = json.dumps({'run': run, 'nonce': uuid.uuid4().hex})
(private / 'owner-marker.json').write_text(marker)
def identity(path):
    value = path.stat()
    return [value.st_dev, value.st_ino, value.st_uid]
budget = dict(model_calls=2, provider_calls=2, api_starts=1, ollama_starts=2, headless_browser_starts=1, full_checkpoints=0)
paths = (list((ROOT / 'lvw/backend/app').glob('*.py')) + list((ROOT / 'lvw/frontend/dist').rglob('*'))
    + list((ROOT / 'templates').glob('*.txt')) + list((ROOT / 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge').glob('*.py'))
    + [ROOT / 'tools/local_program_authority.py', BASE / 'live_harness_v6.py', BASE / 'profile.md', Path(__file__)])
frozen = [{'path': str(path.relative_to(ROOT)), 'sha256': a.digest(path)} for path in paths if path.is_file()]
tools = {'python': str(Path(sys.executable).resolve()), 'chromium': '/home/administrator/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome',
    'nvidia-smi': '/usr/lib/wsl/lib/nvidia-smi', 'ollama': '/mnt/c/Users/Administrator/AppData/Local/Programs/Ollama/ollama.exe',
    'powershell': '/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe', 'wslpath': shutil.which('wslpath')}
bindings = {key: {'path': path, 'sha256': a.digest(path)} for key, path in tools.items()}
toolpath = out / 'tool-bindings.json'
toolpath.write_text(json.dumps(bindings, indent=2) + '\n')
samples = [{'path': 'reports/unified-media/dev-image.png', 'sha256': a.digest(ROOT / 'reports/unified-media/dev-image.png')}]
childpath = out / 'authorization.json'
request = dict(kind='LVW_BOUNDED_CHILD/1', argv=['/usr/bin/python3', '-B', str(BASE / 'live_harness_v6.py'), str(childpath)],
    cwd=str(ROOT), environment={'PATH': '/usr/bin:/bin:/usr/lib/wsl/lib', 'HOME': '/home/administrator', 'LANG': 'C.UTF-8',
    'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONPATH': str(ROOT) + ':' + str(ROOT / 'lvw/backend'),
    'LVW_DATA_ROOT': str(data), 'TMPDIR': str(private), 'LVW_AUTHORIZATION_CHILD': str(childpath), 'LVW_REQUIRE_BUDGET': '1'},
    output_dir=str(out / 'controller'), wall_seconds=290, term_grace_seconds=.5, kill_grace_seconds=1)
(out / 'request.json').write_text(json.dumps(request, indent=2) + '\n')
(BASE / 'root-ack-live02.json').write_text(json.dumps(dict(root_ack=True, candidate_sha=sha, run_id=run,
    samples=samples, budget=budget, max_seconds=360, request=request, source_hashes=frozen, tool_bindings=bindings,
    controller_sha256=a.digest(ROOT / 'reports/workflow-rebaseline-2026-11-15/opt-b-14-trusted-stop-cancel/bounded_exec.py'),
    scope='Native job correction root reviewed, CPU120/backend274 and Win32 kernel probe passed. Independent post-live review pending. Main paused; original failed run retained. No Stage189/29 or human signature. Finite one preload and one image,2 native generations only.'), indent=2) + '\n')
a.reserve(run, 'R1', budget, 360, full=False)
issued = time.time()
child = dict(kind='RESOURCE_CLEANUP_V6_LOADED_CHILD/1', run_id=run, stage_id='R1', program=a.COMPLETE_APPROVAL,
    program_sha256=a.digest(ROOT / a.COMPLETE_APPROVAL), budget_ledger=str(a.LEDGER), candidate_sha=sha, fixture=False,
    private_root=str(private), private_identity=identity(private), private_marker=marker, data_root=str(data), data_identity=identity(data),
    port=18898, chromium_executable=tools['chromium'], budget=budget, frozen_files=frozen, samples=samples,
    model_tag='gemma4:26b', model_digest='5571076f3d70050487b26b341705799e0ab29b808164f90d20d4cf84f699d251',
    harness_sha256=a.digest(BASE / 'live_harness_v6.py'), issued_at=issued, expires_at=issued + 350, root_ack=True,
    execution_bindings_required=True, cleanup='Original private job per generation; independent earlier nonce/PID/birth/wrapper; job empty and resources proven, unknown retained; no recursive deletion')
childpath.write_text(json.dumps(child, indent=2) + '\n')
a.bind(run, childpath)
a.bind_execution(run, toolpath)
print(json.dumps({'sealed': run, 'candidate': sha, 'budget': budget}))
