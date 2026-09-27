"""Author-time strategy framework; compiles to the existing data-only Base IR.

No game interpreter or simulated future state lives here. Every phase is admitted
again from public facts and the current options by the pinned Host runtime.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any

from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler


CONSIDERATIONS = {
    'win_condition': 'Main and alternative win conditions; when to stop setup.',
    'prize_clock': 'Fast and robust prize schedules measured in attack windows.',
    'roles_and_identity': 'Exact printings, attacker, engine, bridge and stable entities.',
    'evolution_and_setup': 'Evolution bridges, timing and useful board composition.',
    'draw_and_search': 'Playable resources, dead hands, missing roles and legal whiffs.',
    'exact_payment': 'Same-entity typed energy, special conditions and retreat payment.',
    'resource_competition': 'Supporter, attachment, retreat, bench and scarce-card costs.',
    'pivot_and_gust': 'Current attack access, switching, opponent targets and escape.',
    'continuity': 'Next attacker, engine preservation and recovery after a knockout.',
    'information_checkpoints': 'Draw/search/reveal invalidates conditional suffix proofs.',
    'typed_interactions': 'Search, discard, number, assignment, promotion and targets.',
    'damage_and_counters': 'Damage versus counters; immunity, distribution and self-KO.',
    'credible_responses': 'Public threats, gust/heal/lock responses and unknowns.',
    'bench_liability': 'Capacity, exposed prize liabilities and endgame deployment.',
    'deckout_and_recovery': 'Remaining draw capacity, recursion and exhaustion wins.',
    'fallback_and_coverage': 'Unknown facts, unsupported effects and deterministic fallback.',
}


class BasePlanError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def document_sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


@dataclass(frozen=True)
class ResourceBudget:
    """Remaining costs in this fresh phase, not costs already paid in a prefix.

Only the first four counters are runtime availability gates. The last three are
declared costs, and require explicit public predicates for availability proofs.
"""
    supporter_uses: int = 0
    manual_attachments: int = 0
    retreats: int = 0
    bench_slots: int = 0
    ability_uses: int = 0
    discard_cards: int = 0
    search_cards: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RouteValue:
    """Ordinal comparisons, not estimated win probabilities or rollout results."""
    attack_windows: int = 1
    prize_progress: int = 0
    continuity: int = 1
    resource_cost: int = 0
    response_risk: int = 1
    uncertainty: int = 0

    def to_dict(self) -> dict:
        return {name: dict(base=value, terms=[]) for name, value in asdict(self).items()}


def route_step(step_id, goal_id, option_when, *, when=(), prompt_kinds=('main',),
               selection_count=1, terminal=False) -> dict:
    return copy.deepcopy(dict(step_id=step_id, prompt_kinds=list(prompt_kinds), goal_id=goal_id,
        when=list(when), option_when=list(option_when), selection_count=selection_count,
        terminal=terminal, checkpoint=True))


def route_candidate(route_id, goal_id, steps, *, when=(), budget=None, value=None,
                    owner_goal_id=None, bridge_goal_id=None, pivot_goal_id=None) -> dict:
    """Build native IR without introducing a second execution path."""
    return copy.deepcopy(dict(route_id=route_id, goal_id=goal_id,
        owner_goal_id=owner_goal_id or goal_id, bridge_goal_id=bridge_goal_id or goal_id,
        pivot_goal_id=pivot_goal_id or goal_id, when=list(when),
        resource_budget=(budget or ResourceBudget()).to_dict() if isinstance(budget, (ResourceBudget, type(None))) else budget,
        value=(value or RouteValue()).to_dict() if isinstance(value, (RouteValue, type(None))) else value,
        steps=list(steps)))


@dataclass(frozen=True)
class CompiledStrategyBase:
    adapter: dict
    policy: Any
    report: dict


def _shape(value, keys, code):
    if type(value) is not dict or set(value) != set(keys):
        raise BasePlanError(code)


class StrategyBase:
    """Compile reviewed situation phases and expose missing design obligations.

