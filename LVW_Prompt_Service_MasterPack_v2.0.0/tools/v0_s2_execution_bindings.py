"""Finite installed-code seals for a complete, already-authorized Stage child.

No discovery, CLI, process launch or implicit authorization. The parent supplies
the exact declared roots and files, calls capture before startup, and performs
full verification outside browser RPC deadlines. Short RPC guards check only
explicit critical files; they never claim to rehash the complete dependency set.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

from tools.v0_s2_checkpoint_oracles import EvidenceError


@dataclass(frozen=True)
class Tree:
    root: Path
    excluded_roots: tuple = ()


def plain(path):
    path = Path(path)
    if not path.is_absolute(): raise EvidenceError('binding path must be absolute')
    for current in (path, *path.parents):
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise EvidenceError('binding redirect forbidden')
    if path.resolve(strict=True) != path: raise EvidenceError('binding path is not canonical')
    return path


def stamp(path):
    info = Path(path).lstat()
    if not stat.S_ISREG(info.st_mode): raise EvidenceError('binding is not an ordinary file')
    return identity(info)


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def hashed_file(path, before, deadline, *, write=None):
    """Open each ancestor without following links, then pin the file descriptor."""
    directories = []; file_descriptor = None
    try:
        directories.append(os.open('/', os.O_RDONLY | os.O_DIRECTORY))
        for part in path.parts[1:-1]:
            directories.append(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directories[-1]))
            if getattr(os.fstat(directories[-1]), 'st_file_attributes', 0) & 0x400:
                raise EvidenceError('binding ancestor reparse forbidden')
        file_descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directories[-1])
        info = os.fstat(file_descriptor)
        if not stat.S_ISREG(info.st_mode) or identity(info) != before:
            raise EvidenceError('binding file replaced before open')
        digest = hashlib.sha256(); observed = 0
        while data := os.read(file_descriptor, 1024*1024):
            observed += len(data)
            if observed > before[2] or time.monotonic() > deadline:
                raise EvidenceError('binding changed/time budget exceeded')
            if write is not None: write(data)
            digest.update(data)
        if observed != before[2] or identity(os.fstat(file_descriptor)) != before:
            raise EvidenceError('binding descriptor changed during hash')
        return digest.hexdigest(), observed
    finally:
        if file_descriptor is not None: os.close(file_descriptor)
        for descriptor in reversed(directories): os.close(descriptor)


class ExecutionBindings:
    def __init__(self, *, trees, files, authorize, max_files=100_000,
                 max_bytes=32*1024**3, max_entries=150_000, max_seconds=1800):
        if (not callable(authorize) or not trees or not files
                or set(trees) & set(files) or any(not re.fullmatch('[A-Z][A-Z0-9_]{0,47}', key) for key in (*trees, *files))
                or any(type(value) is not int or value <= 0 for value in (max_files, max_bytes, max_entries, max_seconds))):
            raise ValueError('finite declared bindings and authorization required')
        for tree in trees.values():
            if (not isinstance(tree, Tree) or not isinstance(tree.excluded_roots, tuple)
                    or len(set(tree.excluded_roots)) != len(tree.excluded_roots)
                    or any(not isinstance(name, str) or '/' in name or '\\' in name
                    or name in ('', '.', '..') for name in tree.excluded_roots)):
                raise ValueError('only explicitly excluded top-level roots are supported')
        self.trees = dict(trees); self.files = {key: Path(value) for key, value in files.items()}
        self.authorize = authorize; self.max_files = max_files; self.max_bytes = max_bytes
        self.max_entries = max_entries; self.max_seconds = max_seconds
        self.seal = None; self.paths = {}; self.stamps = {}; self.used = False

    def _inventory(self, deadline):
        paths = {}; visited = 0
        def budget():
            nonlocal visited
            visited += 1
            if visited > self.max_entries or time.monotonic() > deadline:
                raise EvidenceError('binding traversal/time budget exceeded')
        for alias, tree in sorted(self.trees.items()):
            root = plain(tree.root)
            if not root.is_dir(): raise EvidenceError('binding root is not a directory')
            stack = [(root, ())]
            while stack:
                directory, parts = stack.pop()
                plain(directory)
                with os.scandir(directory) as entries:
                    for entry in entries:
                        budget()
                        if not parts and entry.name in tree.excluded_roots: continue
                        path = Path(entry.path); info = entry.stat(follow_symlinks=False)
                        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                            raise EvidenceError('binding tree redirect forbidden')
                        child = parts+(entry.name,)
                        if stat.S_ISDIR(info.st_mode): stack.append((path, child))
                        elif stat.S_ISREG(info.st_mode): paths[alias+'/'+('/'.join(child))] = path
                        else: raise EvidenceError('binding tree special entry forbidden')
                        if len(paths) > self.max_files: raise EvidenceError('binding file budget exceeded')
        for alias, value in self.files.items():
            budget(); paths[alias] = plain(value)
        if len(paths) > self.max_files: raise EvidenceError('binding file budget exceeded')
        return dict(sorted(paths.items()))

    def _snapshot(self):
        deadline = time.monotonic()+self.max_seconds
        paths = self._inventory(deadline); rows = []; states = {}; total = 0
        for alias, path in paths.items():
            plain(path)
            before = stamp(path); total += before[2]
            if total > self.max_bytes: raise EvidenceError('binding byte budget exceeded')
            digest, observed = hashed_file(path, before, deadline)
            plain(path)
            if stamp(path) != before:
                raise EvidenceError('binding file changed during hashing')
            states[alias] = before
            rows.append({'alias': alias, 'bytes': observed, 'sha256': digest})
        # Detect inventory additions, removals and replacements during hashing.
        if self._inventory(deadline) != paths or any(stamp(path) != states[alias] for alias, path in paths.items()):
            raise EvidenceError('binding inventory changed during hashing')
        canonical = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()
        return {'kind': 'INSTALLED_EXECUTION_BYTE_BINDINGS_NOT_ACCEPTANCE', 'files': rows,
            'bytes_hashed': total, 'manifest_sha256': hashlib.sha256(canonical).hexdigest(),
            'excluded_top_level_roots': {alias: list(tree.excluded_roots) for alias, tree in sorted(self.trees.items())},
            'stage_pass_claim': False}, paths, states

    def capture(self):
        if self.used: raise EvidenceError('binding capture is one-shot')
        self.used = True
        self.authorize('capture_installed_execution_bindings', None)
        self.seal, self.paths, self.stamps = self._snapshot()
        return json.loads(json.dumps(self.seal))

    def verify(self):
        if self.seal is None: raise EvidenceError('binding capture is incomplete')
        self.authorize('verify_complete_installed_execution_bindings', None)
        current, paths, states = self._snapshot()
        if current != self.seal or paths != self.paths or states != self.stamps:
            raise EvidenceError('sealed installed execution bytes or identity changed')
        return {'manifest_sha256': self.seal['manifest_sha256'], 'complete_rehash': True}

    def guard(self, aliases):
        """Bounded critical-file guard, explicitly not a full tree verification."""
        if self.seal is None or not aliases or len(aliases) > 32 or len(set(aliases)) != len(aliases):
            raise EvidenceError('binding critical guard set invalid')
        self.authorize('guard_critical_execution_files', list(aliases))
        expected = {row['alias']: row for row in self.seal['files']}
        total = 0; deadline = time.monotonic()+15
        for alias in aliases:
            if alias not in self.paths: raise EvidenceError('critical file not sealed')
            path = plain(self.paths[alias]); before = stamp(path); total += before[2]
            if total > 1024**3: raise EvidenceError('critical guard byte budget exceeded')
            if before != self.stamps[alias]: raise EvidenceError('critical file identity changed')
            digest, observed = hashed_file(path, before, deadline)
            plain(path)
            if (observed != before[2] or stamp(path) != before or digest != expected[alias]['sha256']):
                raise EvidenceError('critical file bytes changed')
        return {'manifest_sha256': self.seal['manifest_sha256'], 'complete_rehash': False, 'critical_files': list(aliases)}
