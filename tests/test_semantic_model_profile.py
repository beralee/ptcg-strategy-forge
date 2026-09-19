import copy
import unittest
import json
import tempfile
from pathlib import Path

from tests.test_competitive_forge_v2 import _frame, _adapter, GRIMMSNARL, MORGREM, DARK_ENERGY


class SemanticModelProfileTests(unittest.TestCase):
    def test_workspace_tensorizes_explicit_development_frame(self):
        from ptcg_strategy_forge.sdk import StrategyWorkspace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root/'package/deck').mkdir(parents=True)
            (root/'package/strategy_package.json').write_text(json.dumps({'policy':{'policy_mode':'rules_with_model'}}))
            (root/'package/deck/deck_manifest.json').write_text(json.dumps({'cards':[
                {'local_card_uid':uid} for uid in (GRIMMSNARL,MORGREM,DARK_ENERGY)]}))
            (root/'frame.json').write_text(json.dumps(_frame()))
            result = StrategyWorkspace(root).model.tensorize('frame.json')
            tensors = json.loads(Path(result['output']).read_bytes())
            self.assertEqual(tensors['profile_id'], 'ptcgdap_local_semantic_actor_i32_v1')
            self.assertEqual(len(tensors['frame_i32'][0]), 128)
            self.assertEqual(len(tensors['option_i32'][0][0]), 32)

    def test_public_state_is_visible_and_reorder_rebinds(self):
        from scripts.ai.ptcgdap.semantic_model_profile import project_semantic_frame
        frame = _frame(); uids = [GRIMMSNARL, MORGREM, DARK_ENERGY]
        original = project_semantic_frame(frame, uids)
        self.assertEqual(len(original.frame_i32), 128)
        frame['public_state']['self']['active'][0]['remaining_hp'] -= 10
        changed = project_semantic_frame(frame, uids)
        self.assertNotEqual(original.frame_i32, changed.frame_i32)
        frame['public_state']['self']['hand'].append({'local_card_uid': DARK_ENERGY, 'serial': 90})
        hand = project_semantic_frame(frame, uids)
        self.assertNotEqual(hand.frame_i32[32:64], changed.frame_i32[32:64])
        frame['options'].reverse()
        for index, option in enumerate(frame['options']): option['index'] = index
        reorder = project_semantic_frame(frame, uids)
        self.assertEqual(hand.option_i32, reorder.option_i32)
        self.assertEqual(hand.semantic_keys, reorder.semantic_keys)
        self.assertEqual(hand.row_to_current_index, tuple(4-i for i in reorder.row_to_current_index))

    def test_privacy_unknown_identity_and_profile_version(self):
        from scripts.ai.ptcgdap.semantic_model_profile import project_semantic_frame, PROFILE_ID
        from scripts.ai.ptcgdap.ptcgai_model_package import tensor_profile_document
        frame = _frame(); uids = [GRIMMSNARL, MORGREM, DARK_ENERGY]
        frame['public_state']['opponent']['hand'] = ['SECRET']
        with self.assertRaisesRegex(ValueError, 'public_frame'): project_semantic_frame(frame, uids)
        with self.assertRaisesRegex(ValueError, 'unknown_uid'): project_semantic_frame(_frame(), [])
        old = tensor_profile_document(); new = tensor_profile_document(PROFILE_ID)
        self.assertEqual(old['frame_width'], 24)
        self.assertEqual(new['frame_width'], 128)
        self.assertNotEqual(new['profile_id'], old['profile_id'])

    def test_base_frontier_protects_forced_tiers_veto_and_transactions(self):
        from scripts.ai.ptcgdap.semantic_model_profile import base_model_frontier
        frame = _frame(); frame['select_semantics'].update(min_count=1, max_count=1)
        frame['prompt_kind']='main'
        for option in frame['options']: option['kind']='play_trainer'
        args = dict(frame=frame, selected=[1], tiers={i: [0] for i in range(5)},
                    vetoed=[4], mandatory=[], terminal=[], evaluated={}, audit={})
        result = base_model_frontier(**args)
        self.assertEqual(result['indexes'], [0,1,2,3])
        self.assertTrue(result['enabled'])
        args['tiers'][0] = [1]
        self.assertEqual(base_model_frontier(**args)['indexes'], [1,2,3])
        for override in ({'mandatory':[1]}, {'terminal':[1]}, {'evaluated':{'selection_quotas':{DARK_ENERGY:1}}},
                         {'audit':{'turn_contract':{'route_authority_applied':True}}},
                         {'audit':{'turn_transaction':{'selected_transaction_id':'bound'}}}):
            result = base_model_frontier(**{**args, **override})
            self.assertFalse(result['enabled']); self.assertEqual(result['indexes'], [1])
        frame['select_semantics']['max_count'] = 2
        self.assertFalse(base_model_frontier(**args)['enabled'])

    def test_base_runtime_emits_frontier_without_changing_teacher(self):
        from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler, CompetitivePolicyV2Runtime
        frame = _frame(); frame['select_semantics'].update(min_count=1, max_count=1)
        policy = CompetitivePolicyV2Compiler.compile_local_uid(_adapter(), allowed_card_uids={GRIMMSNARL,MORGREM,DARK_ENERGY}).policy
        result = CompetitivePolicyV2Runtime.decide(policy, frame)
        self.assertTrue(result.accepted)
        self.assertIn(result.selected_indexes[0], result.model_frontier['indexes'])

    def test_untrained_effect_target_is_explicit_rule_lane(self):
        from scripts.ai.ptcgdap.semantic_model_profile import base_model_frontier
        frame = _frame(); frame['prompt_kind']='main';frame['select_semantics'].update(min_count=1,max_count=1)
        for option in frame['options']:option['kind']='effect_target'
        result=base_model_frontier(frame=frame,selected=[1],tiers={i:[0] for i in range(5)},vetoed=[],mandatory=[],terminal=[],evaluated={},audit={})
        self.assertFalse(result['enabled'])
        self.assertEqual(result['reason'],'unsupported_learning_context')

    def test_final_prize_threshold_and_energy_are_public_facts(self):
        from scripts.ai.ptcgdap.semantic_model_profile import base_model_frontier, project_semantic_frame
        frame = _frame(); frame['select_semantics'].update(min_count=1,max_count=1)
        frame['prompt_kind']='main'
        for option in frame['options']: option['kind']='play_trainer'
        args = dict(frame=frame,selected=[1],tiers={i:[0] for i in range(5)},vetoed=[],mandatory=[],terminal=[],evaluated={},audit={})
        attack = frame['options'][0]
        attack.update(kind='attack',projected_knockout=True,target_prize_value=2)
        frame['public_state']['self']['prizes_remaining']=3
        self.assertTrue(base_model_frontier(**args)['enabled'])
        frame['public_state']['self']['prizes_remaining']=2
        self.assertEqual(base_model_frontier(**args)['reason'],'terminal_attack')
        # A single public energy change is represented, without a hidden state input.
        clean = _frame(); uids=[GRIMMSNARL,MORGREM,DARK_ENERGY]
        before = project_semantic_frame(clean,uids)
        clean['public_state']['self']['active'][0]['attached_energy_count'] += 1
        clean['public_state']['self']['active'][0]['attached_energy_uids'].append(DARK_ENERGY)
        after = project_semantic_frame(clean,uids)
        self.assertEqual(after.frame_i32[11],before.frame_i32[11]+1)


if __name__ == '__main__': unittest.main()
