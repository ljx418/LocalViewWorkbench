"""Finite installed-code seals for a complete, already-authorized Stage child.

No discovery, CLI, process launch or implicit authorization. The parent supplies
the exact declared roots and files, calls capture before startup, and performs
full verification outside browser RPC deadlines. Short RPC guards check only
explicit critical files; they never claim to rehash the complete dependency set.
"""
from contextlib import contextmanager
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


@contextmanager
def directory_handle(path):
    """Pin every ancestor without following links; close all handles on failure."""
    path = Path(path)
    if not path.is_absolute() or any(part in ('.', '..') for part in path.parts):
        raise EvidenceError('binding directory must be canonical and absolute')
    directories = []
    try:
        directories.append(os.open('/', os.O_RDONLY | os.O_DIRECTORY))
        for part in path.parts[1:]:
            directories.append(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directories[-1]))
            if getattr(os.fstat(directories[-1]), 'st_file_attributes', 0) & 0x400:
                raise EvidenceError('binding ancestor reparse forbidden')
        yield directories[-1]
    finally:
        for descriptor in reversed(directories): os.close(descriptor)


def hashed_at(directory, name, before, deadline, *, write=None):
    """Read an ordinary file relative to an already pinned, authorized parent."""
    if time.monotonic() > deadline: raise EvidenceError('binding hash time budget exceeded')
    descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or identity(info) != before:
            raise EvidenceError('binding file replaced before open')
        digest = hashlib.sha256(); observed = 0
        while True:
            if time.monotonic() > deadline: raise EvidenceError('binding hash time budget exceeded')
            data = os.read(descriptor, 1024*1024)
            if not data: break
            observed += len(data)
            if observed > before[2]: raise EvidenceError('binding file exceeded declared size')
            if write is not None: write(data)
            digest.update(data)
        if observed != before[2] or identity(os.fstat(descriptor)) != before:
            raise EvidenceError('binding descriptor changed during hash')
        return digest.hexdigest(), observed
    finally:
        os.close(descriptor)


def hashed_file(path, before, deadline, *, write=None):
    """One-file reader for bounded copies and critical-file guards."""
    with directory_handle(path.parent) as directory:
        return hashed_at(directory, path.name, before, deadline, write=write)


class ExecutionBindings:
    def __init__(self, *, trees, files, authorize, max_files=100_000,
                 max_bytes=32*1024**3, max_entries=150_000, max_seconds=1800, observe=None):
        if (not callable(authorize) or (observe is not None and not callable(observe)) or not trees or not files
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
        self.observe = observe or (lambda value: None); self.snapshot_number = 0

    def _inventory(self, deadline, observe=None):
        paths = {}; states = {}; directories = {}; visited = 0; last_report = time.monotonic()
        def budget():
            nonlocal visited, last_report
            visited += 1
            if visited > self.max_entries or time.monotonic() > deadline:
                raise EvidenceError('binding traversal/time budget exceeded')
            if observe is not None and time.monotonic()-last_report >= 5:
                observe(visited, len(paths)); last_report = time.monotonic()
        def walk(alias, root, directory, parts, excluded):
            directories[alias+'/'+('/'.join(parts))] = identity(os.fstat(directory))
            with os.scandir(directory) as entries:
                for entry in entries:
                    budget()
                    if not parts and entry.name in excluded: continue
                    info = entry.stat(follow_symlinks=False)
                    if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
                        raise EvidenceError('binding tree redirect forbidden')
                    child = parts+(entry.name,); key = alias+'/'+('/'.join(child))
                    if stat.S_ISDIR(info.st_mode):
                        child_fd = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                        try:
                            if identity(os.fstat(child_fd)) != identity(info):
                                raise EvidenceError('binding directory changed before traversal')
                            walk(alias, root, child_fd, child, excluded)
                        finally: os.close(child_fd)
                    elif stat.S_ISREG(info.st_mode):
                        paths[key] = root.joinpath(*child); states[key] = identity(info)
                    else: raise EvidenceError('binding tree special entry forbidden')
                    if len(paths) > self.max_files: raise EvidenceError('binding file budget exceeded')
        for alias, tree in sorted(self.trees.items()):
            root = plain(tree.root)
            with directory_handle(root) as directory:
                walk(alias, root, directory, (), tree.excluded_roots)
        for alias, value in self.files.items():
            budget(); path = plain(value); paths[alias] = path; states[alias] = stamp(path)
        if len(paths) > self.max_files: raise EvidenceError('binding file budget exceeded')
        return dict(sorted(paths.items())), states, directories

    def _snapshot(self):
        started = time.monotonic(); deadline = started+self.max_seconds
        self.snapshot_number += 1
        progress = {'snapshot': self.snapshot_number, 'phase': 'inventory', 'files_hashed': 0, 'bytes_hashed': 0}
        def report():
            self.observe({**progress, 'elapsed_seconds': time.monotonic()-started})
        report()
        try:
            def inventory_progress(entries, files):
                progress.update(inventory_entries=entries, inventory_files=files); report()
            paths, states, directories = self._inventory(deadline, inventory_progress)
            progress.update(phase='hash', files_total=len(paths))
            report()
            groups = {}
            for alias, path in paths.items(): groups.setdefault(path.parent, []).append((alias, path))
            rows = []; total = 0; last_report = time.monotonic()
            for parent, entries in groups.items():
                # Ancestors are pinned once per parent, rather than repeatedly
                # resolving the complete NTFS path for every ordinary file.
                with directory_handle(parent) as directory:
                    for alias, path in entries:
                        progress['current_alias'] = alias
                        before = states[alias]; total += before[2]
                        if total > self.max_bytes: raise EvidenceError('binding byte budget exceeded')
                        digest, observed = hashed_at(directory, path.name, before, deadline)
                        rows.append({'alias': alias, 'bytes': observed, 'sha256': digest})
                        progress.update(files_hashed=len(rows), bytes_hashed=total)
                        if time.monotonic()-last_report >= 5:
                            report(); last_report = time.monotonic()
            progress['phase'] = 'verify_inventory'; report()
            # The second descriptor traversal verifies all original file AND
            # directory identities, additions/removals and metadata changes.
            if self._inventory(deadline, inventory_progress) != (paths, states, directories):
                raise EvidenceError('binding inventory changed during hashing')
            rows.sort(key=lambda row: row['alias'])
            canonical = json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()
            progress['phase'] = 'complete'; report()
            return {'kind': 'INSTALLED_EXECUTION_BYTE_BINDINGS_NOT_ACCEPTANCE', 'files': rows,
                'bytes_hashed': total, 'manifest_sha256': hashlib.sha256(canonical).hexdigest(),
                'excluded_top_level_roots': {alias: list(tree.excluded_roots) for alias, tree in sorted(self.trees.items())},
                'stage_pass_claim': False}, paths, states
        except BaseException as error:
            progress.update(phase='failed', error_code=type(error).__name__+':'+str(error))
            report()
            raise

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
