"""Verified replay opportunities are hypotheses, not fabricated winning labels."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_strategy_base import window
from tests.test_competitive_forge_v2 import _slot, MORGREM
from scripts.ai.ptcgdap.cabt_tree_hash import jcs_canonical_json_bytes, public_observation_hash
from ptcg_strategy_forge.decision_bench import bind_frame
from ptcg_strategy_forge.native_trace import PREFIX
from ptcg_strategy_forge.strategy_reflection import reflect_native, reflect_bench


def write_trace(root, frames, *, dirty=False):
    previous = None
    rows = []
    for i, frame in enumerate(frames):
        frame = copy.deepcopy(frame)
        frame['sequence'] = i + 1
        bind_frame(frame)
        for option in frame['options']:
            option['option_fingerprint'] = public_observation_hash(dict(
                profile_id='ptcgdap-scoped-option-fingerprint-v1',
                public_observation_hash=frame['source']['public_observation_hash'],
                window_id=frame['source']['window_id'],index=option['index'],option=copy.deepcopy(option)))
        decision_id = f'{root.name}.window.{i}'
        payloads = [dict(document_type='decision_window_record_v1',decision_id=decision_id,frame=frame,
            host=dict(status='accepted',accepted_indexes=[0],accepted_option_fingerprints=[frame['options'][0]['option_fingerprint']],
                      error_code='',fallback_used=False),policy=dict(base_result={})),
            dict(document_type='owner_step_witness_v1',decision_ids=[decision_id],
                 engine_commit_delta=1,engine_rejection_delta=int(dirty))]
        for payload in payloads:
            row = dict(document_type='developer_decision_trace_record_v1',schema_version=1,native_match_id=root.name,
                       record_index=len(rows),previous_record_sha256=previous,payload=payload)
            previous = hashlib.sha256(PREFIX + jcs_canonical_json_bytes(row)).hexdigest().upper()
            rows.append(dict(row, record_sha256=previous))
    (root/'developer_decisions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows),encoding='utf-8')
    manifest = dict(document_type='developer_decision_trace_manifest_v1',schema_version=1,native_match_id=root.name,
        complete=True,record_count=len(rows),decision_count=len(frames),owner_step_count=len(frames),
        chain_root_sha256=previous,dropped_record_count=0,private_replay_used=False,
        visibility='acting_policy_public_view_allow_list_v1')
    (root/'developer_decision_trace_manifest.json').write_text(json.dumps(manifest),encoding='utf-8')


class StrategyReflectionTests(unittest.TestCase):
    def test_bench_integrity_identity_and_path_gates(self):
        from tools.local_engine_bench import COUNTERS
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            frame=window('attack',False);other=copy.deepcopy(frame);other['seat']=1
            write_trace(root,[frame,other])
            native=[json.loads(line)['payload'] for line in (root/'developer_decisions.jsonl').read_text().splitlines()]
            decisions=[row for row in native if row['document_type']=='decision_window_record_v1']
            chain='0'*64;lines=[]
            for decision in decisions:
                payload=json.dumps(dict(seat=decision['frame']['seat'],decision=decision))
                chain=hashlib.sha256((chain+'\n'+payload).encode()).hexdigest().upper()
                lines.append(json.dumps(dict(payload=payload,chain_sha256=chain)))
            trace=root/'bench.jsonl';trace.write_text('\n'.join(lines)+'\n',encoding='utf-8')
            audit=dict(policy_calls=1,policy_successes=1,engine_commits=1,**{key:0 for key in COUNTERS})
            game=dict(candidate_sha256='A'*64,opponent_sha256='B'*64,candidate_seat=0.0,seed=1,
                terminal=True,winner_index=0,failure_code='',trace_verified=True,trace_count=2,
                trace_path='bench.jsonl',trace_file_sha256=hashlib.sha256(trace.read_bytes()).hexdigest().upper(),
                trace_root_sha256=chain,candidate_audit=audit,opponent_audit=audit)
            report=root/'report.json'
            def save(row):report.write_text(json.dumps(dict(clean=True,errors=[],games=[row])),encoding='utf-8')
            save(game)
            result=reflect_bench(report,expected_candidate_sha256='A'*64)
            self.assertEqual(result['reviewed_windows'],1)
            self.assertFalse(result['sources'][0]['individual_commits_proven'])
            with self.assertRaisesRegex(ValueError,'reflection_game_unqualified'):
                reflect_bench(report,expected_candidate_sha256='C'*64)
            for name in ['../outside','C:/outside','/outside']:
                save(dict(game,trace_path=name))
                with self.assertRaisesRegex(ValueError,'reflection_trace_path_invalid'):
                    reflect_bench(report,expected_candidate_sha256='A'*64)
            save(game);trace.write_text(lines[0]+'\n',encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'reflection_trace_verification_failed'):
                reflect_bench(report,expected_candidate_sha256='A'*64)

    def test_zero_damage_is_review_opportunity_and_only_selected_seat_is_used(self):
        frame = window('attack',False)
        frame['options'][1]['projected_damage'] = 0
        frame['public_state']['opponent']['bench'] = [_slot(90,MORGREM,0,2)]
        other = copy.deepcopy(frame); other['seat'] = 1
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); write_trace(root,[frame,other])
            report=reflect_native(root,seat=0)
            self.assertEqual(report['reviewed_windows'],1)
            issue=next(r for r in report['issues'] if r['code']=='zero_damage_attack_with_bench')
            self.assertEqual(issue['occurrences'],1)
            self.assertEqual(issue['status'],'hypothesis')
            self.assertFalse(report['claims']['alternative_executed'])
            self.assertNotIn('hand',json.dumps(report))

    def test_dirty_incomplete_and_tampered_traces_cannot_feed_reflection(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); write_trace(root,[window('attack',False)],dirty=True)
            with self.assertRaisesRegex(ValueError,'reflection_dirty_trace'):
                reflect_native(root,seat=0)
            write_trace(root,[window('attack',False)])
            path=root/'developer_decisions.jsonl'
            path.write_text(path.read_text().replace('accepted','rejected',1),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'native_trace_hash_mismatch'):
                reflect_native(root,seat=0)

    def test_private_state_rejected_without_echo(self):
        frame=window('attack',False)
        frame['public_state']['opponent']['hand']=['SECRET_SENTINEL']
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);write_trace(root,[frame])
            with self.assertRaises(ValueError) as error:
                reflect_native(root,seat=0)
            self.assertNotIn('SECRET_SENTINEL',str(error.exception))

    def test_seat_is_required_and_trace_with_no_matching_seat_is_not_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); write_trace(root,[window('attack',False)])
            for seat in [True,2,None]:
                with self.assertRaisesRegex(ValueError,'reflection_seat_invalid'):
                    reflect_native(root,seat=seat)
            with self.assertRaisesRegex(ValueError,'reflection_no_qualified_windows'):
                reflect_native(root,seat=1)


if __name__ == '__main__': unittest.main()
