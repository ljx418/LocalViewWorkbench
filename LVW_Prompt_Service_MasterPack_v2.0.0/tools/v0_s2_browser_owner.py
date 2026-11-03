"""Independent Linux browser ownership witnesses, with no launch/kill/delete.

Only call from the sealed parent's authorized browser handlers. These functions
read process/executable/profile facts; they do not grant permission themselves.
"""
import hashlib
import os
from pathlib import Path
import re
import stat

from tools.v0_s2_checkpoint_oracles import EvidenceError


def birth(pid):
    if type(pid) is not int or pid <= 0: raise EvidenceError('invalid browser PID')
    value = Path(f'/proc/{pid}/stat').read_text()
    fields = value[value.rfind(')')+2:].split()
    return {'pid': pid, 'state': fields[0], 'parent': int(fields[1]), 'group': int(fields[2]),
        'session': int(fields[3]), 'start_ticks': fields[19]}


def executable(path, *, kernel=False):
    path = Path(path)
    if kernel and not re.fullmatch('/proc/[1-9][0-9]*/exe', str(path)):
        raise EvidenceError('invalid kernel executable reference')
    fd = os.open(path, os.O_RDONLY | (0 if kernel else os.O_NOFOLLOW))
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or not 4 <= before.st_size <= 1024*1024*1024:
            raise EvidenceError('invalid browser executable size/type')
        digest, size, header = hashlib.sha256(), 0, b''
        while True:
            raw = os.read(fd, 65536)
            if not raw: break
            if not header: header = raw[:4]
            size += len(raw)
            if size > before.st_size: raise EvidenceError('browser executable grew')
            digest.update(raw)
        after = os.fstat(fd)
        keys = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        if size != before.st_size or header != b'\x7fELF' or any(getattr(before, k) != getattr(after, k) for k in keys):
            raise EvidenceError('browser executable changed/not ELF')
        return {'sha256': digest.hexdigest(), 'bytes': size}
    finally: os.close(fd)


def profile_baseline(temporary_root):
    root = Path(temporary_root)
    if root.resolve(strict=True) != root: raise EvidenceError('temporary root is not canonical')
    entries = list(root.iterdir())
    if len(entries) > 8192: raise EvidenceError('temporary directory catalog limit')
    # Retain only public auto-generated names/inodes, never profile contents.
    rows = {}
    for path in entries:
        if path.name.startswith('playwright_chromiumdev_profile-'):
            info = path.lstat()
            rows[path.name] = {'inode': info.st_ino, 'device': info.st_dev}
    return rows


def verify_driver_listener(worker_birth, port):
    """Bind the ephemeral Playwright control listener before its first client."""
    if type(port) is not int or not 1024 <= port <= 65535 or port in (8191, 11434, 18765):
        raise EvidenceError('browser driver port outside ephemeral control policy')
    worker = birth(worker_birth['pid'])
    if worker['state'] == 'Z' or any(worker[key] != worker_birth[key] for key in ('pid', 'parent', 'group', 'session', 'start_ticks')):
        raise EvidenceError('browser driver original worker changed')
    descriptors = list(Path(f"/proc/{worker['pid']}/fd").iterdir())
    if len(descriptors) > 4096: raise EvidenceError('browser driver fd catalog limit')
    sockets = set()
    for descriptor in descriptors:
        try: target = os.readlink(descriptor)
        except FileNotFoundError: continue
        match = re.fullmatch(r'socket:\[([0-9]+)\]', target)
        if match: sockets.add(match[1])
    raw = Path(f"/proc/{worker['pid']}/net/tcp").read_bytes()
    if len(raw) > 2*1024**2: raise EvidenceError('browser driver TCP catalog limit')
    lines = raw.decode('ascii', 'strict').splitlines()
    if len(lines) > 8193: raise EvidenceError('browser driver TCP row limit')
    matches = []
    for line in lines[1:]:
        fields = line.split()
        if len(fields) < 10: raise EvidenceError('browser driver TCP row malformed')
        if fields[3] == '0A' and fields[1] == f'0100007F:{port:04X}' and fields[9] in sockets:
            matches.append(fields[9])
    after = birth(worker['pid'])
    if len(matches) != 1 or after['state'] == 'Z' or any(after[key] != worker[key] for key in ('pid', 'parent', 'group', 'session', 'start_ticks')):
        raise EvidenceError('browser driver listener is not the original worker-owned loopback socket')
    return {'address': '127.0.0.1', 'port': port, 'socket_inode': matches[0], 'worker_birth': worker,
        'proven_before_connect': True, 'stage_pass_claim': False}


