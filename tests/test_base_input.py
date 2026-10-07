import copy
import unittest

from tools.ptcgdap.public_decision_contract import decision_fixture
from tools.ptcgdap.build_competitive_policy_v2_contract import _frame, _option, _sample_policy


class BaseInputTests(unittest.TestCase):
    def frame(self):
        return decision_fixture(_option, _frame)

    def test_lossless_immutable_and_presence(self):
        from scripts.ai.ptcgdap.base_input import BaseInput
        frame = self.frame()
        value = BaseInput.capture(frame)
        self.assertEqual(value.frame(), frame)
        frame['public_state']['self']['deck_count'] += 1
        self.assertNotEqual(value.frame(), frame)
        restored = value.frame()
        restored['sequence'] += 1
        self.assertNotEqual(value.frame(), restored)
        old = _frame([_option(0)], 'main', 1, 1)
        legacy = BaseInput.capture(old)
        self.assertFalse(legacy.coverage()['ready'])
        with self.assertRaisesRegex(ValueError, 'base_input_incomplete'):
            legacy.require_learning_ready()

    def test_critical_fields_change_model_input(self):
        from scripts.ai.ptcgdap.base_input import BaseInput
        original = self.frame()
        mutations = [
            lambda f: f['public_state']['opponent'].__setitem__('hand_count', 9),
            lambda f: f['public_state']['self'].__setitem__('deck_count', 7),
            lambda f: f['public_state']['decision']['turn'].__setitem__('stadium_effect_used', True),
            lambda f: f['public_state']['decision']['entities'][0].__setitem__('conditions', ['poisoned']),
            lambda f: f['public_state']['decision']['entities'][0].__setitem__('ability_use_recorded_this_turn', True),
        ]
        baseline = BaseInput.capture(original).model_document()
        for mutate in mutations:
            changed = copy.deepcopy(original)
            mutate(changed)
            self.assertNotEqual(baseline, BaseInput.capture(changed).model_document())

    def test_reorder_and_binding_are_separate(self):
        from scripts.ai.ptcgdap.base_input import BaseInput
        frame = self.frame()
        first = BaseInput.capture(frame)
        frame['options'].reverse()
        for i, option in enumerate(frame['options']):
            option['index'] = i
        second = BaseInput.capture(frame)
        self.assertEqual(first.model_document(), second.model_document())
        self.assertNotEqual(first.option_indexes, second.option_indexes)
        frame['source']['window_id'] = 'E' * 64
        self.assertEqual(second.model_document(), BaseInput.capture(frame).model_document())

    def test_private_and_unknown_fields_rejected(self):
        from scripts.ai.ptcgdap.base_input import BaseInput
        for key in ('hand', 'private_rng', 'unknown_field'):
            frame = self.frame()
            frame['public_state']['opponent'][key] = []
            with self.assertRaises(ValueError):
                BaseInput.capture(frame)

    def test_actor_mask_is_current_base_frontier_not_teacher_score(self):
        from scripts.ai.ptcgdap.base_input import BaseInput
        value=BaseInput.capture(self.frame())
        frontier=dict(profile_id='ptcgdap-base-model-frontier-v1',enabled=True,indexes=[1],
                      **value.frame()['source'])
        model=value.actor_document(frontier)
        self.assertEqual(sum(model['action_mask']),1)
        self.assertIn('/action_mask/0',model['presence'])
        self.assertEqual(model['action_mask'][value.option_indexes.index(1)],1)
        frontier['enabled']=False
        self.assertEqual(sum(value.actor_document(frontier)['action_mask']),0)
        frontier['window_id']='E'*64
        with self.assertRaisesRegex(ValueError,'base_input_frontier_binding'):
            value.actor_document(frontier)

    def test_native_overlay_is_scoped_and_preserves_decision_audit(self):
        from tools.base_input_runtime import patched_core
        text='\tvar turn_program_frame: Dictionary = frame_value.duplicate(true)\n\t\t"model_frontier": _base_model_frontier(frame),\n'
        changed=patched_core(text)
        self.assertIn('"base_input": base_input',changed)
        self.assertIn('capture_validated(frame_value',changed)
        with self.assertRaisesRegex(ValueError,'base_input_runtime_already_patched'):patched_core(changed)
        with self.assertRaisesRegex(ValueError,'base_input_runtime_owner_changed'):patched_core('unknown runtime')

    def test_plan_only_carries_semantic_intent(self):
        from scripts.ai.ptcgdap.base_input import BaseInput
        plan=dict(goal_id='attack',target_entity=10,turn=3,phase='prepare')
        self.assertEqual(BaseInput.capture(self.frame(),plan=plan).model_document()['plan'],plan)
        for forbidden in ('old_index','score','proof','private_rng'):
            with self.assertRaisesRegex(ValueError,'base_input_plan_invalid'):
                BaseInput.capture(self.frame(),plan={**plan,forbidden:1})

    def test_base_always_produces_standard_input_without_changing_authority(self):
        from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler as C, CompetitivePolicyV2Runtime as R
        from scripts.ai.ptcgdap.base_input import BaseInput
        from tools.ptcgdap.public_decision_contract import decision_cases
        case = decision_cases(_sample_policy, _option, _frame)[0]
        compiled = C.compile_local_uid(case['policy'], allowed_card_uids=set(case['allowed_card_uids']))
        self.assertTrue(compiled.accepted, compiled.error_code)
        frame = case['frame']
        decision = R.decide(compiled.policy, frame, mandatory_indexes=[1])
        self.assertTrue(decision.accepted, decision.error_code)
        self.assertEqual(decision.selected_indexes, [1])
        self.assertIsInstance(decision.base_input, BaseInput)
        self.assertEqual(decision.base_input.frame(), frame)


if __name__ == '__main__':
    unittest.main()
