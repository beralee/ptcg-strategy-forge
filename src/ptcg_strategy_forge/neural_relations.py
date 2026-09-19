"""Relations of already-authorized semantic v1 tensors, never legality proofs.

Energy count minus printed minimum is not a typed attack-cost certificate.
Each value has a separate presence bit; unknown operands cannot become facts.
"""
import numpy as np

RELATIONS = (
    ('damage_margin','sub',('o',13),('o',8),.01),
    ('energy_count_margin','sub',('o',10),('o',25),.25),
    ('available_attachment_debt','mul',('f',22),('o',11),.25),
    ('available_attachment_ready','mul',('f',22),('o',12),1.),
    ('target_prize_margin','sub',('o',15),('f',1),.5),
    ('hand_copy_surplus','sub',('o',17),('c',1),.25),
    ('ready_attacker_surplus','sub',('f',15),('c',1),.5),
    ('prize_race_margin','sub',('f',1),('f',2),.5),
)
RELATION_WIDTH = 2*len(RELATIONS)


def encode_relations(frame,frame_presence,options,option_presence):
    frame,frame_presence,options,option_presence=map(np.asarray,(frame,frame_presence,options,option_presence))
    n=len(options)
    def operand(ref):
        zone,col=ref
        if zone=='c':return np.full(n,col,np.float32),np.ones(n,np.float32)
        values,present=(frame,frame_presence) if zone=='f' else (options,option_presence)
        return np.broadcast_to(values[...,col],(n,)).astype(np.float32),np.broadcast_to(present[...,col],(n,)).astype(np.float32)
    values=[];presence=[]
    for _,op,a,b,scale in RELATIONS:
        av,ap=operand(a);bv,bp=operand(b);known=ap*bp
        raw=av-bv if op=='sub' else av*bv
        values.append(np.clip(raw*scale,-10,10)*known);presence.append(known)
    return np.stack(values+presence,axis=-1).astype(np.float32)


def export_relation_hidden(node,const,weights,*,float_type):
    """Use only the existing model operator allow-list and fixed input shapes."""
    one=const('rel_one',np.float32(1))
    minus=const('rel_minus',np.float32(-1));low=const('rel_low',np.float32(-10));high=const('rel_high',np.float32(10))
    cache={}
    def operand(ref):
        if ref in cache:return cache[ref]
        zone,col=ref;name=f'rel_{zone}{col}'
        if zone=='c':
            cache[ref]=(const(name,np.float32(col)),one)
            return cache[ref]
        prefix='frame' if zone=='f' else 'option'
        index=const(name+'_col',np.array([col],np.int64));parts=[]
        for field,suffix in ((prefix+'_i32','v'),(prefix+'_presence_i32','p')):
            value=node('Gather',[field,index],name+'_'+suffix+'_raw',axis=-1)
            value=node('Cast',[value],name+'_'+suffix+'_float',to=float_type)
            if zone=='f':value=node('Reshape',[value,const(name+'_'+suffix+'_shape',np.array([1,1,1],np.int64))],name+'_'+suffix+'_broadcast')
            parts.append(value)
        cache[ref]=tuple(parts);return cache[ref]
    result=None
    for i,(name,op,a,b,scale) in enumerate(RELATIONS):
        name='rel_'+name;av,ap=operand(a);bv,bp=operand(b)
        known=node('Mul',[ap,bp],name+'_known')
        if op=='sub':
            negative=node('Mul',[bv,minus],name+'_negative')
            raw=node('Add',[av,negative],name+'_raw')
        else:raw=node('Mul',[av,bv],name+'_raw')
        scaled=node('Mul',[raw,const(name+'_scale',np.float32(scale))],name+'_scaled')
        clipped=node('Clip',[scaled,low,high],name+'_clipped')
        value=node('Mul',[clipped,known],name+'_value')
        for field,row,label in ((value,i,'v'),(known,i+len(RELATIONS),'p')):
            hidden=node('MatMul',[field,const(name+'_'+label+'_w',weights[row:row+1])],name+'_'+label+'_hidden')
            result=hidden if result is None else node('Add',[result,hidden],name+'_'+label+'_sum')
    return result
