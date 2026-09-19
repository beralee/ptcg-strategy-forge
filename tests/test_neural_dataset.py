import copy
import unittest
from unittest.mock import patch
from tests.test_competitive_forge_v2 import _frame, GRIMMSNARL, MORGREM, DARK_ENERGY
from tests.test_local_engine_bench import bound_decision
from scripts.ai.ptcgdap.semantic_model_profile import project_semantic_frame,base_model_frontier,PROFILE_ID
from ptcg_strategy_forge.neural_dataset import qualify_teacher_record

UIDS={GRIMMSNARL,MORGREM,DARK_ENERGY}

def fixture():
    frame=_frame(); frame['select_semantics'].update(min_count=1,max_count=1)
    frame['prompt_kind']='main'
    for option in frame['options']: option['kind']='play_trainer'
    with patch('tests.test_local_engine_bench._frame',return_value=frame): record=bound_decision()
    clean=copy.deepcopy(record['frame'])
    for o in clean['options']: o.pop('option_fingerprint')
    t=project_semantic_frame(clean,UIDS); n=len(clean['options'])
    frontier=base_model_frontier(frame=clean,selected=[1],tiers={i:[0] for i in range(n)},vetoed=[],mandatory=[],terminal=[],evaluated={},audit={})
    record['policy']={'ok':True,'error_code':'','reported_indexes':[1],'base_result':{'selected_indexes':[1]},
        'reported_window_id':clean['source']['window_id'],'reported_public_observation_hash':clean['source']['public_observation_hash']}
    capture={'status':'captured','profile_id':'ptcgdap-semantic-model-input-v1','tensor_profile_id':PROFILE_ID,'semantic_projector_sha256':'C'*64,
        'base_frontier':frontier,'frontier_indexes':frontier['indexes'],'frame_i32':list(t.frame_i32),'frame_presence_i32':list(t.frame_presence_i32),
        'option_i32':[v for row in t.option_i32[:n] for v in row],'option_presence_i32':[v for row in t.option_presence_i32[:n] for v in row],
        'option_mask_i32':list(t.option_mask_i32[:n]),'row_to_current_index':list(t.row_to_current_index),'semantic_keys':list(t.semantic_keys)}
    record['host'].update(status='accepted',fallback_used=False,error_code='',model_input_evidence=capture)
    return {'decision':record,'step_decision_count':1,'engine_commit_delta':1,'engine_rejection_delta':0}

class NeuralDatasetTests(unittest.TestCase):
    def qualify(self,payload): return qualify_teacher_record(payload,allowed_uids=UIDS,projector_sha256='C'*64)

    def test_qualified_label_and_ambiguous_commit(self):
        payload=fixture(); example,reason=self.qualify(payload)
        self.assertEqual(reason,'qualified');self.assertEqual(example['current_indexes'][example['label']],1)
        for field,value in [('step_decision_count',2),('engine_commit_delta',0),('engine_commit_delta',True),('engine_rejection_delta',1)]:
            changed=copy.deepcopy(payload);changed[field]=value
            self.assertIsNone(self.qualify(changed)[0])

    def test_duplicate_windows_must_not_hide_conflicting_teacher_labels(self):
        from ptcg_strategy_forge.neural_dataset import admit_unique_teacher_example
        e,_=self.qualify(fixture());seen={};identity=(1,0,e['window_id'])
        self.assertTrue(admit_unique_teacher_example(seen,identity,e))
        mirrored=copy.deepcopy(e);mirrored['decision_id']='different-match-same-window'
        self.assertFalse(admit_unique_teacher_example(seen,identity,mirrored))
        conflicting=copy.deepcopy(e);conflicting['label']=(e['label']+1)%len(e['options'])
        with self.assertRaisesRegex(ValueError,'duplicate_teacher_conflict'):
            admit_unique_teacher_example(seen,identity,conflicting)

    def test_stale_teacher_frontier_and_tampered_projection_fail_closed(self):
        for mutation in ('teacher','frontier','projection','projector'):
            p=fixture(); d=p['decision']; cap=d['host']['model_input_evidence']
            if mutation=='teacher': d['policy']['reported_window_id']='D'*64
            if mutation=='frontier': cap['base_frontier']['window_id']='D'*64
            if mutation=='projection': cap['frame_i32'][9]+=10
            if mutation=='projector': cap['semantic_projector_sha256']='D'*64
            with self.assertRaises(ValueError,msg=mutation): self.qualify(p)

    def test_model_visited_rows_are_not_executed_teacher_labels(self):
        p=fixture();p['decision']['host']['model_decision']={'invoked':True}
        self.assertIsNone(self.qualify(p)[0])

    def test_teacher_query_retains_model_execution_and_rejects_forged_teacher(self):
        from ptcg_strategy_forge.neural_dataset import qualify_teacher_query_record
        p=fixture();d=p['decision'];d['host']['accepted_indexes']=[2]
        d['host']['accepted_option_fingerprints']=[d['frame']['options'][2]['option_fingerprint']]
        d['host']['model_decision']={'invoked':True,'diagnostic_code':'','fallback_indexes':[1],'selected_indexes':[2],'model_artifact_sha256':'E'*64}
        def qualify(p):return qualify_teacher_query_record(p,allowed_uids=UIDS,projector_sha256='C'*64,model_artifact_sha256='E'*64)
        example,reason=qualify(p)
        self.assertEqual(reason,'qualified')
        self.assertEqual(example['evidence_kind'],'godot_same_window_rule_query_v1')
        self.assertFalse(example['teacher_was_executed'])
        self.assertEqual(example['observed_host_indexes'],[2])
        self.assertEqual(example['current_indexes'][example['label']],1)
        d['host']['model_decision']['fallback_indexes']=[2]
        with self.assertRaisesRegex(ValueError,'teacher_query_binding'):qualify(p)

if __name__=='__main__': unittest.main()
