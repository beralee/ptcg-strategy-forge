from __future__ import annotations

import copy
import json
from pathlib import Path
import re
from typing import Any

from scripts.ai.ptcgdap.author_strategy_package import (
    AuthorStrategyPackageError,
    AuthorStrategyPackageLoader,
    WINDOWS_LOCAL_DECK_DOMAIN,
)
from scripts.ai.ptcgdap.competitive_policy_v2 import (
    CompetitivePolicyV2Compiler,
    CompetitivePolicyV2Runtime,
)
from scripts.ai.ptcgdap.public_damage_planning import SemanticTransactionJournal
from scripts.ai.ptcgdap.source_lock import load_json_bytes_strict


SUITE_DOCUMENT_TYPE = "ptcg_strategy_forge_scenario_suite_v1"
COMPETITIVE_SCENARIO_DOCUMENT_TYPE = "ptcg_strategy_forge_competitive_scenario_v2"
COMPETITIVE_SCENARIO_KEYS = {
    "document_type",
    "schema_version",
    "scenario_id",
    "frame",
    "base_authority",
    "expected_selected_indexes",
}
BASE_AUTHORITY_KEYS = {
    "mandatory_indexes",
    "terminal_indexes",
    "base_hard_tiers",
    "base_vetoed_indexes",
}
SCENARIO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
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


def is_competitive_scenario(value: object) -> bool:
    return (
        type(value) is dict
        and value.get("document_type") == COMPETITIVE_SCENARIO_DOCUMENT_TYPE
        and value.get("schema_version") == 2
    )


