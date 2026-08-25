"""Portable Competitive Policy IR v2 reference runtime.

The module consumes only a closed public frame and returns indexes from the
current immutable option window.  It deliberately owns no engine objects,
bindings, tickets or commands.  Base cardinality, forced selections, hard
tiers and veto remain the final adjudication boundary.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
import math
import re
from types import MappingProxyType
from typing import Any, Mapping

from .cabt_tree_hash import CabtTreeHashError, public_observation_hash


PROFILE_ID = "ptcgdap-competitive-policy-v2"
FRAME_PROFILE_ID = "ptcgdap-competitive-public-frame-v2"
MAX_SAFE_INTEGER = 9_007_199_254_740_991
MAX_SCORE = 1_000_000_000
GOAL_STAGES = frozenset(
    {"acquire", "deploy", "fund", "ready", "execute", "maintain", "recover"}
)
CHANNELS = frozenset({"macro", "tactical", "interaction", "future", "uncertainty"})
OPS = frozenset({"eq", "ne", "lt", "lte", "gt", "gte", "contains", "not_contains"})
COUNT_MODES = frozenset(
    {
        "fixed",
        "goal_energy_debt",
        "goal_missing_energy_sources",
        "ceil_public_fact_divisor",
        "ceil_public_fact_divisor_with_reserve",
    }
)
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
LOCAL_UID = re.compile(r"^[A-Za-z0-9.]+_[A-Za-z0-9._]+$")
UPPER_SHA = re.compile(r"^[0-9A-F]{64}$")

# Locked to the official CABT sample bundle. New enum values may be appended
# upstream; an unknown raw integer deliberately maps to None so symbolic rules
# fail closed while select.type_raw/select.context_raw remain auditable.
SELECT_TYPE_NAMES = (
    "main",
    "card",
    "attached_card",
    "card_or_attached_card",
    "energy",
    "skill",
    "attack",
    "evolve",
    "count",
    "yes_no",
    "special_condition",
)
SELECT_CONTEXT_NAMES = (
    "main",
    "setup_active_pokemon",
    "setup_bench_pokemon",
    "switch",
    "to_active",
    "to_bench",
    "to_field",
    "to_hand",
    "discard",
    "to_deck",
    "to_deck_bottom",
    "to_prize",
    "not_move",
    "damage_counter",
    "damage_counter_any",
    "damage",
    "remove_damage_counter",
    "heal",
    "evolves_from",
    "evolves_to",
    "devolve",
    "attach_from",
    "attach_to",
    "detach_from",
    "look",
    "effect_target",
    "discard_energy_card",
    "discard_tool_card",
    "switch_energy_card",
    "discard_card_or_attached_card",
    "discard_energy",
    "to_hand_energy",
    "to_deck_energy",
    "switch_energy",
    "skill_order",
    "attack",
    "disable_attack",
    "evolve",
    "draw_count",
    "damage_counter_count",
    "remove_damage_counter_count",
    "is_first",
    "mulligan",
    "activate",
    "first_effect",
    "more_devolve",
    "coin_head",
    "affect_special_condition",
    "recover_special_condition",
)

SCALAR_FACTS = frozenset(
    {
        "prompt_kind",
        "select.type",
        "select.context",
        "select.type_raw",
        "select.context_raw",
        "turn_number",
        "turn.supporter_available",
        "turn.manual_attachment_available",
        "turn.retreat_available",
        "self.prizes_remaining",
        "opponent.prizes_remaining",
        "self.deck_count",
        "opponent.deck_count",
        "self.hand_count",
        "opponent.hand_count",
        "self.bench_count",
        "self.bench_capacity",
        "self.bench_space",
        "self.bench_open",
        "opponent.bench_count",
        "self.active.remaining_hp",
        "self.active.prize_value",
        "opponent.active.remaining_hp",
        "opponent.active.prize_value",
        "window.source_uid",
        "window.option_kind",
        "select.min_count",
        "select.max_count",
        "option.index",
        "option.kind",
        "option.card_uid",
        "option.source_uid",
        "option.source_serial",
        "option.target_uid",
        "option.target_serial",
        "option.target_remaining_hp",
        "option.target_prize_value",
        "option.target_attached_energy_count",
        "option.target_attached_energy_uids",
        "option.target_minimum_attack_energy_count",
        "option.target_attack_ready",
        "option.target_energy_debt",
        "option.projected_damage",
        "option.projected_knockout",
        "option.requires_interaction",
        "option.attack_index",
        "option.ability_index",
        "option.pending_assignment_count",
        "option.tags",
        "option.target_attached_energy_uids",
        "option.source_is_active",
        "option.target_is_active",
        "self.bench_open",
        "goal.energy_debt",
        "goal.ready_count",
        "goal.deployed_count",
        "goal.active_ready_count",
        "goal.bench_ready_count",
        "goal.near_ready_count",
        "goal.board_energy_count",
        "goal.hand_energy_count",
        "goal.discard_energy_count",
        "goal.immediate",
        "goal.complete",
        "goal.option.matches_target",
        "goal.option.acquires_missing_target",
        "goal.option.deploys_missing_target",
        "goal.option.supplies_missing_energy",
        "goal.option.funds_target",
        "goal.option.completes_target",
        "goal.option.pivots_ready_target",
        "goal.option.executes_requirement",
        "goal.option.target_energy_debt",
        "goal.option.progress",
        "goal.option.is_max_progress",
        "goal.window.max_progress",
        "goal.option.is_max_setup_progress",
        "goal.window.max_setup_progress",
        "threat.own_attacks_to_win",
        "threat.opponent_attacks_to_win",
        "threat.tempo_margin",
    }
)
ZONE_FACTS = frozenset(
    {
        "self.hand.count_uid",
        "self.active.count_uid",
        "self.bench.count_uid",
        "self.discard.count_uid",
        "self.board.count_uid",
        "opponent.active.count_uid",
        "opponent.bench.count_uid",
        "opponent.discard.count_uid",
        "opponent.board.count_uid",
    }
)
ENERGY_ZONE_FACTS = frozenset(
    {
        "self.active.energy_count_uid",
        "self.bench.energy_count_uid",
        "self.board.energy_count_uid",
        "opponent.active.energy_count_uid",
        "opponent.bench.energy_count_uid",
        "opponent.board.energy_count_uid",
    }
)
GOAL_UID_FACTS = frozenset(
    {
        "goal.deployed_count_uid",
        "goal.ready_count_uid",
        "goal.near_ready_count_uid",
        "goal.energy_debt_uid",
        "goal.active_ready_count_uid",
        "goal.bench_ready_count_uid",
    }
)
WINDOW_UID_FACTS = frozenset(
    {
        "window.option_count_card_uid",
        "window.option_count_source_uid",
        "window.option_count_target_uid",
    }
)
NUMERIC_TERM_FACTS = frozenset(
    fact
    for fact in SCALAR_FACTS
    if fact
    not in {
        "prompt_kind",
        "select.type",
        "select.context",
        "option.kind",
        "option.card_uid",
        "option.source_uid",
        "option.target_uid",
        "option.tags",
        "option.source_is_active",
        "option.target_is_active",
        "goal.complete",
        "goal.immediate",
        "goal.option.matches_target",
        "goal.option.acquires_missing_target",
        "goal.option.deploys_missing_target",
        "goal.option.supplies_missing_energy",
        "goal.option.funds_target",
        "goal.option.completes_target",
        "goal.option.pivots_ready_target",
        "goal.option.executes_requirement",
        "goal.option.is_max_progress",
        "goal.option.is_max_setup_progress",
        "turn.supporter_available",
        "turn.manual_attachment_available",
        "turn.retreat_available",
    }
)
PRIVATE_KEYS = frozenset(
    {
        "deck_order",
        "private_state",
        "search_begin_input",
        "callback",
        "binding",
        "ticket",
        "command",
        "object_ref",
        "instance_id",
        "raw_private_hash",
    }
)

DOCUMENT_REQUIRED_KEYS = {
    "schema_version",
    "adapter_id",
    "adapter_version",
    "goals",
    "count_rules",
    "rules",
}
DOCUMENT_KEYS = DOCUMENT_REQUIRED_KEYS | {
    "turn_routes",
    "route_candidates",
    "interaction_recipes",
    "turn_bonus_contracts",
}
GOAL_KEYS = {"goal_id", "stage", "priority", "requirements"}
REQUIREMENT_REQUIRED_KEYS = {"card_uid", "ready_target_count", "energy_required"}
REQUIREMENT_KEYS = REQUIREMENT_REQUIRED_KEYS | {
    "energy_requirements",
    "attack_index",
    "ability_index",
}
ENERGY_REQUIREMENT_KEYS = {"energy_uid", "count"}
COUNT_RULE_KEYS = {
    "rule_id",
    "priority",
    "goal_id",
    "mode",
    "fixed_count",
    "fact",
    "divisor",
    "when",
}
RULE_KEYS = {
    "rule_id",
    "goal_id",
    "goal_stage",
    "channel",
    "horizon",
    "confidence_milli",
    "base_score",
    "when",
    "score_terms",
}
TURN_ROUTE_KEYS = {
    "route_id",
    "priority",
    "goal_id",
    "owner_goal_id",
    "bridge_goal_id",
    "pivot_goal_id",
    "when",
    "steps",
}
ROUTE_CANDIDATE_KEYS = {
    "route_id",
    "goal_id",
    "owner_goal_id",
    "bridge_goal_id",
    "pivot_goal_id",
    "when",
    "resource_budget",
    "value",
    "steps",
}
ROUTE_RESOURCE_BUDGET_KEYS = {
    "supporter_uses",
    "manual_attachments",
    "retreats",
    "bench_slots",
    "ability_uses",
    "discard_cards",
    "search_cards",
}
ROUTE_VALUE_COMPONENTS = (
    "attack_windows",
    "prize_progress",
    "continuity",
    "resource_cost",
    "response_risk",
    "uncertainty",
)
ROUTE_VALUE_COMPONENT_KEYS = {"base", "terms"}
ROUTE_STEP_KEYS = {
    "step_id",
    "prompt_kinds",
    "goal_id",
    "when",
    "option_when",
    "score_bonus",
    "selection_count",
    "terminal",
    "checkpoint",
}
ROUTE_CANDIDATE_STEP_KEYS = ROUTE_STEP_KEYS - {"score_bonus"}
INTERACTION_RECIPE_KEYS = {
    "recipe_id",
    "priority",
    "route_id",
    "goal_id",
    "source_uids",
    "when",
    "steps",
}
TURN_BONUS_CONTRACT_KEYS = {
    "contract_id",
    "priority",
    "goal_id",
    "when",
    "bonuses",
}
TURN_BONUS_KEYS = {
    "bonus_id",
    "prompt_kinds",
    "goal_id",
    "when",
    "option_when",
    "score_bonus",
}
CONDITION_KEYS = {"fact", "op", "value", "card_uid"}
TERM_KEYS = {"fact", "coefficient", "minimum", "maximum"}
FRAME_KEYS = {
    "schema_version",
    "profile_id",
    "sequence",
    "seat",
    "prompt_kind",
    "source",
    "public_state",
    "select_semantics",
    "options",
}
SOURCE_KEYS = {"public_observation_hash", "window_id"}
STATE_KEYS = {"turn_number", "phase", "self", "opponent"}
SELF_REQUIRED_KEYS = {"hand", "active", "bench", "discard", "deck_count", "prizes_remaining"}
SELF_KEYS = SELF_REQUIRED_KEYS | {"turn", "bench_capacity"}
TURN_LEDGER_KEYS = {
    "supporter_available",
    "manual_attachment_available",
    "retreat_available",
}
OPPONENT_KEYS = {
    "hand_count",
    "active",
    "bench",
    "discard",
    "deck_count",
    "prizes_remaining",
}
SEMANTIC_KEYS = {"min_count", "max_count", "select_type_raw", "select_context_raw"}
CARD_KEYS = {"serial", "local_card_uid"}
SLOT_KEYS = {
    "serial",
    "local_card_uid",
    "remaining_hp",
    "prize_value",
    "attached_energy_count",
    "attached_energy_uids",
    "minimum_attack_energy_count",
    "attack_ready",
    "energy_debt",
}
OPTION_KEYS = {
    "index",
    "kind",
    "card_uid",
    "source_uid",
    "source_serial",
    "target_uid",
    "target_serial",
    "target_remaining_hp",
    "target_prize_value",
    "target_attached_energy_count",
    "target_attached_energy_uids",
    "target_minimum_attack_energy_count",
    "target_attack_ready",
    "target_energy_debt",
    "projected_damage",
    "projected_knockout",
    "requires_interaction",
    "attack_index",
    "ability_index",
    "pending_assignment_count",
    "tags",
    "option_type_raw",
    "option_player_index",
}


def _sha(value: Any) -> str:
    try:
        return public_observation_hash(value)
    except CabtTreeHashError:
        return ""


def _safe_int(value: Any, *, signed: bool = False) -> bool:
    if type(value) is not int:
        return False
    minimum = -MAX_SAFE_INTEGER if signed else 0
    return minimum <= value <= MAX_SAFE_INTEGER


def _uid(value: Any) -> bool:
    return type(value) is str and 3 <= len(value) <= 64 and LOCAL_UID.fullmatch(value) is not None


def _identifier(value: Any) -> bool:
    return type(value) is str and IDENTIFIER.fullmatch(value) is not None and "private" not in value


def _contains_private(value: Any) -> bool:
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str or key.lower() in PRIVATE_KEYS or "private" in key.lower():
                return True
            if _contains_private(child):
                return True
    elif type(value) is list:
        return any(_contains_private(child) for child in value)
    elif type(value) not in {str, int, bool, type(None)}:
        return True
    return False


def _freeze(value: Any) -> Any:
    if type(value) is dict:
        return MappingProxyType({key: _freeze(child) for key, child in value.items()})
    if type(value) is list:
        return tuple(_freeze(child) for child in value)
    return value


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(child) for key, child in value.items()}
    if type(value) is tuple:
        return [_thaw(child) for child in value]
    return value


def _condition_error(value: Any, allowed_uids: frozenset[str]) -> str | None:
    if type(value) is not dict or set(value) != CONDITION_KEYS:
        return "invalid_public_condition"
    fact = value["fact"]
    if type(fact) is not str or fact not in SCALAR_FACTS | ZONE_FACTS | ENERGY_ZONE_FACTS | GOAL_UID_FACTS | WINDOW_UID_FACTS:
        return "invalid_public_fact"
    if value["op"] not in OPS:
        return "invalid_public_condition"
    card_uid = value["card_uid"]
    if fact in ZONE_FACTS | ENERGY_ZONE_FACTS | GOAL_UID_FACTS | WINDOW_UID_FACTS:
        if not _uid(card_uid) or card_uid not in allowed_uids:
            return "invalid_public_condition"
    elif card_uid is not None:
        return "invalid_public_condition"
    scalar = value["value"]
    if type(scalar) not in {str, int, bool, type(None)} or (type(scalar) is int and not _safe_int(scalar, signed=True)):
        return "invalid_public_condition"
    if (
        fact not in ZONE_FACTS | ENERGY_ZONE_FACTS | GOAL_UID_FACTS | WINDOW_UID_FACTS
        and fact.endswith("_uid")
        and scalar is not None
        and (not _uid(scalar) or scalar not in allowed_uids)
    ):
        return "invalid_public_condition"
    return None


def _condition_list_error(
    value: Any,
    allowed_uids: frozenset[str],
    *,
    allow_option_facts: bool,
) -> str | None:
    if type(value) is not list or len(value) > 32:
        return "invalid_public_condition"
    for condition in value:
        error = _condition_error(condition, allowed_uids)
        if error is not None:
            return error
        fact = condition["fact"]
        if not allow_option_facts and (
            fact.startswith("option.") or fact.startswith("goal.option.")
        ):
            return "invalid_public_condition"
    return None


def _route_step_error(
    step: Any,
    allowed_uids: frozenset[str],
    goal_ids: set[str],
) -> str | None:
    if type(step) is not dict or set(step) != ROUTE_STEP_KEYS:
        return "invalid_turn_route"
    if (
        not _identifier(step["step_id"])
        or step["goal_id"] not in goal_ids
        or type(step["prompt_kinds"]) is not list
        or not step["prompt_kinds"]
        or len(step["prompt_kinds"]) > 16
        or any(type(kind) is not str or not kind or len(kind) > 64 for kind in step["prompt_kinds"])
        or len(set(step["prompt_kinds"])) != len(step["prompt_kinds"])
        or not _safe_int(step["score_bonus"])
        or not 0 <= step["score_bonus"] <= 1_000_000
        or type(step["terminal"]) is not bool
        or type(step["checkpoint"]) is not bool
    ):
        return "invalid_turn_route"
    selection_count = step["selection_count"]
    if selection_count is not None and (
        not _safe_int(selection_count) or not 0 <= selection_count <= 1024
    ):
        return "invalid_turn_route"
    error = _condition_list_error(
        step["when"], allowed_uids, allow_option_facts=False
    )
    if error is not None:
        return error
    if not step["option_when"]:
        return "invalid_turn_route"
    return _condition_list_error(
        step["option_when"], allowed_uids, allow_option_facts=True
    )


def _route_candidate_step_error(
    step: Any,
    allowed_uids: frozenset[str],
    goal_ids: set[str],
) -> str | None:
    if type(step) is not dict or set(step) != ROUTE_CANDIDATE_STEP_KEYS:
        return "invalid_route_candidate"
    if (
        not _identifier(step["step_id"])
        or step["goal_id"] not in goal_ids
        or type(step["prompt_kinds"]) is not list
        or not step["prompt_kinds"]
        or len(step["prompt_kinds"]) > 16
        or any(
            type(kind) is not str or not kind or len(kind) > 64
            for kind in step["prompt_kinds"]
        )
        or len(set(step["prompt_kinds"])) != len(step["prompt_kinds"])
        or type(step["terminal"]) is not bool
        or type(step["checkpoint"]) is not bool
    ):
        return "invalid_route_candidate"
    selection_count = step["selection_count"]
    if selection_count is not None and (
        not _safe_int(selection_count) or not 0 <= selection_count <= 1024
    ):
        return "invalid_route_candidate"
    error = _condition_list_error(
        step["when"], allowed_uids, allow_option_facts=False
    )
    if error is not None:
        return error
    if not step["option_when"]:
        return "invalid_route_candidate"
    return _condition_list_error(
        step["option_when"], allowed_uids, allow_option_facts=True
    )


def _route_value_component_error(value: Any) -> str | None:
    if type(value) is not dict or set(value) != ROUTE_VALUE_COMPONENT_KEYS:
        return "invalid_route_value"
    if (
        not _safe_int(value["base"], signed=True)
        or abs(value["base"]) > 1_000_000
        or type(value["terms"]) is not list
        or len(value["terms"]) > 16
    ):
        return "invalid_route_value"
    for term in value["terms"]:
        if type(term) is not dict or set(term) != TERM_KEYS:
            return "invalid_route_value"
        fact = term["fact"]
        if (
            fact not in NUMERIC_TERM_FACTS
            or fact.startswith("option.")
            or fact.startswith("goal.option.")
            or not _safe_int(term["coefficient"], signed=True)
            or abs(term["coefficient"]) > 10_000
            or not _safe_int(term["minimum"], signed=True)
            or not _safe_int(term["maximum"], signed=True)
            or term["minimum"] > term["maximum"]
        ):
            return "invalid_route_value"
    return None


def _turn_bonus_error(
    bonus: Any,
    allowed_uids: frozenset[str],
    goal_ids: set[str],
) -> str | None:
    if type(bonus) is not dict or set(bonus) != TURN_BONUS_KEYS:
        return "invalid_turn_bonus_contract"
    if (
        not _identifier(bonus["bonus_id"])
        or bonus["goal_id"] not in goal_ids
        or type(bonus["prompt_kinds"]) is not list
        or not bonus["prompt_kinds"]
        or len(bonus["prompt_kinds"]) > 16
        or any(
            type(kind) is not str or not kind or len(kind) > 64
            for kind in bonus["prompt_kinds"]
        )
        or len(set(bonus["prompt_kinds"])) != len(bonus["prompt_kinds"])
        or not _safe_int(bonus["score_bonus"], signed=True)
        or not -1_000_000 <= bonus["score_bonus"] <= 1_000_000
    ):
        return "invalid_turn_bonus_contract"
    error = _condition_list_error(
        bonus["when"], allowed_uids, allow_option_facts=False
    )
    if error is not None:
        return error
    if not bonus["option_when"]:
        return "invalid_turn_bonus_contract"
    return _condition_list_error(
        bonus["option_when"], allowed_uids, allow_option_facts=True
    )


def _document_error(value: Any, allowed_uids: frozenset[str]) -> str | None:
    if _contains_private(value):
        return "private_policy_input"
    if (
        type(value) is not dict
        or not DOCUMENT_REQUIRED_KEYS <= set(value) <= DOCUMENT_KEYS
    ):
        return "invalid_policy_document"
    if (
        value["schema_version"] != 2
        or not _identifier(value["adapter_id"])
        or not _safe_int(value["adapter_version"])
        or value["adapter_version"] < 2
    ):
        return "invalid_policy_document"
    goals = value["goals"]
    count_rules = value["count_rules"]
    rules = value["rules"]
    turn_routes = value.get("turn_routes", [])
    route_candidates = value.get("route_candidates", [])
    interaction_recipes = value.get("interaction_recipes", [])
    turn_bonus_contracts = value.get("turn_bonus_contracts", [])
    if type(goals) is not list or not goals or len(goals) > 64:
        return "invalid_goal_state"
    if type(count_rules) is not list or len(count_rules) > 128:
        return "invalid_count_rule"
    if type(rules) is not list or not rules or len(rules) > 512:
        return "invalid_score_rule"
    if type(turn_routes) is not list or len(turn_routes) > 64:
        return "invalid_turn_route"
    if type(route_candidates) is not list or len(route_candidates) > 32:
        return "invalid_route_candidate"
    if type(interaction_recipes) is not list or len(interaction_recipes) > 128:
        return "invalid_interaction_recipe"
    if type(turn_bonus_contracts) is not list or len(turn_bonus_contracts) > 64:
        return "invalid_turn_bonus_contract"
    goal_ids: set[str] = set()
    for goal in goals:
        if type(goal) is not dict or set(goal) != GOAL_KEYS:
            return "invalid_goal_state"
        if (
            not _identifier(goal["goal_id"])
            or goal["goal_id"] in goal_ids
            or goal["stage"] not in GOAL_STAGES
            or not _safe_int(goal["priority"])
        ):
            return "invalid_goal_state"
        goal_ids.add(goal["goal_id"])
        requirements = goal["requirements"]
        if type(requirements) is not list or not requirements or len(requirements) > 32:
            return "invalid_goal_state"
        seen_uids: set[str] = set()
        for requirement in requirements:
            if (
                type(requirement) is not dict
                or not REQUIREMENT_REQUIRED_KEYS <= set(requirement) <= REQUIREMENT_KEYS
            ):
                return "invalid_goal_state"
            uid = requirement["card_uid"]
            if (
                not _uid(uid)
                or uid not in allowed_uids
                or uid in seen_uids
                or not _safe_int(requirement["ready_target_count"])
                or not 1 <= requirement["ready_target_count"] <= 6
                or not _safe_int(requirement["energy_required"])
                or not 0 <= requirement["energy_required"] <= 16
            ):
                return "invalid_goal_state"
            energy_requirements = requirement.get("energy_requirements", [])
            if type(energy_requirements) is not list or len(energy_requirements) > 16:
                return "invalid_goal_state"
            seen_energy_uids: set[str] = set()
            typed_total = 0
            for energy_requirement in energy_requirements:
                if (
                    type(energy_requirement) is not dict
                    or set(energy_requirement) != ENERGY_REQUIREMENT_KEYS
                    or not _uid(energy_requirement["energy_uid"])
                    or energy_requirement["energy_uid"] not in allowed_uids
                    or energy_requirement["energy_uid"] in seen_energy_uids
                    or not _safe_int(energy_requirement["count"])
                    or not 1 <= energy_requirement["count"] <= 16
                ):
                    return "invalid_goal_state"
                seen_energy_uids.add(energy_requirement["energy_uid"])
                typed_total += energy_requirement["count"]
            if typed_total > 16:
                return "invalid_goal_state"
            attack_index = requirement.get("attack_index")
            ability_index = requirement.get("ability_index")
            if (
                attack_index is not None
                and (not _safe_int(attack_index) or not 0 <= attack_index <= 15)
            ):
                return "invalid_goal_state"
            if (
                ability_index is not None
                and (not _safe_int(ability_index) or not 0 <= ability_index <= 15)
            ):
                return "invalid_goal_state"
            if attack_index is not None and ability_index is not None:
                return "invalid_goal_state"
            seen_uids.add(uid)
    route_ids: set[str] = set()
    for route in turn_routes:
        if type(route) is not dict or set(route) != TURN_ROUTE_KEYS:
            return "invalid_turn_route"
        route_id = route["route_id"]
        referenced_goals = (
            route["goal_id"],
            route["owner_goal_id"],
            route["bridge_goal_id"],
            route["pivot_goal_id"],
        )
        if (
            not _identifier(route_id)
            or route_id in route_ids
            or not _safe_int(route["priority"])
            or route["priority"] > 1_000_000
            or any(goal_id not in goal_ids for goal_id in referenced_goals)
            or type(route["steps"]) is not list
            or not route["steps"]
            or len(route["steps"]) > 32
        ):
            return "invalid_turn_route"
        route_ids.add(route_id)
        error = _condition_list_error(
            route["when"], allowed_uids, allow_option_facts=False
        )
        if error is not None:
            return error
        step_ids: set[str] = set()
        for step in route["steps"]:
            error = _route_step_error(step, allowed_uids, goal_ids)
            if error is not None:
                return error
            if step["step_id"] in step_ids:
                return "invalid_turn_route"
            step_ids.add(step["step_id"])
    for route in route_candidates:
        if type(route) is not dict or set(route) != ROUTE_CANDIDATE_KEYS:
            return "invalid_route_candidate"
        route_id = route["route_id"]
        referenced_goals = (
            route["goal_id"],
            route["owner_goal_id"],
            route["bridge_goal_id"],
            route["pivot_goal_id"],
        )
        budget = route["resource_budget"]
        route_value = route["value"]
        if (
            not _identifier(route_id)
            or route_id in route_ids
            or any(goal_id not in goal_ids for goal_id in referenced_goals)
            or type(budget) is not dict
            or set(budget) != ROUTE_RESOURCE_BUDGET_KEYS
            or not all(_safe_int(amount) for amount in budget.values())
            or not 0 <= budget["supporter_uses"] <= 1
            or not 0 <= budget["manual_attachments"] <= 1
            or not 0 <= budget["retreats"] <= 1
            or not 0 <= budget["bench_slots"] <= 8
            or not 0 <= budget["ability_uses"] <= 16
            or not 0 <= budget["discard_cards"] <= 60
            or not 0 <= budget["search_cards"] <= 60
            or type(route_value) is not dict
            or set(route_value) != set(ROUTE_VALUE_COMPONENTS)
            or type(route["steps"]) is not list
            or not route["steps"]
            or len(route["steps"]) > 32
        ):
            return "invalid_route_candidate"
        route_ids.add(route_id)
        error = _condition_list_error(
            route["when"], allowed_uids, allow_option_facts=False
        )
        if error is not None:
            return error
        for component_name in ROUTE_VALUE_COMPONENTS:
            error = _route_value_component_error(route_value[component_name])
            if error is not None:
                return error
        step_ids: set[str] = set()
        for step in route["steps"]:
            error = _route_candidate_step_error(step, allowed_uids, goal_ids)
            if error is not None:
                return error
            if step["step_id"] in step_ids:
                return "invalid_route_candidate"
            step_ids.add(step["step_id"])
    recipe_ids: set[str] = set()
    for recipe in interaction_recipes:
        if type(recipe) is not dict or set(recipe) != INTERACTION_RECIPE_KEYS:
            return "invalid_interaction_recipe"
        route_id = recipe["route_id"]
        if (
            not _identifier(recipe["recipe_id"])
            or recipe["recipe_id"] in recipe_ids
            or not _safe_int(recipe["priority"])
            or recipe["priority"] > 1_000_000
            or (route_id is not None and route_id not in route_ids)
            or recipe["goal_id"] not in goal_ids
            or type(recipe["source_uids"]) is not list
            or not recipe["source_uids"]
            or len(recipe["source_uids"]) > 32
            or len(set(recipe["source_uids"])) != len(recipe["source_uids"])
            or any(not _uid(uid) or uid not in allowed_uids for uid in recipe["source_uids"])
            or type(recipe["steps"]) is not list
            or not recipe["steps"]
            or len(recipe["steps"]) > 32
        ):
            return "invalid_interaction_recipe"
        recipe_ids.add(recipe["recipe_id"])
        error = _condition_list_error(
            recipe["when"], allowed_uids, allow_option_facts=False
        )
        if error is not None:
            return error
        step_ids: set[str] = set()
        for step in recipe["steps"]:
            error = _route_step_error(step, allowed_uids, goal_ids)
            if error is not None:
                return "invalid_interaction_recipe" if error == "invalid_turn_route" else error
            if step["step_id"] in step_ids:
                return "invalid_interaction_recipe"
            step_ids.add(step["step_id"])
    contract_ids: set[str] = set()
    for contract in turn_bonus_contracts:
        if type(contract) is not dict or set(contract) != TURN_BONUS_CONTRACT_KEYS:
            return "invalid_turn_bonus_contract"
        contract_id = contract["contract_id"]
        if (
            not _identifier(contract_id)
            or contract_id in contract_ids
            or not _safe_int(contract["priority"])
            or contract["priority"] > 1_000_000
            or contract["goal_id"] not in goal_ids
            or type(contract["bonuses"]) is not list
            or not contract["bonuses"]
            or len(contract["bonuses"]) > 64
        ):
            return "invalid_turn_bonus_contract"
        contract_ids.add(contract_id)
        error = _condition_list_error(
            contract["when"], allowed_uids, allow_option_facts=False
        )
        if error is not None:
            return error
        bonus_ids: set[str] = set()
        for bonus in contract["bonuses"]:
            error = _turn_bonus_error(bonus, allowed_uids, goal_ids)
            if error is not None:
                return error
            if bonus["bonus_id"] in bonus_ids:
                return "invalid_turn_bonus_contract"
            bonus_ids.add(bonus["bonus_id"])
    rule_ids: set[str] = set()
    for count_rule in count_rules:
        if type(count_rule) is not dict or set(count_rule) != COUNT_RULE_KEYS:
            return "invalid_count_rule"
        if (
            not _identifier(count_rule["rule_id"])
            or count_rule["rule_id"] in rule_ids
            or not _safe_int(count_rule["priority"])
            or count_rule["goal_id"] not in goal_ids
            or count_rule["mode"] not in COUNT_MODES
        ):
            return "invalid_count_rule"
        rule_ids.add(count_rule["rule_id"])
        fixed = count_rule["fixed_count"]
        fact = count_rule["fact"]
        divisor = count_rule["divisor"]
        if count_rule["mode"] == "fixed":
            if not _safe_int(fixed) or fixed > 1024 or fact is not None or divisor is not None:
                return "invalid_count_rule"
        elif count_rule["mode"] in {"goal_energy_debt", "goal_missing_energy_sources"}:
            if fixed is not None or fact is not None or divisor is not None:
                return "invalid_count_rule"
            if count_rule["mode"] == "goal_missing_energy_sources":
                goal = next(goal for goal in goals if goal["goal_id"] == count_rule["goal_id"])
                if not any(
                    requirement.get("energy_requirements", [])
                    for requirement in goal["requirements"]
                ):
                    return "invalid_count_rule"
        else:
            if (
                fact not in NUMERIC_TERM_FACTS
                or type(fact) is not str
                or fact.startswith("option.")
                or fact.startswith("goal.option.")
                or not _safe_int(divisor)
                or not 1 <= divisor <= 1_000_000
            ):
                return "invalid_count_rule"
            if count_rule["mode"] == "ceil_public_fact_divisor":
                if fixed is not None:
                    return "invalid_count_rule"
            elif not _safe_int(fixed) or fixed > 1024:
                return "invalid_count_rule"
        if type(count_rule["when"]) is not list or len(count_rule["when"]) > 32:
            return "invalid_count_rule"
        for condition in count_rule["when"]:
            error = _condition_error(condition, allowed_uids)
            if error is not None:
                return error
    for rule in rules:
        if type(rule) is not dict or set(rule) != RULE_KEYS:
            return "invalid_score_rule"
        if (
            not _identifier(rule["rule_id"])
            or rule["rule_id"] in rule_ids
            or rule["goal_id"] not in goal_ids
            or rule["goal_stage"] not in GOAL_STAGES
            or rule["channel"] not in CHANNELS
            or not _safe_int(rule["horizon"])
            or rule["horizon"] > 2
            or not _safe_int(rule["confidence_milli"])
            or rule["confidence_milli"] > 1000
            or not _safe_int(rule["base_score"], signed=True)
            or abs(rule["base_score"]) > 1_000_000
        ):
            return "invalid_score_rule"
        rule_ids.add(rule["rule_id"])
        if type(rule["when"]) is not list or len(rule["when"]) > 32:
            return "invalid_score_rule"
        for condition in rule["when"]:
            error = _condition_error(condition, allowed_uids)
            if error is not None:
                return error
        terms = rule["score_terms"]
        if type(terms) is not list or len(terms) > 16:
            return "invalid_score_rule"
        for term in terms:
            if type(term) is not dict or set(term) != TERM_KEYS:
                return "invalid_score_rule"
            if (
                term["fact"] not in NUMERIC_TERM_FACTS
                or not _safe_int(term["coefficient"], signed=True)
                or abs(term["coefficient"]) > 10_000
                or not _safe_int(term["minimum"], signed=True)
                or not _safe_int(term["maximum"], signed=True)
                or term["minimum"] > term["maximum"]
            ):
                return "invalid_score_rule"
    return None


@dataclass(frozen=True, slots=True, init=False)
class CompetitivePolicyV2:
    _document: Any
    _allowed_uids: frozenset[str]
    _policy_hash: str

    @classmethod
    def _create(cls, document: dict[str, Any], allowed_uids: frozenset[str]) -> "CompetitivePolicyV2":
        value = object.__new__(cls)
        object.__setattr__(value, "_document", _freeze(copy.deepcopy(document)))
        object.__setattr__(value, "_allowed_uids", allowed_uids)
        object.__setattr__(value, "_policy_hash", _sha({"profile_id": PROFILE_ID, "document": document}))
        return value

    @property
    def policy_hash(self) -> str:
        return self._policy_hash if self.validate_integrity() else ""

    def validate_integrity(self) -> bool:
        document = _thaw(self._document)
        return (
            bool(self._allowed_uids)
            and all(_uid(uid) for uid in self._allowed_uids)
            and _document_error(document, self._allowed_uids) is None
            and self._policy_hash == _sha({"profile_id": PROFILE_ID, "document": document})
        )

    def to_public_dict(self) -> dict[str, Any]:
        if not self.validate_integrity():
            raise ValueError("policy_integrity_invalid")
        return copy.deepcopy(_thaw(self._document))


@dataclass(frozen=True, slots=True)
class CompetitivePolicyV2CompileOutcome:
    accepted: bool
    error_code: str
    policy: CompetitivePolicyV2 | None


class CompetitivePolicyV2Compiler:
    @staticmethod
    def compile_local_uid(document: Any, *, allowed_card_uids: Any) -> CompetitivePolicyV2CompileOutcome:
        if type(allowed_card_uids) not in {set, frozenset}:
            return CompetitivePolicyV2CompileOutcome(False, "invalid_allowed_card_uids", None)
        allowed = frozenset(allowed_card_uids)
        if not allowed or not all(_uid(uid) for uid in allowed):
            return CompetitivePolicyV2CompileOutcome(False, "invalid_allowed_card_uids", None)
        error = _document_error(document, allowed)
        if error is not None:
            return CompetitivePolicyV2CompileOutcome(False, error, None)
        return CompetitivePolicyV2CompileOutcome(
            True,
            "",
            CompetitivePolicyV2._create(copy.deepcopy(document), allowed),
        )


def _card_error(value: Any, *, slot: bool) -> bool:
    keys = SLOT_KEYS if slot else CARD_KEYS
    if type(value) is not dict or set(value) != keys:
        return True
    if not _safe_int(value["serial"]) or not _uid(value["local_card_uid"]):
        return True
    if not slot:
        return False
    return not (
        _safe_int(value["remaining_hp"])
        and _safe_int(value["prize_value"])
        and 1 <= value["prize_value"] <= 3
        and _safe_int(value["attached_energy_count"])
        and type(value["attached_energy_uids"]) is list
        and len(value["attached_energy_uids"]) == value["attached_energy_count"]
        and all(_uid(uid) for uid in value["attached_energy_uids"])
        and _safe_int(value["minimum_attack_energy_count"])
        and type(value["attack_ready"]) is bool
        and _safe_int(value["energy_debt"])
        and value["energy_debt"] <= 16
    )


def _nullable(value: Any, kind: type) -> bool:
    return value is None or type(value) is kind


def _frame_error(value: Any) -> str | None:
    if _contains_private(value):
        return "private_or_runtime_frame"
    if type(value) is not dict or set(value) != FRAME_KEYS:
        return "invalid_public_frame"
    if (
        value["schema_version"] != 2
        or value["profile_id"] != FRAME_PROFILE_ID
        or not _safe_int(value["sequence"])
        or value["sequence"] < 1
        or value["seat"] not in {0, 1}
        or type(value["prompt_kind"]) is not str
        or not value["prompt_kind"]
    ):
        return "invalid_public_frame"
    source = value["source"]
    state = value["public_state"]
    semantics = value["select_semantics"]
    options = value["options"]
    if (
        type(source) is not dict
        or set(source) != SOURCE_KEYS
        or UPPER_SHA.fullmatch(str(source["public_observation_hash"])) is None
        or UPPER_SHA.fullmatch(str(source["window_id"])) is None
        or type(state) is not dict
        or set(state) != STATE_KEYS
        or type(semantics) is not dict
        or set(semantics) != SEMANTIC_KEYS
        or type(options) is not list
        or len(options) > 1024
    ):
        return "invalid_public_frame"
    own = state["self"]
    opponent = state["opponent"]
    if (
        type(own) is not dict
        or not SELF_REQUIRED_KEYS <= set(own) <= SELF_KEYS
        or type(opponent) is not dict
        or set(opponent) != OPPONENT_KEYS
    ):
        return "invalid_public_frame"
    if "turn" in own:
        turn = own["turn"]
        if (
            type(turn) is not dict
            or set(turn) != TURN_LEDGER_KEYS
            or any(type(value) is not bool for value in turn.values())
        ):
            return "invalid_public_frame"
    if not _safe_int(state["turn_number"]) or type(state["phase"]) is not str:
        return "invalid_public_frame"
    for key in ("hand", "active", "bench", "discard"):
        values = own[key]
        if type(values) is not list or any(_card_error(child, slot=key in {"active", "bench"}) for child in values):
            return "invalid_public_frame"
    if "bench_capacity" in own and (
        not _safe_int(own["bench_capacity"])
        or own["bench_capacity"] > 8
        or own["bench_capacity"] < len(own["bench"])
    ):
        return "invalid_public_frame"
    for key in ("active", "bench", "discard"):
        values = opponent[key]
        if type(values) is not list or any(_card_error(child, slot=key in {"active", "bench"}) for child in values):
            return "invalid_public_frame"
    for item in (
        own["deck_count"],
        own["prizes_remaining"],
        opponent["hand_count"],
        opponent["deck_count"],
        opponent["prizes_remaining"],
    ):
        if not _safe_int(item):
            return "invalid_public_frame"
    minimum = semantics["min_count"]
    maximum = semantics["max_count"]
    if (
        not _safe_int(minimum)
        or not _safe_int(maximum)
        or not 0 <= minimum <= maximum <= len(options)
        or not _safe_int(semantics["select_type_raw"])
        or not _safe_int(semantics["select_context_raw"])
    ):
        return "invalid_public_frame"
    for index, option in enumerate(options):
        if type(option) is not dict or set(option) != OPTION_KEYS or option["index"] != index:
            return "invalid_public_frame"
        if type(option["kind"]) is not str or not option["kind"]:
            return "invalid_public_frame"
        for key in ("card_uid", "source_uid", "target_uid"):
            if option[key] is not None and not _uid(option[key]):
                return "invalid_public_frame"
        for key in (
            "source_serial",
            "target_serial",
            "target_remaining_hp",
            "target_prize_value",
            "target_attached_energy_count",
            "target_minimum_attack_energy_count",
            "target_energy_debt",
            "projected_damage",
            "attack_index",
            "ability_index",
        ):
            if not _nullable(option[key], int) or (type(option[key]) is int and not _safe_int(option[key])):
                return "invalid_public_frame"
        attached_uids = option["target_attached_energy_uids"]
        if attached_uids is not None and (
            type(attached_uids) is not list
            or len(attached_uids) > 64
            or any(not _uid(uid) for uid in attached_uids)
        ):
            return "invalid_public_frame"
        for key in ("target_attack_ready",):
            if not _nullable(option[key], bool):
                return "invalid_public_frame"
        if (
            type(option["projected_knockout"]) is not bool
            or type(option["requires_interaction"]) is not bool
            or not _safe_int(option["pending_assignment_count"])
            or type(option["tags"]) is not list
            or any(type(tag) is not str for tag in option["tags"])
            or not _safe_int(option["option_type_raw"])
            or option["option_player_index"] not in {0, 1, None}
        ):
            return "invalid_public_frame"
    return None


def _requirement_slot_debt(requirement: dict[str, Any], slot: dict[str, Any]) -> int:
    attached = slot["attached_energy_count"]
    generic_debt = max(0, requirement["energy_required"] - attached)
    typed_debt = sum(
        max(0, item["count"] - slot["attached_energy_uids"].count(item["energy_uid"]))
        for item in requirement.get("energy_requirements", [])
    )
    return max(generic_debt, typed_debt)


def _requirement_slot_ready(requirement: dict[str, Any], slot: dict[str, Any]) -> bool:
    if _requirement_slot_debt(requirement, slot) != 0:
        return False
    if requirement.get("attack_index") is not None:
        return True
    if requirement.get("ability_index") is not None:
        return True
    return bool(slot["attack_ready"])


def _goal_states(
    document: dict[str, Any], frame: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    own = frame["public_state"]["self"]
    active_slots = list(own["active"])
    bench_slots = list(own["bench"])
    slots = [*active_slots, *bench_slots]
    active_serials = {slot["serial"] for slot in active_slots}
    states: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    for goal in document["goals"]:
        deployed = 0
        ready = 0
        debt = 0
        active_ready = 0
        bench_ready = 0
        near_ready = 0
        requirement_states: dict[str, dict[str, int]] = {}
        energy_uids: set[str] = set()
        for requirement in goal["requirements"]:
            energy_uids.update(
                item["energy_uid"]
                for item in requirement.get("energy_requirements", [])
            )
            matches = [slot for slot in slots if slot["local_card_uid"] == requirement["card_uid"]]
            matches.sort(
                key=lambda slot: (
                    _requirement_slot_debt(requirement, slot),
                    -slot["attached_energy_count"],
                    slot["serial"],
                )
            )
            matches = matches[: requirement["ready_target_count"]]
            deployed_count = len(matches)
            ready_matches = [
                slot for slot in matches if _requirement_slot_ready(requirement, slot)
            ]
            ready_count = len(ready_matches)
            requirement_debt = sum(
                _requirement_slot_debt(requirement, slot) for slot in matches
            )
            near_ready_count = sum(
                1
                for slot in matches
                if _requirement_slot_debt(requirement, slot) <= 1
            )
            active_ready_count = sum(
                1 for slot in ready_matches if slot["serial"] in active_serials
            )
            bench_ready_count = ready_count - active_ready_count
            deployed += deployed_count
            ready += ready_count
            debt += requirement_debt
            active_ready += active_ready_count
            bench_ready += bench_ready_count
            near_ready += near_ready_count
            requirement_states[requirement["card_uid"]] = {
                "deployed_count": deployed_count,
                "ready_count": ready_count,
                "near_ready_count": near_ready_count,
                "energy_debt": requirement_debt,
                "active_ready_count": active_ready_count,
                "bench_ready_count": bench_ready_count,
            }
        state = {
            "goal_id": goal["goal_id"],
            "stage": goal["stage"],
            "priority": goal["priority"],
            "deployed_count": deployed,
            "ready_count": ready,
            "energy_debt": debt,
            "active_ready_count": active_ready,
            "bench_ready_count": bench_ready,
            "near_ready_count": near_ready,
        }
        states.append(state)
        by_id[goal["goal_id"]] = {
            "priority": goal["priority"],
            "deployed_count": deployed,
            "ready_count": ready,
            "energy_debt": debt,
            "active_ready_count": active_ready,
            "bench_ready_count": bench_ready,
            "near_ready_count": near_ready,
            "requirement_states": requirement_states,
            "energy_uids": sorted(energy_uids),
            "required_target_count": sum(
                requirement["ready_target_count"] for requirement in goal["requirements"]
            ),
            "requirements": [dict(requirement) for requirement in goal["requirements"]],
        }
    return states, by_id


_DEPLOY_OPTION_KINDS = frozenset({"setup_active", "setup_bench", "play_basic_to_bench", "evolve"})
_PIVOT_OPTION_KINDS = frozenset({"retreat", "send_out"})
_FUND_OPTION_KINDS = frozenset({"attach_energy", "assignment_target"})


def _self_slots(frame: dict[str, Any]) -> list[dict[str, Any]]:
    own = frame["public_state"]["self"]
    return [*own["active"], *own["bench"]]


def _target_slot(frame: dict[str, Any], option: dict[str, Any]) -> dict[str, Any] | None:
    target_serial = option.get("target_serial")
    target_uid = option.get("target_uid")
    for slot in _self_slots(frame):
        if target_serial is not None and slot["serial"] == target_serial:
            return slot
    for slot in _self_slots(frame):
        if target_uid is not None and slot["local_card_uid"] == target_uid:
            return slot
    return None


def _energy_uid_needed(
    requirement: dict[str, Any], slot: dict[str, Any] | None, energy_uid: Any
) -> bool:
    if type(energy_uid) is not str:
        return False
    typed = requirement.get("energy_requirements", [])
    if typed:
        attached_uids = [] if slot is None else slot["attached_energy_uids"]
        for item in typed:
            if item["energy_uid"] == energy_uid and attached_uids.count(energy_uid) < item["count"]:
                return True
        return False
    if slot is None:
        return requirement["energy_required"] > 0
    return slot["attached_energy_count"] < requirement["energy_required"]


def _goal_missing_energy_source_quotas(
    goal: dict[str, Any], frame: dict[str, Any]
) -> dict[str, int]:
    """Bind an optional multi-select source window to exact public typed debt.

    Quotas are computed from the closest deployed targets required by the goal,
    then capped by the energy identities actually present in this immutable
    option window. This prevents duplicate copies of one type from satisfying a
    different missing type and permits a legal zero-card choice when no offered
    source advances the declared route.
    """
    slots = _self_slots(frame)
    debt_by_uid: dict[str, int] = {}
    for requirement in goal.get("requirements", []):
        typed = requirement.get("energy_requirements", [])
        if not typed:
            continue
        matches = [
            slot
            for slot in slots
            if slot["local_card_uid"] == requirement["card_uid"]
        ]
        matches.sort(
            key=lambda slot: (
                _requirement_slot_debt(requirement, slot),
                -slot["attached_energy_count"],
                slot["serial"],
            )
        )
        for slot in matches[: requirement["ready_target_count"]]:
            for item in typed:
                uid = item["energy_uid"]
                debt_by_uid[uid] = debt_by_uid.get(uid, 0) + max(
                    0, item["count"] - slot["attached_energy_uids"].count(uid)
                )
    available_by_uid: dict[str, int] = {}
    for option in frame["options"]:
        uid = option.get("card_uid")
        if type(uid) is str:
            available_by_uid[uid] = available_by_uid.get(uid, 0) + 1
    return {
        uid: min(debt, available_by_uid.get(uid, 0))
        for uid, debt in debt_by_uid.items()
        if debt > 0 and available_by_uid.get(uid, 0) > 0
    }


def _slot_after_energy(slot: dict[str, Any], energy_uid: str) -> dict[str, Any]:
    projected = dict(slot)
    projected["attached_energy_count"] = slot["attached_energy_count"] + 1
    projected["attached_energy_uids"] = [*slot["attached_energy_uids"], energy_uid]
    return projected


def _goal_option_facts(
    goal: dict[str, Any], frame: dict[str, Any], option: dict[str, Any] | None
) -> dict[str, Any]:
    empty = {
        "matches_target": False,
        "acquires_missing_target": False,
        "deploys_missing_target": False,
        "supplies_missing_energy": False,
        "funds_target": False,
        "completes_target": False,
        "pivots_ready_target": False,
        "executes_requirement": False,
        "target_energy_debt": None,
        "progress": 0,
    }
    if option is None:
        return empty
    kind = option["kind"]
    slots = _self_slots(frame)
    target_slot = _target_slot(frame, option)
    target_uid = option.get("target_uid")
    source_uid = option.get("source_uid")
    card_uid = option.get("card_uid")
    for requirement in goal.get("requirements", []):
        uid = requirement["card_uid"]
        matches = [slot for slot in slots if slot["local_card_uid"] == uid]
        missing_target = len(matches) < requirement["ready_target_count"]
        target_matches = target_uid == uid and target_slot is not None
        if target_matches:
            empty["matches_target"] = True
            debt = _requirement_slot_debt(requirement, target_slot)
            current = empty["target_energy_debt"]
            empty["target_energy_debt"] = debt if current is None else min(current, debt)
        if kind == "search" and missing_target and card_uid == uid:
            empty["acquires_missing_target"] = True
        if kind in _DEPLOY_OPTION_KINDS and missing_target and card_uid == uid:
            empty["deploys_missing_target"] = True
        energy_uid = card_uid
        if frame["prompt_kind"] in {"search", "assignment_source"}:
            for slot in matches or [None]:
                if _energy_uid_needed(requirement, slot, energy_uid):
                    empty["supplies_missing_energy"] = True
                    break
        if kind in _FUND_OPTION_KINDS and target_matches and _energy_uid_needed(
            requirement, target_slot, energy_uid
        ):
            empty["funds_target"] = True
            projected = _slot_after_energy(target_slot, energy_uid)
            if _requirement_slot_debt(requirement, projected) == 0:
                empty["completes_target"] = True
        if kind in _PIVOT_OPTION_KINDS and target_matches and _requirement_slot_ready(
            requirement, target_slot
        ):
            empty["pivots_ready_target"] = True
        if kind in {"attack", "granted_attack"} and source_uid == uid:
            declared = requirement.get("attack_index")
            if declared is not None and option.get("attack_index") == declared:
                source_slot = next(
                    (slot for slot in slots if slot["serial"] == option.get("source_serial")),
                    None,
                )
                if source_slot is not None and _requirement_slot_ready(requirement, source_slot):
                    empty["executes_requirement"] = True
        if kind == "use_ability" and source_uid == uid:
            declared = requirement.get("ability_index")
            if declared is not None and option.get("ability_index") == declared:
                empty["executes_requirement"] = True
    progress_levels = (
        ("executes_requirement", 7),
        ("pivots_ready_target", 6),
        ("completes_target", 5),
        ("funds_target", 4),
        ("supplies_missing_energy", 3),
        ("deploys_missing_target", 2),
        ("acquires_missing_target", 1),
    )
    empty["progress"] = next((level for key, level in progress_levels if empty[key]), 0)
    return empty


def _goal_window_max_progress(
    goal: dict[str, Any], frame: dict[str, Any]
) -> int:
    return max(
        (
            int(_goal_option_facts(goal, frame, option).get("progress", 0))
            for option in frame["options"]
        ),
        default=0,
    )


def _goal_window_max_setup_progress(
    goal: dict[str, Any], frame: dict[str, Any]
) -> int:
    return max(
        (
            progress
            if 0 < progress < 7
            else 0
            for progress in (
                int(_goal_option_facts(goal, frame, option).get("progress", 0))
                for option in frame["options"]
            )
        ),
        default=0,
    )


def _threat_clock(frame: dict[str, Any]) -> dict[str, int]:
    own = frame["public_state"]["self"]
    opponent = frame["public_state"]["opponent"]
    opponent_targets = [*opponent["active"], *opponent["bench"]]
    own_targets = [*own["active"], *own["bench"]]
    opponent_yield = max((slot["prize_value"] for slot in opponent_targets), default=1)
    own_yield = max((slot["prize_value"] for slot in own_targets), default=1)
    own_attacks = int(math.ceil(own["prizes_remaining"] / max(1, opponent_yield)))
    opponent_attacks = int(math.ceil(opponent["prizes_remaining"] / max(1, own_yield)))
    return {
        "own_attacks_to_win": own_attacks,
        "opponent_attacks_to_win": opponent_attacks,
        "tempo_margin": opponent_attacks - own_attacks,
    }


def _zone(frame: dict[str, Any], fact: str) -> list[dict[str, Any]]:
    owner, rest = fact.split(".", 1)
    state = frame["public_state"][owner]
    zone_name = rest.split(".", 1)[0]
    if zone_name == "board":
        return [*state["active"], *state["bench"]]
    return list(state[zone_name])


def _active_scalar(state: dict[str, Any], field: str) -> int | None:
    active = state["active"]
    return active[0][field] if active else None


def _window_uniform(frame: dict[str, Any], field: str) -> Any:
    values = {option[field] for option in frame["options"] if option[field] is not None}
    return next(iter(values)) if len(values) == 1 else None


def _enum_name(names: tuple[str, ...], raw: Any) -> str | None:
    return names[raw] if type(raw) is int and 0 <= raw < len(names) else None


def _fact(
    fact: str,
    frame: dict[str, Any],
    option: dict[str, Any] | None,
    goal: dict[str, Any],
    threat: dict[str, int],
    card_uid: str | None,
) -> Any:
    own = frame["public_state"]["self"]
    opponent = frame["public_state"]["opponent"]
    turn = own.get("turn", {})
    scalar = {
        "prompt_kind": frame["prompt_kind"],
        "select.type": _enum_name(SELECT_TYPE_NAMES, frame["select_semantics"]["select_type_raw"]),
        "select.context": _enum_name(SELECT_CONTEXT_NAMES, frame["select_semantics"]["select_context_raw"]),
        "select.type_raw": frame["select_semantics"]["select_type_raw"],
        "select.context_raw": frame["select_semantics"]["select_context_raw"],
        "turn_number": frame["public_state"]["turn_number"],
        "turn.supporter_available": turn.get("supporter_available"),
        "turn.manual_attachment_available": turn.get("manual_attachment_available"),
        "turn.retreat_available": turn.get("retreat_available"),
        "self.prizes_remaining": own["prizes_remaining"],
        "opponent.prizes_remaining": opponent["prizes_remaining"],
        "self.deck_count": own["deck_count"],
        "opponent.deck_count": opponent["deck_count"],
        "self.hand_count": len(own["hand"]),
        "opponent.hand_count": opponent["hand_count"],
        "self.bench_count": len(own["bench"]),
        "self.bench_capacity": own.get("bench_capacity"),
        "self.bench_space": (
            own["bench_capacity"] - len(own["bench"])
            if "bench_capacity" in own
            else None
        ),
        "self.bench_open": (
            len(own["bench"]) < own["bench_capacity"]
            if "bench_capacity" in own
            else any(
                current["kind"] == "play_basic_to_bench"
                for current in frame["options"]
            )
        ),
        "opponent.bench_count": len(opponent["bench"]),
        "self.active.remaining_hp": _active_scalar(own, "remaining_hp"),
        "self.active.prize_value": _active_scalar(own, "prize_value"),
        "opponent.active.remaining_hp": _active_scalar(opponent, "remaining_hp"),
        "opponent.active.prize_value": _active_scalar(opponent, "prize_value"),
        "window.source_uid": _window_uniform(frame, "source_uid"),
        "window.option_kind": _window_uniform(frame, "kind"),
        "select.min_count": frame["select_semantics"]["min_count"],
        "select.max_count": frame["select_semantics"]["max_count"],
        "goal.energy_debt": goal["energy_debt"],
        "goal.ready_count": goal["ready_count"],
        "goal.deployed_count": goal["deployed_count"],
        "goal.active_ready_count": goal["active_ready_count"],
        "goal.bench_ready_count": goal["bench_ready_count"],
        "goal.near_ready_count": goal["near_ready_count"],
        "goal.complete": goal["ready_count"] >= goal["required_target_count"],
        "threat.own_attacks_to_win": threat["own_attacks_to_win"],
        "threat.opponent_attacks_to_win": threat["opponent_attacks_to_win"],
        "threat.tempo_margin": threat["tempo_margin"],
    }
    if fact in scalar:
        return scalar[fact]
    if fact in {"goal.board_energy_count", "goal.hand_energy_count", "goal.discard_energy_count"}:
        energy_uids = set(goal.get("energy_uids", []))
        if fact == "goal.board_energy_count":
            return sum(
                1
                for slot in _self_slots(frame)
                for uid in slot["attached_energy_uids"]
                if uid in energy_uids
            )
        zone_name = "hand" if fact == "goal.hand_energy_count" else "discard"
        return sum(
            1
            for card in frame["public_state"]["self"][zone_name]
            if card["local_card_uid"] in energy_uids
        )
    if fact == "goal.immediate":
        if goal.get("active_ready_count", 0) > 0:
            return True
        return any(
            _goal_option_facts(goal, frame, current).get("pivots_ready_target", False)
            for current in frame["options"]
        )
    if fact in GOAL_UID_FACTS:
        field = fact.removeprefix("goal.").removesuffix("_uid")
        return goal.get("requirement_states", {}).get(card_uid, {}).get(field, 0)
    if fact == "goal.window.max_progress":
        return _goal_window_max_progress(goal, frame)
    if fact == "goal.option.is_max_progress":
        if option is None:
            return None
        progress = int(_goal_option_facts(goal, frame, option).get("progress", 0))
        maximum = _goal_window_max_progress(goal, frame)
        return maximum > 0 and progress == maximum
    if fact == "goal.window.max_setup_progress":
        return _goal_window_max_setup_progress(goal, frame)
    if fact == "goal.option.is_max_setup_progress":
        if option is None:
            return None
        progress = int(_goal_option_facts(goal, frame, option).get("progress", 0))
        maximum = _goal_window_max_setup_progress(goal, frame)
        return maximum > 0 and progress == maximum
    if fact.startswith("goal.option."):
        route_facts = _goal_option_facts(goal, frame, option)
        return route_facts.get(fact.removeprefix("goal.option."))
    if fact in ZONE_FACTS:
        return sum(1 for item in _zone(frame, fact) if item["local_card_uid"] == card_uid)
    if fact in ENERGY_ZONE_FACTS:
        return sum(slot["attached_energy_uids"].count(card_uid) for slot in _zone(frame, fact))
    if fact in WINDOW_UID_FACTS:
        field = fact.removeprefix("window.option_count_")
        return sum(1 for current in frame["options"] if current[field] == card_uid)
    if fact in {"option.source_is_active", "option.target_is_active"}:
        if option is None:
            return None
        serial_field = "source_serial" if fact == "option.source_is_active" else "target_serial"
        serial = option.get(serial_field)
        return serial is not None and any(
            slot["serial"] == serial
            for slot in frame["public_state"]["self"]["active"]
        )
    if fact.startswith("option."):
        return None if option is None else option[fact.split(".", 1)[1]]
    return None


def _compare(actual: Any, op: str, expected: Any) -> bool:
    try:
        if op == "eq":
            return type(actual) is type(expected) and actual == expected
        if op == "ne":
            return type(actual) is not type(expected) or actual != expected
        if op == "contains":
            return type(actual) is list and expected in actual
        if op == "not_contains":
            return type(actual) is list and expected not in actual
        if type(actual) is not int or type(expected) is not int:
            return False
        if op == "lt":
            return actual < expected
        if op == "lte":
            return actual <= expected
        if op == "gt":
            return actual > expected
        if op == "gte":
            return actual >= expected
    except Exception:
        return False
    return False


def _matches(
    conditions: list[dict[str, Any]],
    frame: dict[str, Any],
    option: dict[str, Any] | None,
    goal: dict[str, int],
    threat: dict[str, int],
) -> bool:
    return all(
        _compare(
            _fact(condition["fact"], frame, option, goal, threat, condition["card_uid"]),
            condition["op"],
            condition["value"],
        )
        for condition in conditions
    )


def _trunc_div(value: int, divisor: int) -> int:
    return value // divisor if value >= 0 else -((-value) // divisor)


def _clamp_score(value: int) -> int:
    return max(-MAX_SCORE, min(MAX_SCORE, value))


def _base_tactical_floor(option: dict[str, Any]) -> dict[str, Any] | None:
    """Return the locked public Base floor for a strictly productive action.

    This is deliberately narrower than the classic deck strategy: a legal
    positive-damage attack dominates ending the same public turn, while
    zero/unknown-damage effect attacks remain adapter-owned.
    """
    if option["kind"] != "attack":
        return None
    projected_damage = option["projected_damage"]
    if type(projected_damage) is not int or projected_damage <= 0:
        return None
    return {
        "rule_id": "@base.positive-damage-attack",
        "channel": "base",
        "contribution": 1,
    }


def _executable_route_step(
    steps: list[dict[str, Any]],
    frame: dict[str, Any],
    goals: dict[str, dict[str, Any]],
    threat: dict[str, int],
) -> tuple[dict[str, Any], list[int]] | None:
    minimum = frame["select_semantics"]["min_count"]
    maximum = frame["select_semantics"]["max_count"]
    for step in steps:
        if frame["prompt_kind"] not in step["prompt_kinds"]:
            continue
        goal = goals[step["goal_id"]]
        if not _matches(step["when"], frame, None, goal, threat):
            continue
        matching = [
            option["index"]
            for option in frame["options"]
            if _matches(step["option_when"], frame, option, goal, threat)
        ]
        selection_count = step["selection_count"]
        if selection_count is not None:
            if not minimum <= selection_count <= maximum:
                continue
            if selection_count > len(matching):
                continue
            if selection_count == 0:
                return step, []
        if matching:
            return step, matching
    return None


def _route_budget_rejection(
    budget: dict[str, int], frame: dict[str, Any]
) -> str | None:
    own = frame["public_state"]["self"]
    turn = own.get("turn", {})
    if budget["supporter_uses"] > 0 and turn.get("supporter_available") is not True:
        return "supporter_unavailable"
    if (
        budget["manual_attachments"] > 0
        and turn.get("manual_attachment_available") is not True
    ):
        return "manual_attachment_unavailable"
    if budget["retreats"] > 0 and turn.get("retreat_available") is not True:
        return "retreat_unavailable"
    if budget["bench_slots"] > 0:
        capacity = own.get("bench_capacity")
        if type(capacity) is not int:
            return "bench_capacity_unknown"
        if capacity - len(own["bench"]) < budget["bench_slots"]:
            return "insufficient_bench_space"
    return None


def _route_component_value(
    component: dict[str, Any],
    frame: dict[str, Any],
    goal: dict[str, Any],
    threat: dict[str, int],
) -> int:
    value = component["base"]
    for term in component["terms"]:
        actual = _fact(term["fact"], frame, None, goal, threat, None)
        if type(actual) is not int:
            continue
        bounded = max(term["minimum"], min(term["maximum"], actual))
        value = _clamp_score(value + bounded * term["coefficient"])
    return value


def _route_candidate_adjudication(
    document: dict[str, Any],
    frame: dict[str, Any],
    goals: dict[str, dict[str, Any]],
    threat: dict[str, int],
) -> tuple[
    dict[str, Any] | None,
    dict[str, Any] | None,
    list[int],
    dict[str, Any],
]:
    considered: list[dict[str, Any]] = []
    proposals: list[
        tuple[tuple[int | str, ...], dict[str, Any], dict[str, Any], list[int], int]
    ] = []
    for order, route in enumerate(document.get("route_candidates", [])):
        goal = goals[route["goal_id"]]
        row: dict[str, Any] = {
            "route_id": route["route_id"],
            "accepted": False,
            "selected": False,
            "rejection_reason": "",
            "first_executable_step_id": None,
            "current_indexes": [],
            "value": None,
        }
        if not _matches(route["when"], frame, None, goal, threat):
            row["rejection_reason"] = "route_guard_unmatched"
            considered.append(row)
            continue
        rejection = _route_budget_rejection(route["resource_budget"], frame)
        if rejection is not None:
            row["rejection_reason"] = rejection
            considered.append(row)
            continue
        executable = _executable_route_step(route["steps"], frame, goals, threat)
        if executable is None:
            row["rejection_reason"] = "no_current_executable_step"
            considered.append(row)
            continue
        step, indexes = executable
        route_value = {
            component_name: _route_component_value(
                route["value"][component_name], frame, goal, threat
            )
            for component_name in ROUTE_VALUE_COMPONENTS
        }
        comparison: tuple[int | str, ...] = (
            route_value["attack_windows"],
            -route_value["prize_progress"],
            -route_value["continuity"],
            route_value["resource_cost"],
            route_value["response_risk"],
            route_value["uncertainty"],
            route["route_id"],
        )
        row.update(
            {
                "accepted": True,
                "first_executable_step_id": step["step_id"],
                "current_indexes": list(indexes),
                "value": route_value,
            }
        )
        considered.append(row)
        proposals.append((comparison, route, step, indexes, order))
    selected_route: dict[str, Any] | None = None
    selected_step: dict[str, Any] | None = None
    selected_indexes: list[int] = []
    selected_value: dict[str, int] | None = None
    if proposals:
        _comparison, selected_route, selected_step, selected_indexes, selected_order = min(
            proposals, key=lambda proposal: (proposal[0], proposal[4])
        )
        considered[selected_order]["selected"] = True
        selected_value = considered[selected_order]["value"]
    audit = {
        "comparison_order": [
            "attack_windows.asc",
            "prize_progress.desc",
            "continuity.desc",
            "resource_cost.asc",
            "response_risk.asc",
            "uncertainty.asc",
            "route_id.asc",
        ],
        "considered_routes": considered,
        "selected_route_id": (
            None if selected_route is None else selected_route["route_id"]
        ),
        "selected_step_id": (
            None if selected_step is None else selected_step["step_id"]
        ),
        "selected_value": selected_value,
        "public_current_window_only": True,
    }
    return selected_route, selected_step, list(selected_indexes), audit


def _current_turn_contract(
    document: dict[str, Any],
    frame: dict[str, Any],
    goals: dict[str, dict[str, Any]],
    threat: dict[str, int],
) -> tuple[dict[str, Any], list[dict[str, Any]], int | None]:
    own = frame["public_state"]["self"]
    ledger = copy.deepcopy(own.get("turn", {}))
    contract: dict[str, Any] = {
        "route_id": None,
        "route_source": None,
        "route_goal_id": None,
        "owner_goal_id": None,
        "bridge_goal_id": None,
        "pivot_goal_id": None,
        "first_executable_step_id": None,
        "interaction_recipe_id": None,
        "interaction_step_id": None,
        "terminal": False,
        "checkpoint": False,
        "selection_count": None,
        "turn_ledger": ledger,
        "route_authority_indexes": [],
        "route_authority_applied": False,
        "route_candidate_adjudication": {},
        "current_window_only": True,
        "reobserve_after_commit": True,
        "stale_index_authority": False,
    }
    overlays: list[dict[str, Any]] = []
    selection_count: int | None = None
    selected_route: dict[str, Any] | None = None

    candidate_route, candidate_step, candidate_indexes, candidate_audit = (
        _route_candidate_adjudication(document, frame, goals, threat)
    )
    contract["route_candidate_adjudication"] = candidate_audit
    if candidate_route is not None and candidate_step is not None:
        selected_route = candidate_route
        selection_count = candidate_step["selection_count"]
        contract.update(
            {
                "route_id": candidate_route["route_id"],
                "route_source": "route_candidate",
                "route_goal_id": candidate_route["goal_id"],
                "owner_goal_id": candidate_route["owner_goal_id"],
                "bridge_goal_id": candidate_route["bridge_goal_id"],
                "pivot_goal_id": candidate_route["pivot_goal_id"],
                "first_executable_step_id": candidate_step["step_id"],
                "terminal": candidate_step["terminal"],
                "checkpoint": candidate_step["checkpoint"],
                "selection_count": selection_count,
                "route_authority_indexes": candidate_indexes,
            }
        )
        overlays.append(
            {
                "rule_id": (
                    f"@route_candidate.{candidate_route['route_id']}."
                    f"{candidate_step['step_id']}"
                ),
                "channel": "route_candidate",
                "contribution": 0,
                "goal_id": candidate_step["goal_id"],
                "indexes": candidate_indexes,
            }
        )

    ordered_routes = sorted(
        enumerate(document.get("turn_routes", [])),
        key=lambda pair: (-pair[1]["priority"], pair[0]),
    )
    for _order, route in ordered_routes if selected_route is None else []:
        goal = goals[route["goal_id"]]
        if not _matches(route["when"], frame, None, goal, threat):
            continue
        executable = _executable_route_step(route["steps"], frame, goals, threat)
        if executable is None:
            continue
        step, indexes = executable
        selected_route = route
        selection_count = step["selection_count"]
        contract.update(
            {
                "route_id": route["route_id"],
                "route_source": "turn_route",
                "route_goal_id": route["goal_id"],
                "owner_goal_id": route["owner_goal_id"],
                "bridge_goal_id": route["bridge_goal_id"],
                "pivot_goal_id": route["pivot_goal_id"],
                "first_executable_step_id": step["step_id"],
                "terminal": step["terminal"],
                "checkpoint": step["checkpoint"],
                "selection_count": selection_count,
            }
        )
        overlays.append(
            {
                "rule_id": f"@turn_route.{route['route_id']}.{step['step_id']}",
                "channel": "route",
                "contribution": step["score_bonus"],
                "goal_id": step["goal_id"],
                "indexes": indexes,
            }
        )
        break

    source_uid = _window_uniform(frame, "source_uid")
    ordered_recipes = sorted(
        enumerate(document.get("interaction_recipes", [])),
        key=lambda pair: (-pair[1]["priority"], pair[0]),
    )
    for _order, recipe in ordered_recipes:
        if source_uid not in recipe["source_uids"]:
            continue
        if recipe["route_id"] is not None and (
            selected_route is None or selected_route["route_id"] != recipe["route_id"]
        ):
            continue
        goal = goals[recipe["goal_id"]]
        if not _matches(recipe["when"], frame, None, goal, threat):
            continue
        executable = _executable_route_step(recipe["steps"], frame, goals, threat)
        if executable is None:
            continue
        step, indexes = executable
        if step["selection_count"] is not None:
            selection_count = step["selection_count"]
            contract["selection_count"] = selection_count
        contract["interaction_recipe_id"] = recipe["recipe_id"]
        contract["interaction_step_id"] = step["step_id"]
        contract["terminal"] = bool(contract["terminal"] or step["terminal"])
        contract["checkpoint"] = bool(contract["checkpoint"] or step["checkpoint"])
        overlays.append(
            {
                "rule_id": f"@interaction_recipe.{recipe['recipe_id']}.{step['step_id']}",
                "channel": "interaction_recipe",
                "contribution": step["score_bonus"],
                "goal_id": step["goal_id"],
                "indexes": indexes,
            }
        )
        break

    if not contract["terminal"]:
        ordered_contracts = sorted(
            enumerate(document.get("turn_bonus_contracts", [])),
            key=lambda pair: (-pair[1]["priority"], pair[0]),
        )
        for _order, bonus_contract in ordered_contracts:
            contract_goal = goals[bonus_contract["goal_id"]]
            if not _matches(
                bonus_contract["when"], frame, None, contract_goal, threat
            ):
                continue
            matched_bonus_ids: list[str] = []
            for bonus in bonus_contract["bonuses"]:
                if frame["prompt_kind"] not in bonus["prompt_kinds"]:
                    continue
                goal = goals[bonus["goal_id"]]
                if not _matches(bonus["when"], frame, None, goal, threat):
                    continue
                indexes = [
                    option["index"]
                    for option in frame["options"]
                    if _matches(bonus["option_when"], frame, option, goal, threat)
                ]
                if not indexes:
                    continue
                matched_bonus_ids.append(bonus["bonus_id"])
                overlays.append(
                    {
                        "rule_id": (
                            f"@turn_bonus.{bonus_contract['contract_id']}."
                            f"{bonus['bonus_id']}"
                        ),
                        "channel": "turn_bonus",
                        "contribution": bonus["score_bonus"],
                        "goal_id": bonus["goal_id"],
                        "indexes": indexes,
                    }
                )
            if matched_bonus_ids:
                contract["turn_bonus_contract_id"] = bonus_contract["contract_id"]
                contract["turn_bonus_ids"] = matched_bonus_ids
                break
    return contract, overlays, selection_count


def _evaluate(
    policy: CompetitivePolicyV2,
    frame: dict[str, Any],
) -> tuple[
    list[int],
    int,
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, int],
    bool,
    dict[str, int] | None,
    dict[str, Any],
]:
    document = policy.to_public_dict()
    goal_states, goals = _goal_states(document, frame)
    threat = _threat_clock(frame)
    turn_contract, route_overlays, route_selection_count = _current_turn_contract(
        document, frame, goals, threat
    )
    scorecards: list[dict[str, Any]] = []
    for option in frame["options"]:
        total = 0
        matched: list[dict[str, Any]] = []
        best_priority = 0
        base_floor = _base_tactical_floor(option)
        if base_floor is not None:
            total = _clamp_score(total + base_floor["contribution"])
            matched.append(base_floor)
        for rule in document["rules"]:
            goal = goals[rule["goal_id"]]
            if not _matches(rule["when"], frame, option, goal, threat):
                continue
            raw = rule["base_score"]
            for term in rule["score_terms"]:
                actual = _fact(term["fact"], frame, option, goal, threat, None)
                if type(actual) is not int:
                    continue
                bounded = max(term["minimum"], min(term["maximum"], actual))
                raw = _clamp_score(raw + bounded * term["coefficient"])
            contribution = _trunc_div(raw * rule["confidence_milli"], 1000)
            total = _clamp_score(total + contribution)
            best_priority = max(best_priority, goal["priority"])
            matched.append(
                {
                    "rule_id": rule["rule_id"],
                    "channel": rule["channel"],
                    "contribution": contribution,
                }
            )
        for overlay in route_overlays:
            if option["index"] not in overlay["indexes"]:
                continue
            contribution = overlay["contribution"]
            total = _clamp_score(total + contribution)
            best_priority = max(best_priority, goals[overlay["goal_id"]]["priority"])
            matched.append(
                {
                    "rule_id": overlay["rule_id"],
                    "channel": overlay["channel"],
                    "contribution": contribution,
                }
            )
        scorecards.append(
            {
                "index": option["index"],
                "score": total,
                "goal_priority": best_priority,
                "matched_rules": matched,
            }
        )
    option_kinds = {option["index"]: option["kind"] for option in frame["options"]}
    ranked = [
        card["index"]
        for card in sorted(
            scorecards,
            key=lambda card: (
                -card["score"],
                -card["goal_priority"],
                0 if option_kinds.get(card["index"]) == "end_turn" else 1,
                card["index"],
            ),
        )
    ]
    route_authority_indexes = turn_contract["route_authority_indexes"]
    if route_authority_indexes:
        ranked = [
            *(index for index in ranked if index in route_authority_indexes),
            *(index for index in ranked if index not in route_authority_indexes),
        ]
    minimum = frame["select_semantics"]["min_count"]
    maximum = frame["select_semantics"]["max_count"]
    desired = minimum
    count_rule_matched = False
    selection_quotas: dict[str, int] | None = None
    ordered_count_rules = sorted(enumerate(document["count_rules"]), key=lambda pair: (pair[1]["priority"], pair[0]))
    for _order, rule in ordered_count_rules:
        goal = goals[rule["goal_id"]]
        if not _matches(rule["when"], frame, None, goal, threat):
            continue
        if rule["mode"] == "fixed":
            desired = rule["fixed_count"]
        elif rule["mode"] == "goal_energy_debt":
            desired = goal["energy_debt"]
        elif rule["mode"] == "goal_missing_energy_sources":
            selection_quotas = _goal_missing_energy_source_quotas(goal, frame)
            desired = sum(selection_quotas.values())
        else:
            actual = _fact(rule["fact"], frame, None, goal, threat, None)
            if type(actual) is not int:
                continue
            lethal = int(math.ceil(max(0, actual) / rule["divisor"]))
            if rule["mode"] == "ceil_public_fact_divisor_with_reserve":
                available = len(frame["options"])
                desired = (
                    lethal
                    if lethal <= available
                    else max(0, available - rule["fixed_count"])
                )
            else:
                desired = lethal
        desired = max(minimum, min(maximum, desired))
        count_rule_matched = True
        break
    if route_selection_count is not None:
        desired = max(minimum, min(maximum, route_selection_count))
        count_rule_matched = True
    return (
        ranked,
        desired,
        scorecards,
        goal_states,
        threat,
        count_rule_matched,
        selection_quotas,
        turn_contract,
    )


@dataclass(frozen=True, slots=True)
class CompetitivePolicyV2Decision:
    accepted: bool
    error_code: str
    selected_indexes: list[int]
    audit: dict[str, Any]


def _index_list(value: Any, option_count: int) -> bool:
    return (
        type(value) is list
        and len(value) == len(set(value))
        and all(type(index) is int and 0 <= index < option_count for index in value)
    )


class CompetitivePolicyV2Runtime:
    @staticmethod
    def decide(
        policy: Any,
        frame: Any,
        *,
        mandatory_indexes: list[int] | None = None,
        terminal_indexes: list[int] | None = None,
        base_hard_tiers: list[dict[str, Any]] | None = None,
        base_vetoed_indexes: list[int] | None = None,
    ) -> CompetitivePolicyV2Decision:
        if type(policy) is not CompetitivePolicyV2 or not policy.validate_integrity():
            return CompetitivePolicyV2Decision(False, "invalid_policy", [], {})
        frame_value = copy.deepcopy(frame)
        error = _frame_error(frame_value)
        if error is not None:
            return CompetitivePolicyV2Decision(False, error, [], {})
        option_count = len(frame_value["options"])
        mandatory = [] if mandatory_indexes is None else copy.deepcopy(mandatory_indexes)
        terminal = [] if terminal_indexes is None else copy.deepcopy(terminal_indexes)
        vetoed = [] if base_vetoed_indexes is None else copy.deepcopy(base_vetoed_indexes)
        if not all(_index_list(value, option_count) for value in (mandatory, terminal, vetoed)):
            return CompetitivePolicyV2Decision(False, "invalid_base_authority", [], {})
        if base_hard_tiers is None:
            tiers = {index: (0,) for index in range(option_count)}
        else:
            if type(base_hard_tiers) is not list or len(base_hard_tiers) != option_count:
                return CompetitivePolicyV2Decision(False, "invalid_base_authority", [], {})
            tiers: dict[int, tuple[int, ...]] = {}
            for entry in base_hard_tiers:
                if (
                    type(entry) is not dict
                    or set(entry) != {"index", "tier"}
                    or type(entry["index"]) is not int
                    or not 0 <= entry["index"] < option_count
                    or entry["index"] in tiers
                    or type(entry["tier"]) is not list
                    or not entry["tier"]
                    or len(entry["tier"]) > 8
                    or any(not _safe_int(part, signed=True) for part in entry["tier"])
                ):
                    return CompetitivePolicyV2Decision(False, "invalid_base_authority", [], {})
                tiers[entry["index"]] = tuple(entry["tier"])
            if set(tiers) != set(range(option_count)):
                return CompetitivePolicyV2Decision(False, "invalid_base_authority", [], {})
        minimum = frame_value["select_semantics"]["min_count"]
        maximum = frame_value["select_semantics"]["max_count"]
        for forced in (terminal, mandatory):
            if forced and not minimum <= len(forced) <= maximum:
                return CompetitivePolicyV2Decision(False, "invalid_base_authority", [], {})
        (
            ranked,
            desired,
            scorecards,
            goals,
            threat,
            count_matched,
            selection_quotas,
            turn_contract,
        ) = _evaluate(policy, frame_value)
        any_rule_matched = any(card["matched_rules"] for card in scorecards)
        if not count_matched and not any_rule_matched:
            end_turn = [
                option["index"]
                for option in frame_value["options"]
                if option["kind"] == "end_turn"
            ]
            ranked = [*end_turn, *(index for index in ranked if index not in end_turn)]
        fallback_used = False
        if terminal:
            owner = "terminal"
            selected = list(terminal)
        elif mandatory:
            owner = "mandatory"
            selected = list(mandatory)
        else:
            owner = "base_graph"
            frontier = list(range(option_count))
            if frontier:
                best_tier = min(tiers[index] for index in frontier)
                frontier = [index for index in frontier if tiers[index] == best_tier]
            frontier = [index for index in frontier if index not in vetoed]
            ordered = [index for index in ranked if index in frontier]
            if selection_quotas is not None:
                remaining = dict(selection_quotas)
                typed_ordered: list[int] = []
                for index in ordered:
                    uid = frame_value["options"][index].get("card_uid")
                    if type(uid) is str and remaining.get(uid, 0) > 0:
                        typed_ordered.append(index)
                        remaining[uid] -= 1
                if len(typed_ordered) < minimum:
                    fallback_used = True
                    desired = minimum
                    selected = ordered[:desired]
                else:
                    desired = max(minimum, min(maximum, len(typed_ordered)))
                    selected = typed_ordered[:desired]
            else:
                if desired > len(ordered):
                    fallback_used = True
                    desired = minimum
                selected = ordered[:desired]
            if not minimum <= len(selected) <= maximum:
                return CompetitivePolicyV2Decision(False, "insufficient_candidates", [], {})
            if not count_matched and not any_rule_matched:
                fallback_used = True
            elif not count_matched and any(
                frame_value["options"][index]["kind"] == "end_turn"
                and not scorecards[index]["matched_rules"]
                for index in selected
            ):
                # A veto/negative rule on some other option must not make a
                # neutral, unmatched action outrank Base's safe end-turn tie
                # fallback. Keep the audit honest about who owned that choice.
                fallback_used = True
        audit_payload = {
            "schema_version": 2,
            "profile_id": PROFILE_ID,
            "policy_hash": policy.policy_hash,
            "public_observation_hash": frame_value["source"]["public_observation_hash"],
            "window_id": frame_value["source"]["window_id"],
            "owner_layer": owner,
            "ranked_indexes": ranked,
            "desired_count": desired,
            "selected_indexes": selected,
            "goal_states": goals,
            "threat_clock": threat,
            "turn_contract": turn_contract,
            "scorecards": scorecards,
            "fallback_used": fallback_used,
            "public_only": True,
            "stale_plan_has_authority": False,
        }
        authority_indexes = turn_contract.get("route_authority_indexes", [])
        turn_contract["route_authority_applied"] = bool(
            authority_indexes
            and owner == "base_graph"
            and any(index in authority_indexes for index in selected)
        )
        audit = {**audit_payload, "audit_hash": _sha(audit_payload)}
        return CompetitivePolicyV2Decision(True, "", list(selected), audit)


__all__ = [
    "CompetitivePolicyV2",
    "CompetitivePolicyV2CompileOutcome",
    "CompetitivePolicyV2Compiler",
    "CompetitivePolicyV2Decision",
    "CompetitivePolicyV2Runtime",
    "FRAME_PROFILE_ID",
    "PROFILE_ID",
]
