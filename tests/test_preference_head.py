import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import numpy as np
from ptcg_strategy_forge.preference_head import pair_loss_gradient
from ptcg_strategy_forge.preference_head import fit_head
from ptcg_strategy_forge.neural_actor import FeatureSpec,NeuralRanker


class PreferenceHeadTests(unittest.TestCase):
    def test_task_checkpoint_requires_learning_and_bounded_retention(self):
        from ptcg_strategy_forge.preference_head import task_checkpoint_admitted
        initial=dict(validation_bc_accuracy=.9,validation_pair_accuracy=.75)
        row=dict(training_pair_accuracy=1.,validation_pair_accuracy=.75,validation_bc_accuracy=.89)
        self.assertTrue(task_checkpoint_admitted(row,initial,.02))
        self.assertFalse(task_checkpoint_admitted(dict(row,training_pair_accuracy=.6),initial,.02))
        self.assertFalse(task_checkpoint_admitted(dict(row,validation_bc_accuracy=.87),initial,.02))
        self.assertFalse(task_checkpoint_admitted(dict(row,validation_pair_accuracy=.5),initial,.02))

    def test_gradient_and_reorder(self):
        scores=np.array([0.2,-0.7,1.1])
        loss,gradient=pair_loss_gradient(scores,0,2)
        for i in range(3):
            v=scores.copy();v[i]+=1e-5
            w=scores.copy();w[i]-=1e-5
            numeric=(pair_loss_gradient(v,0,2)[0]-pair_loss_gradient(w,0,2)[0])/2e-5
            self.assertAlmostEqual(numeric,gradient[i],places=5)
        permutation=[2,0,1]
        l,g=pair_loss_gradient(scores[permutation],1,0)
        self.assertAlmostEqual(loss,l)
        np.testing.assert_allclose(g,gradient[permutation])
        self.assertLess(gradient[0],0);self.assertGreater(gradient[2],0)

    def test_unknown_or_same_is_not_preference(self):
        for pair in ((0,0),(0,3),(None,1)):
            with self.assertRaises(ValueError):pair_loss_gradient(np.array([1.,2.]),*pair)

    def test_training_preserves_hidden_parameters_and_counts_head(self):
        model=NeuralRanker(FeatureSpec(1,1,{0:1.},{0:1.},{},{}),hidden=4,bottleneck=3,seed=4)
        original={k:v.copy() for k,v in model.parameters.items()}
        e=dict(frame=[1],frame_presence=[1],options=[[0],[1]],option_presence=[[1],[1]],label=1)
        bc=[dict(e,split='train'),dict(e,split='validation')]
        prefs=[dict(e,split=s,preferred=1,rejected=0) for s in ('train','validation')]
        report=fit_head(model,bc,prefs,weight=.25,epochs=2)
        self.assertEqual(report['trained_parameters'],3)
        for k in original:
            if k!='w3':np.testing.assert_array_equal(original[k],model.parameters[k])
        with self.assertRaises(ValueError):fit_head(model,bc,[],weight=.25)
