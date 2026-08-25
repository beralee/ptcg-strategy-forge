from __future__ import annotations

import copy
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

from ptcg_strategy_forge.cli import run_suite  # noqa: E402
from ptcg_strategy_forge.scenarios import write_json  # noqa: E402
from scripts.ai.ptcgdap.competitive_policy_v2 import (  # noqa: E402
    CompetitivePolicyV2Compiler,
    CompetitivePolicyV2Runtime,
)
from tools.ptcgdap.author_strategy_developer import build_development_package  # noqa: E402


GRIMMSNARL = "CSV10C_148"
MORGREM = "CSV10C_147"
DARK_ENERGY = "CSVE1C_DAR"
RAGING_BOLT = "CSV7C_154"
TEAL_MASK_OGERPON = "CSV8C_028"
FAN_ROTOM = "CSV9C_161"
FIGHTING_ENERGY = "CSVE1C_FIG"
LIGHTNING_ENERGY = "CSVE1C_LIG"
GRASS_ENERGY = "CSVE1C_GRA"
NIGHT_STRETCHER = "CSV8C_183"
NEST_BALL = "CSVH1C_043"


def _condition(fact: str, op: str, value: object) -> dict[str, object]:
    return {"fact": fact, "op": op, "value": value, "card_uid": None}


def _adapter() -> dict[str, object]:
    goal_id = "ready-two-attackers"
    return {
        "schema_version": 2,
        "adapter_id": "dev.beralee.marnie-forge-demo",
        "adapter_version": 2,
        "goals": [
            {
                "goal_id": goal_id,
                "stage": "fund",
                "priority": 100,
                "requirements": [
                    {"card_uid": GRIMMSNARL, "ready_target_count": 1, "energy_required": 2},
                    {"card_uid": MORGREM, "ready_target_count": 1, "energy_required": 2},
                ],
            }
        ],
        "count_rules": [
            {
                "rule_id": "exact-public-energy-debt",
                "priority": 0,
                "goal_id": goal_id,
                "mode": "goal_energy_debt",
                "fixed_count": None,
                "fact": None,
                "divisor": None,
                "when": [_condition("prompt_kind", "eq", "assignment_source")],
            }
        ],
        "rules": [
            {
                "rule_id": "select-dark-energy",
                "goal_id": goal_id,
                "goal_stage": "fund",
                "channel": "interaction",
                "horizon": 0,
                "confidence_milli": 1000,
                "base_score": 1000,
                "when": [_condition("option.card_uid", "eq", DARK_ENERGY)],
                "score_terms": [],
            },
            {
                "rule_id": "assign-to-largest-debt",
                "goal_id": goal_id,
                "goal_stage": "fund",
                "channel": "interaction",
                "horizon": 0,
                "confidence_milli": 1000,
                "base_score": 0,
                "when": [_condition("prompt_kind", "eq", "assignment_target")],
                "score_terms": [
                    {
                        "fact": "option.target_energy_debt",
                        "coefficient": 100,
                        "minimum": 0,
                        "maximum": 10,
                    }
                ],
            },
        ],
    }


def _slot(serial: int, uid: str, attached: int, required: int) -> dict[str, object]:
    return {
        "serial": serial,
        "local_card_uid": uid,
        "remaining_hp": 200,
        "prize_value": 2 if uid == GRIMMSNARL else 1,
        "attached_energy_count": attached,
        "attached_energy_uids": [DARK_ENERGY] * attached,
        "minimum_attack_energy_count": required,
        "attack_ready": attached >= required,
        "energy_debt": max(0, required - attached),
    }


def _option(index: int, *, card_uid: str | None = None) -> dict[str, object]:
    return {
        "index": index,
        "kind": "assignment_source",
        "card_uid": card_uid,
        "source_uid": None,
        "source_serial": None,
        "target_uid": None,
        "target_serial": None,
        "target_remaining_hp": None,
        "target_prize_value": None,
        "target_attached_energy_count": None,
        "target_attached_energy_uids": None,
        "target_minimum_attack_energy_count": None,
        "target_attack_ready": None,
        "target_energy_debt": None,
        "projected_damage": None,
        "projected_knockout": False,
        "requires_interaction": False,
        "attack_index": None,
        "ability_index": None,
        "pending_assignment_count": 0,
        "tags": [],
        "option_type_raw": 3,
        "option_player_index": 0,
    }


def _frame() -> dict[str, object]:
    return {
        "schema_version": 2,
        "profile_id": "ptcgdap-competitive-public-frame-v2",
        "sequence": 1,
        "seat": 0,
        "prompt_kind": "assignment_source",
        "source": {
            "public_observation_hash": "A" * 64,
            "window_id": "B" * 64,
        },
        "public_state": {
            "turn_number": 10,
            "phase": "MAIN",
            "self": {
                "hand": [],
                "active": [_slot(10, GRIMMSNARL, 1, 2)],
                "bench": [_slot(11, MORGREM, 0, 2)],
                "discard": [],
                "deck_count": 30,
                "prizes_remaining": 4,
            },
            "opponent": {
                "hand_count": 5,
                "active": [],
                "bench": [],
                "discard": [],
                "deck_count": 28,
                "prizes_remaining": 2,
            },
        },
        "select_semantics": {
            "min_count": 0,
            "max_count": 5,
            "select_type_raw": 1,
            "select_context_raw": 0,
        },
        "options": [_option(index, card_uid=DARK_ENERGY) for index in range(5)],
    }


