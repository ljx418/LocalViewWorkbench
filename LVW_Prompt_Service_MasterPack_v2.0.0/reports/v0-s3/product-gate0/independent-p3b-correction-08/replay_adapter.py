"""Change only the immutable resource probe's output directory in memory."""
import hashlib
from pathlib import Path
probe = Path(__file__).resolve().parent.parent / 'implementation-p3b-correction-08/probe_correction08_counterexamples.py'
raw = probe.read_bytes()
assert hashlib.sha256(raw).hexdigest() == 'e664f586d1d6db6b049c7de05475b77dbf9fe5848985b8fd160a9aa5b7e235d9'
old = 'OUT = Path(__file__).resolve().parent'
assert raw.decode().count(old) == 1
source = raw.decode().replace(old, 'OUT = Path(' + repr(str(Path(__file__).resolve().parent)) + ')')
exec(compile(source, str(probe), 'exec'), {'__name__': '__main__', '__file__': str(probe)})
assert hashlib.sha256(probe.read_bytes()).hexdigest() == 'e664f586d1d6db6b049c7de05475b77dbf9fe5848985b8fd160a9aa5b7e235d9'
