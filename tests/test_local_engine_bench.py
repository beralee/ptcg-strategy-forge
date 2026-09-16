import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,Mock

from tools.local_engine_bench import audit_game, compare_runs, verify_window, runtime_hash
from tests.test_competitive_forge_v2 import _frame
from scripts.ai.ptcgdap.cabt_tree_hash import public_observation_hash
from scripts.ai.ptcgdap.competitive_policy_v2 import _frame_error


def bound_decision():
    f = _frame()
    observation = {key:f[key] for key in ('schema_version','sequence','seat','prompt_kind','public_state')}
    f['source']['public_observation_hash'] = public_observation_hash(observation)
    f['source']['window_id'] = public_observation_hash(dict(public_observation_hash=f['source']['public_observation_hash'],select_semantics=f['select_semantics'],options=f['options']))
    for option in f['options']:
        option['option_fingerprint'] = public_observation_hash(dict(profile_id='ptcgdap-scoped-option-fingerprint-v1',public_observation_hash=f['source']['public_observation_hash'],window_id=f['source']['window_id'],index=option['index'],option=option))
    return dict(decision_id='test-window',frame=f,host=dict(accepted_indexes=[1],accepted_option_fingerprints=[f['options'][1]['option_fingerprint']]))


def game(won=True, seed=1, seat=0):
    audit = dict(policy_calls=3, policy_successes=3, policy_errors=0,
                 invalid_outputs=0, same_window_fallbacks=0, classic_fallbacks=0,
                 engine_commits=3, engine_rejections=0, external_process_attempts=0,
                 developer_trace_dropped_records=0)
    return dict(seed=seed, candidate_seat=seat, terminal=True, winner_index=seat if won else 1-seat,
                failure_code="", candidate_audit=audit, opponent_audit=copy.deepcopy(audit),
                candidate_sha256="A"*64, opponent_sha256="B"*64, trace_verified=True)


