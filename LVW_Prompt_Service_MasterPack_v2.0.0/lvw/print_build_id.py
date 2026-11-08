"""No server/model side effects: print the exact local API build fingerprint."""
from pathlib import Path
import runpy
if __name__=='__main__':
    module=runpy.run_path(str(Path(__file__).parent/'backend/app/build_info.py'))
    print(module['build_id']())
