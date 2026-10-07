"""Generate the versioned Base observation contract from its owning validator."""
from pathlib import Path
import argparse
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.ai.ptcgdap.base_input import contract_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    target = ROOT/'contracts/ptcgdap/base_input_v1.json'
    data = (json.dumps(json.loads(contract_bytes()), ensure_ascii=False, indent=2) + '\n').encode()
    if args.check:
        if not target.exists() or target.read_bytes() != data:
            raise SystemExit('base_input_contract_drift')
    else:
        target.write_bytes(data)


if __name__ == '__main__':
    main()
