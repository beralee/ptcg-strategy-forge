from __future__ import annotations

"""Small, dependency-free UCIS helper shipped with generated `.ptcgbot` projects.

The module is deliberately a view over one immutable current window.  It does
not own legality, engine commands, tickets, callbacks, or cross-window state.
"""

from dataclasses import dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence


UCIS_GENERATION = 1
CONTRACT_GENERATION = 2
REGISTRY_SHA256 = "95472B7D2245A5F26D7911A863DCCA67A9997BB1C6CECB9E3DC086454201C492"

SELECT_TYPE_NAMES = (
    "MAIN",
    "CARD",
    "ATTACHED_CARD",
    "CARD_OR_ATTACHED_CARD",
    "ENERGY",
    "SKILL",
    "ATTACK",
    "EVOLVE",
    "COUNT",
    "YES_NO",
    "SPECIAL_CONDITION",
)
CONTEXT_NAMES = (
    "MAIN",
    "SETUP_ACTIVE_POKEMON",
    "SETUP_BENCH_POKEMON",
    "SWITCH",
    "TO_ACTIVE",
    "TO_BENCH",
    "TO_FIELD",
    "TO_HAND",
    "DISCARD",
    "TO_DECK",
    "TO_DECK_BOTTOM",
    "TO_PRIZE",
    "NOT_MOVE",
    "DAMAGE_COUNTER",
    "DAMAGE_COUNTER_ANY",
    "DAMAGE",
    "REMOVE_DAMAGE_COUNTER",
    "HEAL",
    "EVOLVES_FROM",
    "EVOLVES_TO",
    "DEVOLVE",
    "ATTACH_FROM",
    "ATTACH_TO",
    "DETACH_FROM",
    "LOOK",
    "EFFECT_TARGET",
    "DISCARD_ENERGY_CARD",
    "DISCARD_TOOL_CARD",
    "SWITCH_ENERGY_CARD",
    "DISCARD_CARD_OR_ATTACHED_CARD",
    "DISCARD_ENERGY",
    "TO_HAND_ENERGY",
    "TO_DECK_ENERGY",
    "SWITCH_ENERGY",
    "SKILL_ORDER",
    "ATTACK",
    "DISABLE_ATTACK",
    "EVOLVE",
    "DRAW_COUNT",
    "DAMAGE_COUNTER_COUNT",
    "REMOVE_DAMAGE_COUNTER_COUNT",
    "IS_FIRST",
    "MULLIGAN",
    "ACTIVATE",
    "FIRST_EFFECT",
    "MORE_DEVOLVE",
    "COIN_HEAD",
    "AFFECT_SPECIAL_CONDITION",
    "RECOVER_SPECIAL_CONDITION",
)
OPTION_TYPE_NAMES = (
    "NUMBER",
    "YES",
    "NO",
    "CARD",
    "TOOL_CARD",
    "ENERGY_CARD",
    "ENERGY",
    "PLAY",
    "ATTACH",
    "EVOLVE",
    "ABILITY",
    "DISCARD",
    "RETREAT",
    "ATTACK",
    "END",
    "SKILL",
    "SPECIAL_CONDITION",
)
OPTION_TYPE_RAW = MappingProxyType(
    {name: raw for raw, name in enumerate(OPTION_TYPE_NAMES)}
)
OPTION_FIELDS = (
    ("type", "number"),
    ("type",),
    ("type",),
    ("type", "area", "index", "playerIndex"),
    ("type", "area", "index", "playerIndex", "toolIndex"),
    ("type", "area", "index", "playerIndex", "energyIndex"),
    ("type", "area", "index", "playerIndex", "energyIndex", "count"),
    ("type", "index"),
    ("type", "area", "index", "inPlayArea", "inPlayIndex"),
    ("type", "area", "index", "inPlayArea", "inPlayIndex"),
    ("type", "area", "index"),
    ("type", "area", "index"),
    ("type",),
    ("type", "attackId"),
    ("type",),
    ("type", "cardId", "serial"),
    ("type", "specialConditionType"),
)
_SELECT_FIELDS = frozenset(
    {
        "type",
        "context",
        "minCount",
        "maxCount",
        "remainDamageCounter",
        "remainEnergyCost",
        "option",
        "deck",
        "contextCard",
        "effect",
    }
)


