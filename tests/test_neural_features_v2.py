import copy
import unittest
import numpy as np
from tests.test_semantic_model_profile_v2 import attachment_frame, UIDS, V2
from scripts.ai.ptcgdap.semantic_model_profile import project_semantic_frame
from ptcg_strategy_forge.neural_features import build_feature_spec
from ptcg_strategy_forge.neural_actor import NeuralRanker


def dataset():
    t=project_semantic_frame(attachment_frame(),UIDS,profile_id=V2)
    e=dict(frame=list(t.frame_i32),frame_presence=list(t.frame_presence_i32),options=[list(r) for r in t.option_i32[:2]],
           option_presence=[list(r) for r in t.option_presence_i32[:2]],split='train',label=0)
    return dict(tensor_profile_id=V2,uid_vocabulary=UIDS,examples=[e])


class NeuralFeaturesV2Tests(unittest.TestCase):
    def test_public_hashes_cannot_be_ordinal_in_generated_encoding(self):
        d=dataset();s=build_feature_spec(d,relations=True)
        for start in range(128,416,16):
            for c in (0,11,14):self.assertIn(start+c,s.frame_categories);self.assertNotIn(start+c,s.frame_numeric)
        for c in (35,38,39,40,41,45):self.assertIn(c,s.option_categories);self.assertNotIn(c,s.option_numeric)
        held=copy.deepcopy(d['examples'][0]);held['split']='validation';held['options'][0][39]=123456789
        d['examples'].append(held)
        self.assertEqual(s,build_feature_spec(d,relations=True))

    def test_extended_initialization_preserves_common_function(self):
        from ptcg_strategy_forge.neural_features import initialize_from_parent
        d=dataset();old=copy.deepcopy(d);old.pop('tensor_profile_id')
        for e in old['examples']:
            e['frame']=e['frame'][:128];e['frame_presence']=e['frame_presence'][:128]
            for key in ('options','option_presence'):e[key]=[r[:32] for r in e[key]]
        parent=NeuralRanker(build_feature_spec(old,relations=True),hidden=12,bottleneck=8,seed=1)
        child=NeuralRanker(build_feature_spec(d,relations=True),hidden=12,bottleneck=8,seed=2)
        initialize_from_parent(child,parent)
        np.testing.assert_allclose(parent.scores(old['examples'][0]),child.scores(d['examples'][0]),rtol=0,atol=2e-6)
        from ptcg_strategy_forge.neural_actor import _loss_grad
        from ptcg_strategy_forge.neural_features import _feature_keys
        previous=set(_feature_keys(parent.spec.option_numeric,parent.spec.option_categories,parent.spec.relations))
        current=_feature_keys(child.spec.option_numeric,child.spec.option_categories,child.spec.relations)
        new=[i for i,k in enumerate(current) if k not in previous]
        _,grads=_loss_grad(child,*child.encode(d['examples'][0]),0)
        self.assertGreater(float(np.linalg.norm(grads['wo'][new])),0)

    def test_profile_width_mismatch_rejected(self):
        d=dataset();d['examples'][0]['options'][0]=[0]*32
        with self.assertRaisesRegex(ValueError,'profile_shape'):build_feature_spec(d)
