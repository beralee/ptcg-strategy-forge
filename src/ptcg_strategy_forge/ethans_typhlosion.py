from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .scenarios import write_json


def _condition(
    fact: str,
    op: str,
    value: object,
    card_uid: str | None = None,
) -> dict[str, object]:
    return {"fact": fact, "op": op, "value": value, "card_uid": card_uid}


def _rule(
    rule_id: str,
    goal_id: str,
    stage: str,
    channel: str,
    score: int,
    *conditions: dict[str, object],
    score_terms: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "rule_id": rule_id,
        "goal_id": goal_id,
        "goal_stage": stage,
        "channel": channel,
        "horizon": 0,
        "confidence_milli": 1000,
        "base_score": score,
        "when": list(conditions),
        "score_terms": list(score_terms or []),
    }


def build_adapter(
    package_id: str,
    package_version: str = "0.1.0",
) -> dict[str, object]:
    """Compile the public current-window portion of the locked 800018880 plan."""

    version_parts = package_version.split(".")
    optimization_round = (
        max(0, int(version_parts[1]) - 1)
        if len(version_parts) == 3
        and version_parts[0] == "0"
        and version_parts[1].isdigit()
        and version_parts[2] == "0"
        else 0
    )

    cyndaquil = "CSV10C_028"
    quilava = "CSV10C_029"
    typhlosion = "CSV10C_030"
    pidgey = "151C_016"
    pidgeotto = "151C_017"
    pidgeot = "CSV4C_101"
    victini = "CSV9C_023"
    fezandipiti = "CSV8C_135"
    adventure = "CSV10C_208"
    arven = "CSV1C_123"
    iono = "CSV3C_123"
    research = "CSV1C_121"
    boss = "CSVH1aC_023"
    ultra_ball = "CSV1C_112"
    poffin = "CSV7C_177"
    super_rod = "CSV1C_109"
    counter_catcher = "CSV6C_114"
    energy_search = "CSVH1C_035"
    redeemable_ticket = "CSV10C_193"
    rare_candy = "CSVH1C_045"
    secret_box = "CSV8C_176"
    tm_evolution = "CSV5C_119"
    luxurious_cape = "CSV4C_117"
    gravity_mountain = "CSV7C_201"
    artazon = "CSV2C_127"
    fire = "CSVE1C_FIR"

    c = _condition
    goals = [
        {
            "goal_id": "typhlosion-prize-route",
            "stage": "execute",
            "priority": 1000,
            "requirements": [{
                "card_uid": typhlosion,
                "ready_target_count": 1,
                "energy_required": 1,
                "energy_requirements": [{"energy_uid": fire, "count": 1}],
                "attack_index": 0,
                "ability_index": None,
            }],
        },
        {
            "goal_id": "backup-typhlosion",
            "stage": "ready",
            "priority": 950,
            "requirements": [{
                "card_uid": typhlosion,
                "ready_target_count": 2,
                "energy_required": 1,
                "energy_requirements": [{"energy_uid": fire, "count": 1}],
                "attack_index": 0,
                "ability_index": None,
            }],
        },
        {
            "goal_id": "pidgeot-engine",
            "stage": "maintain",
            "priority": 900,
            "requirements": [{
                "card_uid": pidgeot,
                "ready_target_count": 1,
                "energy_required": 0,
                "energy_requirements": [],
                "attack_index": None,
                "ability_index": 0,
            }],
        },
        {
            "goal_id": "quilava-adventure-engine",
            "stage": "acquire",
            "priority": 875,
            "requirements": [{
                "card_uid": quilava,
                "ready_target_count": 1,
                "energy_required": 0,
                "energy_requirements": [],
                "attack_index": None,
                "ability_index": 0,
            }],
        },
        {
            "goal_id": "victini-support",
            "stage": "maintain",
            "priority": 700,
            "requirements": [{
                "card_uid": victini,
                "ready_target_count": 1,
                "energy_required": 0,
                "energy_requirements": [],
                "attack_index": None,
                "ability_index": None,
            }],
        },
        {
            "goal_id": "tm-evolution-setup",
            "stage": "deploy",
            "priority": 825,
            "requirements": [{
                "card_uid": quilava,
                "ready_target_count": 1,
                "energy_required": 0,
                "energy_requirements": [],
                "attack_index": None,
                "ability_index": 0,
            }],
        },
        {
            "goal_id": "single-prize-continuity",
            "stage": "recover",
            "priority": 300,
            "requirements": [{
                "card_uid": pidgey,
                "ready_target_count": 1,
                "energy_required": 0,
                "energy_requirements": [],
                "attack_index": 0,
                "ability_index": None,
            }],
        },
    ]
    count_rules = [
        {
            "rule_id": "poffin.exact-two", "priority": 0,
            "goal_id": "tm-evolution-setup", "mode": "fixed",
            "fixed_count": 2, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", poffin)],
        },
        {
            "rule_id": "tm-evolution.exact-two", "priority": 1,
            "goal_id": "tm-evolution-setup", "mode": "fixed",
            "fixed_count": 2, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", tm_evolution)],
        },
        {
            "rule_id": "ethans-adventure.up-to-three", "priority": 2,
            "goal_id": "typhlosion-prize-route", "mode": "fixed",
            "fixed_count": 3, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", adventure)],
        },
        {
            "rule_id": "super-rod.up-to-three", "priority": 3,
            "goal_id": "backup-typhlosion", "mode": "fixed",
            "fixed_count": 3, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "recovery"), c("window.source_uid", "eq", super_rod)],
        },
        {
            "rule_id": "single-search", "priority": 20,
            "goal_id": "typhlosion-prize-route", "mode": "fixed",
            "fixed_count": 1, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "search")],
        },
        {
            "rule_id": "single-target", "priority": 21,
            "goal_id": "typhlosion-prize-route", "mode": "fixed",
            "fixed_count": 1, "fact": None, "divisor": None,
            "when": [c("prompt_kind", "eq", "assignment_target")],
        },
    ]

    rules: list[dict[str, object]] = [
        _rule("setup.active-pidgey", "single-prize-continuity", "deploy", "macro", 21000,
              c("prompt_kind", "eq", "setup_active"), c("option.card_uid", "eq", pidgey)),
        _rule("setup.active-cyndaquil", "quilava-adventure-engine", "deploy", "future", 20000,
              c("prompt_kind", "eq", "setup_active"), c("option.card_uid", "eq", cyndaquil)),
        _rule("setup.active-victini", "victini-support", "maintain", "future", 15000,
              c("prompt_kind", "eq", "setup_active"), c("option.card_uid", "eq", victini)),
        _rule("setup.bench-cyndaquil-first", "backup-typhlosion", "deploy", "macro", 25000,
              c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", cyndaquil),
              c("self.board.count_uid", "lt", 1, cyndaquil)),
        _rule("setup.bench-pidgey-first", "pidgeot-engine", "deploy", "future", 24000,
              c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", pidgey),
              c("self.board.count_uid", "lt", 1, pidgey)),
        _rule("setup.bench-victini", "victini-support", "maintain", "future", 18500,
              c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", victini),
              c("self.board.count_uid", "lt", 1, victini)),
        _rule("setup.bench-second-cyndaquil", "backup-typhlosion", "deploy", "future", 18000,
              c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", cyndaquil),
              c("self.board.count_uid", "eq", 1, cyndaquil)),
        _rule("setup.defer-fezandipiti", "single-prize-continuity", "maintain", "uncertainty", -16000,
              c("prompt_kind", "eq", "setup_bench"), c("option.card_uid", "eq", fezandipiti)),
        _rule("main.poffin", "tm-evolution-setup", "acquire", "macro", 26000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
              c("option.card_uid", "eq", poffin), c("self.bench_space", "gte", 2)),
        _rule("main.arven-development", "tm-evolution-setup", "acquire", "macro", 25500,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
              c("option.card_uid", "eq", arven), c("turn.supporter_available", "eq", True),
              c("self.deck_count", "gt", 6)),
        _rule("main.ultra-ball", "backup-typhlosion", "acquire", "macro", 20500,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", ultra_ball),
              c("self.hand_count", "gte", 3)),
        _rule("main.energy-search", "typhlosion-prize-route", "fund", "macro", 17000,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", energy_search),
              c("goal.energy_debt", "gt", 0)),
        _rule("main.secret-box", "tm-evolution-setup", "acquire", "future", 13500,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", secret_box),
              c("self.hand_count", "gte", 4)),
        _rule("main.artazon-development", "backup-typhlosion", "acquire", "future", 16500,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", artazon),
              c("self.bench_open", "eq", True)),
        _rule("main.artazon-use", "backup-typhlosion", "deploy", "macro", 23000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "use_stadium"),
              c("option.source_uid", "eq", artazon), c("self.bench_open", "eq", True)),
        _rule("main.bench-cyndaquil", "backup-typhlosion", "deploy", "macro", 25000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
              c("option.card_uid", "eq", cyndaquil), c("self.board.count_uid", "lt", 2, cyndaquil)),
        _rule("main.bench-pidgey", "pidgeot-engine", "deploy", "future", 23500,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
              c("option.card_uid", "eq", pidgey), c("self.board.count_uid", "lt", 1, pidgey)),
        _rule("main.bench-victini", "victini-support", "maintain", "future", 19000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
              c("option.card_uid", "eq", victini), c("self.board.count_uid", "lt", 1, victini)),
        _rule("main.bench-fezandipiti-after-ko", "single-prize-continuity", "recover", "future", 15000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_basic_to_bench"),
              c("option.card_uid", "eq", fezandipiti), c("self.prizes_remaining", "lte", 4)),
        _rule("main.evolve-quilava", "quilava-adventure-engine", "deploy", "macro", 32000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "evolve"),
              c("option.card_uid", "eq", quilava), c("option.target_uid", "eq", cyndaquil)),
        _rule("main.evolve-typhlosion", "typhlosion-prize-route", "deploy", "macro", 35000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "evolve"),
              c("option.card_uid", "eq", typhlosion)),
        _rule("main.evolve-pidgeotto", "pidgeot-engine", "deploy", "future", 24500,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "evolve"),
              c("option.card_uid", "eq", pidgeotto)),
        _rule("main.evolve-pidgeot", "pidgeot-engine", "deploy", "macro", 34000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "evolve"),
              c("option.card_uid", "eq", pidgeot)),
        _rule("main.rare-candy-typhlosion", "typhlosion-prize-route", "deploy", "macro", 33000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
              c("option.card_uid", "eq", rare_candy), c("self.hand.count_uid", "gt", 0, typhlosion)),
        _rule("main.rare-candy-pidgeot", "pidgeot-engine", "deploy", "future", 30000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
              c("option.card_uid", "eq", rare_candy), c("self.hand.count_uid", "gt", 0, pidgeot)),
        _rule("main.tm-evolution", "tm-evolution-setup", "deploy", "future", 22000,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", tm_evolution),
              c("self.bench_count", "gte", 2)),
        _rule("main.tm-evolution-energy-first", "tm-evolution-setup", "fund", "macro", 29000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
              c("option.card_uid", "eq", fire), c("option.target_is_active", "eq", True),
              c("self.hand.count_uid", "gt", 0, tm_evolution)),
        _rule("main.stop-low-deck-information", "typhlosion-prize-route", "maintain", "uncertainty", -50000,
              c("prompt_kind", "eq", "main"), c("self.deck_count", "lte", 6),
              c("option.card_uid", "eq", research)),
        _rule("main.stop-information-after-ko", "typhlosion-prize-route", "maintain", "uncertainty", -55000,
              c("prompt_kind", "eq", "main"), c("goal.active_ready_count", "gte", 1),
              c("option.kind", "eq", "use_ability"), c("option.source_uid", "eq", pidgeot)),
        _rule("main.iono-late-prize-lock", "typhlosion-prize-route", "recover", "tactical", 16000,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", iono),
              c("opponent.prizes_remaining", "lte", 2), c("self.deck_count", "gt", 6)),
        _rule("main.research-development", "backup-typhlosion", "recover", "macro", 12000,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", research),
              c("self.deck_count", "gt", 8), c("goal.ready_count", "eq", 0)),
    ]

    for rule_id, uid, score, extra in (
        ("search.poffin-cyndaquil-first", cyndaquil, 35000, c("self.board.count_uid", "lt", 1, cyndaquil)),
        ("search.poffin-pidgey-first", pidgey, 34000, c("self.board.count_uid", "lt", 1, pidgey)),
        ("search.poffin-second-cyndaquil", cyndaquil, 30000, c("self.board.count_uid", "eq", 1, cyndaquil)),
        ("search.poffin-victini", victini, 28000, c("self.board.count_uid", "lt", 1, victini)),
    ):
        rules.append(_rule(rule_id, "tm-evolution-setup", "acquire", "interaction", score,
                           c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", poffin),
                           c("option.card_uid", "eq", uid), extra))

    for rule_id, uid, score, goal in (
        ("search.arven-poffin-core", poffin, 40000, "tm-evolution-setup"),
        ("search.arven-ultra-ball-core", ultra_ball, 30000, "backup-typhlosion"),
        ("search.arven-energy-search-core", energy_search, 28000, "typhlosion-prize-route"),
        ("search.arven-tm-evolution-core", tm_evolution, 40000, "tm-evolution-setup"),
        ("search.arven-rare-candy-core", rare_candy, 36000, "typhlosion-prize-route"),
        ("search.arven-luxurious-cape", luxurious_cape, 22000, "single-prize-continuity"),
    ):
        rules.append(_rule(rule_id, goal, "acquire", "interaction", score,
                           c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", arven),
                           c("option.card_uid", "eq", uid)))

    for rule_id, uid, score, goal in (
        ("search.ultra-ball-typhlosion", typhlosion, 39000, "typhlosion-prize-route"),
        ("search.ultra-ball-pidgeot", pidgeot, 37000, "pidgeot-engine"),
        ("search.ultra-ball-quilava", quilava, 35000, "quilava-adventure-engine"),
        ("search.ultra-ball-pidgeotto", pidgeotto, 30000, "pidgeot-engine"),
    ):
        rules.append(_rule(rule_id, goal, "acquire", "interaction", score,
                           c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", ultra_ball),
                           c("option.card_uid", "eq", uid)))

    rules.extend([
        _rule("quilava.journey-bond", "quilava-adventure-engine", "acquire", "future", 38000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "use_ability"),
              c("option.source_uid", "eq", quilava), c("self.deck_count", "gt", 4)),
        _rule("search.journey-bond-adventure", "quilava-adventure-engine", "acquire", "interaction", 45000,
              c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", quilava),
              c("option.card_uid", "eq", adventure)),
        _rule("pidgeot.quick-search", "pidgeot-engine", "acquire", "future", 30000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "use_ability"),
              c("option.source_uid", "eq", pidgeot), c("self.deck_count", "gt", 4)),
        _rule("search.pidgeot-adventure", "typhlosion-prize-route", "acquire", "interaction", 43000,
              c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", pidgeot),
              c("option.card_uid", "eq", adventure), c("self.discard.count_uid", "lt", 3, adventure)),
        _rule("search.pidgeot-rare-candy", "typhlosion-prize-route", "acquire", "interaction", 41000,
              c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", pidgeot),
              c("option.card_uid", "eq", rare_candy)),
        _rule("search.pidgeot-typhlosion", "typhlosion-prize-route", "acquire", "interaction", 40000,
              c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", pidgeot),
              c("option.card_uid", "eq", typhlosion)),
        _rule("fezandipiti.flip", "backup-typhlosion", "recover", "future", 15500,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "use_ability"),
              c("option.source_uid", "eq", fezandipiti), c("self.deck_count", "gt", 6)),
        _rule("main.ethans-adventure", "typhlosion-prize-route", "acquire", "macro", 31000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "play_trainer"),
              c("option.card_uid", "eq", adventure), c("turn.supporter_available", "eq", True)),
    ])

    for rule_id, uid, score, goal in (
        ("search.adventure.typhlosion-first", typhlosion, 46000, "typhlosion-prize-route"),
        ("search.adventure.quilava-line", quilava, 42000, "quilava-adventure-engine"),
        ("search.adventure.cyndaquil-line", cyndaquil, 39000, "backup-typhlosion"),
        ("search.adventure.fire-energy", fire, 44000, "typhlosion-prize-route"),
    ):
        rules.append(_rule(rule_id, goal, "acquire", "interaction", score,
                           c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", adventure),
                           c("option.card_uid", "eq", uid)))

    rules.extend([
        _rule("search.tm-evolution-quilava", "quilava-adventure-engine", "deploy", "interaction", 45000,
              c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", tm_evolution),
              c("option.card_uid", "eq", quilava)),
        _rule("search.tm-evolution-pidgeotto", "pidgeot-engine", "deploy", "interaction", 44000,
              c("prompt_kind", "eq", "search"), c("window.source_uid", "eq", tm_evolution),
              c("option.card_uid", "eq", pidgeotto)),
        _rule("attach.active-typhlosion-debt", "typhlosion-prize-route", "fund", "tactical", 42000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
              c("option.card_uid", "eq", fire), c("option.target_uid", "eq", typhlosion),
              c("option.target_is_active", "eq", True), c("option.target_energy_debt", "gt", 0)),
        _rule("attach.backup-typhlosion-debt", "backup-typhlosion", "fund", "future", 30000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
              c("option.card_uid", "eq", fire), c("option.target_uid", "eq", typhlosion),
              c("option.target_energy_debt", "gt", 0)),
        _rule("attach.tm-evolution-active", "tm-evolution-setup", "fund", "macro", 33000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
              c("option.card_uid", "eq", fire), c("option.target_is_active", "eq", True),
              c("self.hand.count_uid", "gt", 0, tm_evolution)),
        _rule("attach.victini-emergency", "victini-support", "fund", "future", 11000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
              c("option.card_uid", "eq", fire), c("option.target_uid", "eq", victini),
              c("goal.ready_count", "eq", 0)),
        _rule("attach.no-overfund-ready", "backup-typhlosion", "maintain", "uncertainty", -40000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
              c("option.target_attack_ready", "eq", True)),
        _rule("attack.partner-blast-ko", "typhlosion-prize-route", "execute", "tactical", 60000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
              c("option.source_uid", "eq", typhlosion), c("option.attack_index", "eq", 0),
              c("option.projected_knockout", "eq", True)),
        _rule("attack.partner-blast-pressure", "typhlosion-prize-route", "execute", "tactical", 25000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
              c("option.source_uid", "eq", typhlosion), c("option.attack_index", "eq", 0)),
        _rule("attack.steam-artillery-ko", "typhlosion-prize-route", "execute", "tactical", 56000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
              c("option.source_uid", "eq", typhlosion), c("option.attack_index", "eq", 1),
              c("option.projected_knockout", "eq", True)),
        _rule("attack.tm-evolution-develop", "tm-evolution-setup", "deploy", "macro", 52000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
              c("option.source_uid", "eq", tm_evolution), c("goal.deployed_count", "lt", 2)),
        _rule("attack.pidgey-call-for-family", "tm-evolution-setup", "deploy", "future", 17000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
              c("option.source_uid", "eq", pidgey), c("self.bench_space", "gte", 2)),
        _rule("attack.victini-pressure", "victini-support", "execute", "future", 9000,
              c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attack"),
              c("option.source_uid", "eq", victini)),
        _rule("main.boss-with-active-attacker", "typhlosion-prize-route", "execute", "tactical", 23000,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", boss),
              c("goal.active_ready_count", "gte", 1)),
        _rule("main.counter-catcher-window", "typhlosion-prize-route", "execute", "tactical", 24000,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", counter_catcher),
              c("goal.active_ready_count", "gte", 1)),
        _rule("gust.target-two-prize", "typhlosion-prize-route", "execute", "interaction", 36000,
              c("prompt_kind", "eq", "assignment_target"), c("option.target_prize_value", "eq", 2)),
        _rule("handoff.ready-typhlosion", "typhlosion-prize-route", "ready", "tactical", 40000,
              c("prompt_kind", "eq", "send_out"), c("option.target_uid", "eq", typhlosion),
              c("option.target_attack_ready", "eq", True)),
        _rule("handoff.near-ready-typhlosion", "backup-typhlosion", "ready", "future", 26000,
              c("prompt_kind", "eq", "send_out"), c("option.target_uid", "eq", typhlosion),
              c("option.target_energy_debt", "eq", 1)),
        _rule("handoff.pidgey-single-prize-bridge", "single-prize-continuity", "recover", "future", 23000,
              c("prompt_kind", "eq", "send_out"), c("option.target_uid", "eq", pidgey),
              c("opponent.prizes_remaining", "lte", 2)),
        _rule("main.super-rod-continuity", "backup-typhlosion", "recover", "future", 15000,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", super_rod),
              c("self.deck_count", "gt", 4)),
        _rule("recover.typhlosion", "backup-typhlosion", "recover", "interaction", 38000,
              c("prompt_kind", "eq", "recovery"), c("window.source_uid", "eq", super_rod),
              c("option.card_uid", "eq", typhlosion)),
        _rule("recover.fire-energy", "backup-typhlosion", "recover", "interaction", 34000,
              c("prompt_kind", "eq", "recovery"), c("window.source_uid", "eq", super_rod),
              c("option.card_uid", "eq", fire)),
        _rule("main.gravity-mountain", "typhlosion-prize-route", "execute", "tactical", 17500,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", gravity_mountain),
              c("opponent.active.prize_value", "eq", 2)),
        _rule("main.luxurious-cape", "single-prize-continuity", "maintain", "future", 13000,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", luxurious_cape)),
        _rule("main.redeemable-ticket", "backup-typhlosion", "recover", "future", 5000,
              c("prompt_kind", "eq", "main"), c("option.card_uid", "eq", redeemable_ticket),
              c("self.prizes_remaining", "gte", 4)),
    ])

    if optimization_round >= 1:
        rules.append(_rule(
            "pivot.ready-typhlosion-from-victini",
            "typhlosion-prize-route",
            "execute",
            "tactical",
            65000,
            c("prompt_kind", "eq", "main"),
            c("option.kind", "eq", "retreat"),
            c("option.target_uid", "eq", typhlosion),
            c("option.target_attack_ready", "eq", True),
        ))
    if optimization_round >= 2:
        rules.extend([
            _rule(
                "attach.active-quilava-debt", "quilava-adventure-engine", "fund",
                "tactical", 43000,
                c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                c("option.card_uid", "eq", fire), c("option.target_uid", "eq", quilava),
                c("option.target_is_active", "eq", True),
                c("option.target_energy_debt", "gt", 0),
            ),
            _rule(
                "attach.active-cyndaquil-debt", "backup-typhlosion", "fund",
                "tactical", 42000,
                c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                c("option.card_uid", "eq", fire), c("option.target_uid", "eq", cyndaquil),
                c("option.target_is_active", "eq", True),
                c("option.target_energy_debt", "gt", 0),
            ),
        ])
    if optimization_round >= 3:
        rules.append(_rule(
            "search.adventure.cyndaquil-missing-root",
            "backup-typhlosion",
            "acquire",
            "interaction",
            55000,
            c("prompt_kind", "eq", "search"),
            c("window.source_uid", "eq", adventure),
            c("option.card_uid", "eq", cyndaquil),
            c("self.board.count_uid", "lt", 1, cyndaquil),
            c("self.board.count_uid", "lt", 1, quilava),
            c("self.board.count_uid", "lt", 1, typhlosion),
        ))
    if optimization_round >= 4:
        rules.append(_rule(
            "search.pidgeot-fourth-adventure",
            "typhlosion-prize-route",
            "acquire",
            "interaction",
            50000,
            c("prompt_kind", "eq", "search"),
            c("window.source_uid", "eq", pidgeot),
            c("option.card_uid", "eq", adventure),
            c("self.discard.count_uid", "eq", 3, adventure),
        ))
    if optimization_round >= 5:
        rules.append(_rule(
            "search.artazon-cyndaquil-missing-root",
            "backup-typhlosion",
            "acquire",
            "interaction",
            52000,
            c("prompt_kind", "eq", "search"),
            c("window.source_uid", "eq", artazon),
            c("option.card_uid", "eq", cyndaquil),
            c("self.board.count_uid", "lt", 1, cyndaquil),
            c("self.board.count_uid", "lt", 1, quilava),
            c("self.board.count_uid", "lt", 1, typhlosion),
        ))
    if optimization_round >= 6:
        rules.extend([
            _rule(
                "attach.benched-quilava-debt", "backup-typhlosion", "fund", "future", 37000,
                c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                c("option.card_uid", "eq", fire), c("option.target_uid", "eq", quilava),
                c("option.target_is_active", "eq", False),
                c("option.target_energy_debt", "gt", 0),
            ),
            _rule(
                "attach.benched-cyndaquil-debt", "backup-typhlosion", "fund", "future", 35000,
                c("prompt_kind", "eq", "main"), c("option.kind", "eq", "attach_energy"),
                c("option.card_uid", "eq", fire), c("option.target_uid", "eq", cyndaquil),
                c("option.target_is_active", "eq", False),
                c("option.target_energy_debt", "gt", 0),
            ),
        ])
    if optimization_round == 7:
        rules.append(_rule(
            "pivot.ready-quilava-from-nonline-active",
            "quilava-adventure-engine",
            "execute",
            "tactical",
            48000,
            c("prompt_kind", "eq", "main"),
            c("option.kind", "eq", "retreat"),
            c("option.target_uid", "eq", quilava),
            c("option.target_attack_ready", "eq", True),
            c("self.active.count_uid", "eq", 0, quilava),
            c("self.active.count_uid", "eq", 0, typhlosion),
        ))
    if optimization_round == 8:
        rules.append(_rule(
            "search.ultra-ball-quilava-missing-bridge",
            "quilava-adventure-engine",
            "acquire",
            "interaction",
            56000,
            c("prompt_kind", "eq", "search"),
            c("window.source_uid", "eq", ultra_ball),
            c("option.card_uid", "eq", quilava),
            c("self.board.count_uid", "gt", 0, cyndaquil),
            c("self.board.count_uid", "eq", 0, quilava),
        ))
    if optimization_round == 9:
        rules.append(_rule(
            "search.ultra-ball-quilava-missing-hand-bridge",
            "quilava-adventure-engine",
            "acquire",
            "interaction",
            56000,
            c("prompt_kind", "eq", "search"),
            c("window.source_uid", "eq", ultra_ball),
            c("option.card_uid", "eq", quilava),
            c("self.board.count_uid", "gt", 0, cyndaquil),
            c("self.board.count_uid", "eq", 0, quilava),
            c("self.hand.count_uid", "eq", 0, quilava),
        ))
    if optimization_round >= 10:
        rules.append(_rule(
            "evolve.rare-candy-typhlosion-first",
            "typhlosion-prize-route",
            "deploy",
            "interaction",
            65000,
            c("prompt_kind", "eq", "evolve"),
            c("window.source_uid", "eq", rare_candy),
            c("option.card_uid", "eq", typhlosion),
            c("option.target_uid", "eq", cyndaquil),
        ))

    return {
        "schema_version": 2,
        "adapter_id": package_id,
        "adapter_version": 2 + optimization_round,
        "goals": goals,
        "count_rules": count_rules,
        "rules": rules,
        "turn_routes": [],
        "route_candidates": [],
        "interaction_recipes": [],
        "turn_bonus_contracts": [],
    }


def _option(index: int, kind: str, **values: object) -> dict[str, object]:
    from .reviewed_decks import _competitive_option

    return _competitive_option(index, kind, **values)


def _slot(
    entity_serial: int,
    card_serial: int,
    uid: str,
    *,
    remaining_hp: int,
    max_hp: int,
    prize_value: int,
    energy_count: int = 0,
    minimum_attack_energy_count: int = 0,
    energy_uid: str = "CSVE1C_FIR",
) -> dict[str, object]:
    return {
        "serial": card_serial,
        "entity_serial": entity_serial,
        "local_card_uid": uid,
        "remaining_hp": remaining_hp,
        "max_hp": max_hp,
        "damage_counters": max(0, (max_hp - remaining_hp) // 10),
        "prize_value": prize_value,
        "attached_energy_count": energy_count,
        "attached_energy_uids": [energy_uid] * energy_count,
        "attached_tool_uid": None,
        "pokemon_stack_uids": [uid],
        "minimum_attack_energy_count": minimum_attack_energy_count,
        "attack_ready": energy_count >= minimum_attack_energy_count,
        "energy_debt": max(0, minimum_attack_energy_count - energy_count),
    }


def _frame(prompt_kind: str = "main") -> dict[str, object]:
    return {
        "schema_version": 2,
        "profile_id": "ptcgdap-competitive-public-frame-v2",
        "sequence": 1,
        "seat": 0,
        "prompt_kind": prompt_kind,
        "source": {"public_observation_hash": "A" * 64, "window_id": "B" * 64},
        "public_state": {
            "turn_number": 5,
            "phase": "MAIN",
            "self": {
                "hand": [],
                "active": [_slot(100, 101, "CSV10C_030", remaining_hp=170, max_hp=170,
                                 prize_value=1, energy_count=1, minimum_attack_energy_count=1)],
                "bench": [
                    _slot(110, 111, "CSV10C_029", remaining_hp=100, max_hp=100, prize_value=1),
                    _slot(120, 121, "CSV4C_101", remaining_hp=280, max_hp=280, prize_value=2),
                ],
                "discard": [{"serial": 201, "local_card_uid": "CSV10C_208"}],
                "deck_count": 30,
                "prizes_remaining": 4,
                "turn": {"supporter_available": True, "manual_attachment_available": True,
                         "retreat_available": True},
                "bench_capacity": 5,
            },
            "opponent": {
                "hand_count": 5,
                "active": [_slot(900, 901, "CSV10C_148", remaining_hp=160, max_hp=320,
                                 prize_value=2, energy_count=2, minimum_attack_energy_count=2,
                                 energy_uid="CSVE1C_DAR")],
                "bench": [_slot(910, 911, "CSV7C_059", remaining_hp=140, max_hp=140,
                                prize_value=1)],
                "discard": [],
                "deck_count": 27,
                "prizes_remaining": 4,
            },
        },
        "select_semantics": {
            "min_count": 1, "max_count": 1, "select_type_raw": 0, "select_context_raw": 0,
        },
        "options": [],
    }


def generate_scenarios(workspace: Path) -> dict[str, object]:
    scenario_root = workspace / "scenarios"
    cases: list[dict[str, object]] = []

    def add(
        scenario_id: str,
        frame: dict[str, Any],
        expected: list[int],
        *,
        matched_rule_id: str = "",
        selected_source: str | None = None,
        mandatory: list[int] | None = None,
        terminal: list[int] | None = None,
        tiers: list[dict[str, object]] | None = None,
        vetoed: list[int] | None = None,
        error_code: str = "",
    ) -> None:
        sequence = len(cases) + 1
        frame["sequence"] = sequence
        frame["source"]["window_id"] = f"{sequence:064X}"
        path = f"{sequence:02d}-{scenario_id}.json"
        write_json(scenario_root / path, {
            "document_type": "ptcg_strategy_forge_competitive_scenario_v2",
            "schema_version": 2,
            "scenario_id": scenario_id,
            "frame": frame,
            "base_authority": {
                "mandatory_indexes": list(mandatory or []),
                "terminal_indexes": list(terminal or []),
                "base_hard_tiers": list(
                    tiers or [{"index": index, "tier": [0]} for index in range(len(frame["options"]))]
                ),
                "base_vetoed_indexes": list(vetoed or []),
            },
            "expected_selected_indexes": expected,
        })
        if error_code:
            expect: dict[str, object] = {"status": "error", "error_code": error_code}
        else:
            expect = {
                "status": "passed",
                "selected_indexes": expected,
                "selected_source": selected_source or (
                    "terminal" if terminal else "mandatory" if mandatory else "adapter_proposal"
                ),
            }
            if matched_rule_id:
                expect["matched_rule_id"] = matched_rule_id
        cases.append({"id": scenario_id, "path": f"scenarios/{path}", "expect": expect})

    poffin = _frame("search")
    poffin["select_semantics"].update({"min_count": 0, "max_count": 2})
    poffin["options"] = [
        _option(0, "search", card_uid="CSV10C_028", source_uid="CSV7C_177"),
        _option(1, "search", card_uid="151C_016", source_uid="CSV7C_177"),
        _option(2, "search", card_uid="CSV9C_023", source_uid="CSV7C_177"),
    ]
    add("poffin-cyndaquil-pidgey", poffin, [0, 1], matched_rule_id="search.poffin-cyndaquil-first")
    poffin_reordered = copy.deepcopy(poffin)
    poffin_reordered["options"] = [
        copy.deepcopy(poffin["options"][1]),
        copy.deepcopy(poffin["options"][2]),
        copy.deepcopy(poffin["options"][0]),
    ]
    for index, option in enumerate(poffin_reordered["options"]):
        option["index"] = index
    add("poffin-cyndaquil-pidgey-reordered", poffin_reordered, [2, 0],
        matched_rule_id="search.poffin-cyndaquil-first")

    tm = _frame("search")
    tm["select_semantics"].update({"min_count": 0, "max_count": 2})
    tm["public_state"]["self"]["active"] = [_slot(
        100, 101, "CSV9C_023", remaining_hp=70, max_hp=70, prize_value=1,
        energy_count=1, minimum_attack_energy_count=2,
    )]
    tm["public_state"]["self"]["bench"] = [
        _slot(110, 111, "CSV10C_028", remaining_hp=70, max_hp=70, prize_value=1),
        _slot(120, 121, "151C_016", remaining_hp=50, max_hp=50, prize_value=1),
    ]
    tm["options"] = [
        _option(0, "search", card_uid="CSV10C_029", source_uid="CSV5C_119"),
        _option(1, "search", card_uid="151C_017", source_uid="CSV5C_119"),
    ]
    add("tm-evolution-two-roots", tm, [0, 1], matched_rule_id="search.tm-evolution-quilava")

    ability = _frame()
    ability["options"] = [
        _option(0, "use_ability", source_uid="CSV10C_029", ability_index=0),
        _option(1, "end_turn"),
    ]
    add("journey-bond-searches-adventure", ability, [0], matched_rule_id="quilava.journey-bond")
    ability_reordered = copy.deepcopy(ability)
    ability_reordered["options"] = [copy.deepcopy(ability["options"][1]), copy.deepcopy(ability["options"][0])]
    for index, option in enumerate(ability_reordered["options"]):
        option["index"] = index
    add("journey-bond-searches-adventure-reordered", ability_reordered, [1],
        matched_rule_id="quilava.journey-bond")

    journey_search = _frame("search")
    journey_search["options"] = [
        _option(0, "search", card_uid="CSV1C_121", source_uid="CSV10C_029"),
        _option(1, "search", card_uid="CSV10C_208", source_uid="CSV10C_029"),
    ]
    add("journey-bond-binds-adventure", journey_search, [1],
        matched_rule_id="search.journey-bond-adventure")

    adventure = _frame("search")
    adventure["select_semantics"].update({"min_count": 0, "max_count": 3})
    adventure["options"] = [
        _option(0, "search", card_uid="CSV10C_030", source_uid="CSV10C_208"),
        _option(1, "search", card_uid="CSVE1C_FIR", source_uid="CSV10C_208"),
        _option(2, "search", card_uid="CSV10C_029", source_uid="CSV10C_208"),
        _option(3, "search", card_uid="CSV10C_028", source_uid="CSV10C_208"),
    ]
    add("adventure-gets-typhlosion-and-fire", adventure, [0, 1, 2],
        matched_rule_id="search.adventure.typhlosion-first")

    attack = _frame()
    attack["options"] = [
        _option(0, "attack", source_uid="CSV10C_030", attack_index=0,
                projected_damage=160, projected_knockout=True),
        _option(1, "end_turn"),
    ]
    add("partner-blast-public-ko", attack, [0], matched_rule_id="attack.partner-blast-ko")
    attack_reordered = copy.deepcopy(attack)
    attack_reordered["options"] = [copy.deepcopy(attack["options"][1]), copy.deepcopy(attack["options"][0])]
    for index, option in enumerate(attack_reordered["options"]):
        option["index"] = index
    add("partner-blast-public-ko-reordered", attack_reordered, [1],
        matched_rule_id="attack.partner-blast-ko")

    non_ko = _frame()
    non_ko["public_state"]["self"]["active"][0].update({
        "attached_energy_count": 0,
        "attached_energy_uids": [],
        "attack_ready": False,
        "energy_debt": 1,
    })
    non_ko["options"] = [
        _option(0, "attack", source_uid="CSV10C_030", attack_index=0,
                projected_damage=100, projected_knockout=False),
        _option(1, "use_ability", source_uid="CSV4C_101", ability_index=0),
        _option(2, "end_turn"),
    ]
    add("partner-blast-non-ko-develops", non_ko, [1], matched_rule_id="pidgeot.quick-search")

    add("terminal-protects-base", copy.deepcopy(attack), [1], terminal=[1], selected_source="terminal")
    add("mandatory-protects-base", copy.deepcopy(attack), [1], mandatory=[1], selected_source="mandatory")
    add("hard-tier-protects-base", copy.deepcopy(attack), [1],
        tiers=[{"index": 0, "tier": [1]}, {"index": 1, "tier": [0]}],
        selected_source="deterministic_fallback")
    add("veto-protects-base", copy.deepcopy(attack), [1], vetoed=[0],
        selected_source="deterministic_fallback")

    unknown = _frame()
    unknown["options"] = [_option(0, "play_trainer", card_uid="PRIVATE_SENTINEL"), _option(1, "end_turn")]
    add("unknown-uid-fails-closed", unknown, [1], selected_source="deterministic_fallback")
    hidden = _frame()
    hidden["public_state"]["opponent"]["hand"] = [{"serial": 999, "local_card_uid": "PRIVATE_SENTINEL"}]
    hidden["options"] = [_option(0, "end_turn")]
    add("hidden-field-rejected", hidden, [], error_code="invalid_public_frame")

    low = _frame()
    low["public_state"]["self"]["deck_count"] = 4
    low["options"] = [_option(0, "play_trainer", card_uid="CSV1C_121"), _option(1, "end_turn")]
    add("low-deck-stops-research", low, [1], matched_rule_id="main.stop-low-deck-information",
        selected_source="deterministic_fallback")
    developed = copy.deepcopy(low)
    developed["public_state"]["self"]["deck_count"] = 12
    developed["public_state"]["self"]["active"][0].update({
        "attached_energy_count": 0, "attached_energy_uids": [], "attack_ready": False, "energy_debt": 1,
    })
    add("research-above-reserve", developed, [0], matched_rule_id="main.research-development")

    adapter = json.loads(
        (workspace / "package/policy/adapter.json").read_text(encoding="utf-8")
    )
    rule_ids = {row["rule_id"] for row in adapter["rules"]}
    if "pivot.ready-typhlosion-from-victini" in rule_ids:
        pivot = _frame()
        pivot["public_state"]["self"]["active"] = [_slot(
            100, 101, "CSV9C_023", remaining_hp=70, max_hp=70, prize_value=1,
            energy_count=2, minimum_attack_energy_count=2,
        )]
        pivot["public_state"]["self"]["bench"] = [_slot(
            110, 111, "CSV10C_030", remaining_hp=170, max_hp=170, prize_value=1,
            energy_count=1, minimum_attack_energy_count=1,
        )]
        pivot["options"] = [
            _option(0, "attack", source_uid="CSV9C_023", attack_index=0,
                    projected_damage=30, projected_knockout=False),
            _option(1, "retreat", target_uid="CSV10C_030", target_attack_ready=True,
                    target_energy_debt=0),
            _option(2, "end_turn"),
        ]
        add("pivot-ready-typhlosion-from-victini", pivot, [1],
            matched_rule_id="pivot.ready-typhlosion-from-victini")
        pivot_reordered = copy.deepcopy(pivot)
        pivot_reordered["options"] = [
            copy.deepcopy(pivot["options"][1]),
            copy.deepcopy(pivot["options"][2]),
            copy.deepcopy(pivot["options"][0]),
        ]
        for index, option in enumerate(pivot_reordered["options"]):
            option["index"] = index
        add("pivot-ready-typhlosion-from-victini-reordered", pivot_reordered, [0],
            matched_rule_id="pivot.ready-typhlosion-from-victini")
    if "attach.active-cyndaquil-debt" in rule_ids:
        attach = _frame()
        attach["public_state"]["self"]["active"] = [_slot(
            100, 101, "CSV10C_028", remaining_hp=70, max_hp=70, prize_value=1,
            energy_count=0, minimum_attack_energy_count=1,
        )]
        attach["public_state"]["self"]["bench"] = [_slot(
            110, 111, "CSV9C_023", remaining_hp=70, max_hp=70, prize_value=1,
            energy_count=0, minimum_attack_energy_count=2,
        )]
        attach["options"] = [
            _option(0, "attach_energy", card_uid="CSVE1C_FIR", target_uid="CSV9C_023",
                    target_entity_serial=110, target_attached_energy_count=0,
                    target_energy_debt=2, target_attack_ready=False),
            _option(1, "attach_energy", card_uid="CSVE1C_FIR", target_uid="CSV10C_028",
                    target_entity_serial=100, target_attached_energy_count=0,
                    target_energy_debt=1, target_attack_ready=False),
            _option(2, "end_turn"),
        ]
        add("attach-active-cyndaquil-before-victini", attach, [1],
            matched_rule_id="attach.active-cyndaquil-debt")
        attach_reordered = copy.deepcopy(attach)
        attach_reordered["options"] = [
            copy.deepcopy(attach["options"][1]),
            copy.deepcopy(attach["options"][2]),
            copy.deepcopy(attach["options"][0]),
        ]
        for index, option in enumerate(attach_reordered["options"]):
            option["index"] = index
        add("attach-active-cyndaquil-before-victini-reordered", attach_reordered, [0],
            matched_rule_id="attach.active-cyndaquil-debt")
    if "search.adventure.cyndaquil-missing-root" in rule_ids:
        missing_root = _frame("search")
        missing_root["select_semantics"].update({"min_count": 0, "max_count": 3})
        missing_root["public_state"]["self"]["active"] = [_slot(
            100, 101, "CSV9C_023", remaining_hp=70, max_hp=70, prize_value=1,
            energy_count=1, minimum_attack_energy_count=2,
        )]
        missing_root["public_state"]["self"]["bench"] = [_slot(
            110, 111, "CSV9C_023", remaining_hp=70, max_hp=70, prize_value=1,
            energy_count=0, minimum_attack_energy_count=2,
        )]
        missing_root["options"] = [
            _option(0, "search", card_uid="CSV10C_030", source_uid="CSV10C_208"),
            _option(1, "search", card_uid="CSVE1C_FIR", source_uid="CSV10C_208"),
            _option(2, "search", card_uid="CSV10C_029", source_uid="CSV10C_208"),
            _option(3, "search", card_uid="CSV10C_028", source_uid="CSV10C_208"),
        ]
        add("adventure-repairs-missing-cyndaquil-root", missing_root, [3, 0, 1],
            matched_rule_id="search.adventure.cyndaquil-missing-root")
        missing_root_reordered = copy.deepcopy(missing_root)
        missing_root_reordered["options"] = [
            copy.deepcopy(missing_root["options"][3]),
            copy.deepcopy(missing_root["options"][1]),
            copy.deepcopy(missing_root["options"][0]),
            copy.deepcopy(missing_root["options"][2]),
        ]
        for index, option in enumerate(missing_root_reordered["options"]):
            option["index"] = index
        add("adventure-repairs-missing-cyndaquil-root-reordered", missing_root_reordered,
            [0, 2, 1], matched_rule_id="search.adventure.cyndaquil-missing-root")
    if "search.pidgeot-fourth-adventure" in rule_ids:
        fourth = _frame("search")
        fourth["public_state"]["self"]["discard"] = [
            {"serial": 201 + index, "local_card_uid": "CSV10C_208"}
            for index in range(3)
        ]
        fourth["options"] = [
            _option(0, "search", card_uid="CSVH1C_045", source_uid="CSV4C_101"),
            _option(1, "search", card_uid="CSV10C_029", source_uid="CSV4C_101"),
            _option(2, "search", card_uid="CSV10C_208", source_uid="CSV4C_101"),
        ]
        add("pidgeot-gets-fourth-adventure", fourth, [2],
            matched_rule_id="search.pidgeot-fourth-adventure")
        fourth_reordered = copy.deepcopy(fourth)
        fourth_reordered["options"] = [
            copy.deepcopy(fourth["options"][2]),
            copy.deepcopy(fourth["options"][0]),
            copy.deepcopy(fourth["options"][1]),
        ]
        for index, option in enumerate(fourth_reordered["options"]):
            option["index"] = index
        add("pidgeot-gets-fourth-adventure-reordered", fourth_reordered, [0],
            matched_rule_id="search.pidgeot-fourth-adventure")
    if "search.artazon-cyndaquil-missing-root" in rule_ids:
        artazon_root = _frame("search")
        artazon_root["public_state"]["self"]["active"] = [_slot(
            100, 101, "CSV9C_023", remaining_hp=70, max_hp=70, prize_value=1,
            energy_count=0, minimum_attack_energy_count=2,
        )]
        artazon_root["public_state"]["self"]["bench"] = [_slot(
            110, 111, "151C_016", remaining_hp=50, max_hp=50, prize_value=1,
        )]
        artazon_root["options"] = [
            _option(0, "search", card_uid="151C_016", source_uid="CSV2C_127"),
            _option(1, "search", card_uid="CSV10C_028", source_uid="CSV2C_127"),
            _option(2, "search", card_uid="CSV9C_023", source_uid="CSV2C_127"),
        ]
        add("artazon-repairs-missing-cyndaquil-root", artazon_root, [1],
            matched_rule_id="search.artazon-cyndaquil-missing-root")
        artazon_root_reordered = copy.deepcopy(artazon_root)
        artazon_root_reordered["options"] = [
            copy.deepcopy(artazon_root["options"][1]),
            copy.deepcopy(artazon_root["options"][2]),
            copy.deepcopy(artazon_root["options"][0]),
        ]
        for index, option in enumerate(artazon_root_reordered["options"]):
            option["index"] = index
        add("artazon-repairs-missing-cyndaquil-root-reordered", artazon_root_reordered, [0],
            matched_rule_id="search.artazon-cyndaquil-missing-root")
    if "attach.benched-cyndaquil-debt" in rule_ids:
        bench_attach = _frame()
        bench_attach["public_state"]["self"]["active"] = [_slot(
            100, 101, "151C_016", remaining_hp=50, max_hp=50, prize_value=1,
        )]
        bench_attach["public_state"]["self"]["bench"] = [
            _slot(110, 111, "CSV10C_028", remaining_hp=70, max_hp=70, prize_value=1,
                  energy_count=0, minimum_attack_energy_count=1),
            _slot(120, 121, "CSV9C_023", remaining_hp=70, max_hp=70, prize_value=1,
                  energy_count=0, minimum_attack_energy_count=2),
        ]
        bench_attach["options"] = [
            _option(0, "attach_energy", card_uid="CSVE1C_FIR", target_uid="CSV9C_023",
                    target_entity_serial=120, target_attached_energy_count=0,
                    target_energy_debt=2, target_attack_ready=False),
            _option(1, "attach_energy", card_uid="CSVE1C_FIR", target_uid="CSV10C_028",
                    target_entity_serial=110, target_attached_energy_count=0,
                    target_energy_debt=1, target_attack_ready=False),
        ]
        add("attach-benched-cyndaquil-before-victini", bench_attach, [1],
            matched_rule_id="attach.benched-cyndaquil-debt")
        bench_attach_reordered = copy.deepcopy(bench_attach)
        bench_attach_reordered["options"].reverse()
        for index, option in enumerate(bench_attach_reordered["options"]):
            option["index"] = index
        add("attach-benched-cyndaquil-before-victini-reordered", bench_attach_reordered, [0],
            matched_rule_id="attach.benched-cyndaquil-debt")
    if "pivot.ready-quilava-from-nonline-active" in rule_ids:
        quilava_pivot = _frame()
        quilava_pivot["public_state"]["self"]["active"] = [_slot(
            100, 101, "151C_017", remaining_hp=100, max_hp=100, prize_value=1,
        )]
        quilava_pivot["public_state"]["self"]["bench"] = [_slot(
            110, 111, "CSV10C_029", remaining_hp=100, max_hp=100, prize_value=1,
            energy_count=1, minimum_attack_energy_count=1,
        )]
        quilava_pivot["options"] = [
            _option(0, "end_turn"),
            _option(1, "retreat", target_uid="CSV10C_029", target_entity_serial=110,
                    target_attached_energy_count=1, target_energy_debt=0,
                    target_attack_ready=True),
        ]
        add("pivot-ready-quilava-from-pidgeotto", quilava_pivot, [1],
            matched_rule_id="pivot.ready-quilava-from-nonline-active")
        quilava_pivot_reordered = copy.deepcopy(quilava_pivot)
        quilava_pivot_reordered["options"].reverse()
        for index, option in enumerate(quilava_pivot_reordered["options"]):
            option["index"] = index
        add("pivot-ready-quilava-from-pidgeotto-reordered", quilava_pivot_reordered, [0],
            matched_rule_id="pivot.ready-quilava-from-nonline-active")
    if "search.ultra-ball-quilava-missing-bridge" in rule_ids:
        ultra_bridge = _frame("search")
        ultra_bridge["public_state"]["self"]["active"] = [_slot(
            100, 101, "CSV10C_028", remaining_hp=70, max_hp=70, prize_value=1,
        )]
        ultra_bridge["public_state"]["self"]["bench"] = [_slot(
            110, 111, "CSV10C_028", remaining_hp=70, max_hp=70, prize_value=1,
        )]
        ultra_bridge["options"] = [
            _option(0, "search", card_uid="CSV10C_030", source_uid="CSV1C_112"),
            _option(1, "search", card_uid="CSV4C_101", source_uid="CSV1C_112"),
            _option(2, "search", card_uid="CSV10C_029", source_uid="CSV1C_112"),
        ]
        add("ultra-ball-repairs-missing-quilava-bridge", ultra_bridge, [2],
            matched_rule_id="search.ultra-ball-quilava-missing-bridge")
        ultra_bridge_reordered = copy.deepcopy(ultra_bridge)
        ultra_bridge_reordered["options"] = [
            copy.deepcopy(ultra_bridge["options"][2]),
            copy.deepcopy(ultra_bridge["options"][0]),
            copy.deepcopy(ultra_bridge["options"][1]),
        ]
        for index, option in enumerate(ultra_bridge_reordered["options"]):
            option["index"] = index
        add("ultra-ball-repairs-missing-quilava-bridge-reordered", ultra_bridge_reordered, [0],
            matched_rule_id="search.ultra-ball-quilava-missing-bridge")
    if "search.ultra-ball-quilava-missing-hand-bridge" in rule_ids:
        refined_bridge = _frame("search")
        refined_bridge["public_state"]["self"]["active"] = [_slot(
            100, 101, "CSV10C_028", remaining_hp=70, max_hp=70, prize_value=1,
        )]
        refined_bridge["public_state"]["self"]["bench"] = [_slot(
            110, 111, "CSV10C_028", remaining_hp=70, max_hp=70, prize_value=1,
        )]
        refined_bridge["options"] = [
            _option(0, "search", card_uid="CSV10C_030", source_uid="CSV1C_112"),
            _option(1, "search", card_uid="CSV4C_101", source_uid="CSV1C_112"),
            _option(2, "search", card_uid="CSV10C_029", source_uid="CSV1C_112"),
        ]
        add("ultra-ball-repairs-missing-hand-quilava-bridge", refined_bridge, [2],
            matched_rule_id="search.ultra-ball-quilava-missing-hand-bridge")
        refined_bridge_reordered = copy.deepcopy(refined_bridge)
        refined_bridge_reordered["options"] = [
            copy.deepcopy(refined_bridge["options"][2]),
            copy.deepcopy(refined_bridge["options"][0]),
            copy.deepcopy(refined_bridge["options"][1]),
        ]
        for index, option in enumerate(refined_bridge_reordered["options"]):
            option["index"] = index
        add("ultra-ball-repairs-missing-hand-quilava-bridge-reordered",
            refined_bridge_reordered, [0],
            matched_rule_id="search.ultra-ball-quilava-missing-hand-bridge")
        already_in_hand = copy.deepcopy(refined_bridge)
        already_in_hand["public_state"]["self"]["hand"] = [
            {"serial": 501, "local_card_uid": "CSV10C_029"}
        ]
        add("ultra-ball-does-not-duplicate-quilava-in-hand", already_in_hand, [0],
            matched_rule_id="search.ultra-ball-typhlosion")
    if "evolve.rare-candy-typhlosion-first" in rule_ids:
        candy_evolve = _frame("evolve")
        candy_evolve["public_state"]["self"]["active"] = [_slot(
            100, 101, "151C_016", remaining_hp=50, max_hp=50, prize_value=1,
        )]
        candy_evolve["public_state"]["self"]["bench"] = [_slot(
            110, 111, "CSV10C_028", remaining_hp=70, max_hp=70, prize_value=1,
        )]
        candy_evolve["options"] = [
            _option(0, "evolve", card_uid="CSV4C_101", source_uid="CSVH1C_045",
                    target_uid="151C_016", target_entity_serial=100),
            _option(1, "evolve", card_uid="CSV10C_030", source_uid="CSVH1C_045",
                    target_uid="CSV10C_028", target_entity_serial=110),
        ]
        add("rare-candy-prefers-typhlosion-over-pidgeot", candy_evolve, [1],
            matched_rule_id="evolve.rare-candy-typhlosion-first")
        candy_evolve_reordered = copy.deepcopy(candy_evolve)
        candy_evolve_reordered["options"].reverse()
        for index, option in enumerate(candy_evolve_reordered["options"]):
            option["index"] = index
        add("rare-candy-prefers-typhlosion-over-pidgeot-reordered",
            candy_evolve_reordered, [0],
            matched_rule_id="evolve.rare-candy-typhlosion-first")

    write_json(workspace / "scenario-suite.json", {
        "document_type": "ptcg_strategy_forge_scenario_suite_v1",
        "schema_version": 1,
        "cases": cases,
    })
    return {"case_count": len(cases), "suite_path": str(workspace / "scenario-suite.json")}
