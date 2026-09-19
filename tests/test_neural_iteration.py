import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tests.test_neural_dataset import fixture, UIDS


class NeuralIterationTests(unittest.TestCase):
    def test_native_runtime_is_a_copy_and_does_not_track_source_edits(self):
        from tools.local_engine_bench import copy_native_runtime
        with tempfile.TemporaryDirectory() as temp:
            game=Path(temp)/'game';runtime=Path(temp)/'runtime'
            (game/'native/plugin/build').mkdir(parents=True);runtime.mkdir()
            source=game/'native/plugin/loader.gdextension';source.write_text('original')
            (game/'native/plugin/build/cache.bin').write_bytes(b'build cache')
            copy_native_runtime(game,runtime)
            source.write_text('changed by another task')
            self.assertEqual((runtime/'native/plugin/loader.gdextension').read_text(),'original')
            self.assertFalse((runtime/'native/plugin/build').exists())
            self.assertFalse((runtime/'native').is_junction())

    def test_mixed_match_accepts_only_teacher_seat_and_mirror_accepts_both(self):
        from ptcg_strategy_forge.neural_dataset import teacher_seats
        g=dict(candidate_sha256='A'*64,opponent_sha256='B'*64,candidate_seat=1)
        self.assertEqual(teacher_seats(g,'A'*64),{1})
        self.assertEqual(teacher_seats({**g,'opponent_sha256':'A'*64},'A'*64),{0,1})
        with self.assertRaisesRegex(ValueError,'teacher_identity'):teacher_seats(g,'B'*64)
        with self.assertRaises(ValueError):teacher_seats({**g,'candidate_seat':True},'A'*64)

    def test_copy_equivalence_keeps_target_entity_and_action_context(self):
        from ptcg_strategy_forge.neural_dataset import equivalent_hand_copy_indexes
        f={'seat':0,'public_state':{'self':{'hand':[{'serial':1,'local_card_uid':'ENERGY'},{'serial':2,'local_card_uid':'ENERGY'}]}},
           'options':[dict(index=0,kind='attach_energy',card_serial=1,card_uid='ENERGY',target_entity_serial=10),
                      dict(index=1,kind='attach_energy',card_serial=2,card_uid='ENERGY',target_entity_serial=10),
                      dict(index=2,kind='attach_energy',card_serial=2,card_uid='ENERGY',target_entity_serial=11)]}
        self.assertEqual(equivalent_hand_copy_indexes(f,[0,1,2],0),[0,1])
        reversed_frame=copy.deepcopy(f);reversed_frame['options'].reverse()
        for i,o in enumerate(reversed_frame['options']):o['index']=i
        self.assertEqual(equivalent_hand_copy_indexes(reversed_frame,[0,1,2],2),[1,2])
        self.assertEqual(equivalent_hand_copy_indexes(f,[0,2],0),[0])
        f['options'][0]['kind']='ability';f['options'][1]['kind']='ability'
        self.assertEqual(equivalent_hand_copy_indexes(f,[0,1,2],0),[0])
        f['options'][0]['kind']='attach_energy';f['options'][1]['kind']='attach_energy'
        f['public_state']['self']['hand'][1]['local_card_uid']='DIFFERENT'
        self.assertEqual(equivalent_hand_copy_indexes(f,[0,1,2],0),[0])

    def test_bench_exact_fixture_opponents_are_admitted_without_changing_product_gate(self):
        from tools.local_engine_bench import build_match_schedule
        def package(path,expected=None):
            spec=dict(path=path,sha256=path*64,id=path,requires_model=False,mode='development_exact_fixture')
            return spec,dict(package_id=path,package_version='1',archive_sha256=path*64)
        with tempfile.TemporaryDirectory() as temp:
            original=Path(temp)/'development-gate-original.txt';original.write_text('const CANDIDATES := [\n]\n')
            plan=dict(candidate='A',candidate_sha256='A'*64,seeds=[1],opponents=[dict(path='A',sha256='A'*64),dict(path='B',sha256='B'*64)])
            with patch('tools.local_engine_bench.package_spec',side_effect=package):
                candidate,games,gate=build_match_schedule(Path(temp),plan)
            self.assertEqual(len(games),4)
            self.assertEqual(gate.count('"archive_sha256": "'+'A'*64+'"'),1)
            self.assertIn('B'*64,gate)
            self.assertEqual(original.read_text(),'const CANDIDATES := [\n]\n')


if __name__=='__main__':unittest.main()
