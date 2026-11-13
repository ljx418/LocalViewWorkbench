"""The outer, read-only observation of the shared counter.

This observation happens *outside* the guarded batch: the guard of the
batch refuses every read of the protected state, and the counter of the
root is read by the outer layer only.

The file is opened for reading and nothing else: it is never written, it
is never refunded, it is never reset, it is never replaced and no new
counter is created and no old grant is revived.
"""
import hashlib
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
out = Path(sys.argv[2])
raw = path.read_bytes()
document = json.loads(raw.decode('utf-8'))
record = {
    'kind': 'lvw.s3-cpu-budget-readonly/1',
    'path': str(path),
    'readable': True,
    'sha256': hashlib.sha256(raw).hexdigest(),
    'active': document.get('active'),
    'starts_total': document.get('starts_total'),
    'reserved_wall_seconds': document.get('reserved_wall_seconds'),
    'spent_wall_seconds': document.get('spent_wall_seconds'),
    'charges': document.get('charges'),
    'counter_keys': sorted(document) if isinstance(document, dict) else None,
    'read_mode': 'READ_ONLY_OUTSIDE_THE_GUARDED_BATCH',
    'written_by_this_run': False,
    'refunded_by_this_run': False,
    'reset_by_this_run': False,
    'new_counter_created': False,
    'old_grant_revived': False,
    'stage_pass_claim': False,
    'product_gate0': False,
}
out.write_text(json.dumps(record, indent=2), encoding='utf-8')
print(json.dumps(record, indent=2))
