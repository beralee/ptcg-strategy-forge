import copy
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from ptcg_strategy_forge.controlled_branch import bind_intervention, qualify_pair


class ControlledBranchTests(unittest.TestCase):
    def test_research_schedule_can_omit_unintervened_control_seat(self):
        from tools.local_engine_bench import apply_research_interventions
        games=[dict(seed=1,seat=0),dict(seed=1,seat=1)]
        plan=dict(research_single_interventions={'1':{'window_id':'w'}},research_only_requested_seats=True)
        result=apply_research_interventions(dict(requires_model=False),games,plan)
        self.assertEqual([r['seat'] for r in result],[1])
        self.assertNotIn('research_intervention',games[1])
        with self.assertRaises(ValueError):apply_research_interventions(dict(requires_model=True),games,plan)
        with self.assertRaises(ValueError):apply_research_interventions(dict(requires_model=False),games,dict(plan,research_single_interventions={'2':{}}))

    def fixture(self):
        frame = dict(source=dict(public_observation_hash='obs', window_id='win'),
                     select_semantics=dict(min_count=1, max_count=1),
                     options=[dict(index=0, kind='attach_energy', target_uid='a'),
                              dict(index=1, kind='attach_energy', target_uid='b')])
        frontier = dict(enabled=True, profile_id='ptcgdap-base-model-frontier-v1',
                        indexes=[0,1], **frame['source'])
        return frame, frontier, dict(**frame['source'], option=dict(kind='attach_energy', target_uid='b'))

    def test_current_semantic_binding_and_reorder(self):
        f,b,i = self.fixture()
        self.assertEqual(bind_intervention(f,b,[0],i),1)
        f['options'].reverse()
        for n,o in enumerate(f['options']): o['index']=n
        self.assertEqual(bind_intervention(f,b,[1],i),0)

    def test_reject_closed_stale_cardinality_outside_and_ambiguous(self):
        for change in ('disabled','stale','multi','outside','duplicate','wrong_kind'):
            f,b,i=self.fixture()
            if change=='disabled': b['enabled']=False
            if change=='stale': b['window_id']='old'
            if change=='multi': f['select_semantics']['max_count']=2
            if change=='outside': b['indexes']=[0]
            if change=='duplicate': f['options'][0]['target_uid']='b'
            if change=='wrong_kind': i['option']['kind']='attack'
            with self.subTest(change=change),self.assertRaises(ValueError): bind_intervention(f,b,[0],i)

    def test_pair_requires_prefix_once_clean_and_same_continuation(self):
        f,b,i=self.fixture()
        d=dict(frame=f,host=dict(accepted_indexes=[0],status='accepted',fallback_used=False,error_code='',model_input_evidence=dict(base_frontier=b)),
               policy=dict(decision_audit=dict(model_frontier=b)))
        original=[dict(seat=0,decision=d)]
        branch=copy.deepcopy(original);branch[0]['decision']['host']['accepted_indexes']=[1]
        meta=dict(clean=True,terminal=True,seed=4,candidate_seat=0,candidate_sha256='c',opponent_sha256='o',runtime_sha256='r',winner_index=0)
        self.assertEqual(qualify_pair(original,branch,meta,meta,i)['outcome_delta'],0)
        for change in ('runtime','prefix','dirty','missing'):
            altered=copy.deepcopy(meta);tr=copy.deepcopy(branch)
            if change=='runtime':altered['runtime_sha256']='other'
            if change=='prefix':tr[0]['decision']['frame']['source']['window_id']='bad'
            if change=='dirty':altered['clean']=False
            if change=='missing':tr[0]['decision']['host']['accepted_indexes']=[0]
            with self.subTest(change=change),self.assertRaises(ValueError):qualify_pair(original,tr,meta,altered,i)
