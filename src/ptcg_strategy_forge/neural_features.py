"""Versioned BC encodings; public identity hashes are categorical only."""
from .neural_actor import FeatureSpec
from scripts.ai.ptcgdap.semantic_model_profile import KINDS, PROFILE_ID as V1
from scripts.ai.ptcgdap.semantic_model_profile_v2 import PROFILE_ID as V2


def build_feature_spec(data, *, relations=False):
    profile = data.get('tensor_profile_id', V1)
    if profile not in (V1, V2): raise ValueError('model_tensor_profile_invalid')
    fw, ow = (416,48) if profile == V2 else (128,32)
    for e in data.get('examples',[]):
        if len(e['frame'])!=fw or len(e['frame_presence'])!=fw or any(len(row)!=ow for row in e['options']+e['option_presence']):
            raise ValueError('neural_dataset_profile_shape_invalid')
    uid_codes=list(range(len(data['uid_vocabulary'])+1))
    fc={19:list(range(49)),20:list(range(11)),24:uid_codes,25:uid_codes,26:uid_codes,31:list(range(1,len(KINDS)+1))}
    oc={0:list(range(1,len(KINDS)+1)),1:uid_codes,2:uid_codes,3:uid_codes,4:list(range(12)),6:list(range(8)),7:list(range(8)),21:list(range(8)),22:list(range(10)),29:list(range(17))}
    fn={i:1.0 for i in range(128) if i not in fc}; on={i:1.0 for i in range(32) if i not in oc}
    for i in (0,3,4,5,6): fn[i]=0.05
    for i in (9,10): fn[i]=0.01
    for i in (13,14,29,30): fn[i]=0.1
    for i in range(32,128): fn[i]=0.25
    for i in (8,13): on[i]=0.01
    for i in (9,11,25,26): on[i]=0.1
    if profile == V2:
        train=[e for e in data['examples'] if e['split']=='train']
        def vocabulary(columns, option=False):
            values={0}
            for e in train:
                rows=zip(e['options'],e['option_presence']) if option else [(e['frame'],e['frame_presence'])]
                for row,presence in rows:
                    values.update(row[c] for c in columns if presence[c])
            return sorted(values)
        identity_cols=[128+16*s+c for s in range(18) for c in (0,11)]
        energy_cols=[128+16*s+14 for s in range(18)]
        identities=sorted(set(vocabulary(identity_cols)+vocabulary([35,38,39,40],True)))
        energies=sorted(set(vocabulary(energy_cols)+vocabulary([41,45],True)))
        for s in range(18):
            start=128+16*s
            fc.update({start:identities,start+1:uid_codes,start+11:identities,start+14:energies})
            for c in range(16):
                if start+c not in fc:fn[start+c]=0.01 if c in (2,3) else 0.1 if c in (4,5,6,10) else 1.0
        oc.update({32:uid_codes,35:identities,38:identities,39:identities,40:identities,41:energies,43:list(range(18)),45:energies,46:list(range(18))})
        for c in range(32,48):
            if c not in oc:on[c]=0.01 if c==36 else 0.1 if c==34 else 1.0
    return FeatureSpec(fw,ow,fn,on,fc,oc,relations='public_resource_relations_v1' if relations else '')


def _feature_keys(numeric,categories,relations=''):
    keys=[('number',c,numeric[c]) for c in sorted(numeric)]
    keys += [('presence',c) for c in sorted(numeric)]
    keys += [('category',c,value) for c,values in sorted(categories.items()) for value in values]
    if relations:
        from .neural_relations import RELATION_WIDTH
        keys += [('relation',relations,i) for i in range(RELATION_WIDTH)]
    return keys


def initialize_from_parent(child,parent):
    """Copy matching semantic channels and zero only newly introduced channels."""
    if (child.hidden,child.bottleneck)!=(parent.hidden,parent.bottleneck):
        raise ValueError('neural_parent_architecture_mismatch')
    for key in ('wf','wo'):
        side='frame' if key=='wf' else 'option'
        def keys(spec):return _feature_keys(getattr(spec,side+'_numeric'),getattr(spec,side+'_categories'),spec.relations if side=='option' else '')
        previous=keys(parent.spec);current=keys(child.spec);mapping={v:i for i,v in enumerate(current)}
        if any(k not in mapping for k in previous):raise ValueError('neural_parent_features_missing')
        child.parameters[key].fill(0)
        for i,k in enumerate(previous):child.parameters[key][mapping[k]]=parent.parameters[key][i]
    for key in ('b1','w2','b2','w3','b3'):child.parameters[key][:]=parent.parameters[key]


def load_ranker(path):
    import json
    import numpy as np
    from pathlib import Path
    from .neural_actor import NeuralRanker
    path=Path(path);metadata=json.loads(path.with_suffix('.json').read_bytes());spec=metadata['spec']
    for key in ('frame_numeric','option_numeric','frame_categories','option_categories'):
        spec[key]={int(k):v for k,v in spec[key].items()}
    model=NeuralRanker(FeatureSpec(**spec),hidden=metadata['hidden'],bottleneck=metadata['bottleneck'])
    with np.load(path,allow_pickle=False) as values:
        if set(values.files)!=set(model.parameters):raise ValueError('neural_parent_parameters_invalid')
        for key,value in model.parameters.items():
            if values[key].shape!=value.shape or not np.isfinite(values[key]).all():raise ValueError('neural_parent_parameters_invalid')
            value[:]=values[key]
    return model
