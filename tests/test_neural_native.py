import copy
import unittest

from tests.test_competitive_forge_v2 import _frame


class NeuralNativeTests(unittest.TestCase):
    def test_native_projection_rebinds_semantics_after_reordering(self):
        from ptcg_strategy_forge.neural_native import project_native_frame
        frame = _frame()
        allowed = {o[k] for o in frame['options'] for k in ('card_uid', 'source_uid', 'target_uid') if o.get(k)}
        original = copy.deepcopy(frame)
        a = project_native_frame(frame, allowed)
        frame['options'].reverse()
        for i, option in enumerate(frame['options']): option['index'] = i
        b = project_native_frame(frame, allowed)
        self.assertEqual(a.option_i32, b.option_i32)
        self.assertEqual(a.semantic_keys, b.semantic_keys)
        self.assertEqual(a.row_to_current_index, tuple(len(frame['options'])-1-i for i in b.row_to_current_index))
        self.assertEqual(original['public_state'], frame['public_state'])

    def test_unknown_card_and_hidden_input_are_rejected(self):
        from ptcg_strategy_forge.neural_native import project_native_frame
        with self.assertRaisesRegex(ValueError, 'unknown_uid'):
            project_native_frame(_frame(), set())
        frame = _frame(); frame['public_state']['opponent']['hand'] = ['SECRET']
        with self.assertRaisesRegex(ValueError, 'public_frame'):
            project_native_frame(frame, {'CSVE1C_DAR', 'CSV10C_148'})

    def test_native_projection_does_not_invent_board_information(self):
        from ptcg_strategy_forge.neural_native import project_native_frame
        frame = _frame()
        allowed = {o[k] for o in frame['options'] for k in ('card_uid', 'source_uid', 'target_uid') if o.get(k)}
        a = project_native_frame(frame, allowed)
        frame['public_state']['self']['active'][0]['remaining_hp'] -= 10
        b = project_native_frame(frame, allowed)
        self.assertEqual(a.frame_i32, b.frame_i32)
        self.assertEqual(a.option_i32, b.option_i32)

    def test_frontier_requires_qualified_source_not_teacher_ranking(self):
        from ptcg_strategy_forge.neural_native import native_frontier
        self.assertIsNone(native_frontier({'base_result': {'ranked_indexes': [0,1]}}, 2))
        base = {'base_result': {'node_audit': [{'operator': 'base_veto', 'output_indexes': [1]}]}}
        self.assertEqual(native_frontier(base, 2), [1])
        for indexes in ([1,1], [2], [True], ['0']):
            base['base_result']['node_audit'][0]['output_indexes'] = indexes
            with self.assertRaisesRegex(ValueError, 'frontier_invalid'): native_frontier(base, 2)


if __name__ == '__main__': unittest.main()
