from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ptcg_strategy_forge.ucis_runtime import (  # noqa: E402
    CONTRACT_GENERATION,
    CONTEXT_NAMES,
    OPTION_FIELDS,
    OPTION_TYPE_NAMES,
    REGISTRY_SHA256,
    UCIS_GENERATION,
    PublicBattleFacts,
    SelectionWindow,
    UcisRuntimeError,
    option,
    semantic_key,
)
from ptcg_strategy_forge import SelectionWindow as PublicSelectionWindow  # noqa: E402
from scripts.ai.ptcgdap.ucis_sdk import UcisDeveloperSdk  # noqa: E402


def _observation(options: list[dict], *, minimum: int = 0, maximum: int = 5) -> dict:
    return {
        "select": {
            "type": 1,
            "context": 24,
            "minCount": minimum,
            "maxCount": maximum,
            "remainDamageCounter": 0,
            "remainEnergyCost": 0,
            "option": options,
            "deck": None,
            "contextCard": None,
            "effect": None,
        },
        "logs": [],
        "current": {
            "turn": 8,
            "turnActionCount": 3,
            "yourIndex": 0,
            "players": [
                {
                    "active": [{"energies": [1]}],
                    "bench": [{}, {}],
                    "benchMax": 5,
                    "deckCount": 31,
                    "handCount": 5,
                    "prize": [None, None, None, None],
                },
                {
                    "active": [{"energies": [1, 2]}],
                    "bench": [{}],
                    "benchMax": 5,
                    "deckCount": 29,
                    "handCount": 6,
                    "prize": [None, None],
                },
            ],
        },
    }


class UcisRuntimeSdkTests(unittest.TestCase):
    def test_embedded_runtime_contract_matches_vendored_generation(self) -> None:
        self.assertIs(SelectionWindow, PublicSelectionWindow)
        sdk = UcisDeveloperSdk.load(ROOT)
        self.assertEqual(sdk.registry.ucis_generation, UCIS_GENERATION)
        self.assertEqual(sdk.registry.contract_generation, CONTRACT_GENERATION)
        self.assertEqual(sdk.registry.document_hash, REGISTRY_SHA256)
        ordered_rows = [sdk.registry.context_rows[index] for index in range(49)]
        self.assertEqual(tuple(row.context_name for row in ordered_rows), CONTEXT_NAMES)
        self.assertEqual(
            tuple(sdk.option_types[name] for name in OPTION_TYPE_NAMES),
            tuple(range(17)),
        )
        self.assertEqual(
            tuple(sdk.registry.option_shapes[index] for index in range(17)),
            OPTION_FIELDS,
        )
        for row in ordered_rows:
            options = []
            for option_type in row.option_types:
                fields = {
                    field: 0
                    for field in sdk.registry.option_shapes[option_type]
                    if field != "type"
                }
                options.append(option(OPTION_TYPE_NAMES[option_type], **fields))
            raw = sdk.build_scenario_window(
                context_name=row.context_name,
                options=options,
                min_count=0,
                max_count=len(options),
            )
            parsed = SelectionWindow.parse(raw)
            self.assertEqual(row.context_name, parsed.context_name)
            self.assertEqual(tuple(row.option_type_names), tuple(item.option_type_name for item in parsed.options))

    def test_exact_quantity_and_semantic_reorder_use_fresh_indexes(self) -> None:
        cards = [option("CARD", area=2, index=value, playerIndex=0) for value in (10, 20, 30, 40, 50)]
        first = SelectionWindow.parse(_observation(cards))
        wanted = [
            semantic_key("CARD", area=2, index=value, playerIndex=0)
            for value in (10, 30, 50)
        ]
        self.assertEqual([0, 2, 4], first.rebind(wanted))
        self.assertEqual(
            [0, 2, 4],
            first.choose_exact(3, lambda candidate: candidate.field("index") in {10, 30, 50}),
        )

        second = SelectionWindow.parse(_observation(list(reversed(cards))))
        self.assertEqual([4, 2, 0], second.rebind(wanted))
        self.assertEqual([4, 2, 0], second.validate_indexes([4, 2, 0]))

    def test_named_number_boolean_and_deterministic_fallback_helpers(self) -> None:
        count = SelectionWindow.parse(
            {
                "select": {
                    "type": 8,
                    "context": 38,
                    "minCount": 1,
                    "maxCount": 1,
                    "remainDamageCounter": 0,
                    "remainEnergyCost": 0,
                    "option": [option("NUMBER", number=1), option("NUMBER", number=3)],
                    "deck": None,
                    "contextCard": None,
                    "effect": None,
                }
            }
        )
        self.assertEqual([1], count.choose_number(3))

        boolean = SelectionWindow.parse(
            {
                "select": {
                    "type": 9,
                    "context": 43,
                    "minCount": 1,
                    "maxCount": 1,
                    "remainDamageCounter": 0,
                    "remainEnergyCost": 0,
                    "option": [option("NO"), option("YES")],
                    "deck": None,
                    "contextCard": None,
                    "effect": None,
                }
            }
        )
        self.assertEqual([1], boolean.choose_boolean(True))
        self.assertEqual([0], boolean.first_legal())

    def test_public_facts_expose_prize_clock_and_energy_debt_only(self) -> None:
        facts = PublicBattleFacts.parse(_observation([]))
        self.assertEqual(4, facts.acting_prizes_remaining)
        self.assertEqual(2, facts.opponent_prizes_remaining)
        self.assertEqual(1, facts.acting_active_energy_units)
        self.assertEqual(1, facts.acting_active_energy_debt(2))
        self.assertEqual(1, facts.acting_attack_windows_to_win(2))
        self.assertEqual(3, facts.acting_bench_free)

    def test_unknown_shape_and_missing_semantic_target_fail_closed(self) -> None:
        raw = _observation(
            [option("CARD", area=2, index=10, playerIndex=0)], maximum=1
        )
        raw["select"]["option"][0]["engineTicket"] = 7
        with self.assertRaisesRegex(UcisRuntimeError, "ucis_runtime_option_shape_invalid"):
            SelectionWindow.parse(raw)
        clean = SelectionWindow.parse(
            _observation(
                [option("CARD", area=2, index=10, playerIndex=0)], maximum=1
            )
        )
        with self.assertRaisesRegex(UcisRuntimeError, "ucis_runtime_semantic_rebind_missing"):
            clean.rebind([semantic_key("CARD", area=2, index=99, playerIndex=0)])

    def test_checked_in_walkthrough_is_directly_executable(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "demo/marnie-forge/sdk_walkthrough.py")],
            cwd=ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        report = json.loads(completed.stdout)
        self.assertEqual("passed", report["status"])
        self.assertEqual([0, 2, 4], report["exact_quantity"]["first_indexes"])
        self.assertEqual([4, 2, 0], report["exact_quantity"]["reordered_indexes"])
        self.assertTrue(report["fresh_reobserve"])


if __name__ == "__main__":
    unittest.main()
