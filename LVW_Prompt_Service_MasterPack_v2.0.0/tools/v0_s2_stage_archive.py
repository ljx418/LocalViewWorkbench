"""Archive raw run-owned evidence before removing a proven terminal S2 root.

No CLI, authorization or process termination. Registered fresh roots only.
Inputs and deployed code are represented by the parent's frozen bindings rather
than copied again (in particular the deliberately oversized negative fixture).
Raw output stays in the child's controlled evidence directory. Public/log
redaction and independent review remain the complete parent executor's duties.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

from tools.v0_s2_execution_bindings import plain, stamp, hashed_file
from tools.v0_s2_checkpoint_oracles import EvidenceError


class OwnedArchive:
    def __init__(self, directory, *, run_id, candidate_sha, authorization_sha256, authorize,
                 max_files=4096, max_file_bytes=32*1024**2, max_bytes=512*1024**2):
        if (not re.fullmatch('[A-Za-z0-9][A-Za-z0-9._-]{0,79}', run_id)
                or not re.fullmatch('[a-f0-9]{40}', candidate_sha)
                or not re.fullmatch('[a-f0-9]{64}', authorization_sha256) or not callable(authorize)
                or any(type(v) is not int or v <= 0 for v in (max_files, max_file_bytes, max_bytes))):
            raise ValueError('archive finite identity/authorization required')
        self.directory = Path(directory); self.run_id = run_id; self.candidate = candidate_sha
        self.auth = authorization_sha256; self.authorize = authorize; self.leases = {}; self.used = set()
        self.max_files = max_files; self.max_file_bytes = max_file_bytes; self.max_bytes = max_bytes

    def register(self, root, label):
        if label not in ('default', 'warm') or label in self.leases: raise EvidenceError('archive root lease replay/label')
        self.authorize('register_fresh_archive_root', label)
        root = plain(root)
        if not root.is_dir() or list(root.iterdir()): raise EvidenceError('archive lease requires a fresh empty root')
        directory = plain(self.directory)
        if directory == root or directory.is_relative_to(root): raise EvidenceError('archive destination is inside run root')
        info = root.lstat()
        record = {'kind': 'FRESH_OWNED_ROOT_IDENTITY_NOT_ACCEPTANCE', 'run_id': self.run_id,
            'candidate_sha': self.candidate, 'authorization_sha256': self.auth,
            'label': label, 'root': str(root), 'device': str(info.st_dev), 'inode': str(info.st_ino),
            'registered_wall_seconds': time.time(), 'stage_pass_claim': False}
        # Persist before population. Recovery must never invent the original
        # identity by adopting whatever happens to occupy a historical path.
        with (directory/(label+'-root-lease.json')).open('xb') as output:
            output.write((json.dumps(record, sort_keys=True)+'\n').encode()); output.flush(); os.fsync(output.fileno())
        self.leases[label] = (root, info.st_dev, info.st_ino)

    def lease(self, label):
        root, device, inode = self.leases[label]; plain(root); info = root.lstat()
        if not stat.S_ISDIR(info.st_mode) or (info.st_dev, info.st_ino) != (device, inode):
            raise EvidenceError('archive root identity changed')
        return root

    def inventory(self, root, *, exclusions):
        rows = {}; directories = []; stack = [root]; visited = 0
        while stack:
            directory = stack.pop(); plain(directory); directories.append(directory)
            with os.scandir(directory) as entries:
                for entry in entries:
                    visited += 1
                    if visited > 8192: raise EvidenceError('archive entry budget exceeded')
                    path = Path(entry.path); relative = path.relative_to(root).as_posix()
                    if exclusions and directory == root and entry.name in ('input', 'custom_nodes'): continue
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400 or path.resolve() != path:
                        # The one declared path-security fixture is removed as a
                        # link, never followed. No other redirect is accepted.
                        if (not exclusions and relative == 'input/redirect'
                                and path.resolve(strict=True) == root/'outside-input'):
                            rows[relative] = ('redirect', path, None)
                            continue
                        raise EvidenceError('archive unexpected redirect')
                    if stat.S_ISDIR(info.st_mode): stack.append(path)
                    elif stat.S_ISREG(info.st_mode): rows[relative] = ('file', path, stamp(path))
                    else: raise EvidenceError('archive special entry forbidden')
                    if len(rows) > self.max_files: raise EvidenceError('archive file budget exceeded')
        return dict(sorted(rows.items())), sorted(directories, key=lambda p: len(p.parts), reverse=True)

    def __call__(self, context, cleanup):
        matches = [label for label, lease in self.leases.items() if lease[0] == context.root]
        if len(matches) != 1 or matches[0] in self.used: raise EvidenceError('archive unknown or consumed root')
        label = matches[0]
        if (context.binding.get('candidate_sha') != self.candidate
                or context.binding.get('authorization_sha256') != self.auth
                or context.binding.get('run_id', self.run_id) != self.run_id):
            raise EvidenceError('archive context identity mismatch')
        # A failed prelude can own zero or one service. The original runtime's
        # recorded handles/proofs, rather than invented empty cleanup rows,
        # define that denominator. Normal default/warm contexts own both.
        ports = set(context.driver.listener_proofs)
        owned = len(context.driver.owned)
        if (cleanup.get('proven') is not True or cleanup.get('final_target_listener_count') != 0
                or cleanup.get('owned_count') != owned
                or any(cleanup.get('http_workers_pending', {}).values())
                or not ports.issubset({8191, 11434})
                or len(cleanup.get('owned_listener_terminal_states', [])) != len(ports)
                or {row.get('port') for row in cleanup.get('owned_listener_terminal_states', [])} != ports
                or any(row.get('terminal_absent') is not True or row.get('unknown_descendants_absent') is not True
                    for row in cleanup['owned_listener_terminal_states'])
                or len(cleanup.get('owned_wrapper_terminal_states', [])) != owned
                or any(row.get('exited') is not True or row.get('native_wrapper_absent') is not True
                    for row in cleanup['owned_wrapper_terminal_states'])):
            raise EvidenceError('archive requires terminal native roots/wrappers/HTTP workers')
        self.authorize('archive_owned_terminal_root', label)
        root = self.lease(label); plain(self.directory)
        self.used.add(label)
        reparse_cleanup = None
        if getattr(context.driver, 'evidence', {}).get('reparse_fixture_creation_attempted'):
            self.authorize('remove_owned_terminal_reparse_fixture', label)
            reparse_cleanup = context.driver.remove_owned_reparse_fixture(root)
            if reparse_cleanup.get('proven') is not True: raise EvidenceError('native junction cleanup unproven')
        destination = self.directory/(label+'-raw'); destination.mkdir(exist_ok=False)
        before, _ = self.inventory(root, exclusions=True); records = []; total = 0
        deadline = time.monotonic()+120
        for relative, (kind, source, observed) in before.items():
            if kind != 'file': raise EvidenceError('archive redirect cannot be copied')
            total += observed[2]
            if observed[2] > self.max_file_bytes or total > self.max_bytes:
                raise EvidenceError('archive byte budget exceeded; preserve source root')
            target = destination/relative; target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('xb') as output:
                digest, count = hashed_file(source, observed, deadline, write=output.write)
                output.flush(); os.fsync(output.fileno())
            if stamp(source) != observed: raise EvidenceError('archive source changed during copy')
            copied_digest, copied_count = hashed_file(target, stamp(target), deadline)
            if (copied_digest, copied_count) != (digest, count): raise EvidenceError('archive copy verification failed')
            records.append({'file': relative, 'bytes': count, 'sha256': digest})
        after, _ = self.inventory(root, exclusions=True)
        if after != before: raise EvidenceError('archive source inventory changed')
        manifest = {'kind': 'BOUND_RAW_STAGE_ARTIFACT_ARCHIVE_NOT_ACCEPTANCE', 'run_id': self.run_id,
            'candidate_sha': self.candidate, 'authorization_sha256': self.auth, 'label': label,
            'files': records, 'excluded_trees': ['input', 'custom_nodes'],
            'excluded_tree_reason': 'fixed input hashes and deployed code belong to complete parent bindings',
            'cleanup': cleanup, 'owned_reparse_cleanup': reparse_cleanup, 'stage_pass_claim': False}
        raw = (json.dumps(manifest, ensure_ascii=False, separators=(',', ':'))+'\n').encode()
        manifest_path = destination/'ARCHIVE_MANIFEST.json'
        if manifest_path.exists(): raise EvidenceError('archive reserved manifest path occupied')
        with manifest_path.open('xb') as output: output.write(raw); output.flush(); os.fsync(output.fileno())
        if manifest_path.read_bytes() != raw: raise EvidenceError('archive manifest bytes changed')
        # Validate ALL source entries, including excluded fixtures/deployed code,
        # before beginning deletion; no blanket recursive delete follows links.
        all_files, directories = self.inventory(self.lease(label), exclusions=False)
        for relative, (kind, path, observed) in all_files.items():
            self.lease(label)
            if kind == 'redirect':
                if path.is_symlink(): path.unlink()
                else: path.rmdir()  # Native directory junction: remove link only.
            else:
                plain(path)
                if stamp(path) != observed: raise EvidenceError('archive cleanup source changed')
                path.unlink()
        for directory in directories:
            self.lease(label); plain(directory); directory.rmdir()
        return {'proven': not root.exists(), 'run_id': self.run_id, 'candidate_sha': self.candidate,
            'authorization_sha256': self.auth, 'manifest_sha256': hashlib.sha256(raw).hexdigest(),
            'manifest_file': label+'-raw/ARCHIVE_MANIFEST.json', 'files': len(records), 'bytes': total,
            'stage_pass_claim': False}
