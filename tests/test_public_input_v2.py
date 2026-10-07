import copy
import unittest
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from scripts.ai.ptcgdap.public_input_v2 import (
    PublicInputV2, PublicEventMemory, fact, validate_payload, contract,
)

from tools.ptcgdap.public_decision_contract import decision_fixture
from tools.ptcgdap.build_competitive_policy_v2_contract import _frame, _option


class PublicInputV2Tests(unittest.TestCase):
    def test_saved_evidence_matches_qualified_source_hashes(self):
        import hashlib
        root = Path(__file__).resolve().parents[1]
        receipt = json.loads((root / 'evidence/public-input-v2/engine-acceptance.json').read_bytes())
        self.assertEqual(receipt['status'], 'passed')
        for name, expected in receipt['files'].items():
            self.assertEqual(hashlib.sha256((root / name.replace('\\', '/')).read_bytes()).hexdigest().upper(), expected)
        for name, key in [('engine-snapshots.json', 'engine_evidence_sha256'),
                          ('engine-source-manifest.json', 'engine_source_manifest_sha256')]:
            self.assertEqual(hashlib.sha256((root / 'evidence/public-input-v2' / name).read_bytes()).hexdigest().upper(), receipt[key])
        self.assertEqual(hashlib.sha256((root / 'contracts/ptcgdap/public_input_v2.json').read_bytes()).hexdigest().upper(), receipt['contract_sha256'])

    def test_sdk_facade_and_coverage_are_immutable(self):
        from ptcg_strategy_forge import PublicDecisionView
        row = self.witnessed()
        view = PublicDecisionView(row['frame'], public_semantics_v2=row['supplement'])
        self.assertTrue(view.capabilities['public_input_v2'])
        self.assertTrue(view.ability_ledger())
        self.assertFalse(view.input_coverage()['training_ready'])
        with self.assertRaises(TypeError): view.ability_ledger()[0]['player'] = 7
        coverage = view.public_input_v2.coverage()
        coverage['capabilities']['supported_effect_types'].clear()
        self.assertTrue(view.public_input_v2.coverage()['capabilities']['supported_effect_types'])

    def test_unknown_event_enum_and_phase_are_rejected(self):
        for field, value in [('type', 'private_future_event'), ('phase', 10)]:
            history = self.history()
            history['events'][0][field] = value
            with self.assertRaisesRegex(ValueError, 'history_shape'): PublicEventMemory().ingest(history)

    def frame(self):
        return decision_fixture(_option, _frame)

    def witnessed(self, label='normal'):
        evidence = Path(__file__).resolve().parents[1] / 'evidence/public-input-v2/engine-snapshots.json'
        rows = json.loads(evidence.read_bytes())['rows']
        return copy.deepcopy(next(r for r in rows if r['label'] == label))

    def history(self, seqs=(1, 2), cursor=2, first=1):
        return dict(stream='m:view:0', match='m', seat=0, cursor=cursor, first_available=first,
                    complete=True, scope='engine_logged_actions', events=[
                        dict(seq=i, turn=3, player=1, phase=1, type='draw_card', visibility='all', visible_to=None,
                             count=fact(1), cards=fact(status='unknown', reason='opponent_hidden_cards'),
                             knowledge='invalidate_hidden_associations') for i in seqs])

    def test_all_saved_engine_observations_validate(self):
        evidence = Path(__file__).resolve().parents[1] / 'evidence/public-input-v2/engine-snapshots.json'
        for row in json.loads(evidence.read_bytes())['rows']:
            with self.subTest(row=row['label']):
                value = PublicInputV2.capture(row['frame'], row['supplement'])
                self.assertFalse(value.coverage()['training_ready'])
                self.assertEqual(value.document(), PublicInputV2.capture(value.base.frame(), value.payload()).document())

    def test_immutable_and_exact_zero(self):
        row = self.witnessed('independent-native-used')
        value = PublicInputV2.capture(row['frame'], row['supplement'])
        row['supplement']['abilities'].clear()
        query = value.abilities()
        self.assertTrue(query)
        query.clear()
        self.assertTrue(value.abilities())
        self.assertEqual(next(a for a in value.abilities() if a['source_uid'] == 'CS4DaC_137')['quota']['remaining']['value'], 0)

    def test_payload_binding_rejects_every_stale_component(self):
        for key in ('window_id', 'public_observation_hash', 'sequence', 'seat'):
            row = self.witnessed()
            old = row['supplement']['binding'][key]
            row['supplement']['binding'][key] = 'E' * 64 if isinstance(old, str) else old + 1
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'public_input_v2_binding'):
                PublicInputV2.capture(row['frame'], row['supplement'])

    def test_unknown_fields_hidden_ids_and_callbacks_rejected(self):
        for path in ('root', 'ability', 'event', 'entity'):
            for key in ('private_rng', 'callback', 'card_instance_id', 'ticket'):
                row = self.witnessed('independent-native-used')
                dest = {'root': row['supplement'], 'ability': row['supplement']['abilities'][0],
                        'event': row['supplement']['history']['events'][0], 'entity': row['supplement']['entities'][0]}[path]
                dest[key] = 123
                with self.subTest(path=path, key=key), self.assertRaisesRegex(ValueError, 'public_input_v2_shape'):
                    PublicInputV2.capture(row['frame'], row['supplement'])

    def test_unknown_never_silently_coerced(self):
        row = self.witnessed()
        row['supplement']['abilities'][0]['quota']['remaining'] = fact(status='unknown', reason='source_missing')
        value = PublicInputV2.capture(row['frame'], row['supplement'])
        self.assertIsNone(value.abilities()[0]['quota']['remaining']['value'])
        self.assertTrue(value.coverage()['missing'])
        with self.assertRaisesRegex(ValueError, 'public_input_v2_incomplete'):
            value.require_training('public-state-complete-v2')

    def test_payload_cannot_self_certify_complete_training(self):
        row = self.witnessed()
        row['supplement']['gaps'] = []
        value = PublicInputV2.capture(row['frame'], row['supplement'])
        self.assertIn('complete_training_profile_not_qualified', value.coverage()['gaps'])
        self.assertFalse(value.coverage()['training_ready'])

    def test_invalid_tagged_values_fail_closed(self):
        for status, value in [('known', None), ('unknown', 0), ('not_applicable', False), ('unlimited', None)]:
            row = self.witnessed()
            row['supplement']['abilities'][0]['disabled'] = fact(value, status=status, reason='test')
            with self.subTest(status=status), self.assertRaises(ValueError):
                PublicInputV2.capture(row['frame'], row['supplement'])

    def test_wrong_public_source_and_visibility_rejected(self):
        row = self.witnessed()
        row['supplement']['abilities'][0]['source_uid'] = 'HIDDEN_001'
        with self.assertRaisesRegex(ValueError, 'ability_source'):
            PublicInputV2.capture(row['frame'], row['supplement'])
        history = self.history()
        history['events'][0].update(visibility='seat', visible_to=1)
        with self.assertRaisesRegex(ValueError, 'visibility'): PublicEventMemory().ingest(history)

    def test_quota_arithmetic_and_identity_negatives(self):
        for mutation, code in [
            (lambda p: p['abilities'][0]['quota']['remaining'].__setitem__('value', 9), 'quota_arithmetic'),
            (lambda p: p['abilities'].append(copy.deepcopy(p['abilities'][0])), 'duplicate_identity'),
            (lambda p: p['abilities'][0].__setitem__('entity', 99999), 'ability_entity'),
            (lambda p: p['entities'].pop(), 'entity'),
        ]:
            row = self.witnessed()
            mutation(row['supplement'])
            with self.subTest(code=code), self.assertRaisesRegex(ValueError, 'public_input_v2_' + code):
                PublicInputV2.capture(row['frame'], row['supplement'])

    def test_nonmain_and_opponent_availability_cannot_be_false_from_absence(self):
        row = self.witnessed('interaction-window')
        self.assertEqual(row['supplement']['abilities'][0]['main_availability']['status'], 'unknown')
        row['supplement']['abilities'][0]['main_availability'] = fact('not_offered')
        with self.assertRaisesRegex(ValueError, 'nonmain_availability'):
            PublicInputV2.capture(row['frame'], row['supplement'])
        row = self.witnessed('opponent-turn')
        opponent = next(a for a in row['supplement']['abilities'] if a['player'] != row['frame']['seat'])
        opponent['main_availability'] = fact('offered')
        with self.assertRaisesRegex(ValueError, 'opponent_availability'):
            PublicInputV2.capture(row['frame'], row['supplement'])

    def test_reorder_v2_semantics_and_base_authority(self):
        row = self.witnessed()
        first = PublicInputV2.capture(row['frame'], row['supplement'])
        row['frame']['options'].reverse()
        for i, option in enumerate(row['frame']['options']): option['index'] = i
        second = PublicInputV2.capture(row['frame'], row['supplement'])
        self.assertEqual(first.document(), second.document())
        from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler
        from tools.ptcgdap.public_decision_contract import decision_cases
        from tools.ptcgdap.build_competitive_policy_v2_contract import _sample_policy
        case = decision_cases(_sample_policy, _option, _frame)[0]
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(case['policy'], allowed_card_uids=set(case['allowed_card_uids']))
        value = PublicInputV2.capture(case['frame'])
        self.assertEqual(value.decide(compiled.policy, mandatory_indexes=[1]).selected_indexes, [1])
        self.assertEqual(value.decide(compiled.policy, terminal_indexes=[0]).selected_indexes, [0])

    def test_attack_cost_receipt_is_not_damage_or_legality(self):
        row = self.witnessed()
        value = PublicInputV2.capture(row['frame'], row['supplement'])
        entities = row['supplement']['entities']
        result = value.evaluate_attack(entities[0]['entity'], 0, entities[-1]['entity'])
        self.assertFalse(result['legal_authority'])
        self.assertFalse(result['simulation_supported'])
        self.assertEqual(result['damage']['status'], 'unsupported')
        self.assertEqual(result['binding'], value.base.binding)
        with self.assertRaisesRegex(ValueError, 'attack_identity'): value.evaluate_attack(999, 0, 1)

    def test_memory_dedup_restore_and_gap(self):
        memory = PublicEventMemory()
        self.assertEqual(memory.ingest(self.history())['accepted'], 2)
        self.assertEqual(memory.ingest(self.history())['accepted'], 0)
        restored = PublicEventMemory.restore(memory.export())
        self.assertEqual(restored.export(), memory.export())
        self.assertTrue(restored.ingest(self.history((4,), 4, 4))['gap'])
        self.assertFalse(restored.complete)
        self.assertFalse(restored.ingest(self.history((5,), 5, 5))['complete'])

    def test_memory_survives_contiguous_ring_truncation_and_old_duplicates(self):
        memory = PublicEventMemory()
        memory.ingest(self.history())
        delta = self.history((3,), 3, 3)
        delta['complete'] = False
        self.assertTrue(memory.ingest(delta)['complete'])
        duplicate = memory.ingest(self.history())
        self.assertEqual(duplicate['accepted'], 0)
        self.assertFalse(duplicate['gap'])
        self.assertTrue(duplicate['complete'])

    def test_conflicting_duplicate_atomicity_and_stream_isolation(self):
        memory = PublicEventMemory()
        memory.ingest(self.history())
        before = memory.export()
        duplicate = self.history()
        duplicate['events'][0]['count']['value'] = 2
        with self.assertRaisesRegex(ValueError, 'event_conflict'): memory.ingest(duplicate)
        self.assertEqual(before, memory.export())
        wrong = self.history()
        wrong['seat'] = 1
        with self.assertRaisesRegex(ValueError, 'stream_mismatch'): memory.ingest(wrong)

    def test_history_order_cursor_bounds_and_hidden_cards(self):
        for history in (self.history((2, 1)), self.history((1, 1)), self.history((1, 3)), self.history((), 0, 2)):
            with self.assertRaisesRegex(ValueError, 'history_sequence'): PublicEventMemory().ingest(history)
        for event_type in ('draw_card', 'take_prize'):
            history = self.history()
            history['events'][0].update(type=event_type, cards=fact(['CSV8C_159']))
            with self.assertRaisesRegex(ValueError, 'hidden_cards'): PublicEventMemory().ingest(history)

    def test_reveal_knowledge_invalidated_on_shuffle(self):
        history = self.history((1,), 1)
        history['events'][0].update(type='public_reveal', cards=fact(['CSV8C_159']), knowledge='public_reveal')
        memory = PublicEventMemory()
        memory.ingest(history)
        self.assertEqual(len(memory.reveals), 1)
        shuffle = self.history((2,), 2, 2)
        shuffle['events'][0].update(type='shuffle_deck')
        memory.ingest(shuffle)
        self.assertEqual(memory.reveals, [])

    def test_card_serials_are_binding_only(self):
        row = self.witnessed()
        doc = PublicInputV2.capture(row['frame'], row['supplement']).document()
        text = json.dumps(doc)
        for field in ('"serial":', '"card_serial":', '"source_serial":', '"target_serial":'):
            self.assertNotIn(field, text)

    def test_contract_is_generated_and_sdk_api_is_discoverable(self):
        path = Path(__file__).resolve().parents[1] / 'contracts/ptcgdap/public_input_v2.json'
        self.assertEqual(json.loads(path.read_bytes()), contract())
        from ptcg_strategy_forge import PublicInputV2 as Export, PublicEventMemory as Memory
        self.assertIs(Export, PublicInputV2)
        self.assertIs(Memory, PublicEventMemory)

    def test_unlimited_and_not_applicable_are_not_unknown(self):
        value = self.witnessed('unlimited-used-twice')['supplement']
        ability = next(a for a in value['abilities'] if a['source_uid'] == 'CSV3C_042')
        self.assertEqual(ability['quota']['limit']['status'], 'unlimited')
        self.assertEqual(ability['quota']['used']['status'], 'history_incomplete')
        self.assertEqual(ability['quota']['group']['status'], 'not_applicable')

    def test_machine_input_identical_for_hidden_identity_pair(self):
        a, b = self.witnessed('turn-reset'), self.witnessed('hidden-mutated')
        self.assertEqual(PublicInputV2.capture(a['frame'], a['supplement']).document(),
                         PublicInputV2.capture(b['frame'], b['supplement']).document())

    def test_legacy_is_explicitly_incomplete(self):
        from scripts.ai.ptcgdap.public_input_v2 import PublicInputV2
        value = PublicInputV2.capture(self.frame())
        self.assertEqual(value.document()['semantics']['status'], 'unsupported')
        with self.assertRaisesRegex(ValueError, 'public_input_v2_incomplete'):
            value.require_training('public-state-complete-v2')

    def test_legacy_reordering_preserves_model_semantics(self):
        from scripts.ai.ptcgdap.public_input_v2 import PublicInputV2
        frame = self.frame()
        first = PublicInputV2.capture(frame)
        frame['options'].reverse()
        for i, row in enumerate(frame['options']):
            row['index'] = i
        self.assertEqual(first.document(), PublicInputV2.capture(frame).document())

    def test_unknown_is_not_zero_and_bad_tags_rejected(self):
        from scripts.ai.ptcgdap.public_input_v2 import fact, validate_fact
        self.assertNotEqual(fact(0), fact(status='unknown', reason='source_missing'))
        self.assertNotEqual(fact(False), fact(status='not_applicable', reason='passive'))
        with self.assertRaisesRegex(ValueError, 'public_input_v2_fact'):
            validate_fact(dict(status='unknown', value=0, reason='source_missing', source='engine'), {'type': 'integer'})


if __name__ == '__main__':
    unittest.main()
