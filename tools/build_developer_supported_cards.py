from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "contracts/ptcgdap/ucis_card_catalog_v1.json"
QUALIFICATION_PATH = ROOT / "contracts/ptcgdap/ucis_catalog_qualification_v1.json"
OUTPUT_PATH = ROOT / "data/developer/supported-cards-v1.json"
USABLE_STATUSES = {"automatic", "compiled"}
KNOWN_STATUSES = {*USABLE_STATUSES, "unsupported"}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("supported_cards_source_invalid")
    return value


def _raw_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def build_document() -> dict[str, Any]:
    catalog = _read_json(CATALOG_PATH)
    qualification = _read_json(QUALIFICATION_PATH)
    if catalog.get("document_type") != "ptcgdap_ucis_card_catalog_v1":
        raise ValueError("supported_cards_catalog_invalid")
    if qualification.get("qualification_status") != "passed":
        raise ValueError("supported_cards_qualification_not_passed")

    raw_cards = catalog.get("cards")
    if not isinstance(raw_cards, list):
        raise ValueError("supported_cards_catalog_invalid")
    cards: list[dict[str, Any]] = []
    seen: set[str] = set()
    status_counts: Counter[str] = Counter()
    for raw in sorted(raw_cards, key=lambda item: item.get("card_uid", "")):
        if not isinstance(raw, dict):
            raise ValueError("supported_cards_catalog_invalid")
        card_uid = raw.get("card_uid")
        status = raw.get("status")
        effect_id = raw.get("effect_id")
        if (
            not isinstance(card_uid, str)
            or not card_uid
            or card_uid in seen
            or status not in KNOWN_STATUSES
            or not isinstance(effect_id, str)
            or not effect_id
        ):
            raise ValueError("supported_cards_catalog_invalid")
        seen.add(card_uid)
        status_counts[status] += 1
        capability_ids = raw.get("capability_ids", [])
        if not isinstance(capability_ids, list) or not all(isinstance(value, str) for value in capability_ids):
            raise ValueError("supported_cards_catalog_invalid")
        cards.append(
            {
                "card_uid": card_uid,
                "effect_id": effect_id,
                "interaction_status": status,
                "usable": status in USABLE_STATUSES,
                "capability_ids": sorted(capability_ids),
                "source_path": raw.get("source_path"),
                "source_sha256": raw.get("source_sha256"),
            }
        )

    scope = qualification.get("scope", {})
    if not isinstance(scope, dict) or scope.get("total_cards") != len(cards):
        raise ValueError("supported_cards_count_mismatch")
    catalog_sha256 = _raw_sha256(CATALOG_PATH)
    qualification_sha256 = _raw_sha256(QUALIFICATION_PATH)
    identities = qualification.get("contract_identities", {})
    if not isinstance(identities, dict) or identities.get("catalog_raw_sha256") != catalog_sha256:
        raise ValueError("supported_cards_catalog_identity_mismatch")

    return {
        "document_type": "ptcg_strategy_forge_supported_cards_v1",
        "schema_version": 1,
        "identity_domain": catalog.get("identity_domain"),
        "ucis_generation": catalog.get("ucis_generation"),
        "qualification_status": qualification.get("qualification_status"),
        "claim": qualification.get("maximum_claim"),
        "counts": {
            "total_cards": len(cards),
            "usable_cards": sum(1 for row in cards if row["usable"]),
            "explicit_unsupported_cards": sum(1 for row in cards if not row["usable"]),
            "by_interaction_status": dict(sorted(status_counts.items())),
        },
        "status_meanings": {
            "automatic": "No author-visible selection program is required for this card effect.",
            "compiled": "The card effect interaction compiles to the qualified UCIS current-window contract.",
            "unsupported": "The effect is intentionally unavailable and must not silently fall back.",
        },
        "sources": {
            "catalog_path": CATALOG_PATH.relative_to(ROOT).as_posix(),
            "catalog_raw_sha256": catalog_sha256,
            "qualification_path": QUALIFICATION_PATH.relative_to(ROOT).as_posix(),
            "qualification_raw_sha256": qualification_sha256,
            "qualification_evidence_sha256": qualification.get("evidence_sha256"),
        },
        "limitations": [
            "Local card UID identity only; this is not official CABT Card ID equality.",
            "Usable means the declared interaction path is available, not full official rule-result parity.",
            "Display names are intentionally omitted because the qualified catalog owns local UID identity, not translations.",
            "Deck templates and strategy strength are separate from card interaction support.",
        ],
        "cards": cards,
    }


def encoded_document() -> bytes:
    return (json.dumps(build_document(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def verify_supported_cards_delivery() -> dict[str, Any]:
    expected = encoded_document()
    if not OUTPUT_PATH.is_file():
        raise ValueError("supported_cards_delivery_missing")
    actual = OUTPUT_PATH.read_bytes()
    if actual != expected:
        raise ValueError("supported_cards_delivery_stale")
    document = json.loads(actual)
    return {
        "accepted": True,
        "path": OUTPUT_PATH.relative_to(ROOT).as_posix(),
        "sha256": hashlib.sha256(actual).hexdigest().upper(),
        "total_cards": document["counts"]["total_cards"],
        "usable_cards": document["counts"]["usable_cards"],
        "explicit_unsupported_cards": document["counts"]["explicit_unsupported_cards"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the developer-facing supported-card snapshot.")
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in snapshot is missing or stale.")
    args = parser.parse_args()
    if args.check:
        print(json.dumps(verify_supported_cards_delivery(), ensure_ascii=False, indent=2))
        return 0
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = encoded_document()
    OUTPUT_PATH.write_bytes(payload)
    print(
        json.dumps(
            {
                "status": "written",
                "path": OUTPUT_PATH.relative_to(ROOT).as_posix(),
                "sha256": hashlib.sha256(payload).hexdigest().upper(),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
