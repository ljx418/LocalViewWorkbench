import sys,json
from pathlib import Path
import pytest
O=Path(__file__).resolve().parent
nodes=json.loads((O/'selection.json').read_text())['nodes']
raise SystemExit(pytest.main(nodes+['-q','-p','no:cacheprovider','--basetemp='+str(O/'pytest-temp')]))
