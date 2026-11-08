"""Native NTFS runner: normalize JSON relative-path keys, preserving every assertion.
The repository verifier expects POSIX keys in its data dictionary. Windows Path.__str__
uses backslashes. Only those four relative-key/diagnostic serializations are adapted;
no file discovery, manifest hash, schema, threshold or acceptance assertion is removed.
"""
from pathlib import Path
import sys
verifier=Path(sys.argv.pop(1))
source=verifier.read_text(encoding='utf-8')
old='str(f.relative_to(ROOT))'
assert source.count(old)==4,'Verifier changed: review the narrow path-key adapter again'
source=source.replace(old,'f.relative_to(ROOT).as_posix()')
exec(compile(source,str(verifier),'exec'),{'__name__':'__main__','__file__':str(verifier)})
