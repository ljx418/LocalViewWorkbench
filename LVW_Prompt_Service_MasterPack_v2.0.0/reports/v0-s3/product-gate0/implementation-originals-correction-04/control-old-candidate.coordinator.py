"""S3 offline integration coordinator.

This module owns exactly three new things of the S3-P4-OFFLINE integration
workpack:

* the *first* profile binding of the S3 budget regime.  It is a private hook
  of the inherited factory; the accepted S2 behaviour of that hook is the
  empty mapping, so no S2 call site and no S2 profile byte changes;
* the binding of the controlled video snapshot residue accessor on the run
  root that this factory already verified;
* the parent's own original evidence and the fixed V0-A01..A12 aggregation.

The accepted ``InstalledPackageRuntimeFactory`` is *inherited*.  It is never
changed, never replaced and never copied into a source-copy factory.  The
accepted owners of the phase, of the install and rollback, of the archive and
of the original ledger stay where they are; this module only reads their
receipts and registers them.

Nothing in this module proves a product gate.  Every document it produces
carries ``stage_pass_claim = False`` and ``product_gate0 = False``.  A
synthetic fixture never counts as a product pass.
"""
import errno
import hashlib
import json
import os
import re
import stat
import time
from pathlib import Path

from tools.v0_s3_budget_authority import AUTHORITY_HASH
from tools.v0_s3_stage_runtime import InstalledPackageRuntimeFactory
from LVW_V0_RuntimePatch.custom_nodes.lvw_v0_bridge import program_budget as budget

PACK_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_SOURCE = 'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge/program_budget.py'
MAX_SEALED_ORIGINAL_BYTES = 8 * 1024 * 1024
AGGREGATE_RECEIPT_KIND = 'lvw.s3-aggregate-receipt/1'
TWELVE_KEYS = tuple('V0-A%02d' % index for index in range(1, 13))

# The fixed V0-A01..A12 aggregation.  Every key registers the receipts that
# its own product obligation needs.  The old S2 nine key phase facts and the
# old 45+20 submissions are phase facts of the S2 stage; they are never
# accepted here as an S3 receipt, so they cannot fill a green key.
#
# The cleanup of the run is a global obligation: every key of this summary
# describes a stage of a run that has to end clean.  The cleanup receipt is
# therefore required by every key, and a key without a proven cleanup can
# never be green.  The fixed set of the twelve keys and the product
# denominator are not changed by this.
TWELVE_REQUIREMENTS = {
    'V0-A01': ('stage_binding', 'image_input', 'cleanup'),
    'V0-A02': ('stage_binding', 'video_input', 'cleanup'),
    'V0-A03': ('stage_binding', 'output_contract', 'cleanup'),
    'V0-A04': ('stage_binding', 'manual_export', 'cleanup'),
    'V0-A05': ('stage_binding', 'no_overwrite', 'cleanup'),
    'V0-A06': ('stage_binding', 'a06_isolation', 'install', 'rollback', 'cleanup'),
    'V0-A07': ('stage_binding', 'file_safety', 'cleanup'),
    'V0-A08': ('stage_binding', 'no_approval_gate', 'cleanup'),
    'V0-A09': ('stage_binding', 'resource_budget', 'cleanup'),
    'V0-A10': ('stage_binding', 'cancel_release', 'cleanup'),
    'V0-A11': ('stage_binding', 'quality_16_rows', 'independent_score', 'cleanup'),
    'V0-A12': ('stage_binding', 'quality_16_rows', 'independent_score', 'webp_format',
               'cleanup'),
}

# The receipts whose own truth is not a single phase result: the A06 real
# isolation, the independent quality score and the cleanup proof.
BLOCKING_RECEIPTS = ('a06_isolation', 'independent_score')

# The receipt that carries the proof that the run ended clean.  It is a
# normal aggregate receipt: it has the kind, the status, the stage claim
# flag and the run/candidate binding of every other receipt, and it has to
# state the cleanup proof with the strict boolean ``True``.
CLEANUP_RECEIPT = 'cleanup'


