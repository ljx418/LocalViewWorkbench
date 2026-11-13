"""The independent owner probes of the S3-P4 integration correction 03.

This file is the adaptation of the independent owner probes of the received
review of the correction 02.  The three probes of that review are still
here: the aggregation without a cleanup receipt, the ancestor link that
points out of the bound root and the original that changed after the seal.
The probes that reproduced a defect now assert the corrected behaviour.

Every file of this probe is synthetic and lives in this report directory.
No original of the product is read and no root of the product is touched.
"""
import hashlib
import json
import shutil
from pathlib import Path

from tools import v0_s3_coordinator as c

O = Path(__file__).resolve().parent
binding = {'run_id': 'synthetic-owner', 'candidate_sha': 'a' * 40}

# The aggregation without a cleanup receipt is never green.
required = {name for names in c.TWELVE_REQUIREMENTS.values() for name in names}
receipts = {name: {'kind': c.AGGREGATE_RECEIPT_KIND, 'status': 'PASS', **binding,
                   'stage_pass_claim': False, 'product_gate0': False,
                   'independent': True, 'real_isolation': True}
            for name in required if name != 'cleanup'}
assert 'cleanup' not in receipts
summary = c.aggregate_twelve_keys(receipts=receipts, binding=binding)
assert summary['pass_count'] != 12
assert summary['not_run_count'] == 12
assert summary['cleanup_proven'] is False
for entry in summary['keys'].values():
    assert entry['status'] == 'NOT_RUN'
    assert 'cleanup:RECEIPT_MISSING' in entry['reasons']

# The same receipts with the legal cleanup of this round are green.
receipts['cleanup'] = {'kind': c.AGGREGATE_RECEIPT_KIND, 'status': 'PASS', **binding,
                       'stage_pass_claim': False, 'product_gate0': False,
                       'cleanup_proven': True}
with_cleanup = c.aggregate_twelve_keys(receipts=receipts, binding=binding)
assert with_cleanup['pass_count'] == 12
assert with_cleanup['cleanup_proven'] is True

# A matching root identity can not allow a raw from an ancestor symlink
# that escapes that root.
root = O / 'owner-bound-root'
outside = O / 'owner-outside-bound-root'
shutil.rmtree(root, ignore_errors=True)
shutil.rmtree(outside, ignore_errors=True)
root.mkdir()
outside.mkdir()
(outside / 'canonical.json').write_text('{"rows":[]}')
(outside / 'source.json').write_text('{"plan":[]}')
(outside / 'raw.bin').write_bytes(b'EXTERNAL_SYNTHETIC_RAW')
(root / 'redirect').symlink_to(outside, target_is_directory=True)
evidence = c.ParentOriginalEvidence(**binding, child_sha256='b' * 64, root=root,
                                    projection_sha256='c' * 64)
evidence.seal_plan([{'ordinal': index, 'asset_id': 'I%02d' % index, 'media_kind': 'image',
                     'source_sha256': 'd' * 64, 'source_bytes': 1}
                    for index in range(1, 17)])
status = root.stat()
evidence.seal_root([status.st_dev, status.st_ino])
verified = evidence.verify_selected_root()
escape = None
try:
    evidence.seal_originals(canonical='redirect/canonical.json',
                            source_plan='redirect/source.json',
                            raw=['redirect/raw.bin'])
except c.S3IntegrationError as error:
    escape = error.reason
assert escape == 'S3_ORIGINAL_REDIRECT_FORBIDDEN:canonical', escape
assert evidence.originals == {}

# A legal file inside the root is sealed and re-checked.
(root / 'canonical.json').write_text('{"rows":[]}')
(root / 'temp').mkdir()
(root / 'temp' / 'source.json').write_bytes(b'LEGAL_SYNTHETIC_SOURCE')
(root / 'temp' / 'raw.bin').write_bytes(b'LEGAL_SYNTHETIC_RAW')
sealed = evidence.seal_originals(canonical='canonical.json',
                                 source_plan='temp/source.json',
                                 raw=['temp/raw.bin'])
assert sealed['raw'][0]['sha256'] == hashlib.sha256(b'LEGAL_SYNTHETIC_RAW').hexdigest()
manifest = evidence.manifest()
assert manifest['reverification']['verified'] is True
assert len(manifest['reverification']['checked']) == 3

# An original that changed after the seal is refused by the re-check.
(root / 'temp' / 'raw.bin').write_bytes(b'CHANGED_AFTER_SEAL')
changed = None
try:
    evidence.manifest()
except c.S3IntegrationError as error:
    changed = error.reason
assert changed is not None and changed.startswith('S3_ORIGINAL_'), changed

# An original that was replaced by another file is refused as well.
(root / 'temp' / 'raw.bin').write_bytes(b'LEGAL_SYNTHETIC_RAW')
(root / 'temp' / 'raw.bin').unlink()
(root / 'temp' / 'raw.bin').write_bytes(b'LEGAL_SYNTHETIC_RAW')
replaced = None
try:
    evidence.manifest()
except c.S3IntegrationError as error:
    replaced = error.reason
assert replaced == 'S3_ORIGINAL_REPLACED:raw', replaced

# An original that vanished is refused.
(root / 'temp' / 'raw.bin').unlink()
vanished = None
try:
    evidence.manifest()
except c.S3IntegrationError as error:
    vanished = error.reason
assert vanished == 'S3_ORIGINAL_UNREADABLE:raw', vanished

# A root that was replaced is refused.
(root / 'temp' / 'raw.bin').write_bytes(b'LEGAL_SYNTHETIC_RAW')
replacement = O / 'owner-replacement-root'
shutil.rmtree(replacement, ignore_errors=True)
replacement.mkdir()
shutil.rmtree(root)
replacement.rename(root)
root_replaced = None
try:
    evidence.manifest()
except c.S3IntegrationError as error:
    root_replaced = error.reason
assert root_replaced == 'S3_SELECTED_ROOT_REPLACED', root_replaced

result = {
    'all12_without_cleanup': summary,
    'all12_with_legal_cleanup': with_cleanup,
    'symlink_escape': {'root_verified': verified, 'escape_reason': escape,
                       'bound_root': str(root)},
    'changed_raw': {'manifest_reason': changed, 'replaced_reason': replaced,
                    'vanished_reason': vanished, 'root_replaced_reason': root_replaced},
}
(O / 'owner-observations.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
