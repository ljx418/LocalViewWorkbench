"""Installed-package deployment for the inherited native runtime lifecycle.

Explicit opt-in only: this does not implement S3 budgets, network isolation,
quality acceptance or rollback acceptance. No service or package CLI is launched.
"""
import copy
import re
import time
from pathlib import Path
from types import SimpleNamespace

from tools import v0_incremental_package as package
from tools.v0_s2_stage_runtime import StageRuntimeFactory
from tools.v0_s2_execution_bindings import plain, stamp, hashed_file
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


class InstalledPackageRuntimeFactory(StageRuntimeFactory):
    def __init__(self, *, package_path, package_sha256, manifest_sha256, **kwargs):
        super().__init__(**kwargs)
        self.package_path = Path(package_path)
        self.package_sha256 = package_sha256
        self.manifest_sha256 = manifest_sha256

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
            if _digest(self.package_path, package.SIZE_LIMIT_BYTES)[0] != self.package_sha256:
                raise EvidenceError('installed package hash drift')
            validation = package._validate_archive(self.package_path)
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
                receipt_out=None, redact_root=[]))
            # Preserve the original returned receipt, including if post-install
            # verification fails. The archive retains the in-target owner record.
            with receipt_path.open('xb') as output:
                output.write(package._dump_json(receipt).encode('utf-8'))
            evidence['install_receipt'] = copy.deepcopy(receipt)
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
        except BaseException as error:
            evidence.update(status='FAILED', error_type=type(error).__name__, error=str(error))
            if isinstance(error, package.PackageError):
                evidence['installer_error'] = error.to_dict()
            raise