class S3IntegrationError(RuntimeError):
    """A refused S3 integration step.

    The reason is a stable, machine readable code.  The cause is kept as
    text only; no path or payload dump ever reaches a receipt.
    """

    def __init__(self, reason, *, detail=None):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False)


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _no_follow_open_supported():
    """Whether this platform has the safe opening primitives.

    The originals of a bound root are only ever opened through the
    directory descriptor of their own parent with ``O_NOFOLLOW``.  A
    platform that does not have these primitives is not silently treated
    as if it had them: the caller fails closed and the run stays
    ``NOT_PROVEN``.
    """
    if not hasattr(os, 'O_NOFOLLOW') or not hasattr(os, 'O_DIRECTORY'):
        return False
    return os.open in getattr(os, 'supports_dir_fd', ())


def _digest_handle(descriptor, limit=MAX_SEALED_ORIGINAL_BYTES):
    """The digest and the length of the bytes of one verified handle.

    The bytes are read from the handle that was opened and verified, so
    the digest and the identity belong to the same object.  There is no
    second, unchecked open of the same path.
    """
    digest = hashlib.sha256()
    length = 0
    while True:
        block = os.read(descriptor, 1024 * 1024)
        if not block:
            break
        length += len(block)
        if length > limit:
            raise S3IntegrationError('ORIGINAL_EXCEEDS_BOUND')
        digest.update(block)
    return digest.hexdigest(), length