The source adapter stays the executable floor. A plan is hash-bound to that exact
adapter; when it changes, deliberately redraft/rebase and rerun acceptance.
"""

    @staticmethod
    def draft(adapter: dict) -> dict:
        if type(adapter) is not dict or adapter.get('schema_version') != 2:
            raise BasePlanError('base_requires_competitive_v2')
        return dict(document_type='forge_strategy_base_plan_v1', schema_version=1,
            base_adapter_sha256=document_sha256(adapter),
            considerations={key: dict(status='unresolved', rationale='', evidence=[])
                            for key in CONSIDERATIONS}, lines=[])

    @staticmethod
    def _materialize(adapter, plan, allowed_card_uids):
        _shape(plan, {'document_type','schema_version','base_adapter_sha256','considerations','lines'}, 'base_plan_shape_invalid')
        if plan['document_type'] != 'forge_strategy_base_plan_v1' or type(plan['schema_version']) is not int or plan['schema_version'] != 1:
            raise BasePlanError('base_plan_version_invalid')
        if document_sha256(adapter) != plan['base_adapter_sha256']:
            raise BasePlanError('base_adapter_changed')
        _shape(plan['considerations'], CONSIDERATIONS, 'base_considerations_incomplete')
        if type(plan['lines']) is not list or len(plan['lines']) > 32:
            raise BasePlanError('base_lines_invalid')
        result = copy.deepcopy(adapter)
        routes = result.setdefault('route_candidates', [])
        if type(routes) is not list:
            raise BasePlanError('base_routes_invalid')
        generated = []
        line_ids = set()
        for line in plan['lines']:
            _shape(line, {'line_id','goal_id','owner_goal_id','bridge_goal_id','pivot_goal_id','when','phases'}, 'base_line_invalid')
            if type(line['line_id']) is not str or line['line_id'] in line_ids:
                raise BasePlanError('base_line_id_invalid')
            line_ids.add(line['line_id'])
            if type(line['when']) is not list or type(line['phases']) is not list or not 1 <= len(line['phases']) <= 32:
                raise BasePlanError('base_phases_invalid')
            for phase in line['phases']:
                _shape(phase, {'phase_id','when','budget','value','steps'}, 'base_phase_invalid')
                if type(phase['phase_id']) is not str or type(phase['when']) is not list or type(phase['steps']) is not list:
                    raise BasePlanError('base_phase_invalid')
                for step in phase['steps']:
                    if type(step) is not dict or step.get('checkpoint') is not True:
                        raise BasePlanError('base_fresh_checkpoint_required')
                identity = line['line_id'] + '.' + phase['phase_id']
                routes.append(route_candidate(identity, line['goal_id'], phase['steps'],
                    when=[*line['when'], *phase['when']], budget=phase['budget'], value=phase['value'],
                    owner_goal_id=line['owner_goal_id'], bridge_goal_id=line['bridge_goal_id'], pivot_goal_id=line['pivot_goal_id']))
                generated.append(identity)
        # Use the actual SDK compiler for facts, enums, counts, identities and limits.
        outcome = CompetitivePolicyV2Compiler.compile_local_uid(result, allowed_card_uids=allowed_card_uids)
        if not outcome.accepted:
            raise BasePlanError('base_ir_' + outcome.error_code)
        references = set()
        for field, id_field, prefix in [('rules','rule_id','rule'),('count_rules','rule_id','count'),
                ('goals','goal_id','goal'),('route_candidates','route_id','route'),('turn_routes','route_id','turn'),
                ('interaction_recipes','recipe_id','interaction'),('damage_plans','plan_id','damage')]:
            references.update(prefix + ':' + row[id_field] for row in result.get(field, []) if id_field in row)
        unresolved, gaps = [], []
        coverage = {}
        for name, item in plan['considerations'].items():
            _shape(item, {'status','rationale','evidence'}, 'base_consideration_invalid')
            status = item['status']
            if type(status) is not str or status not in {'unresolved','implemented','not_applicable','gap'}:
                raise BasePlanError('base_consideration_status_invalid')
            if type(item['rationale']) is not str or len(item['rationale']) > 4000:
                raise BasePlanError('base_rationale_invalid')
            if status != 'unresolved' and not item['rationale'].strip():
                raise BasePlanError('base_rationale_required')
            evidence = item['evidence']
            if type(evidence) is not list or len(evidence) > 128 or any(type(ref) is not str or ref not in references for ref in evidence):
                raise BasePlanError('base_evidence_reference_invalid')
            if status == 'implemented' and not evidence:
                raise BasePlanError('base_evidence_reference_required')
            if status == 'unresolved': unresolved.append(name)
            if status == 'gap': gaps.append(name)
            # References prove a code owner exists, not semantic correctness or strength.
            coverage[name] = dict(status=status, implementation_references=list(evidence))
        report = dict(document_type='forge_strategy_base_audit_v1', schema_version=1,
            status='needs_design' if unresolved else ('compiled_with_gaps' if gaps else 'compiled'),
            base_adapter_sha256=plan['base_adapter_sha256'], plan_sha256=document_sha256(plan),
            adapter_sha256=document_sha256(result), allowed_card_uids_sha256=document_sha256(sorted(allowed_card_uids)),
            route_count=len(routes), generated_routes=generated, unresolved=unresolved, gaps=gaps,
            considerations=coverage,
            claims=dict(authoring_compile=True, semantic_coverage_proven=False, public_window_simulation=False,
                        engine_execution=False, strength_improvement=False, production_authority=False))
        return CompiledStrategyBase(result, outcome.policy, report)

    @staticmethod
    def audit(adapter, plan, *, allowed_card_uids):
        return StrategyBase._materialize(adapter, plan, allowed_card_uids).report

    @staticmethod
    def compile(adapter, plan, *, allowed_card_uids):
        result = StrategyBase._materialize(adapter, plan, allowed_card_uids)
        if result.report['unresolved']:
            raise BasePlanError('base_design_unresolved')
        return result
