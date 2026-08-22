from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


SUITE_DOCUMENT_TYPE = "ptcg_strategy_forge_scenario_suite_v1"
FORBIDDEN_REPORT_KEYS = {
    "raw_observation",
    "search_begin_input",
    "opponent_hand",
    "opponent_deck",
    "deck_order",
    "private_rng",
    "callback",
    "ticket",
    "command",
}


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _case(base: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    value = copy.deepcopy(base)
    value["scenario_id"] = scenario_id
    value["prompt"]["prompt_id"] = scenario_id
    return value


def generate_demo_scenarios(
    demo_root: Path,
    *,
    matched_rule_id: str = "forge.morgrem.evolve",
    scenario_namespace: str = "forge",
) -> dict[str, object]:
    scenario_root = demo_root / "scenarios"
    scaffold_path = scenario_root / "morgrem-evolve.json"
    base_path = scaffold_path if scaffold_path.is_file() else scenario_root / "01-positive.json"
    base = load_json(base_path)
    base["scenario_id"] = f"{scenario_namespace}-morgrem-positive"
    base["prompt"]["prompt_id"] = f"{scenario_namespace}-morgrem-positive"
    write_json(scenario_root / "01-positive.json", base)

    no_hand = _case(base, f"{scenario_namespace}-morgrem-no-hand")
    no_hand["local_uid_bindings"]["acting_hand"] = [
        {"serial": 30, "local_card_uid": "CSV10C_216"}
    ]
    no_hand["expected_selected_indexes"] = [0]
    write_json(scenario_root / "02-no-key-card.json", no_hand)

    wrong_target = _case(base, f"{scenario_namespace}-morgrem-wrong-target")
    wrong_target["local_uid_bindings"]["options"][1]["local_card_uid"] = "CSV10C_147"
    wrong_target["expected_selected_indexes"] = [0]
    write_json(scenario_root / "03-wrong-target.json", wrong_target)

    reordered = _case(base, f"{scenario_namespace}-morgrem-reordered")
    reordered["local_uid_bindings"]["options"] = [
        {"index": 0, "local_card_uid": "CSV10C_146"},
        {"index": 1, "local_card_uid": None},
    ]
    reordered["expected_selected_indexes"] = [0]
    write_json(scenario_root / "04-reordered.json", reordered)

    mandatory = _case(base, f"{scenario_namespace}-morgrem-mandatory-block")
    mandatory["prompt"]["mandatory_indexes"] = [0]
    mandatory["expected_selected_indexes"] = [0]
    write_json(scenario_root / "05-mandatory-block.json", mandatory)

    terminal = _case(base, f"{scenario_namespace}-morgrem-terminal-block")
    terminal["prompt"]["terminal_indexes"] = [0]
    terminal["expected_selected_indexes"] = [0]
    write_json(scenario_root / "06-terminal-block.json", terminal)

    hard_tier = _case(base, f"{scenario_namespace}-morgrem-hard-tier-block")
    hard_tier["prompt"]["base_hard_tiers"] = [
        {"index": 0, "tier": [0]},
        {"index": 1, "tier": [1]},
    ]
    hard_tier["expected_selected_indexes"] = [0]
    write_json(scenario_root / "07-hard-tier-block.json", hard_tier)

    veto = _case(base, f"{scenario_namespace}-morgrem-veto-block")
    veto["prompt"]["base_vetoed_indexes"] = [1]
    veto["expected_selected_indexes"] = [0]
    write_json(scenario_root / "08-veto-block.json", veto)

    unknown_uid = _case(base, f"{scenario_namespace}-morgrem-unknown-uid")
    unknown_uid["local_uid_bindings"]["options"][1]["local_card_uid"] = "PRIVATE_SENTINEL"
    write_json(scenario_root / "09-unknown-uid.json", unknown_uid)

    hidden_field = _case(base, f"{scenario_namespace}-hidden-field-rejected")
    hidden_field["raw_observation"]["current"]["players"][1]["hand"] = [
        {"id": 7, "serial": 31, "playerIndex": 1}
    ]
    write_json(scenario_root / "10-hidden-field.json", hidden_field)

    cases = [
        {
            "id": "positive",
            "path": "scenarios/01-positive.json",
            "expect": {
                "status": "passed",
                "selected_indexes": [1],
                "matched_rule_id": matched_rule_id,
                "selected_source": "adapter_proposal",
            },
        },
        {
            "id": "no-key-card",
            "path": "scenarios/02-no-key-card.json",
            "expect": {"status": "passed", "selected_indexes": [0], "selected_source": "deterministic_fallback"},
        },
        {
            "id": "wrong-target",
            "path": "scenarios/03-wrong-target.json",
            "expect": {"status": "passed", "selected_indexes": [0], "selected_source": "deterministic_fallback"},
        },
        {
            "id": "reordered",
            "path": "scenarios/04-reordered.json",
            "expect": {
                "status": "passed",
                "selected_indexes": [0],
                "matched_rule_id": matched_rule_id,
                "selected_source": "adapter_proposal",
            },
        },
        {
            "id": "mandatory-block",
            "path": "scenarios/05-mandatory-block.json",
            "expect": {"status": "passed", "selected_indexes": [0], "selected_source": "mandatory"},
        },
        {
            "id": "terminal-block",
            "path": "scenarios/06-terminal-block.json",
            "expect": {"status": "passed", "selected_indexes": [0], "selected_source": "terminal"},
        },
        {
            "id": "hard-tier-block",
            "path": "scenarios/07-hard-tier-block.json",
            "expect": {"status": "passed", "selected_indexes": [0], "selected_source": "deterministic_fallback"},
        },
        {
            "id": "veto-block",
            "path": "scenarios/08-veto-block.json",
            "expect": {"status": "passed", "selected_indexes": [0], "selected_source": "deterministic_fallback"},
        },
        {
            "id": "unknown-uid",
            "path": "scenarios/09-unknown-uid.json",
            "expect": {"status": "error", "error_code": "invalid_local_uid_public_context"},
        },
        {
            "id": "hidden-field",
            "path": "scenarios/10-hidden-field.json",
            "expect": {"status": "error", "error_code": "developer_observation_rejected"},
        },
    ]
    suite = {"document_type": SUITE_DOCUMENT_TYPE, "schema_version": 1, "cases": cases}
    write_json(demo_root / "scenario-suite.json", suite)
    if scaffold_path.is_file():
        scaffold_path.unlink()
    return {"scenario_count": len(cases), "suite_path": str(demo_root / "scenario-suite.json")}


def assert_public_report(value: object) -> None:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            for key, child in current.items():
                if key.lower() in FORBIDDEN_REPORT_KEYS:
                    raise ValueError("simulation_report_private_key")
                stack.append(child)
        elif isinstance(current, list):
            stack.extend(current)