class S3BudgetBindingProvider:
    """The bounded provider of the single S3 profile binding parameter.

    The provider never invents a budget identity and it never touches the
    original ledger.  It reads the sealed binding document through the
    *accepted* validator and loader of the bridge protocol and refuses every
    deviation of the run, candidate, child, authority, ledger, tool, source
    and expiry identity.  The refusal happens before the first exclusive
    profile write and therefore long before the first model send.

    The real debit owner stays the existing authority.  A shape check here
    never replaces the real ledger verification of that owner.
    """

    def __init__(self, *, binding, run_id, candidate_sha, authorization_sha256,
                 model_digest, authority_root, model=None, ledger_path=None, now=None):
        self.binding = binding
        self.run_id = run_id
        self.candidate_sha = candidate_sha
        self.authorization_sha256 = authorization_sha256
        self.model_digest = model_digest
        self.model = model
        self.authority_root = Path(authority_root)
        self.ledger_path = Path(ledger_path) if ledger_path is not None else None
        self.now = now
        self._sealed = None

    # -- the accepted loader and validator --------------------------------
    def _load(self):
        ref = self.binding
        if (not isinstance(ref, dict) or set(ref) != {'path', 'sha256'}
                or not isinstance(ref['path'], str) or not ref['path']
                or not isinstance(ref['sha256'], str)
                or not re.fullmatch('[0-9a-f]{64}', ref['sha256'])):
            raise S3IntegrationError('S3_BUDGET_BINDING_CAPABILITY_INVALID')
        try:
            binding, seal = budget.load_binding(ref)
            budget.validate_config(binding, self.now)
        except Exception as error:  # noqa: BLE001 - the refusal reason is stable
            raise S3IntegrationError('S3_BUDGET_BINDING_INVALID:' + type(error).__name__,
                                     detail=str(error)[:200]) from error
        return binding, seal

    # -- the identity cross checks ----------------------------------------
    def _check_identity(self, binding):
        if binding['run_id'] != self.run_id:
            raise S3IntegrationError('S3_BUDGET_RUN_ID_MISMATCH')
        if binding['candidate_sha'] != self.candidate_sha:
            raise S3IntegrationError('S3_BUDGET_CANDIDATE_MISMATCH')
        if binding['child_sha256'] != self.authorization_sha256:
            raise S3IntegrationError('S3_BUDGET_CHILD_MISMATCH')
        if binding['model_digest'] != self.model_digest:
            raise S3IntegrationError('S3_BUDGET_MODEL_DIGEST_MISMATCH')
        if self.model is not None and binding['model'] != self.model:
            raise S3IntegrationError('S3_BUDGET_MODEL_MISMATCH')
        if Path(binding['authority_root']).resolve() != self.authority_root.resolve():
            raise S3IntegrationError('S3_BUDGET_AUTHORITY_ROOT_MISMATCH')
        ledger = Path(binding['ledger_path'])
        if not ledger.is_absolute():
            raise S3IntegrationError('S3_BUDGET_LEDGER_IDENTITY_INVALID')
        if not ledger.resolve().is_relative_to(Path(binding['authority_root']).resolve()):
            raise S3IntegrationError('S3_BUDGET_LEDGER_OUTSIDE_AUTHORITY')
        if self.ledger_path is not None and ledger.resolve() != self.ledger_path.resolve():
            raise S3IntegrationError('S3_BUDGET_LEDGER_MISMATCH')
        roles = binding['tools']
        if any(roles.get(role) is None for role in ('authority', 'shim', 'python')):
            raise S3IntegrationError('S3_BUDGET_TOOL_ROLE_MISSING')
        if roles['authority']['sha256'] != AUTHORITY_HASH:
            raise S3IntegrationError('S3_BUDGET_AUTHORITY_IMPLEMENTATION_DRIFT')
        for role in ('authority', 'shim', 'python'):
            item = roles[role]
            try:
                actual = budget.digest(item['path'])
            except OSError as error:
                raise S3IntegrationError('S3_BUDGET_TOOL_UNREADABLE:' + role) from error
            if actual != item['sha256']:
                raise S3IntegrationError('S3_BUDGET_TOOL_DRIFT:' + role)
        try:
            execution = budget.read_json(binding['execution_path'], binding['execution_sha256'])
        except Exception as error:  # noqa: BLE001 - the refusal reason is stable
            raise S3IntegrationError('S3_BUDGET_EXECUTION_BINDING_INVALID') from error
        if not isinstance(execution, dict):
            raise S3IntegrationError('S3_BUDGET_EXECUTION_BINDING_INVALID')
        for role in ('authority', 'shim', 'python'):
            item = roles[role]
            if execution.get('s3_' + role) != {'path': item['path'], 'sha256': item['sha256']}:
                raise S3IntegrationError('S3_BUDGET_EXECUTION_BINDING_MISMATCH:' + role)
        protocol_path = Path(binding['authority_root']) / PROTOCOL_SOURCE
        try:
            protocol_digest = budget.digest(protocol_path)
        except OSError as error:
            raise S3IntegrationError('S3_BUDGET_PROTOCOL_SOURCE_UNREADABLE') from error
        if execution.get('s3_protocol') != {'path': str(protocol_path), 'sha256': protocol_digest}:
            raise S3IntegrationError('S3_BUDGET_PROTOCOL_SOURCE_MISMATCH')
        now = time.time() if self.now is None else self.now
        if not binding['issued_at'] <= now < binding['expires_at']:
            raise S3IntegrationError('S3_BUDGET_BINDING_EXPIRED')
        return binding

    def sealed(self):
        """The validated binding document and its seal."""
        if self._sealed is None:
            binding, seal = self._load()
            self._check_identity(binding)
            self._sealed = (binding, seal)
        return self._sealed

    def parameters(self, *, root, label, baseline):
        """The exact additional profile parameters of this preparation.

        Only the one allowed key is returned.  The value is the sealed
        capability of the binding document, never a copy of its content and
        never a command.
        """
        self.sealed()
        return {'s3_budget_binding': dict(self.binding)}


