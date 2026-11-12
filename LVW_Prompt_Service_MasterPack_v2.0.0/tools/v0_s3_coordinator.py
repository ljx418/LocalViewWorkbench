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
TWELVE_REQUIREMENTS = {
    'V0-A01': ('stage_binding', 'image_input'),
    'V0-A02': ('stage_binding', 'video_input'),
    'V0-A03': ('stage_binding', 'output_contract'),
    'V0-A04': ('stage_binding', 'manual_export'),
    'V0-A05': ('stage_binding', 'no_overwrite'),
    'V0-A06': ('stage_binding', 'a06_isolation', 'install', 'rollback'),
    'V0-A07': ('stage_binding', 'file_safety'),
    'V0-A08': ('stage_binding', 'no_approval_gate'),
    'V0-A09': ('stage_binding', 'resource_budget'),
    'V0-A10': ('stage_binding', 'cancel_release'),
    'V0-A11': ('stage_binding', 'quality_16_rows', 'independent_score'),
    'V0-A12': ('stage_binding', 'quality_16_rows', 'independent_score', 'webp_format'),
}

# The receipts whose own truth is not a single phase result: the A06 real
# isolation, the independent quality score and the cleanup proof.
BLOCKING_RECEIPTS = ('a06_isolation', 'independent_score')


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


def _digest_file(path, limit=MAX_SEALED_ORIGINAL_BYTES):
    """Bounded, symlink free digest of one regular file."""
    path = Path(path)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise S3IntegrationError('ORIGINAL_NOT_A_REGULAR_FILE')
    if not stat.S_ISREG(info.st_mode):
        raise S3IntegrationError('ORIGINAL_NOT_A_REGULAR_FILE')
    if info.st_size > limit:
        raise S3IntegrationError('ORIGINAL_EXCEEDS_BOUND')
    digest = hashlib.sha256()
    length = 0
    with path.open('rb') as stream:
        while True:
            block = stream.read(1024 * 1024)
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

    def _resolve_inside_root(self, relative, category='original'):
        """Resolve one artifact of the selected root, without following a link."""
        if not isinstance(relative, str) or not relative:
            raise S3IntegrationError('S3_ORIGINAL_REFERENCE_INVALID')
        pure = Path(relative)
        if pure.is_absolute() or '..' in pure.parts:
            raise S3IntegrationError('S3_ORIGINAL_REFERENCE_INVALID')
        path = self.root / pure
        try:
            info = path.lstat()
        except OSError as error:
            raise S3IntegrationError('S3_ORIGINAL_UNREADABLE:' + category) from error
        if stat.S_ISLNK(info.st_mode):
            raise S3IntegrationError('S3_ORIGINAL_REDIRECT_FORBIDDEN:' + category)
        return path

    def seal_originals(self, *, canonical, source_plan, raw=()):
        """Read the real originals of the selected root and seal their bytes.

        ``canonical`` and ``source_plan`` are root relative references of the
        canonical receipt and of the sealed source plan.  ``raw`` is the
        sequence of the root relative raw artifact references.  A missing,
        foreign or changed original is refused; it is never recorded as an
        empty result.
        """
        if self.root_identity is None or self.rows is None:
            raise S3IntegrationError('S3_ORIGINALS_NOT_SEALABLE')
        entries = {}
        for name, references in (('canonical', [canonical]), ('source_plan', [source_plan]),
                                 ('raw', list(raw))):
            sealed = []
            for reference in references:
                path = self._resolve_inside_root(reference, name)
                try:
                    digest, length = _digest_file(path)
                except OSError as error:
                    raise S3IntegrationError('S3_ORIGINAL_UNREADABLE:' + name) from error
                sealed.append({'reference': reference, 'sha256': digest, 'bytes': length})
            entries[name] = sealed
        self.originals = entries
        return entries

    def verify_selected_root(self, root=None):
        """Re-check that the selected root is still the sealed root.

        A root that was archived and migrated is *not* accepted silently: the
        caller has to keep the migration blocked until it is proven.
        """
        target = self.root if root is None else Path(root)
        if str(target) != str(self.root):
            raise S3IntegrationError('S3_SELECTED_ROOT_MISMATCH')
        if self.root_identity is None:
            raise S3IntegrationError('S3_SELECTED_ROOT_NOT_SEALED')
        try:
            info = target.lstat()
        except OSError as error:
            raise S3IntegrationError('S3_SELECTED_ROOT_UNAVAILABLE') from error
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            raise S3IntegrationError('S3_SELECTED_ROOT_REPLACED')
        if [info.st_dev, info.st_ino] != list(self.root_identity):
            raise S3IntegrationError('S3_SELECTED_ROOT_REPLACED')
        return {'root': str(target), 'identity': list(self.root_identity)}

    def manifest(self):
        """The parent's own manifest of the sealed originals."""
        if self.rows is None or self.root_identity is None:
            raise S3IntegrationError('S3_ORIGINALS_NOT_SEALED')
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
            'stage_pass_claim': False,
            'product_gate0': False,
            'real_execution_performed': False,
        }


def _receipt_status(receipt):
    """The status of one aggregate receipt, with its refusals."""
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
        if receipts.get('cleanup') is not None and isinstance(receipts.get('cleanup'), dict) \
                and receipts['cleanup'].get('cleanup_proven') is not True:
            status = 'BLOCKED' if status != 'FAIL' else status
            reasons.append('cleanup:CLEANUP_UNPROVEN')
        keys[key] = {
            'key': key,
            'status': status,
            'required_receipts': list(required),
            'reasons': sorted(set(reasons)),
            'stage_pass_claim': False,
            'product_gate0': False,
        }
    statuses = [entry['status'] for entry in keys.values()]
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
        'old_s2_nine_keys_accepted_as_green': False,
        'old_s2_submissions_accepted_as_budget': False,
        'synthetic_fixtures_count_as_product_pass': False,
        'stage_pass_claim': False,
        'product_gate0': False,
        'real_execution_performed': False,
    }
