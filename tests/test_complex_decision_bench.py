import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests.test_competitive_forge_v2 import _frame, _adapter, GRIMMSNARL, MORGREM, DARK_ENERGY
from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler
from ptcg_strategy_forge.decision_bench import bind_frame, run_chain, load_steps, run_bench


def scenario(sequence=1):
    frame = _frame(); frame['sequence'] = sequence
    frame['select_semantics'].update(min_count=1, max_count=1)
    # Stable physical card 1001 must follow its new current-window index.
    frame['options'][0]['card_uid'] = GRIMMSNARL
    frame['options'] = frame['options'][:2]
    bind_frame(frame)
    return dict(document_type='ptcg_strategy_forge_competitive_scenario_v2', schema_version=2,
                scenario_id='chain-step-' + str(sequence), frame=frame,
                expected_selected_indexes=[1], base_authority=dict(mandatory_indexes=[], terminal_indexes=[],
                base_hard_tiers=[dict(index=0,tier=[0]),dict(index=1,tier=[0])], base_vetoed_indexes=[]))


class ComplexDecisionBenchTests(unittest.TestCase):
    def setUp(self):
        adapter = _adapter(); adapter['count_rules'] = []
        result = CompetitivePolicyV2Compiler.compile_local_uid(adapter, allowed_card_uids={GRIMMSNARL,MORGREM,DARK_ENERGY})
        self.assertTrue(result.accepted)
        self.policy = result.policy

    def test_chain_rebinds_each_step_and_reverse_remaps_authority(self):
        steps = [dict(scenario=scenario(1), expect_error=''), dict(scenario=scenario(2), expect_error='')]
        for reverse, index in ((False,1),(True,0)):
            result = run_chain(self.policy, steps, reverse=reverse)
            self.assertTrue(result['passed'], result)
            self.assertEqual([x['selected_indexes'] for x in result['steps']], [[index],[index]])
        steps[0]['scenario']['base_authority']['mandatory_indexes'] = [0]
        steps[0]['scenario']['expected_selected_indexes'] = [0]
        result = run_chain(self.policy, steps, reverse=True)
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['steps'][0]['owner_layer'], 'mandatory')

    def test_wrong_prefix_stops_suffix(self):
        first = scenario(); first['expected_selected_indexes'] = [0]
        result = run_chain(self.policy, [dict(scenario=first,expect_error=''), dict(scenario=scenario(2),expect_error='')])
        self.assertFalse(result['passed'])
        self.assertEqual(len(result['steps']), 1)
        self.assertEqual(result['error_code'], 'decision_chain_expectation_failed')

    def test_stale_window_and_observation_tampering_rejected(self):
        step = dict(scenario=scenario(), expect_error='')
        result = run_chain(self.policy, [step, copy.deepcopy(step)])
        self.assertEqual(result['error_code'], 'decision_chain_stale_window')
        changed = copy.deepcopy(step); changed['scenario']['frame']['public_state']['opponent']['hand_count'] += 1
        result = run_chain(self.policy, [changed])
        self.assertEqual(result['error_code'], 'decision_chain_binding_mismatch')

    def test_private_field_is_rejected_without_echoing_it(self):
        s = scenario(); s['frame']['public_state']['opponent']['hand'] = ['SECRET_SENTINEL']
        bind_frame(s['frame'])
        result = run_chain(self.policy, [dict(scenario=s,expect_error='invalid_public_frame')])
        self.assertTrue(result['passed'], result)
        self.assertNotIn('SECRET_SENTINEL',json.dumps(result))

    def test_safe_paths_and_duplicate_steps(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); (root/'case.json').write_text(json.dumps(scenario()))
            steps=load_steps(root,[dict(path='case.json',expect_error='')])
            self.assertEqual(len(steps),1)
            for path in ('../case.json','/case.json','C:/case.json','dir\\case.json'):
                with self.assertRaisesRegex(ValueError,'decision_bench_path_invalid'):
                    load_steps(root,[dict(path=path,expect_error='')])
            with self.assertRaisesRegex(ValueError,'decision_bench_duplicate_step'):
                load_steps(root,[dict(path='case.json',expect_error='')]*2)

    def test_report_binds_unexecuted_suffix_fixtures(self):
        adapter = _adapter(); adapter['count_rules'] = []
        payloads = {'policy/adapter.json': adapter,
                    'deck/deck_manifest.json': {'cards': [{'local_card_uid': u} for u in (GRIMMSNARL,MORGREM,DARK_ENERGY)]}}
        package = SimpleNamespace(archive_sha256='A'*64, payload_bytes=lambda name: json.dumps(payloads[name]).encode())
        with tempfile.TemporaryDirectory() as temp, patch('ptcg_strategy_forge.decision_bench.AuthorStrategyPackageLoader') as loader:
            loader.return_value.load_path.return_value = package
            root = Path(temp)
            first = scenario(1); first['expected_selected_indexes'] = [0]
            second = scenario(2)
            (root/'first.json').write_text(json.dumps(first))
            (root/'second.json').write_text(json.dumps(second))
            suite = dict(document_type='forge_complex_decision_bench_v1',schema_version=1,
                         cases=[dict(id='chain',family='fresh',steps=[dict(path=p,expect_error='') for p in ('first.json','second.json')])])
            (root/'suite.json').write_text(json.dumps(suite))
            before = run_bench(root/'unused.ptcgai',root/'suite.json')
            second['expected_selected_indexes'] = [0]
            (root/'second.json').write_text(json.dumps(second))
            after = run_bench(root/'unused.ptcgai',root/'suite.json')
            self.assertEqual(before['results'][0]['executed_steps'],1)
            self.assertEqual(before['suite_sha256'],after['suite_sha256'])
            self.assertNotEqual(before['fixture_manifest_sha256'],after['fixture_manifest_sha256'])
            self.assertIn('second.json',before['fixture_manifest'])


if __name__ == '__main__':unittest.main()
