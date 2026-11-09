"""Source identity shared by launcher checks and the running API."""
from pathlib import Path
import hashlib

def build_id():
    root=Path(__file__).resolve().parents[3]
    files=list((root/'lvw/backend/app').glob('*.py'))+list((root/'lvw/frontend/dist').rglob('*'))
    files+=[root/'templates/analysis_system_zh.txt']
    files += [root/'LVW_V0_RuntimePatch/custom_nodes/lvw_v0_bridge'/name for name in
              ['core.py','video_files.py','video_input.py','video_process.py','video_decoder.py']]
    digest=hashlib.sha256()
    for p in sorted(x for x in files if x.is_file()):
        digest.update(str(p.relative_to(root)).encode()+b'\0'+p.read_bytes()+b'\0')
    return digest.hexdigest()
