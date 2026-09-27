"""Low-capacity outcome correction: update only the 48-value output head.

Inputs/hidden representation remain frozen. Paired terminal outcomes are samples,
not oracle labels; zero differences are omitted rather than declared equivalent.
"""
import copy
import math
import numpy as np
from .neural_actor import listwise_loss_gradient, positive_labels


def pair_loss_gradient(scores, preferred, rejected):
    if (type(preferred) is not int or type(rejected) is not int or preferred==rejected
        or not 0<=preferred<len(scores) or not 0<=rejected<len(scores)
        or not np.isfinite(scores).all()):raise ValueError('preference_pair_invalid')
    margin=float(scores[preferred]-scores[rejected])
    loss=float(np.logaddexp(0.,-margin))
    probability=math.exp(-float(np.logaddexp(0.,margin)))
    gradient=np.zeros_like(scores);gradient[preferred]=-probability;gradient[rejected]=probability
    return loss,gradient


def task_checkpoint_admitted(row, initial, tolerance):
    return (row['training_pair_accuracy']==1. and row['validation_pair_accuracy'] is not None
            and initial['validation_pair_accuracy'] is not None
            and row['validation_pair_accuracy']>=initial['validation_pair_accuracy']
            and row['validation_bc_accuracy']>=initial['validation_bc_accuracy']-tolerance)


def fit_head(model, bc, preferences, *, weight, epochs=20, seed=260921,
             checkpoint_policy='combined_loss',retention_tolerance=.02):
    if not 0<weight<=4 or not preferences:raise ValueError('preference_training_empty_or_weight_invalid')
    if checkpoint_policy not in ('combined_loss','task_first') or not 0<=retention_tolerance<=.02:
        raise ValueError('preference_checkpoint_policy_invalid')
    frozen={k:v.copy() for k,v in model.parameters.items() if k!='w3'}
    def hidden(e):return model.forward(*model.encode(e))[1][-1]
    retention=[(hidden(e),positive_labels(e,len(e['options'])),e['split']) for e in bc]
    pairs=[(hidden(e),e['preferred'],e['rejected'],e['split']) for e in preferences]
    train=[r for r in retention if r[2]=='train'];valid=[r for r in retention if r[2]=='validation']
    ptr=[r for r in pairs if r[3]=='train'];pval=[r for r in pairs if r[3]=='validation']
    if not train or not valid or not ptr:raise ValueError('preference_training_split_empty')
    head=model.parameters['w3'];m=np.zeros_like(head);v=m.copy();rng=np.random.default_rng(seed)
    def metrics():
        losses=[];correct=0
        for h,label,_ in valid:
            score=(h@head).reshape(-1);losses.append(listwise_loss_gradient(score,label)[0]);correct+=int(np.argmax(score) in label)
        pl=[pair_loss_gradient((h@head).reshape(-1),a,b)[0] for h,a,b,_ in pval]
        trainpl=[pair_loss_gradient((h@head).reshape(-1),a,b)[0] for h,a,b,_ in ptr]
        def pair_accuracy(rows):
            return sum(float((h@head)[a,0])>float((h@head)[b,0]) for h,a,b,_ in rows)/len(rows) if rows else None
        return dict(validation_bc_loss=float(np.mean(losses)),validation_bc_accuracy=correct/len(valid),
                    validation_pair_loss=float(np.mean(pl)) if pl else None,training_pair_loss=float(np.mean(trainpl)),
                    training_pair_accuracy=pair_accuracy(ptr),validation_pair_accuracy=pair_accuracy(pval))
    initial=metrics();best=copy.deepcopy(head);best_epoch=0
    if checkpoint_policy=='task_first':best_epoch=None
    def objective(r):return r['validation_bc_loss']+weight*(r['validation_pair_loss'] or 0)
    best_value=objective(initial);step=0;history=[]
    for epoch in range(1,epochs+1):
        order=rng.permutation(len(train))
        for start in range(0,len(order),32):
            chosen=order[start:start+32];g=np.zeros_like(head)
            for index in chosen:
                h,label,_=train[int(index)];_,d=listwise_loss_gradient((h@head).reshape(-1),label)
                g+=h.T@d[:,None]/len(chosen)
            for index in rng.integers(0,len(ptr),size=8):
                h,a,b,_=ptr[int(index)];_,d=pair_loss_gradient((h@head).reshape(-1),a,b)
                g+=weight*(h.T@d[:,None])/8
            g*=min(1.,5/max(float(np.linalg.norm(g)),1e-8));step+=1
            m[:]=.9*m+.1*g;v[:]=.999*v+.001*g*g
            head-=.001*(m/(1-.9**step))/(np.sqrt(v/(1-.999**step))+1e-8)
            if not np.isfinite(head).all():raise ValueError('preference_training_nonfinite')
        r=dict(epoch=epoch,**metrics());history.append(r)
        admitted=(objective(r)<best_value if checkpoint_policy=='combined_loss' else
                  best_epoch is None and task_checkpoint_admitted(r,initial,retention_tolerance))
        if admitted:
            best_value=objective(r);best=head.copy();best_epoch=epoch
    if best_epoch is None:raise ValueError('preference_capability_gate_failed')
    head[:]=best
    for k,value in frozen.items():
        if not np.array_equal(value,model.parameters[k]):raise ValueError('preference_frozen_parameters_changed')
    return dict(initial=initial,**metrics(),best_epoch=best_epoch,epochs=epochs,history=history,
                checkpoint_policy=checkpoint_policy,retention_tolerance=retention_tolerance if checkpoint_policy=='task_first' else None,
                train_preferences=len(ptr),validation_preferences=len(pval),trained_parameters=head.size,
                parameter_count=sum(p.size for p in model.parameters.values()),preference_weight=weight)
