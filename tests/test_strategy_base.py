"""Behavioral contracts for reusable current-window route authoring."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT)]

from tests.test_competitive_forge_v2 import _adapter, _frame, _condition, GRIMMSNARL, MORGREM, DARK_ENERGY
from ptcg_strategy_forge.strategy_base import (
    StrategyBase, BasePlanError, ResourceBudget, RouteValue, route_step, route_candidate,
)
from ptcg_strategy_forge.decision_bench import bind_frame
from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Runtime

ALLOWED = {GRIMMSNARL, MORGREM, DARK_ENERGY}
GOAL = 'ready-two-attackers'


def make_plan():
    adapter = _adapter()
    adapter['count_rules'] = []
    adapter['rules'][0]['base_score'] = 0
    plan = StrategyBase.draft(adapter)
    # Explicit gaps are acceptable development inputs, never claimed as coverage.
    for entry in plan['considerations'].values():
        entry.update(status='gap', rationale='Example scope; requires deck-specific evidence.')
    plan['lines'] = [dict(line_id='relay', goal_id=GOAL, owner_goal_id=GOAL,
        bridge_goal_id=GOAL, pivot_goal_id=GOAL, when=[], phases=[
            dict(phase_id='fund', when=[_condition('turn.manual_attachment_available','eq',True)],
                 budget=ResourceBudget(manual_attachments=1).to_dict(), value=RouteValue().to_dict(),
                 steps=[route_step('pay', GOAL, [_condition('option.kind','eq','attach_energy')])]),
            dict(phase_id='attack', when=[_condition('turn.manual_attachment_available','eq',False)],
                 budget=ResourceBudget().to_dict(), value=RouteValue(attack_windows=0).to_dict(),
                 steps=[route_step('strike', GOAL, [_condition('option.kind','eq','attack')], terminal=True)]),
        ])]
    return adapter, plan


def window(kind, available):
    frame = _frame()
    frame['prompt_kind'] = 'main'
    frame['select_semantics'].update(min_count=1, max_count=1, select_type_raw=0, select_context_raw=0)
    frame['public_state']['self']['turn'] = dict(supporter_available=True,
        manual_attachment_available=available, retreat_available=True)
    frame['options'] = frame['options'][:2]
    for option, name in zip(frame['options'], ['end_turn', kind]):
        option.update(kind=name, option_type_raw={'end_turn':14,'attach_energy':8,'attack':13}[name])
        if name != 'attach_energy':
            option.update(card_uid=None, card_serial=None)
        if name == 'attack':
            option.update(source_uid=GRIMMSNARL, source_serial=10, attack_index=0)
        if name == 'attach_energy':
            option.update(target_uid=GRIMMSNARL, target_serial=10)
    bind_frame(frame)
    return frame


def decide(policy, frame, **overrides):
    authority = dict(mandatory_indexes=[], terminal_indexes=[], base_vetoed_indexes=[],
                     base_hard_tiers=[dict(index=i,tier=[0]) for i in range(len(frame['options']))])
    authority.update(overrides)
    result = CompetitivePolicyV2Runtime.decide(policy, frame, **authority)
    assert result.accepted, result.error_code
    return list(result.selected_indexes)


class StrategyBaseTests(unittest.TestCase):
    def test_draft_reports_every_unresolved_consideration(self):
        adapter = _adapter()
        plan = StrategyBase.draft(adapter)
        audit = StrategyBase.audit(adapter, plan, allowed_card_uids=ALLOWED)
        self.assertEqual(audit['status'], 'needs_design')
        self.assertGreaterEqual(len(audit['unresolved']), 14)
        with self.assertRaisesRegex(BasePlanError, 'base_design_unresolved'):
            StrategyBase.compile(adapter, plan, allowed_card_uids=ALLOWED)

    def test_remaining_budget_releases_spent_token_in_fresh_window(self):
        adapter, plan = make_plan()
        result = StrategyBase.compile(adapter, plan, allowed_card_uids=ALLOWED)
        self.assertEqual(decide(result.policy, window('attach_energy',True)), [1])
        self.assertEqual(decide(result.policy, window('attack',False)), [1])
        self.assertEqual(result.adapter['route_candidates'][1]['resource_budget']['manual_attachments'], 0)
        self.assertFalse(result.report['claims']['engine_execution'])

    def test_reordering_and_authority_always_rebind(self):
        adapter, plan = make_plan()
        policy = StrategyBase.compile(adapter, plan, allowed_card_uids=ALLOWED).policy
        frame = window('attack',False)
        for gate in [dict(mandatory_indexes=[0]),dict(terminal_indexes=[0]),dict(base_vetoed_indexes=[1]),
                     dict(base_hard_tiers=[dict(index=0,tier=[0]),dict(index=1,tier=[1])])]:
            self.assertEqual(decide(policy,frame,**gate),[0])
        frame['options'].reverse()
        for i, option in enumerate(frame['options']): option['index'] = i
        bind_frame(frame)
        self.assertEqual(decide(policy,frame),[0])

    def test_unknown_or_hidden_facts_cannot_compile(self):
        for fact in ['opponent.hand.cards', 'future.drawn_uid', 'made_up.fact']:
            adapter, plan = make_plan()
            plan['lines'][0]['when'] = [_condition(fact,'eq',True)]
            with self.assertRaises(BasePlanError):
                StrategyBase.compile(adapter,plan,allowed_card_uids=ALLOWED)

    def test_checkpoint_required_and_unknown_fields_fail_closed(self):
        for mutation in ['checkpoint','cached_index']:
            adapter, plan = make_plan()
            step = plan['lines'][0]['phases'][0]['steps'][0]
            if mutation == 'checkpoint': step['checkpoint'] = False
            else: step['cached_index'] = 1
            with self.assertRaises(BasePlanError):
                StrategyBase.compile(adapter,plan,allowed_card_uids=ALLOWED)

    def test_unknown_uid_and_no_executable_step(self):
        adapter, plan = make_plan()
        plan['lines'][0]['phases'][1]['steps'][0]['option_when'].append(_condition('option.source_uid','eq','UNKNOWN_001'))
        with self.assertRaises(BasePlanError):
            StrategyBase.compile(adapter,plan,allowed_card_uids=ALLOWED)
        adapter, plan = make_plan()
        policy = StrategyBase.compile(adapter,plan,allowed_card_uids=ALLOWED).policy
        frame = window('attack',False)
        frame['options'] = frame['options'][:1]
        bind_frame(frame)
        self.assertEqual(decide(policy,frame),[0])

    def test_claimed_implementation_must_resolve_to_executable_owner(self):
        adapter, plan = make_plan()
        item = plan['considerations']['exact_payment']
        item.update(status='implemented', evidence=['rule:nonexistent'])
        with self.assertRaisesRegex(BasePlanError,'base_evidence_reference_invalid'):
            StrategyBase.compile(adapter,plan,allowed_card_uids=ALLOWED)
        item['evidence'] = ['route:relay.fund']
        self.assertEqual(StrategyBase.compile(adapter,plan,allowed_card_uids=ALLOWED).report['status'],'compiled_with_gaps')

    def test_input_not_mutated_and_stale_adapter_binding_rejected(self):
        adapter, plan = make_plan()
        before = copy.deepcopy((adapter,plan))
        result = StrategyBase.compile(adapter,plan,allowed_card_uids=ALLOWED)
        self.assertEqual((adapter,plan),before)
        result.adapter['rules'].clear()
        self.assertTrue(result.policy.validate_integrity())
        adapter['rules'][0]['base_score'] += 1
        with self.assertRaisesRegex(BasePlanError,'base_adapter_changed'):
            StrategyBase.compile(adapter,plan,allowed_card_uids=ALLOWED)

    def test_excess_routes_duplicate_ids_and_impossible_budget(self):
        for change in ['budget','duplicate','limit']:
            adapter, plan = make_plan()
            if change == 'budget': plan['lines'][0]['phases'][0]['budget']['supporter_uses'] = 2
            elif change == 'duplicate': plan['lines'] *= 2
            else:
                plan['lines'] = [dict(copy.deepcopy(plan['lines'][0]),line_id=f'line{i}') for i in range(17)]
            with self.assertRaises(BasePlanError):
                StrategyBase.compile(adapter,plan,allowed_card_uids=ALLOWED)

    def test_no_token_reuse_after_information_checkpoint(self):
        adapter, plan = make_plan()
        policy = StrategyBase.compile(adapter,plan,allowed_card_uids=ALLOWED).policy
        # A fresh window no longer proves the prefix's precondition.
        result = CompetitivePolicyV2Runtime.decide(policy, window('attach_energy',False),
            mandatory_indexes=[],terminal_indexes=[],base_vetoed_indexes=[],
            base_hard_tiers=[dict(index=0,tier=[0]),dict(index=1,tier=[0])])
        self.assertTrue(result.accepted)
        # The existing rule floor may still prefer an option. The old route has
        # no authority; authoring must not silently become a new legality owner.
        self.assertIsNone(result.audit['turn_contract']['route_id'])



if __name__ == '__main__': unittest.main()