def simulate_competitive_public_frame(
    package_path: Path,
    scenario_path: Path,
) -> dict[str, object]:
    """Replay one sealed v2 public frame without claiming engine authority."""

    try:
        scenario = load_json(Path(scenario_path))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("competitive_scenario_invalid") from error
    if (
        type(scenario) is not dict
        or set(scenario) != COMPETITIVE_SCENARIO_KEYS
        or not is_competitive_scenario(scenario)
        or type(scenario.get("scenario_id")) is not str
        or SCENARIO_ID.fullmatch(scenario["scenario_id"]) is None
        or type(scenario.get("frame")) is not dict
        or type(scenario.get("base_authority")) is not dict
        or set(scenario["base_authority"]) != BASE_AUTHORITY_KEYS
        or type(scenario.get("expected_selected_indexes")) is not list
        or any(type(index) is not int for index in scenario["expected_selected_indexes"])
    ):
        raise ValueError("competitive_scenario_invalid")

    error_code = ""
    decision = None
    package = None
    try:
        package = AuthorStrategyPackageLoader().load_path(Path(package_path))
        metadata = package.to_dict()
        if metadata.get("deck_card_id_domain") != WINDOWS_LOCAL_DECK_DOMAIN:
            error_code = "package_policy_unsupported"
        else:
            deck = load_json_bytes_strict(package.payload_bytes("deck/deck_manifest.json"))
            adapter = load_json_bytes_strict(package.payload_bytes("policy/adapter.json"))
            allowed_uids = {
                row.get("local_card_uid")
                for row in deck.get("cards", [])
                if type(row) is dict and type(row.get("local_card_uid")) is str
            }
            compiled = CompetitivePolicyV2Compiler.compile_local_uid(
                adapter,
                allowed_card_uids=allowed_uids,
            )
            if not compiled.accepted or compiled.policy is None:
                error_code = compiled.error_code or "package_policy_unsupported"
            else:
                authority = scenario["base_authority"]
                decision = CompetitivePolicyV2Runtime.decide(
                    compiled.policy,
                    scenario["frame"],
                    transaction_journal=SemanticTransactionJournal(
                        f"scenario:{scenario['scenario_id']}",
                        int(scenario["frame"].get("seat", 0)),
                        f"{package.package_id}@{package.package_version}#{package.archive_sha256}",
                    ),
                    mandatory_indexes=copy.deepcopy(authority["mandatory_indexes"]),
                    terminal_indexes=copy.deepcopy(authority["terminal_indexes"]),
                    base_hard_tiers=copy.deepcopy(authority["base_hard_tiers"]),
                    base_vetoed_indexes=copy.deepcopy(authority["base_vetoed_indexes"]),
                )
                if not decision.accepted:
                    error_code = decision.error_code or "competitive_policy_failed"
    except AuthorStrategyPackageError as error:
        error_code = error.code
    except (OSError, KeyError, UnicodeDecodeError, TypeError, ValueError):
        error_code = "competitive_simulation_failed"

    audit = decision.audit if decision is not None and decision.accepted else {}
    selected = decision.selected_indexes if decision is not None and decision.accepted else []
    matched_rules: list[dict[str, str]] = []
    seen_rule_ids: set[str] = set()
    for scorecard in audit.get("scorecards", []):
        if type(scorecard) is not dict:
            continue
        for match in scorecard.get("matched_rules", []):
            rule_id = match.get("rule_id") if type(match) is dict else None
            if type(rule_id) is str and rule_id not in seen_rule_ids:
                seen_rule_ids.add(rule_id)
                matched_rules.append({"rule_id": rule_id})
    owner = audit.get("owner_layer")
    if owner in {"terminal", "mandatory"}:
        selected_source = str(owner)
    elif bool(audit.get("fallback_used", False)):
        selected_source = "deterministic_fallback"
    else:
        selected_source = "adapter_proposal"
    expected = scenario["expected_selected_indexes"]
    matched = not error_code and selected == expected
    status = "passed" if matched else ("error" if error_code else "failed")
    package_report = {
        "package_id": package.package_id if package is not None else "",
        "package_version": package.package_version if package is not None else "",
        "archive_sha256": package.archive_sha256 if package is not None else "",
    }
    return {
        "document_type": "ptcg_strategy_forge_competitive_simulation_report_v2",
        "schema_version": 2,
        "status": status,
        "error_code": error_code if error_code else ("" if matched else "simulation_expectation_failed"),
        "scenario_id": scenario["scenario_id"],
        "package": package_report,
        "adapter": {
            "matched_rules": matched_rules,
            "policy_hash": audit.get("policy_hash", ""),
        },
        "decision": {
            "selected_indexes": list(selected),
            "audit_hash": audit.get("audit_hash", ""),
        },
        "adjudication": {
            "selected_source": selected_source,
            "owner_layer": owner if type(owner) is str else "",
            "fallback_used": bool(audit.get("fallback_used", False)),
        },
        "expectation": {"selected_indexes": copy.deepcopy(expected), "matched": matched},
        "claims": {
            "public_only": True,
            "current_window_indexes_only": True,
            "authoritative": False,
            "engine_execution": False,
            "production_authority": False,
            "classic_fallback_used": False,
        },
    }


def _case(base: dict[str, Any], scenario_id: str) -> dict[str, Any]:
    value = copy.deepcopy(base)
    value["scenario_id"] = scenario_id
    value["prompt"]["prompt_id"] = scenario_id
    return value


def _normalize_evolution_window(base: dict[str, Any]) -> None:
    """Bind the demo to the UCIS EVOLVES_TO CARD window, not a YES/NO fixture header."""
    select = base["raw_observation"]["select"]
    select["type"] = 1
    select["context"] = 19
    select["minCount"] = 1
    select["maxCount"] = 1
    select["remainDamageCounter"] = 0
    select["remainEnergyCost"] = 0
    select["deck"] = None
    select["contextCard"] = None
    select["effect"] = None


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
    _normalize_evolution_window(base)
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


