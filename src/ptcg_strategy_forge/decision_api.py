"""Author-facing immutable queries over the Competitive public decision window.

This API does not execute actions. Reconstruct it from every observation; use
fresh semantic filters, not indexes or proof objects retained from an old view.
"""
from __future__ import annotations

import copy
from types import MappingProxyType
from collections.abc import Mapping

from scripts.ai.ptcgdap.competitive_policy_v2 import _frame_error
from scripts.ai.ptcgdap.public_decision_facts import DECISION_FACT_TYPES, decision_fact


class DecisionApiError(ValueError):
    pass


def _immutable(value):
    if isinstance(value, dict):
        return MappingProxyType({k: _immutable(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_immutable(v) for v in value)
    return value


class PublicDecisionView:
    """Validated snapshot with explicit unknowns and current-frontier lookup."""

    FACT_TYPES = MappingProxyType(DECISION_FACT_TYPES.copy())
    _FILTERS = frozenset({'kind', 'card_uid', 'card_serial', 'source_uid', 'source_serial',
                          'source_entity_serial', 'target_uid', 'target_serial',
                          'target_entity_serial', 'attack_index', 'ability_index'})

    def __init__(self, frame: dict, *, public_semantics_v2: dict | None = None):
        self.public_input_v3 = None
        if type(frame) is dict and frame.get('profile') == 'ptcg-public-input-v3':
            if public_semantics_v2 is not None:
                raise DecisionApiError('public_input_v3_mixed_versions')
            from scripts.ai.ptcgdap.public_input_v3 import PublicInputV3
            self.public_input_v3 = PublicInputV3.capture(frame)
            frame = self.public_input_v3.base.frame()
        error = _frame_error(frame)
        if error:
            raise DecisionApiError(error)
        from scripts.ai.ptcgdap.public_input_v2 import PublicInputV2
        self.public_input_v2 = PublicInputV2.capture(frame, public_semantics_v2)
        self.public_input = self.public_input_v3 or self.public_input_v2
        self.base_input = self.public_input_v2.base
        self._frame = self.base_input.frame()
        self._snapshot = _immutable(self._frame)

    @property
    def snapshot(self) -> Mapping:
        return self._snapshot

    @property
    def window_id(self) -> str:
        return self._frame['source']['window_id']

    @property
    def capabilities(self) -> Mapping:
        present = 'decision' in self._frame['public_state']
        return MappingProxyType({
            'public_input_v3': self.public_input_v3 is not None,
            'public_input_v2': self.public_input_v2.coverage()['supported'],
            'public_decision_v1': present, 'current_option_query': True,
            'printed_attack_costs': present, 'effective_energy_supply': present,
            'bounded_attack_access_plans': present,
            'bounded_plan_comparison': present,
            'prospective_attack_legality': False, 'exact_arbitrary_target_damage': False,
            'opponent_hidden_information': False,
        })

    def fact(self, name: str, *, option_index: int | None = None):
        if name not in self.FACT_TYPES:
            raise DecisionApiError('unknown_decision_fact')
        option = None
        if option_index is not None:
            if type(option_index) is not int or not 0 <= option_index < len(self._frame['options']):
                raise DecisionApiError('invalid_current_option_index')
            option = self._frame['options'][option_index]
        return _immutable(decision_fact(self._frame, option, name))

    def options(self, **semantic_filters) -> tuple[Mapping, ...]:
        """Rebind semantic identity to indexes in this view only; never dispatch."""
        if set(semantic_filters) - self._FILTERS:
            raise DecisionApiError('unknown_option_filter')
        return tuple(option for option in self._snapshot['options']
                     if all(option.get(k) == v for k, v in semantic_filters.items()))

    def legal_actions(self, **semantic_filters) -> tuple[Mapping, ...] | None:
        """Only a MAIN selection proves present action availability.

        Interaction windows return None, since they are not a complete main
        frontier. Absence there cannot prove an attack/ability is unavailable.
        """
        if self._frame['select_semantics']['select_type_raw'] != 0:
            return None
        return self.options(**semantic_filters)

    def entity(self, entity_serial: int) -> Mapping | None:
        if type(entity_serial) is not int or entity_serial < 1:
            raise DecisionApiError('invalid_entity_identity')
        extension = self._snapshot['public_state'].get('decision')
        if extension is None:
            return None
        return next((e for e in extension['entities'] if e['entity_serial'] == entity_serial), None)

    def attack(self, entity_serial: int, attack_index: int) -> Mapping | None:
        """Printed attack index, cost-only; granted legal attacks use options()."""
        if type(attack_index) is not int or attack_index < 0:
            raise DecisionApiError('invalid_attack_identity')
        entity = self.entity(entity_serial)
        if entity is None:
            return None
        return next((a for a in entity['attacks'] if a['attack_index'] == attack_index), None)

    def energy_sources(self, entity_serial: int) -> tuple[Mapping, ...] | None:
        entity = self.entity(entity_serial)
        return entity['energies'] if entity is not None else None

    def ability_ledger(self, entity_serial: int | None = None):
        return _immutable(self.public_input.abilities(entity_serial))

    def effect_ledger(self, entity_serial: int | None = None):
        return _immutable(self.public_input.effects(entity_serial))

    def input_coverage(self):
        return _immutable(self.public_input.coverage())

    def quota_ledger(self, player: int | None = None):
        return _immutable(self.public_input.quotas(player))

    def interaction_context(self):
        return _immutable(self.public_input.interaction())

    def public_history(self):
        return _immutable(self.public_input.history())

    def evaluate_public_attack(self, entity_serial: int, attack_index: int, target_entity: int):
        return _immutable(self.public_input.evaluate_attack(entity_serial, attack_index, target_entity))

    def attack_access_plans(self) -> Mapping:
        """Conditional resource plans, bound to this snapshot, NOT legal suffixes.

        At most three modeled attach/evolve/retreat edges from the current
        frontier. Unknown capabilities close the corresponding branch. Future
        damage, opponent response and attack legality remain explicit unknowns.
        """
        from scripts.ai.ptcgdap.public_attack_access import plan_attack_access
        return _immutable(dict(window_id=self.window_id,
            **plan_attack_access(self._frame, validated=True)))

    def compare_plans(self, ordered_indexes: list[int], *, profile: str = 'resource-continuity-v1') -> Mapping:
        """Compare a fresh proposed frontier; Base must still authorize it.

        The first entry is the mature rule baseline. Ordinal estimates are
        conditional and cannot certify hidden outcomes or future legality.
        """
        from scripts.ai.ptcgdap.public_plan_comparison import compare_plans
        return _immutable(dict(window_id=self.window_id,
            **compare_plans(self._frame, ordered_indexes, validated=True, profile=profile)))