class S3InstalledRuntimeFactory(InstalledPackageRuntimeFactory):
    """The S3 deployment factory.

    It inherits the accepted installed-package factory unchanged.  The only
    new behaviour is the private profile binding hook, so the S3 budget
    capability is part of the *first* exclusive profile write of the
    preparation.  There is no earlier LOCAL01 profile that is written first
    and overwritten afterwards: the writers create their file exclusively.
    """

    def __init__(self, *, s3_budget_provider=None, **kwargs):
        super().__init__(**kwargs)
        self.s3_budget_provider = s3_budget_provider
        self.video_snapshot_binding = None

    def _profile_binding_parameters(self, *, root, label, baseline):
        if self.s3_budget_provider is None:
            raise S3IntegrationError('S3_BUDGET_PROVIDER_REQUIRED')
        parameters = self.s3_budget_provider.parameters(root=root, label=label, baseline=baseline)
        if (not isinstance(parameters, dict) or set(parameters) != {'s3_budget_binding'}):
            raise S3IntegrationError('S3_PROFILE_PARAMETER_SET_INVALID')
        return parameters

    def bind_video_snapshot_root(self, driver, label):
        """Bind the controlled residue accessor on the verified owned root.

        The root is the one that this factory's own evidence records.  The
        accessor re-verifies the root and temp object identities itself and
        refuses an unbound, missing, replaced or redirected root.
        """
        evidence = self.evidence.get(label)
        if not isinstance(evidence, dict) or not isinstance(evidence.get('owned_run_root'), str):
            raise S3IntegrationError('S3_OWNED_RUN_ROOT_UNAVAILABLE')
        binding = driver.bind_video_snapshot_root(evidence['owned_run_root'])
        self.video_snapshot_binding = binding
        return binding


