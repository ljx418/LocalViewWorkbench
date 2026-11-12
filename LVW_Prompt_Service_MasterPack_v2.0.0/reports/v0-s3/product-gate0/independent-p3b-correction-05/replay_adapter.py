"""Redirect only the immutable observation script's output directory."""
import hashlib
from pathlib import Path
OUT = Path(__file__).resolve().parent
original = OUT.parent / 'implementation-p3b-correction-05/probe_correction05_counterexamples.py'
raw = original.read_bytes()
assert hashlib.sha256(raw).hexdigest() == '202b14adc23c773896b85de503bac1ea19a047184fd1f28c2abf4580160f6ffa'
source = raw.decode()
needle = 'OUT = Path(__file__).resolve().parent'
assert source.count(needle) == 1
source = source.replace(needle, 'OUT = Path(' + repr(str(OUT)) + ')')
exec(compile(source, str(original), 'exec'), {'__name__': '__main__', '__file__': str(original)})
assert hashlib.sha256(original.read_bytes()).hexdigest() == hashlib.sha256(raw).hexdigest()