def generate_macro_scenarios(
    workspace: Path,
    *,
    matched_rule_id: str,
    namespace: str,
    hand_uid: str,
    target_uid: str,
    active_uid: str,
    decoy_hand_uid: str,
    decoy_target_uid: str,
) -> dict[str, object]:
    """Generate the standard ten-case proof matrix for one reviewed macro.

    The fixture shape is inherited from the accepted Marnie demo, while every
    semantic identity is rebound to the selected deck's exact local UID domain.
    """
    scenario_root = workspace / "scenarios"
    scaffold_path = scenario_root / "morgrem-evolve.json"
    base_path = scaffold_path if scaffold_path.is_file() else scenario_root / "01-positive.json"
    base = load_json(base_path)
    _normalize_evolution_window(base)
    base_id = f"{namespace}-primary-positive"
    base["scenario_id"] = base_id
    base["prompt"]["prompt_id"] = base_id
    base["local_uid_bindings"]["acting_hand"] = [
        {"serial": 30, "local_card_uid": hand_uid}
    ]
    base["local_uid_bindings"]["acting_active"] = [
        {"serial": 10, "local_card_uid": active_uid}
    ]
    base["local_uid_bindings"]["options"] = [
        {"index": 0, "local_card_uid": None},
        {"index": 1, "local_card_uid": target_uid},
    ]
    base["expected_selected_indexes"] = [1]
    write_json(scenario_root / "01-positive.json", base)

    no_hand = _case(base, f"{namespace}-primary-no-hand")
    no_hand["local_uid_bindings"]["acting_hand"] = [
        {"serial": 30, "local_card_uid": decoy_hand_uid}
    ]
    no_hand["expected_selected_indexes"] = [0]
    write_json(scenario_root / "02-no-key-card.json", no_hand)

    wrong_target = _case(base, f"{namespace}-primary-wrong-target")
    wrong_target["local_uid_bindings"]["options"][1]["local_card_uid"] = decoy_target_uid
    wrong_target["expected_selected_indexes"] = [0]
    write_json(scenario_root / "03-wrong-target.json", wrong_target)

    reordered = _case(base, f"{namespace}-primary-reordered")
    reordered["local_uid_bindings"]["options"] = [
        {"index": 0, "local_card_uid": target_uid},
        {"index": 1, "local_card_uid": None},
    ]
    reordered["expected_selected_indexes"] = [0]
    write_json(scenario_root / "04-reordered.json", reordered)

    mandatory = _case(base, f"{namespace}-primary-mandatory-block")
    mandatory["prompt"]["mandatory_indexes"] = [0]
    mandatory["expected_selected_indexes"] = [0]
    write_json(scenario_root / "05-mandatory-block.json", mandatory)

    terminal = _case(base, f"{namespace}-primary-terminal-block")
    terminal["prompt"]["terminal_indexes"] = [0]
    terminal["expected_selected_indexes"] = [0]
    write_json(scenario_root / "06-terminal-block.json", terminal)

    hard_tier = _case(base, f"{namespace}-primary-hard-tier-block")
    hard_tier["prompt"]["base_hard_tiers"] = [
        {"index": 0, "tier": [0]},
        {"index": 1, "tier": [1]},
    ]
    hard_tier["expected_selected_indexes"] = [0]
    write_json(scenario_root / "07-hard-tier-block.json", hard_tier)

    veto = _case(base, f"{namespace}-primary-veto-block")
    veto["prompt"]["base_vetoed_indexes"] = [1]
    veto["expected_selected_indexes"] = [0]
    write_json(scenario_root / "08-veto-block.json", veto)

    unknown_uid = _case(base, f"{namespace}-primary-unknown-uid")
    unknown_uid["local_uid_bindings"]["options"][1]["local_card_uid"] = "PRIVATE_SENTINEL"
    write_json(scenario_root / "09-unknown-uid.json", unknown_uid)

    hidden_field = _case(base, f"{namespace}-hidden-field-rejected")
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
    write_json(workspace / "scenario-suite.json", suite)
    if scaffold_path.is_file():
        scaffold_path.unlink()
    return {"scenario_count": len(cases), "suite_path": str(workspace / "scenario-suite.json")}


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
