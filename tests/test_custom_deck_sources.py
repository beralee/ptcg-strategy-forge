import copy
import hashlib
import json
from pathlib import Path
import unittest

from scripts.ai.ptcgdap.author_strategy_match_host import AuthorStrategyExactDeckGate, AuthorStrategyMatchError
from scripts.ai.ptcgdap.source_lock import canonical_json_v1_bytes

ROOT = Path(__file__).resolve().parents[1]


class CustomDeckSourceTests(unittest.TestCase):
    def setUp(self):
        self.cards = []
        for uid, count in sorted({"CSV6C_032": 4, "30thC_102": 4, "30thDC_040": 4, "CSVE1C_WAT": 48}.items()):
            raw = (ROOT / "data/bundled_user/cards" / (uid + ".json")).read_bytes()
            c = json.loads(raw)
            self.cards.append({"local_card_uid": uid, "count": count, "set_code": c["set_code"],
                "card_index": c["card_index"], "card_type": c["card_type"], "stage": c.get("stage", ""),
                "effect_id": c["effect_id"], "source_raw_sha256": hashlib.sha256(raw).hexdigest().upper(),
                "source_canonical_sha256": hashlib.sha256(canonical_json_v1_bytes(c)).hexdigest().upper()})
        self.manifest = {"document_type": "deck_manifest_windows_local_v1", "schema_version": 1,
            "card_id_domain": "godot_local_card_uid_v1", "platform_scope": ["windows"], "cabt_exportable": False,
            "source_deck_id": 2026092001, "unique_card_count": 4, "card_count": 60, "cards": self.cards}

    def map(self):
        rows = [{"local_card_uid": r["local_card_uid"], "count": r["count"]} for r in self.cards]
        return AuthorStrategyExactDeckGate.map_windows_local_rows(rows, self.manifest, root=ROOT)

    def test_custom_deck_uses_embedded_manifest_without_sdk_deck_install(self):
        self.assertFalse((ROOT / "data/bundled_user/decks/2026092001.json").exists())
        self.assertEqual(60, sum(r["count"] for r in self.map()))

    def test_tampered_source_hash_or_effect_is_rejected(self):
        original = copy.deepcopy(self.cards)
        for field in ("source_raw_sha256", "source_canonical_sha256", "effect_id"):
            with self.subTest(field=field):
                self.cards[0][field] = "0" * 64
                with self.assertRaises(AuthorStrategyMatchError): self.map()
                self.cards[:] = copy.deepcopy(original)

    def test_five_copies_of_trainer_are_rejected_even_when_total_is_sixty(self):
        self.cards[0]["count"] += 1
        self.cards[-1]["count"] -= 1
        with self.assertRaises(AuthorStrategyMatchError): self.map()

    def test_non_sixty_card_deck_is_rejected(self):
        self.cards[-1]["count"] -= 1
        with self.assertRaises(AuthorStrategyMatchError): self.map()
