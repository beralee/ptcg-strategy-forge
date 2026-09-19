import tempfile
from pathlib import Path
import unittest
import sys
import numpy as np
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1])]


class NeuralObjectiveTests(unittest.TestCase):
    def test_relation_ablation_starts_from_identical_base_and_can_learn_relations(self):
        from ptcg_strategy_forge.neural_actor import FeatureSpec,NeuralRanker,_loss_grad
        plain=NeuralRanker(FeatureSpec(128,32,{0:1.},{0:1.},{},{}),hidden=4,bottleneck=2,seed=8)
        extended=NeuralRanker(FeatureSpec(128,32,{0:1.},{0:1.},{},{},relations='public_resource_relations_v1'),hidden=4,bottleneck=2,seed=8)
        for key in plain.parameters:
            actual=extended.parameters[key][:len(plain.parameters[key])] if key=='wo' else extended.parameters[key]
            np.testing.assert_array_equal(plain.parameters[key],actual)
        np.testing.assert_array_equal(extended.parameters['wo'][-16:],0)
        f=np.zeros(128,np.int32);o=np.zeros((2,32),np.int32);o[:,13]=[90,110];o[:,8]=100
        e=dict(frame=f,frame_presence=np.ones(128,np.int32),options=o,option_presence=np.ones_like(o))
        np.testing.assert_array_equal(plain.scores(e),extended.scores(e))
        extended.parameters['wo'][:]=0;extended.parameters['wf'][:]=0
        extended.parameters['b1'][:]=.3;extended.parameters['w2'][:]=.1
        extended.parameters['b2'][:]=.2;extended.parameters['w3'][:]=1
        _,grads=_loss_grad(extended,*extended.encode(e),(0,))
        self.assertGreater(float(np.abs(grads['wo'][-16:]).sum()),0)

    def test_positive_objective_is_mass_of_equivalent_choices(self):
        from ptcg_strategy_forge.neural_actor import positive_labels, listwise_loss_gradient
        x=np.array([1001.,1002.,1003.])
        loss,gradient=listwise_loss_gradient(x,(0,2))
        self.assertAlmostEqual(loss,np.log(np.exp(-2)+np.exp(-1)+1)-np.log(np.exp(-2)+1))
        for i in range(3):
            d=np.eye(3)[i]*1e-4
            numeric=(listwise_loss_gradient(x+d,(0,2))[0]-listwise_loss_gradient(x-d,(0,2))[0])/2e-4
            self.assertAlmostEqual(gradient[i],numeric,places=6)
        self.assertEqual(positive_labels({'label':0,'positive_labels':[2,0]},3),(0,2))
        for bad in ([],[0,0],[True],[1],[0,3]):
            with self.assertRaisesRegex(ValueError,'neural_positive_labels_invalid'):
                positive_labels({'label':0,'positive_labels':bad},3)
        full,grad=listwise_loss_gradient(x,(0,1,2))
        self.assertAlmostEqual(full,0);np.testing.assert_allclose(grad,0,atol=1e-7)

    def test_relations_preserve_unknown_and_threshold_and_reorder(self):
        from ptcg_strategy_forge.neural_relations import encode_relations
        f=np.zeros(128,np.int32);fp=np.ones(128,np.int32)
        o=np.zeros((2,32),np.int32);op=np.ones_like(o)
        o[:,8]=100;o[:,13]=[90,110];f[22]=1;o[:,11]=2
        result=encode_relations(f,fp,o,op)
        self.assertAlmostEqual(result[0,0],-.1);self.assertAlmostEqual(result[1,0],.1)
        np.testing.assert_array_equal(result[::-1],encode_relations(f,fp,o[::-1],op[::-1]))
        op[0,13]=0
        missing=encode_relations(f,fp,o,op)
        self.assertEqual(missing[0,0],0);self.assertEqual(missing[0,8],0)
        self.assertEqual(missing[1,8],1)

    def test_relation_actor_exports_with_current_contract_and_mask(self):
        from ptcg_strategy_forge.neural_actor import FeatureSpec,NeuralRanker,export_onnx
        from ptcg_strategy_forge.ptcgai_ort import import_onnx_to_ort,_session_options
        import onnxruntime as ort
        spec=FeatureSpec(128,32,{0:1.},{0:1.},{},{},relations='public_resource_relations_v1')
        model=NeuralRanker(spec,hidden=8,bottleneck=4,seed=9)
        rng=np.random.default_rng(3)
        model.parameters['wo'][-16:]=rng.normal(0,.1,(16,8)).astype(np.float32)
        f=rng.integers(0,8,128,dtype=np.int32);f[17]=1
        o=rng.integers(0,130,(3,32),dtype=np.int32)
        fp=np.ones(128,np.int32);op=np.ones_like(o);op[1,13]=0;fp[22]=0
        e=dict(frame=f,frame_presence=fp,options=o,option_presence=op)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp);export_onnx(model,p/'a.onnx');import_onnx_to_ort(p/'a.onnx',p/'a.ort')
            session=ort.InferenceSession(str(p/'a.ort'),sess_options=_session_options(),providers=['CPUExecutionProvider'])
            feed=dict(frame_i32=f[None],frame_presence_i32=fp[None],option_i32=np.zeros((1,1024,32),np.int32),option_presence_i32=np.zeros((1,1024,32),np.int32),option_mask_i32=np.zeros((1,1024),np.int32))
            feed['option_i32'][0,:3]=o;feed['option_presence_i32'][0,:3]=op;feed['option_mask_i32'][0,:3]=1
            actual,count=session.run(None,feed)
            np.testing.assert_allclose(actual[0,:3],np.trunc(model.scores(e)*10000),atol=2)
            self.assertEqual(count.tolist(),[1]);self.assertTrue(np.all(actual[0,3:]==-2000000000))
            feed['option_i32'][0,:3]=o[::-1];feed['option_presence_i32'][0,:3]=op[::-1]
            reordered,_=session.run(None,feed)
            np.testing.assert_array_equal(actual[0,:3],reordered[0,:3][::-1])
        with self.assertRaisesRegex(ValueError,'neural_relations_profile_invalid'):
            FeatureSpec(24,16,{0:1.},{0:1.},{},{},relations='public_resource_relations_v1')


if __name__=='__main__':unittest.main()
