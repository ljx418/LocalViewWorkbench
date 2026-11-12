"""Redirect only the immutable observation script's output directory."""
import hashlib
from pathlib import Path
OUT = Path(__file__).resolve().parent
original = OUT.parent / 'implementation-p3b-correction-06/probe_correction06_counterexamples.py'
raw = original.read_bytes()
assert hashlib.sha256(raw).hexdigest() == '6892409b377a737dd6161f55d33d0067aeceefe5ff6f5ac8f454805229c5a966'
source = raw.decode()
needle = 'OUT = Path(__file__).resolve().parent'
assert source.count(needle) == 1
source = source.replace(needle, 'OUT = Path(' + repr(str(OUT)) + ')')
exec(compile(source, str(original), 'exec'), {'__name__': '__main__', '__file__': str(original)})
assert hashlib.sha256(original.read_bytes()).hexdigest() == hashlib.sha256(raw).hexdigest()