def verify_owner(claim, *, worker_birth, browser_executable, expected_sha256, temporary_root, before_profiles):
    """Join worker claims with live kernel facts and a prelaunch profile catalog."""
    try:
        if not isinstance(before_profiles, dict) or not re.fullmatch('[a-f0-9]{64}', expected_sha256):
            raise ValueError('missing prelaunch identity')
        worker = birth(worker_birth['pid'])
        if any(worker[k] != worker_birth[k] for k in ('pid', 'parent', 'group', 'session', 'start_ticks')):
            raise ValueError('worker original identity changed')
        actual = birth(claim['pid'])
        if (actual['state'] == 'Z' or actual['parent'] != worker['pid'] or actual['group'] != actual['pid']
                or actual['session'] != actual['pid'] or int(actual['start_ticks']) < int(worker['start_ticks'])
                or any(actual[k] != claim[k] for k in ('pid', 'parent', 'group', 'session', 'start_ticks'))):
            raise ValueError('not the original isolated worker child')
        target = Path(browser_executable)
        if target.resolve(strict=True) != target or Path(f"/proc/{actual['pid']}/exe").resolve(strict=True) != target:
            raise ValueError('running browser executable path mismatch')
        file_proof = executable(target)
        kernel_proof = executable(f"/proc/{actual['pid']}/exe", kernel=True)
        if file_proof != kernel_proof or file_proof['sha256'] != expected_sha256 or claim['executable_sha256'] != expected_sha256:
            raise ValueError('running browser executable bytes mismatch')
        name = claim['profile_relative_name']
        if not isinstance(name, str) or not re.fullmatch('playwright_chromiumdev_profile-[A-Za-z0-9_-]{1,96}', name) or name in before_profiles:
            raise ValueError('profile is not a fresh auto-created name')
        temporary = Path(temporary_root)
        if temporary.resolve(strict=True) != temporary: raise ValueError('temporary root changed')
        profile = temporary/name
        info = profile.lstat()
        if (not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode) or info.st_uid != os.getuid()
                or type(claim['profile_inode']) is not int or type(claim['profile_device']) is not int
                or info.st_ino != claim['profile_inode'] or info.st_dev != claim['profile_device']):
            raise ValueError('profile ownership/inode mismatch')
        # Verify actual launch args rather than accepting a fresh unrelated dir.
        raw = Path(f"/proc/{actual['pid']}/cmdline").read_bytes()
        if len(raw) > 65536 or raw.split(b'\0').count(os.fsencode('--user-data-dir='+str(profile))) != 1:
            raise ValueError('profile not bound to running browser command')
        after = birth(actual['pid'])
        if any(after[k] != actual[k] for k in ('pid', 'parent', 'group', 'session', 'start_ticks')) or after['state'] == 'Z':
            raise ValueError('browser original changed during verification')
        return {'kind': 'INDEPENDENT_BROWSER_OWNER_NOT_ACCEPTANCE', 'original_birth': actual,
            'worker_birth': worker, 'executable': kernel_proof, 'profile_relative_name': name,
            'profile_inode': info.st_ino, 'profile_device': info.st_dev, 'stage_pass_claim': False}
    except (KeyError, TypeError, ValueError, OSError) as error:
        raise EvidenceError('browser ownership unproven: '+str(error)) from error


def cleanup_witness(owner, *, temporary_root):
    """Read facts only. A reused PID is never killed; unrelated profiles stay."""
    original = owner['original_birth']
    try:
        current = birth(original['pid'])
        absent = current['start_ticks'] != original['start_ticks']
    except (FileNotFoundError, ProcessLookupError): absent = True
    entries = [p for p in Path('/proc').iterdir() if p.name.isdigit()]
    if len(entries) > 8192: raise EvidenceError('browser process catalog limit')
    group = []
    for path in entries:
        try:
            value = birth(int(path.name))
            if value['group'] == original['group']: group.append(value)
        except (FileNotFoundError, ProcessLookupError): continue
    if len(group) > 64: raise EvidenceError('browser process group limit')
    temporary = Path(temporary_root)
    if temporary.resolve(strict=True) != temporary: raise EvidenceError('temporary root changed during cleanup')
    profile = temporary/owner['profile_relative_name']
    profile_absent = not profile.exists() and not profile.is_symlink()
    return {'browser_original_absent': absent, 'group_empty': not group, 'profile_absent': profile_absent,
        'decision': 'BROWSER_CLEANUP_PROVEN' if absent and not group and profile_absent else 'NO_GO',
        'stage_pass_claim': False}
