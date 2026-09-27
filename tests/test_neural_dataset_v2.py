import copy
import unittest
from tests.test_neural_dataset import fixture,UIDS
from scripts.ai.ptcgdap.semantic_model_profile import project_semantic_frame
from ptcg_strategy_forge.neural_dataset import qualify_teacher_query_record
V2='ptcgdap_local_semantic_actor_i32_v2'


class NeuralDatasetV2Tests(unittest.TestCase):
    def payload(self):
        p=fixture();d=p['decision'];d['host']['model_decision']={'invoked':True,'diagnostic_code':'','fallback_indexes':[1],'selected_indexes':[1],'model_artifact_sha256':'E'*64}
        f=copy.deepcopy(d['frame'])
        for o in f['options']:o.pop('option_fingerprint')
        t=project_semantic_frame(f,UIDS,profile_id=V2);n=len(t.semantic_keys);cap=d['host']['model_input_evidence']
        cap.update(profile_id='ptcgdap-semantic-model-input-v2',tensor_profile_id=V2,
            frame_i32=list(t.frame_i32),frame_presence_i32=list(t.frame_presence_i32),
            option_i32=[v for r in t.option_i32[:n] for v in r],option_presence_i32=[v for r in t.option_presence_i32[:n] for v in r])
        return p

    def qualify(self,p):
        return qualify_teacher_query_record(p,allowed_uids=UIDS,projector_sha256='C'*64,model_artifact_sha256='E'*64,tensor_profile_id=V2)

    def test_native_v2_query_keeps_executed_action_and_profile(self):
        e,reason=self.qualify(self.payload())
        self.assertEqual(reason,'qualified');self.assertEqual(e['tensor_profile_id'],V2)
        self.assertEqual(len(e['frame']),416);self.assertEqual(len(e['options'][0]),48)
        self.assertFalse(e['teacher_was_executed'])

    def test_changing_capture_header_does_not_upgrade_old_tensors(self):
        p=self.payload();p['decision']['host']['model_input_evidence']['frame_i32']=[0]*128
        with self.assertRaisesRegex(ValueError,'projection_mismatch'):self.qualify(p)

    def test_v2_is_not_silently_read_as_v1(self):
        with self.assertRaisesRegex(ValueError,'projector_identity_mismatch'):
            qualify_teacher_query_record(self.payload(),allowed_uids=UIDS,projector_sha256='C'*64,model_artifact_sha256='E'*64)
