"""Generate the closed v2 public semantic contract; never modify v1."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ai.ptcgdap.public_input_v2 import contract

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    path = ROOT / 'contracts/ptcgdap/public_input_v2.json'
    content = (json.dumps(contract(), ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    if args.check:
        if not path.is_file() or path.read_bytes() != content:
            raise SystemExit('public_input_v2_contract_drift')
    else:
        path.write_bytes(content)
