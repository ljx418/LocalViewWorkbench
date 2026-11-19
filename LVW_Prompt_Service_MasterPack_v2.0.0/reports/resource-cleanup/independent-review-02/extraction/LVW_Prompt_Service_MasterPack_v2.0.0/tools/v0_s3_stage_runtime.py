"""Installed-package deployment for the inherited native runtime lifecycle.

Explicit opt-in only: this does not implement S3 budgets, network isolation,
quality acceptance or rollback acceptance. No service or package CLI is launched.
"""
import copy
import os
import stat
import secrets
from contextlib import ExitStack, contextmanager
import re
import time
from pathlib import Path
from types import SimpleNamespace

from tools import v0_incremental_package as package
from tools.v0_s2_stage_runtime import StageRuntimeFactory
from tools.v0_s2_execution_bindings import plain, stamp, hashed_file, directory_handle
from tools.v0_s2_checkpoint_oracles import EvidenceError


def _digest(path, limit):
    path = plain(path)
    before = stamp(path)
    if before[2] > limit:
        raise EvidenceError('installed deployment file exceeds bounded read limit')
    digest, size = hashed_file(path, before, time.monotonic() + 30)
    if stamp(path) != before:
        raise EvidenceError('installed deployment file changed during read')
    return digest, size


class _ArchiveCleanupBoundary:
    """Guard the one native cleanup callback used by OwnedArchive."""
    def __init__(self, driver, factory):
        self.driver = driver
        self.factory = factory
        self.evidence = driver.evidence
        self.listener_proofs = driver.listener_proofs
        self.owned = driver.owned

    def remove_owned_reparse_fixture(self, root):
        self.factory._preparation_guard()
        result = self.driver.remove_owned_reparse_fixture(root)
        self.factory._preparation_guard()
        return result


class _DeploymentArchive:
    """Retain failed protected installs; never delete via uncertain pathnames."""
    def __init__(self, original, factory):
        self.original = original
        self.factory = factory
        self.retained = set()

    def register(self, root, label):
        self.factory._preparation_guard()
        result = self.original.register(root, label, _parent_fd=self.factory._parent_fd,
                                        _root_fd=self.factory._root_fds[label][0])
        self.factory._pin_preparation_root(root, label)
        return result

    def lease(self, label):
        return self.original.lease(label)

    def __call__(self, context, cleanup):
        if context.root in self.retained:
            raise EvidenceError('failed protected deployment retained; pathname archive deletion forbidden')
        with self.factory._archive_lifecycle(context):
            archive_context = SimpleNamespace(root=context.root, binding=context.binding,
                driver=_ArchiveCleanupBoundary(context.driver, self.factory))
            return self.original(archive_context, cleanup)


