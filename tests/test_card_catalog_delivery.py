from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tools.build_developer_supported_cards import validate_card_sources


class CardCatalogDeliveryTests(unittest.TestCase):
    def fixture(self, root: Path):
        path = root / "data/bundled_user/cards/NEW_001.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"set_code": "NEW", "card_index": "001", "effect_id": "new_effect"}), encoding="utf-8")
        return path, {"cards": [{"card_uid": "NEW_001", "effect_id": "new_effect",
            "source_path": path.relative_to(root).as_posix(),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest().upper()}]}

    def test_every_catalog_card_has_exact_portable_source(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, catalog = self.fixture(root)
            validate_card_sources(root, catalog)
            path.unlink()
            with self.assertRaisesRegex(ValueError, "supported_cards_source_missing"):
                validate_card_sources(root, catalog)

    def test_source_byte_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, catalog = self.fixture(root)
            path.write_bytes(path.read_bytes() + b"\n")
            with self.assertRaisesRegex(ValueError, "supported_cards_source_hash_mismatch"):
                validate_card_sources(root, catalog)

    def test_source_uid_and_effect_must_match_catalog(self):
        for field in ("card_uid", "effect_id"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                _, catalog = self.fixture(root)
                catalog["cards"][0][field] = "wrong"
                with self.assertRaisesRegex(ValueError, "supported_cards_source_identity_mismatch"):
                    validate_card_sources(root, catalog)

    def test_catalog_cannot_read_outside_bundled_cards(self):
        for path in ("../outside.json", "data/bundled_user/cards/../../secret.json", "C:/secret.json"):
            with self.subTest(path=path), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                _, catalog = self.fixture(root)
                catalog["cards"][0]["source_path"] = path
                with self.assertRaisesRegex(ValueError, "supported_cards_source_path_invalid"):
                    validate_card_sources(root, catalog)
