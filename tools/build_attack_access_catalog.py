"""Generate a small reviewed transition catalog, separate from damage proofs."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'contracts/ptcgdap/public_attack_access_catalog_v1.json'


def build():
    # Reviewed public printings; no private deck template is required.
    uids = set(['30thC_101', '30thC_102', '30thDC_039', '30thDC_040', 'CSV10C_146', 'CSV10C_147', 'CSV10C_148', 'CSV1C_079', 'CSV1C_127', 'CSV3C_123', 'CSV6C_114', 'CSV6C_125', 'CSV7C_177', 'CSV7C_203', 'CSV8C_081', 'CSV8C_082', 'CSV8C_083', 'CSV8C_094', 'CSV8C_135', 'CSV8C_157', 'CSV8C_158', 'CSV8C_159', 'CSV8C_172', 'CSV8C_183', 'CSV8C_203', 'CSV9.5C_004', 'CSV9C_078', 'CSVE1C_DAR', 'CSVE1C_FIR', 'CSVE1C_PSY', 'CSVH1C_045'])
    cards = {}; sources = []
    for uid in sorted(uids):
        path = ROOT / 'data/bundled_user/cards' / (uid + '.json')
        raw = path.read_bytes(); card = json.loads(raw)
        sources.append({'path': path.relative_to(ROOT).as_posix(),
                        'sha256': hashlib.sha256(raw).hexdigest().upper()})
        attacks = []
        for i, a in enumerate(card.get('attacks', [])):
            if not str(a.get('damage', '')).isdigit(): continue
            # Ordinal pressure, NOT hypothetical damage / KO / win probability.
            bonus = 60 if uid == 'CSV8C_159' and i == 1 else 90 if uid == 'CSV9.5C_004' else 30 if uid == 'CSV10C_148' else 0
            attacks.append({'index': i, 'cost': a['cost'].replace('0', ''),
                            'pressure': int(a['damage']) + bonus})
        model = 'basic' if card['card_type'] == 'Basic Energy' else (
            'luminous' if uid == 'CSV1C_127' else 'neo_upper' if uid == 'CSV7C_203' else '')
        cards[uid] = {'name': card['name'], 'from': card.get('evolves_from', ''),
            'stage': {'Basic': 0, 'Stage 1': 1, 'Stage 2': 2}.get(card.get('stage'), -1),
            'retreat': card.get('retreat_cost', 0), 'hp': card.get('hp', 0),
            'engine': bool(card.get('abilities')), 'energy_model': model,
            # Reviewed Drakloak Recon Directive: public legal use, no resource
            # payment, inspect two and retain one. Never guess its draw result.
            'information_abilities': [0] if uid == 'CSV8C_158' else [],
            'information_minimum_deck_count': 2 if uid == 'CSV8C_158' else 0,
            'energy_type': card.get('energy_provides', '') if model == 'basic' else card.get('energy_type', ''), 'attacks': attacks}
    return {'profile_id': 'public-attack-access-v1', 'schema_version': 1,
        'scope': 'conditional_public_resource_plans_not_damage_or_legality_proofs',
        'max_actions': 3, 'cards': cards, 'sources': sources}


if __name__ == '__main__':
    import sys
    raw = (json.dumps(build(), ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    if '--check' in sys.argv:
        if OUTPUT.read_bytes() != raw: raise SystemExit('attack_access_catalog_stale')
    else: OUTPUT.write_bytes(raw)