class LocalEngineBenchTests(unittest.TestCase):
    def test_clean_and_both_owners_enforced(self):
        row = game()
        self.assertEqual(audit_game(row, "A"*64, "B"*64), [])
        for owner in ("candidate_audit", "opponent_audit"):
            for key in ("policy_errors", "invalid_outputs", "same_window_fallbacks", "classic_fallbacks", "engine_rejections", "developer_trace_dropped_records"):
                broken=copy.deepcopy(row); broken[owner][key]=1
                self.assertTrue(audit_game(broken, "A"*64, "B"*64))

    def test_missing_counters_artifact_drift_and_nonterminal_rejected(self):
        for key,value in (("terminal",False),("trace_verified",False),("candidate_sha256","C"*64)):
            row=game(); row[key]=value
            self.assertTrue(audit_game(row,"A"*64,"B"*64))
        row=game(); del row["opponent_audit"]["policy_successes"]
        self.assertTrue(audit_game(row,"A"*64,"B"*64))

    def test_pairing_requires_same_seeds_seats_opponents_and_runtime(self):
        base=dict(clean=True, errors=[], runtime_sha256="D"*64, games=[game(False),game(True,seat=1)])
        new=copy.deepcopy(base); new["games"][0]["winner_index"]=0
        result=compare_runs(base,new)
        self.assertEqual((result["improved"],result["regressed"]),(1,0))
        for key,value in (("seed",2),("candidate_seat",1),("opponent_sha256","C"*64)):
            changed=copy.deepcopy(new);changed["games"][0][key]=value
            with self.assertRaisesRegex(ValueError,"bench_pairing_mismatch"):
                compare_runs(base,changed)
        new["runtime_sha256"]="E"*64
        with self.assertRaisesRegex(ValueError,"bench_runtime_mismatch"):
            compare_runs(base,new)

    def test_report_failure_and_mixed_candidate_bytes_rejected(self):
        base=dict(clean=True,errors=[],runtime_sha256='D'*64,games=[game(),game(seat=1)])
        for key,value in (('clean',False),('errors',['bench_runtime_changed'])):
            changed=copy.deepcopy(base);changed[key]=value
            with self.assertRaisesRegex(ValueError,'bench_dirty_run'):compare_runs(base,changed)
        changed=copy.deepcopy(base);changed['games'][1]['candidate_sha256']='C'*64
        with self.assertRaisesRegex(ValueError,'bench_archive_mismatch'):compare_runs(base,changed)

    def test_public_window_bindings_reject_stale_indices_reorder_and_hidden_data(self):
        record=bound_decision()
        self.assertEqual(verify_window(record,_frame_error)['host']['accepted_indexes'],[1])
        changed=copy.deepcopy(record);changed['host']['accepted_indexes']=[2]
        with self.assertRaisesRegex(ValueError,'bench_accepted_binding_invalid'):verify_window(changed,_frame_error)
        changed=copy.deepcopy(record);changed['frame']['options'].reverse()
        with self.assertRaisesRegex(ValueError,'bench_public_frame_invalid'):verify_window(changed,_frame_error)
        changed=copy.deepcopy(record);changed['frame']['public_state']['opponent']['hand']=['SECRET']
        with self.assertRaisesRegex(ValueError,'bench_public_frame_invalid'):verify_window(changed,_frame_error)
        changed=copy.deepcopy(record);changed['frame']['public_state']['opponent']['hand_count']+=1
        with self.assertRaisesRegex(ValueError,'bench_observation_binding_invalid'):verify_window(changed,_frame_error)

    def test_sealed_runtime_covers_card_inputs_native_bytes_and_effective_save(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);runtime=root/'runtime';runtime.mkdir();user=root/'user';user.mkdir()
            for part in ('scripts','contracts','data','native'):(runtime/part).mkdir()
            for name in ('bench.gd','bench.tscn','project.godot','development-gate-original.txt'):(runtime/name).write_text('fixture')
            (user/'cards').mkdir();godot=root/'godot.exe';godot.write_bytes(b'fixture')
            (runtime/'sealed-inputs.json').write_text(json.dumps(dict(version=2,user_path=str(user))))
            for path in (runtime/'data/card.json',runtime/'native/engine.dll',user/'cards/card.json'):
                before=runtime_hash(runtime,godot)[0]
                path.write_bytes(b'new bytes')
                self.assertNotEqual(before,runtime_hash(runtime,godot)[0])

    def test_related_opponents_on_one_seed_are_one_statistical_cluster(self):
        base=dict(clean=True,errors=[],runtime_sha256='D'*64,games=[])
        for sha in ('B','C','D'):
            row=game(False);row['opponent_sha256']=sha*64;base['games'].append(row)
        candidate=copy.deepcopy(base)
        for row in candidate['games']:row['winner_index']=0
        result=compare_runs(base,candidate)
        self.assertEqual(result['seed_cluster_count'],1)
        self.assertEqual(result['seed_cluster_sign_flip_p'],1)

    def test_cleanup_stops_only_the_owned_windows_process_tree(self):
        from tools.local_engine_bench import stop_process_tree
        process=Mock(pid=12345);process.poll.return_value=None
        with patch('tools.local_engine_bench.os.name','nt'),patch('tools.local_engine_bench.subprocess.run') as run:
            stop_process_tree(process)
            self.assertEqual(run.call_args.args[0],['taskkill','/PID','12345','/T','/F'])
            process.wait.assert_called_once_with(timeout=30)

    def test_npc_masked_prize_shape_preserves_privacy_and_all_other_gates(self):
        from tools.local_engine_bench import npc_frame_error
        f=_frame();f['prompt_kind']='take_prize';f['public_state']['self']['prizes_remaining']=5
        f['select_semantics'].update(min_count=1,max_count=1,select_type_raw=1,select_context_raw=7)
        for o in f['options']:
            o.update(kind='take_prize',card_uid=None,card_serial=None,option_type_raw=3)
        self.assertIsNotNone(_frame_error(f))
        original=copy.deepcopy(f)
        self.assertIsNone(npc_frame_error(f,_frame_error))
        self.assertEqual(f,original)
        for key,value in (('card_uid','CSVE1C_DAR'),('card_serial',1),('option_number',0),('option_player_index',1),('tags',['extra']),('pending_assignment_count',1)):
            changed=copy.deepcopy(f);changed['options'][0][key]=value
            self.assertIsNotNone(npc_frame_error(changed,_frame_error))
        changed=copy.deepcopy(f);changed['prompt_kind']='search'
        self.assertIsNotNone(npc_frame_error(changed,_frame_error))
        changed=copy.deepcopy(f);changed['public_state']['opponent']['hand']=['SECRET']
        self.assertIsNotNone(npc_frame_error(changed,_frame_error))
        changed=copy.deepcopy(f);changed['public_state']['self']['prizes_remaining']=4
        self.assertIsNotNone(npc_frame_error(changed,_frame_error))
        changed=copy.deepcopy(f);changed['options'][0].update(card_uid='CSVE1C_DAR',card_serial=1000)
        self.assertIsNotNone(npc_frame_error(changed,_frame_error))
        changed=copy.deepcopy(f)
        for i,option in enumerate(changed['options']):option.update(card_uid='CSVE1C_DAR',card_serial=1000+i)
        self.assertIsNotNone(npc_frame_error(changed,_frame_error))


if __name__ == "__main__":
    unittest.main()