class InstalledPackageRuntimeFactory(StageRuntimeFactory):
    def __init__(self, *, package_path, package_sha256, manifest_sha256, **kwargs):
        super().__init__(**kwargs)
        self.package_path = Path(package_path)
        self.package_sha256 = package_sha256
        self.manifest_sha256 = manifest_sha256
        self.archive = _DeploymentArchive(self.archive, self)
        self.preparation_failures = {}
        self._parent_fd = None
        self._root_fds = {}
        self._archive_identities = {}
        self._archiving = False
        original_authorize = self.authorize
        def authorize(*args):
            self._preparation_guard()
            result = original_authorize(*args)
            self._preparation_guard()
            return result
        self.authorize = authorize
        original_archive_authorize = self.archive.original.authorize
        def archive_authorize(*args):
            # Direct legacy-owner callers retain their existing semantics;
            # the protected adapter always establishes its own active context.
            if self._parent_fd is None:
                return original_archive_authorize(*args)
            self._preparation_guard()
            result = original_archive_authorize(*args)
            self._preparation_guard()
            return result
        self.archive.original.authorize = archive_authorize

    def _preparation_guard(self):
        if self._parent_fd is None:
            raise EvidenceError('protected lifecycle descriptor unavailable')
        current = plain(self.directory).stat()
        pinned = os.fstat(self._parent_fd)
        if (current.st_dev, current.st_ino) != (pinned.st_dev, pinned.st_ino):
            raise EvidenceError('preparation parent identity drift')
        for label, (fd, name, identity) in self._root_fds.items():
            current = os.stat(name, dir_fd=self._parent_fd, follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != identity:
                raise EvidenceError('preparation root identity drift')

    def _pin_preparation_root(self, root, label):
        self._preparation_guard()
        before = plain(self.archive.original.lease(label)).stat()
        fd, name, identity = self._root_fds[label]
        if identity != (before.st_dev, before.st_ino):
            raise EvidenceError('registered root differs from allocated original identity')
        parent = os.fstat(self._parent_fd)
        self._archive_identities[label] = ((parent.st_dev, parent.st_ino), name,
            identity, self.run_id, self.candidate, self.auth)

    @contextmanager
    def _archive_lifecycle(self, context):
        if self._archiving:
            raise EvidenceError('archive lifecycle reentry')
        matches = [label for label, record in self._archive_identities.items()
                   if self.directory / record[1] == context.root]
        if len(matches) != 1:
            raise EvidenceError('archive original preparation identity unavailable')
        label = matches[0]
        parent_identity, name, identity, run_id, candidate, auth = self._archive_identities[label]
        if ((self.run_id, self.candidate, self.auth) != (run_id, candidate, auth)
                or context.binding.get('run_id', run_id) != run_id
                or context.binding.get('candidate_sha') != candidate
                or context.binding.get('authorization_sha256') != auth
                or self.archive.original.leases.get(label) != (context.root, *identity)):
            raise EvidenceError('archive preparation binding mismatch')
        active = self._parent_fd is not None
        self._archiving = True
        try:
            with ExitStack() as stack:
                if active:
                    if set(self._root_fds) != {label} or self._root_fds[label][1:] != (name, identity):
                        raise EvidenceError('archive active preparation root mismatch')
                else:
                    parent = stack.enter_context(directory_handle(self.directory))
                    info = os.fstat(parent)
                    if (info.st_dev, info.st_ino) != parent_identity:
                        raise EvidenceError('archive original parent identity drift')
                    root = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
                    stack.callback(os.close, root)
                    info = os.fstat(root)
                    if (info.st_dev, info.st_ino) != identity:
                        raise EvidenceError('archive original root identity drift')
                    self._parent_fd = parent
                    self._root_fds[label] = (root, name, identity)
                info = os.fstat(self._parent_fd)
                if (info.st_dev, info.st_ino) != parent_identity:
                    raise EvidenceError('archive active parent identity mismatch')
                self._preparation_guard()
                self.archive.original.lease(label)
                yield
                # Successful owner deletion is terminal: do not require root existence here.
        finally:
            if not active:
                self._root_fds.clear()
                self._parent_fd = None
            self._archiving = False

    def _preparation_boundary(self):
        self._preparation_guard()

    def _allocate_preparation_root(self, label):
        self._preparation_guard()
        for attempt in range(8):
            name = 'lvw-s2-' + label + '-' + secrets.token_hex(8)
            try:
                os.mkdir(name, 0o700, dir_fd=self._parent_fd)
            except FileExistsError:
                continue
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=self._parent_fd)
            self._root_fds[label] = (fd, name, (os.fstat(fd).st_dev, os.fstat(fd).st_ino))
            self._preparation_guard()
            return self.directory / name
        raise EvidenceError('protected root allocation collision budget exhausted')

    def _prepare_directories(self, root, label):
        self._preparation_guard()
        fd = self._root_fds[label][0]
        for name in ('input', 'output', 'temp', 'custom_nodes'):
            os.mkdir(name, 0o700, dir_fd=fd)
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(child)
        self._preparation_guard()

    def _persist_preparation_evidence(self, root, label, evidence):
        self._preparation_guard()
        temp = os.open('temp', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                       dir_fd=self._root_fds[label][0])
        try:
            fd = os.open('runtime-preparation.json', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=temp)
            try:
                data = memoryview(package._dump_json(evidence).encode('utf-8'))
                while data:
                    count = os.write(fd, data)
                    if count <= 0: raise OSError('preparation evidence write made no progress')
                    data = data[count:]
                os.fsync(fd)
            finally:
                os.close(fd)
        finally:
            os.close(temp)
        self._preparation_guard()

    def prepare_default(self):
        context = self._with_preparation(False)
        # Keep the inherited closures, including launch's internal verify call.
        # The identity scope itself neither invokes nor consumes the archive.
        def bounded(callback):
            def invoke(*args, **kwargs):
                with self._archive_lifecycle(context):
                    if 'default' in self.archive.original.used:
                        raise EvidenceError('returned callback root already archived')
                    result = callback(*args, **kwargs)
                    self._preparation_guard()
                    return result
            return invoke
        context.verify_bindings = bounded(context.verify_bindings)
        context.authorize_launch = bounded(context.authorize_launch)
        return context

    def prepare_warm(self):
        return self._with_preparation(True)

    def _with_preparation(self, warm):
        label = 'warm' if warm else 'default'
        # No lifecycle state is reused. Keep the evidence parent open across
        # the inherited handler, including errors after _deploy returns.
        if self._parent_fd is not None:
            raise EvidenceError('preparation lifecycle reentry')
        with ExitStack() as stack:
            try:
                self._parent_fd = stack.enter_context(directory_handle(self.directory))
                return super()._prepare(warm)
            except BaseException as error:
                if label not in self.preparation_failures:
                    failure = {'error_type': type(error).__name__, 'error': str(error),
                        'run_id': self.run_id, 'candidate_sha': self.candidate,
                        'authorization_sha256': self.auth, 'stage_pass_claim': False,
                        'evidence': self.evidence.get(label, {}), 'root_name': self._root_fds[label][1] if label in self._root_fds else None}
                    self._persist_preparation_failure(label, None, failure)
                raise
            finally:
                for fd, _, _ in self._root_fds.values():
                    os.close(fd)
                self._root_fds.clear()
                self._parent_fd = None

    def _persist_preparation_failure(self, label, root, failure):
        # This method must never replace the triggering exception.
        self.preparation_failures[label] = failure
        failure['root_retained'] = None
        failure['root_retention_observation'] = 'UNKNOWN: original root descriptor unavailable'
        try:
            if label in self._root_fds:
                fd, name, identity = self._root_fds[label]
                info = os.fstat(fd)
                if (info.st_dev, info.st_ino) == identity:
                    failure['root_retained'] = info.st_nlink > 0
                    failure['root_retention_observation'] = {
                        'basis': 'allocated original directory descriptor',
                        'archive_registered': label in self.archive.original.leases,
                        'device': info.st_dev, 'inode': info.st_ino, 'links': info.st_nlink}
            failure['persistence'] = {'status': 'PERSISTENCE_UNPROVEN'}
            if self._parent_fd is None:
                raise EvidenceError('original evidence parent descriptor unavailable')
            parent = os.fstat(self._parent_fd)
            failure['persistence'] = {'status': 'PERSISTENCE_UNPROVEN',
                'note': 'record of attempt; completion acknowledged in factory memory after fsync',
                'basis': 'exclusive no-follow write relative to original owned parent descriptor',
                'parent_device': parent.st_dev, 'parent_inode': parent.st_ino}
            fd = os.open(label + '-preparation-failure.json',
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=self._parent_fd)
            try:
                remaining = memoryview(package._dump_json(failure).encode('utf-8'))
                while remaining:
                    count = os.write(fd, remaining)
                    if count <= 0:
                        raise OSError('failure receipt write made no progress')
                    remaining = remaining[count:]
                os.fsync(fd)
            finally:
                os.close(fd)
            failure['persistence']['status'] = 'PERSISTED'
        except BaseException as persistence_error:
            failure['persistence'] = {'status': 'PERSISTENCE_UNPROVEN',
                'error_type': type(persistence_error).__name__, 'error': str(persistence_error)}

    def _copy(self, *args, **kwargs):
        self._preparation_guard()
        result = super()._copy(*args, **kwargs)
        self._preparation_guard()
        return result

    def _registered(self, root):
        plain(self.directory)
        root = plain(root)
        matches = [label for label, evidence in self.evidence.items()
                   if evidence['owned_run_root'] == str(root)]
        if (not root.is_dir() or root.parent != self.directory or len(matches) != 1
                or self.archive.lease(matches[0]) != root):
            raise EvidenceError('installed deployment requires this prepare registered direct child')
        return matches[0]

    def _marker(self):
        path = self.directory / package.SANDBOX_MARKER_NAME
        digest, _ = _digest(path, package.SIZE_LIMIT_BYTES)
        marker = package._read_sandbox_marker(self.directory)
        if marker['sha256'] != digest:
            raise EvidenceError('installed deployment sandbox marker changed')
        return marker

    def _source(self, validation):
        if (self.source_identity.get('candidate_sha') != self.candidate
                or validation['manifest']['source_commit'] != self.candidate):
            raise EvidenceError('installed package source_commit differs from candidate')
        sealed = self.source_identity.get('execution_artifact_sha256', {})
        for prefix in (package.BRIDGE_SOURCE_DIR + '/', package.WORKFLOWS_SOURCE_DIR + '/'):
            expected = {name: digest for name, digest in sealed.items() if name.startswith(prefix)}
            actual = {item['source_path']: item['sha256'] for item in validation['items']
                      if item['source_path'].startswith(prefix)}
            if not expected or actual != expected:
                raise EvidenceError('installed package source seal mismatch: ' + prefix
                                    + ' missing=' + repr(sorted(actual.keys() - expected.keys()))
                                    + ' extra=' + repr(sorted(expected.keys() - actual.keys())))

    def _deploy(self, root):
        label = self._registered(root)
        evidence = self.evidence[label]['deployment'] = {
            'mode': 'INSTALLED_PACKAGE', 'candidate_sha': self.candidate,
            'package_sha256': self.package_sha256, 'manifest_sha256': self.manifest_sha256,
            'target': str(root), 'status': 'VALIDATING', 'stage_pass_claim': False}
        try:
            for digest in (self.package_sha256, self.manifest_sha256):
                if not isinstance(digest, str) or not re.fullmatch('[a-f0-9]{64}', digest):
                    raise EvidenceError('installed package digest must be lowercase SHA256')
            # _prepare creates exactly these empty directories after registration.
            # Refuse redirects or prepopulation before the installer can resolve
            # any child path (its CLI resolves the root itself).
            children = list(root.iterdir())
            if {path.name for path in children} != {'input', 'output', 'temp', 'custom_nodes'}:
                raise EvidenceError('installed deployment root was populated outside prepare')
            for path in children:
                if not plain(path).is_dir() or any(path.iterdir()):
                    raise EvidenceError('installed deployment requires empty plain preparation directories')
            marker = self._marker()
            plain(self.package_path)  # The protected reader owns the bounded hash/read.
            self.archive.retained.add(root)
            with package.ProtectedInstall(target=root, sandbox_parent=self.directory,
                    package_path=self.package_path, package_sha256=self.package_sha256,
                    manifest_sha256=self.manifest_sha256, candidate_sha=self.candidate) as handoff:
                validation = handoff.validate()
                if (validation['package_sha256'] != self.package_sha256
                        or validation['manifest_sha256'] != self.manifest_sha256):
                    raise EvidenceError('installed package/manifest hash drift')
                self._source(validation)
                # Recheck the registered root and caller-owned marker immediately
                # before the existing installer owns the only extraction transaction.
                self._registered(root)
                if self._marker() != marker:
                    raise EvidenceError('installed deployment sandbox marker drift')
                receipt_path = self.directory / (label + '-package-install.json')
                if receipt_path.exists() or receipt_path.is_symlink():
                    raise EvidenceError('installed deployment receipt already exists')
                receipt = package.command_install(SimpleNamespace(
                    package=str(self.package_path), manifest=None, target=str(root),
                    sandbox_parent=str(self.directory), session_id=None,
                    receipt_out=None, redact_root=[], _protected_handoff=handoff))
                # Preserve the original returned receipt, including if post-install
                # verification fails. The archive retains the in-target owner record.
                evidence['install_receipt'] = copy.deepcopy(receipt)
                handoff.save_receipt(receipt_path.name, receipt)
                handoff.check()
                self._registered(root)
                if self._marker() != marker:
                    raise EvidenceError('installed deployment sandbox marker drift')
                if (receipt.get('status') != 'OK' or receipt.get('target') != str(root)
                        or receipt.get('sandbox_parent') != str(self.directory)
                        or receipt.get('source_commit') != self.candidate
                        or receipt.get('package', {}).get('sha256') != self.package_sha256
                        or receipt.get('manifest', {}).get('sha256') != self.manifest_sha256
                        or receipt.get('manifest', {}).get('content') != validation['manifest']):
                    raise EvidenceError('installed deployment receipt identity mismatch')
                owner_path = root / package.OWNERSHIP_FILE_NAME
                owner_digest, _ = _digest(owner_path, package.SIZE_LIMIT_BYTES)
                owner, loaded_digest = package._read_ownership_record(root)
                if (loaded_digest != owner_digest or receipt['ownership']['sha256'] != owner_digest
                        or receipt['ownership']['install_hash'] != owner['install_hash']
                        or receipt.get('session_id') != owner.get('session_id')
                        or package._cross_check_receipt_against_ownership(receipt, owner)):
                    raise EvidenceError('installed deployment ownership mismatch')
                expected = {item['install_path']: (item['sha256'], item['length'])
                            for item in validation['items']}
                actual = {}
                visited = 0
                for prefix in (package.BRIDGE_INSTALL_DIR, package.WORKFLOWS_INSTALL_DIR):
                    subtree = plain(root / prefix)
                    for path in subtree.rglob('*'):
                        visited += 1
                        if visited > 8192:
                            raise EvidenceError('installed payload entry budget exceeded')
                        plain(path)
                        if path.is_file():
                            actual[path.relative_to(root).as_posix()] = _digest(path, package.SIZE_LIMIT_BYTES)
                        elif not path.is_dir():
                            raise EvidenceError('installed payload contains special entry')
                if actual != expected:
                    raise EvidenceError('installed payload bytes/set differ from frozen manifest')
                owned = {row['install_path']: (row['sha256'], row['length']) for row in owner['owned']['files']}
                if owned != expected:
                    raise EvidenceError('installed ownership payload set differs from manifest')
                evidence.update(status='VERIFIED', payload_files=len(actual),
                                payload_bytes=sum(size for _, size in actual.values()),
                                ownership_sha256=owner_digest, sandbox_marker_sha256=marker['sha256'])
                handoff.check()
                self.archive.retained.remove(root)
        except BaseException as error:
            evidence.update(status='FAILED', error_type=type(error).__name__, error=str(error))
            evidence['retention_required'] = root in self.archive.retained
            if isinstance(error, package.PackageError):
                evidence['installer_error'] = error.to_dict()
            raise
