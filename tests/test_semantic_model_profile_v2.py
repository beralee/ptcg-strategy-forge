import copy
import unittest

from tests.test_competitive_forge_v2 import _frame, _option, _slot, GRIMMSNARL, MORGREM, DARK_ENERGY
from scripts.ai.ptcgdap import semantic_model_profile as profile


V2 = 'ptcgdap_local_semantic_actor_i32_v2'
UIDS = [GRIMMSNARL, MORGREM, DARK_ENERGY]


def attachment_frame():
    frame = _frame()
    frame['prompt_kind'] = 'main'
    frame['select_semantics'].update(min_count=1, max_count=1)
    a = _slot(21, MORGREM, 0, 2)
    a.update(entity_serial=3, appeared_this_turn=False)
    b = copy.deepcopy(a)
    b.update(serial=22, entity_serial=4, appeared_this_turn=True)
    frame['public_state']['self']['bench'] = [a, b]
    options = []
    for i, target in enumerate([a, b]):
        o = _option(i, card_uid=DARK_ENERGY)
        o.update(kind='attach_energy', card_serial=1000,
                 target_uid=MORGREM, target_serial=target['serial'],
                 target_entity_serial=target['entity_serial'])
        options.append(o)
    frame['options'] = options
    return frame


def row(tensors, index):
    r = tensors.current_index_to_row[index]
    return tensors.option_i32[r], tensors.option_presence_i32[r]


class SemanticModelProfileV2Tests(unittest.TestCase):
    def project(self, frame):
        return profile.project_semantic_frame(frame, UIDS, profile_id=V2)

    def test_workspace_uses_manifest_profile(self):
        import json,tempfile
        from pathlib import Path
        from ptcg_strategy_forge.sdk import StrategyWorkspace
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'package/deck').mkdir(parents=True);(root/'package/model').mkdir()
            (root/'package/strategy_package.json').write_text(json.dumps({'policy':{'policy_mode':'rules_with_model'}}))
            (root/'package/deck/deck_manifest.json').write_text(json.dumps({'cards':[{'local_card_uid':u} for u in UIDS]}))
            (root/'package/model/model_manifest.json').write_text(json.dumps({'tensor_profile':{'profile_id':V2}}))
            (root/'frame.json').write_text(json.dumps(attachment_frame()))
            result=StrategyWorkspace(root).model.tensorize('frame.json')
            projected=json.loads(Path(result['output']).read_bytes())
            self.assertEqual(projected['profile_id'],V2)
            self.assertEqual(len(projected['frame_i32'][0]),416)

    def test_newly_played_attachment_targets_are_distinguishable(self):
        frame = attachment_frame()
        legacy = profile.project_semantic_frame(frame, UIDS)
        self.assertEqual(row(legacy, 0), row(legacy, 1))
        upgraded = self.project(frame)
        self.assertNotEqual(row(upgraded, 0), row(upgraded, 1))
        self.assertEqual(row(upgraded, 0)[0][33], 0)
        self.assertEqual(row(upgraded, 1)[0][33], 1)

    def test_unknown_age_is_not_false(self):
        frame = attachment_frame()
        del frame['public_state']['self']['bench'][0]['appeared_this_turn']
        t = self.project(frame)
        self.assertEqual(row(t, 0)[1][33], 0)
        self.assertEqual(row(t, 1)[1][33], 1)

    def test_old_contract_and_features_remain_exact(self):
        from scripts.ai.ptcgdap.ptcgai_model_package import tensor_profile_document
        frame = attachment_frame()
        before = profile.project_semantic_frame(frame, UIDS)
        upgraded = self.project(frame)
        after = profile.project_semantic_frame(frame, UIDS)
        self.assertEqual(before, after)
        self.assertEqual(upgraded.frame_i32[:128], before.frame_i32)
        self.assertEqual(upgraded.frame_presence_i32[:128], before.frame_presence_i32)
        self.assertEqual(tensor_profile_document(profile.PROFILE_ID)['frame_width'], 128)
        self.assertEqual(tensor_profile_document(V2)['frame_width'], 416)
        self.assertEqual(tensor_profile_document(V2)['option_width'], 48)

    def test_option_reordering_rebinds_same_features(self):
        frame = attachment_frame()
        a = self.project(frame)
        frame['options'].reverse()
        for i, option in enumerate(frame['options']): option['index'] = i
        b = self.project(frame)
        self.assertEqual(a.frame_i32, b.frame_i32)
        self.assertEqual(a.option_i32, b.option_i32)
        self.assertEqual(a.semantic_keys, b.semantic_keys)
        self.assertEqual(a.row_to_current_index, tuple(1-i for i in b.row_to_current_index))

    def test_foreign_public_identity_is_distinguished(self):
        frame = attachment_frame()
        frame['public_state']['opponent']['active'] = [_slot(81, 'CSV1C_001', 1, 2)]
        a = self.project(frame)
        frame['public_state']['opponent']['active'][0]['local_card_uid'] = 'CSV1C_002'
        b = self.project(frame)
        self.assertNotEqual(a.frame_i32, b.frame_i32)

    def test_evolved_card_identity_is_not_replaced_by_target(self):
        frame = attachment_frame()
        frame['options'][0].update(kind='evolve', card_uid=GRIMMSNARL)
        t = self.project(frame)
        self.assertEqual(row(t, 0)[0][32], sorted(UIDS).index(GRIMMSNARL)+1)

    def test_unknown_owned_evolution_card_fails_closed(self):
        frame = attachment_frame()
        frame['options'][0].update(kind='evolve', card_uid='UNKNOWN_001')
        with self.assertRaisesRegex(ValueError, 'model_unknown_uid'):
            self.project(frame)

    def test_private_and_unknown_profile_fail_closed(self):
        frame = attachment_frame()
        frame['public_state']['opponent']['hand'] = ['SECRET']
        with self.assertRaisesRegex(ValueError, 'public_frame'): self.project(frame)
        with self.assertRaisesRegex(ValueError, 'tensor_profile_invalid'):
            profile.project_semantic_frame(attachment_frame(), UIDS, profile_id='unknown')

    def test_padding_and_board_capacity_are_explicit(self):
        t = self.project(attachment_frame())
        self.assertEqual(len(t.frame_i32), 416)
        self.assertEqual(len(t.option_i32[-1]), 48)
        self.assertFalse(any(t.option_presence_i32[-1]))
        frame = attachment_frame()
        frame['public_state']['self']['bench'] *= 5
        with self.assertRaises(ValueError): self.project(frame)


if __name__ == '__main__': unittest.main()
