import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ai.ptcgdap.public_input_v3 import contract
path = ROOT / 'contracts/ptcgdap/public_input_v3.json'
data = (json.dumps(contract(), ensure_ascii=False, indent=2) + '\n').encode()
if '--check' in sys.argv:
    if not path.exists() or path.read_bytes() != data: raise SystemExit('public_input_v3_contract_drift')
else:
    path.write_bytes(data)
