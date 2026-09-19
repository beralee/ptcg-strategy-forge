"""Small state-conditioned BC network and data-only ONNX exporter.

Training uses NumPy; deployment uses only the approved ORT operators. Card
identities are categorical integer comparisons, never ordinal hash features.
Admission to real training and Host context gating are separate responsibilities.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import copy
import json
import math
from pathlib import Path

import numpy as np


@dataclass
class FeatureSpec:
    frame_width: int
    option_width: int
    frame_numeric: dict[int, float]
    option_numeric: dict[int, float]
    frame_categories: dict[int, list[int]]
    option_categories: dict[int, list[int]]
    relations: str = ''

    def __post_init__(self):
        if self.relations not in ('','public_resource_relations_v1') or (self.relations and (self.frame_width,self.option_width)!=(128,32)):
            raise ValueError('neural_relations_profile_invalid')
        for width, numeric, categories in (
            (self.frame_width, self.frame_numeric, self.frame_categories),
            (self.option_width, self.option_numeric, self.option_categories),
        ):
            if type(width) is not int or width <= 0: raise ValueError('neural_feature_spec_invalid')
            if set(numeric) & set(categories): raise ValueError('neural_category_cannot_be_ordinal')
            for col in [*numeric, *categories]:
                if type(col) is not int or not 0 <= col < width: raise ValueError('neural_feature_spec_invalid')
            if any(not math.isfinite(scale) or scale <= 0 for scale in numeric.values()):
                raise ValueError('neural_feature_scale_invalid')
            for values in categories.values():
                if (not values or len(values) != len(set(values)) or
                    any(type(v) is not int or not -(2**31) < v < 2**31 for v in values)):
                    raise ValueError('neural_feature_categories_invalid')


def feature_width(numeric, categories):
    return 2*len(numeric) + sum(len(values) for values in categories.values())


def encode_features(values, presence, numeric, categories):
    values, presence = np.asarray(values), np.asarray(presence)
    if values.shape != presence.shape: raise ValueError('neural_presence_shape_invalid')
    parts = []
    cols = sorted(numeric)
    if cols:
        scale = np.array([numeric[col] for col in cols], dtype=np.float32)
        known = presence[..., cols].astype(np.float32)
        parts.extend([np.clip(values[..., cols].astype(np.float32)*scale, -10, 10)*known, known])
    for col, vocabulary in sorted(categories.items()):
        # Compare integers before casting: distant i32 UID hashes need exact identity.
        equal = values[..., col, None] == np.asarray(vocabulary, dtype=np.int32)
        parts.append(equal.astype(np.float32)*presence[..., col, None])
    if not parts: return np.zeros((*values.shape[:-1], 0), dtype=np.float32)
    return np.concatenate(parts, axis=-1).astype(np.float32)


class NeuralRanker:
    def __init__(self, spec, *, hidden=128, bottleneck=64, seed=0):
        self.spec, self.hidden, self.bottleneck = spec, hidden, bottleneck
        rng = np.random.default_rng(seed)
        f = feature_width(spec.frame_numeric, spec.frame_categories)
        o = feature_width(spec.option_numeric, spec.option_categories)
        if min(f, o, hidden, bottleneck) <= 0: raise ValueError('neural_architecture_invalid')
        def weight(a,b): return (rng.standard_normal((a,b))*math.sqrt(2/max(a,1))).astype(np.float32)
        self.parameters = {'wf':weight(f,hidden), 'wo':weight(o,hidden), 'b1':np.zeros(hidden,np.float32),
                           'w2':weight(hidden,bottleneck), 'b2':np.zeros(bottleneck,np.float32),
                           'w3':weight(bottleneck,1), 'b3':np.zeros(1,np.float32)}
        if spec.relations:
            from .neural_relations import RELATION_WIDTH
            # Matched ablation: do not shift the RNG stream or rescale old weights.
            # Zero-added columns preserve the original forward pass yet receive gradients.
            self.parameters['wo']=np.concatenate((self.parameters['wo'],np.zeros((RELATION_WIDTH,hidden),np.float32)),axis=0)

    def encode(self, example):
        s = self.spec
        options=encode_features(example['options'], example['option_presence'], s.option_numeric, s.option_categories)
        if s.relations:
            from .neural_relations import encode_relations
            options=np.concatenate((options,encode_relations(example['frame'],example['frame_presence'],example['options'],example['option_presence'])),axis=-1)
        return (
            encode_features(example['frame'], example['frame_presence'], s.frame_numeric, s.frame_categories),
            options,
        )

    def forward(self, frame, options):
        p = self.parameters
        z1 = frame@p['wf'] + options@p['wo'] + p['b1']
        h1 = np.clip(z1, 0, 6)
        z2 = h1@p['w2'] + p['b2']; h2 = np.clip(z2, 0, 6)
        logits = (h2@p['w3'] + p['b3']).reshape(-1)
        return logits, (frame, options, z1, h1, z2, h2)

    def scores(self, example): return self.forward(*self.encode(example))[0]

    def save(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream: np.savez(stream, **self.parameters)
        metadata = {'spec':asdict(self.spec), 'hidden':self.hidden, 'bottleneck':self.bottleneck}
        path.with_suffix('.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')


def positive_labels(example, size):
    label=example['label'];labels=example.get('positive_labels',[label])
    if (type(label) is not int or not 0<=label<size or type(labels) not in (list,tuple) or not labels or
        any(type(i) is not int or not 0<=i<size for i in labels) or len(set(labels))!=len(labels) or label not in labels):
        raise ValueError('neural_positive_labels_invalid')
    return tuple(sorted(labels))


def listwise_loss_gradient(logits, labels):
    if type(labels) is int: labels=(labels,)
    if type(labels) not in (list,tuple) or not labels or any(type(i) is not int or not 0<=i<len(logits) for i in labels) or len(set(labels))!=len(labels):
        raise ValueError('neural_label_invalid')
    shifted = logits - np.max(logits)
    probs = np.exp(shifted); probs /= np.sum(probs)
    selected=shifted[list(labels)];maximum=np.max(selected)
    positive=np.exp(selected-maximum);positive/=np.sum(positive)
    loss=float(np.log(np.sum(np.exp(shifted)))-maximum-np.log(np.sum(np.exp(selected-maximum))))
    delta=probs.copy();delta[list(labels)]-=positive
    return loss,delta


def _loss_grad(model, frame, options, label):
    logits, cache = model.forward(frame, options)
    loss,delta=listwise_loss_gradient(logits,label);delta=delta[:,None]
    f,o,z1,h1,z2,h2 = cache; p = model.parameters
    grads = {'w3':h2.T@delta, 'b3':np.sum(delta,axis=0)}
    d2 = (delta@p['w3'].T)*((z2>0)&(z2<6))
    grads.update(w2=h1.T@d2, b2=np.sum(d2,axis=0))
    d1 = (d2@p['w2'].T)*((z1>0)&(z1<6))
    grads.update(wf=np.outer(f,np.sum(d1,axis=0)), wo=o.T@d1, b1=np.sum(d1,axis=0))
    return loss, grads


def _metrics(model, encoded):
    losses, correct = [], 0
    for f,o,label in encoded:
        logits = model.forward(f,o)[0]
        losses.append(listwise_loss_gradient(logits,label)[0])
        correct += int(int(np.argmax(logits)) in ((label,) if type(label) is int else label))
    return float(np.mean(losses)), correct/len(encoded)


def fit(model, training, validation, *, epochs=100, learning_rate=0.001, batch_size=32, seed=0, progress=None, multi_positive=False):
    """Listwise BC over each example's already-authorized candidate set.

    Callers must group/split whole games before this function. The validation
    set selects checkpoints; no test set is accepted by this training API.
    """
    if not training or not validation: raise ValueError('neural_training_split_empty')
    def encoded(examples): return [(*model.encode(e), positive_labels(e,len(e['options'])) if multi_positive else e['label']) for e in examples]
    train, valid = encoded(training), encoded(validation)
    rng = np.random.default_rng(seed)
    m = {k:np.zeros_like(v) for k,v in model.parameters.items()}; v = copy.deepcopy(m)
    best_loss, _ = _metrics(model, valid); best = copy.deepcopy(model.parameters); best_epoch = 0
    step = 0; history = []
    for epoch in range(1, epochs+1):
        order = rng.permutation(len(train))
        for offset in range(0,len(order),batch_size):
            batch = order[offset:offset+batch_size]
            grads = {k:np.zeros_like(value) for k,value in model.parameters.items()}
            for index in batch:
                _, item = _loss_grad(model, *train[int(index)])
                for k in grads: grads[k] += item[k]/len(batch)
            norm = math.sqrt(sum(float(np.sum(g*g)) for g in grads.values()))
            factor = min(1.,5/max(norm,1e-8)); step += 1
            for k, p in model.parameters.items():
                g = grads[k]*factor
                m[k] = 0.9*m[k] + 0.1*g; v[k] = 0.999*v[k] + 0.001*g*g
                p -= learning_rate*(m[k]/(1-0.9**step))/(np.sqrt(v[k]/(1-0.999**step))+1e-8)
                if not np.isfinite(p).all(): raise ValueError('neural_training_nonfinite')
        loss, accuracy = _metrics(model,valid)
        history.append({'epoch':epoch, 'validation_loss':loss, 'validation_accuracy':accuracy})
        if loss < best_loss:
            best_loss, best_epoch, best = loss, epoch, copy.deepcopy(model.parameters)
        if progress: progress(history[-1])
    model.parameters = best
    train_loss, train_accuracy = _metrics(model,train)
    loss, accuracy = _metrics(model,valid)
    return {'best_epoch':best_epoch, 'training_loss':train_loss, 'training_accuracy':train_accuracy,
            'validation_loss':loss, 'validation_accuracy':accuracy,
            'parameter_count':sum(p.size for p in model.parameters.values()), 'history':history}


def export_onnx(model, path, *, max_options=1024, count_frame_column=17):
    import onnx
    from onnx import TensorProto, helper, numpy_helper
    path = Path(path)
    if path.exists(): raise ValueError('model_output_exists')
    spec = model.spec; nodes, initializers = [], []
    def const(name, data):
        initializers.append(numpy_helper.from_array(np.asarray(data), name)); return name
    def node(op, inputs, output, **kwargs):
        nodes.append(helper.make_node(op, inputs, [output], **kwargs)); return output
    zero = const('zero_f32',np.float32(0)); one = const('one_f32',np.float32(1))
    six = const('six_f32',np.float32(6)); negten = const('negten_f32',np.float32(-10)); ten = const('ten_f32',np.float32(10))
    def project(prefix, numeric, categories, weights):
        values, presence = prefix+'_i32', prefix+'_presence_i32'
        parts, offset = [], 0
        cols = sorted(numeric)
        if cols:
            indices = const(prefix+'_numeric_cols',np.array(cols,np.int64))
            raw = node('Gather',[values,indices],prefix+'_raw',axis=-1)
            known = node('Gather',[presence,indices],prefix+'_known',axis=-1)
            raw = node('Cast',[raw],prefix+'_float',to=TensorProto.FLOAT)
            known = node('Cast',[known],prefix+'_known_f',to=TensorProto.FLOAT)
            scaled = node('Mul',[raw,const(prefix+'_scales',np.array([numeric[c] for c in cols],np.float32))],prefix+'_scaled')
            clipped = node('Clip',[scaled,negten,ten],prefix+'_clipped')
            masked = node('Mul',[clipped,known],prefix+'_masked')
            for part, label in [(masked,'numeric'),(known,'presence')]:
                w = const(prefix+'_'+label+'_w',weights[offset:offset+len(cols)])
                parts.append(node('MatMul',[part,w],prefix+'_'+label+'_hidden')); offset += len(cols)
        for col, vocabulary in sorted(categories.items()):
            name = prefix+'_cat'+str(col)
            index = const(name+'_col',np.array([col],np.int64))
            raw = node('Gather',[values,index],name+'_raw',axis=-1)
            present = node('Gather',[presence,index],name+'_present',axis=-1)
            present = node('Cast',[present],name+'_present_f',to=TensorProto.FLOAT)
            ge = node('Greater',[raw,const(name+'_lower',np.array(vocabulary,np.int32)-1)],name+'_ge')
            gt = node('Greater',[raw,const(name+'_values',np.array(vocabulary,np.int32))],name+'_gt')
            le = node('Where',[gt,zero,one],name+'_le')
            equal = node('Where',[ge,le,zero],name+'_equal')
            equal = node('Mul',[equal,present],name+'_known_equal')
            w = const(name+'_w',weights[offset:offset+len(vocabulary)])
            parts.append(node('MatMul',[equal,w],name+'_hidden')); offset += len(vocabulary)
        if not parts: raise ValueError('neural_feature_spec_empty')
        result = parts[0]
        for i,part in enumerate(parts[1:]): result = node('Add',[result,part],prefix+'_sum'+str(i))
        return result
    p = model.parameters
    frame_hidden = project('frame',spec.frame_numeric,spec.frame_categories,p['wf'])
    frame_hidden = node('Reshape',[frame_hidden,const('frame_hidden_shape',np.array([1,1,model.hidden],np.int64))],'frame_hidden_broadcast')
    option_hidden = project('option',spec.option_numeric,spec.option_categories,p['wo'])
    if spec.relations:
        from .neural_relations import export_relation_hidden
        offset=feature_width(spec.option_numeric,spec.option_categories)
        relations=export_relation_hidden(node,const,p['wo'][offset:],float_type=TensorProto.FLOAT)
        option_hidden=node('Add',[option_hidden,relations],'option_with_relations')
    combined = node('Add',[frame_hidden,option_hidden],'combined')
    z1 = node('Add',[combined,const('b1',p['b1'])],'z1')
    h1 = node('Clip',[z1,zero,six],'h1')
    linear2 = node('MatMul',[h1,const('w2',p['w2'])],'linear2')
    z2 = node('Add',[linear2,const('b2',p['b2'])],'z2')
    h2 = node('Clip',[z2,zero,six],'h2')
    linear3 = node('MatMul',[h2,const('w3',p['w3'])],'linear3')
    logits = node('Add',[linear3,const('b3',p['b3'])],'logits')
    logits = node('Clip',[logits,const('score_min',np.float32(-100000)),const('score_max',np.float32(100000))],'bounded_scores')
    scaled = node('Mul',[logits,const('score_scale',np.float32(10000))],'scaled_scores')
    scores = node('Cast',[scaled],'scores_i32',to=TensorProto.INT32)
    scores = node('Reshape',[scores,const('score_shape',np.array([1,max_options],np.int64))],'reshaped_scores')
    mask = node('Greater',['option_mask_i32',const('zero_i32',np.int32(0))],'valid_mask')
    node('Where',[mask,scores,const('masked_score',np.int32(-2000000000))],'option_scores')
    count = node('Gather',['frame_i32',const('count_col',np.array([count_frame_column],np.int64))],'count',axis=1)
    node('Reshape',[count,const('count_shape',np.array([1],np.int64))],'desired_count')
    inputs = [helper.make_tensor_value_info(name,TensorProto.INT32,shape) for name,shape in [
        ('frame_i32',[1,spec.frame_width]),('frame_presence_i32',[1,spec.frame_width]),
        ('option_i32',[1,max_options,spec.option_width]),('option_presence_i32',[1,max_options,spec.option_width]),
        ('option_mask_i32',[1,max_options]),
    ]]
    outputs = [helper.make_tensor_value_info('option_scores',TensorProto.INT32,[1,max_options]),
               helper.make_tensor_value_info('desired_count',TensorProto.INT32,[1])]
    graph = helper.make_graph(nodes,'ptcg-state-conditioned-neural-bc',inputs,outputs,initializer=initializers)
    document = helper.make_model(graph,opset_imports=[helper.make_opsetid('',18)]); document.ir_version = 10
    onnx.checker.check_model(document,full_check=True)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(document.SerializeToString())
    return {'bytes':path.stat().st_size,'operators':sorted({n.op_type for n in nodes}),
            'parameter_count':sum(value.size for value in p.values())}