class ParentOriginalEvidence:
    """The parent's own sealed view of the originals of one run.

    The parent seals the run, candidate and child identity, the sixteen row
    plan, the projection digest and the root identity *before* the worker is
    allowed to send anything.  After the terminal event the parent reads the
    canonical receipt, the source plan and the raw artifacts of the selected
    root itself and records their real lengths and hashes.

    The worker can never replace this list by changing an in-memory return
    value: every entry is read from the parent's own root.

    The originals are opened through the bound root without following a
    link: every component of a reference is opened from the descriptor of
    its own parent with ``O_NOFOLLOW``, so an ancestor that points out of
    the root is refused and not only a link on the artifact itself.  The
    digest is computed from the handle that was verified.  A platform that
    does not have these primitives fails closed and stays ``NOT_PROVEN``.
    """

    def __init__(self, *, run_id, candidate_sha, child_sha256, root, projection_sha256):
        self.run_id = run_id
        self.candidate_sha = candidate_sha
        self.child_sha256 = child_sha256
        self.root = Path(root)
        self.projection_sha256 = projection_sha256
        self.rows = None
        self.plan_sha256 = None
        self.root_identity = None
        self.originals = {}
        self.terminal = None

    def seal_plan(self, rows):
        """Seal the complete sixteen row plan."""
        if not isinstance(rows, list) or len(rows) != 16:
            raise S3IntegrationError('S3_PLAN_INCOMPLETE')
        seen_ordinal = set()
        seen_asset = set()
        sealed = []
        for row in rows:
            if not isinstance(row, dict):
                raise S3IntegrationError('S3_PLAN_ROW_INVALID')
            for key in ('ordinal', 'asset_id', 'media_kind', 'source_sha256', 'source_bytes'):
                if key not in row:
                    raise S3IntegrationError('S3_PLAN_ROW_INVALID')
            ordinal = row['ordinal']
            asset_id = row['asset_id']
            if type(ordinal) is not int or not 1 <= ordinal <= 16 or ordinal in seen_ordinal:
                raise S3IntegrationError('S3_PLAN_ORDINAL_INVALID')
            if not isinstance(asset_id, str) or not asset_id or asset_id in seen_asset:
                raise S3IntegrationError('S3_PLAN_ASSET_INVALID')
            if row['media_kind'] not in ('image', 'video'):
                raise S3IntegrationError('S3_PLAN_MEDIA_KIND_INVALID')
            if not re.fullmatch('[0-9a-f]{64}', str(row['source_sha256'])):
                raise S3IntegrationError('S3_PLAN_SOURCE_SHA_INVALID')
            if type(row['source_bytes']) is not int or row['source_bytes'] <= 0:
                raise S3IntegrationError('S3_PLAN_SOURCE_BYTES_INVALID')
            seen_ordinal.add(ordinal)
            seen_asset.add(asset_id)
            sealed.append({'ordinal': ordinal, 'asset_id': asset_id,
                           'media_kind': row['media_kind'],
                           'source_sha256': row['source_sha256'],
                           'source_bytes': row['source_bytes'],
                           'input_reference': row.get('input_reference')})
        if len(seen_ordinal) != 16:
            raise S3IntegrationError('S3_PLAN_INCOMPLETE')
        self.rows = sealed
        self.plan_sha256 = sha256_bytes(canonical_json(sealed).encode('utf-8'))
        return self.plan_sha256

    def seal_root(self, root_identity):
        """Seal the object identity of the selected root."""
        if (not isinstance(root_identity, (list, tuple)) or len(root_identity) != 2
                or any(type(value) is not int for value in root_identity)):
            raise S3IntegrationError('S3_ROOT_IDENTITY_INVALID')
        self.root_identity = [int(root_identity[0]), int(root_identity[1])]
        return self.root_identity

    def _bound_root_fd(self):
        """Open the bound root and verify its object identity.

        The root is opened without following a link and the identity of the
        opened object is compared with the sealed one.  A root that was
        replaced, that became a link or that vanished is refused here,
        before any original is touched.
        """
        if self.root_identity is None:
            raise S3IntegrationError('S3_SELECTED_ROOT_NOT_SEALED')
        if not _no_follow_open_supported():
            # The platform can not open an artifact of the root without
            # following a link.  The run stays NOT_PROVEN instead of
            # claiming that the originals are inside the root.
            raise S3IntegrationError('S3_ORIGINAL_SAFE_OPEN_UNSUPPORTED')
        try:
            descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise S3IntegrationError('S3_SELECTED_ROOT_REPLACED') from error
            raise S3IntegrationError('S3_SELECTED_ROOT_UNAVAILABLE') from error
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISDIR(info.st_mode):
                raise S3IntegrationError('S3_SELECTED_ROOT_REPLACED')
            if [info.st_dev, info.st_ino] != list(self.root_identity):
                raise S3IntegrationError('S3_SELECTED_ROOT_REPLACED')
        except BaseException:
            os.close(descriptor)
            raise
        return descriptor

    @staticmethod
    def _reference_parts(relative):
        """The components of one root relative reference."""
        if not isinstance(relative, str) or not relative:
            raise S3IntegrationError('S3_ORIGINAL_REFERENCE_INVALID')
        pure = Path(relative)
        if pure.is_absolute() or '..' in pure.parts:
            raise S3IntegrationError('S3_ORIGINAL_REFERENCE_INVALID')
        parts = [part for part in pure.parts if part != '.']
        if not parts:
            raise S3IntegrationError('S3_ORIGINAL_REFERENCE_INVALID')
        return parts

    @staticmethod
    def _open_error(error, category):
        """The stable refusal of one refused opening."""
        if error.errno == errno.ELOOP:
            return S3IntegrationError('S3_ORIGINAL_REDIRECT_FORBIDDEN:' + category)
        if error.errno == errno.ENOTDIR:
            return S3IntegrationError('S3_ORIGINAL_ANCESTOR_NOT_A_DIRECTORY:' + category)
        return S3IntegrationError('S3_ORIGINAL_UNREADABLE:' + category)

    @staticmethod
    def _is_link(directory, name):
        """Whether one component of a reference is a link.

        The classification never decides whether an artifact is safe: the
        safe opening with ``O_NOFOLLOW`` already refused the artifact.  It
        only names the reason of that refusal.
        """
        try:
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
        except (OSError, ValueError, NotImplementedError):
            return False
        return stat.S_ISLNK(info.st_mode)

    def _open_inside_root(self, relative, category='original'):
        """Open one artifact of the bound root without following a link.

        Every component of the reference is opened one by one from the
        descriptor of its own parent directory with ``O_NOFOLLOW``.  An
        ancestor that is a link is therefore refused: the artifact is never
        reached through a link, and the bytes that are digested are the
        bytes of the handle that was verified.  There is no pre-check of
        the path and no second, unchecked open of the same path.
        """
        parts = self._reference_parts(relative)
        directory = self._bound_root_fd()
        try:
            for part in parts[:-1]:
                try:
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                    dir_fd=directory)
                except OSError as error:
                    if self._is_link(directory, part):
                        raise S3IntegrationError(
                            'S3_ORIGINAL_REDIRECT_FORBIDDEN:' + category) from error
                    raise self._open_error(error, category) from error
                os.close(directory)
                directory = child
            try:
                descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW,
                                     dir_fd=directory)
            except OSError as error:
                if self._is_link(directory, parts[-1]):
                    raise S3IntegrationError(
                        'S3_ORIGINAL_REDIRECT_FORBIDDEN:' + category) from error
                raise self._open_error(error, category) from error
        finally:
            os.close(directory)
        return descriptor

    def _seal_one(self, reference, category):
        """Read one original through its verified handle and seal it."""
        try:
            descriptor = self._open_inside_root(reference, category)
        except ValueError as error:
            raise S3IntegrationError('S3_ORIGINAL_REFERENCE_INVALID') from error
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode):
                raise S3IntegrationError('ORIGINAL_NOT_A_REGULAR_FILE')
            if info.st_size > MAX_SEALED_ORIGINAL_BYTES:
                raise S3IntegrationError('ORIGINAL_EXCEEDS_BOUND')
            digest, length = _digest_handle(descriptor, MAX_SEALED_ORIGINAL_BYTES)
        except OSError as error:
            raise S3IntegrationError('S3_ORIGINAL_UNREADABLE:' + category) from error
        finally:
            os.close(descriptor)
        return {'reference': reference, 'sha256': digest, 'bytes': length,
                'identity': [int(info.st_dev), int(info.st_ino)],
                'change_time_ns': int(info.st_ctime_ns),
                'modify_time_ns': int(info.st_mtime_ns)}

    def seal_originals(self, *, canonical, source_plan, raw=()):
        """Read the real originals of the selected root and seal their bytes.

        ``canonical`` and ``source_plan`` are root relative references of the
        canonical receipt and of the sealed source plan.  ``raw`` is the
        sequence of the root relative raw artifact references.  A missing,
        foreign, redirected or changed original is refused; it is never
        recorded as an empty result.

        Every artifact is opened through the bound root without following a
        link, so an ancestor that points out of the root is refused as well
        and not only a link on the artifact itself.
        """
        if self.root_identity is None or self.rows is None:
            raise S3IntegrationError('S3_ORIGINALS_NOT_SEALABLE')
        entries = {}
        for name, references in (('canonical', [canonical]), ('source_plan', [source_plan]),
                                 ('raw', list(raw))):
            sealed = []
            for reference in references:
                sealed.append(self._seal_one(reference, name))
            entries[name] = sealed
        self.originals = entries
        return entries

    def verify_originals(self):
        """Re-read every sealed original through its verified handle.

        The re-check is independent of the seal: it opens the artifact
        again, compares the object identity, the length and the digest with
        the sealed values and refuses every difference.  The identity of the
        root is not the identity of the originals: a replaced, rewritten,
        vanished or redirected original is refused even when the root is
        still the sealed one.
        """
        if not self.originals:
            raise S3IntegrationError('S3_ORIGINALS_NOT_SEALED')
        self.verify_selected_root()
        checked = []
        for category, entries in self.originals.items():
            for entry in entries:
                try:
                    descriptor = self._open_inside_root(entry['reference'], category)
                except ValueError as error:
                    raise S3IntegrationError('S3_ORIGINAL_REFERENCE_INVALID') from error
                try:
                    info = os.fstat(descriptor)
                    if not stat.S_ISREG(info.st_mode):
                        raise S3IntegrationError('S3_ORIGINAL_REPLACED:' + category)
                    digest, length = _digest_handle(descriptor, MAX_SEALED_ORIGINAL_BYTES)
                except OSError as error:
                    raise S3IntegrationError('S3_ORIGINAL_UNREADABLE:' + category) from error
                finally:
                    os.close(descriptor)
                identity = [int(info.st_dev), int(info.st_ino)]
                if identity != list(entry.get('identity', [])):
                    raise S3IntegrationError('S3_ORIGINAL_REPLACED:' + category)
                # The change time of the object is part of its identity: a
                # file that was replaced by another file with the very same
                # bytes can reuse the number of the object on some file
                # systems, and the change time still tells the two apart.
                if int(info.st_ctime_ns) != int(entry.get('change_time_ns', -1)) \
                        or int(info.st_mtime_ns) != int(entry.get('modify_time_ns', -1)):
                    raise S3IntegrationError('S3_ORIGINAL_REPLACED:' + category)
                if length != entry['bytes'] or digest != entry['sha256']:
                    raise S3IntegrationError('S3_ORIGINAL_CHANGED:' + category)
                checked.append({'category': category, 'reference': entry['reference'],
                                'sha256': digest, 'bytes': length,
                                'identity': identity})
        return {'root': str(self.root), 'identity': list(self.root_identity),
                'checked': checked, 'verified': True}

    def verify_selected_root(self, root=None):
        """Re-check that the selected root is still the sealed root.

        The root is opened without following a link and the identity of the
        opened object is compared with the sealed one.  A root that was
        archived and migrated is *not* accepted silently: the caller has to
        keep the migration blocked until it is proven.
        """
        target = self.root if root is None else Path(root)
        if str(target) != str(self.root):
            raise S3IntegrationError('S3_SELECTED_ROOT_MISMATCH')
        if self.root_identity is None:
            raise S3IntegrationError('S3_SELECTED_ROOT_NOT_SEALED')
        descriptor = self._bound_root_fd()
        os.close(descriptor)
        return {'root': str(target), 'identity': list(self.root_identity)}

    def manifest(self):
        """The parent's own manifest of the sealed originals.

        The manifest is the consumption boundary of the originals: it calls
        the re-check of the root and of every original before it hands the
        document out.  A manifest that would be built from a root whose
        originals changed, vanished or were redirected is refused instead of
        being written from the stale seal.
        """
        if self.rows is None or self.root_identity is None:
            raise S3IntegrationError('S3_ORIGINALS_NOT_SEALED')
        reverification = self.verify_originals()
        return {
            'kind': 'lvw.s3-parent-originals/1',
            'run_id': self.run_id,
            'candidate_sha': self.candidate_sha,
            'child_sha256': self.child_sha256,
            'projection_sha256': self.projection_sha256,
            'plan_sha256': self.plan_sha256,
            'row_count': len(self.rows),
            'root': str(self.root),
            'root_identity': list(self.root_identity),
            'originals': self.originals,
            'reverification': reverification,
            'original_open_primitive': 'no_follow_dirfd',
            'stage_pass_claim': False,
            'product_gate0': False,
            'real_execution_performed': False,
        }


