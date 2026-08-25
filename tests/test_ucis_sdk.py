from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.ai.ptcgdap.ucis_sdk import UcisDeveloperSdk, UcisSdkError  # noqa: E402
from ptcg_strategy_forge.cli import (  # noqa: E402
    _ucis_qualification,
    doctor,
    inspect_ucis_scenario,
    run_ucis_sdk_walkthrough,
    ucis_catalog_report,
)


def _card(index: int) -> dict:
    return {"type": 3, "area": 2, "index": index, "playerIndex": 0}


class ForgeUcisSdkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sdk = UcisDeveloperSdk.load(ROOT)

    def test_vendored_registry_catalog_and_doctor_are_generation_closed(self) -> None:
        catalog = self.sdk.capability_catalog()
        self.assertEqual(catalog["ucis_generation"], 1)
        self.assertEqual(len(catalog["primitives"]), 16)
        self.assertEqual(catalog["closure"]["total_cards"], 797)
        for key in (
            "unregistered",
            "legacy_author_visible",
            "custom_prompt_builder",
            "silent_fallback",
        ):
            self.assertEqual(catalog["closure"][key], 0)
        checks = {row["id"]: row for row in doctor()["checks"]}
        self.assertTrue(checks["ucis-sdk"]["accepted"])
        self.assertTrue(checks["ucis-sdk"]["qualification"]["accepted"])
        self.assertEqual(
            checks["ucis-sdk"]["qualification"]["representative_operation_claim"],
            "corresponding_card_whole_battle_input_index_contract",
        )

    def test_developer_cli_reports_catalog_inspection_and_walkthrough(self) -> None:
        catalog = ucis_catalog_report()
        self.assertEqual("passed", catalog["status"])
        self.assertEqual(16, catalog["primitive_count"])
        self.assertEqual(729, catalog["usable_effects"])
        self.assertEqual(1, catalog["unsupported_effects"])

        inspection = inspect_ucis_scenario(
            ROOT / "demo/marnie-forge/scenarios/01-positive.json"
        )
        self.assertEqual("passed", inspection["status"])
        self.assertEqual("EVOLVES_TO", inspection["window"]["context"])
        self.assertEqual("CSV10C_146", inspection["window"]["options"][1]["local_card_uid"])
        rendered = json.dumps(inspection, ensure_ascii=False)
        self.assertNotIn("raw_observation", rendered)
        self.assertNotIn("search_begin_input", rendered)

        walkthrough = run_ucis_sdk_walkthrough()
        self.assertEqual("passed", walkthrough["status"])
        self.assertTrue(walkthrough["fresh_reobserve"])

    def test_author_can_parse_and_semantically_rebind_only_the_current_window(self) -> None:
        first = self.sdk.parse_selection(
            self.sdk.build_scenario_window(
                context_name="LOOK",
                options=[_card(10), _card(20), _card(30)],
                min_count=1,
                max_count=2,
            )
        )
        intent = [first.options[2].semantic_fingerprint, first.options[0].semantic_fingerprint]
        second = self.sdk.parse_selection(
            self.sdk.build_scenario_window(
                context_name="LOOK",
                options=[_card(30), _card(20), _card(10)],
                min_count=1,
                max_count=2,
            )
        )
        self.assertEqual(second.rebind_semantic_fingerprints(intent), [0, 2])
        self.assertEqual(second.validate_indexes([0, 2]), [0, 2])

    def test_unknown_private_select_field_fails_closed(self) -> None:
        raw = self.sdk.build_scenario_window(
            context_name="TO_HAND",
            options=[_card(1)],
            min_count=0,
            max_count=1,
        )
        raw["select"]["engine_ticket"] = "secret"
        with self.assertRaisesRegex(UcisSdkError, "ucis_sdk_select_fields_invalid"):
            self.sdk.parse_selection(raw)

    def test_vendored_qualification_receipts_preserve_claim_boundaries(self) -> None:
        contract_root = ROOT / "contracts/ptcgdap"
        qualification = json.loads(
            (contract_root / "ucis_catalog_qualification_v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(qualification["qualification_status"], "passed")
        self.assertEqual(qualification["scope"]["declared_usable"], 729)
        self.assertEqual(qualification["scope"]["explicit_unsupported"], 1)
        self.assertIn(
            "not_post_selection_state_damage_ko_rng_or_terminal_a3",
            qualification["nonclaims"],
        )
        payload = dict(qualification)
        expected = payload.pop("evidence_sha256")
        canonical = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        self.assertEqual(expected, hashlib.sha256(canonical).hexdigest().upper())

        operation = json.loads(
            (
                contract_root
                / "corresponding_card_whole_battle_input_index_v1.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(operation["qualification_status"], "passed")
        self.assertEqual(operation["post_state_comparison"], "not_claimed")
        self.assertEqual(
            operation["claim_scope"],
            "corresponding_card_whole_battle_input_index_contract",
        )

    def test_qualification_receipt_mutation_fails_closed_before_workspace_execution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="forge-ucis-qualification-") as name:
            root = Path(name)
            target = root / "contracts/ptcgdap"
            target.mkdir(parents=True)
            for filename in (
                "ucis_catalog_qualification_v1.json",
                "ucis_performance_qualification_v1.json",
                "corresponding_card_whole_battle_input_index_v1.json",
            ):
                shutil.copy2(ROOT / "contracts/ptcgdap" / filename, target / filename)
            document = json.loads(
                (target / "ucis_catalog_qualification_v1.json").read_text(
                    encoding="utf-8"
                )
            )
            document["scope"]["declared_usable"] -= 1
            (target / "ucis_catalog_qualification_v1.json").write_text(
                json.dumps(document, ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "ucis_catalog_qualification_invalid"):
                _ucis_qualification(root)


if __name__ == "__main__":
    unittest.main()
