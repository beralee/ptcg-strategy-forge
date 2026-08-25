from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]
REVIEWED_DECK_IDS = (800018501, 800017097, 800018499, 800018509, 800018502)


def sync(source_root: Path) -> dict[str, object]:
    source_root = source_root.resolve(strict=True)
    copied_cards: set[str] = set()
    copied_decks: list[int] = []
    for deck_id in REVIEWED_DECK_IDS:
        source_deck = source_root / "data/bundled_user/decks" / f"{deck_id}.json"
        deck = json.loads(source_deck.read_text(encoding="utf-8"))
        if deck.get("id") != deck_id or deck.get("total_cards") != 60 or not isinstance(deck.get("cards"), list):
            raise ValueError(f"reviewed_deck_invalid:{deck_id}")
        target_deck = ROOT / "data/bundled_user/decks" / source_deck.name
        target_deck.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_deck, target_deck)
        copied_decks.append(deck_id)
        for row in deck["cards"]:
            uid = f"{row['set_code']}_{row['card_index']}"
            source_card = source_root / "data/bundled_user/cards" / f"{uid}.json"
            card = json.loads(source_card.read_text(encoding="utf-8"))
            if card.get("set_code") != row["set_code"] or card.get("card_index") != row["card_index"]:
                raise ValueError(f"reviewed_card_identity_invalid:{uid}")
            target_card = ROOT / "data/bundled_user/cards" / source_card.name
            target_card.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_card, target_card)
            copied_cards.add(uid)
    return {
        "document_type": "ptcg_strategy_forge_reviewed_deck_sync_v1",
        "schema_version": 1,
        "source_root": str(source_root),
        "deck_ids": copied_decks,
        "deck_count": len(copied_decks),
        "unique_card_count": len(copied_cards),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(sync(args.source_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