class UcisRuntimeError(ValueError):
    """Stable fail-closed error for author-visible UCIS helpers."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _fail(code: str) -> None:
    raise UcisRuntimeError(code)


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as error:
        raise UcisRuntimeError("ucis_runtime_value_invalid") from error


def _context_select_type(context_raw: int) -> int:
    if context_raw == 0:
        return 0
    if 1 <= context_raw <= 25:
        return 1
    if 26 <= context_raw <= 28:
        return 2
    if context_raw == 29:
        return 3
    if 30 <= context_raw <= 33:
        return 4
    if context_raw == 34:
        return 5
    if 35 <= context_raw <= 36:
        return 6
    if context_raw == 37:
        return 7
    if 38 <= context_raw <= 40:
        return 8
    if 41 <= context_raw <= 46:
        return 9
    if 47 <= context_raw <= 48:
        return 10
    _fail("ucis_runtime_context_unknown")


def _allowed_option_types(context_raw: int) -> tuple[int, ...]:
    if context_raw == 0:
        return tuple(range(7, 15))
    if 1 <= context_raw <= 25:
        return (3,)
    if context_raw == 26:
        return (5,)
    if context_raw == 27:
        return (4,)
    if context_raw == 28:
        return (5,)
    if context_raw == 29:
        return (3, 4, 5)
    if 30 <= context_raw <= 33:
        return (6,)
    if context_raw == 34:
        return (15,)
    if 35 <= context_raw <= 36:
        return (13,)
    if context_raw == 37:
        return (9,)
    if 38 <= context_raw <= 40:
        return (0,)
    if 41 <= context_raw <= 46:
        return (1, 2)
    if 47 <= context_raw <= 48:
        return (16,)
    _fail("ucis_runtime_context_unknown")


@dataclass(frozen=True, slots=True)
class SemanticOptionKey:
    option_type_name: str
    fields: tuple[tuple[str, int], ...]


def semantic_key(option_type_name: str, **fields: int) -> SemanticOptionKey:
    raw = OPTION_TYPE_RAW.get(option_type_name)
    if raw is None:
        _fail("ucis_runtime_option_type_unknown")
    expected = OPTION_FIELDS[raw][1:]
    if set(fields) != set(expected) or any(type(fields[name]) is not int for name in expected):
        _fail("ucis_runtime_option_shape_invalid")
    return SemanticOptionKey(
        option_type_name=option_type_name,
        fields=tuple((name, fields[name]) for name in expected),
    )


def option(option_type_name: str, **fields: int) -> dict[str, int]:
    raw = OPTION_TYPE_RAW.get(option_type_name)
    if raw is None:
        _fail("ucis_runtime_option_type_unknown")
    key = semantic_key(option_type_name, **fields)
    return {"type": raw, **dict(key.fields)}


@dataclass(frozen=True, slots=True)
class OptionView:
    index: int
    option_type_raw: int
    option_type_name: str
    fields: Mapping[str, int]
    semantic_key: SemanticOptionKey
    audit_fingerprint: str

    def field(self, name: str) -> int | None:
        return self.fields.get(name)


@dataclass(frozen=True, slots=True)
class SelectionWindow:
    select_type_raw: int
    select_type_name: str
    context_raw: int
    context_name: str
    min_count: int
    max_count: int
    remain_damage_counter: int
    remain_energy_cost: int
    options: tuple[OptionView, ...]

    @classmethod
    def parse(cls, raw_observation: Mapping[str, Any]) -> "SelectionWindow":
        if type(raw_observation) is not dict or type(raw_observation.get("select")) is not dict:
            _fail("ucis_runtime_observation_invalid")
        select = raw_observation["select"]
        if set(select) != _SELECT_FIELDS:
            _fail("ucis_runtime_select_shape_invalid")
        select_type = select["type"]
        context = select["context"]
        minimum = select["minCount"]
        maximum = select["maxCount"]
        remain_damage = select["remainDamageCounter"]
        remain_energy = select["remainEnergyCost"]
        raw_options = select["option"]
        if (
            any(
                type(value) is not int
                for value in (select_type, context, minimum, maximum, remain_damage, remain_energy)
            )
            or type(raw_options) is not list
        ):
            _fail("ucis_runtime_select_value_invalid")
        if not 0 <= context < len(CONTEXT_NAMES):
            _fail("ucis_runtime_context_unknown")
        expected_select_type = _context_select_type(context)
        if select_type != expected_select_type:
            _fail("ucis_runtime_context_type_mismatch")
        if (
            minimum < 0
            or maximum < minimum
            or maximum > len(raw_options)
            or remain_damage < 0
            or remain_energy < 0
        ):
            _fail("ucis_runtime_cardinality_invalid")
        allowed = _allowed_option_types(context)
        parsed: list[OptionView] = []
        for index, raw_option in enumerate(raw_options):
            if type(raw_option) is not dict or type(raw_option.get("type")) is not int:
                _fail("ucis_runtime_option_invalid")
            option_type = raw_option["type"]
            if not 0 <= option_type < len(OPTION_TYPE_NAMES) or option_type not in allowed:
                _fail("ucis_runtime_context_option_mismatch")
            expected_fields = OPTION_FIELDS[option_type]
            if set(raw_option) != set(expected_fields):
                _fail("ucis_runtime_option_shape_invalid")
            if any(type(raw_option[name]) is not int for name in expected_fields):
                _fail("ucis_runtime_option_value_invalid")
            name = OPTION_TYPE_NAMES[option_type]
            fields = {field: raw_option[field] for field in expected_fields[1:]}
            parsed.append(
                OptionView(
                    index=index,
                    option_type_raw=option_type,
                    option_type_name=name,
                    fields=MappingProxyType(fields),
                    semantic_key=semantic_key(name, **fields),
                    audit_fingerprint=hashlib.sha256(_canonical(raw_option)).hexdigest().upper(),
                )
            )
        return cls(
            select_type_raw=select_type,
            select_type_name=SELECT_TYPE_NAMES[select_type],
            context_raw=context,
            context_name=CONTEXT_NAMES[context],
            min_count=minimum,
            max_count=maximum,
            remain_damage_counter=remain_damage,
            remain_energy_cost=remain_energy,
            options=tuple(parsed),
        )

    def validate_indexes(self, indexes: Sequence[int]) -> list[int]:
        if type(indexes) not in (list, tuple) or any(type(index) is not int for index in indexes):
            _fail("ucis_runtime_indexes_invalid")
        result = list(indexes)
        if (
            len(result) != len(set(result))
            or any(index < 0 or index >= len(self.options) for index in result)
            or not self.min_count <= len(result) <= self.max_count
        ):
            _fail("ucis_runtime_indexes_invalid")
        return result

    def first_legal(self) -> list[int]:
        return self.validate_indexes(list(range(self.min_count)))

    def choose_exact(
        self,
        count: int,
        predicate: Callable[[OptionView], bool],
    ) -> list[int]:
        if type(count) is not int or not self.min_count <= count <= self.max_count:
            _fail("ucis_runtime_count_invalid")
        if not callable(predicate):
            _fail("ucis_runtime_predicate_invalid")
        matches: list[int] = []
        try:
            for candidate in self.options:
                matched = predicate(candidate)
                if type(matched) is not bool:
                    _fail("ucis_runtime_predicate_invalid")
                if matched:
                    matches.append(candidate.index)
        except UcisRuntimeError:
            raise
        except BaseException as error:
            raise UcisRuntimeError("ucis_runtime_predicate_invalid") from error
        if len(matches) < count:
            _fail("ucis_runtime_not_enough_matches")
        return self.validate_indexes(matches[:count])

    def choose_up_to(
        self,
        limit: int,
        predicate: Callable[[OptionView], bool],
    ) -> list[int]:
        if type(limit) is not int or limit < 0:
            _fail("ucis_runtime_count_invalid")
        count_limit = min(limit, self.max_count)
        if not callable(predicate):
            _fail("ucis_runtime_predicate_invalid")
        matches: list[int] = []
        try:
            for candidate in self.options:
                matched = predicate(candidate)
                if type(matched) is not bool:
                    _fail("ucis_runtime_predicate_invalid")
                if matched and len(matches) < count_limit:
                    matches.append(candidate.index)
        except UcisRuntimeError:
            raise
        except BaseException as error:
            raise UcisRuntimeError("ucis_runtime_predicate_invalid") from error
        return self.validate_indexes(matches)

    def rebind(self, keys: Sequence[SemanticOptionKey]) -> list[int]:
        if type(keys) not in (list, tuple) or any(type(key) is not SemanticOptionKey for key in keys):
            _fail("ucis_runtime_semantic_key_invalid")
        available: dict[SemanticOptionKey, list[int]] = {}
        for candidate in self.options:
            available.setdefault(candidate.semantic_key, []).append(candidate.index)
        result: list[int] = []
        for key in keys:
            candidates = available.get(key, [])
            if not candidates:
                _fail("ucis_runtime_semantic_rebind_missing")
            result.append(candidates.pop(0))
        return self.validate_indexes(result)

    def choose_number(self, value: int) -> list[int]:
        if type(value) is not int:
            _fail("ucis_runtime_number_invalid")
        return self.choose_exact(
            1,
            lambda candidate: candidate.option_type_name == "NUMBER"
            and candidate.field("number") == value,
        )

    def choose_boolean(self, value: bool) -> list[int]:
        if type(value) is not bool:
            _fail("ucis_runtime_boolean_invalid")
        wanted = "YES" if value else "NO"
        return self.choose_exact(1, lambda candidate: candidate.option_type_name == wanted)

    def public_summary(self) -> dict[str, Any]:
        return {
            "ucis_generation": UCIS_GENERATION,
            "registry_sha256": REGISTRY_SHA256,
            "select_type": self.select_type_name,
            "context": self.context_name,
            "min_count": self.min_count,
            "max_count": self.max_count,
            "remain_damage_counter": self.remain_damage_counter,
            "remain_energy_cost": self.remain_energy_cost,
            "options": [
                {
                    "index": candidate.index,
                    "option_type": candidate.option_type_name,
                    "fields": dict(candidate.fields),
                    "audit_fingerprint": candidate.audit_fingerprint,
                }
                for candidate in self.options
            ],
        }


def _required_int(mapping: Mapping[str, Any], name: str) -> int:
    value = mapping.get(name)
    if type(value) is not int:
        _fail("ucis_runtime_public_state_invalid")
    return value


def _required_list(mapping: Mapping[str, Any], name: str) -> list[Any]:
    value = mapping.get(name)
    if type(value) is not list:
        _fail("ucis_runtime_public_state_invalid")
    return value


def _active_energy_units(player: Mapping[str, Any]) -> int:
    active = _required_list(player, "active")
    if not active or active[0] is None:
        return 0
    pokemon = active[0]
    if type(pokemon) is not dict:
        _fail("ucis_runtime_public_state_invalid")
    energies = _required_list(pokemon, "energies")
    if any(type(value) is not int for value in energies):
        _fail("ucis_runtime_public_state_invalid")
    return len(energies)


@dataclass(frozen=True, slots=True)
class PublicBattleFacts:
    turn: int
    turn_action_count: int
    acting_player_index: int
    acting_prizes_remaining: int
    opponent_prizes_remaining: int
    acting_deck_count: int
    opponent_deck_count: int
    acting_hand_count: int
    opponent_hand_count: int
    acting_bench_free: int
    opponent_bench_free: int
    acting_active_energy_units: int
    opponent_active_energy_units: int

    @classmethod
    def parse(cls, raw_observation: Mapping[str, Any]) -> "PublicBattleFacts":
        if type(raw_observation) is not dict or type(raw_observation.get("current")) is not dict:
            _fail("ucis_runtime_public_state_invalid")
        current = raw_observation["current"]
        chooser = _required_int(current, "yourIndex")
        players = _required_list(current, "players")
        if chooser not in (0, 1) or len(players) != 2 or any(type(player) is not dict for player in players):
            _fail("ucis_runtime_public_state_invalid")
        opponent = 1 - chooser
        acting = players[chooser]
        opposing = players[opponent]
        acting_bench = _required_list(acting, "bench")
        opposing_bench = _required_list(opposing, "bench")
        acting_bench_max = _required_int(acting, "benchMax")
        opposing_bench_max = _required_int(opposing, "benchMax")
        if acting_bench_max < len(acting_bench) or opposing_bench_max < len(opposing_bench):
            _fail("ucis_runtime_public_state_invalid")
        return cls(
            turn=_required_int(current, "turn"),
            turn_action_count=_required_int(current, "turnActionCount"),
            acting_player_index=chooser,
            acting_prizes_remaining=len(_required_list(acting, "prize")),
            opponent_prizes_remaining=len(_required_list(opposing, "prize")),
            acting_deck_count=_required_int(acting, "deckCount"),
            opponent_deck_count=_required_int(opposing, "deckCount"),
            acting_hand_count=_required_int(acting, "handCount"),
            opponent_hand_count=_required_int(opposing, "handCount"),
            acting_bench_free=acting_bench_max - len(acting_bench),
            opponent_bench_free=opposing_bench_max - len(opposing_bench),
            acting_active_energy_units=_active_energy_units(acting),
            opponent_active_energy_units=_active_energy_units(opposing),
        )

    def acting_active_energy_debt(self, required_units: int) -> int:
        if type(required_units) is not int or required_units < 0:
            _fail("ucis_runtime_energy_requirement_invalid")
        return max(0, required_units - self.acting_active_energy_units)

    def acting_attack_windows_to_win(self, prizes_per_attack: int) -> int:
        if type(prizes_per_attack) is not int or prizes_per_attack <= 0:
            _fail("ucis_runtime_prize_value_invalid")
        return (self.opponent_prizes_remaining + prizes_per_attack - 1) // prizes_per_attack

    def opponent_attack_windows_to_win(self, prizes_per_attack: int) -> int:
        if type(prizes_per_attack) is not int or prizes_per_attack <= 0:
            _fail("ucis_runtime_prize_value_invalid")
        return (self.acting_prizes_remaining + prizes_per_attack - 1) // prizes_per_attack


__all__ = [
    "CONTRACT_GENERATION",
    "CONTEXT_NAMES",
    "OPTION_FIELDS",
    "OPTION_TYPE_NAMES",
    "OPTION_TYPE_RAW",
    "OptionView",
    "PublicBattleFacts",
    "REGISTRY_SHA256",
    "SELECT_TYPE_NAMES",
    "SelectionWindow",
    "SemanticOptionKey",
    "UCIS_GENERATION",
    "UcisRuntimeError",
    "option",
    "semantic_key",
]
