"""The distributed damage planner must recognize every shipped printing."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DamageRegistryCatalogTests(unittest.TestCase):
    def test_all_bundled_printings_have_damage_metadata(self):
        catalog = {}
        for path in (ROOT / "data/bundled_user/cards").glob("*.json"):
            card = json.loads(path.read_bytes())
            catalog[f'{card["set_code"]}_{card["card_index"]}'] = card
        registry = json.loads((ROOT / "contracts/ptcgdap/public_damage_capability_registry_v1.json").read_bytes())
        self.assertEqual(set(catalog), set(registry["cards"]), "damage_registry_catalog_gap")
        self.assertEqual(len(catalog), registry["generation"]["card_count"])
        for uid, card in catalog.items():
            with self.subTest(uid=uid):
                entry = registry["cards"][uid]
                self.assertEqual(entry["max_hp"], card.get("hp", 0) if type(card.get("hp")) is int else 0)
                self.assertEqual(entry["has_ability"], bool(card.get("abilities", [])))


if __name__ == "__main__":
    unittest.main()