class CompetitiveForgeV2Tests(unittest.TestCase):
    def test_route_candidates_adjudicate_complete_routes_before_local_scores(self) -> None:
        document = _adapter()
        goal_id = "ready-two-attackers"
        document["adapter_version"] = 25
        document["count_rules"] = []
        document["rules"] = [
            {
                "rule_id": "local.greedy-attack",
                "goal_id": goal_id,
                "goal_stage": "execute",
                "channel": "tactical",
                "horizon": 0,
                "confidence_milli": 1000,
                "base_score": 900000,
                "when": [_condition("option.kind", "eq", "attack")],
                "score_terms": [],
            }
        ]

        def component(base: int) -> dict[str, object]:
            return {"base": base, "terms": []}

        def budget(manual_attachment: int) -> dict[str, int]:
            return {
                "supporter_uses": 0,
                "manual_attachments": manual_attachment,
                "retreats": 0,
                "bench_slots": 0,
                "ability_uses": 0,
                "discard_cards": 0,
                "search_cards": 0,
            }

        def route_value(continuity: int, resource_cost: int, response_risk: int) -> dict[str, object]:
            return {
                "attack_windows": component(1),
                "prize_progress": component(1),
                "continuity": component(continuity),
                "resource_cost": component(resource_cost),
                "response_risk": component(response_risk),
                "uncertainty": component(0),
            }

        document["route_candidates"] = [
            {
                "route_id": "continuity-first",
                "goal_id": goal_id,
                "owner_goal_id": goal_id,
                "bridge_goal_id": goal_id,
                "pivot_goal_id": goal_id,
                "when": [],
                "resource_budget": budget(1),
                "value": route_value(5, 3, 1),
                "steps": [
                    {
                        "step_id": "fund-next-attacker",
                        "prompt_kinds": ["main"],
                        "goal_id": goal_id,
                        "when": [],
                        "option_when": [_condition("option.kind", "eq", "attach_energy")],
                        "selection_count": 1,
                        "terminal": False,
                        "checkpoint": False,
                    }
                ],
            },
            {
                "route_id": "attack-now",
                "goal_id": goal_id,
                "owner_goal_id": goal_id,
                "bridge_goal_id": goal_id,
                "pivot_goal_id": goal_id,
                "when": [],
                "resource_budget": budget(0),
                "value": route_value(1, 0, 2),
                "steps": [
                    {
                        "step_id": "take-current-attack",
                        "prompt_kinds": ["main"],
                        "goal_id": goal_id,
                        "when": [],
                        "option_when": [_condition("option.kind", "eq", "attack")],
                        "selection_count": 1,
                        "terminal": True,
                        "checkpoint": False,
                    }
                ],
            },
        ]
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            document,
            allowed_card_uids={GRIMMSNARL, MORGREM, DARK_ENERGY},
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        self.assertIsNotNone(compiled.policy)

        frame = _frame()
        frame["prompt_kind"] = "main"
        frame["select_semantics"].update({"min_count": 1, "max_count": 1})
        frame["public_state"]["self"]["turn"] = {
            "supporter_available": True,
            "manual_attachment_available": True,
            "retreat_available": True,
        }
        frame["public_state"]["self"]["active"] = [_slot(10, GRIMMSNARL, 1, 2)]
        frame["public_state"]["self"]["bench"] = [_slot(11, MORGREM, 0, 2)]
        attack = _option(0)
        attack.update(
            {
                "kind": "attack",
                "source_uid": GRIMMSNARL,
                "source_serial": 10,
                "attack_index": 0,
                "projected_damage": 120,
            }
        )
        attach = _option(1, card_uid=DARK_ENERGY)
        attach.update(
            {
                "kind": "attach_energy",
                "target_uid": MORGREM,
                "target_serial": 11,
                "target_attached_energy_count": 0,
                "target_attached_energy_uids": [],
                "target_minimum_attack_energy_count": 2,
                "target_attack_ready": False,
                "target_energy_debt": 2,
            }
        )
        frame["options"] = [attack, attach]

        continuity = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertTrue(continuity.accepted, continuity.error_code)
        self.assertEqual([1], continuity.selected_indexes)
        adjudication = continuity.audit["turn_contract"]["route_candidate_adjudication"]
        self.assertEqual("continuity-first", adjudication["selected_route_id"])
        self.assertTrue(continuity.audit["turn_contract"]["route_authority_applied"])

        reordered = copy.deepcopy(frame)
        reordered["source"]["window_id"] = "C" * 64
        reordered["options"] = [copy.deepcopy(attach), copy.deepcopy(attack)]
        for index, option in enumerate(reordered["options"]):
            option["index"] = index
        self.assertEqual(
            [0], CompetitivePolicyV2Runtime.decide(compiled.policy, reordered).selected_indexes
        )

        spent = copy.deepcopy(frame)
        spent["source"]["window_id"] = "D" * 64
        spent["public_state"]["self"]["turn"]["manual_attachment_available"] = False
        attack_now = CompetitivePolicyV2Runtime.decide(compiled.policy, spent)
        self.assertEqual([0], attack_now.selected_indexes)
        spent_adjudication = attack_now.audit["turn_contract"]["route_candidate_adjudication"]
        self.assertEqual("attack-now", spent_adjudication["selected_route_id"])
        continuity_row = next(
            row for row in spent_adjudication["considered_routes"]
            if row["route_id"] == "continuity-first"
        )
        self.assertEqual("manual_attachment_unavailable", continuity_row["rejection_reason"])

        hard_tier = CompetitivePolicyV2Runtime.decide(
            compiled.policy,
            frame,
            base_hard_tiers=[{"index": 0, "tier": [0]}, {"index": 1, "tier": [1]}],
        )
        self.assertEqual([0], hard_tier.selected_indexes)
        self.assertFalse(hard_tier.audit["turn_contract"]["route_authority_applied"])
        vetoed = CompetitivePolicyV2Runtime.decide(
            compiled.policy,
            frame,
            base_vetoed_indexes=[1],
        )
        self.assertEqual([0], vetoed.selected_indexes)
        self.assertFalse(vetoed.audit["turn_contract"]["route_authority_applied"])
        mandatory = CompetitivePolicyV2Runtime.decide(
            compiled.policy,
            frame,
            mandatory_indexes=[0],
        )
        self.assertEqual([0], mandatory.selected_indexes)
        self.assertEqual("mandatory", mandatory.audit["owner_layer"])
        terminal = CompetitivePolicyV2Runtime.decide(
            compiled.policy,
            frame,
            terminal_indexes=[0],
        )
        self.assertEqual([0], terminal.selected_indexes)
        self.assertEqual("terminal", terminal.audit["owner_layer"])
        with tempfile.TemporaryDirectory() as temp_name:
            package_source = Path(temp_name) / "package"
            shutil.copytree(ROOT / "demo/marnie-forge/package", package_source)
            write_json(package_source / "policy/adapter.json", document)
            archive = Path(temp_name) / "route-candidate.ptcgai"
            build_development_package(package_source, archive)
            self.assertTrue(archive.is_file())

    def test_route_value_uses_public_prize_clock_for_opponent_response_risk(self) -> None:
        document = _adapter()
        goal_id = "ready-two-attackers"
        document["adapter_version"] = 26
        document["count_rules"] = []

        def component(base: int, terms: list[dict[str, object]] | None = None) -> dict[str, object]:
            return {"base": base, "terms": [] if terms is None else terms}

        def value(response_risk: dict[str, object]) -> dict[str, object]:
            return {
                "attack_windows": component(1),
                "prize_progress": component(1),
                "continuity": component(1),
                "resource_cost": component(0),
                "response_risk": response_risk,
                "uncertainty": component(0),
            }

        budget = {
            "supporter_uses": 0,
            "manual_attachments": 0,
            "retreats": 0,
            "bench_slots": 0,
            "ability_uses": 0,
            "discard_cards": 0,
            "search_cards": 0,
        }
        document["route_candidates"] = [
            {
                "route_id": "ready-two-prize-counter",
                "goal_id": goal_id,
                "owner_goal_id": goal_id,
                "bridge_goal_id": goal_id,
                "pivot_goal_id": goal_id,
                "when": [],
                "resource_budget": dict(budget),
                "value": value(component(2)),
                "steps": [
                    {
                        "step_id": "send-ready-counter",
                        "prompt_kinds": ["send_out"],
                        "goal_id": goal_id,
                        "when": [],
                        "option_when": [_condition("option.target_uid", "eq", GRIMMSNARL)],
                        "selection_count": 1,
                        "terminal": False,
                        "checkpoint": False,
                    }
                ],
            },
            {
                "route_id": "one-prize-bridge",
                "goal_id": goal_id,
                "owner_goal_id": goal_id,
                "bridge_goal_id": goal_id,
                "pivot_goal_id": goal_id,
                "when": [],
                "resource_budget": dict(budget),
                "value": value(
                    component(
                        -2,
                        [
                            {
                                "fact": "opponent.prizes_remaining",
                                "coefficient": 1,
                                "minimum": 0,
                                "maximum": 6,
                            }
                        ],
                    )
                ),
                "steps": [
                    {
                        "step_id": "send-one-prize-bridge",
                        "prompt_kinds": ["send_out"],
                        "goal_id": goal_id,
                        "when": [],
                        "option_when": [_condition("option.target_uid", "eq", MORGREM)],
                        "selection_count": 1,
                        "terminal": False,
                        "checkpoint": False,
                    }
                ],
            },
        ]
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            document,
            allowed_card_uids={GRIMMSNARL, MORGREM, DARK_ENERGY},
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        frame = _frame()
        frame["prompt_kind"] = "send_out"
        frame["select_semantics"].update({"min_count": 1, "max_count": 1})
        frame["public_state"]["self"]["active"] = []
        frame["public_state"]["self"]["bench"] = [
            _slot(10, GRIMMSNARL, 2, 2),
            _slot(11, MORGREM, 0, 2),
        ]
        ready = _option(0)
        ready.update(
            {
                "kind": "send_out",
                "target_uid": GRIMMSNARL,
                "target_serial": 10,
                "target_prize_value": 2,
                "target_attached_energy_count": 2,
                "target_attached_energy_uids": [DARK_ENERGY, DARK_ENERGY],
                "target_minimum_attack_energy_count": 2,
                "target_attack_ready": True,
                "target_energy_debt": 0,
            }
        )
        bridge = _option(1)
        bridge.update(
            {
                "kind": "send_out",
                "target_uid": MORGREM,
                "target_serial": 11,
                "target_prize_value": 1,
                "target_attached_energy_count": 0,
                "target_attached_energy_uids": [],
                "target_minimum_attack_energy_count": 2,
                "target_attack_ready": False,
                "target_energy_debt": 2,
            }
        )
        frame["options"] = [ready, bridge]
        frame["public_state"]["opponent"]["prizes_remaining"] = 2
        bridge_clock = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertEqual([1], bridge_clock.selected_indexes)
        self.assertEqual(
            "one-prize-bridge",
            bridge_clock.audit["turn_contract"]["route_candidate_adjudication"]["selected_route_id"],
        )
        early_game = copy.deepcopy(frame)
        early_game["source"]["window_id"] = "E" * 64
        early_game["public_state"]["opponent"]["prizes_remaining"] = 6
        counter = CompetitivePolicyV2Runtime.decide(compiled.policy, early_game)
        self.assertEqual([0], counter.selected_indexes)
        self.assertEqual(
            "ready-two-prize-counter",
            counter.audit["turn_contract"]["route_candidate_adjudication"]["selected_route_id"],
        )

    def test_bench_open_uses_public_capacity_without_a_basic_in_hand(self) -> None:
        adapter = {
            "schema_version": 2,
            "adapter_id": "dev.beralee.public-bench-capacity-red",
            "adapter_version": 22,
            "goals": [
                {
                    "goal_id": "first-attacker",
                    "stage": "deploy",
                    "priority": 900,
                    "requirements": [
                        {
                            "card_uid": RAGING_BOLT,
                            "ready_target_count": 1,
                            "energy_required": 2,
                        }
                    ],
                }
            ],
            "count_rules": [],
            "rules": [
                {
                    "rule_id": "nest-for-first-attacker",
                    "goal_id": "first-attacker",
                    "goal_stage": "acquire",
                    "channel": "macro",
                    "horizon": 0,
                    "confidence_milli": 1000,
                    "base_score": 1000,
                    "when": [
                        _condition("self.bench_open", "eq", True),
                        _condition("option.card_uid", "eq", NEST_BALL),
                    ],
                    "score_terms": [],
                }
            ],
        }
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            adapter,
            allowed_card_uids={RAGING_BOLT, TEAL_MASK_OGERPON, NEST_BALL},
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        frame = _frame()
        frame["prompt_kind"] = "main"
        frame["select_semantics"].update({"min_count": 1, "max_count": 1})
        frame["public_state"]["self"].update(
            {
                "active": [_slot(20, TEAL_MASK_OGERPON, 0, 3)],
                "bench": [
                    _slot(21, TEAL_MASK_OGERPON, 0, 3),
                    _slot(22, TEAL_MASK_OGERPON, 0, 3),
                    _slot(23, TEAL_MASK_OGERPON, 0, 3),
                    _slot(24, TEAL_MASK_OGERPON, 0, 3),
                    _slot(25, TEAL_MASK_OGERPON, 0, 3),
                ],
                "bench_capacity": 8,
                "hand": [{"serial": 30, "local_card_uid": NEST_BALL}],
            }
        )
        nest = {**_option(0, card_uid=NEST_BALL), "kind": "play_trainer"}
        end_turn = {**_option(1), "kind": "end_turn"}
        frame["options"] = [nest, end_turn]

        decision = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertTrue(decision.accepted, decision.error_code)
        self.assertEqual([0], decision.selected_indexes)

    def test_goal_relative_continuity_facts_bind_public_debt_and_target_position(self) -> None:
        goal_id = "attack-continuity"
        adapter = {
            "schema_version": 2,
            "adapter_id": "dev.beralee.public-continuity-facts-red",
            "adapter_version": 19,
            "goals": [
                {
                    "goal_id": goal_id,
                    "stage": "maintain",
                    "priority": 900,
                    "requirements": [
                        {
                            "card_uid": RAGING_BOLT,
                            "ready_target_count": 2,
                            "energy_required": 2,
                            "energy_requirements": [
                                {"energy_uid": FIGHTING_ENERGY, "count": 1},
                                {"energy_uid": LIGHTNING_ENERGY, "count": 1},
                            ],
                            "attack_index": 1,
                            "ability_index": None,
                        },
                        {
                            "card_uid": TEAL_MASK_OGERPON,
                            "ready_target_count": 1,
                            "energy_required": 1,
                            "energy_requirements": [
                                {"energy_uid": GRASS_ENERGY, "count": 1}
                            ],
                            "attack_index": None,
                            "ability_index": 0,
                        },
                    ],
                }
            ],
            "count_rules": [],
            "rules": [
                {
                    "rule_id": "attack-baseline",
                    "goal_id": goal_id,
                    "goal_stage": "execute",
                    "channel": "tactical",
                    "horizon": 0,
                    "confidence_milli": 1000,
                    "base_score": 1000,
                    "when": [_condition("option.kind", "eq", "attack")],
                    "score_terms": [],
                },
                {
                    "rule_id": "attach-baseline",
                    "goal_id": goal_id,
                    "goal_stage": "fund",
                    "channel": "future",
                    "horizon": 1,
                    "confidence_milli": 1000,
                    "base_score": 900,
                    "when": [_condition("option.kind", "eq", "attach_energy")],
                    "score_terms": [],
                },
            ],
            "turn_bonus_contracts": [
                {
                    "contract_id": "public-continuity",
                    "priority": 900,
                    "goal_id": goal_id,
                    "when": [
                        {
                            "fact": "goal.active_ready_count_uid",
                            "op": "gte",
                            "value": 1,
                            "card_uid": RAGING_BOLT,
                        },
                        _condition("goal.board_energy_count", "lt", 5),
                        _condition("goal.discard_energy_count", "gte", 2),
                        _condition("self.bench_open", "eq", True),
                    ],
                    "bonuses": [
                        {
                            "bonus_id": "fund-non-active-bolt",
                            "prompt_kinds": ["main"],
                            "goal_id": goal_id,
                            "when": [
                                {
                                    "fact": "goal.near_ready_count_uid",
                                    "op": "gte",
                                    "value": 2,
                                    "card_uid": RAGING_BOLT,
                                },
                                {
                                    "fact": "goal.ready_count_uid",
                                    "op": "eq",
                                    "value": 0,
                                    "card_uid": TEAL_MASK_OGERPON,
                                },
                            ],
                            "option_when": [
                                _condition("option.kind", "eq", "attach_energy"),
                                _condition("option.target_is_active", "eq", False),
                                _condition("goal.option.funds_target", "eq", True),
                            ],
                            "score_bonus": 500,
                        }
                    ],
                }
            ],
        }
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            adapter,
            allowed_card_uids={
                RAGING_BOLT,
                TEAL_MASK_OGERPON,
                FIGHTING_ENERGY,
                LIGHTNING_ENERGY,
                GRASS_ENERGY,
            },
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        self.assertIsNotNone(compiled.policy)

        frame = _frame()
        frame["prompt_kind"] = "main"
        frame["select_semantics"].update({"min_count": 1, "max_count": 1})
        frame["public_state"]["self"].update(
            {
                "active": [
                    {
                        **_slot(20, RAGING_BOLT, 2, 2),
                        "attached_energy_uids": [FIGHTING_ENERGY, LIGHTNING_ENERGY],
                    }
                ],
                "bench": [
                    {
                        **_slot(21, RAGING_BOLT, 1, 2),
                        "attached_energy_uids": [LIGHTNING_ENERGY],
                    },
                    {
                        **_slot(22, TEAL_MASK_OGERPON, 0, 1),
                        "attached_energy_uids": [],
                    },
                    {
                        **_slot(23, TEAL_MASK_OGERPON, 0, 1),
                        "attached_energy_uids": [],
                    },
                    {
                        **_slot(24, TEAL_MASK_OGERPON, 0, 1),
                        "attached_energy_uids": [],
                    },
                    {
                        **_slot(25, TEAL_MASK_OGERPON, 0, 1),
                        "attached_energy_uids": [],
                    },
                ],
                "hand": [{"serial": 31, "local_card_uid": GRASS_ENERGY}],
                "discard": [
                    {"serial": 32, "local_card_uid": FIGHTING_ENERGY},
                    {"serial": 33, "local_card_uid": LIGHTNING_ENERGY},
                ],
                "turn": {
                    "supporter_available": True,
                    "manual_attachment_available": True,
                    "retreat_available": True,
                },
            }
        )
        attack = {
            **_option(0),
            "kind": "attack",
            "source_uid": RAGING_BOLT,
            "source_serial": 20,
            "attack_index": 1,
            "projected_damage": 140,
        }
        attach_backup = {
            **_option(1, card_uid=FIGHTING_ENERGY),
            "kind": "attach_energy",
            "target_uid": RAGING_BOLT,
            "target_serial": 21,
            "target_attached_energy_count": 1,
            "target_attached_energy_uids": [LIGHTNING_ENERGY],
            "target_minimum_attack_energy_count": 2,
            "target_attack_ready": False,
            "target_energy_debt": 1,
        }
        legal_bench_deploy = {
            **_option(2, card_uid=TEAL_MASK_OGERPON),
            "kind": "play_basic_to_bench",
            "target_uid": TEAL_MASK_OGERPON,
        }
        frame["options"] = [attack, attach_backup, legal_bench_deploy]

        decision = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertEqual([1], decision.selected_indexes)
        self.assertEqual(
            ["fund-non-active-bolt"],
            decision.audit["turn_contract"]["turn_bonus_ids"],
        )

        reordered = copy.deepcopy(frame)
        reordered["source"]["window_id"] = "D" * 64
        reordered["options"].reverse()
        for index, option in enumerate(reordered["options"]):
            option["index"] = index
        rebound = CompetitivePolicyV2Runtime.decide(compiled.policy, reordered)
        self.assertEqual([1], rebound.selected_indexes)

        active_target = copy.deepcopy(frame)
        active_target["source"]["window_id"] = "E" * 64
        active_target["options"][1].update(
            {
                "target_serial": 20,
                "target_attached_energy_count": 2,
                "target_attached_energy_uids": [FIGHTING_ENERGY, LIGHTNING_ENERGY],
                "target_attack_ready": True,
                "target_energy_debt": 0,
            }
        )
        no_active_overfund = CompetitivePolicyV2Runtime.decide(
            compiled.policy, active_target
        )
        self.assertEqual([0], no_active_overfund.selected_indexes)

    def test_soft_turn_bonus_rebinds_and_yields_to_terminal_route(self) -> None:
        goal_id = "ready-two-attackers"
        adapter = _adapter()
        adapter["adapter_version"] = 17
        adapter["rules"].extend(
            [
                {
                    "rule_id": "baseline-morgrem",
                    "goal_id": goal_id,
                    "goal_stage": "fund",
                    "channel": "future",
                    "horizon": 1,
                    "confidence_milli": 1000,
                    "base_score": 2000,
                    "when": [_condition("option.card_uid", "eq", MORGREM)],
                    "score_terms": [],
                },
                {
                    "rule_id": "baseline-grimmsnarl",
                    "goal_id": goal_id,
                    "goal_stage": "fund",
                    "channel": "future",
                    "horizon": 1,
                    "confidence_milli": 1000,
                    "base_score": 1000,
                    "when": [_condition("option.card_uid", "eq", GRIMMSNARL)],
                    "score_terms": [],
                },
            ]
        )
        adapter["turn_bonus_contracts"] = [
            {
                "contract_id": "soft-continuity",
                "priority": 900,
                "goal_id": goal_id,
                "when": [_condition("self.prizes_remaining", "gte", 3)],
                "bonuses": [
                    {
                        "bonus_id": "build-owner",
                        "prompt_kinds": ["main"],
                        "goal_id": goal_id,
                        "when": [],
                        "option_when": [
                            _condition("option.card_uid", "eq", GRIMMSNARL)
                        ],
                        "score_bonus": 1500,
                    },
                    {
                        "bonus_id": "defer-bridge",
                        "prompt_kinds": ["main"],
                        "goal_id": goal_id,
                        "when": [],
                        "option_when": [
                            _condition("option.card_uid", "eq", MORGREM)
                        ],
                        "score_bonus": -1000,
                    },
                ],
            }
        ]
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            adapter,
            allowed_card_uids={GRIMMSNARL, MORGREM, DARK_ENERGY},
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        self.assertIsNotNone(compiled.policy)

        frame = _frame()
        frame["prompt_kind"] = "main"
        frame["select_semantics"].update({"min_count": 1, "max_count": 1})
        frame["options"] = [
            {**_option(0, card_uid=MORGREM), "kind": "play_card"},
            {**_option(1, card_uid=GRIMMSNARL), "kind": "play_card"},
        ]
        softened = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertEqual([1], softened.selected_indexes)
        contract = softened.audit["turn_contract"]
        self.assertEqual("soft-continuity", contract["turn_bonus_contract_id"])
        self.assertEqual(["build-owner", "defer-bridge"], contract["turn_bonus_ids"])
        self.assertFalse(contract["terminal"])
        self.assertIsNone(contract["selection_count"])

        reordered = copy.deepcopy(frame)
        reordered["source"]["window_id"] = "C" * 64
        reordered["options"].reverse()
        for index, option in enumerate(reordered["options"]):
            option["index"] = index
        rebound = CompetitivePolicyV2Runtime.decide(compiled.policy, reordered)
        self.assertEqual([0], rebound.selected_indexes)

        terminal_adapter = copy.deepcopy(adapter)
        terminal_adapter["turn_routes"] = [
            {
                "route_id": "terminal-owner",
                "priority": 1000,
                "goal_id": goal_id,
                "owner_goal_id": goal_id,
                "bridge_goal_id": goal_id,
                "pivot_goal_id": goal_id,
                "when": [],
                "steps": [
                    {
                        "step_id": "finish-now",
                        "prompt_kinds": ["main"],
                        "goal_id": goal_id,
                        "when": [],
                        "option_when": [
                            _condition("option.card_uid", "eq", MORGREM)
                        ],
                        "score_bonus": 100000,
                        "selection_count": 1,
                        "terminal": True,
                        "checkpoint": False,
                    }
                ],
            }
        ]
        terminal_compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            terminal_adapter,
            allowed_card_uids={GRIMMSNARL, MORGREM, DARK_ENERGY},
        )
        self.assertTrue(terminal_compiled.accepted, terminal_compiled.error_code)
        terminal = CompetitivePolicyV2Runtime.decide(terminal_compiled.policy, frame)
        self.assertEqual([0], terminal.selected_indexes)
        terminal_contract = terminal.audit["turn_contract"]
        self.assertTrue(terminal_contract["terminal"])
        self.assertNotIn("turn_bonus_contract_id", terminal_contract)
        matched = [
            item["rule_id"]
            for card in terminal.audit["scorecards"]
            for item in card["matched_rules"]
        ]
        self.assertFalse(any(rule_id.startswith("@turn_bonus.") for rule_id in matched))

    def test_public_turn_route_and_typed_recipe_replan_from_each_window(self) -> None:
        goal_id = "bolt-owner"
        adapter = {
            "schema_version": 2,
            "adapter_id": "dev.beralee.turn-route-contract-red",
            "adapter_version": 11,
            "goals": [
                {
                    "goal_id": goal_id,
                    "stage": "execute",
                    "priority": 900,
                    "requirements": [
                        {
                            "card_uid": RAGING_BOLT,
                            "ready_target_count": 1,
                            "energy_required": 2,
                            "energy_requirements": [
                                {"energy_uid": FIGHTING_ENERGY, "count": 1},
                                {"energy_uid": LIGHTNING_ENERGY, "count": 1},
                            ],
                            "attack_index": 1,
                            "ability_index": None,
                        }
                    ],
                }
            ],
            "count_rules": [],
            "rules": [
                {
                    "rule_id": "legacy-prefers-redraw-attack",
                    "goal_id": goal_id,
                    "goal_stage": "execute",
                    "channel": "tactical",
                    "horizon": 0,
                    "confidence_milli": 1000,
                    "base_score": 5000,
                    "when": [
                        _condition("option.kind", "eq", "attack"),
                        _condition("option.attack_index", "eq", 0),
                    ],
                    "score_terms": [],
                }
            ],
            "turn_routes": [
                {
                    "route_id": "bolt-continuity",
                    "priority": 900,
                    "goal_id": goal_id,
                    "owner_goal_id": goal_id,
                    "bridge_goal_id": goal_id,
                    "pivot_goal_id": goal_id,
                    "when": [
                        {
                            "fact": "self.board.count_uid",
                            "op": "gte",
                            "value": 1,
                            "card_uid": RAGING_BOLT,
                        }
                    ],
                    "steps": [
                        {
                            "step_id": "fund-owner",
                            "prompt_kinds": ["main"],
                            "goal_id": goal_id,
                            "when": [
                                _condition("goal.energy_debt", "gt", 0),
                                _condition("turn.manual_attachment_available", "eq", True),
                            ],
                            "option_when": [
                                _condition("goal.option.funds_target", "eq", True)
                            ],
                            "score_bonus": 100000,
                            "selection_count": 1,
                            "terminal": False,
                            "checkpoint": False,
                        },
                        {
                            "step_id": "attack-with-owner",
                            "prompt_kinds": ["main"],
                            "goal_id": goal_id,
                            "when": [_condition("goal.energy_debt", "eq", 0)],
                            "option_when": [
                                _condition("goal.option.executes_requirement", "eq", True)
                            ],
                            "score_bonus": 100000,
                            "selection_count": 1,
                            "terminal": True,
                            "checkpoint": False,
                        },
                    ],
                },
                {
                    "route_id": "bolt-rebuild",
                    "priority": 800,
                    "goal_id": goal_id,
                    "owner_goal_id": goal_id,
                    "bridge_goal_id": goal_id,
                    "pivot_goal_id": goal_id,
                    "when": [
                        {
                            "fact": "self.board.count_uid",
                            "op": "eq",
                            "value": 0,
                            "card_uid": RAGING_BOLT,
                        }
                    ],
                    "steps": [
                        {
                            "step_id": "recover-owner",
                            "prompt_kinds": ["effect_target"],
                            "goal_id": goal_id,
                            "when": [
                                {
                                    "fact": "self.discard.count_uid",
                                    "op": "gte",
                                    "value": 1,
                                    "card_uid": RAGING_BOLT,
                                }
                            ],
                            "option_when": [
                                _condition("option.card_uid", "eq", RAGING_BOLT),
                                _condition("option.source_uid", "eq", NIGHT_STRETCHER),
                            ],
                            "score_bonus": 90000,
                            "selection_count": 1,
                            "terminal": False,
                            "checkpoint": True,
                        }
                    ],
                },
            ],
            "interaction_recipes": [
                {
                    "recipe_id": "night-stretcher-recovers-owner",
                    "priority": 1000,
                    "route_id": "bolt-rebuild",
                    "goal_id": goal_id,
                    "source_uids": [NIGHT_STRETCHER],
                    "when": [
                        {
                            "fact": "self.discard.count_uid",
                            "op": "gte",
                            "value": 1,
                            "card_uid": RAGING_BOLT,
                        }
                    ],
                    "steps": [
                        {
                            "step_id": "recover-owner-target",
                            "prompt_kinds": ["effect_target"],
                            "goal_id": goal_id,
                            "when": [],
                            "option_when": [
                                _condition("option.card_uid", "eq", RAGING_BOLT)
                            ],
                            "score_bonus": 120000,
                            "selection_count": 1,
                            "terminal": False,
                            "checkpoint": True,
                        }
                    ],
                }
            ],
        }
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            adapter,
            allowed_card_uids={
                RAGING_BOLT,
                NIGHT_STRETCHER,
                FIGHTING_ENERGY,
                LIGHTNING_ENERGY,
            },
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        self.assertIsNotNone(compiled.policy)

        frame = _frame()
        frame["prompt_kind"] = "main"
        frame["select_semantics"].update({"min_count": 1, "max_count": 1})
        frame["public_state"]["self"]["turn"] = {
            "supporter_available": True,
            "manual_attachment_available": True,
            "retreat_available": True,
        }
        frame["public_state"]["self"]["active"] = [
            {
                **_slot(20, RAGING_BOLT, 1, 1),
                "attached_energy_uids": [FIGHTING_ENERGY],
            }
        ]
        frame["public_state"]["self"]["bench"] = []
        attach = _option(0, card_uid=LIGHTNING_ENERGY)
        attach.update(
            {
                "kind": "attach_energy",
                "target_uid": RAGING_BOLT,
                "target_serial": 20,
                "target_attached_energy_count": 1,
                "target_attached_energy_uids": [FIGHTING_ENERGY],
                "target_minimum_attack_energy_count": 1,
                "target_attack_ready": True,
                "target_energy_debt": 0,
            }
        )
        redraw = _option(1)
        redraw.update(
            {
                "kind": "attack",
                "source_uid": RAGING_BOLT,
                "source_serial": 20,
                "attack_index": 0,
                "projected_damage": 0,
            }
        )
        frame["options"] = [attach, redraw]
        funded = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertEqual([0], funded.selected_indexes)
        self.assertEqual("bolt-continuity", funded.audit["turn_contract"]["route_id"])
        self.assertEqual("fund-owner", funded.audit["turn_contract"]["first_executable_step_id"])

        vetoed = CompetitivePolicyV2Runtime.decide(
            compiled.policy, frame, base_vetoed_indexes=[0]
        )
        self.assertEqual([1], vetoed.selected_indexes)
        mandatory = CompetitivePolicyV2Runtime.decide(
            compiled.policy, frame, mandatory_indexes=[1]
        )
        self.assertEqual([1], mandatory.selected_indexes)

        ready = copy.deepcopy(frame)
        ready["source"]["window_id"] = "C" * 64
        ready["public_state"]["self"]["turn"]["manual_attachment_available"] = False
        ready["public_state"]["self"]["active"][0].update(
            {
                "attached_energy_count": 2,
                "attached_energy_uids": [FIGHTING_ENERGY, LIGHTNING_ENERGY],
            }
        )
        declared = copy.deepcopy(redraw)
        declared.update({"index": 0, "attack_index": 1, "projected_damage": 210})
        redraw_ready = copy.deepcopy(redraw)
        redraw_ready["index"] = 1
        ready["options"] = [declared, redraw_ready]
        attacked = CompetitivePolicyV2Runtime.decide(compiled.policy, ready)
        self.assertEqual([0], attacked.selected_indexes)
        self.assertEqual(
            "attack-with-owner", attacked.audit["turn_contract"]["first_executable_step_id"]
        )
        self.assertTrue(attacked.audit["turn_contract"]["terminal"])

        reordered = copy.deepcopy(ready)
        reordered["source"]["window_id"] = "D" * 64
        reordered["options"] = [copy.deepcopy(redraw_ready), copy.deepcopy(declared)]
        for index, option in enumerate(reordered["options"]):
            option["index"] = index
        semantic = CompetitivePolicyV2Runtime.decide(compiled.policy, reordered)
        self.assertEqual([1], semantic.selected_indexes)

        recipe_frame = _frame()
        recipe_frame["prompt_kind"] = "effect_target"
        recipe_frame["select_semantics"].update({"min_count": 1, "max_count": 1})
        recipe_frame["public_state"]["self"]["turn"] = {
            "supporter_available": True,
            "manual_attachment_available": True,
            "retreat_available": True,
        }
        recipe_frame["public_state"]["self"]["active"] = []
        recipe_frame["public_state"]["self"]["bench"] = []
        recipe_frame["public_state"]["self"]["discard"] = [
            {"serial": 30, "local_card_uid": RAGING_BOLT}
        ]
        energy = _option(0, card_uid=LIGHTNING_ENERGY)
        energy.update({"kind": "effect_target", "source_uid": NIGHT_STRETCHER})
        bolt = _option(1, card_uid=RAGING_BOLT)
        bolt.update({"kind": "effect_target", "source_uid": NIGHT_STRETCHER})
        recipe_frame["options"] = [energy, bolt]
        recovered = CompetitivePolicyV2Runtime.decide(compiled.policy, recipe_frame)
        self.assertEqual([1], recovered.selected_indexes)
        self.assertEqual(
            "night-stretcher-recovers-owner",
            recovered.audit["turn_contract"]["interaction_recipe_id"],
        )
        self.assertEqual(1, recovered.audit["desired_count"])

        wrong_source = copy.deepcopy(recipe_frame)
        wrong_source["source"]["window_id"] = "E" * 64
        for option in wrong_source["options"]:
            option["source_uid"] = LIGHTNING_ENERGY
        ignored = CompetitivePolicyV2Runtime.decide(compiled.policy, wrong_source)
        self.assertEqual([0], ignored.selected_indexes)
        self.assertIsNone(ignored.audit["turn_contract"]["interaction_recipe_id"])

        unknown_source = copy.deepcopy(adapter)
        unknown_source["interaction_recipes"][0]["source_uids"] = ["CSV0C_999"]
        rejected = CompetitivePolicyV2Compiler.compile_local_uid(
            unknown_source,
            allowed_card_uids={
                RAGING_BOLT,
                NIGHT_STRETCHER,
                FIGHTING_ENERGY,
                LIGHTNING_ENERGY,
            },
        )
        self.assertFalse(rejected.accepted)
        self.assertEqual("invalid_interaction_recipe", rejected.error_code)

    def test_variable_damage_count_reserves_core_when_lethal_is_unavailable(self) -> None:
        adapter = _adapter()
        adapter["adapter_id"] = "dev.beralee.variable-damage-reserve-red"
        adapter["adapter_version"] = 5
        adapter["count_rules"] = [
            {
                "rule_id": "lethal-or-excess-after-core-reserve",
                "priority": 0,
                "goal_id": "ready-two-attackers",
                "mode": "ceil_public_fact_divisor_with_reserve",
                "fixed_count": 2,
                "fact": "opponent.active.remaining_hp",
                "divisor": 70,
                "when": [_condition("prompt_kind", "eq", "assignment_source")],
            }
        ]
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            adapter,
            allowed_card_uids={GRIMMSNARL, MORGREM, DARK_ENERGY},
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        self.assertIsNotNone(compiled.policy)

        frame = _frame()
        frame["select_semantics"].update({"min_count": 0, "max_count": 3})
        frame["public_state"]["opponent"]["active"] = [_slot(90, GRIMMSNARL, 0, 2)]
        frame["public_state"]["opponent"]["active"][0]["remaining_hp"] = 280
        frame["options"] = [_option(index, card_uid=DARK_ENERGY) for index in range(3)]
        nonlethal = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertEqual([0], nonlethal.selected_indexes)
        self.assertEqual(1, nonlethal.audit["desired_count"])

        lethal = copy.deepcopy(frame)
        lethal["source"]["window_id"] = "C" * 64
        lethal["public_state"]["opponent"]["active"][0]["remaining_hp"] = 140
        exact = CompetitivePolicyV2Runtime.decide(compiled.policy, lethal)
        self.assertEqual([0, 1], exact.selected_indexes)
        self.assertEqual(2, exact.audit["desired_count"])

    def test_goal_window_progress_selects_best_current_setup_and_survives_reorder(self) -> None:
        goal_id = "bellowing-thunder-route"
        adapter = {
            "schema_version": 2,
            "adapter_id": "dev.beralee.goal-window-progress-red",
            "adapter_version": 5,
            "goals": [
                {
                    "goal_id": goal_id,
                    "stage": "execute",
                    "priority": 900,
                    "requirements": [
                        {
                            "card_uid": RAGING_BOLT,
                            "ready_target_count": 1,
                            "energy_required": 2,
                            "energy_requirements": [
                                {"energy_uid": FIGHTING_ENERGY, "count": 1},
                                {"energy_uid": LIGHTNING_ENERGY, "count": 1},
                            ],
                            "attack_index": 1,
                            "ability_index": None,
                        }
                    ],
                }
            ],
            "count_rules": [],
            "rules": [
                {
                    "rule_id": "setup.best-current-progress",
                    "goal_id": goal_id,
                    "goal_stage": "fund",
                    "channel": "macro",
                    "horizon": 0,
                    "confidence_milli": 1000,
                    "base_score": 5000,
                    "when": [
                        _condition("goal.window.max_progress", "gte", 1),
                        _condition("goal.option.is_max_progress", "eq", True),
                    ],
                    "score_terms": [],
                },
                {
                    "rule_id": "setup.attack-after-debt",
                    "goal_id": goal_id,
                    "goal_stage": "execute",
                    "channel": "tactical",
                    "horizon": 0,
                    "confidence_milli": 1000,
                    "base_score": 4000,
                    "when": [_condition("option.kind", "eq", "attack")],
                    "score_terms": [],
                },
            ],
        }
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            adapter,
            allowed_card_uids={RAGING_BOLT, FIGHTING_ENERGY, LIGHTNING_ENERGY},
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        self.assertIsNotNone(compiled.policy)

        frame = _frame()
        frame["prompt_kind"] = "main"
        frame["select_semantics"].update({"min_count": 1, "max_count": 1})
        frame["public_state"]["self"]["active"] = [
            {
                **_slot(20, RAGING_BOLT, 1, 1),
                "attached_energy_uids": [FIGHTING_ENERGY],
            }
        ]
        frame["public_state"]["self"]["bench"] = []
        attach = _option(0, card_uid=LIGHTNING_ENERGY)
        attach.update(
            {
                "kind": "attach_energy",
                "target_uid": RAGING_BOLT,
                "target_serial": 20,
                "target_attached_energy_count": 1,
                "target_attached_energy_uids": [FIGHTING_ENERGY],
                "target_minimum_attack_energy_count": 1,
                "target_attack_ready": True,
                "target_energy_debt": 0,
            }
        )
        attack = _option(1)
        attack.update(
            {
                "kind": "attack",
                "source_uid": RAGING_BOLT,
                "source_serial": 20,
                "projected_damage": 0,
                "attack_index": 0,
            }
        )
        end_turn = _option(2)
        end_turn["kind"] = "end_turn"
        frame["options"] = [attach, attack, end_turn]

        current = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertEqual([0], current.selected_indexes)
        attach_scorecard = current.audit["scorecards"][0]
        self.assertIn(
            "setup.best-current-progress",
            [match["rule_id"] for match in attach_scorecard["matched_rules"]],
        )

        reordered = copy.deepcopy(frame)
        reordered["source"]["window_id"] = "D" * 64
        reordered["options"] = [copy.deepcopy(end_turn), copy.deepcopy(attack), copy.deepcopy(attach)]
        for index, option in enumerate(reordered["options"]):
            option["index"] = index
        semantic = CompetitivePolicyV2Runtime.decide(compiled.policy, reordered)
        self.assertEqual([2], semantic.selected_indexes)

    def test_goal_window_setup_progress_precedes_declared_nonterminal_attack(self) -> None:
        goal_id = "two-bolt-continuity"
        adapter = {
            "schema_version": 2,
            "adapter_id": "dev.beralee.goal-window-setup-progress-red",
            "adapter_version": 6,
            "goals": [
                {
                    "goal_id": goal_id,
                    "stage": "maintain",
                    "priority": 900,
                    "requirements": [
                        {
                            "card_uid": RAGING_BOLT,
                            "ready_target_count": 2,
                            "energy_required": 2,
                            "energy_requirements": [
                                {"energy_uid": FIGHTING_ENERGY, "count": 1},
                                {"energy_uid": LIGHTNING_ENERGY, "count": 1},
                            ],
                            "attack_index": 1,
                            "ability_index": None,
                        }
                    ],
                }
            ],
            "count_rules": [],
            "rules": [
                {
                    "rule_id": "continuity.best-current-setup",
                    "goal_id": goal_id,
                    "goal_stage": "fund",
                    "channel": "future",
                    "horizon": 1,
                    "confidence_milli": 1000,
                    "base_score": 5000,
                    "when": [
                        _condition("goal.window.max_setup_progress", "gte", 1),
                        _condition("goal.option.is_max_setup_progress", "eq", True),
                    ],
                    "score_terms": [],
                },
                {
                    "rule_id": "continuity.nonterminal-attack",
                    "goal_id": goal_id,
                    "goal_stage": "execute",
                    "channel": "tactical",
                    "horizon": 0,
                    "confidence_milli": 1000,
                    "base_score": 4000,
                    "when": [
                        _condition("option.kind", "eq", "attack"),
                        _condition("option.projected_knockout", "eq", False),
                    ],
                    "score_terms": [],
                },
            ],
        }
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            adapter,
            allowed_card_uids={RAGING_BOLT, FIGHTING_ENERGY, LIGHTNING_ENERGY},
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        self.assertIsNotNone(compiled.policy)

        frame = _frame()
        frame["prompt_kind"] = "main"
        frame["select_semantics"].update({"min_count": 1, "max_count": 1})
        active = {
            **_slot(20, RAGING_BOLT, 2, 0),
            "attached_energy_uids": [FIGHTING_ENERGY, LIGHTNING_ENERGY],
        }
        bench = {
            **_slot(21, RAGING_BOLT, 1, 1),
            "attached_energy_uids": [FIGHTING_ENERGY],
        }
        frame["public_state"]["self"]["active"] = [active]
        frame["public_state"]["self"]["bench"] = [bench]
        attach = _option(0, card_uid=LIGHTNING_ENERGY)
        attach.update(
            {
                "kind": "attach_energy",
                "target_uid": RAGING_BOLT,
                "target_serial": 21,
                "target_attached_energy_count": 1,
                "target_attached_energy_uids": [FIGHTING_ENERGY],
                "target_minimum_attack_energy_count": 1,
                "target_attack_ready": True,
                "target_energy_debt": 0,
            }
        )
        attack = _option(1)
        attack.update(
            {
                "kind": "attack",
                "source_uid": RAGING_BOLT,
                "source_serial": 20,
                "projected_damage": 70,
                "projected_knockout": False,
                "attack_index": 1,
            }
        )
        frame["options"] = [attach, attack]
        current = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertEqual([0], current.selected_indexes)

        reordered = copy.deepcopy(frame)
        reordered["source"]["window_id"] = "E" * 64
        reordered["options"] = [copy.deepcopy(attack), copy.deepcopy(attach)]
        for index, option in enumerate(reordered["options"]):
            option["index"] = index
        semantic = CompetitivePolicyV2Runtime.decide(compiled.policy, reordered)
        self.assertEqual([1], semantic.selected_indexes)

    def test_typed_source_count_selects_only_available_missing_energy_quota(self) -> None:
        goal_id = "bellowing-thunder-route"
        adapter = {
            "schema_version": 2,
            "adapter_id": "dev.beralee.typed-source-count-red",
            "adapter_version": 4,
            "goals": [
                {
                    "goal_id": goal_id,
                    "stage": "fund",
                    "priority": 900,
                    "requirements": [
                        {
                            "card_uid": RAGING_BOLT,
                            "ready_target_count": 1,
                            "energy_required": 2,
                            "energy_requirements": [
                                {"energy_uid": FIGHTING_ENERGY, "count": 1},
                                {"energy_uid": LIGHTNING_ENERGY, "count": 1},
                            ],
                            "attack_index": 1,
                            "ability_index": None,
                        }
                    ],
                }
            ],
            "count_rules": [
                {
                    "rule_id": "typed-missing-source-count",
                    "priority": 0,
                    "goal_id": goal_id,
                    "mode": "goal_missing_energy_sources",
                    "fixed_count": None,
                    "fact": None,
                    "divisor": None,
                    "when": [_condition("prompt_kind", "eq", "assignment_source")],
                }
            ],
            "rules": [
                {
                    "rule_id": "typed-missing-source",
                    "goal_id": goal_id,
                    "goal_stage": "fund",
                    "channel": "interaction",
                    "horizon": 0,
                    "confidence_milli": 1000,
                    "base_score": 1000,
                    "when": [_condition("goal.option.supplies_missing_energy", "eq", True)],
                    "score_terms": [],
                }
            ],
        }
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            adapter,
            allowed_card_uids={
                RAGING_BOLT,
                FIGHTING_ENERGY,
                LIGHTNING_ENERGY,
                GRASS_ENERGY,
            },
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        self.assertIsNotNone(compiled.policy)

        frame = _frame()
        frame["prompt_kind"] = "assignment_source"
        frame["select_semantics"].update({"min_count": 0, "max_count": 2})
        frame["public_state"]["self"]["active"] = [
            {
                **_slot(20, RAGING_BOLT, 1, 1),
                "attached_energy_uids": [GRASS_ENERGY],
            }
        ]
        frame["public_state"]["self"]["bench"] = []
        frame["options"] = [
            _option(0, card_uid=FIGHTING_ENERGY),
            _option(1, card_uid=FIGHTING_ENERGY),
            _option(2, card_uid=LIGHTNING_ENERGY),
            _option(3, card_uid=GRASS_ENERGY),
        ]
        for option in frame["options"]:
            option["kind"] = "effect_target"

        exact = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertEqual([0, 2], exact.selected_indexes)

        reordered = copy.deepcopy(frame)
        reordered["source"]["window_id"] = "C" * 64
        reordered["options"] = [
            _option(0, card_uid=LIGHTNING_ENERGY),
            _option(1, card_uid=GRASS_ENERGY),
            _option(2, card_uid=FIGHTING_ENERGY),
            _option(3, card_uid=FIGHTING_ENERGY),
        ]
        for option in reordered["options"]:
            option["kind"] = "effect_target"
        semantic = CompetitivePolicyV2Runtime.decide(compiled.policy, reordered)
        self.assertEqual([0, 2], semantic.selected_indexes)

        unavailable = copy.deepcopy(frame)
        unavailable["source"]["window_id"] = "D" * 64
        unavailable["options"] = [_option(0, card_uid=GRASS_ENERGY)]
        unavailable["options"][0]["kind"] = "effect_target"
        no_wrong_type = CompetitivePolicyV2Runtime.decide(compiled.policy, unavailable)
        self.assertEqual([], no_wrong_type.selected_indexes)

    def test_package_builder_accepts_declared_attack_route_contract(self) -> None:
        adapter = _adapter()
        adapter["adapter_version"] = 3
        requirement = adapter["goals"][0]["requirements"][0]
        requirement.update(
            {
                "energy_requirements": [{"energy_uid": DARK_ENERGY, "count": 2}],
                "attack_index": 0,
                "ability_index": None,
            }
        )
        adapter["rules"].append(
            {
                "rule_id": "execute-declared-attack-route",
                "goal_id": "ready-two-attackers",
                "goal_stage": "execute",
                "channel": "tactical",
                "horizon": 0,
                "confidence_milli": 1000,
                "base_score": 5000,
                "when": [_condition("goal.option.executes_requirement", "eq", True)],
                "score_terms": [],
            }
        )
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            package_source = root / "package"
            shutil.copytree(ROOT / "demo/marnie-forge/package", package_source)
            write_json(package_source / "policy/adapter.json", adapter)

            report = build_development_package(package_source, root / "declared-route.ptcgai")

        self.assertEqual("built", report["status"])

    def test_goal_relative_route_facts_use_declared_attack_not_any_legal_attack(self) -> None:
        goal_id = "bellowing-thunder-route"
        adapter = {
            "schema_version": 2,
            "adapter_id": "dev.beralee.route-facts-red",
            "adapter_version": 3,
            "goals": [
                {
                    "goal_id": goal_id,
                    "stage": "execute",
                    "priority": 900,
                    "requirements": [
                        {
                            "card_uid": RAGING_BOLT,
                            "ready_target_count": 1,
                            "energy_required": 2,
                            "energy_requirements": [
                                {"energy_uid": FIGHTING_ENERGY, "count": 1},
                                {"energy_uid": LIGHTNING_ENERGY, "count": 1},
                            ],
                            "attack_index": 1,
                            "ability_index": None,
                        }
                    ],
                }
            ],
            "count_rules": [],
            "rules": [
                {
                    "rule_id": "route.fund-exact-core",
                    "goal_id": goal_id,
                    "goal_stage": "fund",
                    "channel": "macro",
                    "horizon": 0,
                    "confidence_milli": 1000,
                    "base_score": 3000,
                    "when": [_condition("goal.option.funds_target", "eq", True)],
                    "score_terms": [],
                },
                {
                    "rule_id": "route.pivot-exact-ready",
                    "goal_id": goal_id,
                    "goal_stage": "ready",
                    "channel": "macro",
                    "horizon": 0,
                    "confidence_milli": 1000,
                    "base_score": 4000,
                    "when": [_condition("goal.option.pivots_ready_target", "eq", True)],
                    "score_terms": [],
                },
                {
                    "rule_id": "route.execute-declared-attack",
                    "goal_id": goal_id,
                    "goal_stage": "execute",
                    "channel": "tactical",
                    "horizon": 0,
                    "confidence_milli": 1000,
                    "base_score": 5000,
                    "when": [_condition("goal.option.executes_requirement", "eq", True)],
                    "score_terms": [],
                },
            ],
        }
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            adapter,
            allowed_card_uids={
                RAGING_BOLT,
                FAN_ROTOM,
                FIGHTING_ENERGY,
                LIGHTNING_ENERGY,
            },
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        self.assertIsNotNone(compiled.policy)

        frame = _frame()
        frame["prompt_kind"] = "main"
        frame["select_semantics"].update({"min_count": 1, "max_count": 1})
        frame["public_state"]["self"]["active"] = [
            {
                **_slot(20, FAN_ROTOM, 1, 1),
                "attached_energy_uids": [FIGHTING_ENERGY],
            }
        ]
        frame["public_state"]["self"]["bench"] = [
            {
                **_slot(21, RAGING_BOLT, 1, 1),
                "attached_energy_uids": [FIGHTING_ENERGY],
            }
        ]
        attach_fan = _option(0, card_uid=LIGHTNING_ENERGY)
        attach_fan.update(
            {
                "kind": "attach_energy",
                "target_uid": FAN_ROTOM,
                "target_serial": 20,
                "target_attached_energy_count": 1,
                "target_attached_energy_uids": [FIGHTING_ENERGY],
                "target_minimum_attack_energy_count": 1,
                "target_attack_ready": True,
                "target_energy_debt": 0,
            }
        )
        attach_bolt = copy.deepcopy(attach_fan)
        attach_bolt.update(
            {
                "index": 1,
                "target_uid": RAGING_BOLT,
                "target_serial": 21,
            }
        )
        end_turn = _option(2)
        end_turn["kind"] = "end_turn"
        frame["options"] = [attach_fan, attach_bolt, end_turn]

        funded = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)
        self.assertEqual([1], funded.selected_indexes)
        self.assertIn(
            "route.fund-exact-core",
            [
                match["rule_id"]
                for match in funded.audit["scorecards"][1]["matched_rules"]
            ],
        )

        pivot = copy.deepcopy(frame)
        pivot["source"]["window_id"] = "C" * 64
        pivot["prompt_kind"] = "send_out"
        fan_target = copy.deepcopy(attach_fan)
        fan_target.update({"kind": "send_out", "card_uid": None, "index": 0})
        bolt_target = copy.deepcopy(attach_bolt)
        bolt_target.update({"kind": "send_out", "card_uid": None, "index": 1})
        pivot["options"] = [fan_target, bolt_target, copy.deepcopy(end_turn)]
        not_ready = CompetitivePolicyV2Runtime.decide(compiled.policy, pivot)
        self.assertEqual([2], not_ready.selected_indexes)

        pivot["source"]["window_id"] = "D" * 64
        pivot["public_state"]["self"]["bench"][0].update(
            {
                "attached_energy_count": 2,
                "attached_energy_uids": [FIGHTING_ENERGY, LIGHTNING_ENERGY],
                "attack_ready": True,
                "energy_debt": 0,
            }
        )
        pivot["options"][1].update(
            {
                "target_attached_energy_count": 2,
                "target_attached_energy_uids": [FIGHTING_ENERGY, LIGHTNING_ENERGY],
                "target_attack_ready": True,
                "target_energy_debt": 0,
            }
        )
        ready = CompetitivePolicyV2Runtime.decide(compiled.policy, pivot)
        self.assertEqual([1], ready.selected_indexes)

        attack_frame = copy.deepcopy(pivot)
        attack_frame["source"]["window_id"] = "E" * 64
        attack_frame["prompt_kind"] = "main"
        first_attack = _option(0)
        first_attack.update(
            {
                "kind": "attack",
                "source_uid": RAGING_BOLT,
                "source_serial": 21,
                "attack_index": 0,
                "projected_damage": 0,
            }
        )
        declared_attack = copy.deepcopy(first_attack)
        declared_attack.update({"index": 1, "attack_index": 1})
        attack_frame["options"] = [first_attack, declared_attack, copy.deepcopy(end_turn)]
        executed = CompetitivePolicyV2Runtime.decide(compiled.policy, attack_frame)
        self.assertEqual([1], executed.selected_indexes)

    def test_base_tactical_floor_attacks_only_with_strictly_positive_public_damage(self) -> None:
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            _adapter(),
            allowed_card_uids={DARK_ENERGY, GRIMMSNARL, MORGREM},
        )
        self.assertTrue(compiled.accepted, compiled.error_code)
        self.assertIsNotNone(compiled.policy)
        frame = _frame()
        frame["prompt_kind"] = "main"
        frame["select_semantics"]["min_count"] = 1
        frame["select_semantics"]["max_count"] = 1
        frame["options"] = [_option(0), _option(1)]
        frame["options"][0].update({"kind": "attack", "projected_damage": 10})
        frame["options"][1]["kind"] = "end_turn"

        productive = CompetitivePolicyV2Runtime.decide(compiled.policy, frame)

        self.assertTrue(productive.accepted, productive.error_code)
        self.assertEqual([0], productive.selected_indexes)
        self.assertFalse(productive.audit["fallback_used"])
        self.assertIn(
            "@base.positive-damage-attack",
            [rule["rule_id"] for rule in productive.audit["scorecards"][0]["matched_rules"]],
        )

        zero_damage = copy.deepcopy(frame)
        zero_damage["source"]["window_id"] = "C" * 64
        zero_damage["options"][0]["projected_damage"] = 0
        guarded = CompetitivePolicyV2Runtime.decide(compiled.policy, zero_damage)
        self.assertEqual([1], guarded.selected_indexes)
        self.assertTrue(guarded.audit["fallback_used"])

    def test_forge_suite_executes_exact_count_and_reordered_current_indexes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            package_source = root / "package"
            shutil.copytree(ROOT / "demo/marnie-forge/package", package_source)
            write_json(package_source / "policy/adapter.json", _adapter())
            package = root / "competitive.ptcgai"
            build_development_package(package_source, package)

            first = _frame()
            reordered = copy.deepcopy(first)
            reordered["source"]["window_id"] = "C" * 64
            reordered["options"] = [
                _option(0, card_uid=DARK_ENERGY),
                _option(1, card_uid=None),
                _option(2, card_uid=DARK_ENERGY),
                _option(3, card_uid=None),
                _option(4, card_uid=DARK_ENERGY),
            ]
            for scenario_id, frame, expected in (
                ("exact-three", first, [0, 1, 2]),
                ("semantic-reorder", reordered, [0, 2, 4]),
            ):
                write_json(
                    root / f"{scenario_id}.json",
                    {
                        "document_type": "ptcg_strategy_forge_competitive_scenario_v2",
                        "schema_version": 2,
                        "scenario_id": scenario_id,
                        "frame": frame,
                        "base_authority": {
                            "mandatory_indexes": [],
                            "terminal_indexes": [],
                            "base_hard_tiers": [
                                {"index": index, "tier": [0]}
                                for index in range(len(frame["options"]))
                            ],
                            "base_vetoed_indexes": [],
                        },
                        "expected_selected_indexes": expected,
                    },
                )
            write_json(
                root / "scenario-suite.json",
                {
                    "document_type": "ptcg_strategy_forge_scenario_suite_v1",
                    "schema_version": 1,
                    "cases": [
                        {
                            "id": "exact-three",
                            "path": "exact-three.json",
                            "expect": {
                                "status": "passed",
                                "selected_indexes": [0, 1, 2],
                                "matched_rule_id": "select-dark-energy",
                                "selected_source": "adapter_proposal",
                            },
                        },
                        {
                            "id": "semantic-reorder",
                            "path": "semantic-reorder.json",
                            "expect": {
                                "status": "passed",
                                "selected_indexes": [0, 2, 4],
                                "matched_rule_id": "select-dark-energy",
                                "selected_source": "adapter_proposal",
                            },
                        },
                    ],
                },
            )

            report = run_suite(package, root / "scenario-suite.json")

            self.assertEqual("passed", report["status"])
            self.assertEqual((2, 2), (report["passed_count"], report["case_count"]))
            self.assertTrue(all(case["observed"]["claims"]["public_only"] for case in report["cases"]))


if __name__ == "__main__":
    unittest.main()
