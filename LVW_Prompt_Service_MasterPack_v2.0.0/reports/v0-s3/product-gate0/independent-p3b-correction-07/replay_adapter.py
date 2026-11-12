"""Run the immutable probe with only its output directory redirected."""
import hashlib
from pathlib import Path
out = Path(__file__).resolve().parent
probe = out.parent / 'implementation-p3b-correction-07/probe_correction07_counterexamples.py'
raw = probe.read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'dc4cc52a4990b9668014ae0618d9e72a5ec3b88c98c23ee12068afd1b44d5392'
source = raw.decode().replace('OUT = Path(__file__).resolve().parent', 'OUT = ' + repr(out) )
# repr(Path) needs the concrete class bound in this execution namespace.
namespace = {'__file__': str(probe), '__name__': '__main__', 'PosixPath': type(out)}
exec(compile(source, str(probe), 'exec'), namespace)
assert probe.read_bytes() == raw
