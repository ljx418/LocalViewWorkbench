"""Replay the inspected immutable counterexamples once; redirect only OUT via AST."""
import ast
import hashlib
from pathlib import Path
OUT = Path(__file__).resolve().parent
source = OUT.parent / 'implementation-p3b-correction-04/replay_correction03_counterexamples.py'
raw = source.read_bytes()
tree = ast.parse(raw, filename=str(source))
for node in tree.body:
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'OUT' for t in node.targets):
        node.value = ast.parse('Path(' + repr(str(OUT)) + ')', mode='eval').body
        break
else:
    raise RuntimeError('output assignment absent')
print('immutable replay sha256=' + hashlib.sha256(raw).hexdigest())
exec(compile(ast.fix_missing_locations(tree), str(source), 'exec'), {'__name__':'__main__', '__file__':str(source)})
