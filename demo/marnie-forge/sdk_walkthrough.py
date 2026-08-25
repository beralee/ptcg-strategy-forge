from __future__ import annotations

"""Executable UCIS SDK walkthrough used by `forge demo` and developer docs."""

import copy
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ptcg_strategy_forge.ucis_runtime import (  # noqa: E402
    PublicBattleFacts,
    SelectionWindow,
    UcisRuntimeError,
    option,
    semantic_key,
)


def _current() -> dict:
    return {
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
    }


def _window(context: int, options: list[dict], minimum: int, maximum: int) -> dict:
    select_type = 1
    return {
        "select": {
            "type": select_type,
            "context": context,
            "minCount": minimum,
            "maxCount": maximum,
            "remainDamageCounter": 0,
            "remainEnergyCost": 0,
            "option": options,
            "deck": None,
            "contextCard": None,
            "effect": None,
        },
        "current": _current(),
        "logs": [],
    }


def run_walkthrough() -> dict:
    card_options = [
        option("CARD", area=2, index=value, playerIndex=0)
        for value in (10, 20, 30, 40, 50)
    ]
    wanted = [
        semantic_key("CARD", area=2, index=value, playerIndex=0)
        for value in (10, 30, 50)
    ]
    first = SelectionWindow.parse(_window(24, card_options, 0, 5))
    first_indexes = first.rebind(wanted)

    # A new callback means a new immutable window. Reparse it and bind the same
    # semantic goals to its new indexes; never reuse first_indexes.
    second = SelectionWindow.parse(_window(24, list(reversed(card_options)), 0, 5))
    reordered_indexes = second.rebind(wanted)

    target = semantic_key("CARD", area=3, index=1, playerIndex=0)
    assignment_first = SelectionWindow.parse(
        _window(
            22,
            [
                option("CARD", area=1, index=0, playerIndex=0),
                option("CARD", area=3, index=1, playerIndex=0),
            ],
            1,
            1,
        )
    )
    assignment_second = SelectionWindow.parse(
        _window(
            22,
            [
                option("CARD", area=3, index=1, playerIndex=0),
                option("CARD", area=1, index=0, playerIndex=0),
            ],
            1,
            1,
        )
    )

    facts = PublicBattleFacts.parse(_window(24, card_options, 0, 5))
    unknown = copy.deepcopy(_window(24, card_options, 0, 5))
    unknown["select"]["option"][0]["engineTicket"] = 7
    try:
        SelectionWindow.parse(unknown)
        unknown_error = ""
    except UcisRuntimeError as error:
        unknown_error = error.code

    accepted = (
        first_indexes == [0, 2, 4]
        and reordered_indexes == [4, 2, 0]
        and assignment_first.rebind([target]) == [1]
        and assignment_second.rebind([target]) == [0]
        and facts.acting_active_energy_debt(2) == 1
        and facts.acting_attack_windows_to_win(2) == 1
        and unknown_error == "ucis_runtime_option_shape_invalid"
    )
    return {
        "document_type": "ptcg_strategy_forge_ucis_sdk_walkthrough_v1",
        "schema_version": 1,
        "status": "passed" if accepted else "failed",
        "exact_quantity": {
            "desired_count": 3,
            "first_indexes": first_indexes,
            "reordered_indexes": reordered_indexes,
        },
        "repeated_assignment": {
            "first_indexes": assignment_first.rebind([target]),
            "reordered_indexes": assignment_second.rebind([target]),
        },
        "public_facts": {
            "acting_energy_units": facts.acting_active_energy_units,
            "acting_energy_debt_for_two": facts.acting_active_energy_debt(2),
            "opponent_prizes_remaining": facts.opponent_prizes_remaining,
            "acting_attack_windows_to_win_at_two_prizes": facts.acting_attack_windows_to_win(2),
        },
        "unknown_shape_error": unknown_error,
        "fresh_reobserve": first_indexes != reordered_indexes,
        "claims": {
            "current_window_indexes_only": True,
            "engine_authority": False,
            "full_rule_a3": False,
            "production_authority": False,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_walkthrough(), ensure_ascii=False, separators=(",", ":")))