def _receipt_status(receipt):
    """The status of one aggregate receipt, with its refusals."""
    if receipt is None:
        return 'NOT_RUN', 'RECEIPT_MISSING'
    if not isinstance(receipt, dict):
        return 'NOT_RUN', 'RECEIPT_NOT_A_DOCUMENT'
    if receipt.get('kind') != AGGREGATE_RECEIPT_KIND:
        return 'NOT_RUN', 'RECEIPT_KIND_NOT_ACCEPTED'
    status = receipt.get('status')
    if status not in ('PASS', 'FAIL', 'BLOCKED', 'NOT_RUN'):
        return 'NOT_RUN', 'RECEIPT_STATUS_INVALID'
    if receipt.get('stage_pass_claim') is not False:
        return 'BLOCKED', 'RECEIPT_STAGE_PASS_CLAIM_INVALID'
    return status, None


def aggregate_twelve_keys(*, receipts, binding):
    """Aggregate the fixed V0-A01..A12 summary from the real receipts.

    ``receipts`` maps a receipt name to its document.  ``binding`` is the
    run/candidate binding that every receipt has to match.

    * a key without every required receipt is ``NOT_RUN``;
    * a key whose receipt reports a failure is ``FAIL``;
    * a key whose receipt is present but whose independent score, real
      isolation or cleanup proof is missing is ``BLOCKED``;
    * only a complete, matching, passing receipt set is ``PASS``.

    The cleanup of the run is a global obligation: every key needs the
    cleanup receipt, and the cleanup receipt has to state the cleanup proof
    with the strict boolean ``True``.  A missing cleanup, a cleanup of a
    foreign kind, a cleanup of another candidate and a cleanup that only
    claims the proof as a string can never fill a green key.

    The old S2 nine key phase facts and the old 45+20 submissions are facts
    of their own stage.  They are not aggregate receipts, so they can never
    fill a green key here.
    """
    if not isinstance(receipts, dict):
        raise S3IntegrationError('S3_AGGREGATE_RECEIPTS_INVALID')
    if (not isinstance(binding, dict) or set(binding) != {'run_id', 'candidate_sha'}
            or not isinstance(binding['run_id'], str) or not binding['run_id']
            or not re.fullmatch('[0-9a-f]{40}', str(binding['candidate_sha']))):
        raise S3IntegrationError('S3_AGGREGATE_BINDING_INVALID')
    keys = {}
    for key in TWELVE_KEYS:
        required = TWELVE_REQUIREMENTS[key]
        status = 'PASS'
        reasons = []
        for name in required:
            receipt = receipts.get(name)
            state, reason = _receipt_status(receipt)
            if reason is not None:
                reasons.append(name + ':' + reason)
            if state == 'FAIL':
                status = 'FAIL'
            elif state == 'BLOCKED':
                status = 'BLOCKED' if status != 'FAIL' else status
            elif state == 'NOT_RUN':
                status = 'NOT_RUN' if status == 'PASS' else status
            if receipt is not None and isinstance(receipt, dict):
                if receipt.get('run_id') != binding['run_id'] \
                        or receipt.get('candidate_sha') != binding['candidate_sha']:
                    status = 'FAIL' if status in ('PASS', 'BLOCKED') else status
                    reasons.append(name + ':BINDING_MISMATCH')
        for name in BLOCKING_RECEIPTS:
            receipt = receipts.get(name)
            if not isinstance(receipt, dict):
                continue
            if name == 'a06_isolation' and receipt.get('real_isolation') is not True:
                status = 'BLOCKED' if status != 'FAIL' else status
                reasons.append(name + ':REAL_ISOLATION_UNPROVEN')
            if name == 'independent_score' and receipt.get('independent') is not True:
                status = 'BLOCKED' if status != 'FAIL' else status
                reasons.append(name + ':INDEPENDENT_SCORE_MISSING')
        # The cleanup proof of the run.  The receipt itself was already
        # accepted or refused as a required receipt above, so only a legal
        # receipt can reach this point; its own proof has to be the strict
        # boolean ``True``.  A claim that is not the boolean - the string
        # ``true``, the number one or a missing field - is not a proof.
        cleanup = receipts.get(CLEANUP_RECEIPT)
        if isinstance(cleanup, dict) and cleanup.get('kind') == AGGREGATE_RECEIPT_KIND \
                and cleanup.get('cleanup_proven') is not True:
            status = 'BLOCKED' if status != 'FAIL' else status
            reasons.append(CLEANUP_RECEIPT + ':CLEANUP_UNPROVEN')
        keys[key] = {
            'key': key,
            'status': status,
            'required_receipts': list(required),
            'reasons': sorted(set(reasons)),
            'stage_pass_claim': False,
            'product_gate0': False,
        }
    statuses = [entry['status'] for entry in keys.values()]
    cleanup = receipts.get(CLEANUP_RECEIPT)
    cleanup_proven = (isinstance(cleanup, dict)
                      and cleanup.get('kind') == AGGREGATE_RECEIPT_KIND
                      and cleanup.get('cleanup_proven') is True)
    return {
        'kind': 'lvw.s3-twelve-key-summary/1',
        'run_id': binding['run_id'],
        'candidate_sha': binding['candidate_sha'],
        'keys': keys,
        'key_count': len(keys),
        'pass_count': statuses.count('PASS'),
        'fail_count': statuses.count('FAIL'),
        'blocked_count': statuses.count('BLOCKED'),
        'not_run_count': statuses.count('NOT_RUN'),
        'cleanup_receipt_required': True,
        'cleanup_proven': bool(cleanup_proven),
        'old_s2_nine_keys_accepted_as_green': False,
        'old_s2_submissions_accepted_as_budget': False,
        'synthetic_fixtures_count_as_product_pass': False,
        'stage_pass_claim': False,
        'product_gate0': False,
        'real_execution_performed': False,
    }
