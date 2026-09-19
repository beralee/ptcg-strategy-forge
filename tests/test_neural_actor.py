import tempfile
from pathlib import Path
import unittest
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'src'), str(Path(__file__).resolve().parents[1])]


class NeuralActorTests(unittest.TestCase):
    def test_export_does_not_saturate_ordinary_large_logits(self):
        import numpy as np
        import onnxruntime as ort
        from ptcg_strategy_forge.neural_actor import FeatureSpec, NeuralRanker, export_onnx
        spec=FeatureSpec(128,32,{0:1.0},{0:1.0},{},{})
        model=NeuralRanker(spec,hidden=4,bottleneck=2,seed=1)
        model.parameters['b3'][:]=20
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'actor.onnx';export_onnx(model,p)
            session=ort.InferenceSession(str(p),providers=['CPUExecutionProvider'])
            f=np.zeros((1,128),np.int32);o=np.zeros((1,1024,32),np.int32)
            scores,_=session.run(None,dict(frame_i32=f,frame_presence_i32=f,option_i32=o,option_presence_i32=o,option_mask_i32=np.ones((1,1024),np.int32)))
            self.assertEqual(scores[0,0],200000)

    def test_score_cast_cannot_overflow_i32(self):
        import numpy as np
        import onnxruntime as ort
        from ptcg_strategy_forge.neural_actor import FeatureSpec, NeuralRanker, export_onnx
        model=NeuralRanker(FeatureSpec(128,32,{0:1.0},{0:1.0},{},{}),hidden=4,bottleneck=2)
        model.parameters['b3'][:]=1000000
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'actor.onnx';export_onnx(model,p)
            session=ort.InferenceSession(str(p),providers=['CPUExecutionProvider'])
            f=np.zeros((1,128),np.int32);o=np.zeros((1,1024,32),np.int32)
            scores,_=session.run(None,dict(frame_i32=f,frame_presence_i32=f,option_i32=o,option_presence_i32=o,option_mask_i32=np.ones((1,1024),np.int32)))
            self.assertEqual(scores[0,0],1000000000)

    def test_network_learns_state_conditioned_choice_and_exports_exactly(self):
        import numpy as np
        from ptcg_strategy_forge.neural_actor import FeatureSpec, NeuralRanker, export_onnx, fit
        spec = FeatureSpec(frame_width=24, option_width=16,
                           frame_numeric={0: 1.0}, option_numeric={},
                           frame_categories={}, option_categories={14: [101, 202]})
        examples = []
        for cue, label in [(-1, 0), (1, 1)]:
            frame = np.zeros(24, dtype=np.int32); frame[0] = cue
            options = np.zeros((2, 16), dtype=np.int32); options[:, 14] = [101, 202]
            examples.append(dict(frame=frame, frame_presence=np.ones(24, dtype=np.int32),
                                 options=options, option_presence=np.ones((2, 16), dtype=np.int32),
                                 label=label))
        model = NeuralRanker(spec, hidden=16, bottleneck=8, seed=12)
        report = fit(model, examples, examples, epochs=180, learning_rate=0.02, batch_size=2)
        self.assertEqual(report['validation_accuracy'], 1.0)
        with tempfile.TemporaryDirectory() as temp:
            import onnxruntime as ort
            path = Path(temp) / 'actor.onnx'
            export_onnx(model, path)
            session = ort.InferenceSession(str(path), providers=['CPUExecutionProvider'])
            for example in examples:
                scores = model.scores(example)
                options = np.zeros((1, 1024, 16), dtype=np.int32)
                presence = np.zeros_like(options); mask = np.zeros((1, 1024), dtype=np.int32)
                options[0, :2] = example['options']; presence[0, :2] = example['option_presence']; mask[0, :2] = 1
                inputs = dict(frame_i32=example['frame'][None], frame_presence_i32=example['frame_presence'][None],
                              option_i32=options, option_presence_i32=presence, option_mask_i32=mask)
                actual, _ = session.run(None, inputs)
                self.assertTrue(np.allclose(actual[0, :2], np.trunc(scores*10000), atol=1))
                self.assertTrue(np.all(actual[0, 2:] == -2000000000))
                inputs['option_i32'][0, :2] = inputs['option_i32'][0, :2][::-1]
                reordered, _ = session.run(None, inputs)
                self.assertTrue(np.array_equal(actual[0, :2], reordered[0, :2][::-1]))

    def test_hash_values_are_categories_and_missing_is_not_zero(self):
        import numpy as np
        from ptcg_strategy_forge.neural_actor import encode_features
        values = np.array([[0, -1901234567], [0, 1934567890]], dtype=np.int32)
        present = np.array([[0, 1], [1, 1]], dtype=np.int32)
        features = encode_features(values, present, {0: 0.1}, {1: [-1901234567, 1934567890]})
        self.assertEqual(features.tolist(), [[0.,0.,1.,0.], [0.,1.,0.,1.]])


if __name__ == '__main__': unittest.main()
