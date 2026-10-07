import copy
import json
from pathlib import Path
import unittest
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from scripts.ai.ptcgdap.public_input_v3 import PublicInputV3, PublicHistoryV3, contract


class PublicInputV3Tests(unittest.TestCase):
    def row(self, label='normal'):
        rows = json.loads((ROOT/'evidence/public-input-v3/engine-snapshots.json').read_bytes())['rows']
        return copy.deepcopy(next(r for r in rows if r['label'] == label))

    def value(self, label='normal'):
        row = self.row(label)
        return PublicInputV3.capture(row['frame'], row['supplement'])

    def test_every_real_snapshot_and_envelope_roundtrip(self):
        for row in json.loads((ROOT/'evidence/public-input-v3/engine-snapshots.json').read_bytes())['rows']:
            with self.subTest(label=row['label']):
                value = PublicInputV3.capture(row['frame'], row['supplement'])
                self.assertEqual(value.document(), PublicInputV3.capture(value.envelope()).document())

    def test_actual_envelope_reaches_sdk_queries_and_base(self):
        from ptcg_strategy_forge import PublicDecisionView, agent_observation
        from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler
        from tools.ptcgdap.build_competitive_policy_v2_contract import _sample_policy
        value = self.value()
        view = PublicDecisionView(value.envelope())
        self.assertTrue(view.capabilities['public_input_v3'])
        self.assertEqual(view.input_coverage()['profile'], 'ptcg-public-input-v3')
        self.assertTrue(view.effect_ledger())
        policy = _sample_policy()
        compiled = CompetitivePolicyV2Compiler.compile_local_uid(policy, allowed_card_uids={'SVI_003','M2_001','M2_002'})
        result = agent_observation(value.envelope(), compiled.policy, mandatory_indexes=[0])
        self.assertEqual(result, [0])
        for index in result: self.assertLess(index, len(value.base.frame()['options']))

    def test_mixed_versions_and_unknown_envelope_keys_rejected(self):
        from ptcg_strategy_forge import PublicDecisionView
        envelope = self.value().envelope()
        with self.assertRaisesRegex(ValueError, 'mixed_versions'):
            PublicDecisionView(envelope, public_semantics_v2={})
        envelope['ticket'] = 1
        with self.assertRaisesRegex(ValueError, 'envelope'): PublicInputV3.capture(envelope)

    def test_current_public_training_profile_has_positive_and_negative_gates(self):
        value = self.value()
        self.assertIs(value.require_training('public-observation-v3'), value)
        with self.assertRaisesRegex(ValueError, 'incomplete'): value.require_training('semantic-complete-v3')
        with self.assertRaisesRegex(ValueError, 'training_profile'): value.require_training('anything')

    def test_discard_search_allocation_contexts_are_engine_witnessed(self):
        payment = self.value('v3-ultra-ball-payment').interaction()
        search = self.value('v3-ultra-ball-search').interaction()
        first = self.value('v3-dragapult-allocation').interaction()
        second = self.value('v3-dragapult-allocation-remaining').interaction()
        self.assertEqual(payment['action_id'], search['action_id'])
        self.assertEqual(search['stage']['value'], 'search')
        self.assertFalse(search['cancel_allowed']['value'])
        self.assertEqual(search['cancel_semantics']['value'], 'decline_optional')
        self.assertEqual(first['remaining_damage_counters']['value'], 6)
        self.assertEqual(second['remaining_damage_counters']['value'], 4)
        self.assertEqual(first['action_id'], second['action_id'])

    def test_missing_action_log_moves_and_shuffles_are_present(self):
        draw = self.value('v3-direct-effect-draw').history()
        self.assertTrue(any(e['type']=='move' and e['from_zone']['value']=='deck' and e['to_zone']['value']=='hand' for e in draw['events']))
        shuffle = self.value('v3-direct-effect-shuffle').history()
        self.assertTrue(any(e['type']=='shuffle_deck' and e['origin']=='engine_shuffle' for e in shuffle['events']))

    def test_unlimited_usage_is_counted_by_real_commit_events(self):
        value = self.value('unlimited-used-twice')
        a = next(a for a in value.abilities() if a['source_uid']=='CSV3C_042')
        self.assertEqual(a['quota']['used']['value'], 2)
        self.assertEqual(a['quota']['remaining']['status'], 'unlimited')

    def test_effect_survivor_does_not_renumber(self):
        before = [e for e in self.value('v3-effect-instances').effects() if e['type']=='reduce_damage_next_turn']
        after = [e for e in self.value('v3-one-identical-effect-removed').effects() if e['type']=='reduce_damage_next_turn']
        self.assertEqual(len(before), 2)
        self.assertEqual(after[0]['id'], before[1]['id'])
        self.assertEqual(after[0]['identity_scope'], 'engine_instance')

    def test_history_snapshot_export_restore_and_duplicate(self):
        history = self.value('v3-ultra-ball-committed').history()
        memory = PublicHistoryV3()
        self.assertGreater(memory.ingest(history)['accepted'], 0)
        restored = PublicHistoryV3.restore(memory.export())
        self.assertEqual(restored.ingest(history)['accepted'], 0)
        self.assertEqual(memory.export(), restored.export())
        self.assertEqual(memory.snapshot, history['snapshot'])

    def test_gap_recovers_snapshot_but_not_missing_history(self):
        h = self.value('v3-ultra-ball-committed').history()
        h['events'] = h['events'][-1:]
        h['first_available'] = h['events'][0]['seq']
        h['complete'] = False
        memory = PublicHistoryV3()
        report = memory.ingest(h)
        self.assertTrue(report['gap'])
        self.assertTrue(report['snapshot_restored'])
        self.assertFalse(report['history_complete'])
        self.assertEqual(memory.snapshot, h['snapshot'])

    def test_false_complete_or_snapshot_cursor_is_rejected(self):
        for change in ('complete', 'cursor'):
            h = self.value('v3-ultra-ball-committed').history()
            if change=='complete': h['events']=h['events'][-1:]
            else: h['snapshot_cursor'] += 1
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'public_input_v3_'):
                PublicHistoryV3().ingest(h)

    def test_conflicting_duplicate_is_atomic(self):
        h = self.value('v3-ultra-ball-committed').history()
        memory = PublicHistoryV3(); memory.ingest(h); before=memory.export()
        h['events'][0]['turn'] += 1
        with self.assertRaisesRegex(ValueError, 'event_conflict'): memory.ingest(h)
        self.assertEqual(before, memory.export())

    def test_viewer_separation_and_private_zone_negatives(self):
        for label in ('opponent-private-prize','owner-visible-prize'):
            h = self.value(label).history()
            for zone in h['snapshot']:
                if zone['zone'] in ('deck','prizes') or (zone['zone']=='hand' and zone['player']!=h['seat']):
                    self.assertEqual(zone['cards']['status'], 'unknown')
        h = self.value().history()
        zone=next(z for z in h['snapshot'] if z['zone']=='deck')
        zone['cards'].update(status='known',value=['CSV8C_159'])
        with self.assertRaisesRegex(ValueError,'hidden_cards'): PublicHistoryV3().ingest(h)

    def test_restore_cannot_smuggle_private_zone_cards(self):
        m=PublicHistoryV3();m.ingest(self.value().history());saved=m.export()
        zone=next(z for z in saved['snapshot'] if z['zone']=='prizes')
        zone['cards'].update(status='known',value=['CSV8C_159'])
        with self.assertRaisesRegex(ValueError,'hidden_cards'): PublicHistoryV3.restore(saved)

    def test_restore_cannot_claim_complete_with_missing_dedup_history(self):
        m=PublicHistoryV3();m.ingest(self.value('v3-ultra-ball-committed').history());saved=m.export()
        saved['seen'].pop(next(iter(saved['seen'])))
        with self.assertRaisesRegex(ValueError,'memory_incomplete'): PublicHistoryV3.restore(saved)

    def test_incremental_packets_can_qualify_with_complete_local_memory(self):
        v=self.value('v3-ultra-ball-committed');m=PublicHistoryV3();m.ingest(v.history())
        envelope=v.envelope();h=envelope['input']['history']
        h['events']=h['events'][-1:];h['first_available']=h['events'][0]['seq'];h['complete']=False
        for key in ('snapshot','event_stream'):
            envelope['input']['capabilities'][key]['source']='reviewed_engine_transport'
        delta=PublicInputV3.capture(envelope)
        with self.assertRaisesRegex(ValueError,'incomplete'):delta.require_training('public-observation-v3')
        self.assertIs(delta.require_training('public-observation-v3',m),delta)

    def test_stream_and_stale_observation_rejected(self):
        v=self.value('v3-ultra-ball-committed');m=PublicHistoryV3();m.ingest(v.history())
        h=v.history();h['stream']+=':other'
        with self.assertRaisesRegex(ValueError,'stream_mismatch'):m.ingest(h)
        row=self.row();row['supplement']['binding']['sequence']+=1
        with self.assertRaises(ValueError):PublicInputV3.capture(row['frame'],row['supplement'])

    def test_same_visible_state_different_hidden_state_same_model_input(self):
        self.assertEqual(self.value('turn-reset').document(),self.value('hidden-mutated').document())

    def test_known_damage_is_bounded_and_current_binding_only(self):
        v=self.value('v3-journal-start')
        row=next(r for r in v.payload()['evaluations'] if r['damage_hp']['status']=='known')
        result=v.evaluate_attack(row['attacker'],row['attack_index'],row['target'])
        self.assertFalse(result['legal_authority'])
        self.assertFalse(result['simulation_supported'])
        self.assertEqual(result['result_kind'],'conditional')
        self.assertTrue(result['unresolved'])
        self.assertEqual(result['binding'],v.base.binding)

    def test_false_exact_damage_is_rejected(self):
        row=self.row('v3-journal-start')
        row['supplement']['evaluations'][0]['kind']='exact'
        with self.assertRaisesRegex(ValueError,'false_exact'): PublicInputV3.capture(row['frame'],row['supplement'])

    def test_reorder_does_not_change_semantics_or_selected_meaning(self):
        from ptcg_strategy_forge import agent_observation
        from scripts.ai.ptcgdap.competitive_policy_v2 import CompetitivePolicyV2Compiler
        from tools.ptcgdap.build_competitive_policy_v2_contract import _sample_policy
        a=self.value(); env=a.envelope();options=env['frame']['options'];options.reverse()
        for i,o in enumerate(options):o['index']=i
        b=PublicInputV3.capture(env)
        self.assertEqual(a.document(),b.document())
        p=_sample_policy()
        policy=CompetitivePolicyV2Compiler.compile_local_uid(p,allowed_card_uids={'SVI_003','M2_001','M2_002'}).policy
        old=agent_observation(a.envelope(),policy,mandatory_indexes=[0])[0]
        new=agent_observation(b.envelope(),policy,mandatory_indexes=[len(options)-1])[0]
        oa=a.base.frame()['options'][old];ob=b.base.frame()['options'][new]
        oa.pop('index');ob.pop('index');self.assertEqual(oa,ob)

    def test_unknown_and_private_field_injection_rejected_at_all_levels(self):
        for section in ('abilities','effects','evaluations','events'):
            r=self.row('v3-ultra-ball-committed')
            parent=r['supplement']['history']['events'][0] if section=='events' else r['supplement'][section][0]
            parent['private_rng']=123
            with self.subTest(section=section),self.assertRaisesRegex(ValueError,'shape'):
                PublicInputV3.capture(r['frame'],r['supplement'])

    def test_snapshot_queries_are_immutable(self):
        value=self.value();before=value.document();payload=value.payload();payload['effects'].clear()
        self.assertEqual(before,value.document())

    def test_legacy_missing_source_is_detectable(self):
        from tools.ptcgdap.public_decision_contract import decision_fixture
        from tools.ptcgdap.build_competitive_policy_v2_contract import _frame, _option
        value = PublicInputV3.capture(decision_fixture(_option, _frame))
        self.assertFalse(value.coverage()['supported'])
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            value.require_training('public-observation-v3')

    def test_protection_and_attack_lock_follow_real_engine_boundaries(self):
        a=self.value('v3-marker-protection-pending').effects()
        b=self.value('v3-marker-protection-effective').effects()
        c=self.value('v3-marker-protection-expired').effects()
        self.assertTrue(any(e['type']=='prevent_attack_damage_and_effects' and not e['condition_met']['value'] for e in a))
        self.assertTrue(any(e['type']=='prevent_attack_damage_and_effects' and e['condition_met']['value'] and e['expiry_player']['value']==1 for e in b))
        self.assertFalse(any(e['type']=='prevent_attack_damage_and_effects' and e['condition_met']['value'] for e in c))
        self.assertFalse(any(e['type']=='attack_lock_until_leave_active' for e in self.value('v3-marker-left-active').effects()))

    def test_bounce_retires_entity_but_preserves_shared_quota(self):
        before=next(a for a in self.value('v3-before-bounce').abilities() if a['source_uid']=='CSV8C_135')
        after=self.value('v3-reentered-field')
        self.assertNotIn(before['entity'],[e['entity'] for e in after.entities()])
        self.assertTrue(all(a['quota']['remaining']['value']==0 for a in after.abilities() if a['source_uid']=='CSV8C_135'))

    def test_real_engine_journal_ring_truncation(self):
        h=self.value('v3-history-ring-truncated').history()
        self.assertEqual((len(h['events']),h['cursor'],h['first_available']),(512,520,9))
        self.assertFalse(h['complete'])
        report=PublicHistoryV3().ingest(h)
        self.assertTrue(report['gap']);self.assertFalse(report['history_complete'])

    def test_cursor_query_and_completed_random_checkpoint(self):
        value=self.value('v3-ultra-ball-committed');memory=PublicHistoryV3()
        memory.ingest(value.history())
        delta=value.history_since(memory.cursor)
        self.assertEqual(delta['events'],[])
        self.assertEqual(memory.ingest(delta)['accepted'],0)
        self.assertTrue(memory.complete)
        with self.assertRaisesRegex(ValueError,'history_cursor'):value.history_since(memory.cursor+1)
        h=self.value('v3-marker-protection-pending').history()
        self.assertTrue(any(e['type']=='coin_flip' and e['random_outcome']['value']=='heads' for e in h['events']))

    def test_missing_zone_and_count_mismatch_cannot_pass(self):
        row=self.row();row['supplement']['history']['snapshot'].pop()
        with self.assertRaisesRegex(ValueError,'missing_zone'):PublicInputV3.capture(row['frame'],row['supplement'])
        row=self.row();next(z for z in row['supplement']['history']['snapshot'] if z['zone']=='deck')['count']+=1
        with self.assertRaisesRegex(ValueError,'snapshot_frame_mismatch'):PublicInputV3.capture(row['frame'],row['supplement'])

    def test_generated_contract_and_source_evidence_are_exact(self):
        import hashlib
        self.assertEqual(contract(),json.loads((ROOT/'contracts/ptcgdap/public_input_v3.json').read_bytes()))
        receipt=json.loads((ROOT/'evidence/public-input-v3/engine-acceptance.json').read_bytes())
        self.assertEqual(receipt['status'],'passed')
        for name,expected in receipt['files'].items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest().upper(),expected,name)
        for name,key in [('engine-snapshots.json','engine_evidence_sha256'),('engine-source-manifest.json','engine_source_manifest_sha256')]:
            self.assertEqual(hashlib.sha256((ROOT/'evidence/public-input-v3'/name).read_bytes()).hexdigest().upper(),receipt[key])

    def test_cli_coverage_and_training_gate(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'observation.json'
            path.write_text(json.dumps(self.value().envelope()),encoding='utf-8')
            command=[sys.executable,str(ROOT/'forge.py'),'public-input','--input',str(path)]
            passed=subprocess.run(command,cwd=ROOT,capture_output=True,encoding='utf-8')
            self.assertEqual(passed.returncode,0,passed.stderr)
            self.assertTrue(json.loads(passed.stdout)['coverage']['training_profiles']['public-observation-v3'])
            failed=subprocess.run(command+['--require-training','semantic-complete-v3'],cwd=ROOT,capture_output=True,encoding='utf-8')
            self.assertEqual(failed.returncode,1,failed.stderr)
            self.assertEqual(json.loads(failed.stdout)['error_code'],'public_input_v3_incomplete')


if __name__ == '__main__':
    unittest.main()
