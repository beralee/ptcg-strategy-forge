"""Public-only API regressions; expectations do not depend on engine heuristics."""
import copy
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from scripts.ai.ptcgdap.public_decision_facts import (
    DECISION_FACT_TYPES, decision_error, decision_fact,
)
from tools.ptcgdap.public_decision_contract import decision_fixture, decision_cases
from tools.ptcgdap.build_competitive_policy_v2_contract import _frame, _option, _sample_policy
from scripts.ai.ptcgdap.competitive_policy_v2 import (
    CompetitivePolicyV2Compiler, CompetitivePolicyV2Runtime, _frame_error,
)


class PublicDecisionApiTests(unittest.TestCase):
    def test_decision_preferences_cannot_override_base_authority(self):
        case = next(c for c in decision_cases(_sample_policy, _option, _frame)
                    if c['case_id'] == 'public-decision-main-cost-paid-flip')
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(
            case['policy'], allowed_card_uids=set(case['allowed_card_uids']))
        for guards in [
            {'mandatory_indexes': [1]}, {'terminal_indexes': [1]},
            {'base_hard_tiers': [{'index': 0, 'tier': [1]}, {'index': 1, 'tier': [0]}]},
            {'base_vetoed_indexes': [0]},
        ]:
            with self.subTest(guards=guards):
                result = CompetitivePolicyV2Runtime.decide(compiled.policy, case['frame'], **guards)
                self.assertTrue(result.accepted, result.error_code)
                self.assertEqual(list(result.selected_indexes), [1])

    def test_sdk_immutable_queries_and_fresh_semantic_rebind(self):
        from ptcg_strategy_forge import PublicDecisionView, DecisionApiError
        frame = decision_fixture(_option, _frame)
        view = PublicDecisionView(frame)
        self.assertFalse(view.attack(10, 1)['energy_ready'])
        self.assertEqual(view.options(target_entity_serial=10)[0]['index'], 0)
        self.assertIsNone(view.legal_actions(kind='attack'))
        with self.assertRaises(TypeError):
            view.entity(10)['played_this_turn'] = True
        frame['options'].reverse()
        for i, option in enumerate(frame['options']):
            option['index'] = i
        frame['public_state']['decision']['entities'][0]['evolved_this_turn'] = True
        frame['source']['window_id'] = 'C' * 64
        new = PublicDecisionView(frame)
        self.assertEqual(new.options(target_entity_serial=10)[0]['index'], 1)
        self.assertFalse(view.entity(10)['evolved_this_turn'])
        self.assertTrue(new.fact('decision.option.target.evolved_this_turn', option_index=1))
        self.assertNotEqual(view.window_id, new.window_id)
        with self.assertRaises(DecisionApiError):
            view.fact('decision.opponent.hidden_hand')
        with self.assertRaises(DecisionApiError):
            view.options(old_index=0)
        self.assertIsNone(view.attack(10, 7))

    def test_sdk_legal_actions_are_current_frontier_only(self):
        from ptcg_strategy_forge import PublicDecisionView
        frame = decision_fixture(_option, _frame)
        frame['select_semantics']['select_type_raw'] = 0
        frame['options'][0].update(kind='use_ability', source_entity_serial=10, ability_index=0)
        view = PublicDecisionView(frame)
        self.assertEqual(len(view.legal_actions(kind='use_ability', source_entity_serial=10, ability_index=0)), 1)
        self.assertEqual(view.legal_actions(kind='attack'), ())
        self.assertFalse(view.capabilities['exact_arbitrary_target_damage'])

    def test_numeric_fact_types_and_frame_conditions_reject_target_facts(self):
        from scripts.ai.ptcgdap.competitive_policy_v2 import NUMERIC_TERM_FACTS, _condition_list_error
        for fact, kind in DECISION_FACT_TYPES.items():
            self.assertEqual(fact in NUMERIC_TERM_FACTS, kind == 'integer', fact)
        self.assertIsNotNone(_condition_list_error([
            {'fact': 'decision.option.target.evolved_this_turn', 'op': 'eq', 'value': True, 'card_uid': None}
        ], frozenset({'M2_001'}), allow_option_facts=False))

    def test_authored_vectors(self):
        for case in decision_cases(_sample_policy, _option, _frame):
            with self.subTest(case=case['case_id']):
                compiled = CompetitivePolicyV2Compiler.compile_local_uid(
                    case['policy'], allowed_card_uids=set(case['allowed_card_uids']))
                self.assertTrue(compiled.accepted, compiled.error_code)
                result = CompetitivePolicyV2Runtime.decide(compiled.policy, case['frame'])
                self.assertEqual(result.accepted, case['expected']['accepted'])
                self.assertEqual(result.error_code, case['expected']['error_code'])
                self.assertEqual(list(result.selected_indexes), case['expected']['selected_indexes'])

    def test_all_facts_absent_is_unknown(self):
        frame = _frame([_option(0)], 'main', 1, 1)
        for fact in DECISION_FACT_TYPES:
            self.assertIsNone(decision_fact(frame, frame['options'][0], fact), fact)

    def test_public_frame_validation_and_no_mutation(self):
        frame = decision_fixture(_option, _frame)
        before = copy.deepcopy(frame)
        self.assertIsNone(_frame_error(frame))
        self.assertFalse(decision_error(frame['public_state']))
        for fact in DECISION_FACT_TYPES:
            decision_fact(frame, frame['options'][0], fact)
        self.assertEqual(frame, before)

    def test_cost_identity_cannot_contain_trailing_newline(self):
        frame = decision_fixture(_option, _frame)
        frame['public_state']['decision']['entities'][0]['attacks'][0]['cost_candidates'] = ['C\n']
        self.assertEqual(_frame_error(frame), 'invalid_public_frame')


if __name__ == '__main__':
    unittest.main()
